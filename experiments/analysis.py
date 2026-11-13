"""Audit queries evaluated under telemetry conditions and ablations.

Conditions (projections of the SAME runs):
  B0       OTel GenAI semconv spans (opt-in tool-argument capture ON, results OFF)
  B1       B0 + delegation attributes (principal, delegation id, parent)
  FAOGF-S  all fin.audit.* span attributes, spans only
  FAOGF    spans + hash-chained evidence store (store first, span fallback)
Ablations (FAOGF minus one component): -version, -context, -policy, -lineage, -modelcall, -store

Ground truth is the harness Oracle (raw tool outputs), never FAOGF's own records.
An investigator starts from a workflow's root trace id.
"""
import copy
import json
import re
import time
from collections import defaultdict
from faogf import schema as S

CONDITIONS = ["B0", "B1", "FAOGF-S", "FAOGF"]
# how a baseline reconstructs a document identity from opt-in tool arguments
READ_ARGS = {"read_filing": lambda a: a.get("source_id"),
             "edgar_read_filing": lambda a: _edgar_id(a),
             "edgar_xbrl_fact": lambda a: f"xbrl:{str(a.get('ticker', '')).upper()}:{a.get('concept')}"}
UNTRUSTED_TOOLS = {"web_search", "get_analyst_notes"}
NO_DELEGATION = {"B0", "B2", "B3"}          # conditions without delegation attributes
CONTENT_KEYS = {S.GENAI_TOOL_RESULT, S.GENAI_INPUT_MESSAGES}
EVICTED = "[content evicted from context window]"
_MARKERS = [
    (re.compile(r"\[([A-Z0-9][\w-]+) v(\d+)\]"), lambda m: (m.group(1), int(m.group(2)))),
    (re.compile(r"\[(web:[\w-]+)\]"), lambda m: (m.group(1), 1)),
    (re.compile(r"\[analyst-notes:([^\]]+)\]"), lambda m: ("notes:" + m.group(1), 1)),
    (re.compile(r"\[(https://www\.sec\.gov/Archives/\S+) chars"), lambda m: (_edgar_id({"url": m.group(1)}), "original")),
]
SENSITIVE = re.compile(r"ACCT-\d{8}")


def parse_docs(text):
    """Document identities a content-logging baseline can recover from logged tool output text."""
    out = set()
    for rx, fn in _MARKERS:
        for m in rx.finditer(text or ""):
            out.add(fn(m))
    return out
ABLATIONS = ["-version", "-context", "-policy", "-lineage", "-modelcall", "-store"]


# ------------------------------------------------------------------ projections
def project(spans, cond):
    """B0/B1/FAOGF never carry raw content; B2 adds tool results; B3 adds tool results + full prompts."""
    out = []
    for s in spans:
        a = s["attributes"]
        if cond in ("B0", "B2", "B3"):
            a = {k: v for k, v in a.items() if not k.startswith("fin.audit.")}
            if cond == "B0":
                a = {k: v for k, v in a.items() if k not in CONTENT_KEYS}
            elif cond == "B2":
                a = {k: v for k, v in a.items() if k != S.GENAI_INPUT_MESSAGES}
        elif cond == "B1":
            a = {k: v for k, v in a.items() if (not k.startswith("fin.audit.") or k in S.DELEGATION_KEYS)
                 and k not in CONTENT_KEYS}
        else:
            a = {k: v for k, v in a.items() if k not in CONTENT_KEYS}
        out.append({**s, "attributes": a})
    return out


