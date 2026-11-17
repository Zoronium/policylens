# PolicyLens

**An LLM reads the policy. Plain code decides the payout.**

PolicyLens takes a health insurance policy document, extracts the coverage terms with a page number and a verbatim
quote for each one, and then computes the expected payout for a hospital bill with a deterministic rules engine.
The model never makes a money decision, and every rupee in the result has a line in an audit trail.

![PolicyLens home page: the model reads, the rules decide, with a replayed recorded run](docs/screenshots/00-home.png)

Everything in this repo is synthetic. The sample and evaluation policies were written for this project and the
insurers in them are fictional.

**Contents:** [What it does](#what-it-does) · [Worked example](#worked-example) ·
[Why two halves](#why-the-llm-and-the-rules-engine-are-separate) · [The site](#the-site) ·
[The tool](#the-three-screens) ·
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

## The site

The web app has two kinds of page. **Home** and **How it works** explain the idea with animated demos and a mascot,
Lens. **Try it** is the working tool.

![How it works: the model reads and thinks with a token meter, the server checks quotes, plain code decides](docs/screenshots/01-how-it-works.png)

The demos replay **one recorded run**, not a simulation: a real extraction of the synthetic Harbor Shield sample
through `gpt-oss-120b` on Groq (1,051 tokens in, 863 spent thinking, 687 to write the answer, 2,601 in 4.2 seconds),
then the rules engine's real output for a ₹91,000 cataract bill. The model's reasoning text on the page is its own,
cut for length. All of it lives in one file, [web/src/site/recorded.ts](web/src/site/recorded.ts). One element is
invented and labelled as such on the page: the "Needs review" row in step 2 is a made-up misread quote, there to show
what a flag looks like. In the recorded run every quote was found.

- Home and How it works need neither the API nor an LLM key, so they can be hosted as plain static files
  (`npm run build` in `web/`, assets use relative URLs). Try it needs the API.
- The animated demos use the MIT-licensed [Stageshow](https://github.com/benjitaylor/skills) kit, copied into
  [web/src/stageshow](web/src/stageshow) with its licence. The copy leaves out the kit's bundled app-icon artwork,
  which is not MIT-licensed.
- The mascot is [web/src/site/Mascot.tsx](web/src/site/Mascot.tsx): a magnifier with a face, animated in CSS only.
  It also shows up in the "Reading the policy" wait inside the tool.
- Reduced-motion users get the finished frame of each demo instead of the animation.

## The three screens

The tool itself: add a policy, review what was extracted next to the source text, then estimate a claim. One
interface for the analyst who reviews and the engineer who reads the code.

| Add a policy | Review coverage (source quote and page highlight) |
|---|---|
| ![Add a policy screen](docs/screenshots/02-add-policy.png) | ![Extracted coverage, with the ICU cap row expanded to show its quote](docs/screenshots/03-coverage.png) |

![Estimating a claim: the payout and the nine-step audit trail](docs/screenshots/04-estimate.png)

Everything is responsive down to phone width; the home page is shown below at 390 px.

<img src="docs/screenshots/05-home-mobile.png" alt="Home page on a 390 pixel wide phone" width="320">

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
Pages are hash routes: `#/` home, `#/how` how it works, `#/try` add a policy, `#/p/<id>` and `#/p/<id>/estimate` for a
stored policy.

Docker (API and UI in one image; Postgres is optional). The image builds and starts on Coolify; the Postgres profile is
untested. The app is published on http://localhost:8100 (`HOST_PORT` changes the host side, `PORT` the container side):

```bash
docker compose up --build                       # SQLite
docker compose --profile postgres up --build    # with Postgres: put DATABASE_URL=postgresql+psycopg://policylens:policylens@postgres:5432/policylens in .env
```

### Accounts and saved policies

Optional. Sign-in is [Clerk](https://clerk.com) (email code, passkey or social, whichever you switch on in its
dashboard). Without the keys the site runs signed out, exactly as before.

- Anyone can still extract and estimate. Signing in only adds ownership: a policy extracted while signed in is stored
  with your Clerk user id, appears under **My policies**, and answers 404 to everyone else (including `/estimate`).
  A policy made signed out stays open to anyone who has its id, as before.
- The browser sends Clerk's session token as `Authorization: Bearer`. The API verifies the signature against the
  instance's public keys (JWKS), the issuer and the expiry (`app/auth.py`). A bad or expired token is a 401, never
  silently treated as signed out. The Clerk secret key is not used.
- Storage: with `MONGODB_URI` set, policies live in MongoDB (database `MONGODB_DB`, collection `policies`); otherwise
  in SQL through `DATABASE_URL` (SQLite by default). Both sit behind the same three calls in `app/store.py`.
- Settings: `CLERK_PUBLISHABLE_KEY` (API) and `VITE_CLERK_PUBLISHABLE_KEY` (UI build; the same public value),
  `MONGODB_URI`, `MONGODB_DB`. Atlas must allow the server's IP under Network Access.

### Privacy, cookie consent and crawler files

- **Privacy policy** at `#/privacy`, written from what the code does (policy text goes to the LLM provider, results sit
  in the database with no self-serve delete, Clerk handles sign-in, PostHog is opt-in). It is a plain-language draft,
  not legal advice: have it reviewed before relying on it, and say who the operator is.
- **Cookie consent.** The banner appears only when PostHog is configured, with Decline and Accept at equal weight.
  Nothing from PostHog loads, stores or sends until you accept. Declining or withdrawing (footer **Cookie settings**)
  stops capture and deletes PostHog's cookies and storage; events queued in the last few seconds before a withdrawal
  can still be delivered. Session recording is disabled in code, whatever the PostHog project says. Sign-in cookies
  (Clerk) are treated as necessary and are not gated. The choice is kept in local storage as `pl_consent`.
- **`/robots.txt` and `/sitemap.xml`** are generated by the API from `PUBLIC_URL` (or the address the request came in
  on). The sitemap has one URL: pages are `#/hash` routes, which search engines read as the home page.
- **`/llms.txt`** is a static summary for language models (`web/public/llms.txt`).

### Protecting the LLM key

Reading a policy spends your LLM key. Signing in does not gate it: the one endpoint that spends it is rate limited
instead.
Estimating a claim uses no model.

Limits, all returning 429 with `Retry-After`:

| What | Default | Setting |
|---|---|---|
| Extractions per client IP per hour | 5 | `EXTRACTIONS_PER_HOUR` |
| Extractions across everyone, rolling 24 h (the spend ceiling) | 100 | `LLM_DAILY_LIMIT` |
| Estimates per IP per minute | 120 | fixed |

What this does not do:

- Anyone can use the extraction endpoint up to those limits, and strangers can use up the daily cap so you cannot.
  Set a spend cap at your LLM provider as the real backstop. A hosted demo that must stay usable would need extraction
  to require sign-in (not done: it adds friction for a first-time visitor). An earlier version had an hourly access
  code (commit `85d6288`) and can be restored from history.
- It does not protect a key that leaks some other way (a committed `.env`, a shared screenshot, logs). Keep `.env` out
  of git and images (both are already excluded here) and rotate the key if it ever appears anywhere.
- Counters are in memory: they reset when the server restarts and are not shared between workers. Run one worker.
- Behind a reverse proxy set `TRUST_PROXY=1` so the real client IP is used; without a proxy leave it empty, because
  otherwise the header can be forged.
- The key itself is only ever sent to the LLM provider. No endpoint returns it, and provider error details stay in the
  server log instead of the HTTP response.

Deploying (Coolify, Dockerfile build pack): see [docs/DEPLOY.md](docs/DEPLOY.md). It lists every environment
variable, the volume and the single-replica rule.

Tests and lint:

```bash
.venv/Scripts/python -m pytest              # 86 tests (+1 live Mongo test: PL_TEST_MONGO=1)
.venv/Scripts/python -m ruff check .
cd web && npm run typecheck
```

## API

| Method and path | Purpose |
|---|---|
| `POST /policies` | Multipart `file` (PDF or text) or `text`. Rate limited. Returns the coverage, page texts, `needs_human_review` and `review_fields`. Signed in: also saved to your account. |
| `GET /policies/{id}` | The stored policy. The review flags are recomputed with the current threshold. 404 if it belongs to someone else. |
| `GET /me/policies` | Your saved policies, newest first. Needs sign-in (401 otherwise). |
| `POST /estimate` | `{policy_id, scenario}`. Returns payable, patient pays and the audit trail. Money is a decimal string. |
| `GET /samples` | The three synthetic sample policies. |
| `GET /health` | Liveness, and whether an LLM is configured. |

Pasted text marks pages with a line such as `--- Page 2 ---`. Without markers it is read as page 1.

## Repo layout

```
app/       FastAPI service: PDF text, LLM client, extraction, quote checks, storage
engine/    the rules engine (Decimal only, no LLM or network imports) and its assumptions in engine/README.md
evals/     10 hand-labelled synthetic policies, scoring, and the CLI (python -m evals.run)
samples/   three synthetic policies used by the UI
tests/     pytest: extraction with a stub LLM, engine edge cases, API, purity check, eval scoring
web/       Vite + React + TypeScript: the tool screens, the Home and How it works pages
  src/site/       pages, demos, mascot and the recorded run
  src/stageshow/  the Stageshow animation kit (MIT), copied in
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
- **The demos are a recording.** They replay one run on one model and one synthetic policy. A different model or
  document gives different tokens and text. The animation timings are paced for reading, not measured.
- **The animation checks are partly green.** The Stageshow film gate passes at 390 px and at desktop width except one
  line about the kit's own window title bar (its title is deliberately offset 36 px to look centred). Motion was
  judged from contact sheets and not watched live on a real phone.
- **Docker and Postgres are untested** on the author's machine.
- **The privacy policy is a draft.** No lawyer has read it, it names no legal entity, and the app has no delete
  button: deletion is by request through the repository.
- **Accounts are thin.** Sign-in only scopes saved policies to their owner: no roles, no sharing, no audit of who did what, and no payments. A policy extracted while signed out cannot be claimed later after signing in. The Clerk token's `azp` (allowed origin) is not checked. The signed-in flow was verified with generated test keys and by fetching Clerk's real public keys, not by a full sign-in. The `/estimate` result is an estimate, not a claim decision.
