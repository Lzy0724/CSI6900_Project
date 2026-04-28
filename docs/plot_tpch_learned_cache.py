"""Parse TPC-H learned cache analyze logs, write tpch_learned_cache_summary.json, and bar charts."""
import json
import re
import pathlib
import typing as t

import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_COLD = ROOT / "my_rewriter" / "logs_learned_cold" / "tpch.log"
LOG_HOT = ROOT / "my_rewriter" / "logs_learned_hot" / "tpch.log"

COLORS = ("#4C78A8", "#E45756", "#54A24B", "#B279A2")


def _last_group(pattern: str, text: str, group: int = 1) -> t.Optional[str]:
    m = [x for x in re.finditer(pattern, text)]
    if not m:
        return None
    return m[-1].group(group)


def _last_float(pattern: str, text: str, group: int = 1) -> t.Optional[float]:
    s = _last_group(pattern, text, group)
    if s is None or s == "inf":
        return None
    return float(s)


def parse_block(path: pathlib.Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    imp = _last_group(r"Improved\s+(\d+)\s+out\s+of\s+(\d+)\s+queries", txt, 1)
    if imp is None:
        return {"_error": f"no Improved line in {path}"}
    n_imp = int(imp)
    n_tot = int(_last_group(r"Improved\s+(\d+)\s+out\s+of\s+(\d+)\s+queries", txt, 2))
    d: dict = {
        "source_log": str(path.relative_to(ROOT)),
        "improved": n_imp,
        "total": n_tot,
        "improved_pct": 100.0 * n_imp / n_tot,
        "avg_total_time_ms": _last_float(r"Average Total Time:\s*([0-9.eE+-]+)", txt),
        "avg_overall_ms": _last_float(r"Average Overall:\s*([0-9.eE+-]+)", txt),
        "median_overall_ms": _last_float(r"Median Overall:\s*([0-9.eE+-]+)", txt),
        "cache_hit_rate": _last_float(r"Cache Hit Rate:\s*([0-9.eE+-]+)", txt),
        "avg_rewrite_time_hot_ms": _last_float(r"Average Rewrite Time \(Hot\):\s*([0-9.eE+-]+)", txt),
        "avg_rewrite_time_cold_ms": _last_float(r"Average Rewrite Time \(Cold\):\s*([0-9.eE+-]+)", txt),
        "rewrite_time_improvement_ratio": _last_float(
            r"Rewrite Time Improvement \(Hot vs Cold\):\s*([0-9.eE+-]+)", txt
        ),
    }
    return d


def _bar_pair(labels, values, title, ylabel, out_path):
    fig, ax = plt.subplots(figsize=(4.6, 3.8))
    x = (0, 1)
    bars = ax.bar(x, values, color=(COLORS[0], COLORS[1]), width=0.55)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.set_xticks(list(x), labels, rotation=12, ha="right")
    for b, v in zip(bars, values):
        if v is None or (isinstance(v, float) and v != v):
            continue
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", out_path)


def _bar_multi(labels, values, title, ylabel, out_path):
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=[COLORS[i % len(COLORS)] for i in x], width=0.6)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.set_xticks(x, labels, rotation=15, ha="right", fontsize=8)
    for b, v in zip(bars, values):
        ax.text(
            b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.1f}%", ha="center", va="bottom", fontsize=8
        )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", out_path)


def main():
    out_dir = ROOT / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not LOG_COLD.is_file() or not LOG_HOT.is_file():
        print("Missing", LOG_COLD, "or", LOG_HOT, "- run analyze for tpch cold/hot first.")
        return 1
    cold = parse_block(LOG_COLD)
    hot = parse_block(LOG_HOT)
    if cold.get("_error") or hot.get("_error"):
        print(cold, hot)
        return 1

    c_oa = cold.get("avg_overall_ms")
    h_oa = hot.get("avg_overall_ms")
    e2e_ratio = None
    if c_oa and h_oa and c_oa > 0:
        e2e_ratio = (c_oa - h_oa) / c_oa

    clean = {
        "learned_cache_off": {k: v for k, v in cold.items() if k != "_error"},
        "learned_cache_on_hot": {k: v for k, v in hot.items() if k != "_error"},
        "delta": {
            "e2e_avg_overall_ms_reduction": e2e_ratio,
            "e2e_note": "1 - (hot avg_overall / cold avg_overall); same TPC-H queries as in logs",
        },
    }
    (out_dir / "tpch_learned_cache_summary.json").write_text(
        json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Wrote", out_dir / "tpch_learned_cache_summary.json")

    c_tt = cold.get("avg_total_time_ms")
    h_tt = hot.get("avg_total_time_ms")
    if c_oa and h_oa:
        overall_vals = (c_oa, h_oa)
        overall_ylabel = "ms (Average Overall, --large)"
    else:
        # Keep output file parity with DSB even when Average Overall is unavailable.
        overall_vals = (c_tt, h_tt)
        overall_ylabel = "ms (fallback to Average Total Time)"
    if overall_vals[0] and overall_vals[1]:
        _bar_pair(
            ("Cache off (cold)", "Cache on (hot)"),
            overall_vals,
            "TPC-H Learned: average end-to-end time (ms)",
            overall_ylabel,
            out_dir / "tpch_learned_cache_avg_overall.png",
        )
    if c_tt and h_tt:
        _bar_pair(
            ("Cache off (cold)", "Cache on (hot)"),
            (c_tt, h_tt),
            "TPC-H Learned: average pipeline time (ms)",
            "ms (Average Total Time)",
            out_dir / "tpch_learned_cache_avg_total_time.png",
        )
    hhr = hot.get("cache_hit_rate")
    rti = hot.get("rewrite_time_improvement_ratio")
    labels, vals = [], []
    if e2e_ratio is not None:
        labels.append("E2E latency\nreduction")
        vals.append(e2e_ratio * 100.0)
    if hhr is not None:
        labels.append("Cache\nhit rate")
        vals.append(hhr * 100.0)
    if rti is not None:
        labels.append("Relative rewrite\ntime gain (hot vs cold samples)")
        vals.append(rti * 100.0)
    if len(labels) == len(vals) and labels:
        _bar_multi(
            labels,
            vals,
            "TPC-H Learned cache: key percentages",
            "percent",
            out_dir / "tpch_learned_cache_key_pct.png",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
