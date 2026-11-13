#!/usr/bin/env python3
"""Record the software environment used for the FAOGF experiments.

Run once on each machine you report (Linux container, Apple M-series laptop)
from the root of the FAOGF repository:

    python repro/collect_environment.py --machine linux-x86_64 --out repro/environment-linux.json
    python repro/collect_environment.py --machine apple-m-series --out repro/environment-mac.json

It records Python, OS/CPU, every installed opentelemetry-* and openai package
version, the git commit/tag of the repository, and the versions reported by the
otelcol-contrib and weaver binaries (if they are on PATH or passed explicitly).
"""
import argparse
import datetime as dt
import json
import platform
import subprocess
import sys
from importlib import metadata


def run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def package_versions():
    wanted = ("opentelemetry", "openai", "requests", "httpx", "numpy", "pandas", "scipy")
    found = {}
    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "").lower()
        if name.startswith(wanted):
            found[name] = dist.version
    return dict(sorted(found.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", required=True, help="label used in the paper, e.g. linux-x86_64")
    ap.add_argument("--otelcol", default="otelcol-contrib", help="path to the otelcol-contrib binary")
    ap.add_argument("--weaver", default="weaver", help="path to the weaver binary")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    env = {
        "machine_label": args.machine,
        "recorded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "cpu_arch": platform.machine(),
        "processor": platform.processor() or None,
        "git": {
            "commit": run(["git", "rev-parse", "HEAD"]),
            "describe": run(["git", "describe", "--tags", "--always", "--dirty"]),
            "dirty": bool(run(["git", "status", "--porcelain"])),
        },
        "packages": package_versions(),
        "otelcol_contrib_version": run([args.otelcol, "--version"]),
        "weaver_version": run([args.weaver, "--version"]),
    }
    with open(args.out, "w") as f:
        json.dump(env, f, indent=2)
    print(json.dumps(env, indent=2))
    if env["git"]["dirty"]:
        print("\nWARNING: working tree has uncommitted changes; commit before tagging the release.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
