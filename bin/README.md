# OpenTelemetry Collector binary (not included in this repository)

The pipeline experiments (E13–E15) run a real OpenTelemetry Collector:
**otelcol-contrib v0.163.2**. The binary is too large for GitHub, so download it
into this folder before running the experiments.

macOS (Apple silicon):

    curl -L -o bin/otelcol.tgz https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.163.2/otelcol-contrib_0.163.2_darwin_arm64.tar.gz
    tar -xzf bin/otelcol.tgz -C bin otelcol-contrib

Linux (x86-64):

    curl -L -o bin/otelcol.tgz https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.163.2/otelcol-contrib_0.163.2_linux_amd64.tar.gz
    tar -xzf bin/otelcol.tgz -C bin otelcol-contrib

Check:

    bin/otelcol-contrib --version     # otelcol-contrib version 0.163.2

To use a binary stored somewhere else, set OTELCOL_BIN=/path/to/otelcol-contrib.
