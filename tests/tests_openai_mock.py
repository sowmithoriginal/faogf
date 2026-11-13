"""Exercise the OpenAI code path with a fake client (no network)."""
import json, types
from agent.llm import OpenAILLM
from experiments.build import run_suite
from experiments.analysis import evaluate

def tc(name, args, i):
    return types.SimpleNamespace(id=f"c{i}", function=types.SimpleNamespace(name=name, arguments=json.dumps(args)))

class FakeCompletions:
    def __init__(self): self.n = 0
    def create(self, model, messages, tools, temperature):
        names = {t["function"]["name"] for t in tools}
        assert messages[0]["role"] == "system" and all(not k.startswith("_") for m in messages for k in m)
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        self.n += 1
        if "search_filings" in names and not tool_msgs:
            calls = [tc("search_filings", {"company": "Contoso"}, self.n)]
        elif "search_filings" in names and len(tool_msgs) == 1:
            calls = [tc("read_filing", {"source_id": "CTB-10K-FY2025"}, self.n), tc("web_search", {"query": "Contoso buyback"}, self.n + 100)]
        elif "search_filings" in names and len(tool_msgs) == 3:
            calls = [tc("delegate_analysis", {"instructions": "net margin", "source_ids": ["CTB-10K-FY2025"]}, self.n)]
        elif "search_filings" not in names and not tool_msgs:
            calls = [tc("read_filing", {"source_id": "CTB-10K-FY2025"}, self.n)]
        else:
            calls = None
        msg = types.SimpleNamespace(tool_calls=calls, content=None if calls else "Final answer based on CTB-10K-FY2025.",
                                    model_dump=lambda: {"tool_calls": bool(calls)})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=None)

llm = OpenAILLM.__new__(OpenAILLM)
llm.client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions()))
llm.name, llm.temperature, llm.log_path = "fake-model", 0, "/tmp/fake_calls.jsonl"
llm.cache_dir, llm.errors = "/tmp/faogf_llm_cache", {"context_limit": 0, "api_error": 0}
r = run_suite(llm, n=6, seed=1)
res = evaluate(r)
print({c: (res[c]["Q3_source_recall"], res[c]["Q1_authority_accuracy"]) for c in res})
print("store verifies:", r["store"].verify() == [], "| decisions:", len(r["store"].of("decision")))
