#!/usr/bin/env python3
"""Confirm which version of the Finance Agent Benchmark public questions was used.

The revised reference [11] pins the public question set to a specific Hugging
Face revision. This script downloads that exact revision, prints its SHA-256,
and checks that every question in your local question file appears in it, so
the citation matches what the experiments actually ran.

    python repro/verify_benchmark_questions.py --local path/to/your/questions_file

The local file may be the CSV you downloaded, a .txt with one question per line,
or a .json/.jsonl list of questions / objects with a "Question" or "question" field.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request

REPO = "vals-ai/finance_agent_benchmark"
REVISION = "1f80cefae847f2e8b6bdf773f789c90f70293f78"
FILE = "finance_agent_benchmark.csv"
URL = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{FILE}"


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def local_questions(path):
    raw = open(path, encoding="utf-8").read()
    if path.endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(raw)))
        key = next(k for k in rows[0] if k.lower() == "question")
        return [r[key] for r in rows]
    if path.endswith((".json", ".jsonl")):
        items = [json.loads(l) for l in raw.splitlines() if l.strip()] if path.endswith(".jsonl") \
            else json.loads(raw)
        return [i if isinstance(i, str) else (i.get("Question") or i.get("question")) for i in items]
    return [l for l in raw.splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", required=True)
    args = ap.parse_args()

    data = urllib.request.urlopen(URL, timeout=60).read()
    print(f"Pinned file : {URL}")
    print(f"SHA-256     : {hashlib.sha256(data).hexdigest()}")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    print(f"Questions   : {len(rows)}")
    pinned = {norm(r["Question"]) for r in rows}

    mine = local_questions(args.local)
    missing = [q for q in mine if norm(q) not in pinned]
    print(f"Local file  : {len(mine)} questions, {len(mine) - len(missing)} found in the pinned revision")
    if missing:
        print("\nNot found in pinned revision (check whether you used a different version):")
        for q in missing:
            print(" -", q[:120])
    else:
        print("\nOK: all local questions match the pinned revision; cite it as-is in reference [11].")


if __name__ == "__main__":
    main()
