# Evaluation results

**Execution accuracy: 19/20 (95%)**

Recovered by the retry loop: 0

A query counts as correct only if it returns the same rows as a hand-written reference query.

## By question type

| Category | Correct | Total |
| --- | --- | --- |
| ambiguous | 1 | 2 |
| date_grouping | 3 | 3 |
| join_aggregate | 5 | 5 |
| ranking | 1 | 1 |
| schema_detail | 1 | 1 |
| simple_filter | 5 | 5 |
| subquery | 2 | 2 |
| window_function | 1 | 1 |

## Failures

**q19 — How did last month go?**

- Reason: result set differs from gold
```sql
SELECT 
    '2026-05' AS month,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(oi.quantity * oi.unit_price * (1 - oi.discount_rate)) AS total_revenue,
    SUM(oi.quantity * p.unit_cost) AS total_cost,
    SUM(oi.quantity * oi.unit_price * (1 - oi.discount_rate)) - SUM(oi.quantity * p.unit_cost) AS total_profit
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status = 'completed'
  AND strftime('%Y-%m', o.order_date) = '2026-05'
```

## What the failures have in common

Across three evaluation rounds the score moved 12/20 → 16/20 → 19/20, but the
number is the least interesting part of the exercise. What the failures were
actually made of changed completely between rounds.

**Most early failures were not reasoning errors.** In the first round, 7 of the
8 failed queries computed the right answer and were marked wrong for the shape
they returned it in: an extra `product_id`, a missing units column, a quarter
labelled `Q1` instead of `2025-Q1`. In q06 the revenue figures matched my
reference to the decimal point. The model understood the schema, the joins, the
discount arithmetic and the status filter without being told any of it. What it
could not guess was which columns I wanted, because I never said. The first
round measured my specification, not the model's SQL.

**The failures that survived were a different kind.** After the output rules
were added, what remained was two syntax slips (a missing `SELECT` inside a
subquery, a space inside an alias), one case where two of my own rules
contradicted each other, and two cases where my reference query was simply
wrong. Prompting fixed one of those categories. Nothing about prompting would
have fixed the others.

**Two of my reference answers were the actual error.** In q19 the model read
"last month" as May 2026, which follows directly from the rule I had written
telling it to treat 2026-06-30 as the present day. My gold query said June. The
model obeyed me and I scored it as a failure. In q17 I had asked for the
"highest profit margin per unit" and written a reference using the absolute
difference, while the model used a ratio — a reading that is at least as
defensible, and one that produces a completely different top five. Both were
defects in the evaluation set, not in the system being evaluated.

**The retry loop did not fire.** I added a single-retry self-correction step
after round two specifically for the two syntax failures, feeding the SQLite
parser error back to the model. In round three those two queries came back
clean on the first attempt and the loop never triggered. The same prompt and
the same questions produced different output than the round before, which means
a single evaluation run is a sample rather than a measurement, and the 95%
should be read with that in mind.

**The one remaining failure is not fixable by prompting.** q19 asks "how did
last month go?" without defining what counts as going well. The model answered
with orders, revenue, cost and profit; my reference returned orders and revenue.
Neither is wrong. I left it failing on purpose: adjusting the reference to match
the model's output would have produced a perfect score by fitting the ruler to
the object it measures.