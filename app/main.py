import logging
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import access
from app.config import get_settings
from app.db import Policy, get_session
from app.extract import annotate_review, extract_policy
from app.llm import LLMError, LLMNotConfigured, get_llm
from app.pdf import pdf_pages, split_pages
from app.ratelimit import client_ip, limiter
from app.schema import PolicyCoverage, iter_cited
from engine import EngineError, EstimateRequest, EstimateResult, estimate

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PAGES = 60
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

log = logging.getLogger("policylens")
access.check_config()
app = FastAPI(title="PolicyLens", version="0.1.0")


def guard_llm(request: Request, authorization: str | None = Header(None)):
    """Everything that can spend the LLM key goes through here: code, per-IP limit, global cap."""
    access.require_session(authorization)
    s = get_settings()
    limiter.check(f"llm:{client_ip(request)}", s.extractions_per_hour, 3600, "extractions")
    limiter.check("llm:all", s.llm_daily_limit, 86_400, "extractions today (daily cap reached)")


def guard_estimate(request: Request):
    # Cheap (no LLM), but still bounded.
    limiter.check(f"est:{client_ip(request)}", 120, 60)


class LoginIn(BaseModel):
    code: str


class PolicyOut(BaseModel):
    id: str
    created_at: datetime
    source_name: str | None
    model: str
    pages: list[str]
    coverage: PolicyCoverage
    needs_human_review: bool
    review_fields: list[str]  # paths of fields flagged "needs human review"


def _out(row: Policy) -> PolicyOut:
    cov = annotate_review(
        PolicyCoverage.model_validate(row.coverage), get_settings().review_threshold
    )
    flagged = [p for p, c in iter_cited(cov) if c.needs_review]
    return PolicyOut(
        id=row.id,
        created_at=row.created_at,
        source_name=row.source_name,
        model=row.model,
        pages=row.pages,
        coverage=cov,
        needs_human_review=bool(flagged),
        review_fields=flagged,
    )


@app.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "llm_configured": bool(s.llm_api_key), "auth_required": bool(s.admin_token)}


@app.post("/auth/login")
def login(body: LoginIn, request: Request):
    """Trade the current hourly access code for a one-hour session token."""
    if not get_settings().admin_token:
        raise HTTPException(404, "Access codes are not enabled on this server.")
    limiter.check(f"login:{client_ip(request)}", 10, 900, "login attempts")
    if not access.verify_code(body.code):
        raise HTTPException(401, "That access code is not valid. Codes change every hour.")
    token, exp = access.issue_session()
    return {"token": token, "expires_at": exp}


@app.post(
    "/policies", response_model=PolicyOut, status_code=201, dependencies=[Depends(guard_llm)]
)
def create_policy(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    session: Session = Depends(get_session),
):
    if bool(file) == bool(text and text.strip()):
        raise HTTPException(
            422, "Send either a PDF/text `file` or pasted `text`, not both or neither."
        )
    if file:
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File is larger than 10 MB.")
        name = file.filename
        try:
            is_pdf = data[:5] == b"%PDF-"
            pages = pdf_pages(data) if is_pdf else split_pages(data.decode("utf-8"))
        except Exception as e:
            raise HTTPException(422, f"Could not read the file as a PDF or UTF-8 text: {e}") from e
    else:
        name, pages = None, split_pages(text)
    if not any(pages):
        raise HTTPException(422, "No text found in the document (scanned PDFs need OCR first).")
    if len(pages) > MAX_PAGES:
        raise HTTPException(422, f"Document has {len(pages)} pages; the limit is {MAX_PAGES}.")

    try:
        llm = get_llm()
        coverage = extract_policy(pages, llm)
    except LLMNotConfigured as e:
        raise HTTPException(503, str(e)) from e
    except LLMError as e:
        log.warning("LLM request failed: %s", e)  # detail stays in the server log, not the response
        raise HTTPException(502, "The language model request failed. Try again shortly.") from e

    row = Policy(
        source_name=name, model=llm.model, pages=pages, coverage=coverage.model_dump(mode="json")
    )
    session.add(row)
    session.commit()
    return _out(row)


@app.get("/policies/{policy_id}", response_model=PolicyOut)
def get_policy(policy_id: str, session: Session = Depends(get_session)):
    row = session.get(Policy, policy_id)
    if not row:
        raise HTTPException(404, "Policy not found.")
    return _out(row)


@app.post("/estimate", response_model=EstimateResult, dependencies=[Depends(guard_estimate)])
def post_estimate(req: EstimateRequest, session: Session = Depends(get_session)):
    row = session.get(Policy, req.policy_id)
    if not row:
        raise HTTPException(404, "Policy not found.")
    try:
        return estimate(PolicyCoverage.model_validate(row.coverage), req.scenario)
    except EngineError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/samples")
def list_samples():
    return [
        {"name": p.stem, "text": p.read_text(encoding="utf-8")}
        for p in sorted(SAMPLES_DIR.glob("*.txt"))
    ]


if WEB_DIST.is_dir():  # single-container deploy: the API also serves the built UI
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
