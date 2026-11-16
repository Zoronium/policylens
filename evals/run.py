"""python -m evals.run [--limit N]

Runs the real extractor (whatever LLM_* env points at) over the golden set and scores it.
Writes evals/results.json and refreshes the headline block in README.md. If the LLM is not
configured it stops with an error: there is no offline or fake mode, so every published
number was measured.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.extract import annotate_review, extract_policy
from app.llm import LLMError, LLMNotConfigured, get_llm
from app.pdf import split_pages
from evals.score import FIELDS, score_policy, summarise

HERE = Path(__file__).resolve().parent
README = HERE.parent / "README.md"
START, END = "<!-- EVAL:START -->", "<!-- EVAL:END -->"


def pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def headline_markdown(res: dict) -> str:
    s = res["summary"]
    lines = [
        f"Model `{res['model']}`, {s['policies']} synthetic policies, run {res['run_at'][:10]}, "
        f"review threshold {res['threshold']}.",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Field-level accuracy | {pct(s['field_accuracy'])} |",
        f"| Accuracy on fields NOT flagged for review | {pct(s['accuracy_on_unflagged_fields'])} |",
        f"| Citation validity ({s['citations_checked']} quotes) | {pct(s['citation_validity'])} |",
        f"| Fields flagged low-confidence | {pct(s['low_confidence_share'])} |",
        f"| Wrong fields that were flagged | {s['wrong_fields_flagged']} of {s['wrong_fields']} |",
    ]
    if res["failed"]:
        lines += ["", f"Policies that failed outright (scored 0): {', '.join(res['failed'])}."]
    return "\n".join(lines)


def update_readme(res: dict) -> bool:
    if not README.is_file():
        return False
    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        return False
    head, rest = text.split(START, 1)
    tail = rest.split(END, 1)[1]
    README.write_text(f"{head}{START}\n{headline_markdown(res)}\n{END}{tail}", encoding="utf-8")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only the first N policies")
    args = ap.parse_args(argv)

    expected = json.loads((HERE / "golden" / "expected.json").read_text(encoding="utf-8"))
    expected.pop("_comment", None)
    names = sorted(expected)[: args.limit]
    try:
        llm = get_llm()
    except LLMNotConfigured as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    threshold = get_settings().review_threshold
    per_policy: dict[str, dict] = {}
    failed: list[str] = []
    for name in names:
        pages = split_pages((HERE / "golden" / f"{name}.txt").read_text(encoding="utf-8"))
        try:
            cov = annotate_review(extract_policy(pages, llm), threshold)
        except LLMError as e:
            print(f"  {name}: LLM error, scored 0 ({e})", file=sys.stderr)
            failed.append(name)
            per_policy[name] = {
                "fields": {f: {"score": 0.0, "flagged": True} for f in FIELDS},
                "citations_valid": 0,
                "citations_total": 0,
            }
            continue
        per_policy[name] = score_policy(cov, expected[name], pages)
        per_policy[name]["warnings"] = cov.warnings
        acc = sum(f["score"] for f in per_policy[name]["fields"].values()) / len(FIELDS)
        print(f"  {name}: {acc * 100:5.1f}%")

    if len(failed) == len(names):
        print("error: every policy failed; nothing to report.", file=sys.stderr)
        return 1

    res = {
        "model": llm.model,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "threshold": threshold,
        "failed": failed,
        "summary": summarise(per_policy),
        "policies": per_policy,
    }
    (HERE / "results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\n" + headline_markdown(res))
    print("\nBy field:")
    for f, v in res["summary"]["field_accuracy_by_field"].items():
        print(f"  {f:22s} {pct(v)}")
    print("\nWrote evals/results.json" + ("; updated README.md" if update_readme(res) else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
