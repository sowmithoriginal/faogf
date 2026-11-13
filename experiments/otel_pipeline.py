"""Run experiments through a REAL OpenTelemetry pipeline:

    agent -> OTel SDK (BatchSpanProcessor) -> OTLP/HTTP -> otelcol-contrib (processors) -> file exporter

The collector binary is located via $OTELCOL_BIN (default: ./bin/otelcol-contrib).
Download: https://github.com/open-telemetry/opentelemetry-collector-releases/releases
(otelcol-contrib_<version>_<os>_<arch>.tar.gz).
"""
import json
import os
import socket
import subprocess
import tempfile
import time

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanProcessor

COLLECTOR = os.environ.get("OTELCOL_BIN", "bin/otelcol-contrib")

PROCESSORS = {
    # what an operator typically enables; each is a real otelcol-contrib processor
    "passthrough": {},
    "tail_sampling": {"tail_sampling": {
        "decision_wait": "2s", "num_traces": 200000,
        "policies": [
            {"name": "errors", "type": "status_code", "status_code": {"status_codes": ["ERROR"]}},
            {"name": "sensitive-tool", "type": "string_attribute",
             "string_attribute": {"key": "gen_ai.tool.name", "values": ["distribute_report"]}},
            {"name": "baseline-10pct", "type": "probabilistic", "probabilistic": {"sampling_percentage": 10}},
        ]}},
    "redaction_allowlist": {"redaction": {   # hardening: keep only known semantic-convention keys
        "allow_all_keys": False, "summary": "silent",
        "allowed_keys": ["gen_ai.operation.name", "gen_ai.tool.name", "gen_ai.tool.call.id",
                         "gen_ai.tool.call.arguments", "gen_ai.agent.id", "gen_ai.request.model"]}},
    "drop_tool_arguments": {"attributes/drop_args": {   # PII hygiene: never ship raw tool arguments
        "actions": [{"key": "gen_ai.tool.call.arguments", "action": "delete"}]}},
    "truncate_64": {"transform/truncate": {   # cost control: cap attribute length
        "error_mode": "ignore",
        "trace_statements": [{"context": "span", "statements": ["truncate_all(span.attributes, 64)"]}]}},
}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _yaml(obj, indent=0):
    """Tiny YAML emitter (JSON is valid YAML; this keeps configs readable in logs)."""
    return json.dumps(obj, indent=2)


class Collector:
    def __init__(self, processor="passthrough"):
        self.dir = tempfile.mkdtemp(prefix="otelcol_")
        self.out = os.path.join(self.dir, "spans.json")
        self.port = _free_port()
        self.cfg_name = processor
        procs = PROCESSORS[processor]
        cfg = {
            "receivers": {"otlp": {"protocols": {"http": {"endpoint": f"127.0.0.1:{self.port}"}}}},
            "processors": {**procs, "batch": {}},
            "exporters": {"file": {"path": self.out}},
            "service": {"telemetry": {"metrics": {"level": "none"}, "logs": {"level": "warn"}},
                        "pipelines": {"traces": {"receivers": ["otlp"], "processors": list(procs) + ["batch"],
                                                 "exporters": ["file"]}}},
        }
        self.cfg = os.path.join(self.dir, "config.yaml")
        open(self.cfg, "w").write(_yaml(cfg))
        self.log = open(os.path.join(self.dir, "collector.log"), "w")
        self.proc = subprocess.Popen([COLLECTOR, "--config", self.cfg], stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.5).close()
                return
            except OSError:
                if self.proc.poll() is not None:
                    raise RuntimeError(open(os.path.join(self.dir, "collector.log")).read())
                time.sleep(0.2)
        raise RuntimeError("collector did not start")

    @property
    def endpoint(self):
        return f"http://127.0.0.1:{self.port}/v1/traces"

    def stop(self, wait=0.0):
        time.sleep(wait)
        self.proc.terminate()
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()

    def spans(self):
        return read_file_export(self.out) if os.path.exists(self.out) else []


def _val(v):
    if "stringValue" in v:
        return v["stringValue"]
    if "intValue" in v:
        return int(v["intValue"])
    if "doubleValue" in v:
        return float(v["doubleValue"])
    if "boolValue" in v:
        return bool(v["boolValue"])
    if "arrayValue" in v:
        return [_val(x) for x in v["arrayValue"].get("values", [])]
    return None


_STATUS = {0: "UNSET", 1: "OK", 2: "ERROR", "STATUS_CODE_UNSET": "UNSET", "STATUS_CODE_OK": "OK",
           "STATUS_CODE_ERROR": "ERROR"}


def read_file_export(path):
    """OTLP-JSON (file exporter) -> the span dict format used by experiments.analysis."""
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        for rs in json.loads(line).get("resourceSpans", []):
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    st = sp.get("status", {})
                    out.append({
                        "name": sp["name"], "trace_id": sp["traceId"], "span_id": sp["spanId"],
                        "parent_id": sp.get("parentSpanId") or None,
                        "start": int(sp["startTimeUnixNano"]) / 1e9, "end": int(sp["endTimeUnixNano"]) / 1e9,
                        "status": _STATUS.get(st.get("code", 0), "UNSET"),
                        "status_description": st.get("message", ""),
                        "attributes": {a["key"]: _val(a["value"]) for a in sp.get("attributes", [])},
                        "links": [l["spanId"] for l in sp.get("links", [])],
                    })
    return out


class _Counter(SpanProcessor):
    """Counts spans produced by the SDK, so loss = produced - received is measurable."""

    def __init__(self):
        self.n = 0

    def on_end(self, span):
        if span.context.trace_flags.sampled:
            self.n += 1


def otlp_telemetry(collector, max_queue_size=2048, max_export_batch_size=512, schedule_delay_millis=5000,
                   sampler=None):
    """Factory for build.run_suite(telemetry=...)."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    def factory():
        provider = TracerProvider(sampler=sampler) if sampler else TracerProvider()
        counter = _Counter()
        provider.add_span_processor(counter)
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=collector.endpoint), max_queue_size=max_queue_size,
            max_export_batch_size=max_export_batch_size, schedule_delay_millis=schedule_delay_millis))

        def collect():
            wait = 4.0 if "tail" in collector.cfg_name else 1.0
            collector.stop(wait=wait)
            spans = collector.spans()
            return spans, max(counter.n - len(spans), 0)
        return provider.get_tracer("faogf"), provider, collect
    return factory
