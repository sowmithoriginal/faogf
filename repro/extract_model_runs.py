#!/usr/bin/env python3
"""Recover exact model versions and run dates for the real-filing study.

The paper reports "gpt-4o-mini" and "gpt-4o"; the editor asks for exact model
versions and run dates. The OpenAI API returns the dated snapshot it actually
served (e.g. "gpt-4o-mini-2024-07-18") in each response's `model` field, plus a
`created` Unix timestamp. This script finds those values wherever they were
saved and summarizes them, without needing to re-run anything.

It scans, recursively, every *.json / *.jsonl file under the paths you give it
and recognizes two shapes:

  1. Cached OpenAI responses (agent/llm.py response cache):
       {"model": "gpt-4o-mini-2024-07-18", "created": 1730000000, ...}
     (also nested anywhere inside a larger JSON object, e.g. {"response": {...}})

  2. Exported OTLP JSON spans (Collector file exporter / evidence exports) with
     the GenAI attribute `gen_ai.response.model` (and `gen_ai.request.model`);
     the span's startTimeUnixNano gives the run time.

Usage (from the repo root):
    python repro/extract_model_runs.py .cache/llm experiments/out --csv repro/model_runs.csv

Then copy the printed summary into the "Model versions and run dates" table.
"""
import argparse
import csv
import datetime as dt
import json
import os
from collections import defaultdict


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def walk_json(obj, hits, source):
    if isinstance(obj, dict):
        # Shape 1: OpenAI response object
        if isinstance(obj.get("model"), str) and isinstance(obj.get("created"), (int, float)) \
                and ("choices" in obj or obj.get("object", "").startswith("chat.completion")):
            hits.append({"source": source, "kind": "openai_response",
                         "model": obj["model"], "ts": float(obj["created"])})
        # Shape 2: OTLP span with attributes list
        if "attributes" in obj and "startTimeUnixNano" in obj and isinstance(obj["attributes"], list):
            attrs = {}
            for a in obj["attributes"]:
                v = a.get("value", {})
                attrs[a.get("key")] = next(iter(v.values()), None) if isinstance(v, dict) else v
            model = attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model")
            if model:
                hits.append({"source": source, "kind": "otlp_span", "model": str(model),
                             "ts": int(obj["startTimeUnixNano"]) / 1e9})
        for v in obj.values():
            walk_json(v, hits, source)
    elif isinstance(obj, list):
        for v in obj:
            walk_json(v, hits, source)


def load(path, hits):
    with open(path, encoding="utf-8", errors="replace") as f:
        if path.endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if line:
                    try:
                        walk_json(json.loads(line), hits, path)
                    except json.JSONDecodeError:
                        pass
        else:
            try:
                walk_json(json.load(f), hits, path)
            except json.JSONDecodeError:
                # Collector file exporter writes one JSON document per line
                f.seek(0)
                for line in f:
                    try:
                        walk_json(json.loads(line), hits, path)
                    except json.JSONDecodeError:
                        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--csv", help="write every hit to this CSV")
    args = ap.parse_args()

    hits = []
    for root in args.paths:
        if os.path.isfile(root):
            load(root, hits)
            continue
        for d, _, files in os.walk(root):
            for name in files:
                if name.endswith((".json", ".jsonl")):
                    load(os.path.join(d, name), hits)

    if not hits:
        print("No model responses found. Point the script at the LLM response cache "
              "and/or the exported span files.")
        return

    by_model = defaultdict(list)
    for h in hits:
        by_model[(h["kind"], h["model"])].append(h["ts"])

    print(f"{'source kind':<16}{'model (as served)':<34}{'calls':>7}  first run (UTC)            last run (UTC)")
    for (kind, model), ts in sorted(by_model.items()):
        print(f"{kind:<16}{model:<34}{len(ts):>7}  {iso(min(ts)):<27}{iso(max(ts))}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["source", "kind", "model", "timestamp_utc"])
            for h in sorted(hits, key=lambda x: x["ts"]):
                w.writerow([h["source"], h["kind"], h["model"], iso(h["ts"])])
        print(f"\nWrote {len(hits)} rows to {args.csv}")


if __name__ == "__main__":
    main()
