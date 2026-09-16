# Text-to-SQL Agent with an Evaluation Harness

A small agent that answers business questions about a retail database in plain
English: it reads the live schema, asks an LLM for a SQL query, refuses anything
that is not a read-only `SELECT`, runs it, and returns both the answer and the
query it used.

The agent itself took an afternoon. The part worth reading is the evaluation
harness and what three measurement rounds revealed — including two defects in my
own reference answers.

---

## Why show the generated SQL

Every answer is returned together with the query that produced it. An agent that
returns only a number asks to be trusted; one that returns the query can be
checked. For anything touching business reporting, that is not a nice-to-have.

---

## Pipeline

```
question
   ↓
schema read live from sqlite_master  ──┐
   ↓                                   │  both go into the prompt
prompt ─────────────────────────────── ┘
   ↓
LLM (Gemini Flash) generates SQL
   ↓
safety layer: read-only SELECT only
   ↓
execute on SQLite  ──→  on error: feed the parser message back, retry once
   ↓
rows + the SQL that produced them
```

The schema is read out of `sqlite_master` at request time rather than pasted
into the prompt. A hand-written schema silently goes stale the first time a
column changes; this one cannot drift.

### Safety layer

The agent has read access and nothing more. Three independent checks, each
catching a different failure:

| Check | Blocks |
| --- | --- |
| Must begin with `SELECT` or `WITH` | plain write statements |
| No write or schema keyword anywhere | writes hidden inside subqueries |
| No statement separator | stacked queries |

The database handle is also opened read-only (`mode=ro`), so a query that got
past all three still could not modify anything.

---

## The database

Synthetic retail data, generated from a fixed random seed so the database is
byte-identical on every machine — evaluation scores mean nothing if the data
moves underneath them.

| Table | Rows | |
| --- | --- | --- |
| `customers` | 300 | 5 countries, 3 segments |
| `categories` | 5 | |
| `products` | 20 | price, cost, active flag |
| `orders` | 2,000 | completed / cancelled / returned, 3 channels |
| `order_items` | 4,935 | quantity, unit price, discount rate |

Orders span 2025-01-01 to 2026-06-30. The schema is deliberately shaped to
require multi-table joins, date bucketing and a revenue definition that is easy
to get subtly wrong (`quantity × unit_price × (1 − discount_rate)`, completed
orders only).

---

## Evaluation

20 questions across 8 categories, each paired with a hand-written reference
query. A generated query counts as correct only if it returns the same rows as
the reference — **execution accuracy**, not string similarity, because the same
question has many correct SQL spellings and only the answer matters.

### Results

| Round | Accuracy | What changed |
| --- | --- | --- |
| v1 | 12/20 (60%) | baseline prompt: schema + question, nothing else |
| v2 | 16/20 (80%) | output-shape and time-reference rules added |
| v3 | 19/20 (95%) | multi-key output rule; two reference queries corrected |

Every prompt rule was added in response to a specific observed failure. No rule
is speculative — rules for discount handling and status filtering were
deliberately *not* added, because the model already applied both correctly and
fixing an unmeasured problem only inflates the prompt.

### What the rounds showed

Seven of the eight first-round failures computed the correct answer and were
marked wrong for the shape they returned it in — an extra column, a missing
metric, a quarter labelled `Q1` instead of `2025-Q1`. In one case the revenue
figures matched the reference to the decimal. Round one measured my
specification, not the model's SQL.

Two failures turned out to be defects in my own reference answers rather than in
the system. Full write-up in `eval_results.md`.

---

## Limitations

- **A single run is a sample, not a measurement.** Two queries that failed with
  syntax errors in round two came back clean in round three with no change
  aimed at them, and the retry loop I had added for them never fired. The 95%
  should be read with that variance in mind.
- **One failure is left in deliberately.** "How did last month go?" does not
  define what counts as going well; the model returned orders, revenue, cost and
  profit, my reference returned orders and revenue. Adjusting the reference
  would have bought a perfect score by fitting the ruler to the object.
- **Scores are model-specific.** All three rounds ran on the same Gemini Flash
  model. Numbers from a different model are not comparable to these.
- **20 questions is small.** Enough to expose systematic problems, not enough to
  estimate accuracy precisely.
- **Synthetic data.** Clean, evenly distributed, no nulls or messy edge cases.
  Real data would surface failure modes this set cannot.

---

## Setup

```bash
pip install -r requirements.txt
python seed_data.py                      # builds retail.db
setx GEMINI_API_KEY "..."                # Windows; export on macOS/Linux
python agent.py "which category sold the most in 2026?"
python run_eval.py                       # writes eval_results.md
```

A free Google AI Studio key is enough: the evaluation set is 20 requests per
run, well inside the free tier.

| File | |
| --- | --- |
| `schema.sql` | table definitions |
| `seed_data.py` | deterministic synthetic data generator |
| `agent.py` | prompt, model call, safety layer, retry loop |
| `eval_questions.json` | 20 questions with reference queries |
| `run_eval.py` | scoring harness, writes `eval_results.md` |

---

## Next steps

- Run the evaluation several times and report a range rather than a single score.
- Compare two models on the same question set.
- Break accuracy down by question type over repeated runs to see which
  categories are genuinely unstable.

---

## A note on AI assistance

I used Claude Code for environment setup, debugging and boilerplate. The prompt
design, the evaluation questions and reference queries, and the reading of the
failures are mine — those are the parts where the decisions live, and delegating
them would have meant learning nothing from the exercise.

---

Built by Burak Öncel — Management Information Systems, Istinye University.
