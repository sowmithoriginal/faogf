Real-filing study results (gpt-4o-mini, 50 public Finance Agent Benchmark questions, live SEC EDGAR).

* real_gpt-4o-mini.json / _calls.jsonl : run 1, prompt tells the model to treat analyst notes as unverified
  (store/spans were not saved by that version of the harness)
* real_gpt-4o-mini_nowarn.* : run 2, no warning; includes the evidence store (_store.jsonl) and spans
  (_spans.json) for independent re-verification