def ablate(spans, store, comp):
    """Remove one FAOGF component from both the spans and the store copy."""
    spans, store = copy.deepcopy(spans), copy.deepcopy(store)
    recs = [r["body"] for r in store.records]
    if comp == "-version":
        for b in recs:
            if "content_sha256" in b and "source_id" in b:
                b["version"], b["content_sha256"] = None, None
        for s in spans:
            a = s["attributes"]
            if S.EVIDENCE_SOURCES in a:
                a[S.EVIDENCE_SOURCES] = [d.split("@")[0] + "@?#|" + d.split("|")[1] for d in a[S.EVIDENCE_SOURCES]]
    elif comp == "-context":   # decision/model-call support := everything read under the delegation so far
        ev_by_del = defaultdict(list)
        for b in recs:
            if "evidence_id" in b and "retrieved_at" in b:
                ev_by_del[b["delegation_id"]].append((b["retrieved_at"], b["evidence_id"]))
        for b in recs:
            if "supports" in b:
                b["supports"] = [e for t, e in ev_by_del[b["delegation_id"]] if t <= b["ts"]]
            if "context_evidence_ids" in b:
                b["context_evidence_ids"] = [e for t, e in ev_by_del[b["delegation_id"]] if t <= b["ts"]]
        span_ev = defaultdict(list)
        for s in sorted(spans, key=lambda x: x["start"]):
            a = s["attributes"]
            if a.get(S.EVIDENCE_SOURCES):
                span_ev[a.get(S.DELEGATION)].append((s["end"], a.get(S.EVIDENCE_IDS, [])))
        for s in spans:
            a = s["attributes"]
            if a.get(S.ACTION) in ("decide", "generate"):
                a[S.EVIDENCE_IDS] = [e for t, ids in span_ev[a.get(S.DELEGATION)] if t <= s["end"] for e in ids]
    elif comp == "-policy":
        for b in recs:
            b.pop("policy", None)
        for s in spans:
            for k in (S.POLICY_ID, S.POLICY_VERSION, S.POLICY_DECISION, S.POLICY_RULE):
                s["attributes"].pop(k, None)
        store.records = [r for r in store.records if r["kind"] != "policy_version"]
    elif comp == "-lineage":
        for b in recs:
            if "parent_id" in b:
                b["parent_id"] = None
        for s in spans:
            s["attributes"].pop(S.DELEGATION_PARENT, None)
    elif comp == "-modelcall":
        for b in recs:
            b.pop("model_call_id", None)
        for s in spans:
            s["attributes"].pop(S.MODEL_CALL, None)
    return spans, store


# ------------------------------------------------------------------ helpers
def prf(pred, truth):
    pred, truth = set(pred), set(truth)
    if not pred and not truth:
        return 1.0, 1.0
    tp = len(pred & truth)
    # precision of an empty answer is undefined (it is a recall failure, scored in recall)
    return (tp / len(pred) if pred else None), (tp / len(truth) if truth else 1.0)


def r4(x):
    return None if x is None else round(x, 4)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _edgar_id(a):
    """What an investigator can reconstruct from logged read arguments (URL or accession)."""
    from agent.edgar import filing_id
    if a.get("url"):
        return filing_id(url=a["url"])
    return f"edgar:{a.get('accession')}"


def _args(s):
    try:
        return json.loads(s["attributes"].get(S.GENAI_TOOL_ARGS, "{}"))
    except json.JSONDecodeError:
        return {}


