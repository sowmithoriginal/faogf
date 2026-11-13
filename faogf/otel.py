"""OpenTelemetry wiring. Spans are exported as plain dicts so the same run can
be projected into baseline schemas. `drop_rate` simulates export loss."""
import json
import random
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class CollectingExporter(SpanExporter):
    def __init__(self, drop_rate=0.0, seed=0):
        self.spans, self.dropped = [], 0
        self.drop_rate, self.rng = drop_rate, random.Random(seed)

    def export(self, spans):
        for s in spans:
            if self.drop_rate and self.rng.random() < self.drop_rate:
                self.dropped += 1
                continue
            self.spans.append(span_to_dict(s))
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def span_to_dict(s):
    return {
        "name": s.name,
        "trace_id": format(s.context.trace_id, "032x"),
        "span_id": format(s.context.span_id, "016x"),
        "parent_id": format(s.parent.span_id, "016x") if s.parent else None,
        "start": s.start_time / 1e9,
        "end": s.end_time / 1e9,
        "status": s.status.status_code.name,
        "sampled": s.context.trace_flags.sampled,
        "status_description": s.status.description or "",
        "attributes": {k: (list(v) if isinstance(v, tuple) else v) for k, v in s.attributes.items()},
        "links": [format(l.context.span_id, "016x") for l in s.links],
    }


def make_tracer(drop_rate=0.0, seed=0, sampler=None):
    exporter = CollectingExporter(drop_rate, seed)
    provider = TracerProvider(sampler=sampler) if sampler else TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("faogf"), exporter, provider


def span_bytes(span):
    return len(json.dumps(span, separators=(",", ":")))
