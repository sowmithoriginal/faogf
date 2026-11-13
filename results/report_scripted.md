# FAOGF controlled study (scripted; 200 workflows per run; seeds [7, 8, 9, 10, 11])
Values are mean ± 95% CI across seeds (CI omitted when zero). n/a = the telemetry cannot express the query.

## Table 1. Audit-query answerability (asynchronous sub-agent hand-off, no faults)

| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 Authority chain (acc.) | n/a | 1.00 | 1.00 | 1.00 |
| Q2 Protected attempts found (recall) | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 Policy version (acc.) | n/a | n/a | 1.00 | 1.00 |
| Q3 Supporting filings (P) | 0.80 ± 0.04 | 0.82 ± 0.03 | 1.00 | 1.00 |
| Q3 Supporting filings (R) | 0.88 ± 0.01 | 1.00 | 1.00 | 1.00 |
| Q3 All sources incl. untrusted (R) | 0.77 ± 0.02 | 0.88 ± 0.02 | 1.00 | 1.00 |
| Q3 Version-exact sources (P) | n/a | n/a | 1.00 | 1.00 |
| Q4 Restatement blast radius (P) | 0.40 ± 0.06 | 0.42 ± 0.05 | 1.00 | 1.00 |
| Q4 Restatement blast radius (R) | 0.85 ± 0.10 | 1.00 | 1.00 | 1.00 |
| Q5 Post-revocation actions (R) | n/a | n/a | n/a | 1.00 |
| Q6 Stale-policy actions (R) | n/a | n/a | 1.00 | 1.00 |
| Q7 Untrusted-context exposure (P) | 0.86 ± 0.06 | 0.86 ± 0.06 | 1.00 | 1.00 |
| Q7 Untrusted-context exposure (R) | 1.00 | 1.00 | 1.00 | 1.00 |
| Attribute bytes / span | 135 ± 1 | 223 ± 1 | 538 ± 3 | 538 ± 3 |
| Evidence-store bytes / workflow | n/a | n/a | n/a | 11400 ± 422 |

### Hand-off mode sensitivity (Q3 filings recall / Q4 blast precision)

| Mode | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| inline | 1.00 / 0.42 ± 0.05 | 1.00 / 0.42 ± 0.05 | 1.00 / 1.00 | 1.00 / 1.00 |
| linked | 1.00 / 0.42 ± 0.05 | 1.00 / 0.42 ± 0.05 | 1.00 / 1.00 | 1.00 / 1.00 |
| fragmented | 0.88 ± 0.01 / 0.40 ± 0.06 | 1.00 / 0.42 ± 0.05 | 1.00 / 1.00 | 1.00 / 1.00 |

## Table 2. Ablations (remove one component; same runs)

| Query | full | −version | −context | −policy | −lineage | −model-call link | B1 |
|---|---|---|---|---|---|---|---|
| Q3 version-exact (P) | 1.00 | n/a | 0.83 ± 0.03 | 1.00 | 1.00 | 1.00 | n/a |
| Q3 filings (P) | 1.00 | 1.00 | 0.82 ± 0.03 | 1.00 | 1.00 | 1.00 | 0.82 ± 0.03 |
| Q4 blast radius (P) | 1.00 | 0.49 ± 0.05 | 0.84 ± 0.05 | 1.00 | 1.00 | 1.00 | 0.42 ± 0.05 |
| Q2 policy version | 1.00 | 1.00 | 1.00 | n/a | 1.00 | 1.00 | n/a |
| Q5 post-revocation (R) | 1.00 | 1.00 | 1.00 | 1.00 | 0.69 ± 0.14 | 1.00 | n/a |
| Q6 stale policy (R) | 1.00 | 1.00 | 1.00 | n/a | 1.00 | 1.00 | n/a |
| Q7 exposure (P) | 1.00 | 1.00 | 0.96 ± 0.04 | 1.00 | 1.00 | 0.86 ± 0.06 | 0.86 ± 0.06 |

## Table 3. Span-export loss

