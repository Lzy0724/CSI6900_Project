"""
D3 deliverable: runtime curves, failure/timeout-style rates, LLM (rewrite) latency
distributions, cost-benefit vs rewrite-time scatter, and optional paper baselines.

Reads local res.jsonl (ultimate/learned) and/or analyze .log. Outputs under docs/d3_figures/
(ASCII path for Windows + matplotlib).
"""
import json
import math
import pathlib
import re
import typing as t

import matplotlib.pyplot as plt
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "d3_figures"
OUT.mkdir(parents=True, exist_ok=True)
PAPER = ROOT / "docs" / "d3_paper_baseline.json"

# --- Data sources: adjust if your logdir names differ ---------------------------------
# Ultimate hot (has cache_hit, llm_invoked, rewrite_time)
ULTIMATE_HOT = {
    "dsb": ROOT / "my_rewriter" / "logs_ultimate_hot_dsb" / "dsb" / "res.jsonl",
    "tpch": ROOT / "my_rewriter" / "logs_ultimate_hot_tpch" / "tpch" / "res.jsonl",
}
# Optional: learned hot for second curve
LEARNED_HOT = {
    "dsb": ROOT / "my_rewriter" / "logs_learned_hot" / "dsb" / "res.jsonl",
    "tpch": ROOT / "my_rewriter" / "logs_learned_hot" / "tpch" / "res.jsonl",
}
# R-Bot analyze .log (run from my_rewriter: logdir/Database.log) for paper vs ours
PROMPT_LOGS = {
    "tpch_base": ROOT / "my_rewriter" / "logs_tpch_base" / "tpch.log",
    "dsb_base": ROOT / "my_rewriter" / "logs_dsb_base" / "dsb.log",
    "tpch_alt": ROOT / "logs" / "tpch.log",
    "dsb_alt": ROOT / "logs" / "dsb.log",
}

COLORS = ("#4C78A8", "#E45756", "#54A24B", "#B279A2", "#F58518", "#9D755D")


def _load_jsonl(p: pathlib.Path) -> t.List[dict]:
    if not p.is_file():
        return []
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _cost_reduction_frac(r: dict) -> float:
    ic = float(r.get("input_cost", 0))
    oc = float(r.get("output_cost", 0))
    if ic <= 0 or oc < 0 or math.isinf(ic):
        return 0.0
    return max(0.0, min(1.0, (ic - oc) / ic))


def _failed(r: dict) -> bool:
    if str(r.get("output_sql")) == "None":
        return True
    try:
        if float(r.get("output_cost", 0)) < 0:
            return True
    except (TypeError, ValueError):
        return True
    return False


def _parse_log_improved_avg_tt(path: pathlib.Path) -> t.Optional[dict]:
    if not path.is_file():
        return None
    txt = path.read_text(encoding="utf-8", errors="ignore")
    m_imp = [x for x in re.finditer(r"Improved\s+(\d+)\s+out\s+of\s+(\d+)\s+queries", txt)]
    m_tt = [x for x in re.finditer(r"Average Total Time:\s*([0-9.eE+-]+|inf)", txt)]
    if not m_imp or not m_tt:
        return None
    a, b = int(m_imp[-1].group(1)), int(m_imp[-1].group(2))
    tt = m_tt[-1].group(1)
    tt_f = float("inf") if tt == "inf" else float(tt)
    return {"improved": a, "total": b, "improved_pct": 100.0 * a / b if b else 0.0, "avg_total_time_ms": tt_f}


