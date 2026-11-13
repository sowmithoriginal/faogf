# OpenTelemetry Collector configurations used in the experiments

Collector: **otelcol-contrib v0.163.2** (binary in `bin/`).

These are the exact configurations the experiment harness generates in
`experiments/otel_pipeline.py` (`PROCESSORS` and `Collector.__init__`). At run time
the harness only substitutes a free local port for the OTLP/HTTP receiver and a
temporary output path for the file exporter.

| File | Processor(s) | Paper |
|---|---|---|
| 01_passthrough.yaml | batch only | Table X (E14), Table XI pass-through |
| 02_tail_sampling.yaml | tail_sampling: errors + distribute_report + 10% | Table IX (E13) |
| 03_redaction_allowlist.yaml | redaction, allow-list of 6 GenAI keys | Table XI (E15) |
| 04_drop_tool_arguments.yaml | attributes: delete gen_ai.tool.call.arguments | Table XI (E15) |
| 05_truncate_64.yaml | transform: truncate_all(span.attributes, 64) | Table XI (E15) |

The SDK side of each pipeline: BatchSpanProcessor exporting over OTLP/HTTP; queue
sizes 2,048 / 512 / 128 / 32 for E14; head sampling ratios 1.0 / 0.5 / 0.1 / 0.01 for E13.

Validate:

    for f in collector/*.yaml; do bin/otelcol-contrib validate --config "$f"; done