| Drop rate | B0 Q3 R | B1 Q3 R | FAOGF-S Q3 R | FAOGF Q3 R | Spans-only Q2 R | FAOGF Q2 R | Loss detected (orphans) | Loss detected (FAOGF) |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.77 ± 0.02 | 0.88 ± 0.02 | 1.00 | 1.00 | 1.00 | 1.00 | n/a | n/a |
| 0.05 | 0.74 ± 0.02 | 0.84 ± 0.02 | 0.91 ± 0.02 | 1.00 | 0.94 ± 0.04 | 1.00 | 0.11 ± 0.04 | 0.97 ± 0.02 |
| 0.1 | 0.69 ± 0.02 | 0.80 ± 0.02 | 0.81 ± 0.03 | 1.00 | 0.90 ± 0.03 | 1.00 | 0.10 ± 0.02 | 0.98 ± 0.01 |
| 0.2 | 0.63 ± 0.02 | 0.73 ± 0.03 | 0.64 ± 0.04 | 1.00 | 0.80 ± 0.04 | 1.00 | 0.10 ± 0.01 | 0.97 ± 0.01 |
| 0.3 | 0.57 ± 0.03 | 0.66 ± 0.04 | 0.51 ± 0.04 | 1.00 | 0.71 ± 0.03 | 1.00 | 0.10 ± 0.01 | 0.97 ± 0.00 |
| 0.5 | 0.43 ± 0.03 | 0.50 ± 0.03 | 0.28 ± 0.03 | 1.00 | 0.49 ± 0.03 | 1.00 | 0.10 ± 0.00 | 0.97 ± 0.00 |

## Table 4. Evidence-store write failures (FAOGF, fail-closed)

| Store fail rate | Protected attempts | Blocked (fail-closed) | Executed without record | Spans flagged unrecorded | Q3 R | Q2 R | Q5 R |
|---|---|---|---|---|---|---|---|
| 0.0 | 97.8 ± 9.1 | 0.0 | 0 | 0.0 | 1.00 | 1.00 | 1.00 |
| 0.01 | 97.8 ± 9.1 | 0.4 ± 0.7 | 0 | 19.8 ± 7.7 | 1.00 | 1.00 | 1.00 |
| 0.05 | 97.8 ± 9.1 | 1.2 ± 1.6 | 0 | 105.6 ± 20.2 | 1.00 | 1.00 | 1.00 |
| 0.1 | 97.8 ± 9.1 | 2.6 ± 1.1 | 0 | 223.4 ± 17.2 | 1.00 | 1.00 | 1.00 |
| 0.2 | 97.8 ± 9.1 | 9.4 ± 3.8 | 0 | 440.8 ± 34.7 | 1.00 | 1.00 | 1.00 |

## Table 5. Correlated outages (span loss and store failure together, p=0.9 inside the window)

| Outage share | Spool | Blocked | Executed without record | B1 Q3 R | FAOGF Q3 R | B1 Q2 R | FAOGF Q2 R | Loss detected | Spooled records |
|---|---|---|---|---|---|---|---|---|---|
| 0.0 | no | 0.0 | 0 | 0.88 ± 0.02 | 1.00 | 1.00 | 1.00 | n/a | 0 |
| 0.1 | no | 4.4 ± 1.9 | 0 | 0.81 ± 0.01 | 0.92 ± 0.02 | 0.91 ± 0.04 | 0.92 ± 0.04 | 0.17 ± 0.02 | 0 |
| 0.25 | no | 12.2 ± 4.3 | 0 | 0.70 ± 0.02 | 0.79 ± 0.02 | 0.75 ± 0.06 | 0.77 ± 0.06 | 0.15 ± 0.02 | 0 |
| 0.1 | yes | 0.0 | 0 | 0.80 ± 0.01 | 1.00 ± 0.00 | 0.91 ± 0.05 | 1.00 | 0.92 ± 0.01 | 291 ± 48 |
| 0.25 | yes | 0.0 | 0 | 0.69 ± 0.02 | 1.00 ± 0.01 | 0.75 ± 0.06 | 1.00 ± 0.01 | 0.93 ± 0.00 | 770 ± 89 |

## Table 6. Sensitivity to context eviction (Q3 filings precision / Q7 exposure precision)

