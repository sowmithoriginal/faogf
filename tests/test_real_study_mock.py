"""Run the real-filing study end to end against fake SEC + fake OpenAI (no network)."""
import json, re, sys, types
import agent.edgar as E
import agent.llm as L

TICKERS = {"0": {"cik_str": 1018724, "ticker": "AMZN", "title": "AMAZON COM INC"}}
SUB = {"name": "AMAZON COM INC", "tickers": ["AMZN"], "filings": {"files": [], "recent": {"accessionNumber": ["0001018724-25-000004"], "form": ["10-K"],
       "filingDate": ["2025-02-07"], "primaryDocument": ["amzn-20241231.htm"], "reportDate": ["2024-12-31"]}}}
DOC = "<html><body><p>Total net sales were $638.0 billion in 2024.</p></body></html>"
XBRL = {"units": {"USD": [{"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-12-31", "val": 637959000000,
                           "accn": "0001018724-25-000004"}]}}

def fake_get(url, as_json=False):
    if "company_tickers" in url: return TICKERS
    if "submissions" in url: return SUB
    if "companyfacts" in url: return {"facts": {"us-gaap": {"Revenues": XBRL}}}
    if "browse-edgar" in url: return "<feed><cik>1018724</cik><conformed-name>AMAZON COM INC</conformed-name></feed>"
    return DOC
E._get = fake_get

class FakeCompletions:
    def create(self, model, messages, tools, temperature):
        names = {t["function"]["name"] for t in tools}
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        last = tool_msgs[-1]["content"] if tool_msgs else ""
        url = "https://www.sec.gov/Archives/edgar/data/1018724/000101872425000004/amzn-20241231.htm"
        def call(n, a): return types.SimpleNamespace(id=f"c{len(messages)}{n}", function=types.SimpleNamespace(name=n, arguments=json.dumps(a)))
        if "edgar_list_filings" not in names:   # analyst
            calls = None if tool_msgs else [call("edgar_xbrl_fact", {"ticker": "AMZN", "concept": "Revenues"})]
        else:
            step = len(tool_msgs) - 1          # first tool message is the preloaded analyst note
            plan = [[call("edgar_list_filings", {"ticker": "AMZN", "form_types": ["10-K"]})],
                    [call("edgar_read_filing", {"accession": "0001018724-25-000004", "ticker": "AMZN"})],
                    [call("delegate_analysis", {"instructions": "revenue", "source_ids": []})]]
            m = re.search(r"[\w.+-]+@[\w-]+\.biz", " ".join(x["content"] for x in tool_msgs))
            sent = any("distribute_report" in json.dumps(x.get("tool_calls", "")) for x in messages if x["role"] == "assistant")
            if m and not sent:
                calls = [call("distribute_report", {"recipient": m.group(0), "summary": "x"})]
            elif step < len(plan) + (1 if sent else 0):
                calls = plan[step - (1 if sent else 0)] if step - (1 if sent else 0) < len(plan) else None
            else:
                calls = None
        content = None if calls else f"Revenue was $638.0B. Sources: {url}"
        msg = types.SimpleNamespace(tool_calls=calls, content=content, model_dump=lambda: {})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=types.SimpleNamespace(model_dump=lambda: {"prompt_tokens": 100, "completion_tokens": 10}))

def fake_init(self, model=None, temperature=0, log_path=None):
    self.client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions()))
    self.name, self.temperature, self.log_path = model or "fake", 0, log_path
    self.cache_dir, self.errors = None, {"context_limit": 0, "api_error": 0}
L.OpenAILLM.__init__ = fake_init

import experiments.real_study as R
sys.argv = ["x", "--model", "fake-model", "-n", "8"]
R.main()
