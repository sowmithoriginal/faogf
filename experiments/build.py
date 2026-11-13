"""Assemble one experimental run: store, policies, delegations, gateways, runners."""
import copy
import random
from faogf.store import EvidenceStore, SpooledStore
from faogf.policy import PolicyEngine
from faogf.delegation import DelegationManager
from faogf.gateway import Gateway
from faogf.otel import make_tracer
from faogf.schema import now
from agent.corpus import Corpus, synthetic_tools
from agent.runner import Runner, Oracle, ORCH_TOOLS, retry
from experiments.workload import POLICY_V1, POLICY_V2, make_task

PRINCIPALS = ["analyst.jdoe", "pm.asmith", "risk.lchen", "ops.mgarcia", "research.tkim"]


def run_suite(llm, n=200, seed=7, drop_rate=0.0, store_fail=0.0, subagent_trace="fragmented",
              stale_fraction=0.25, tasks=None, n_companies=20, amend_per_event=3,
              outage_frac=0.0, outage_drop=0.9, outage_store_fail=0.9, registry=None, corpus=None,
              orch_tools=None, analyst_tools=None, task_kw=None, spool=False, spool_fail=0.01,
              capture_content=False, taint_mode=None, policy=None, approver=None, corpus_kw=None,
              telemetry=None, sampler=None):
    """telemetry: optional callable() -> (tracer, provider, collect) where collect() -> (spans, dropped).
    Used to route spans through a real OTLP exporter and OpenTelemetry Collector."""
    """outage_frac: fraction of workflows run inside a correlated outage window in which span
    export AND evidence-store writes fail with high probability (outage_drop / outage_store_fail)."""
    rng = random.Random(seed)
    store = EvidenceStore()
    if spool:
        local = EvidenceStore()
        local.set_faults(spool_fail, random.Random(seed + 2))
        store = SpooledStore(store, local)
    if telemetry:
        tracer, provider, collect = telemetry()
        exporter = None
    else:
        tracer, exporter, provider = make_tracer(drop_rate, seed, sampler)
        collect = lambda: (exporter.spans, exporter.dropped)
    policies, delegations = PolicyEngine(store), DelegationManager(store)
    policies.publish(copy.deepcopy(policy[0] if policy else POLICY_V1))
    corpus = corpus or Corpus(n_companies=n_companies, seed=seed, **(corpus_kw or {}))
    outbox = []
    registry = registry or synthetic_tools(corpus, outbox)
    oracle = Oracle()
    gkw = {"capture_content": capture_content, "taint_mode": taint_mode, "approver": approver}
    gw = Gateway(store, policies, delegations, tracer, **gkw)
    tasks = tasks or [make_task(rng, corpus, **(task_kw or {})) for _ in range(n)]
    meta = {"v2_published_at": None, "n": len(tasks), "seed": seed, "drop_rate": drop_rate,
            "store_fail": store_fail, "subagent_trace": subagent_trace, "outage_frac": outage_frac,
            "outage_workflows": []}
    fault_rng = random.Random(seed + 1)
    store.set_faults(store_fail, fault_rng)
    stale_gw = None
    extra_gws = []
    events = {len(tasks) // 4, len(tasks) // 2, 3 * len(tasks) // 4}
    for i, task in enumerate(tasks):
        if i in events and amend_per_event:
            corpus.amend_random(amend_per_event)        # restatements arrive over time
        if i == len(tasks) // 2:
            retry(lambda: policies.publish(copy.deepcopy(policy[1] if policy else POLICY_V2)))
            meta["v2_published_at"] = now()
            stale_gw = Gateway(store, policies, delegations, tracer, policy_pin=1, **gkw)
        in_outage = outage_frac and rng.random() < outage_frac
        if exporter:
            exporter.drop_rate = outage_drop if in_outage else drop_rate
        store.fail_rate = outage_store_fail if in_outage else store_fail
        if in_outage:
            meta["outage_workflows"].append(f"wf{i:04d}")
        g = gw
        if stale_gw and rng.random() < stale_fraction:
            g = stale_gw                               # lagging gateway still on policy v1
        if task.get("revoke_after") is not None and rng.random() < 0.5:
            g = Gateway(store, policies, delegations, tracer, policy_pin=g.policy_pin,
                        revocation_view={}, **gkw)            # revocation never propagates to this gateway
            extra_gws.append(g)
        if callable(task.get("on_start")):
            task["on_start"]()                         # per-workflow environment set-up (real study)
        runner = Runner(g, llm, registry, oracle, tracer, subagent_trace=subagent_trace,
                        orch_tools=orch_tools, analyst_tools=analyst_tools)
        principal = rng.choice(PRINCIPALS)
        root = retry(lambda: delegations.issue(principal, "orchestrator", (orch_tools or ORCH_TOOLS) + ["delegate"]))
        runner.run_workflow(f"wf{i:04d}", task, principal, root)
    store.fail_rate = 0.0
    provider.shutdown()
    spans, dropped = collect()
    approvals = sum(getattr(x, "approvals_requested", 0) for x in {gw, stale_gw} if x) + sum(
        getattr(r_, "approvals_requested", 0) for r_ in extra_gws)
    return {"approvals_requested": approvals, "spans": spans, "dropped": dropped, "store": store, "oracle": oracle,
            "corpus": corpus, "meta": meta, "tasks": tasks, "delegations": delegations, "outbox": outbox}
