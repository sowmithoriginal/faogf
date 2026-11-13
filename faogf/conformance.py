"""Live conformance check of emitted spans against the fin.audit semantic-convention registry."""
import glob
import os
import yaml

TYPES = {"string": str, "int": int, "boolean": bool, "string[]": list}


def load_registry(path="semconv/registry"):
    attrs, groups = {}, {}
    for f in glob.glob(os.path.join(path, "*.yaml")):
        doc = yaml.safe_load(open(f)) or {}
        for g in doc.get("groups", []):
            for a in g.get("attributes", []):
                if "id" in a:
                    attrs[a["id"]] = a["type"]
            if g.get("type") == "span":
                groups[g["id"]] = g["attributes"]
    return attrs, groups


def _group_for(span):
    a = span["attributes"]
    if a.get("gen_ai.operation.name") == "execute_tool":
        return "span.fin.audit.execute_tool"
    if a.get("gen_ai.operation.name") == "chat":
        return "span.fin.audit.chat"
    if a.get("fin.audit.action") == "decide":
        return "span.fin.audit.decision"
    return None


def check(spans, registry=None):
    attrs, groups = registry or load_registry()
    out = {"spans_checked": 0, "conformant": 0, "unknown_attribute": 0, "wrong_type": 0, "missing_required": 0}
    for s in spans:
        g = _group_for(s)
        if not g:
            continue
        out["spans_checked"] += 1
        a, bad = s["attributes"], False
        for k, v in a.items():
            if k.startswith("fin.audit."):
                if k not in attrs:
                    out["unknown_attribute"] += 1; bad = True
                elif not isinstance(v, TYPES[attrs[k]]) or (attrs[k] == "int" and isinstance(v, bool)):
                    out["wrong_type"] += 1; bad = True
        tool = a.get("gen_ai.tool.name")
        for req in groups[g]:
            lvl = req["requirement_level"]
            need = lvl == "required" or (isinstance(lvl, dict) and "conditionally_required" in lvl
                                         and "except delegate" in lvl["conditionally_required"] and tool != "delegate")
            if need and req["ref"] not in a:
                out["missing_required"] += 1; bad = True
        out["conformant"] += not bad
    out["conformance_rate"] = round(out["conformant"] / out["spans_checked"], 4) if out["spans_checked"] else None
    return out
