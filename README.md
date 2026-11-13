# FAOGF lab: prototype and experiments

Prototype of the Financial Agent Observability and Governance Framework (FAOGF) and the
experiment harness for the paper.

## What is here

| Path | Purpose |
|---|---|
| `faogf/schema.py` | Attribute vocabulary: reused `gen_ai.*` semconv + proposed `fin.audit.*` extensions |
| `faogf/gateway.py` | Capture boundary: delegation binding, policy check (fail-closed), evidence capture, OTel spans |
| `faogf/delegation.py` | Gateway-minted delegations, narrowing rule, lineage, revocation (adopted from CIM / Jeffs) |
| `faogf/policy.py` | Versioned declarative policies, deny-overrides, default deny, evaluator error = deny |
| `faogf/store.py` | Append-only, hash-chained evidence store (record-of-record path) |
| `agent/` | Orchestrator + analyst sub-agent, tools, synthetic filing corpus, scripted and OpenAI backends |
| `experiments/analysis.py` | Audit queries Q1-Q8 evaluated under B0, B1, FAOGF-S, FAOGF |
| `experiments/run_all.py` | E1-E5 (comparison, span loss, store faults, tamper, overhead) |
| `experiments/report.py` | Tables (Markdown) and figures (PNG/PDF) |

## Conditions (all projected from the same runs)

* **B0**: OpenTelemetry GenAI semantic-convention spans, tool-argument capture enabled, results off.
* **B1**: B0 + delegation attributes (principal, delegation id, parent). Approximates CIM-style telemetry.
* **FAOGF-S**: all `fin.audit.*` span attributes, spans only.
* **FAOGF**: spans + hash-chained evidence store, store first with span fallback.

## Run

```bash
pip3 install -r requirements.txt   # opentelemetry-sdk, openai, matplotlib, requests, beautifulsoup4

# 1. Controlled study, deterministic and free (E1-E9, about 3 minutes)
python3 -m experiments.run_all -n 200 --seeds 5 --sizes 250,1000,4000,10000
python3 -m experiments.report results/results_scripted.json

# 2. Same controlled study driven by a real model (start small, check cost)
export OPENAI_API_KEY=...  FAOGF_MODEL=gpt-4o-mini
python3 -m experiments.run_all --openai -n 5 --seeds 1 --only e1
python3 -m experiments.run_all --openai -n 40 --seeds 1 --only e1,e6

# 3. Real-filing study: 50 public Finance Agent Benchmark questions, live SEC EDGAR
export SEC_USER_AGENT="Your Name your@email"     # required by SEC fair-access policy
python3 -m experiments.real_study --model gpt-4o-mini -n 5            # smoke test
python3 -m experiments.real_study --model gpt-4o-mini -n 50 --judge   # full run + rubric grading
```

| Experiment | Question it answers |
|---|---|
| E1 | Which audit questions can each telemetry design answer, under three sub-agent hand-off modes? |
| E2 | How does each design degrade as spans are lost in export? |
| E3 | Does capture-as-precondition hold when evidence-store writes fail? |
| E4 | Are edits, deletions, reorderings and forged inserts in the store detected? |
| E5 | What does instrumentation cost per tool call? |
| E6 | Which component is responsible for which query (ablations)? |
| E7 | How do storage, chain verification and audit sweeps scale to 10k workflows? |
| E8 | What happens under correlated outages, and does the local spool fix it? |
| E9 | How sensitive are baselines to context eviction and delegation rate? |
| E10 | How do content-logging baselines (log tool results; log full prompts) compare, and at what storage/privacy cost? |
| E11 | Can FAOGF's context binding drive enforcement (taint-aware policy) against injections that target allowed destinations? |
| E12 | Do epoch Merkle anchors detect and localise full-suffix rewrites and allow single-record disclosure to auditors? |
| E13 | How do real OpenTelemetry sampling strategies (SDK head sampling, Collector tail sampling) affect auditability? |
| E14 | What does SDK batch-queue overflow on the real OTLP path cost each design, and is the loss detected? |
| E15 | Do Collector processors operators commonly enable (redaction allow-list, attribute deletion, truncation) silently break audit telemetry, and does FAOGF detect it? |
| real_study | Do the conclusions hold with a real model on real filings? Injection compliance and containment, citation faithfulness, task accuracy, token usage |

SEC responses are cached in `data/sec_cache/` and every model call is logged to
`results/*_calls.jsonl`; archive both with the paper's artifact.

## Important framing for the paper

* Ground truth comes from the harness `Oracle`, built from raw tool outputs, not from FAOGF records.
* With no faults, FAOGF scores 1.0 **by construction for covered events**, as Mishra & Sharad report
  for CIM. The informative results are (a) how far baselines fall short and why (version blindness,
  context eviction, fragmented hand-off), (b) the fault experiments (span loss, store failures,
  tampering, lagging gateways), and (c) overhead.
* The synthetic corpus (`agent/corpus.py`) is generated and fictional: 20+ issuers, annual/quarterly/current
  reports, scheduled restatements, and five planted indirect-injection styles. The real-model run tests whether conclusions hold when a real
  model, not a script, chooses tools; it does not test retrieval accuracy on real filings.
* `gen_ai.*` attribute names follow the OTel GenAI semantic conventions, which are still evolving.
  Pin and cite the version you check them against.

## Tests

```bash
python3 -m tests.tests_openai_mock       # OpenAI code path with a fake client, no network
python3 -m tests.test_real_study_mock    # real-filing study with fake SEC + fake OpenAI, no network
```


## OpenTelemetry Collector experiments (E13 tail sampling, E14, E15)

These run spans through a real `otelcol-contrib`. Download the build for your machine from
https://github.com/open-telemetry/opentelemetry-collector-releases/releases (e.g. on an Apple-silicon Mac,
`otelcol-contrib_<version>_darwin_arm64.tar.gz`), then:

```bash
mkdir -p bin && tar xzf ~/Downloads/otelcol-contrib_*_darwin_arm64.tar.gz -C bin
xattr -d com.apple.quarantine bin/otelcol-contrib 2>/dev/null   # macOS Gatekeeper
python3 -m experiments.run_all -n 200 --seeds 5 --only e13,e14,e15
```

Without the binary, E13 still runs its head-sampling part and E14/E15 are skipped.

## Semantic-convention registry

`semconv/registry/` defines the `fin.audit.*` attributes and span groups in OpenTelemetry Weaver format
(validated with `weaver registry check -r semconv/registry`, weaver v0.28.0). `faogf/conformance.py` checks
emitted spans against it; E15 reports conformance after each Collector configuration.
