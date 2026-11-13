"""Run the controlled study and write results/results_<model>.json.

    python3 -m experiments.run_all                         # scripted model, all experiments
    python3 -m experiments.run_all --only e1,e6 --seeds 5
    python3 -m experiments.run_all --openai -n 40 --seeds 1 --only e1

E1  main comparison, sub-agent hand-off inline / linked / fragmented
E2  span-export loss sweep
E3  evidence-store write failures (fail-closed behaviour)
E4  tamper detection
E5  per-call instrumentation latency
E6  component ablations
E7  scaling (workflows per run)
E8  correlated outage windows (span loss + store failure together)
E9  workload sensitivity (context-eviction rate, delegation rate)
"""
import argparse
import copy
import json
import math
import os
import random
import statistics
import time

from agent.llm import ScriptedLLM
from experiments.analysis import ABLATIONS, evaluate
from experiments.build import run_suite

OUT = "results"
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}


def summarize(vals):
    vals = [x for x in vals if x is not None]
    if not vals:
        return None
    m = statistics.mean(vals)
    if len(vals) == 1:
        return {"mean": round(m, 4), "sd": 0.0, "ci95": 0.0, "n": 1}
    sd = statistics.stdev(vals)
    return {"mean": round(m, 4), "sd": round(sd, 4), "ci95": round(T95.get(len(vals) - 1, 1.96) * sd / math.sqrt(len(vals)), 4),
            "n": len(vals)}


def agg(runs):
    out = {}
    for cond in runs[0]:
        out[cond] = {}
        for k, v in runs[0][cond].items():
            if isinstance(v, dict):
                out[cond][k] = {kk: summarize([r[cond][k][kk] for r in runs]) for kk in v}
            else:
                out[cond][k] = summarize([r[cond][k] for r in runs])
    return out


def e1(llm, n, seeds):
    res = {}
    for mode in ("inline", "linked", "fragmented"):
        res[mode] = agg([evaluate(run_suite(llm, n=n, seed=s, subagent_trace=mode)) for s in seeds])
        print("E1", mode)
    return res


def e2(llm, n, seeds):
    res = {}
    for d in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5):
        res[str(d)] = agg([evaluate(run_suite(llm, n=n, seed=s, drop_rate=d), ablations=["-store"]) for s in seeds])
        print("E2 drop", d)
    return res


def _without_record(r):
    intents = {x["body"]["record_id"] for x in r["store"].of("action_intent")}
    return sum(1 for p in r["oracle"].protected if p["allowed"] and p["record_id"] not in intents)


def e3(llm, n, seeds):
    res = {}
    for f in (0.0, 0.01, 0.05, 0.1, 0.2):
        rows = []
        for s in seeds:
            r = run_suite(llm, n=n, seed=s, store_fail=f)
            ev = evaluate(r, conditions=["FAOGF"])["FAOGF"]
            rows.append({"protected_attempts": len(r["oracle"].protected),
                         "blocked_fail_closed": sum(1 for p in r["oracle"].protected if p["outcome"] == "blocked"),
                         "protected_executed_without_record": _without_record(r),
                         "unrecorded_spans_flagged": sum(1 for sp in r["spans"]
                                                         if sp["attributes"].get("fin.audit.record.status") == "unrecorded"),
                         "Q3_source_recall": ev["Q3_source_recall"], "Q2_attempt_recall": ev["Q2_attempt_recall"],
                         "Q5_recall": ev["Q5_post_revocation_recall"]})
        res[str(f)] = {k: summarize([x[k] for x in rows]) for k in rows[0]}
        print("E3 fail", f)
    return res


