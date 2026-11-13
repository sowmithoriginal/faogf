"""Render results/results_<model>.json into paper tables (Markdown) and figures.

    python3 -m experiments.report results/results_scripted.json
"""
import json
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CONDS = ["B0", "B1", "FAOGF-S", "FAOGF"]
QROWS = [
    ("Q1 Authority chain (acc.)", "Q1_authority_accuracy"),
    ("Q2 Protected attempts found (recall)", "Q2_attempt_recall"),
    ("Q2 Policy version (acc.)", "Q2_policy_version_accuracy"),
    ("Q3 Supporting filings (P)", "Q3_filings_precision"),
    ("Q3 Supporting filings (R)", "Q3_filings_recall"),
    ("Q3 All sources incl. untrusted (R)", "Q3_source_recall"),
    ("Q3 Version-exact sources (P)", "Q3_version_precision"),
    ("Q4 Restatement blast radius (P)", "Q4_blast_precision"),
    ("Q4 Restatement blast radius (R)", "Q4_blast_recall"),
    ("Q5 Post-revocation actions (R)", "Q5_post_revocation_recall"),
    ("Q6 Stale-policy actions (R)", "Q6_stale_policy_recall"),
    ("Q7 Untrusted-context exposure (P)", "Q7_untrusted_precision"),
    ("Q7 Untrusted-context exposure (R)", "Q7_untrusted_recall"),
]


def c(x, digits=2):
    if x is None:
        return "n/a"
    if isinstance(x, dict):
        m, ci = x["mean"], x["ci95"]
        return f"{m:.{digits}f}" if ci == 0 else f"{m:.{digits}f} ± {ci:.{digits}f}"
    return f"{x:.{digits}f}"


def m(x):
    return None if x is None else (x["mean"] if isinstance(x, dict) else x)


def save(fig, out, name):
    fig.tight_layout()
    fig.savefig(os.path.join(out, f"{name}.png"), dpi=200)
    fig.savefig(os.path.join(out, f"{name}.pdf"))
    plt.close(fig)


