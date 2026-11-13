# FAOGF: Auditable Evidence Provenance for Autonomous Financial AI Agents on OpenTelemetry

Prototype, `fin.audit.*` semantic-convention registry, experiment harness and result files for the paper:

> S. Javvaji, "FAOGF: Auditable Evidence Provenance for Autonomous Financial AI Agents on OpenTelemetry,"
> *International Journal of Data Science and Machine Learning (IJDSML)*, ISSN 2692-5141 (under revision).

Author: Sowmith Javvaji, ORCID [0009-0001-7473-8417](https://orcid.org/0009-0001-7473-8417)

FAOGF (Financial Agent Observability and Governance Framework) is an OpenTelemetry-compatible audit layer for
AI agents. A gateway binds every model call and action to the version-exact, content-hashed evidence that was in
the model's context, plus the delegation and policy version that permitted it. It writes that record
synchronously to a hash-chained evidence store before exporting standard spans, so audit completeness does not
depend on what the tracing pipeline keeps.

## Reproducing the paper

| Paper item | What it shows | How to reproduce | Recorded output |
|---|---|---|---|
| Tables VI–VIII, XII–XV; Figs. 2–5 | Controlled study E1–E12 (scripted agent, 200 workflows × 5 seeds) | `python3 -m experiments.run_all -n 200 --seeds 5 --sizes 250,1000,4000,10000` then `python3 -m experiments.report results/results_scripted.json` | `results/results_scripted.json`, `results/report_scripted.md`, `results/fig*.png` |
| Tables IX–XI | Real OpenTelemetry pipeline: sampling, export-queue overflow, Collector processors (E13–E15) | Install the Collector (`bin/README.md`), then `python3 -m experiments.run_all -n 200 --seeds 5 --only e13,e14,e15` | same files |
| Table XVI | Real-filing study, live SEC EDGAR, gpt-4o-mini and gpt-4o | `python3 -m experiments.real_study ...` (three runs, see below) | `results/real/` |
| Q1–Q9 scoring | Oracle, metrics, intervals, LLM judge | — | `repro/SCORING.md` |
| Versions, dates, settings | Software, machines, model runs, SDK settings | — | `repro/RUNS.md`, `repro/environment-mac.json` |
| Collector configurations | Exact configs used in E13–E15 | — | `collector/` |
| `fin.audit.*` registry | 19 attributes, 3 span groups (Weaver format) | `weaver registry check -r semconv/registry` (Weaver v0.28.0) | `semconv/registry/` |

The controlled study is deterministic given its seeds and needs no API key. Full runs take a few minutes on a
laptop.

### Real-filing study (Table XVI)

All three runs were made on 2026-10-24 at temperature 0, through the OpenAI Chat Completions API by model alias.

```bash
export OPENAI_API_KEY=...
export SEC_USER_AGENT="Your Name your@email"      # required by the SEC fair-access policy

# Run 1: gpt-4o-mini, 50 questions, analyst notes flagged as unverified in the system prompt
python3 -m experiments.real_study --model gpt-4o-mini -n 50 --judge
# Run 2: gpt-4o-mini, 50 questions, no warning
# Run 3: gpt-4o, first 20 questions, no warning
#   (use the no-warning option listed by: python3 -m experiments.real_study --help)
```

You can re-score Table XVI without API access. Every model call (request and response) is in
`results/real/*_calls.jsonl`, and the evidence stores and exported spans of runs 2 and 3 are in
`results/real/*_store.jsonl` and `*_spans.json`. Run 1 predates store/span export in the harness; see
`results/real/README.md`. SEC EDGAR responses were cached locally during the runs. They are public filings and
are re-fetched on demand.

## Installation

```bash
git clone https://github.com/sowmithoriginal/faogf.git
cd faogf
python3 -m pip install -r requirements.txt     # Python 3.12; OpenTelemetry SDK 1.45.1
```

The pipeline experiments need `otelcol-contrib` v0.163.2 in `bin/` (instructions in `bin/README.md`). Without it,
E13 runs only its head-sampling part and E14/E15 are skipped.

Tests (no network):

```bash
python3 -m tests.tests_openai_mock       # OpenAI code path with a fake client
python3 -m tests.test_real_study_mock    # real-filing study with fake SEC and fake OpenAI
```

## Repository map

| Path | Purpose |
|---|---|
| `faogf/schema.py` | Attribute vocabulary: reused `gen_ai.*` semantic conventions plus the `fin.audit.*` extensions |
| `faogf/gateway.py` | Capture boundary: delegation binding, policy check (fail-closed), evidence and context capture, OTel spans |
| `faogf/delegation.py` | Gateway-minted delegations, narrowing rule, lineage and revocation (semantics adopted from Mishra and Sharad) |
| `faogf/policy.py` | Versioned declarative policies, deny-overrides, default deny, evaluator error treated as deny |
| `faogf/store.py` | Append-only, hash-chained evidence store |
| `faogf/merkle.py` | Epoch Merkle roots, inclusion proofs, anchored-root checking |
| `faogf/conformance.py`, `semconv/` | `fin.audit.*` Weaver registry and span conformance checker |
| `faogf/otel.py` | OpenTelemetry SDK setup |
| `agent/` | Orchestrator and analyst sub-agent, tools, synthetic filing corpus, live SEC EDGAR tools, scripted and OpenAI model backends |
| `experiments/workload.py`, `build.py` | Workload generator and suite runner |
| `experiments/analysis.py` | Audit queries Q1–Q9 under each telemetry condition |
| `experiments/run_all.py` | Controlled experiments E1–E15 |
| `experiments/otel_pipeline.py` | Real Collector harness (OTLP/HTTP to otelcol-contrib) |
| `experiments/real_study.py` | Real-filing study |
| `experiments/report.py` | Tables (Markdown) and figures (PNG/PDF) |
| `collector/` | Collector configurations used in E13–E15 |
| `data/fab_public.csv` | Finance Agent Benchmark public validation split, 50 questions (see Data) |
| `results/` | Recorded outputs behind every table and figure |
| `repro/` | Scoring procedure, run details, environment record, helper scripts |

## Experiments

| ID | Question |
|---|---|
| E1 | Which audit questions can each telemetry design answer, under three sub-agent hand-off modes? |
| E2 | How does each design degrade as spans are lost in export? |
| E3 | Does capture-as-precondition hold when evidence-store writes fail? |
| E4 | Are edits, deletions, reorderings and forged inserts in the store detected? |
| E5 | What does instrumentation cost per call? |
| E6 | Which component is responsible for which query (ablations)? |
| E7 | How do storage, chain verification and audit sweeps scale to 10,000 workflows? |
| E8 | What happens under correlated outages, and does the local spool fix it? |
| E9 | How sensitive are the baselines to context eviction and delegation rate? |
| E10 | How do content-logging baselines (log tool results; log full prompts) compare, at what storage and privacy cost? |
| E11 | Can context binding drive enforcement against injections that target allowed destinations? |
| E12 | Do epoch Merkle anchors detect and localize full-suffix rewrites and allow single-record disclosure? |
| E13 | How do real OpenTelemetry sampling strategies (SDK head sampling, Collector tail sampling) affect auditability? |
| E14 | What does SDK batch-queue overflow on the real OTLP path cost each design, and is the loss detected? |
| E15 | Do commonly enabled Collector processors silently break audit telemetry, and does FAOGF detect it? |

### Telemetry conditions (all projected from the same runs)

* **B0**: OpenTelemetry GenAI semantic-convention spans; tool arguments on, results and prompts off.
* **B1**: B0 plus delegation attributes (principal, delegation id, parent), approximating delegation telemetry.
* **B2**: B0 plus full tool results.
* **B3**: B2 plus full model input messages at every call.
* **FAOGF-S**: all `fin.audit.*` span attributes, spans only.
* **FAOGF**: spans plus the hash-chained evidence store (store first, span fallback).

## Interpreting the results

* Ground truth comes from the harness oracle, built from the runner's own record of tool outputs and context
  contents, not from FAOGF records.
* With no faults, FAOGF answers covered queries exactly by construction. The informative results are how far the
  baselines fall short and why (version blindness, context eviction, fragmented hand-off), the fault and pipeline
  experiments (span loss, store failures, tampering, sampling, queue overflow, Collector processors) and overhead.
* The controlled-study corpus (`agent/corpus.py`) is synthetic and fictional. The enforcement result (E11) uses a
  scripted agent that obeys planted instructions; the live models in the real-filing study followed none of them.
* `gen_ai.*` attribute names follow the OpenTelemetry GenAI semantic conventions, which are still evolving.

## Data

`data/fab_public.csv` is the 50-question public validation split of the Finance Agent Benchmark (Bigeard,
Nashold, Krishnan and Wu, 2025, arXiv:2508.00828), released by Vals AI under CC BY 4.0 at
https://github.com/vals-ai/finance-agent. It is redistributed here unmodified (SHA-256
`901e8cff562819007d43ff0c10b43b2e386481eb40f2157ba18da8fbbe05bff5`). See `data/ATTRIBUTION.md`.

## License

Code: MIT (see `LICENSE`). Benchmark questions in `data/`: CC BY 4.0, Vals AI.

## Citation

See `CITATION.cff`, or use GitHub's "Cite this repository" button. The archived release has a Zenodo DOI.
