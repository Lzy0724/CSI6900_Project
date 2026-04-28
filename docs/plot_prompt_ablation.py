"""
Parse R-Bot prompt ablation logs (logs_tpch_* / logs_dsb_*), write JSON + bar charts
matching the style of plot_*_metrics.py.
"""
import json
import re
import pathlib
import typing as t

import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
# ASCII path so Windows + matplotlib can save without encoding issues
OUT = ROOT / "docs" / "prompt_ablation_batch"
COLORS = ("#4C78A8", "#F58518", "#54A24B", "#B279A2")


def _last_match(pattern: str, text: str) -> t.Optional[re.Match]:
    m = [x for x in re.finditer(pattern, text)]
    return m[-1] if m else None


def parse_analyze_log(path: pathlib.Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    m_imp = _last_match(r"Improved\s+(\d+)\s+out\s+of\s+(\d+)\s+queries", txt)
    m_tt = _last_match(r"Average Total Time:\s*([0-9.eE+-]+|inf)", txt)
    m_mo = _last_match(r"Median Overall:\s*([0-9.eE+-]+|inf)", txt)
    m_ao = _last_match(r"Average Overall:\s*([0-9.eE+-]+|inf)", txt)
    if not m_imp or not m_tt:
        return {"_error": f"parse failed: {path}"}
    a, b = int(m_imp.group(1)), int(m_imp.group(2))
    tt = m_tt.group(1)
    tt_f = float("inf") if tt == "inf" else float(tt)
    mo = float("inf")
    if m_mo:
        mo = float("inf") if m_mo.group(1) == "inf" else float(m_mo.group(1))
    ao: t.Optional[float] = None
    if m_ao and m_ao.group(1) != "inf":
        ao = float(m_ao.group(1))
    return {
        "improved": a,
        "total": b,
        "improved_pct": 100.0 * a / b if b else 0.0,
        "avg_total_time_ms": tt_f,
        "median_overall_ms": mo,
        "avg_overall_ms": ao,
    }


def _bar(
    labels: list,
    values: list,
    title: str,
    ylabel: str,
    out: pathlib.Path,
    value_labels: t.Optional[list] = None,
):
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    x = list(range(len(labels)))
    c = [COLORS[i % len(COLORS)] for i in x]
    bars = ax.bar(x, values, color=c, width=0.65)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.set_xticks(x, labels, rotation=20, ha="right", fontsize=9)
    for i, b in enumerate(bars):
        v = values[i]
        if value_labels is not None:
            s = value_labels[i]
        elif v != v or v == float("inf"):
            s, y = "inf", max(values) * 0.02 if values else 0
        else:
            s = f"{v:.0f}" if abs(v) > 30 else f"{v:.1f}"
        y = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, y, str(s), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", out)


def _ser(d: dict) -> dict:
    o = {}
    for k, v in d.items():
        if v == float("inf"):
            o[k] = "inf"
        else:
            o[k] = v
    return o


def run_one(prefix: str, name: str, log_name: str):
    runs: list[tuple[str, str, str]] = [
        ("base\n(Top-5)", f"logs_{prefix}_base", "Top-5, no prune"),
        ("Top-1", f"logs_{prefix}_top1", "Top-1, no prune"),
        ("prune+Top-5", f"logs_{prefix}_prune_top5", "prune+Top-5"),
        ("prune+Top-1", f"logs_{prefix}_prune_top1", "prune+Top-1"),
    ]
    rows: dict = {}
    for short, d, _note in runs:
        p = ROOT / d / log_name
        if not p.is_file():
            print("Missing", p)
            continue
        m = parse_analyze_log(p)
        m["logdir"] = d
        m["config_note"] = _note
        if "_error" in m:
            print(m["_error"])
            continue
        rows[short] = m

    if not rows:
        return

    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / f"prompt_ablation_{prefix}_summary.json"
    serial = {k: _ser(v) for k, v in rows.items()}
    out_json.write_text(json.dumps(serial, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote", out_json)

    keys = list(rows.keys())
    _bar(
        keys,
        [rows[k]["improved_pct"] for k in keys],
        f"{name}: improved query share (%)",
        "Share of queries improved (%)",
        OUT / f"prompt_ablation_{prefix}_improved_pct.png",
    )
    ttm_raw = [rows[k]["avg_total_time_ms"] for k in keys]
    fin = [t for t in ttm_raw if t != float("inf") and t == t]
    cap = max(fin) * 1.05 if fin else 1.0
    ttm = [cap if t == float("inf") else t for t in ttm_raw]
    ttm_lbl = [f"{t:.0f}" if t != float("inf") else "inf" for t in ttm_raw]
    _bar(
        keys,
        ttm,
        f"{name}: average total pipeline time (ms)",
        "ms",
        OUT / f"prompt_ablation_{prefix}_avg_total_time.png",
        value_labels=ttm_lbl,
    )
    # median overall (skip if all inf)
    mo = [rows[k]["median_overall_ms"] for k in keys]
    if not all(m == float("inf") for m in mo):
        _bar(
            keys,
            [0 if m == float("inf") else m for m in mo],
            f"{name}: median overall (ms, --large)",
            "ms",
            OUT / f"prompt_ablation_{prefix}_median_overall.png",
        )
    aov = [rows[k].get("avg_overall_ms") for k in keys]
    if aov and all(x is not None for x in aov):
        _bar(keys, aov, f"{name}: average overall (ms, --large)", "ms", OUT / f"prompt_ablation_{prefix}_avg_overall.png")


def main():
    run_one("tpch", "TPC-H", "tpch.log")
    run_one("dsb", "DSB", "dsb.log")


if __name__ == "__main__":
    main()