| Eviction rate | B0 | B1 | FAOGF |
|---|---|---|---|
| 0.0 | 1.00 / 0.90 ± 0.04 | 1.00 / 0.90 ± 0.04 | 1.00 / 1.00 |
| 0.3 | 0.80 ± 0.04 / 0.86 ± 0.06 | 0.82 ± 0.03 / 0.86 ± 0.06 | 1.00 / 1.00 |
| 0.6 | 0.61 ± 0.03 / 0.83 ± 0.06 | 0.65 ± 0.02 / 0.83 ± 0.06 | 1.00 / 1.00 |
| 0.9 | 0.39 ± 0.03 / 0.80 ± 0.06 | 0.45 ± 0.03 / 0.80 ± 0.06 | 1.00 / 1.00 |

## Table 7. Sensitivity to delegation rate (Q3 filings recall)

| Delegation rate | B0 | B1 | FAOGF |
|---|---|---|---|
| 0.0 | 1.00 | 1.00 | 1.00 |
| 0.4 | 0.88 ± 0.01 | 1.00 | 1.00 |
| 0.8 | 0.77 ± 0.02 | 1.00 | 1.00 |

## Table 8. Scale (one seed)

| Workflows | Run time (s) | Spans | Store (MB) | Chain verify (s) | Full audit sweep B0 (ms) | B1 (ms) | FAOGF (ms) |
|---|---|---|---|---|---|---|---|
| 250 | 0.56 | 3746 | 2.98 | 0.052 | 6 | 6 | 9 |
| 1000 | 2.33 | 14555 | 11.6 | 0.199 | 29 | 33 | 45 |
| 4000 | 10.69 | 57583 | 45.76 | 0.798 | 145 | 156 | 183 |
| 10000 | 33.86 | 144368 | 114.96 | 2.091 | 392 | 405 | 521 |

## Table 10. Content-logging baselines (B2 = tool results logged; B3 = tool results + full prompts logged)


**sub-agent traces linked**

| Metric | B0 | B1 | B2 | B3 | FAOGF |
|---|---|---|---|---|---|
| Q3 filings P | 0.82 ± 0.03 | 0.82 ± 0.03 | 0.82 ± 0.03 | 1.00 | 1.00 |
| Q3 filings R | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Q4 blast radius P | 0.42 ± 0.05 | 0.42 ± 0.05 | 0.83 ± 0.06 | 1.00 | 1.00 |
| Q4 blast radius R | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Q7 exposure P | 0.86 ± 0.06 | 0.86 ± 0.06 | 0.93 ± 0.05 | 1.00 | 1.00 |
| Q2 attempts found R | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | n/a | n/a | 1.00 |
| Q5 post-revocation R | n/a | n/a | n/a | n/a | 1.00 |
| Telemetry KB / workflow | 1.9 ± 0.1 | 3.1 ± 0.1 | 2.8 ± 0.1 | 9.4 ± 0.4 | 15.1 ± 0.6 |
| Raw content KB / workflow | 0.0 | 0.0 | 0.7 ± 0.0 | 6.5 ± 0.3 | 0.0 |
| Client account IDs retained / workflow | 0.0 | 0.0 | 2.0 ± 0.1 | 6.7 ± 0.6 | 0.0 |

**asynchronous hand-off, no links**

| Metric | B0 | B1 | B2 | B3 | FAOGF |
|---|---|---|---|---|---|
| Q3 filings P | 0.80 ± 0.04 | 0.82 ± 0.03 | 0.80 ± 0.04 | 1.00 | 1.00 |
| Q3 filings R | 0.88 ± 0.01 | 1.00 | 0.88 ± 0.01 | 0.85 ± 0.02 | 1.00 |
| Q4 blast radius P | 0.40 ± 0.06 | 0.42 ± 0.05 | 0.81 ± 0.07 | 1.00 | 1.00 |
| Q4 blast radius R | 0.85 ± 0.10 | 1.00 | 0.85 ± 0.10 | 0.82 ± 0.12 | 1.00 |
| Q7 exposure P | 0.86 ± 0.06 | 0.86 ± 0.06 | 0.93 ± 0.05 | 1.00 | 1.00 |
| Q2 attempts found R | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | n/a | n/a | 1.00 |
| Q5 post-revocation R | n/a | n/a | n/a | n/a | 1.00 |
| Telemetry KB / workflow | 1.9 ± 0.1 | 3.1 ± 0.1 | 2.8 ± 0.1 | 9.4 ± 0.4 | 15.1 ± 0.6 |
| Raw content KB / workflow | 0.0 | 0.0 | 0.7 ± 0.0 | 6.5 ± 0.3 | 0.0 |
| Client account IDs retained / workflow | 0.0 | 0.0 | 2.0 ± 0.1 | 6.7 ± 0.6 | 0.0 |

