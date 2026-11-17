import logging
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import current_user
from app.config import get_settings
from app.extract import annotate_review, extract_policy
from app.llm import LLMError, LLMNotConfigured, get_llm
from app.pdf import pdf_pages, split_pages
from app.ratelimit import client_ip, limiter
from app.schema import PolicyCoverage, iter_cited
from app.store import PolicyRecord, get_store
from engine import EngineError, EstimateRequest, EstimateResult, estimate

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PAGES = 60
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

log = logging.getLogger("policylens")
app = FastAPI(title="PolicyLens", version="0.1.0")


def guard_llm(request: Request):
    """Everything that can spend the LLM key goes through here: per-IP limit, then global cap."""
    s = get_settings()
    limiter.check(f"llm:{client_ip(request)}", s.extractions_per_hour, 3600, "extractions")
    limiter.check("llm:all", s.llm_daily_limit, 86_400, "extractions today (daily cap reached)")


def guard_estimate(request: Request):
    # Cheap (no LLM), but still bounded.
    limiter.check(f"est:{client_ip(request)}", 120, 60)


class PolicyOut(BaseModel):
    id: str
    created_at: datetime
    source_name: str | None
    model: str
    pages: list[str]
    coverage: PolicyCoverage
    needs_human_review: bool
    review_fields: list[str]  # paths of fields flagged "needs human review"


def _out(row: PolicyRecord) -> PolicyOut:
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


class PolicySummary(BaseModel):
    id: str
    created_at: datetime
    source_name: str | None
    needs_human_review: bool


def _load(store, policy_id: str, user: str | None) -> PolicyRecord:
    """A policy made while signed in belongs to its owner; anyone else gets the same 404."""
    row = store.get(policy_id)
    if not row or (row.owner_id and row.owner_id != user):
        raise HTTPException(404, "Policy not found.")
    return row


@app.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "llm_configured": bool(s.llm_api_key)}


@app.post(
    "/policies", response_model=PolicyOut, status_code=201, dependencies=[Depends(guard_llm)]
)
def create_policy(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    store=Depends(get_store),
    user: str | None = Depends(current_user),
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

    row = PolicyRecord(
        source_name=name,
        model=llm.model,
        pages=pages,
        coverage=coverage.model_dump(mode="json"),
        owner_id=user,
    )
    store.add(row)
    return _out(row)


@app.get("/policies/{policy_id}", response_model=PolicyOut)
def get_policy(
    policy_id: str, store=Depends(get_store), user: str | None = Depends(current_user)
):
    return _out(_load(store, policy_id, user))


@app.get("/me/policies", response_model=list[PolicySummary])
def my_policies(store=Depends(get_store), user: str | None = Depends(current_user)):
    if not user:
        raise HTTPException(401, "Sign in to see your saved policies.")
    return [
        PolicySummary(
            id=p.id,
            created_at=p.created_at,
            source_name=p.source_name,
            needs_human_review=_out(p).needs_human_review,
        )
        for p in store.by_owner(user)
    ]


@app.post("/estimate", response_model=EstimateResult, dependencies=[Depends(guard_estimate)])
def post_estimate(
    req: EstimateRequest, store=Depends(get_store), user: str | None = Depends(current_user)
):
    row = _load(store, req.policy_id, user)
    try:
        return estimate(PolicyCoverage.model_validate(row.coverage), req.scenario)
    except EngineError as e:
        raise HTTPException(422, str(e)) from e


def _site_url(request: Request) -> str:
    """PUBLIC_URL when set (correct behind a proxy); else the URL this request came in on."""
    return get_settings().public_url or str(request.base_url).rstrip("/")


@app.get("/robots.txt", include_in_schema=False)
def robots(request: Request):
    body = f"User-agent: *\nAllow: /\n\nSitemap: {_site_url(request)}/sitemap.xml\n"
    return Response(body, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request):
    # One URL: the pages are #/hash routes, which search engines treat as the home page.
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{_site_url(request)}/</loc></url>\n"
        "</urlset>\n"
    )
    return Response(body, media_type="application/xml")


@app.get("/samples")
def list_samples():
    return [
        {"name": p.stem, "text": p.read_text(encoding="utf-8")}
        for p in sorted(SAMPLES_DIR.glob("*.txt"))
    ]


if WEB_DIST.is_dir():  # single-container deploy: the API also serves the built UI
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