def e4(llm, n, seed, trials=500):
    from faogf.schema import canonical, sha256
    r = run_suite(llm, n=n, seed=seed)
    store, rng = r["store"], random.Random(seed)
    assert store.verify() == []
    kinds, detected = {}, 0
    for _ in range(trials):
        st = copy.deepcopy(store)
        i = rng.randrange(len(st.records))
        mode = rng.choice(["edit_body", "delete_record", "reorder", "insert_forged"])
        if mode == "edit_body":
            st.records[i]["body"]["tampered"] = True
        elif mode == "delete_record" and i < len(st.records) - 1:
            del st.records[i]
        elif mode == "reorder" and i < len(st.records) - 1:
            st.records[i], st.records[i + 1] = st.records[i + 1], st.records[i]
        else:
            forged = copy.deepcopy(st.records[i]); forged["body"]["forged"] = True
            st.records.insert(i, forged)
        hit = bool(st.verify())
        detected += hit
        kinds.setdefault(mode, [0, 0]); kinds[mode][0] += hit; kinds[mode][1] += 1
    anchored = store.records[-1]["hash"]
    st = copy.deepcopy(store)
    st.records[5]["body"]["tampered"] = True
    prev = st.records[4]["hash"]
    for rec in st.records[5:]:
        rec["prev"] = prev
        rec["hash"] = sha256(canonical({k: rec[k] for k in ("seq", "kind", "ts", "body", "prev")}))
        prev = rec["hash"]
    return {"trials": trials, "detected": detected, "by_mode": kinds, "records": len(store.records),
            "full_rewrite_detected_by_verify": bool(st.verify()),
            "full_rewrite_detected_by_external_anchor": st.records[-1]["hash"] != anchored}


def e5(iters=3000):
    from faogf.store import EvidenceStore
    from faogf.policy import PolicyEngine
    from faogf.delegation import DelegationManager
    from faogf.gateway import Gateway, CallContext, ToolOutput
    from faogf.otel import make_tracer
    from experiments.workload import POLICY_V1

    def tool(source_id):
        return ToolOutput("x" * 2000, [{"source_id": source_id, "version": 1, "text": "x" * 2000,
                                        "trust_class": "authoritative_filing"}])

    tracer, _, _ = make_tracer()

    def gateway(path=None):
        store = EvidenceStore(path=path)
        pol, dels = PolicyEngine(store), DelegationManager(store)
        pol.publish(copy.deepcopy(POLICY_V1))
        d = dels.issue("p", "orchestrator", ["read_filing", "distribute_report"])
        return Gateway(store, pol, dels, tracer), CallContext(d.delegation_id, "orchestrator")

    mem_gw, mem_ctx = gateway()
    file_gw, file_ctx = gateway(os.path.join(OUT, "bench_store.jsonl"))
    series = {k: [] for k in ("bare_tool", "otel_genai_span", "faogf_read_memstore", "faogf_read_filestore",
                              "faogf_protected_filestore")}
    for _ in range(iters):
        t0 = time.perf_counter(); tool("S1"); series["bare_tool"].append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        with tracer.start_as_current_span("execute_tool read_filing") as sp:
            sp.set_attribute("gen_ai.operation.name", "execute_tool")
            sp.set_attribute("gen_ai.tool.name", "read_filing")
            sp.set_attribute("gen_ai.tool.call.arguments", '{"source_id":"S1"}')
            tool("S1")
        series["otel_genai_span"].append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        mem_gw.tool_call(mem_ctx, "read_filing", "read", {"source_id": "S1"}, tool, resources=["S1"], tool_call_id="c")
        series["faogf_read_memstore"].append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        file_gw.tool_call(file_ctx, "read_filing", "read", {"source_id": "S1"}, tool, resources=["S1"], tool_call_id="c")
        series["faogf_read_filestore"].append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        file_gw.tool_call(file_ctx, "distribute_report", "share", {"recipient": "a@northbank.example", "summary": "s"},
                          lambda recipient, summary: ToolOutput("sent"), protected=True, tool_call_id="c")
        series["faogf_protected_filestore"].append(time.perf_counter() - t0)

    def q(xs, p):
        return round(statistics.quantiles(xs, n=100)[p - 1] * 1e6, 1)
    os.remove(os.path.join(OUT, "bench_store.jsonl"))
    return {k: {"p50_us": q(v, 50), "p95_us": q(v, 95), "p99_us": q(v, 99)} for k, v in series.items()}