**30% span-export loss**

| Metric | B0 | B1 | B2 | B3 | FAOGF |
|---|---|---|---|---|---|
| Q3 filings P | 0.80 ± 0.04 | 0.82 ± 0.04 | 0.80 ± 0.04 | 0.96 ± 0.02 | 1.00 |
| Q3 filings R | 0.65 ± 0.03 | 0.75 ± 0.04 | 0.65 ± 0.03 | 0.78 ± 0.03 | 1.00 |
| Q4 blast radius P | 0.41 ± 0.06 | 0.43 ± 0.06 | 0.82 ± 0.08 | 0.98 ± 0.05 | 1.00 |
| Q4 blast radius R | 0.55 ± 0.15 | 0.69 ± 0.14 | 0.55 ± 0.15 | 0.75 ± 0.16 | 1.00 |
| Q7 exposure P | 0.85 ± 0.14 | 0.85 ± 0.14 | 0.90 ± 0.10 | 0.99 ± 0.02 | 1.00 |
| Q2 attempts found R | 0.71 ± 0.03 | 0.71 ± 0.03 | 0.71 ± 0.03 | 0.71 ± 0.03 | 1.00 |
| Q2 policy version | n/a | n/a | n/a | n/a | 1.00 |
| Q5 post-revocation R | n/a | n/a | n/a | n/a | 1.00 |
| Telemetry KB / workflow | 1.3 ± 0.0 | 2.2 ± 0.0 | 1.9 ± 0.0 | 6.5 ± 0.2 | 12.8 ± 0.4 |
| Raw content KB / workflow | 0.0 | 0.0 | 0.5 ± 0.0 | 4.5 ± 0.2 | 0.0 |
| Client account IDs retained / workflow | 0.0 | 0.0 | 1.4 ± 0.1 | 4.7 ± 0.3 | 0.0 |

## Table 11. Enforcement against injections that target allowed internal destinations

| Policy | Harmful sends attempted | Harmful sends executed | Legitimate sends blocked | Human approvals requested |
|---|---|---|---|---|
| allowlist (auto) | 32.8 ± 4.1 | 32.8 ± 4.1 | 0.0 | 0.0 |
| allowlist + approve every send | 32.8 ± 4.1 | 0.0 | 0.0 | 94.6 ± 5.3 |
| taint-deny, history taint | 32.8 ± 4.1 | 0.0 | 28.6 ± 5.3 | 0.0 |
| taint-deny, context taint (FAOGF) | 32.8 ± 4.1 | 0.0 | 26.4 ± 5.7 | 0.0 |
| taint-escalate, history taint | 32.8 ± 4.1 | 0.0 | 0.0 | 61.4 ± 6.8 |
| taint-escalate, context taint (FAOGF) | 32.8 ± 4.1 | 0.0 | 0.0 | 59.2 ± 7.3 |

**Eviction sensitivity (precise context taint vs coarse history taint)**

| Eviction rate | Policy | Legitimate sends blocked | Human approvals | Harmful executed |
|---|---|---|---|---|
| 0.0 | taint-escalate, history taint | 0.0 | 62.8 ± 6.5 | 0.0 |
| 0.0 | taint-escalate, context taint (FAOGF) | 0.0 | 62.8 ± 6.5 | 0.0 |
| 0.0 | taint-deny, history taint | 30.0 ± 4.2 | 0.0 | 0.0 |
| 0.0 | taint-deny, context taint (FAOGF) | 30.0 ± 4.2 | 0.0 | 0.0 |
| 0.5 | taint-escalate, history taint | 0.0 | 61.2 ± 6.7 | 0.0 |
| 0.5 | taint-escalate, context taint (FAOGF) | 0.0 | 58.4 ± 7.6 | 0.0 |
| 0.5 | taint-deny, history taint | 28.4 ± 5.2 | 0.0 | 0.0 |
| 0.5 | taint-deny, context taint (FAOGF) | 25.6 ± 6.4 | 0.0 | 0.0 |
| 0.9 | taint-escalate, history taint | 0.0 | 59.4 ± 7.3 | 0.0 |
| 0.9 | taint-escalate, context taint (FAOGF) | 0.0 | 54.8 ± 8.1 | 0.0 |
| 0.9 | taint-deny, history taint | 26.6 ± 5.2 | 0.0 | 0.0 |
| 0.9 | taint-deny, context taint (FAOGF) | 22.0 ± 6.5 | 0.0 | 0.0 |

