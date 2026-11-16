# PolicyLens

**An LLM reads the policy. Plain code decides the payout.**

PolicyLens takes a health insurance policy document, extracts the coverage terms with a page number and a verbatim
quote for each one, and then computes the expected payout for a hospital bill with a deterministic rules engine.
The model never makes a money decision, and every rupee in the result has a line in an audit trail.

![Estimating a claim: the payout and the nine-step audit trail](docs/screenshots/03-estimate.png)

Everything in this repo is synthetic. The sample and evaluation policies were written for this project and the
insurers in them are fictional.

**Contents:** [What it does](#what-it-does) · [Worked example](#worked-example) ·
[Why two halves](#why-the-llm-and-the-rules-engine-are-separate) · [Screens](#the-three-screens) ·
[Eval results](#eval-results) · [Run it](#run-it) · [API](#api) · [Repo layout](#repo-layout) ·
[Limitations](#limitations)

## What it does

1. **Read.** Upload a policy (PDF or pasted text). A language model returns a structured `PolicyCoverage`: sum
   insured, room rent cap, ICU cap, co-pay, deductible, waiting periods, sub-limits, exclusions. Each value carries
   `source_page`, `source_quote` and a confidence.
2. **Check.** The server verifies that every quote really appears on the page it cites. A value is flagged for
   human review when its confidence is under the threshold (default 0.7) or when its quote cannot be found.
3. **Decide.** Enter a procedure and an itemised bill. The rules engine applies the policy in a fixed order and
   returns what the insurer pays, what the patient pays, and the amount before and after every rule.

## Worked example

Policy: Harbor Shield "Care Basic" (synthetic). Sum insured ₹5,00,000, room rent capped at 1% of the sum insured
per day, cataract sub-limit ₹40,000, 10% co-pay. The patient has a cataract admission of 3 days, a room at ₹8,000
a day, and a bill of ₹91,000. This is the engine's actual output, shown in the screenshot above:

| # | Rule | What happened | Amount after |
|---|---|---|---|
| 1 | Bill as submitted | Sum of itemised charges | ₹91,000.00 |
| 2 | Waiting period | Policy age 800 days, cataract wait 730 days: complete | ₹91,000.00 |
| 3 | Exclusions | Cataract is not excluded | ₹91,000.00 |
| 4 | Room rent cap | Cap ₹5,000 / room ₹8,000 = 0.6250, applied to room, doctor and OT charges only | ₹65,875.00 |
| 5 | ICU cap | No ICU stay billed | ₹65,875.00 |
| 6 | Sub-limit | Cataract limit ₹40,000 | ₹40,000.00 |
| 7 | Deductible | None | ₹40,000.00 |
| 8 | Co-payment | 10%, insurer pays 90% | ₹36,000.00 |
| 9 | Sum insured ceiling | Remaining ₹5,00,000 covers it | ₹36,000.00 |

Insurer pays **₹36,000**, the patient pays ₹55,000. The step that surprises people is step 4: a room costing more
than the cap also scales the doctor and theatre charges, which is why ₹25,125 disappears before the sub-limit is
even looked at.

## Why the LLM and the rules engine are separate

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

A language model is good at reading messy documents and bad at arithmetic you have to defend. A payout is the
second kind of problem. Keeping them apart gives three things:

1. **Auditability.** The payout is a fixed sequence of rules (waiting period, exclusions, room rent cap with
   proportionate deduction, sub-limit, deductible, co-pay, sum insured). Each step shows its inputs and the amount
   before and after. Same inputs, same answer, every time.
2. **Testability.** The engine has unit tests with exact `Decimal` expectations. The extractor is measured with an
   eval set instead, because its failures are statistical.
3. **A place for a human.** The only uncertain part is extraction, and it reports its own uncertainty. A reviewer
   checks the flagged values, not the arithmetic.

The split is enforced, not just intended: `engine/` imports no LLM or network code, and a test fails if it ever
does.

## The three screens

One interface for the analyst who reviews and the engineer who reads the code. Add a policy, review what was
extracted next to the source text, then estimate a claim.

| Add a policy | Review coverage (source quote and page highlight) |
|---|---|
| ![Add a policy screen](docs/screenshots/01-add-policy.png) | ![Extracted coverage, with the ICU cap row expanded to show its quote](docs/screenshots/02-coverage.png) |

The estimate screen is responsive; the audit trail stays readable at phone width.

<img src="docs/screenshots/04-estimate-mobile.png" alt="Estimate screen on a 390 pixel wide phone" width="320">

Design notes are in [DESIGN.md](DESIGN.md) and the product brief in [PRODUCT.md](PRODUCT.md). Money is shown with
Indian digit grouping (₹10,00,000) and travels through the API as decimal strings, never floats.

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
  model did not flag it. **On this set the review flag has not been shown to catch errors.**
- **A known miss.** The sample "Lakeview family floater" states a co-pay of "20% for insured persons aged 60 and
  above, and for all claims at non-network hospitals". The engine models a flat co-pay, so this is a conditional term
  it cannot represent. In one manual run the model flagged that value at 60% confidence; in another run (the coverage
  screenshot above) it returned a flat 20% at 100% with no flag. Treat conditional terms as something a person must
  read.

## Run it

Needs Python 3.12 or newer (developed on 3.13) and Node 20 or newer.

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # Linux and macOS: .venv/bin/pip
cp .env.example .env                        # set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Any OpenAI-compatible chat-completions endpoint works (OpenAI, Groq, OpenRouter, a local Ollama or vLLM). The client
asks for `response_format: json_object`, validates the reply with Pydantic, retries once with the validation error,
and after that keeps the fields that validate and marks the rest as unknown with confidence 0. HTTP 429 and 5xx are
retried with backoff. The rules engine needs no LLM at all: `POST /estimate` works on any stored policy.

UI, in development with hot reload:

```bash
cd web && npm install && npm run dev        # http://localhost:5173, proxies to :8000
```

UI, built and served by the API on one port: `cd web && npm run build`, then open http://localhost:8000.

Docker (API and UI in one image; Postgres is optional). The compose file is validated but the image build has not
been run on the author's machine:

```bash
docker compose up --build                       # SQLite
docker compose --profile postgres up --build    # with Postgres: put DATABASE_URL=postgresql+psycopg://policylens:policylens@postgres:5432/policylens in .env
```

### Protecting the LLM key

Reading a policy spends your LLM key, so on a public server that endpoint is guarded. Estimating a claim uses no
model and stays open.

1. Set `ADMIN_TOKEN` in `.env` (16+ random characters). With it empty there is no login, which is fine locally and
   wrong for a public server.
2. Get the current access code on the server: `python -m app.access` (in Docker:
   `docker compose exec api python -m app.access`). It prints something like `AJXJ-YOQA` and when it stops working.
   The code is derived from `ADMIN_TOKEN` and the current UTC hour, so it changes on the hour and nobody can compute
   it without the token. `--next` prints the next hour's code.
3. A visitor enters the code on the Add a policy screen. The server trades it for a signed session token that lasts
   one hour. Without a valid token, `POST /policies` returns 401.

Limits, all returning 429 with `Retry-After`:

| What | Default | Setting |
|---|---|---|
| Extractions per client IP per hour | 5 | `EXTRACTIONS_PER_HOUR` |
| Extractions across everyone, rolling 24 h (the spend ceiling) | 100 | `LLM_DAILY_LIMIT` |
| Login attempts per IP per 15 min | 10 | fixed |
| Estimates per IP per minute | 120 | fixed |

What this does not do:

- It limits who can spend the key and how much. It does not protect a key that leaks some other way (a committed
  `.env`, a shared screenshot, logs). Keep `.env` out of git and images (both are already excluded here), rotate the
  key if it ever appears anywhere, and set a spend cap at your LLM provider as the real backstop.
- Whoever has the code can use it until it changes, and a session lasts an hour after login, so a code shared late in
  the hour can be used for up to about two more hours.
- Counters are in memory: they reset when the server restarts and are not shared between workers. Run one worker.
- Behind a reverse proxy set `TRUST_PROXY=1` so the real client IP is used; without a proxy leave it empty, because
  otherwise the header can be forged.
- The key itself is only ever sent to the LLM provider. No endpoint returns it, and provider error details stay in the
  server log instead of the HTTP response.

Tests and lint:

```bash
.venv/Scripts/python -m pytest              # 79 tests
.venv/Scripts/python -m ruff check .
cd web && npm run typecheck
```

## API

| Method and path | Purpose |
|---|---|
| `POST /auth/login` | `{code}`: the hourly access code. Returns a one-hour bearer token. Only when `ADMIN_TOKEN` is set. |
| `POST /policies` | Multipart `file` (PDF or text) or `text`. Needs the bearer token when `ADMIN_TOKEN` is set. Returns the coverage, page texts, `needs_human_review` and `review_fields`. |
| `GET /policies/{id}` | The stored policy. The review flags are recomputed with the current threshold. |
| `POST /estimate` | `{policy_id, scenario}`. Returns payable, patient pays and the audit trail. Money is a decimal string. |
| `GET /samples` | The three synthetic sample policies. |
| `GET /health` | Liveness, whether an LLM is configured, and whether an access code is required. |

Pasted text marks pages with a line such as `--- Page 2 ---`. Without markers it is read as page 1.

## Repo layout

```
app/       FastAPI service: PDF text, LLM client, extraction, quote checks, storage
engine/    the rules engine (Decimal only, no LLM or network imports) and its assumptions in engine/README.md
evals/     10 hand-labelled synthetic policies, scoring, and the CLI (python -m evals.run)
samples/   three synthetic policies used by the UI
tests/     pytest: extraction with a stub LLM, engine edge cases, API, purity check, eval scoring
web/       Vite + React + TypeScript UI
docs/      README screenshots
```

## Limitations

- **The engine is a simplified model of a policy.** Its assumptions are listed in
  [engine/README.md](engine/README.md): inclusive waiting boundaries, a flat co-pay only, no accumulation of
  deductibles or sub-limits across claims, no floater or restoration logic, and exact-name matching of procedures.
- **The list of charges scaled by proportionate deduction is an assumption** drawn from secondary articles about IRDAI
  rules, not from the circular. Check it against the policy wording.
- **Conditional terms are not modelled.** A co-pay that depends on age or hospital type is extracted as one number;
  the engine would apply it to every claim (see the known miss above).
- **No OCR.** Scanned PDFs return no text and are rejected.
- **Page numbers come from the PDF page order,** not the printed page numbers.
- **Extraction depends on the model.** Quotes are checked against the page, but a correct quote can still support a
  wrong reading of it.
- **Evaluation is small and in-house** (see above). There are no real insurer documents in the repo and none were used.
- **Docker and Postgres are untested** on the author's machine.
- **Access is one shared hourly code, not user accounts.** There are no users, roles or audit of who did what, and
  no payments. The `/estimate` result is an estimate, not a claim decision.
