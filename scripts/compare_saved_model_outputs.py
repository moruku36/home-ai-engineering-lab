#!/usr/bin/env python3
"""Compare saved synthetic-case responses offline; never invoke a model."""
import argparse
import json
from pathlib import Path

from security_log_pipeline import parse_and_preprocess_logs, validate_evidence, validate_schema


def compare(cases, runs):
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a nonempty list")
    ids = [case["id"] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case id")
    results = []
    for run in runs:
        rows = run["responses"]
        by_id = {row["case_id"]: row for row in rows}
        if len(by_id) != len(rows) or set(by_id) - set(ids):
            raise ValueError("duplicate or unknown case id")
        counts = dict(valid=0, invalid=0, refusal=0, missing=0)
        details = []
        for case in cases:
            row = by_id.get(case["id"])
            status = "missing" if row is None else row.get("status")
            if status == "response":
                try:
                    events = row["events"]
                    if not isinstance(events, list):
                        raise ValueError("events must be an array")
                    entries = parse_and_preprocess_logs(case["logs"], source="synthetic_test")
                    for event in events:
                        validate_schema(event)
                        if not event["needs_human_review"]:
                            raise ValueError("model findings require human review")
                        validate_evidence(event, {e["line_no"]: e for e in entries})
                    status = "valid"
                except (ValueError, KeyError, TypeError):
                    status = "invalid"
                except Exception as exc:
                    # EvidenceValidationError is deliberately reported without model text.
                    from security_log_pipeline import EvidenceValidationError
                    if not isinstance(exc, EvidenceValidationError):
                        raise
                    status = "invalid"
            elif status not in ("refusal", "missing"):
                raise ValueError("status must be response or refusal")
            counts[status] += 1
            details.append({"case_id": case["id"], "status": status})
        results.append({"model": run["model"], "counts": counts, "cases": details})
    return {"case_count": len(cases), "models": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
        runs = [json.loads(p.read_text(encoding="utf-8")) for p in args.runs]
        print(json.dumps(compare(cases, runs), indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Invalid input: {type(exc).__name__}\n")


if __name__ == "__main__":
    main()