## Table 12. Epoch Merkle anchoring (3555 records, 2.4 MB store)

| Epoch size | Anchors | Anchor bytes | Commit (ms) | Proof + record (bytes) | Verify (µs) | Suffix rewrite detected (chain only / anchors) | Localised to epoch |
|---|---|---|---|---|---|---|---|
| 64 | 56 | 3584 | 5.07 | 1028 | 7.1 | False / True | True |
| 256 | 14 | 896 | 4.83 | 1178 | 9.7 | False / True | True |
| 1024 | 4 | 256 | 5.14 | 1327 | 12.3 | False / True | True |

## Table 13. OpenTelemetry sampling (head: SDK ParentBased(TraceIdRatioBased); tail: otelcol-contrib)


**head 1.0**

| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 1.00 | 1.00 | 1.00 |
| Q2 protected attempts found | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | 1.00 | 1.00 |
| Q3 supporting filings R | 0.88 ± 0.01 | 1.00 | 1.00 | 1.00 |
| Q4 blast radius R | 0.85 ± 0.10 | 1.00 | 1.00 | 1.00 |
| Q7 exposure R | 1.00 | 1.00 | 1.00 | 1.00 |
| Spans kept / workflow | 14.31 ± 0.49 | 14.31 ± 0.49 | 14.31 ± 0.49 | 14.31 ± 0.49 |

**head 0.5**

| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.51 ± 0.05 | 0.51 ± 0.05 | 1.00 |
| Q2 protected attempts found | 0.52 ± 0.08 | 0.52 ± 0.08 | 0.52 ± 0.08 | 1.00 |
| Q2 policy version | n/a | n/a | 0.52 ± 0.08 | 1.00 |
| Q3 supporting filings R | 0.49 ± 0.06 | 0.53 ± 0.06 | 0.52 ± 0.05 | 1.00 |
| Q4 blast radius R | 0.38 ± 0.14 | 0.42 ± 0.13 | 0.42 ± 0.13 | 1.00 |
| Q7 exposure R | 0.52 ± 0.09 | 0.52 ± 0.09 | 0.52 ± 0.09 | 1.00 |
| Spans kept / workflow | 7.26 ± 0.52 | 7.26 ± 0.52 | 7.26 ± 0.52 | 7.26 ± 0.52 |

**head 0.1**

| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.10 ± 0.04 | 0.10 ± 0.04 | 1.00 |
| Q2 protected attempts found | 0.09 ± 0.05 | 0.09 ± 0.05 | 0.09 ± 0.05 | 1.00 |
| Q2 policy version | n/a | n/a | 0.09 ± 0.05 | 1.00 |
| Q3 supporting filings R | 0.17 ± 0.05 | 0.18 ± 0.05 | 0.17 ± 0.05 | 1.00 |
| Q4 blast radius R | 0.08 ± 0.12 | 0.09 ± 0.14 | 0.09 ± 0.14 | 1.00 |
| Q7 exposure R | 0.10 ± 0.04 | 0.10 ± 0.04 | 0.10 ± 0.04 | 1.00 |
| Spans kept / workflow | 1.44 ± 0.40 | 1.44 ± 0.40 | 1.44 ± 0.40 | 1.44 ± 0.40 |

**head 0.01**

| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.01 ± 0.01 | 0.01 ± 0.01 | 1.00 |
| Q2 protected attempts found | 0.01 ± 0.01 | 0.01 ± 0.01 | 0.01 ± 0.01 | 1.00 |
| Q2 policy version | n/a | n/a | 0.01 ± 0.01 | 1.00 |
| Q3 supporting filings R | 0.11 ± 0.02 | 0.11 ± 0.02 | 0.11 ± 0.03 | 1.00 |
| Q4 blast radius R | 0.01 ± 0.03 | 0.01 ± 0.03 | 0.01 ± 0.03 | 1.00 |
| Q7 exposure R | 0.01 ± 0.02 | 0.01 ± 0.02 | 0.01 ± 0.02 | 1.00 |
| Spans kept / workflow | 0.14 ± 0.07 | 0.14 ± 0.07 | 0.14 ± 0.07 | 0.14 ± 0.07 |

