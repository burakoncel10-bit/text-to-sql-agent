"""
Runs every question in eval_questions.json through the agent and scores it.

Scoring is execution accuracy: the agent's SQL is correct if running it
returns the same rows as the gold SQL. Comparing SQL strings would be wrong -
there are many correct ways to write the same query, and only the answer matters.

Usage:  python run_eval.py
Output: eval_results.md  (paste the table into your README)
"""

import json
import time
from collections import defaultdict
from pathlib import Path

from agent import DB_PATH, Result, ask, run_sql

QUESTIONS_PATH = Path(__file__).with_name("eval_questions.json")
REPORT_PATH = Path(__file__).with_name("eval_results.md")

SLEEP_SECONDS = 4.0  # stay under the free-tier requests-per-minute limit


def normalise(rows) -> list:
    """Order-insensitive, float-tolerant view of a result set."""
    out = []
    for row in rows:
        cells = []
        for value in row:
            if isinstance(value, float):
                cells.append(round(value, 2))
            else:
                cells.append(value)
        out.append(tuple(cells))
    return sorted(out, key=repr)


def score(agent_result: Result, gold_sql: str) -> tuple:
    if agent_result.error:
        return False, agent_result.error
    gold = run_sql(gold_sql)
    if normalise(agent_result.rows) == normalise(gold.rows):
        return True, ""
    return False, "result set differs from gold"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit("retail.db not found - run: python seed_data.py")

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    records = []

    for i, item in enumerate(questions, start=1):
        print(f"[{i}/{len(questions)}] {item['id']} ...", end=" ", flush=True)
        result = ask(item["question"])
        passed, note = score(result, item["gold_sql"])
        mark = "PASS" if passed else f"FAIL ({note})"
        print(f"{mark}{' [repaired]' if result.repaired else ''}")
        records.append({**item, "passed": passed, "note": note,
                        "agent_sql": result.sql, "repaired": result.repaired})
        if i < len(questions):
            time.sleep(SLEEP_SECONDS)

    total = len(records)
    passed = sum(r["passed"] for r in records)

    by_category = defaultdict(lambda: [0, 0])
    for r in records:
        by_category[r["category"]][1] += 1
        by_category[r["category"]][0] += int(r["passed"])

    repaired_ok = sum(r["passed"] and r["repaired"] for r in records)

    lines = [
        "# Evaluation results",
        "",
        f"**Execution accuracy: {passed}/{total} ({passed / total:.0%})**",
        "",
        f"Recovered by the retry loop: {repaired_ok}",
        "",
        "A query counts as correct only if it returns the same rows as a "
        "hand-written reference query.",
        "",
        "## By question type",
        "",
        "| Category | Correct | Total |",
        "| --- | --- | --- |",
    ]
    for category, (ok, n) in sorted(by_category.items()):
        lines.append(f"| {category} | {ok} | {n} |")

    failures = [r for r in records if not r["passed"]]
    lines += ["", "## Failures", ""]
    if not failures:
        lines.append("None.")
    else:
        for r in failures:
            lines += [
                f"**{r['id']} — {r['question']}**",
                "",
                f"- Reason: {r['note']}",
                "```sql",
                r["agent_sql"] or "(no SQL generated)",
                "```",
                "",
            ]

    lines += [
        "## What the failures have in common",
        "",
        "<!-- Write this yourself after reading the failures above. This paragraph",
        "     is the most valuable thing in the whole repo: it shows you can read",
        "     your own results instead of just reporting a number. -->",
        "",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nExecution accuracy: {passed}/{total} ({passed / total:.0%})")
    print(f"Wrote {REPORT_PATH.name}")


if __name__ == "__main__":
    main()
