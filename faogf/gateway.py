"""The FAOGF capture boundary.

Every tool call and model call made by an agent passes through the gateway,
which (1) binds the call to a gateway-minted delegation, (2) evaluates policy
before protected actions, (3) records evidence and outcomes to the
hash-chained store, and (4) emits OTel spans using gen_ai.* + fin.audit.*.

Capture-as-precondition: a protected action whose intent record cannot be
written is not executed (fail closed). Unprotected reads proceed but the span
is marked fin.audit.record.status=unrecorded, making the gap visible.
"""
from dataclasses import dataclass, field
from opentelemetry.trace import Status, StatusCode
from . import schema as S
from .store import StoreUnavailable


@dataclass
class CallContext:
    delegation_id: str
    agent_id: str
    model_call_id: str = None      # the model call whose output requested this tool call


@dataclass
class ToolOutput:
    content: str
    evidence: list = field(default_factory=list)   # dicts: source_id, version, uri, text, trust_class


@dataclass
class GatewayResult:
    allowed: bool
    content: str
    evidence_ids: list
    outcome: str
    record_id: str = None


class Gateway:
    def __init__(self, store, policies, delegations, tracer, policy_id="fin-agent-policy",
                 approver=None, policy_pin=None, revocation_view=None, capture_content=False,
                 taint_mode=None):
        self.store, self.policies, self.delegations, self.tracer = store, policies, delegations, tracer
        self.policy_id = policy_id
        self.approver = approver or (lambda req: True)
        self.policy_pin = policy_pin            # simulate a lagging gateway on an old policy version
        self.revocation_view = revocation_view  # simulate stale revocation propagation
        self.evidence_index = {}                # evidence_id -> body (for the runner's convenience)
        self.capture_content = capture_content  # emulate full-content logging for baseline comparisons
        # taint-aware policy input: "context" = untrusted evidence in the issuing model call's context
        # (needs FAOGF context binding); "history" = any untrusted retrieval earlier in the delegation
        # lineage (what delegation-only telemetry supports); None = not provided to policy
        self.taint_mode = taint_mode
        self.mc_context = {}
        self.tainted_delegations = set()
        self.current_request = ""

    # ---------------------------------------------------------------- helpers
    def _safe_append(self, kind, body):
        try:
            return self.store.append(kind, body)
        except StoreUnavailable:
            return None

    def _bind(self, span, ctx):
        d = self.delegations.by_id.get(ctx.delegation_id)
        span.set_attribute(S.GENAI_AGENT_ID, ctx.agent_id)
        if d is None:
            span.set_attribute(S.BINDING, "unbound")
            return None
        span.set_attribute(S.BINDING, "gateway")
        span.set_attribute(S.DELEGATION, d.delegation_id)
        span.set_attribute(S.PRINCIPAL, d.principal_id)
        if d.parent_id:
            span.set_attribute(S.DELEGATION_PARENT, d.parent_id)
        return d

    def _policy(self):
        if self.policy_pin is not None:
            return self.policies.get(self.policy_id, self.policy_pin)
        return self.policies.current(self.policy_id)

    def _span_ids(self, span):
        c = span.get_span_context()
        return format(c.trace_id, "032x"), format(c.span_id, "016x")

    # ------------------------------------------------------------- tool calls
    def tool_call(self, ctx, tool, action, args, fn, protected=False, resources=(), tool_call_id=None):
        rid = S.new_id("act")
        with self.tracer.start_as_current_span(f"execute_tool {tool}") as span:
            span.set_attribute(S.GENAI_OPERATION, "execute_tool")
            span.set_attribute(S.GENAI_TOOL_NAME, tool)
            if tool_call_id:
                span.set_attribute(S.GENAI_TOOL_CALL_ID, tool_call_id)
            if ctx.model_call_id:
                span.set_attribute(S.MODEL_CALL, ctx.model_call_id)
            span.set_attribute(S.GENAI_TOOL_ARGS, S.canonical(args))   # opt-in arg capture (baselines use it)
            span.set_attribute(S.ACTION, action)
            span.set_attribute(S.RESOURCES, list(resources))
            span.set_attribute(S.RECORD_ID, rid)
            trace_id, span_id = self._span_ids(span)
            d = self._bind(span, ctx)

            # 1. authority + policy (fail closed on unknown delegation or evaluator error)
            policy = self._policy()
            untrusted = False
            if self.taint_mode == "context":
                untrusted = any(self.evidence_index.get(e, {}).get("trust_class") == "untrusted_web"
                                for e in self.mc_context.get(ctx.model_call_id, []))
            elif self.taint_mode == "history" and d is not None:
                untrusted = any(x in self.tainted_delegations for x in self.delegations.lineage(d.delegation_id))
            span.set_attribute("fin.audit.context.untrusted", untrusted)
            if d is None:
                dec_outcome, rule = "deny", "unbound_delegation"
            elif not self.delegations.active(d.delegation_id, self.revocation_view):
                dec_outcome, rule = "deny", "delegation_inactive"
            elif tool not in d.tools:
                dec_outcome, rule = "deny", "outside_delegated_scope"
            else:
                dec = self.policies.evaluate(policy, {"tool": tool, "action": action, "agent": ctx.agent_id,
                                                      "args": args, "untrusted_context": untrusted})
                dec_outcome, rule = dec.outcome, dec.rule_id
            approval = "not_required"
            if dec_outcome == "permit" and d and protected:
                dec_req = self.policies.evaluate(policy, {"tool": tool, "action": action, "agent": ctx.agent_id,
                                                          "args": args, "untrusted_context": untrusted})
                if dec_req.requires_approval:
                    self.approvals_requested = getattr(self, "approvals_requested", 0) + 1
                    approval = "granted" if self.approver({"tool": tool, "args": args,
                                                           "request_text": self.current_request}) else "denied"
                    if approval == "denied":
                        dec_outcome, rule = "deny", "approval_denied"
            span.set_attribute(S.POLICY_ID, policy.policy_id)
            span.set_attribute(S.POLICY_VERSION, policy.version)
            span.set_attribute(S.POLICY_DECISION, dec_outcome)
            span.set_attribute(S.POLICY_RULE, rule)
            span.set_attribute(S.APPROVAL, approval)

            base = {"record_id": rid, "delegation_id": ctx.delegation_id,
                    "principal_id": d.principal_id if d else None, "agent_id": ctx.agent_id,
                    "tool": tool, "action": action, "resources": list(resources),
                    "args_hash": S.sha256(S.canonical(args)), "protected": protected,
                    "policy": {"id": policy.policy_id, "version": policy.version,
                               "decision": dec_outcome, "rule": rule},
                    "approval": approval, "model_call_id": ctx.model_call_id, "tool_call_id": tool_call_id,
                    "untrusted_context": untrusted,
                    "trace_id": trace_id, "span_id": span_id}

            if dec_outcome != "permit":
                span.set_status(Status(StatusCode.ERROR, f"policy:{dec_outcome}"))
                rec = self._safe_append("action", {**base, "outcome": "denied", "evidence_ids": [], "ts": S.now()})
                span.set_attribute(S.RECORD_STATUS, "recorded" if rec else "unrecorded")
                return GatewayResult(False, f"DENIED by policy ({rule})", [], "denied", rid)

            # 2. capture-as-precondition for protected actions
            if protected:
                try:
                    self.store.append("action_intent", {**base, "ts": S.now()})
                except StoreUnavailable:
                    span.set_status(Status(StatusCode.ERROR, "evidence_store_unavailable"))
                    span.set_attribute(S.RECORD_STATUS, "unrecorded")
                    return GatewayResult(False, "BLOCKED: audit record could not be written", [], "blocked", rid)

            # 3. execute
            try:
                out = fn(**args)
                outcome = "success"
            except Exception as e:  # tool failure is recorded, not hidden
                out, outcome = ToolOutput(f"ERROR: {e}"), "failure"
                span.set_status(Status(StatusCode.ERROR, str(e)))

            # 4. evidence (content is hashed; text is not placed on the span)
            ev_ids, ev_desc = [], []
            for ev in out.evidence:
                eid = S.new_id("ev")
                body = {"evidence_id": eid, "source_id": ev["source_id"], "version": ev["version"],
                        "uri": ev.get("uri"), "trust_class": ev.get("trust_class", "unknown"),
                        "content_sha256": S.sha256(ev["text"]), "retrieved_at": S.now(),
                        "action_record_id": rid, "delegation_id": ctx.delegation_id}
                self._safe_append("evidence", body)
                self.evidence_index[eid] = body
                if body["trust_class"] == "untrusted_web":
                    self.tainted_delegations.add(ctx.delegation_id)
                ev_ids.append(eid)
                ev_desc.append(f"{body['source_id']}@{body['version']}#{body['content_sha256'][:16]}|{body['trust_class']}")
            span.set_attribute(S.EVIDENCE_IDS, ev_ids)
            span.set_attribute(S.EVIDENCE_SOURCES, ev_desc)
            if self.capture_content:
                span.set_attribute(S.GENAI_TOOL_RESULT, out.content)
            rec = self._safe_append("action", {**base, "outcome": outcome, "evidence_ids": ev_ids, "ts": S.now()})
            span.set_attribute(S.RECORD_STATUS, "recorded" if rec else "unrecorded")
            return GatewayResult(True, out.content, ev_ids, outcome, rid)

    # ------------------------------------------------------------ model calls
    def model_call(self, ctx, model, context_evidence_ids, fn, messages=None):
        """Record which evidence was in the model's context (observable), not its reasoning."""
        cid = S.new_id("mc")
        self.mc_context[cid] = list(context_evidence_ids)
        with self.tracer.start_as_current_span(f"chat {model}") as span:
            span.set_attribute(S.GENAI_OPERATION, "chat")
            span.set_attribute(S.GENAI_MODEL, model)
            span.set_attribute(S.ACTION, "generate")
            span.set_attribute(S.RECORD_ID, cid)
            span.set_attribute(S.EVIDENCE_IDS, list(context_evidence_ids))
            self._bind(span, ctx)
            if self.capture_content and messages is not None:
                span.set_attribute(S.GENAI_INPUT_MESSAGES, S.canonical(
                    [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]))
            out = fn()
            trace_id, span_id = self._span_ids(span)
            rec = self._safe_append("model_call", {"record_id": cid, "delegation_id": ctx.delegation_id,
                                                   "agent_id": ctx.agent_id, "model": model,
                                                   "context_evidence_ids": list(context_evidence_ids),
                                                   "output_sha256": S.sha256(S.canonical(out)),
                                                   "trace_id": trace_id, "span_id": span_id, "ts": S.now()})
            span.set_attribute(S.RECORD_STATUS, "recorded" if rec else "unrecorded")
            return out, cid

    def record_decision(self, ctx, content, model_call_id, context_evidence_ids, derived_from=()):
        did = S.new_id("dec")
        with self.tracer.start_as_current_span("decision") as span:
            span.set_attribute(S.ACTION, "decide")
            span.set_attribute(S.RECORD_ID, did)
            span.set_attribute(S.EVIDENCE_IDS, list(context_evidence_ids))
            span.set_attribute(S.DERIVED_FROM, list(derived_from))
            if model_call_id:
                span.set_attribute(S.MODEL_CALL, model_call_id)
            self._bind(span, ctx)
            trace_id, span_id = self._span_ids(span)
        self._safe_append("decision", {"record_id": did, "trace_id": trace_id, "span_id": span_id, "delegation_id": ctx.delegation_id,
                                       "agent_id": ctx.agent_id, "content_sha256": S.sha256(content),
                                       "model_call_id": model_call_id,
                                       "supports": list(context_evidence_ids),
                                       "derived_from": list(derived_from), "ts": S.now()})
        return did

    # ------------------------------------------------------------- delegation
    def delegate(self, ctx, child_agent_id, tools):
        with self.tracer.start_as_current_span("execute_tool delegate") as span:
            span.set_attribute(S.GENAI_OPERATION, "execute_tool")
            span.set_attribute(S.GENAI_TOOL_NAME, "delegate")
            span.set_attribute(S.ACTION, "delegate")
            d = self._bind(span, ctx)
            if d is None or not self.delegations.active(d.delegation_id, self.revocation_view):
                span.set_status(Status(StatusCode.ERROR, "delegation_inactive"))
                raise PermissionError("cannot re-delegate from an inactive or unbound delegation")
            child = self.delegations.issue(None, child_agent_id, tools, parent_id=ctx.delegation_id)
            span.set_attribute("fin.audit.delegation.child_id", child.delegation_id)
            return child