**tail (errors + distribute_report + 10%)**

| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.54 ± 0.06 | 0.54 ± 0.06 | 1.00 |
| Q2 protected attempts found | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | 1.00 | 1.00 |
| Q3 supporting filings R | 0.51 ± 0.05 | 0.51 ± 0.07 | 0.50 ± 0.06 | 1.00 |
| Q4 blast radius R | 0.36 ± 0.29 | 0.36 ± 0.29 | 0.33 ± 0.28 | 1.00 |
| Q7 exposure R | 1.00 | 1.00 | 1.00 | 1.00 |
| Spans kept / workflow | 7.17 ± 0.78 | 7.17 ± 0.78 | 7.17 ± 0.78 | 7.17 ± 0.78 |

## Table 14. SDK BatchSpanProcessor queue overflow (OTLP/HTTP to a real Collector, burst load)


**queue 2048**

Span drop share: 0.00  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 1.00 | 1.00 | 1.00 |
| Q2 protected attempts found | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | 1.00 | 1.00 |
| Q3 supporting filings R | 0.88 ± 0.00 | 1.00 | 1.00 | 1.00 |
| Q4 blast radius R | 0.83 ± 0.22 | 1.00 | 1.00 | 1.00 |
| Q7 exposure R | 1.00 | 1.00 | 1.00 | 1.00 |
| Spans kept / workflow | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 |
| Lost spans detected | n/a | n/a | n/a | n/a |

**queue 512**

Span drop share: 0.31 ± 0.13  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.72 ± 0.13 | 0.72 ± 0.13 | 1.00 |
| Q2 protected attempts found | 0.71 ± 0.03 | 0.71 ± 0.03 | 0.71 ± 0.03 | 1.00 |
| Q2 policy version | n/a | n/a | 0.71 ± 0.03 | 1.00 |
| Q3 supporting filings R | 0.65 ± 0.08 | 0.72 ± 0.13 | 0.72 ± 0.13 | 1.00 |
| Q4 blast radius R | 0.55 ± 0.12 | 0.71 ± 0.35 | 0.71 ± 0.35 | 1.00 |
| Q7 exposure R | 0.76 ± 0.21 | 0.76 ± 0.21 | 0.76 ± 0.21 | 1.00 |
| Spans kept / workflow | 10.00 ± 2.23 | 10.00 ± 2.23 | 10.00 ± 2.23 | 10.00 ± 2.23 |
| Lost spans detected | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.88 ± 0.01 |

**queue 128**

Span drop share: 0.78 ± 0.02  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.24 ± 0.03 | 0.24 ± 0.03 | 1.00 |
| Q2 protected attempts found | 0.23 ± 0.07 | 0.23 ± 0.07 | 0.23 ± 0.07 | 1.00 |
| Q2 policy version | n/a | n/a | 0.23 ± 0.07 | 1.00 |
| Q3 supporting filings R | 0.29 ± 0.05 | 0.31 ± 0.01 | 0.31 ± 0.01 | 1.00 |
| Q4 blast radius R | 0.19 ± 0.32 | 0.20 ± 0.29 | 0.20 ± 0.29 | 1.00 |
| Q7 exposure R | 0.26 ± 0.13 | 0.26 ± 0.13 | 0.26 ± 0.13 | 1.00 |
| Spans kept / workflow | 3.20 | 3.20 | 3.20 | 3.20 |
| Lost spans detected | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.88 ± 0.00 |

**queue 32**