class Views:
    def __init__(self, spans, store=None):
        self.spans = spans
        self.by_trace, self.by_del, self.by_record, self.by_tool = (defaultdict(list) for _ in range(4))
        self.by_record = {}
        self.parent_of, self.link_from = {}, defaultdict(set)
        for s in spans:
            a = s["attributes"]
            self.by_trace[s["trace_id"]].append(s)
            if a.get(S.RECORD_ID):
                self.by_record[a[S.RECORD_ID]] = s
            if a.get(S.DELEGATION):
                self.by_del[a[S.DELEGATION]].append(s)
                self.parent_of.setdefault(a[S.DELEGATION], a.get(S.DELEGATION_PARENT))
            if a.get(S.GENAI_TOOL_NAME):
                self.by_tool[a[S.GENAI_TOOL_NAME]].append(s)
            for l in s["links"]:
                self.link_from[l].add(s["trace_id"])
        self.children = defaultdict(set)
        for d, p in self.parent_of.items():
            if p:
                self.children[p].add(d)
        self.store = store
        if store:
            self.rec = {}
            for r in store.records:
                key = r["body"].get("record_id") or r["body"].get("evidence_id")
                if key:
                    self.rec.setdefault(key, r)
            self.ev = {r["body"]["evidence_id"]: r["body"] for r in store.of("evidence")}
            self.issued = {r["body"]["delegation_id"]: r["body"] for r in store.of("delegation_issued")}
            self.revoked = {r["body"]["delegation_id"]: r["body"]["at"] for r in store.of("delegation_revoked")}
            self.actions = {r["body"].get("tool_call_id"): r["body"] for r in store.of("action")}
            self.model_calls = {r["body"]["record_id"]: r["body"] for r in store.of("model_call")}
            self.mc_by_trace = defaultdict(list)
            for b in self.model_calls.values():
                self.mc_by_trace[b["trace_id"]].append(b)
        self.idx = self._desc_index()

    def _desc_index(self):
        idx = {}
        for s in self.spans:
            a = s["attributes"]
            for eid, desc in zip(a.get(S.EVIDENCE_IDS, []) if a.get(S.EVIDENCE_SOURCES) else [],
                                 a.get(S.EVIDENCE_SOURCES, [])):
                sid_ver, trust = desc.split("|")
                sid, ver = sid_ver.split("#")[0].rsplit("@", 1)
                idx[eid] = (sid, None if ver == "?" else (int(ver) if ver.isdigit() and len(ver) < 6 else ver), trust)
        return idx

    def descendants(self, root):
        out, stack = {root}, [root]
        while stack:
            for c in self.children[stack.pop()]:
                if c not in out:
                    out.add(c)
                    stack.append(c)
        return out

    def ev_info(self, eid):
        if self.store and eid in self.ev:
            b = self.ev[eid]
            return b["source_id"], b["version"], b["trust_class"]
        return self.idx.get(eid)


def scope_spans(v, cond, truth):
    root_trace = v.by_trace.get(truth["root_trace_id"], [])
    if cond in NO_DELEGATION:   # follow span links into linked traces
        traces, frontier = {truth["root_trace_id"]}, [truth["root_trace_id"]]
        while frontier:
            t = frontier.pop()
            for s in v.by_trace[t]:
                for t2 in v.link_from.get(s["span_id"], ()):
                    if t2 not in traces:
                        traces.add(t2)
                        frontier.append(t2)
        return [s for t in traces for s in v.by_trace[t]]
    root_del = next((s["attributes"][S.DELEGATION] for s in root_trace
                     if s["attributes"].get(S.GENAI_AGENT_ID) == "orchestrator" and s["attributes"].get(S.DELEGATION)),
                    None)
    if not root_del:
        return root_trace
    return [s for d in v.descendants(root_del) for s in v.by_del[d]]


# ------------------------------------------------------------------ queries
def decision_sources(v, dec_id, depth=0):
    """FAOGF: store first, span fallback. FAOGF-S: spans only."""
    if depth > 6:
        return set()
    if v.store and dec_id in v.rec:
        b = v.rec[dec_id]["body"]
        supports, derived = b["supports"], b["derived_from"]
    elif dec_id in v.by_record:
        a = v.by_record[dec_id]["attributes"]
        supports, derived = a.get(S.EVIDENCE_IDS, []), a.get(S.DERIVED_FROM, [])
    else:
        return set()
    out = {v.ev_info(e)[:2] for e in supports if v.ev_info(e)}
    for sub in derived:
        out |= decision_sources(v, sub, depth + 1)
    return out


