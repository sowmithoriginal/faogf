# Runs, versions and dates

## Software
| Item | Version |
|---|---|
| FAOGF prototype | release `v1.0.0-ijdsml` (see GitHub release / Zenodo DOI) |
| Python | 3.12 (see `environment-mac.json`) |
| OpenTelemetry Python SDK | see `environment-mac.json` (1.45.x) |
| OpenTelemetry Collector | otelcol-contrib v0.163.2 (`bin/otelcol-contrib`) |
| OTel Weaver | v0.28.0 |
| OpenAI Python SDK | see `environment-mac.json` |

## Machines
| Label | Hardware / OS | Used for |
|---|---|---|
| Linux | x86-64 Linux cloud container | E1–E15, Table X Linux column |
| Apple M-series | Apple silicon MacBook Air, macOS (arm64) | E13–E15, real-filing study |

## Real-filing study (live models)
Models were called through the OpenAI Chat Completions API by alias at temperature 0.
The harness logged the requested alias; it did not log a dated snapshot identifier or
system fingerprint, so the served snapshot is whichever version OpenAI's alias pointed to
on the run date.

| Run | Model alias | Questions | Model calls | Run date | Files |
|---|---|---|---|---|---|
| 1, analyst notes flagged as unverified | gpt-4o-mini | 50 | 948 | 2026-10-24 | `results/real/real_gpt-4o-mini*` (calls and results only; store and spans not saved by that harness version) |
| 2, no warning | gpt-4o-mini | 50 | 612 | 2026-10-24 | `results/real/real_gpt-4o-mini_nowarn*` (incl. evidence store and spans) |
| 3, no warning | gpt-4o | 20 (first 20) | 334 | 2026-10-24 | `results/real/real_gpt-4o_nowarn*` (incl. evidence store and spans) |

Other settings: six-message context window per agent, 25-step limit, live SEC EDGAR
access with a disk cache (`agent/edgar.py`).

Questions: `data/fab_public.csv`, the 50-question public validation split of the Finance
Agent Benchmark (Vals AI, CC BY 4.0), used unmodified.
SHA-256 `901e8cff562819007d43ff0c10b43b2e386481eb40f2157ba18da8fbbe05bff5`.

## SDK settings for the pipeline experiments
| Experiment | Setting |
|---|---|
| E13 sampling | head sampling 1.0 / 0.5 / 0.1 / 0.01; tail sampling per `collector/02_tail_sampling.yaml` |
| E14 queue overflow | BatchSpanProcessor max_queue_size 2048 / 512 / 128 / 32, OTLP/HTTP to the Collector |
| E15 processors | `collector/01`, `03`, `04`, `05` |

## Reproduce
```bash
pip install -r requirements.txt
python3 -m experiments.run_all -n 200 --seeds 5 --sizes 250,1000,4000,10000   # E1–E15 -> results/results_scripted.json
python3 -m experiments.report results/results_scripted.json                     # tables and figures
python3 -m experiments.real_study --model gpt-4o-mini -n 50 --judge             # real-filing run 1 (needs OPENAI_API_KEY, SEC_USER_AGENT)
```
E13–E15 need `bin/otelcol-contrib` (see `bin/README.md`).