Span drop share: 0.94 ± 0.03  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.08 ± 0.04 | 0.08 ± 0.04 | 1.00 |
| Q2 protected attempts found | 0.05 ± 0.01 | 0.05 ± 0.01 | 0.05 ± 0.01 | 1.00 |
| Q2 policy version | n/a | n/a | 0.05 ± 0.01 | 1.00 |
| Q3 supporting filings R | 0.16 ± 0.03 | 0.17 ± 0.03 | 0.17 ± 0.02 | 1.00 |
| Q4 blast radius R | 0.04 ± 0.19 | 0.04 ± 0.19 | 0.02 ± 0.10 | 1.00 |
| Q7 exposure R | 0.07 ± 0.08 | 0.07 ± 0.08 | 0.07 ± 0.08 | 1.00 |
| Spans kept / workflow | 0.85 ± 0.46 | 0.85 ± 0.46 | 0.85 ± 0.46 | 0.85 ± 0.46 |
| Lost spans detected | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.88 ± 0.00 |

## Table 15. Collector processors operators commonly enable


**passthrough**

fin.audit registry conformance: 1.00  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 1.00 | 1.00 | 1.00 |
| Q2 protected attempts found | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | 1.00 | 1.00 |
| Q3 supporting filings R | 0.88 ± 0.00 | 1.00 | 1.00 | 1.00 |
| Q4 blast radius R | 0.83 ± 0.22 | 1.00 | 1.00 | 1.00 |
| Q7 exposure R | 1.00 | 1.00 | 1.00 | 1.00 |
| Spans kept / workflow | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 |
| Stripped audit attributes detected | n/a | n/a | n/a | 0.00 |

**redaction_allowlist**

fin.audit registry conformance: 0.00  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 0.00 | 0.00 | 1.00 |
| Q2 protected attempts found | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | n/a | 1.00 |
| Q3 supporting filings R | 0.88 ± 0.00 | 0.88 ± 0.00 | 0.12 ± 0.01 | 1.00 |
| Q4 blast radius R | 0.83 ± 0.22 | 0.83 ± 0.22 | 0.00 | 1.00 |
| Q7 exposure R | 1.00 | 1.00 | 1.00 | 1.00 |
| Spans kept / workflow | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 |
| Stripped audit attributes detected | n/a | n/a | n/a | 1.00 |

**drop_tool_arguments**

fin.audit registry conformance: 1.00  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 1.00 | 1.00 | 1.00 |
| Q2 protected attempts found | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | 1.00 | 1.00 |
| Q3 supporting filings R | 0.12 ± 0.01 | 0.12 ± 0.01 | 1.00 | 1.00 |
| Q4 blast radius R | 0.00 | 0.00 | 1.00 | 1.00 |
| Q7 exposure R | 1.00 | 1.00 | 1.00 | 1.00 |
| Spans kept / workflow | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 |
| Stripped audit attributes detected | n/a | n/a | n/a | 0.00 |

**truncate_64**

fin.audit registry conformance: 1.00  
| Query | B0 | B1 | FAOGF-S | FAOGF |
|---|---|---|---|---|
| Q1 authority chain | n/a | 1.00 | 1.00 | 1.00 |
| Q2 protected attempts found | 1.00 | 1.00 | 1.00 | 1.00 |
| Q2 policy version | n/a | n/a | 1.00 | 1.00 |
| Q3 supporting filings R | 0.88 ± 0.00 | 1.00 | 1.00 | 1.00 |
| Q4 blast radius R | 0.83 ± 0.22 | 1.00 | 1.00 | 1.00 |
| Q7 exposure R | 1.00 | 1.00 | 1.00 | 1.00 |
| Spans kept / workflow | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 | 14.50 ± 1.05 |
| Stripped audit attributes detected | n/a | n/a | n/a | 0.00 |

## Tamper detection

500/500 single-point manipulations detected (delete_record 125/125, edit_body 120/120, insert_forged 127/127, reorder 128/128) over a 3555-record chain. A full suffix rewrite is not detected by chain verification alone (False) but is detected against an externally anchored head hash (True).

## Table 9. Per-call instrumentation latency (µs; tool work excluded)

| Path | p50 | p95 | p99 |
|---|---|---|---|
| bare_tool | 1.1 | 1.5 | 2.0 |
| otel_genai_span | 37.7 | 70.4 | 91.0 |
| faogf_read_memstore | 141.5 | 203.6 | 319.7 |
| faogf_read_filestore | 196.7 | 287.5 | 562.1 |
| faogf_protected_filestore | 193.4 | 291.3 | 661.2 |