def _final_chat(spans, agent="orchestrator"):
    chats = [s for s in spans if s["attributes"].get(S.GENAI_OPERATION) == "chat"
             and s["attributes"].get(S.GENAI_AGENT_ID, agent) == agent]
    return max(chats, key=lambda s: s["start"]) if chats else None


def _context_docs(chat_span):
    """Docs a full-prompt log shows in a model call's input (evicted tool messages excluded)."""
    if not chat_span or S.GENAI_INPUT_MESSAGES not in chat_span["attributes"]:
        return set(), False
    msgs = json.loads(chat_span["attributes"][S.GENAI_INPUT_MESSAGES])
    docs, analyst = set(), False
    for m in msgs:
        if m.get("role") == "tool" and m.get("content") != EVICTED:
            docs |= parse_docs(m.get("content"))
            analyst = analyst or str(m.get("content", "")).startswith("Analyst result")
    return docs, analyst


def q3_sources(v, cond, truth):
    if cond == "B2":   # tool results logged: every retrieved document in scope, version-aware
        sc = scope_spans(v, cond, truth)
        return {d for s in sc if s["status"] != "ERROR" for d in parse_docs(s["attributes"].get(S.GENAI_TOOL_RESULT))}
    if cond == "B3":   # full prompts logged: parse the final model call's input
        root = v.by_trace.get(truth["root_trace_id"], [])
        docs, analyst = _context_docs(_final_chat(root))
        if analyst:    # follow span links to sub-agent traces, if any exist
            for s in scope_spans(v, "B0", truth):
                if s["trace_id"] != truth["root_trace_id"]:
                    sub = _final_chat(v.by_trace[s["trace_id"]], "analyst")
                    docs |= _context_docs(sub)[0]
        return docs
    if cond in ("B0", "B1"):
        sc = scope_spans(v, cond, truth)
        return {(READ_ARGS[s["attributes"][S.GENAI_TOOL_NAME]](_args(s)), None) for s in sc
                if s["attributes"].get(S.GENAI_TOOL_NAME) in READ_ARGS and s["status"] != "ERROR"}
    return decision_sources(v, truth["decision_id"])