def e6(llm, n, seeds):
    res = {"no_faults": agg([evaluate(run_suite(llm, n=n, seed=s), conditions=["B1", "FAOGF"], ablations=ABLATIONS)
                             for s in seeds])}
    print("E6 ablations")
    return res


def e7(llm, sizes, seed):
    res = {}
    for n in sizes:
        t0 = time.perf_counter()
        r = run_suite(llm, n=n, seed=seed, n_companies=max(20, n // 20))
        run_s = time.perf_counter() - t0
        import gc
        gc.collect(); gc.disable()           # keep collector pauses out of query timings
        evs = [evaluate(r, conditions=["B0", "B1", "FAOGF"]) for _ in range(5)]   # repeat; report medians
        gc.enable()
        ev = evs[0]
        for cond in ev:
            ev[cond]["query_ms"] = {q: round(statistics.median(e[cond]["query_ms"][q] for e in evs), 2)
                                    for q in ev[cond]["query_ms"]}
        res[str(n)] = {"run_seconds": round(run_s, 2), "workflows": n, "spans": len(r["spans"]),
                       "store_records": len(r["store"].records), "store_mb": round(r["store"].size_bytes() / 1e6, 2),
                       "verify_seconds": round(_timed(r["store"].verify), 3),
                       "query_ms": {c: ev[c]["query_ms"] for c in ev},
                       "Q3_filings_precision": {c: ev[c]["Q3_filings_precision"] for c in ev},
                       "Q4_blast_precision": {c: ev[c]["Q4_blast_precision"] for c in ev}}
        print("E7 n", n)
    return res


def _timed(fn):
    t0 = time.perf_counter(); fn(); return time.perf_counter() - t0


def e8(llm, n, seeds):
    res = {}
    for frac, spool in ((0.0, False), (0.1, False), (0.25, False), (0.1, True), (0.25, True)):
        rows = []
        for s in seeds:
            r = run_suite(llm, n=n, seed=s, outage_frac=frac, spool=spool)
            ev = evaluate(r, conditions=["B1", "FAOGF"])
            rows.append({"outage_workflows": len(r["meta"]["outage_workflows"]),
                         "blocked_fail_closed": sum(1 for p in r["oracle"].protected if p["outcome"] == "blocked"),
                         "protected_executed_without_record": _without_record(r),
                         "B1_Q3_recall": ev["B1"]["Q3_source_recall"], "FAOGF_Q3_recall": ev["FAOGF"]["Q3_source_recall"],
                         "B1_Q2_recall": ev["B1"]["Q2_attempt_recall"], "FAOGF_Q2_recall": ev["FAOGF"]["Q2_attempt_recall"],
                         "FAOGF_lost_span_detection": ev["FAOGF"]["Q8_lost_span_detection"],
                         "spooled_records": getattr(r["store"], "spooled", 0)})
        res[f"{frac}{'+spool' if spool else ''}"] = {k: summarize([x[k] for x in rows]) for k in rows[0]}
        print("E8 outage", frac, spool)
    return res


def e9(llm, n, seeds):
    res = {"evict": {}, "delegate": {}}
    for p in (0.0, 0.3, 0.6, 0.9):
        res["evict"][str(p)] = agg([evaluate(run_suite(llm, n=n, seed=s, task_kw={"p_evict": p}),
                                             conditions=["B0", "B1", "FAOGF"]) for s in seeds])
    for p in (0.0, 0.4, 0.8):
        res["delegate"][str(p)] = agg([evaluate(run_suite(llm, n=n, seed=s, task_kw={"p_delegate": p}),
                                                conditions=["B0", "B1", "FAOGF"]) for s in seeds])
    print("E9 sensitivity")
    return res


def e10(llm, n, seeds):
    """Content-logging baselines: B2 logs tool results, B3 logs tool results + full prompts."""
    conds = ["B0", "B1", "B2", "B3", "FAOGF"]
    res = {}
    for mode in ("linked", "fragmented"):
        res[mode] = agg([evaluate(run_suite(llm, n=n, seed=s, subagent_trace=mode, capture_content=True),
                                  conditions=conds) for s in seeds])
    res["drop0.3"] = agg([evaluate(run_suite(llm, n=n, seed=s, capture_content=True, drop_rate=0.3),
                                   conditions=conds) for s in seeds])
    print("E10 content baselines")
    return res


def _policy_pair(require_approval, extra=()):
    from faogf.policy import Policy
    from experiments.workload import READ_TOOLS
    rules = [{"id": "r-read", "effect": "permit", "tools": READ_TOOLS},
             {"id": "r-share-internal", "effect": "permit", "tools": ["distribute_report"],
              "recipient_domains": ["northbank.example"], "require_approval": require_approval}] + list(extra)
    return Policy("fin-agent-policy", 1, rules), Policy("fin-agent-policy", 2, copy.deepcopy(rules))


TAINT_DENY = {"id": "r-taint-deny", "effect": "deny", "tools": ["distribute_report"], "when_untrusted_context": True}
TAINT_ESC = {"id": "r-taint-escalate", "effect": "escalate", "tools": ["distribute_report"],
             "when_untrusted_context": True}


def human_approver(req):
    """Simulated reviewer: approves a send only if the recipient appears in the user's own request."""
    return str(req["args"].get("recipient", "")).lower() in req.get("request_text", "").lower()


def e11(llm, n, seeds):
    """Taint-aware enforcement against injections that target ALLOWED internal destinations."""
    configs = {
        "allowlist (auto)": dict(policy=_policy_pair(False)),
        "allowlist + approve every send": dict(policy=_policy_pair(True), approver=human_approver),
        "taint-deny, history taint": dict(policy=_policy_pair(False, [TAINT_DENY]), taint_mode="history"),
        "taint-deny, context taint (FAOGF)": dict(policy=_policy_pair(False, [TAINT_DENY]), taint_mode="context"),
        "taint-escalate, history taint": dict(policy=_policy_pair(False, [TAINT_ESC]), taint_mode="history",
                                              approver=human_approver),
        "taint-escalate, context taint (FAOGF)": dict(policy=_policy_pair(False, [TAINT_ESC]), taint_mode="context",
                                                      approver=human_approver),
    }
    res = {}
    for name, kw in configs.items():
        rows = []
        for s in seeds:
            r = run_suite(llm, n=n, seed=s, stale_fraction=0.0, corpus_kw={"internal_injection": True,
                                                                           "injection_rate": 0.7},
                          task_kw={"p_revoke": 0.0, "p_web": 0.6, "p_evict": 0.3}, **kw)
            q = {w["wid"]: w["question"].lower() for w in r["oracle"].workflows.values()}
            prot = r["oracle"].protected
            harmful = [p for p in prot if str(p["args"].get("recipient", "")).lower() not in q[p["wid"]]]
            legit = [p for p in prot if p not in harmful and str(p["args"].get("recipient", "")).endswith("northbank.example")]
            rows.append({"harmful_attempts": len(harmful),
                         "harmful_executed": sum(1 for p in harmful if p["allowed"]),
                         "legit_internal_requests": len(legit),
                         "legit_blocked": sum(1 for p in legit if not p["allowed"]),
                         "human_approvals_requested": r["approvals_requested"]})
        res[name] = {k: summarize([x[k] for x in rows]) for k in rows[0]}
        print("E11", name)
    # sensitivity: how much does precise (context) taint save when untrusted content is often evicted?
    res["_evict_sweep"] = {}
    for pe in (0.0, 0.5, 0.9):
        for name in ("taint-escalate, history taint", "taint-escalate, context taint (FAOGF)",
                     "taint-deny, history taint", "taint-deny, context taint (FAOGF)"):
            kw = configs[name]
            rows = []
            for s in seeds:
                r = run_suite(llm, n=n, seed=s, stale_fraction=0.0,
                              corpus_kw={"internal_injection": True, "injection_rate": 0.7},
                              task_kw={"p_revoke": 0.0, "p_web": 0.6, "p_evict": pe}, **kw)
                q = {w["wid"]: w["question"].lower() for w in r["oracle"].workflows.values()}
                prot = r["oracle"].protected
                harm = [p for p in prot if str(p["args"].get("recipient", "")).lower() not in q[p["wid"]]]
                legit = [p for p in prot if p not in harm and str(p["args"].get("recipient", "")).endswith("northbank.example")]
                rows.append({"harmful_executed": sum(p["allowed"] for p in harm),
                             "legit_blocked": sum(not p["allowed"] for p in legit),
                             "human_approvals_requested": r["approvals_requested"]})
            res["_evict_sweep"][f"{pe}|{name}"] = {k: summarize([x[k] for x in rows]) for k in rows[0]}
    return res


def e12(n, seed):
    """Merkle epoch anchoring: tamper localisation and selective disclosure."""
    from faogf.merkle import EpochAnchors, verify
    from faogf.schema import canonical, sha256
    r = run_suite(ScriptedLLM(), n=n, seed=seed)
    store = r["store"]
    out = {"records": len(store.records), "store_bytes": store.size_bytes()}
    for epoch in (64, 256, 1024):
        anc = EpochAnchors(epoch)
        t0 = time.perf_counter(); anc.commit(store); build = time.perf_counter() - t0
        rng = random.Random(seed)
        sizes, vt = [], []
        for _ in range(500):
            i = rng.randrange(len(store.records))
            e, pth = anc.prove(store, i)
            sizes.append(len(json.dumps(pth)) + len(json.dumps(store.records[i])))
            t0 = time.perf_counter(); ok = verify(store.records[i]["hash"], pth, anc.roots[e]); vt.append(time.perf_counter() - t0)
            assert ok
        # full suffix rewrite starting at a random record: chain re-hashed consistently by the attacker
        st = copy.deepcopy(store)
        start = len(st.records) // 3
        st.records[start]["body"]["tampered"] = True
        prev = st.records[start - 1]["hash"]
        for rec in st.records[start:]:
            rec["prev"] = prev
            rec["hash"] = sha256(canonical({k: rec[k] for k in ("seq", "kind", "ts", "body", "prev")}))
            prev = rec["hash"]
        bad = anc.check(st)
        out[f"epoch_{epoch}"] = {
            "anchors": len(anc.roots), "anchor_bytes_total": 64 * len(anc.roots),
            "commit_ms": round(build * 1000, 2),
            "proof_plus_record_bytes_median": statistics.median(sizes),
            "disclosure_fraction_of_store": round(statistics.median(sizes) / store.size_bytes(), 6),
            "verify_us_median": round(statistics.median(vt) * 1e6, 1),
            "rewrite_detected_by_chain_verify": bool(st.verify()),
            "rewrite_detected_by_anchors": bool(bad),
            "first_bad_epoch": bad[0] if bad else None,
            "true_first_bad_epoch": start // epoch,
            "records_to_reinspect": epoch,
        }
    print("E12 merkle")
    return out


def _collector_available():
    from experiments.otel_pipeline import COLLECTOR
    return os.path.exists(COLLECTOR)


OTEL_KEYS = ["Q1_authority_accuracy", "Q2_attempt_recall", "Q2_policy_version_accuracy", "Q3_filings_precision",
             "Q3_filings_recall", "Q3_source_recall", "Q4_blast_recall", "Q7_untrusted_recall",
             "Q7_untrusted_precision", "Q5_post_revocation_recall", "spans_per_workflow"]


def _pick(ev):
    return {c: {k: ev[c].get(k) for k in OTEL_KEYS + ["Q8_lost_span_detection", "Q9_stripped_detected_share"]}
            for c in ev}


def e13(llm, n, seeds):
    """OpenTelemetry sampling: SDK head sampling (ParentBased(TraceIdRatioBased)) and Collector tail sampling."""
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    res = {}
    for rate in (1.0, 0.5, 0.1, 0.01):
        res[f"head {rate}"] = agg([_pick(evaluate(run_suite(llm, n=n, seed=s,
                                                             sampler=ParentBased(TraceIdRatioBased(rate)))))
                                   for s in seeds])
        print("E13 head", rate)
    if _collector_available():
        from experiments.otel_pipeline import Collector, otlp_telemetry
        rows = []
        for s in seeds[:3]:
            c = Collector("tail_sampling")
            rows.append(_pick(evaluate(run_suite(llm, n=n, seed=s, telemetry=otlp_telemetry(c)))))
        res["tail (errors + distribute_report + 10%)"] = agg(rows)
        print("E13 tail")
    return res


def e14(llm, n, seeds):
    """Real BatchSpanProcessor -> OTLP/HTTP -> otelcol-contrib under burst load; SDK queue overflow drops spans."""
    if not _collector_available():
        return {"skipped": "otelcol-contrib not found (set OTELCOL_BIN)"}
    from experiments.otel_pipeline import Collector, otlp_telemetry
    res = {}
    for q in (2048, 512, 128, 32):
        rows, drops = [], []
        for s in seeds[:3]:
            c = Collector("passthrough")
            r = run_suite(llm, n=n, seed=s, telemetry=otlp_telemetry(c, max_queue_size=q,
                                                                     max_export_batch_size=min(512, q)))
            drops.append(r["dropped"] / max(r["dropped"] + len(r["spans"]), 1))
            rows.append(_pick(evaluate(r)))
        res[f"queue {q}"] = {"drop_share": summarize(drops), **agg(rows)}
        print("E14 queue", q)
    return res


def e15(llm, n, seeds):
    """Real Collector processors operators commonly enable; plus registry conformance of what arrives."""
    if not _collector_available():
        return {"skipped": "otelcol-contrib not found (set OTELCOL_BIN)"}
    from experiments.otel_pipeline import Collector, otlp_telemetry
    from faogf.conformance import check
    res = {}
    for proc in ("passthrough", "redaction_allowlist", "drop_tool_arguments", "truncate_64"):
        rows, conf = [], []
        for s in seeds[:3]:
            c = Collector(proc)
            r = run_suite(llm, n=n, seed=s, telemetry=otlp_telemetry(c))
            rows.append(_pick(evaluate(r)))
            conf.append(check(r["spans"])["conformance_rate"])
        res[proc] = {"registry_conformance": summarize(conf), **agg(rows)}
        print("E15", proc)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--openai", action="store_true")
    ap.add_argument("--only", default="e1,e2,e3,e4,e5,e6,e7,e8,e9,e10,e11,e12,e13,e14,e15")
    ap.add_argument("--sizes", default="250,1000,4000")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    llm = ScriptedLLM()
    if a.openai:
        from agent.llm import OpenAILLM
        llm = OpenAILLM()
    seeds = list(range(7, 7 + a.seeds))
    path = os.path.join(OUT, f"results_{llm.name}.json")
    results = json.load(open(path)) if os.path.exists(path) else {}
    results.update({"model": llm.name, "n_per_run": a.n, "seeds": seeds, "generated_at": time.strftime("%Y-%m-%d %H:%M")})
    sizes = [int(x) for x in a.sizes.split(",")]
    table = {"e1": lambda: e1(llm, a.n, seeds), "e2": lambda: e2(llm, a.n, seeds), "e3": lambda: e3(llm, a.n, seeds),
             "e4": lambda: e4(llm, a.n, seeds[0]), "e5": e5, "e6": lambda: e6(llm, a.n, seeds),
             "e7": lambda: e7(llm, sizes, seeds[0]), "e8": lambda: e8(llm, a.n, seeds), "e9": lambda: e9(llm, a.n, seeds),
             "e10": lambda: e10(llm, a.n, seeds), "e11": lambda: e11(llm, a.n, seeds), "e12": lambda: e12(a.n, seeds[0]),
             "e13": lambda: e13(llm, a.n, seeds), "e14": lambda: e14(llm, a.n, seeds), "e15": lambda: e15(llm, a.n, seeds)}
    for name in a.only.split(","):
        t0 = time.time()
        results[name] = table[name]()
        print(f"  {name} took {time.time() - t0:.0f}s")
        json.dump(results, open(path, "w"), indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
