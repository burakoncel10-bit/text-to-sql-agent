"""
Streamlit front end for the text-to-SQL agent.

Run with:  streamlit run app.py

The generated SQL is shown next to every answer on purpose: an agent that
returns only a number asks to be trusted, one that shows its query can be
checked.
"""

import os
import sqlite3

import pandas as pd
import streamlit as st

from agent import DB_PATH, MODEL, ask, load_schema

EXAMPLES = [
    "Which product category generated the most revenue?",
    "Who are the top 5 customers by total spending?",
    "What was the net revenue for each quarter of 2025?",
    "Which inactive products have still been sold?",
]

st.set_page_config(page_title="Text-to-SQL Agent", page_icon="🔎", layout="wide")

st.title("Text-to-SQL Agent")
st.caption(
    "Ask a question about the retail database in plain English. "
    "The agent writes the SQL, checks that it is read-only, runs it, "
    "and shows you both the answer and the query."
)

# --- sidebar ---------------------------------------------------------------

with st.sidebar:
    st.subheader("Database")
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ["customers", "categories", "products", "orders", "order_items"]
        }
        conn.close()
        st.table(pd.DataFrame(counts.items(), columns=["table", "rows"]))
    else:
        st.error("retail.db not found — run `python seed_data.py` first.")

    st.caption(f"Model: `{MODEL}`")
    with st.expander("Schema"):
        st.code(load_schema(), language="sql")

    st.markdown(
        "Evaluated at **19/20** execution accuracy over 20 reference "
        "questions. See `eval_results.md` for the failure analysis."
    )

# --- main ------------------------------------------------------------------

if not os.environ.get("GEMINI_API_KEY"):
    st.warning("GEMINI_API_KEY is not set. The agent cannot call the model.")

if "question" not in st.session_state:
    st.session_state.question = ""

st.write("**Try one of these:**")
cols = st.columns(len(EXAMPLES))
for col, example in zip(cols, EXAMPLES):
    if col.button(example, use_container_width=True):
        st.session_state.question = example

question = st.text_input(
    "Your question",
    value=st.session_state.question,
    placeholder="e.g. how many completed orders were placed in 2026?",
)

if st.button("Run", type="primary") and question.strip():
    with st.spinner("Generating SQL and running it…"):
        result = ask(question.strip())

    if result.repaired:
        st.info(
            "The first query failed to parse. The error was fed back to the "
            "model and this is its corrected attempt."
        )

    st.subheader("Generated SQL")
    st.code(result.sql or "(no SQL generated)", language="sql")

    st.subheader("Result")
    if result.error:
        st.error(result.error)
    elif not result.rows:
        st.info("The query ran but returned no rows.")
    else:
        st.dataframe(
            pd.DataFrame(result.rows, columns=result.columns),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(result.rows)} row(s)")
