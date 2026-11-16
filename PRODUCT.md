# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Vite + React + TypeScript, hand-written CSS, no UI kit (given in the brief). Served by the FastAPI app in production, Vite dev proxy in development.

## Users
Two viewers, one interface (user's answer: "make 1 for both"):
- A claims or operations analyst at a health insurer or insurtech who checks what an extraction pulled from a policy document and wants an expected payout they can defend line by line.
- A hiring engineer skimming a portfolio demo who needs to see, within a minute, that the model only reads and the rules decide the money.
The interface is built for the analyst and explains the split plainly enough for the second viewer.

## Product Purpose
PolicyLens extracts structured coverage (sum insured, room rent cap, co-pay, waiting periods, sub-limits, exclusions) from a health insurance policy document with an LLM, then a deterministic rules engine computes the expected claim payout for a scenario. Success: every number on screen can be traced to a quote on a page of the document or to a named rule in the audit trail.

## Positioning
The LLM never makes a money decision. Extraction and arithmetic are separate systems with separate evidence: cited quotes and confidence on one side, a step-by-step audit trail on the other.

## Operating Context
Indian consumer health insurance (IRDAI Customer Information Sheet format). Money in INR with Indian digit grouping (3,00,000). Policies arrive as PDF or pasted text. All sample and eval policies are synthetic with fictional insurers; no real personal data or insurer documents.

## Capabilities and Constraints
- Three screens: upload or paste a policy; extracted coverage with click-to-view source quote and page and low-confidence fields flagged; scenario form with payout and audit trail.
- Fields below the confidence threshold, or whose quote is not found on the cited page, are marked "needs human review".
- No auth, no payments, no extra features.
- Estimates are an engine's reading of extracted terms, not a claim decision (limitations in engine/README.md).

## Brand Commitments
Name: PolicyLens. Calm, precise, trustworthy; no marketing language; no emoji; no gradient blobs.

## Evidence on Hand
Three synthetic sample policies (/samples), ten hand-labelled synthetic golden policies (/evals/golden). No testimonials, customers or benchmarks beyond the project's own eval run, which must be measured, never invented.

## Product Principles
1. Show the evidence beside every extracted value.
2. Flag uncertainty instead of smoothing it over.
3. Arithmetic is shown, never summarised: each rule, its inputs, amount before and after.
4. Money is exact and legible: INR, Indian grouping, tabular figures.
5. Say what the system will not do.

## Accessibility & Inclusion
WCAG AA contrast, full keyboard operation, responsive to mobile, reduced-motion respected. Meaning is never carried by colour alone.
