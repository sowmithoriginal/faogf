"""Agent loop. Every tool and model call goes through the FAOGF gateway.

The Oracle is the experiment's ground truth. It is maintained by the harness
from raw tool outputs (corpus identities), independently of what the gateway
records, mirroring the gateway-side ground truth used by Mishra & Sharad.
"""
import json
from opentelemetry import context as otel_context, trace
from faogf.gateway import CallContext
from faogf.schema import now

ORCH_TOOLS = ["search_filings", "read_filing", "web_search", "calculate", "distribute_report", "delegate_analysis"]
ANALYST_TOOLS = ["read_filing", "calculate"]


def retry(fn, attempts=500):
    """Governance writes (issue/revoke/publish) are retried until durable."""
    for i in range(attempts):
        try:
            return fn()
        except IOError:
            if i == attempts - 1:
                raise


EVICTED = "[content evicted from context window]"


class Oracle:
    def __init__(self):
        self.workflows = {}     # wid -> truth dict
        self.protected = []     # every protected attempt
        self.executions = []    # every tool execution (allowed or not)
        self.repeats, self.loop_guard_trips = {}, 0


class Runner:
    def __init__(self, gateway, llm, registry, oracle, tracer, subagent_trace="fragmented", max_steps=12,
                 orch_tools=None, analyst_tools=None):
        assert subagent_trace in ("inline", "linked", "fragmented")
        self.gw, self.llm, self.oracle, self.tracer = gateway, llm, oracle, tracer
        self.tools = registry
        self.orch_tools = orch_tools or ORCH_TOOLS
        self.analyst_tools = analyst_tools or ANALYST_TOOLS
        self.subagent_trace = subagent_trace     # fragmented (new trace, no link) | linked (span link)
        self.max_steps = max_steps

    # ----------------------------------------------------------------------
    def run_workflow(self, wid, task, principal, root_delegation):
        with self.tracer.start_as_current_span("invoke_agent orchestrator",
                                               context=otel_context.Context()) as root:
            root.set_attribute("gen_ai.operation.name", "invoke_agent")
            trace_id = format(root.get_span_context().trace_id, "032x")
            self.gw.current_request = task["question"]
            truth = {"wid": wid, "root_trace_id": trace_id, "principal": principal, "question": task["question"],
                     "root_delegation": root_delegation.delegation_id, "revoked_at": None}
            self.oracle.workflows[wid] = truth
            ctx = CallContext(root_delegation.delegation_id, "orchestrator")
            messages = [{"role": "user", "content": task["question"]}]
            for j, (name, args) in enumerate(task.get("preload", [])):   # retrieval injected before the first turn
                call = {"id": f"preload_{wid}_{j}", "name": name, "args": args}
                content, ev_ids, raw_docs, _ = self._dispatch("orchestrator", ctx, task, call, wid, set())
                messages.append({"role": "assistant", "content": None, "tool_calls": [
                    {"id": call["id"], "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": content, "_ev": ev_ids,
                                 "_docs": [list(d) for d in raw_docs], "_dec": []})
            answer, docs, dec = self._loop("orchestrator", ctx, task, messages, wid, self.orch_tools)
            truth.update(final_docs=sorted(docs), answer=answer, decision_id=dec)
            return truth

    # ----------------------------------------------------------------------
    def _context(self, messages, max_tools):
        """Evict older tool outputs beyond the window (content replaced, pairs kept valid)."""
        tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
        if max_tools is not None:
            for i in tool_idx[:-max_tools] if max_tools else tool_idx:
                messages[i]["content"] = EVICTED
                messages[i]["_ev"], messages[i]["_docs"], messages[i]["_dec"] = [], [], []
        ev, docs, decs = [], set(), []
        for i in tool_idx:
            ev += messages[i].get("_ev", [])
            docs |= set(map(tuple, messages[i].get("_docs", [])))
            decs += messages[i].get("_dec", [])
        return ev, docs, decs

    def _loop(self, role, ctx, task, messages, wid, tool_names):
        window = task.get("context_window")
        for step in range(task.get("max_steps", self.max_steps)):
            ev, docs, decs = self._context(messages, window)
            out, mc_id = self.gw.model_call(ctx, getattr(self.llm, "name", "model"), ev,
                                            lambda: self.llm.step(role, task, messages, tool_names, self.tools),
                                            messages=messages)
            if "content" in out:
                dec = self.gw.record_decision(ctx, out["content"], mc_id, ev, derived_from=decs)
                return out["content"], docs, dec
            messages.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": json.dumps(c["args"])}} for c in out["tool_calls"]]})
            call_ctx = CallContext(ctx.delegation_id, ctx.agent_id, model_call_id=mc_id)
            for c in out["tool_calls"]:
                content, ev_ids, raw_docs, sub_dec = self._dispatch(role, call_ctx, task, c, wid, docs)
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": content,
                                 "_ev": ev_ids, "_docs": [list(d) for d in raw_docs],
                                 "_dec": [sub_dec] if sub_dec else []})
            self._maybe_revoke(task, wid, ctx)
        ev, docs, decs = self._context(messages, window)
        return "(step limit reached)", docs, self.gw.record_decision(ctx, "(step limit)", None, ev, decs)

    def _maybe_revoke(self, task, wid, ctx):
        truth = self.oracle.workflows[wid]
        if task.get("revoke_after") is not None and truth["revoked_at"] is None:
            n_exec = sum(1 for e in self.oracle.executions if e["wid"] == wid)
            if n_exec >= task["revoke_after"]:
                truth["revoked_at"] = now()
                retry(lambda: self.gw.delegations.revoke(truth["root_delegation"]))

    def _dispatch(self, role, ctx, task, call, wid, context_docs):
        name, args = call["name"], call["args"]
        key = (wid, role, name, json.dumps(args, sort_keys=True))
        self.oracle.repeats[key] = self.oracle.repeats.get(key, 0) + 1
        if self.oracle.repeats[key] > 2:                 # harness loop guard (not a FAOGF control)
            self.oracle.loop_guard_trips += 1
            return "ERROR: identical call already made twice with the same result; change your approach.", [], [], None
        if name == "delegate_analysis" and role == "orchestrator":
            return self._delegate(ctx, task, args, wid)
        if name not in self.tools:
            return f"ERROR: unknown tool {name}", [], [], None
        t = self.tools[name]
        fn, action, protected, res_fn = t.fn, t.action, t.protected, t.resources
        raw = []

        import inspect
        params = inspect.signature(fn).parameters
        if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
            args = {k: v for k, v in args.items() if k in params}   # drop arguments the tool does not take

        def traced_fn(**kw):
            out = fn(**kw)
            raw.extend((e["source_id"], e["version"], e["trust_class"]) for e in out.evidence)
            return out

        res = self.gw.tool_call(ctx, name, action, args, traced_fn, protected=protected, resources=res_fn(args),
                               tool_call_id=call["id"])
        truth_wf = self.oracle.workflows[wid]
        rec = {"wid": wid, "tool": name, "allowed": res.allowed, "outcome": res.outcome, "ts": now(),
               "delegation_id": ctx.delegation_id, "record_id": res.record_id, "call_id": call["id"],
               "after_revocation": truth_wf["revoked_at"] is not None}
        self.oracle.executions.append(rec)
        if protected:
            self.oracle.protected.append({**rec, "args": args,
                                          "policy_version": self.gw._policy().version,
                                          "untrusted_in_context": any(d[2] == "untrusted_web" for d in context_docs)})
        docs = [(s, v, t) for s, v, t in raw]
        return res.content, res.evidence_ids, docs, None

    def _delegate(self, ctx, task, args, wid):
        try:
            child = self.gw.delegate(ctx, "analyst", self.analyst_tools)
        except (PermissionError, ValueError, IOError) as e:
            return f"ERROR: delegation refused ({e})", [], [], None
        sub_task = {**task, "question": args.get("instructions", "")}
        sub_task["context_window"] = task.get("analyst_context_window")   # sub-agent window (None = unlimited)
        messages = [{"role": "user", "content": f"{args.get('instructions', '')} Filings: {args.get('source_ids')}"}]
        sub_ctx = CallContext(child.delegation_id, "analyst")
        if self.subagent_trace == "inline":                 # same trace, child span
            parent, links = None, []
        elif self.subagent_trace == "linked":               # new trace, span link to parent
            parent, links = otel_context.Context(), [trace.Link(trace.get_current_span().get_span_context())]
        else:                                               # fragmented: async hand-off, context lost
            parent, links = otel_context.Context(), []
        with self.tracer.start_as_current_span("invoke_agent analyst", context=parent, links=links) as s:
            s.set_attribute("gen_ai.operation.name", "invoke_agent")
            answer, docs, dec = self._loop("analyst", sub_ctx, sub_task, messages, wid, self.analyst_tools)
        return f"Analyst result: {answer}", [], sorted(docs), dec
