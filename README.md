# PolicyLens

An LLM reads a health insurance policy and extracts the coverage terms, each with a page number and a verbatim quote.
A deterministic rules engine then computes the expected claim payout for a hospital bill.
The model never makes a money decision, and every rupee in the result has a line in an audit trail.

Built as a portfolio project. Everything in the repo is synthetic: the sample and evaluation policies are written for
this project, and the insurers in them are fictional.

## Architecture

```mermaid
flowchart LR
    subgraph read["Reads (LLM, may be wrong, always cited)"]
        D[Policy PDF or text] --> P[Page splitter]
        P --> L[LLM extractor<br/>JSON, validate, retry once]
        L --> V[Quote check<br/>is the quote on the cited page?]
        V --> C[(PolicyCoverage<br/>value, page, quote, confidence)]
    end
    C --> H{Confidence below threshold<br/>or quote not found?}
    H -- yes --> F[Flagged: needs human review]
    subgraph decide["Decides (plain code, no LLM imports)"]
        S[Scenario: procedure, days, charges] --> E[Rules engine<br/>Decimal arithmetic]
        C --> E
        E --> R[Payable, patient pays,<br/>audit trail]
    end
```

- `app/` FastAPI service, PDF text, LLM client, extraction, storage.
- `engine/` the rules engine. It imports no LLM or network code; a test fails if it ever does.
- `evals/` hand-labelled golden set and the scoring CLI.
- `web/` Vite, React and TypeScript UI with three screens: add a policy, review extracted coverage, estimate a claim.

## Why the LLM and the rules engine are separate

A language model is good at reading messy documents and bad at arithmetic you have to defend. A payout is the
second kind of problem. Keeping them apart gives three things:

1. **Auditability.** The payout is a fixed sequence of rules (waiting period, exclusions, room rent cap with
   proportionate deduction, sub-limit, deductible, co-pay, sum insured). Each step shows its inputs and the amount
   before and after. Same inputs, same answer, every time.
2. **Testability.** The engine has unit tests with exact `Decimal` expectations. The extractor is measured with an
   eval set instead, because its failures are statistical.
3. **A place for a human.** The only uncertain part is extraction, and it reports its own uncertainty: a value is
   flagged when its confidence is under the threshold (default 0.7) or when its quote cannot be found on the page it
   cites. A reviewer checks those values, not the arithmetic.

## Eval results

Run it yourself: `python -m evals.run` (needs `LLM_*` set, see below). It fails with an error if no LLM is
configured; there is no offline mode that could print made-up numbers.

<!-- EVAL:START -->
Model `openai/gpt-oss-120b`, 10 synthetic policies, run 2026-11-16, review threshold 0.7.

| Metric | Result |
|---|---|
| Field-level accuracy | 99.8% |
| Accuracy on fields NOT flagged for review | 99.8% |
| Citation validity (157 quotes) | 98.1% |
| Fields flagged low-confidence | 3.6% |
| Wrong fields that were flagged | 0 of 1 |
<!-- EVAL:END -->

How to read these numbers:

- **Field-level accuracy** is the mean over 11 fields per policy. Numbers must match exactly (caps compare kind and
  amount). Lists (sub-limits, specific illnesses, exclusions) score F1; two items match when their words are equal or
  one contains the other, so "cosmetic surgery" matches "cosmetic or plastic surgery for appearance". For
  co-pay and deductible, "none" and 0 are the same.
- **Citation validity** is recomputed from the page text by the eval script: the quote must appear on the cited page
  (case and punctuation ignored, whole words).
- **Fields flagged** is the share of the 11 fields where at least one value needs review.
- These are a small set: 10 policies, 110 fields. The policies were written and labelled by the same author, in
  fairly regular layouts, so the accuracy here is an upper bound for real documents, not an estimate of them. One run
  is reported; results move a little between runs even at temperature 0.
- Accuracy on unflagged fields is almost the same as overall accuracy because there was one wrong field and the
  model did not flag it. On this set the flag has not been shown to catch errors. It has caught a conditional co-pay
  in a sample policy ("20% for insureds aged 60 and above") in manual use, which is the case it is meant for.

## Run it

Needs Python 3.12 or newer (developed on 3.13), Node 20 or newer.

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # Linux and macOS: .venv/bin/pip
cp .env.example .env                        # set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Any OpenAI-compatible chat-completions endpoint works (OpenAI, Groq, OpenRouter, a local Ollama or vLLM). The client
asks for `response_format: json_object`, validates the reply with Pydantic, retries once with the validation error,
and after that keeps the fields that validate and marks the rest as unknown with confidence 0. HTTP 429 and 5xx are
retried with backoff.

UI, in development with hot reload:

```bash
cd web && npm install && npm run dev        # http://localhost:5173, proxies to :8000
```

UI, built and served by the API on one port: `cd web && npm run build`, then open http://localhost:8000.

Docker (API and UI in one image; Postgres is optional):

```bash
docker compose up --build                       # SQLite
docker compose --profile postgres up --build    # with Postgres: put DATABASE_URL=postgresql+psycopg://policylens:policylens@postgres:5432/policylens in .env
```

Tests and lint:

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
cd web && npm run typecheck
```

API:

| Method and path | Purpose |
|---|---|
| `POST /policies` | Multipart `file` (PDF or text) or `text`. Returns the coverage, page texts, and `review_fields`. |
| `GET /policies/{id}` | The stored policy. The review flags are recomputed with the current threshold. |
| `POST /estimate` | `{policy_id, scenario}`. Returns payable, patient pays and the audit trail. Money is a decimal string. |
| `GET /samples` | The three synthetic sample policies. |

Pasted text marks pages with a line such as `--- Page 2 ---`. Without markers it is read as page 1.

## Limitations

- **The engine is a simplified model of a policy.** Its assumptions are listed in
  [engine/README.md](engine/README.md): inclusive waiting boundaries, a flat co-pay only, no accumulation of
  deductibles or sub-limits across claims, no floater or restoration logic, and exact-name matching of procedures.
- **The list of charges scaled by proportionate deduction is an assumption** drawn from secondary articles about IRDAI
  rules, not from the circular. Check it against the policy wording.
- **Conditional terms are not modelled.** A co-pay that depends on age or hospital type is extracted as a number with
  low confidence at best; the engine would apply it to every claim.
- **No OCR.** Scanned PDFs return no text and are rejected.
- **Page numbers come from the PDF page order,** not the printed page numbers.
- **Extraction depends on the model.** Quotes are checked against the page, but a correct quote can still support a
  wrong reading of it.
- **Evaluation is small and in-house** (see above). There are no real insurer documents in the repo and none were used.
- **No auth, no multi-user concerns, no payments.** The `/estimate` result is an estimate, not a claim decision.