def main(path):
    R = json.load(open(path))
    out = os.path.dirname(path) or "."
    md = [f"# FAOGF controlled study ({R['model']}; {R['n_per_run']} workflows per run; seeds {R['seeds']})",
          "Values are mean ± 95% CI across seeds (CI omitted when zero). n/a = the telemetry cannot express the query.\n"]

    if "e1" in R:
        b = R["e1"]["fragmented"]
        md += ["## Table 1. Audit-query answerability (asynchronous sub-agent hand-off, no faults)\n",
               "| Query | " + " | ".join(CONDS) + " |", "|---|" + "---|" * len(CONDS)]
        md += [f"| {l} | " + " | ".join(c(b[k_].get(k)) for k_ in CONDS) + " |" for l, k in QROWS]
        md += [f"| Attribute bytes / span | " + " | ".join(c(b[k_]["bytes_per_span"], 0) for k_ in CONDS) + " |",
               f"| Evidence-store bytes / workflow | n/a | n/a | n/a | {c(b['FAOGF']['store_bytes_per_workflow'], 0)} |"]
        md += ["\n### Hand-off mode sensitivity (Q3 filings recall / Q4 blast precision)\n",
               "| Mode | " + " | ".join(CONDS) + " |", "|---|" + "---|" * len(CONDS)]
        for mode in ("inline", "linked", "fragmented"):
            bb = R["e1"][mode]
            md.append(f"| {mode} | " + " | ".join(f"{c(bb[k]['Q3_filings_recall'])} / {c(bb[k]['Q4_blast_precision'])}"
                                                  for k in CONDS) + " |")
        fig, ax = plt.subplots(figsize=(7.5, 3.2))
        keys = [("Q3 filings P", "Q3_filings_precision"), ("Q3 filings R", "Q3_filings_recall"),
                ("Q4 blast P", "Q4_blast_precision"), ("Q7 exposure P", "Q7_untrusted_precision")]
        w = 0.2
        for j, cond in enumerate(CONDS):
            ax.bar([i + j * w for i in range(len(keys))], [m(b[cond][k]) or 0 for _, k in keys], w, label=cond,
                   yerr=[(b[cond][k] or {"ci95": 0})["ci95"] for _, k in keys], capsize=2)
        ax.set_xticks([i + 1.5 * w for i in range(len(keys))], [l for l, _ in keys])
        ax.set_ylim(0, 1.08); ax.set_ylabel("score"); ax.legend(ncol=4, fontsize=8, loc="lower right")
        save(fig, out, "fig1_query_scores")

    if "e6" in R:
        b = R["e6"]["no_faults"]
        cols = ["FAOGF", "FAOGF-version", "FAOGF-context", "FAOGF-policy", "FAOGF-lineage", "FAOGF-modelcall", "B1"]
        rows = [("Q3 version-exact (P)", "Q3_version_precision"), ("Q3 filings (P)", "Q3_filings_precision"),
                ("Q4 blast radius (P)", "Q4_blast_precision"), ("Q2 policy version", "Q2_policy_version_accuracy"),
                ("Q5 post-revocation (R)", "Q5_post_revocation_recall"), ("Q6 stale policy (R)", "Q6_stale_policy_recall"),
                ("Q7 exposure (P)", "Q7_untrusted_precision")]
        md += ["\n## Table 2. Ablations (remove one component; same runs)\n",
               "| Query | full | −version | −context | −policy | −lineage | −model-call link | B1 |", "|---|" + "---|" * 7]
        md += [f"| {l} | " + " | ".join(c(b[k_].get(k)) for k_ in cols) + " |" for l, k in rows]

    if "e2" in R:
        drops = sorted(R["e2"], key=float)
        md += ["\n## Table 3. Span-export loss\n",
               "| Drop rate | B0 Q3 R | B1 Q3 R | FAOGF-S Q3 R | FAOGF Q3 R | Spans-only Q2 R | FAOGF Q2 R | Loss detected (orphans) | Loss detected (FAOGF) |",
               "|---|---|---|---|---|---|---|---|---|"]
        for d in drops:
            r = R["e2"][d]
            md.append(f"| {d} | " + " | ".join(c(r[k]["Q3_source_recall"]) for k in CONDS)
                      + f" | {c(r['B1']['Q2_attempt_recall'])} | {c(r['FAOGF']['Q2_attempt_recall'])}"
                      + f" | {c(r['B0']['Q8_lost_span_detection'])} | {c(r['FAOGF']['Q8_lost_span_detection'])} |")
        fig, axes = plt.subplots(1, 2, figsize=(8, 3))
        x = [float(d) for d in drops]
        for cond in CONDS:
            axes[0].plot(x, [m(R["e2"][d][cond]["Q3_source_recall"]) for d in drops], marker="o", label=cond)
            axes[1].plot(x, [m(R["e2"][d][cond]["Q2_attempt_recall"]) for d in drops], marker="o", label=cond)
        axes[0].set_title("Q3 supporting-source recall"); axes[1].set_title("Q2 protected-attempt recall")
        for a in axes:
            a.set_xlabel("span export drop rate"); a.set_ylim(0, 1.05)
        axes[0].legend(fontsize=8)
        save(fig, out, "fig2_span_loss")

    if "e3" in R:
        md += ["\n## Table 4. Evidence-store write failures (FAOGF, fail-closed)\n",
               "| Store fail rate | Protected attempts | Blocked (fail-closed) | Executed without record | Spans flagged unrecorded | Q3 R | Q2 R | Q5 R |",
               "|---|---|---|---|---|---|---|---|"]
        for f, r in R["e3"].items():
            md.append(f"| {f} | {c(r['protected_attempts'], 1)} | {c(r['blocked_fail_closed'], 1)} | "
                      f"{c(r['protected_executed_without_record'], 0)} | {c(r['unrecorded_spans_flagged'], 1)} | "
                      f"{c(r['Q3_source_recall'])} | {c(r['Q2_attempt_recall'])} | {c(r['Q5_recall'])} |")

    if "e8" in R:
        md += ["\n## Table 5. Correlated outages (span loss and store failure together, p=0.9 inside the window)\n",
               "| Outage share | Spool | Blocked | Executed without record | B1 Q3 R | FAOGF Q3 R | B1 Q2 R | FAOGF Q2 R | Loss detected | Spooled records |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in R["e8"].items():
            frac, spool = k.replace("+spool", ""), "yes" if "spool" in k else "no"
            md.append(f"| {frac} | {spool} | {c(r['blocked_fail_closed'], 1)} | {c(r['protected_executed_without_record'], 0)} | "
                      f"{c(r['B1_Q3_recall'])} | {c(r['FAOGF_Q3_recall'])} | {c(r['B1_Q2_recall'])} | "
                      f"{c(r['FAOGF_Q2_recall'])} | {c(r['FAOGF_lost_span_detection'])} | {c(r['spooled_records'], 0)} |")

    if "e9" in R:
        ev = R["e9"]["evict"]
        ps = sorted(ev, key=float)
        md += ["\n## Table 6. Sensitivity to context eviction (Q3 filings precision / Q7 exposure precision)\n",
               "| Eviction rate | B0 | B1 | FAOGF |", "|---|---|---|---|"]
        for p in ps:
            md.append(f"| {p} | " + " | ".join(f"{c(ev[p][k]['Q3_filings_precision'])} / {c(ev[p][k]['Q7_untrusted_precision'])}"
                                              for k in ("B0", "B1", "FAOGF")) + " |")
        dl = R["e9"]["delegate"]
        md += ["\n## Table 7. Sensitivity to delegation rate (Q3 filings recall)\n",
               "| Delegation rate | B0 | B1 | FAOGF |", "|---|---|---|---|"]
        for p in sorted(dl, key=float):
            md.append(f"| {p} | " + " | ".join(c(dl[p][k]["Q3_filings_recall"]) for k in ("B0", "B1", "FAOGF")) + " |")
        fig, axes = plt.subplots(1, 2, figsize=(8, 3))
        for k in ("B0", "B1", "FAOGF"):
            axes[0].plot([float(p) for p in ps], [m(ev[p][k]["Q3_filings_precision"]) for p in ps], marker="o", label=k)
            axes[1].plot([float(p) for p in sorted(dl, key=float)],
                         [m(dl[p][k]["Q3_filings_recall"]) for p in sorted(dl, key=float)], marker="o", label=k)
        axes[0].set_xlabel("share of workflows with context eviction"); axes[0].set_title("Q3 filings precision")
        axes[1].set_xlabel("share of workflows delegating"); axes[1].set_title("Q3 filings recall")
        for a in axes:
            a.set_ylim(0, 1.05)
        axes[0].legend(fontsize=8)
        save(fig, out, "fig3_sensitivity")

    if "e7" in R:
        md += ["\n## Table 8. Scale (one seed)\n",
               "| Workflows | Run time (s) | Spans | Store (MB) | Chain verify (s) | Full audit sweep B0 (ms) | B1 (ms) | FAOGF (ms) |",
               "|---|---|---|---|---|---|---|---|"]
        ns = sorted(R["e7"], key=int)
        for n in ns:
            r = R["e7"][n]
            tot = {k: sum(v.values()) for k, v in r["query_ms"].items()}
            md.append(f"| {n} | {r['run_seconds']} | {r['spans']} | {r['store_mb']} | {r['verify_seconds']} | "
                      f"{tot['B0']:.0f} | {tot['B1']:.0f} | {tot['FAOGF']:.0f} |")
        fig, ax = plt.subplots(figsize=(4.5, 3))
        for k in ("B0", "B1", "FAOGF"):
            ax.plot([int(n) for n in ns], [sum(R["e7"][n]["query_ms"][k].values()) / int(n) for n in ns], marker="o", label=k)
        ax.set_xscale("log"); ax.set_xlabel("workflows in store"); ax.set_ylabel("audit sweep ms / workflow")
        ax.legend(fontsize=8)
        save(fig, out, "fig4_scale")

    if "e10" in R:
        cols = ["B0", "B1", "B2", "B3", "FAOGF"]
        md += ["\n## Table 10. Content-logging baselines (B2 = tool results logged; B3 = tool results + full prompts logged)\n"]
        for mode, title in (("linked", "sub-agent traces linked"), ("fragmented", "asynchronous hand-off, no links"),
                            ("drop0.3", "30% span-export loss")):
            b = R["e10"][mode]
            md += [f"\n**{title}**\n", "| Metric | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
            for label, k, d in (("Q3 filings P", "Q3_filings_precision", 2), ("Q3 filings R", "Q3_filings_recall", 2),
                                ("Q4 blast radius P", "Q4_blast_precision", 2), ("Q4 blast radius R", "Q4_blast_recall", 2),
                                ("Q7 exposure P", "Q7_untrusted_precision", 2), ("Q2 attempts found R", "Q2_attempt_recall", 2),
                                ("Q2 policy version", "Q2_policy_version_accuracy", 2), ("Q5 post-revocation R", "Q5_post_revocation_recall", 2),
                                ("Telemetry KB / workflow", "telemetry_kb_per_workflow", 1),
                                ("Raw content KB / workflow", "raw_content_kb_per_workflow", 1),
                                ("Client account IDs retained / workflow", "sensitive_ids_retained_per_workflow", 1)):
                md.append(f"| {label} | " + " | ".join(c(b[k_].get(k), d) for k_ in cols) + " |")

    if "e11" in R:
        md += ["\n## Table 11. Enforcement against injections that target allowed internal destinations\n",
               "| Policy | Harmful sends attempted | Harmful sends executed | Legitimate sends blocked | Human approvals requested |",
               "|---|---|---|---|---|"]
        for k, r in R["e11"].items():
            if k.startswith("_"):
                continue
            md.append(f"| {k} | {c(r['harmful_attempts'], 1)} | {c(r['harmful_executed'], 1)} | "
                      f"{c(r['legit_blocked'], 1)} | {c(r['human_approvals_requested'], 1)} |")
        md += ["\n**Eviction sensitivity (precise context taint vs coarse history taint)**\n",
               "| Eviction rate | Policy | Legitimate sends blocked | Human approvals | Harmful executed |", "|---|---|---|---|---|"]
        for k, r in R["e11"]["_evict_sweep"].items():
            pe, name = k.split("|")
            md.append(f"| {pe} | {name} | {c(r['legit_blocked'], 1)} | {c(r['human_approvals_requested'], 1)} | "
                      f"{c(r['harmful_executed'], 1)} |")

    if "e12" in R:
        e = R["e12"]
        md += [f"\n## Table 12. Epoch Merkle anchoring ({e['records']} records, {e['store_bytes'] / 1e6:.1f} MB store)\n",
               "| Epoch size | Anchors | Anchor bytes | Commit (ms) | Proof + record (bytes) | Verify (µs) | Suffix rewrite detected (chain only / anchors) | Localised to epoch |",
               "|---|---|---|---|---|---|---|---|"]
        for k, r in e.items():
            if k.startswith("epoch_"):
                md.append(f"| {k[6:]} | {r['anchors']} | {r['anchor_bytes_total']} | {r['commit_ms']} | "
                          f"{r['proof_plus_record_bytes_median']:.0f} | {r['verify_us_median']} | "
                          f"{r['rewrite_detected_by_chain_verify']} / {r['rewrite_detected_by_anchors']} | "
                          f"{r['first_bad_epoch'] == r['true_first_bad_epoch']} |")

    otel_rows = (("Q1 authority chain", "Q1_authority_accuracy"), ("Q2 protected attempts found", "Q2_attempt_recall"),
                 ("Q2 policy version", "Q2_policy_version_accuracy"), ("Q3 supporting filings R", "Q3_filings_recall"),
                 ("Q4 blast radius R", "Q4_blast_recall"), ("Q7 exposure R", "Q7_untrusted_recall"),
                 ("Spans kept / workflow", "spans_per_workflow"))

    def otel_table(block, title, extra=()):
        out = [f"\n**{title}**\n"] + [f"{lbl}: {c(block[k])}  " for lbl, k in extra if k in block]
        out += ["| Query | B0 | B1 | FAOGF-S | FAOGF |", "|---|---|---|---|---|"]
        out += [f"| {l} | " + " | ".join(c(block[cnd].get(k)) for cnd in ("B0", "B1", "FAOGF-S", "FAOGF")) + " |"
                for l, k in otel_rows]
        return out

    if "e13" in R:
        md += ["\n## Table 13. OpenTelemetry sampling (head: SDK ParentBased(TraceIdRatioBased); tail: otelcol-contrib)\n"]
        for k, b in R["e13"].items():
            md += otel_table(b, k)
        heads = [k for k in R["e13"] if k.startswith("head")]
        rates = [float(k.split()[1]) for k in heads]
        fig, ax = plt.subplots(figsize=(5, 3.2))
        for cnd in ("B0", "B1", "FAOGF"):
            ax.plot(rates, [m(R["e13"][k][cnd]["Q2_attempt_recall"]) for k in heads], marker="o", label=f"{cnd} Q2")
        ax.plot(rates, [m(R["e13"][k]["B1"]["Q3_filings_recall"]) for k in heads], marker="s", ls="--", label="B1 Q3")
        ax.set_xscale("log"); ax.set_xlabel("head sampling rate"); ax.set_ylabel("recall"); ax.set_ylim(0, 1.05)
        ax.legend(fontsize=7)
        save(fig, out, "fig5_sampling")
    if "e14" in R and "skipped" not in R["e14"]:
        md += ["\n## Table 14. SDK BatchSpanProcessor queue overflow (OTLP/HTTP to a real Collector, burst load)\n"]
        for k, b in R["e14"].items():
            md += otel_table(b, k, extra=(("Span drop share", "drop_share"),))
            md.append(f"| Lost spans detected | {c(b['B0']['Q8_lost_span_detection'])} | {c(b['B1']['Q8_lost_span_detection'])} | "
                      f"{c(b['FAOGF-S']['Q8_lost_span_detection'])} | {c(b['FAOGF']['Q8_lost_span_detection'])} |")
    if "e15" in R and "skipped" not in R["e15"]:
        md += ["\n## Table 15. Collector processors operators commonly enable\n"]
        for k, b in R["e15"].items():
            md += otel_table(b, k, extra=(("fin.audit registry conformance", "registry_conformance"),))
            md.append(f"| Stripped audit attributes detected | n/a | n/a | n/a | {c(b['FAOGF']['Q9_stripped_detected_share'])} |")

    if "e4" in R:
        e = R["e4"]
        modes = ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in e["by_mode"].items())
        md += [f"\n## Tamper detection\n\n{e['detected']}/{e['trials']} single-point manipulations detected ({modes}) "
               f"over a {e['records']}-record chain. A full suffix rewrite is not detected by chain verification alone "
               f"({e['full_rewrite_detected_by_verify']}) but is detected against an externally anchored head hash "
               f"({e['full_rewrite_detected_by_external_anchor']})."]
    if "e5" in R:
        md += ["\n## Table 9. Per-call instrumentation latency (µs; tool work excluded)\n",
               "| Path | p50 | p95 | p99 |", "|---|---|---|---|"]
        md += [f"| {k} | {v['p50_us']} | {v['p95_us']} | {v['p99_us']} |" for k, v in R["e5"].items()]

    path_md = os.path.join(out, f"report_{R['model']}.md")
    open(path_md, "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/results_scripted.json")
