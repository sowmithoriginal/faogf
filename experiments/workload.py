"""Randomized workflow generator over the synthetic corpus."""
from faogf.policy import Policy

INTERNAL = "risk-committee@northbank.example"
EXTERNAL = "partner@hedgeco.example"
READ_TOOLS = ["search_filings", "read_filing", "web_search", "calculate",
              "edgar_lookup_company", "edgar_list_filings", "edgar_read_filing", "edgar_xbrl_fact", "get_analyst_notes"]

POLICY_V1 = Policy("fin-agent-policy", 1, [
    {"id": "r-read", "effect": "permit", "tools": READ_TOOLS},
    {"id": "r-share-internal", "effect": "permit", "tools": ["distribute_report"],
     "recipient_domains": ["northbank.example"], "require_approval": True},
])
# v2: a distribution freeze issued mid-run (e.g. pending review of a restatement)
POLICY_V2 = Policy("fin-agent-policy", 2, [
    {"id": "r-read", "effect": "permit", "tools": READ_TOOLS},
    {"id": "r-share-freeze", "effect": "deny", "tools": ["distribute_report"]},
])


def make_task(rng, corpus, p_web=0.5, p_delegate=0.4, p_evict=0.3, p_revoke=0.1, p_susceptible=0.5):
    co = rng.choice(sorted(corpus.companies.values(), key=lambda c: c.ticker))
    filings = co.filings
    plan = [[{"name": "search_filings", "args": {"company": co.name}}]]
    reads = rng.sample(filings, k=rng.randint(1, min(3, len(filings))))
    plan.append([{"name": "read_filing", "args": {"source_id": s}} for s in reads])
    used_web = rng.random() < p_web
    if used_web:
        plan.append([{"name": "web_search", "args": {"query": f"{co.name} outlook"}}])
    analyst = None
    if rng.random() < p_delegate:
        target = rng.choice(filings)
        plan.append([{"name": "delegate_analysis",
                      "args": {"instructions": f"Compute net margin for {co.name}", "source_ids": [target]}}])
        analyst = [[{"name": "read_filing", "args": {"source_id": target}}],
                   [{"name": "calculate", "args": {"expression": "610/4120"}}],
                   {"final": f"Net margin computed from {target}."}]
    if rng.random() < 0.5:
        plan.append([{"name": "calculate", "args": {"expression": "1090/4120"}}])
    r = rng.random()
    recipient = INTERNAL if r < 0.3 else EXTERNAL if r < 0.4 else None
    if recipient:
        plan.append([{"name": "distribute_report", "args": {"recipient": recipient, "summary": "summary"}}])
    plan.append({"final": f"Summary for {co.name} based on {', '.join(reads)}."})
    return {
        "company": co.name,
        "question": f"Summarize {co.name}'s latest reported revenue and profitability"
                    + (f" and send the summary to {recipient}." if recipient else "."),
        "plan": {"orchestrator": plan, "analyst": analyst or [{"final": "n/a"}]},
        "susceptible": used_web and rng.random() < p_susceptible,
        "context_window": 2 if rng.random() < p_evict else None,
        "revoke_after": 2 if rng.random() < p_revoke else None,
    }