def _paper_json() -> dict:
    if not PAPER.is_file():
        return {}
    try:
        return json.loads(PAPER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def fig_latency_histograms():
    """Overlaid histograms of rewrite_time (ms) for ultimate hot vs learned hot per dataset."""
    for key in ULTIMATE_HOT:
        p_ult, p_lrn = ULTIMATE_HOT[key], LEARNED_HOT.get(key, pathlib.Path(""))
        u_rows, l_rows = _load_jsonl(p_ult), _load_jsonl(p_lrn) if p_lrn else []
        if not u_rows:
            continue
        t_u = [int(r.get("rewrite_time", 0)) for r in u_rows]
        t_l = [int(r.get("rewrite_time", 0)) for r in l_rows] if l_rows else []
        p99u = max(float(np.percentile(t_u, 99) or 1), 1.0)
        p99l = max(float(np.percentile(t_l, 99) or 1), 1.0) if t_l else p99u
        rmax = max(p99u, p99l)
        fig, ax = plt.subplots(figsize=(6.2, 4.0))
        bins = 25
        ax.hist(
            t_u, bins=bins, alpha=0.55, color=COLORS[0], label="Ultimate (hot)", density=True, range=(0, rmax)
        )
        if t_l:
            ax.hist(
                t_l, bins=bins, alpha=0.45, color=COLORS[1], label="Learned (hot)", density=True, range=(0, rmax)
            )
        ax.set_xlabel("rewrite_time (ms)", fontsize=10)
        ax.set_ylabel("Density", fontsize=10)
        ax.set_title(f"{key.upper()}: LLM/rewrite latency distribution (res.jsonl)", fontsize=11)
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT / f"d3_{key}_rewrite_time_hist.png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        print("Wrote", (OUT / f"d3_{key}_rewrite_time_hist.png").name)


def fig_runtime_curves():
    """Sorted rewrite_time curves (empirical "runtime profile") per method."""
    for key in ULTIMATE_HOT:
        p_ult, p_lrn = ULTIMATE_HOT[key], LEARNED_HOT.get(key, pathlib.Path(""))
        u_rows, l_rows = _load_jsonl(p_ult), _load_jsonl(p_lrn) if p_lrn else []
        if not u_rows:
            continue
        t_u = sorted(int(r.get("rewrite_time", 0)) for r in u_rows)
        t_l = sorted(int(r.get("rewrite_time", 0)) for r in l_rows) if l_rows else None
        fig, ax = plt.subplots(figsize=(5.6, 4.0))
        ax.plot(range(len(t_u)), t_u, color=COLORS[0], lw=1.5, label="Ultimate (hot), sorted")
        if t_l:
            ax.plot(range(len(t_l)), t_l, color=COLORS[1], lw=1.2, label="Learned (hot), sorted", alpha=0.9)
        ax.set_xlabel("Query rank (by ascending rewrite time)", fontsize=9)
        ax.set_ylabel("rewrite_time (ms)", fontsize=9)
        ax.set_title(f"{key.upper()}: sorted rewrite-time profile", fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT / f"d3_{key}_sorted_rewrite_time_curve.png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        print("Wrote", (OUT / f"d3_{key}_sorted_rewrite_time_curve.png").name)


def fig_failure_rates():
    """Bar chart: "failure" rate (bad output) per dataset and method (ultimate vs learned if present)."""
    keys = [k for k in ULTIMATE_HOT if ULTIMATE_HOT[k].is_file() or LEARNED_HOT.get(k) and LEARNED_HOT[k].is_file()]
    if not keys:
        return
    w = 0.35
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    for i, key in enumerate(keys):
        p_u, p_l = ULTIMATE_HOT[key], LEARNED_HOT.get(key, pathlib.Path(""))
        u_rows = _load_jsonl(p_u) if p_u.is_file() else []
        l_rows = _load_jsonl(p_l) if p_l and p_l.is_file() else []
        fu_u = sum(1 for r in u_rows if _failed(r)) / len(u_rows) * 100 if u_rows else 0.0
        fu_l = sum(1 for r in l_rows if _failed(r)) / len(l_rows) * 100 if l_rows else None
        x0, x1 = i - w / 2, i + w / 2
        ax.bar(x0, fu_u, w, color=COLORS[0], label="Ultimate" if i == 0 else None)
        if l_rows:
            ax.bar(x1, fu_l, w, color=COLORS[1], label="Learned" if i == 0 else None)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([k.upper() for k in keys], rotation=10, ha="right")
    ax.set_ylabel("Bad output rate (%)", fontsize=9)
    ax.set_title("Proxy failure rate: output_sql=None or output_cost<0 in res.jsonl", fontsize=10)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "d3_failure_rate_by_dataset.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote d3_failure_rate_by_dataset.png")


def fig_correlation_scatter():
    """Scatter: x = cost reduction fraction, y = log10(1+rewrite_time_ms) — cost vs 'LLM time' (proxy)."""
    for key in ULTIMATE_HOT:
        p = ULTIMATE_HOT[key]
        rows = _load_jsonl(p)
        if len(rows) < 3:
            continue
        x = [_cost_reduction_frac(r) for r in rows]
        y = [math.log10(1.0 + int(r.get("rewrite_time", 0))) for r in rows]
        ch = [bool(r.get("cache_hit")) for r in rows]
        fig, ax = plt.subplots(figsize=(5.4, 4.0))
        hit_x = [x[i] for i, h in enumerate(ch) if h]
        hit_y = [y[i] for i, h in enumerate(ch) if h]
        miss_x = [x[i] for i, h in enumerate(ch) if not h]
        miss_y = [y[i] for i, h in enumerate(ch) if not h]
        if miss_x:
            ax.scatter(miss_x, miss_y, c=COLORS[1], s=20, alpha=0.6, label="no cache (cold in batch)")
        if hit_x:
            ax.scatter(hit_x, hit_y, c=COLORS[0], s=20, alpha=0.5, label="cache hit (hot run)")
        ax.set_xlabel("Relative plan cost gain (input−output)/input", fontsize=9)
        ax.set_ylabel("log10(1 + rewrite_time_ms)", fontsize=9)
        ax.set_title(f"{key.upper()}: cost gain vs LLM/rewrite time (proxy; not phys. speedup)", fontsize=9)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT / f"d3_{key}_cost_gain_vs_log_rewrite_scatter.png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        print("Wrote", (OUT / f"d3_{key}_cost_gain_vs_log_rewrite_scatter.png").name)

    if len(ULTIMATE_HOT) == 0:
        return
    if all(not _load_jsonl(ULTIMATE_HOT[k]) for k in ULTIMATE_HOT if ULTIMATE_HOT[k].is_file()):
        return
    all_x, all_y, colors = [], [], []
    for j, key in enumerate(ULTIMATE_HOT):
        p = ULTIMATE_HOT[key]
        rows = _load_jsonl(p)
        for r in rows:
            all_x.append(_cost_reduction_frac(r))
            all_y.append(math.log10(1.0 + int(r.get("rewrite_time", 0))))
            colors.append(COLORS[j % len(COLORS)])
    if len(all_x) > 2:
        fig, ax = plt.subplots(figsize=(5.0, 4.0))
        ax.scatter(all_x, all_y, c=colors, s=12, alpha=0.4)
        ax.set_xlabel("Relative plan cost gain", fontsize=9)
        ax.set_ylabel("log10(1 + rewrite_time_ms)", fontsize=9)
        ax.set_title("All datasets: cost gain vs log rewrite (legend by color order DSB,TPCH)", fontsize=8)
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(OUT / "d3_pooled_cost_vs_log_rewrite.png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        print("Wrote d3_pooled_cost_vs_log_rewrite.png")


def _count_inf_reported(path: pathlib.Path) -> t.Optional[tuple[int, int]]:
    if not path.is_file():
        return None
    txt = path.read_text(encoding="utf-8", errors="ignore")
    n_inf = len(re.findall(r"(?:Average Overall|Median Overall|Average:|Median:)\s*inf", txt, re.I))
    n_lines = max(1, len(re.findall(r"Improved\s+\d+\s+out\s+of", txt)) or 1)
    return n_inf, n_lines


def fig_timeout_inf_proxy():
    """Proxy for 'timeout/inf' style outcomes in analyze .log (large-run SQL latency = inf in logs)."""
    logs = {
        "dsb_ultimate_hot": ROOT / "my_rewriter" / "logs_ultimate_hot_dsb" / "dsb.log",
        "tpch_ultimate_hot": ROOT / "my_rewriter" / "logs_ultimate_hot_tpch" / "tpch.log",
    }
    items = []
    for lab, p in logs.items():
        t = _count_inf_reported(p)
        if t is None:
            continue
        n_inf, _ = t
        items.append((lab, n_inf))
    if not items:
        return
    fig, ax = plt.subplots(figsize=(5.0, 3.4))
    x = list(range(len(items)))
    ax.bar(
        x,
        [b for _, b in items],
        color=[COLORS[i % len(COLORS)] for i in x],
        width=0.55,
    )
    ax.set_xticks(x, [a.replace("_", "\n") for a, _ in items], rotation=0, ha="center", fontsize=7)
    ax.set_ylabel("Count of 'inf' latency lines in log (proxy)", fontsize=8)
    ax.set_title("Timeout proxy: 'inf' in analyze log (not query-level %)", fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "d3_timeout_inf_count_analyze_log.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote d3_timeout_inf_count_analyze_log.png")


def fig_paper_bars():
    """Side-by-side: improved % and avg total time from R-Bot logs vs paper JSON (if filled)."""
    paper = _paper_json()
    our_logs = {
        "tpch": [PROMPT_LOGS.get("tpch_base"), PROMPT_LOGS.get("tpch_alt")],
        "dsb": [PROMPT_LOGS.get("dsb_base"), PROMPT_LOGS.get("dsb_alt")],
    }
    series = {}
    for ds, candidates in our_logs.items():
        found = None
        for c in candidates:
            if c and c.is_file():
                found = _parse_log_improved_avg_tt(c)
                if found and found.get("total", 0) > 0:
                    break
        if found:
            series[ds] = found

    if not series:
        print("skip paper bar chart (no R-Bot analyze logs found at expected paths)")
        return
    p_tpch, p_dsb = paper.get("tpch", {}), paper.get("dsb", {})
    order: t.List[t.Tuple[str, t.Any]] = []
    for k_label, k_key in (("TPCH", "tpch"), ("DSB", "dsb")):
        if k_key in series:
            order.append((k_label, series[k_key]))
    nplots = max(1, len(order))
    fig, axes = plt.subplots(1, nplots, figsize=(4.0 + 3.5 * nplots, 3.6))
    if nplots == 1:
        axes = [axes]
    for ax, (ds, data) in zip(axes, order):
        if not data:
            ax.set_visible(False)
            continue
        pp = p_tpch if ds == "TPCH" else p_dsb
        paper_imp = pp.get("r_bot_improved_pct")
        paper_tt = pp.get("r_bot_avg_total_time_ms")
        labels, vals, cols = ["Ours (log)"], [data["improved_pct"]], [COLORS[0]]
        if paper_imp is not None:
            labels.append("Paper (from JSON)")
            vals.append(float(paper_imp))
            cols.append(COLORS[2])
        x = range(len(labels))
        ax.bar(x, vals, color=cols, width=0.55)
        ax.set_xticks(list(x), labels, rotation=12, ha="right", fontsize=8)
        ax.set_ylabel("Improved % of queries (cost-based)", fontsize=8)
        ax.set_title(f"{ds}: R-Bot improved% (fill paper in d3_paper_baseline.json)", fontsize=9)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("D3: Ours vs paper (optional)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "d3_ours_vs_paper_improved_pct.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote d3_ours_vs_paper_improved_pct.png")

    fig, axes2 = plt.subplots(1, nplots, figsize=(4.0 + 3.5 * nplots, 3.6))
    if nplots == 1:
        axes2 = [axes2]
    for ax, (ds, data) in zip(axes2, order):
        if not data or not math.isfinite(data.get("avg_total_time_ms", float("inf"))):
            if not data:
                ax.set_visible(False)
            continue
        pp = p_tpch if ds == "TPCH" else p_dsb
        paper_tt = pp.get("r_bot_avg_total_time_ms")
        cur = data["avg_total_time_ms"]
        if not math.isfinite(cur) or cur == float("inf"):
            continue
        labels, vals, cols = ["Ours (log)"], [cur], [COLORS[0]]
        if paper_tt is not None and math.isfinite(float(paper_tt)):
            labels.append("Paper (from JSON)")
            vals.append(float(paper_tt))
            cols.append(COLORS[2])
        x = range(len(labels))
        ax.bar(x, vals, color=cols, width=0.55)
        ax.set_xticks(list(x), labels, rotation=12, ha="right", fontsize=8)
        ax.set_ylabel("Average Total Time (ms)", fontsize=8)
        ax.set_title(f"{ds}: pipeline time", fontsize=9)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("D3: average total time — ours vs paper (optional)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "d3_ours_vs_paper_avg_total_time.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote d3_ours_vs_paper_avg_total_time.png")


def _write_d3_index():
    index = {
        "figures": [
            "d3_*_rewrite_time_hist.png",
            "d3_*_sorted_rewrite_time_curve.png",
            "d3_failure_rate_by_dataset.png",
            "d3_*_cost_gain_vs_log_rewrite_scatter.png",
            "d3_pooled_cost_vs_log_rewrite.png",
            "d3_ours_vs_paper_improved_pct.png",
            "d3_ours_vs_paper_avg_total_time.png",
            "d3_timeout_inf_count_analyze_log.png",
        ],
        "notes": {
            "timeout": "No explicit server-side timeout in res.jsonl; 'failure' uses output_sql==None or output_cost<0. True SQL 300s timeouts are in analyze flow only.",
            "correlation": "Cost gain vs log(rewrite_time) is a proxy, not physical speedup; for SQL speedup, use analyze --compute_latency and join per query.",
        },
    }
    (OUT / "d3_figures_index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print("Wrote d3_figures_index.json")


def main() -> int:
    fig_latency_histograms()
    fig_runtime_curves()
    fig_failure_rates()
    fig_correlation_scatter()
    fig_paper_bars()
    fig_timeout_inf_proxy()
    _write_d3_index()
    print("All outputs in", str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
