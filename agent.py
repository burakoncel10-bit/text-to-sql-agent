"""
Text-to-SQL agent over retail.db.

Pipeline:  question -> prompt (schema + question) -> LLM -> SQL
           -> safety check -> execute -> rows

Setup:
    pip install google-genai
    export GEMINI_API_KEY="..."      # Windows: setx GEMINI_API_KEY "..."
    python seed_data.py
    python agent.py "how many completed orders were placed in 2026?"
"""

import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).with_name("retail.db")
MODEL = "gemini-3.5-flash-lite"

# Statements the agent is never allowed to run. The database is read-only
# from the agent's point of view; anything that writes is a bug, not a feature.
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|"
    r"detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------

def load_schema(db_path: Path = DB_PATH) -> str:
    """Read the live CREATE TABLE statements straight out of the database.

    Hand-writing the schema into the prompt means it silently goes stale the
    moment a column changes. Reading it from sqlite_master cannot drift.
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return "\n\n".join(r[0] for r in rows if r[0])


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------

def build_prompt(question: str, schema: str) -> str:
    """Assemble the prompt sent to the model.

    Version 2. Each rule below was added in response to a specific failure
    observed in the v1 evaluation run (12/20). No rule is speculative:
    if a rule is here, a query failed without it.
    """
    return f"""You are a SQL analyst working on a SQLite database.

Database schema:
{schema}

The data covers orders placed between 2025-01-01 and 2026-06-30.
Treat 2026-06-30 as the present day. Relative expressions such as
"last month", "this year" or "recently" are relative to that date,
never to the real current date.

Output rules:
- Return every column needed to identify a row in the answer, plus the
  value the question asks for. A question about the top product per
  category needs three columns: category, product, and the metric.
- Add nothing beyond that. No id, city, segment or other descriptive
  column the question did not ask for.
- Whenever rows are ranked, compared or aggregated, the metric used must
  itself be one of the returned columns.
- Label time periods with the year included: use 2025-Q1 for quarters and
  2026-03 for months.

Question: {question}

Write a single SQLite SELECT query that answers the question.
Return only the SQL. No explanation, no markdown fences."""


def build_repair_prompt(question: str, schema: str, bad_sql: str, error: str) -> str:
    """Second attempt, given the error the database reported.

    Added after the v2 evaluation, where 2 of 4 remaining failures were plain
    syntax slips (a missing SELECT inside a subquery, a space inside an alias)
    rather than reasoning errors. A model that can see the parser's complaint
    can usually fix its own typo; no amount of extra instruction prevents it.
    """
    return f"""You are a SQL analyst working on a SQLite database.

Database schema:
{schema}

You previously answered this question:
{question}

with this query:
{bad_sql}

SQLite rejected it with this error:
{error}

Write a corrected SQLite SELECT query. Keep the same intent and the same
output columns. Return only the SQL. No explanation, no markdown fences."""


# ---------------------------------------------------------------------------
# model call
# ---------------------------------------------------------------------------

def call_model(prompt: str) -> str:
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text or ""


def generate_sql(question: str, schema: str) -> str:
    return clean_sql(call_model(build_prompt(question, schema)))


def clean_sql(raw: str) -> str:
    """Strip markdown fences and trailing prose the model sometimes adds."""
    text = raw.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    return text.strip().rstrip(";").strip()


# ---------------------------------------------------------------------------
# safety + execution
# ---------------------------------------------------------------------------

class UnsafeQuery(Exception):
    pass


def assert_safe(sql: str) -> None:
    """Reject anything that is not a single read-only SELECT.

    Three separate checks, because each catches a different failure:
      1. must start with SELECT or WITH  -> blocks plain write statements
      2. no forbidden keyword anywhere   -> blocks writes hidden in subqueries
      3. no statement separator          -> blocks stacked queries
    """
    if not sql:
        raise UnsafeQuery("empty query")
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        raise UnsafeQuery("query does not start with SELECT or WITH")
    if FORBIDDEN.search(sql):
        raise UnsafeQuery("query contains a write or schema-level keyword")
    if ";" in sql.strip().rstrip(";"):
        raise UnsafeQuery("multiple statements are not allowed")


@dataclass
class Result:
    sql: str
    columns: list
    rows: list
    error: str = ""
    repaired: bool = False


def run_sql(sql: str, db_path: Path = DB_PATH, limit: int = 200) -> Result:
    assert_safe(sql)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # read-only handle
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(limit)
        columns = [d[0] for d in cur.description] if cur.description else []
        return Result(sql=sql, columns=columns, rows=rows)
    finally:
        conn.close()


def ask(question: str) -> Result:
    """Answer a question, with one self-correction attempt on failure.

    Only one retry. A second one rarely helps: if the model cannot fix the
    query when handed the exact parser error, the problem is its reading of
    the question, and repeating the same request will not change that.
    """
    schema = load_schema()
    sql = generate_sql(question, schema)

    try:
        return run_sql(sql)
    except (UnsafeQuery, sqlite3.Error) as first_error:
        repaired = clean_sql(
            call_model(build_repair_prompt(question, schema, sql, str(first_error)))
        )
        try:
            result = run_sql(repaired)
            result.repaired = True
            return result
        except (UnsafeQuery, sqlite3.Error) as second_error:
            return Result(
                sql=repaired,
                columns=[],
                rows=[],
                error=f"{second_error} (first attempt: {first_error})",
                repaired=True,
            )


# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python agent.py "your question"')
        raise SystemExit(1)

    result = ask(" ".join(sys.argv[1:]))

    print("\n--- generated SQL ---")
    print(result.sql)
    print("\n--- result ---")
    if result.error:
        print(f"ERROR: {result.error}")
    else:
        print(" | ".join(result.columns))
        for row in result.rows:
            print(" | ".join(str(v) for v in row))


if __name__ == "__main__":
    main()
