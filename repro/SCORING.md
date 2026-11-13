# Scoring procedure

## 1. Ground truth (oracle)
The runner (`agent/runner.py`) records, independently of any telemetry condition, the
context contents at each model call, each tool call and the model call that requested
it, the acting delegation, the policy version in force, and every protected action and
its outcome. In the controlled study this record, together with the workload
generator's injected events (revocations, restatements, policy change v1 to v2, planted
untrusted content), is the ground truth for Q1–Q7. In the real-filing study it is the
ground truth for Q3 and Q7.

## 2. Conditions are projections of one run
The gateway emits the richest telemetry once. Each condition (B0, B1, B2, B3, FAOGF-S,
FAOGF) keeps only the fields its design would capture (Table IV), so differences between
conditions reflect what was captured, not run-to-run variation.

## 3. Per-query metrics
For each query and condition, the condition's best available heuristic produces a
prediction set, which is compared with the oracle set:
- Precision = |predicted ∩ truth| / |predicted|
- Recall = |predicted ∩ truth| / |truth|
- Accuracy (Q1, Q2 policy version): share of actions whose authority chain or policy
  version is reported exactly.
- An empty prediction when the truth set is non-empty counts as a recall failure;
  precision is then undefined and excluded from the mean.
- `n/a`: the condition's data cannot express the query.
- Q8: lost spans flagged by the auditor ÷ spans actually lost.
- Q9: records whose audit attributes were stripped and were flagged ÷ records stripped.

## 4. Aggregation and intervals
- Controlled study: 200 workflows per configuration, seeds 7–11. Tables report the mean
  over the five per-seed values ± the 95% Student-t interval, t(0.975, n−1)·sd/√n
  (`experiments/run_all.py`).
- Real-filing study: summary intervals are bootstrap percentile intervals (2.5th and
  97.5th percentiles of resampled means; `experiments/real_study.py`).

## 5. Storage, sensitive content and overhead
- Storage: serialized attribute bytes per span plus evidence-store record bytes per workflow.
- Retained sensitive content: raw content bytes in telemetry, and the number of planted
  synthetic client account identifiers found by string search in exported telemetry.
- Overhead: wall-clock time added per call, excluding tool work; p50, p95 and p99 (Table XV).

## 6. Real-filing task accuracy (context only)
Final answers were graded against each question's public rubric by an LLM judge
(`experiments/real_study.py`, `judge()`; judge model gpt-4o-mini, the harness default).
Task accuracy is reported only as context, and no claim depends on it.