def evaluate(run, conditions=None, ablations=(), per_item=False):
    conditions = conditions or CONDITIONS
    oracle, store = run["oracle"], run["store"]
    jobs = [(c, c, run["spans"], store) for c in conditions]
    for comp in ablations:
        if comp == "-store":
            jobs.append(("FAOGF-store", "FAOGF-S", run["spans"], store))
        else:
            sp, st = ablate(run["spans"], store, comp)
            jobs.append((f"FAOGF{comp}", "FAOGF", sp, st))
    results = {}
    for label, cond, spans_in, store_in in jobs:
        spans = project(spans_in, "FAOGF" if cond.startswith("FAOGF") else cond)
        v = Views(spans, store_in if cond == "FAOGF" else None)
        res, timing = {}, {}
        has_policy = any(S.POLICY_VERSION in s["attributes"] for s in spans) or (
            v.store and any("policy" in b for b in v.actions.values()))

        # Q1 authority ------------------------------------------------------
        t0 = time.perf_counter()
        if cond in NO_DELEGATION:
            res["Q1_authority_accuracy"] = None
        else:
            ok = []
            for t in oracle.workflows.values():
                ans = None
                if v.store:
                    mc = [b for b in v.mc_by_trace.get(t["root_trace_id"], []) if b["agent_id"] == "orchestrator"]
                    if mc:
                        d = v.issued.get(mc[0]["delegation_id"], {})
                        ans = (d.get("principal_id"), d.get("delegation_id"))
                if ans is None:
                    for s in v.by_trace.get(t["root_trace_id"], []):
                        a = s["attributes"]
                        if a.get(S.GENAI_AGENT_ID) == "orchestrator" and a.get(S.DELEGATION):
                            ans = (a.get(S.PRINCIPAL), a[S.DELEGATION])
                            break
                ok.append(1.0 if ans == (t["principal"], t["root_delegation"]) else 0.0)
            res["Q1_authority_accuracy"] = mean(ok)
        timing["Q1"] = time.perf_counter() - t0

        # Q3 supporting evidence / Q4 blast radius ----------------------------
        t0 = time.perf_counter()
        ps, rs, pv, rv, fps, frs = [], [], [], [], [], []
        preds = {}
        for t in oracle.workflows.values():
            pred = q3_sources(v, cond, t)
            preds[t["wid"]] = pred
            truth_v = {(s, ver) for s, ver, _ in t["final_docs"]}
            p, r = prf({s for s, _ in pred}, {s for s, _ in truth_v})
            ps.append(p); rs.append(r)
            fil_t = {s for s, _, tr in t["final_docs"] if tr == "authoritative_filing"}
            p, r = prf({s for s, _ in pred if s and not s.startswith(("web:", "notes:"))}, fil_t)
            fps.append(p); frs.append(r)
            if pred and all(ver is not None for _, ver in pred) or (not pred and not truth_v):
                p, r = prf(pred, truth_v)
                pv.append(p); rv.append(r)
        res["Q3_source_precision"], res["Q3_source_recall"] = mean(ps), mean(rs)
        res["Q3_filings_precision"], res["Q3_filings_recall"] = mean(fps), mean(frs)
        if per_item:
            res["_items"] = {"Q3_filings_precision": fps, "Q3_filings_recall": frs}
        version_aware = any(ver is not None for pred in preds.values() for _, ver in pred)
        res["Q3_version_precision"] = mean(pv) if version_aware else None
        res["Q3_version_recall"] = mean(rv) if version_aware else None
        timing["Q3"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        tp = fp = fn = 0
        for sid, oldv in run["corpus"].amended:
            truth = {t["wid"] for t in oracle.workflows.values()
                     if (sid, oldv) in {(s, ver) for s, ver, _ in t["final_docs"]}}
            pred = {w for w, pr in preds.items() if (sid, oldv) in pr or (sid, None) in pr}
            tp, fp, fn = tp + len(pred & truth), fp + len(pred - truth), fn + len(truth - pred)
        res["Q4_blast_precision"] = round(tp / (tp + fp), 4) if tp + fp else 1.0
        res["Q4_blast_recall"] = round(tp / (tp + fn), 4) if tp + fn else 1.0
        res["Q4_amended_pairs"] = len(run["corpus"].amended)
        timing["Q4"] = time.perf_counter() - t0

        # Q2 protected attempts ----------------------------------------------
        t0 = time.perf_counter()
        by_call = {s["attributes"].get(S.GENAI_TOOL_CALL_ID): s for s in v.by_tool.get("distribute_report", [])}
        found = outcome_ok = version_ok = 0
        for p in oracle.protected:
            b = v.actions.get(p["call_id"]) if v.store else None
            if b:
                found += 1
                outcome_ok += (b["outcome"] not in ("denied", "blocked")) == p["allowed"]
                version_ok += b.get("policy", {}).get("version") == p["policy_version"]
                continue
            s = by_call.get(p["call_id"])
            if s:
                found += 1
                denied = s["status"] == "ERROR" and s.get("status_description", "").startswith(("policy:", "evidence_store"))
                outcome_ok += (not denied) == p["allowed"]
                version_ok += s["attributes"].get(S.POLICY_VERSION) == p["policy_version"]
        n = len(oracle.protected) or 1
        res["Q2_attempt_recall"] = round(found / n, 4)
        res["Q2_outcome_accuracy"] = round(outcome_ok / n, 4)
        res["Q2_policy_version_accuracy"] = round(version_ok / n, 4) if has_policy else None
        timing["Q2"] = time.perf_counter() - t0

        # Q5 actions executed after revocation --------------------------------
        t0 = time.perf_counter()
        truth5 = {e["call_id"] for e in oracle.executions if e["allowed"] and e["after_revocation"]}
        res["Q5_truth_count"] = len(truth5)
        if v.store and v.revoked:
            pred5 = set()
            cands = [(b["tool_call_id"], b["delegation_id"], b["ts"]) for b in v.actions.values()
                     if b["outcome"] == "success"]
            for s_ in spans:   # span fallback: executed tool calls the store did not record
                a = s_["attributes"]
                cid = a.get(S.GENAI_TOOL_CALL_ID)
                if cid and cid not in v.actions and a.get(S.POLICY_DECISION) == "permit" and s_["status"] != "ERROR":
                    cands.append((cid, a.get(S.DELEGATION), s_["end"]))
            for cid, did, ts in cands:
                chain, cur, hops = [], did, 0
                while cur and hops < 20:
                    chain.append(cur)
                    cur, hops = v.issued.get(cur, {}).get("parent_id"), hops + 1
                if any(d in v.revoked and ts > v.revoked[d] for d in chain):
                    pred5.add(cid)
            p, r = prf(pred5, truth5)
            res["Q5_post_revocation_precision"], res["Q5_post_revocation_recall"] = r4(p), r4(r)
        else:
            res["Q5_post_revocation_precision"] = res["Q5_post_revocation_recall"] = None
        timing["Q5"] = time.perf_counter() - t0

        # Q6 actions under superseded policy ------------------------------------
        t0 = time.perf_counter()
        v2_at = run["meta"]["v2_published_at"]
        truth6 = {p["call_id"] for p in oracle.protected if v2_at and p["ts"] > v2_at and p["policy_version"] < 2}
        res["Q6_truth_count"] = len(truth6)
        if cond.startswith("FAOGF") and has_policy:
            if v.store and store_in.of("policy_version"):
                pub = {r["body"]["version"]: r["body"]["published_at"] for r in store_in.of("policy_version")}
            else:
                pub = {1: 0, 2: v2_at}          # release log known out of band
            cand = []
            for p in oracle.protected:      # every attempt the telemetry can surface
                b = v.actions.get(p["call_id"]) if v.store else None
                if b and "policy" in b:
                    cand.append((p["call_id"], b["policy"]["version"], b["ts"]))
                elif p["call_id"] in by_call:
                    s = by_call[p["call_id"]]
                    cand.append((p["call_id"], s["attributes"].get(S.POLICY_VERSION), s["start"]))
            pred6 = {c for c, ver, ts in cand if ver is not None and ver < max(k for k, t1 in pub.items() if t1 <= ts)}
            p, r = prf(pred6, truth6)
            res["Q6_stale_policy_precision"], res["Q6_stale_policy_recall"] = r4(p), r4(r)
        else:
            res["Q6_stale_policy_precision"] = res["Q6_stale_policy_recall"] = None
        timing["Q6"] = time.perf_counter() - t0

        # Q7 protected attempt issued with untrusted content in context ---------
        t0 = time.perf_counter()
        truth7 = {p["call_id"] for p in oracle.protected if p["untrusted_in_context"]}
        res["Q7_truth_count"] = len(truth7)
        pred7 = set()
        wf_of_call = {p["call_id"]: p["wid"] for p in oracle.protected}
        for p in oracle.protected:
            cid = p["call_id"]
            mc_ev = None
            b = v.actions.get(cid) if v.store else None
            if b and b.get("model_call_id") and b["model_call_id"] in v.model_calls:
                mc_ev = v.model_calls[b["model_call_id"]]["context_evidence_ids"]
            elif cond.startswith("FAOGF") and cid in by_call and by_call[cid]["attributes"].get(S.MODEL_CALL):
                mc = v.by_record.get(by_call[cid]["attributes"][S.MODEL_CALL])
                mc_ev = mc["attributes"].get(S.EVIDENCE_IDS, []) if mc else []
            if mc_ev is not None:
                if any((v.ev_info(e) or ("", 0, ""))[2] == "untrusted_web" for e in mc_ev):
                    pred7.add(cid)
                continue
            # fallback heuristic: any earlier untrusted retrieval in the investigator's scope
            s = by_call.get(cid)
            if not s:
                continue
            truth_wf = oracle.workflows[wf_of_call[cid]]
            if cond == "B3":   # the model call that issued this tool call is logged with its full input
                prior = [x for x in v.by_trace[s["trace_id"]] if x["attributes"].get(S.GENAI_OPERATION) == "chat"
                         and x["end"] <= s["start"]]
                if prior:
                    docs, _ = _context_docs(max(prior, key=lambda x: x["end"]))
                    if any(str(d[0]).startswith(("web:", "notes:")) for d in docs):
                        pred7.add(cid)
                continue
            sc = scope_spans(v, "B0" if cond in NO_DELEGATION else "B1", truth_wf)
            if any(x["attributes"].get(S.GENAI_TOOL_NAME) in UNTRUSTED_TOOLS and x["end"] < s["start"]
                   and not str(x["attributes"].get(S.GENAI_TOOL_RESULT, "")).startswith("No ") for x in sc):
                pred7.add(cid)
        if per_item:
            res["_items"]["Q7_pred"], res["_items"]["Q7_truth"] = sorted(pred7), sorted(truth7)
        p, r = prf(pred7, truth7)
        res["Q7_untrusted_precision"], res["Q7_untrusted_recall"] = r4(p), r4(r)
        timing["Q7"] = time.perf_counter() - t0

        # Q8 lost telemetry detection ------------------------------------------
        present = {s["span_id"] for s in spans}
        detected = {s["parent_id"] for s in spans if s["parent_id"] and s["parent_id"] not in present}
        if v.store:
            detected |= {r["body"]["span_id"] for r in store_in.records
                         if r["body"].get("span_id") and r["body"]["span_id"] not in present}
        res["Q8_lost_span_detection"] = round(min(len(detected), run["dropped"]) / run["dropped"], 4) \
            if run["dropped"] else None
        # Q9: audit attributes stripped in transit (span arrived, but its FAOGF record pointer did not)
        if v.store:
            by_id = {s_["span_id"]: s_ for s_ in spans}
            recorded = [r["body"]["span_id"] for r in store_in.records
                        if r["kind"] in ("action", "model_call", "decision") and r["body"].get("span_id") in by_id]
            stripped = [sid for sid in recorded if S.RECORD_ID not in by_id[sid]["attributes"]]
            res["Q9_spans_arrived_with_records"] = len(recorded)
            res["Q9_stripped_detected_share"] = round(len(stripped) / len(recorded), 4) if recorded else None

        blob = json.dumps([s_["attributes"] for s_ in spans])
        store_blob = json.dumps([r["body"] for r in store_in.records]) if v.store else ""
        nwf = max(len(oracle.workflows), 1)
        res["telemetry_kb_per_workflow"] = round((len(blob) + len(store_blob)) / nwf / 1024, 2)
        res["sensitive_ids_retained_per_workflow"] = round(len(SENSITIVE.findall(blob + store_blob)) / nwf, 2)
        res["raw_content_kb_per_workflow"] = round(sum(len(str(s_["attributes"].get(k, ""))) for s_ in spans
                                                       for k in CONTENT_KEYS) / nwf / 1024, 2)
        res["bytes_per_span"] = round(sum(len(json.dumps(s["attributes"])) for s in spans) / max(len(spans), 1), 1)
        res["spans_per_workflow"] = round(len(spans) / max(len(oracle.workflows), 1), 2)
        if v.store:
            res["store_bytes_per_workflow"] = round(store_in.size_bytes() / max(len(oracle.workflows), 1), 1)
        res["query_ms"] = {k: round(x * 1000, 2) for k, x in timing.items()}
        results[label] = res
    return results
