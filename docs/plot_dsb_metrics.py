"""Parse DSB analyze logs, write dsb_metrics_summary.json, and three separate bar charts."""
import json
import re
import pathlib

import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
COLORS = ["#4C78A8", "#F58518", "#54A24B"]
FILES = {
    "R-Bot": ROOT / "logs" / "dsb.log",
    "LLM-Only": ROOT / "my_rewriter" / "logs_llm_only" / "dsb.log",
    "LearnedRewrite": ROOT / "my_rewriter" / "logs_learned_rewrite" / "dsb.log",
}


def _single_bar_chart(labels, values, title, ylabel, out_path):
    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=COLORS)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.set_xticks(x, labels, rotation=18, ha="right")
    for b, v in zip(bars, values):
        lab = f"{v:.1f}" if v > 200 else f"{v:.2f}"
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), lab, ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", out_path)


def main():
    metrics = {}
    for k, p in FILES.items():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        m1 = re.findall(r"Improved\s+(\d+)\s+out\s+of\s+(\d+)\s+queries", txt)
        m_med = re.findall(
            r"^\d{2}:\d{2}:\d{2},\d+\s+root INFO Median:\s*([0-9.eE+-]+|inf)\s*$", txt, re.M
        )
        m_med_overall = re.findall(
            r"^\d{2}:\d{2}:\d{2},\d+\s+root INFO Median Overall:\s*([0-9.eE+-]+|inf)\s*$",
            txt,
            re.M,
        )
        m3 = re.findall(r"Average Total Time:\s*([0-9.]+|inf)", txt)
        if not m1:
            raise SystemExit(f"no Improved line in {p}")
        imp, tot = map(int, m1[-1])
        med_s = float(m_med[-1]) if m_med and m_med[-1] != "inf" else float("inf")
        med_overall_ms = (
            float(m_med_overall[-1]) if m_med_overall and m_med_overall[-1] != "inf" else float("inf")
        )
        avg = float("inf") if not m3 or m3[-1] == "inf" else float(m3[-1])
        med_ms = med_s * 1000.0 if med_s != float("inf") else float("inf")
        metrics[k] = {
            "improved": imp,
            "total": tot,
            "improved_pct": imp * 100.0 / tot,
            "median_output_latency_s": med_s,
            "median_output_ms": med_ms,
            "median_overall_ms": med_overall_ms,
            "avg_total_time_ms": avg,
            "note": (
                "If Median Overall exists (analyze --large), chart uses it; "
                "otherwise falls back to Median output latency."
            ),
        }

    out_dir = ROOT / "docs"
    out_json = out_dir / "dsb_metrics_summary.json"
    out_json.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Wrote", out_json)

    labels = list(metrics)
    improved = [metrics[k]["improved_pct"] for k in labels]
    median = [
        metrics[k]["median_overall_ms"]
        if metrics[k]["median_overall_ms"] != float("inf")
        else metrics[k]["median_output_ms"]
        for k in labels
    ]
    att = [metrics[k]["avg_total_time_ms"] for k in labels]

    _single_bar_chart(
        labels,
        improved,
        "DSB: Improved query ratio (%)",
        "Share of queries improved (%)",
        out_dir / "dsb_chart_improved_pct.png",
    )
    _single_bar_chart(
        labels,
        median,
        "DSB: Median overall latency (ms)",
        "ms (Median Overall if available)",
        out_dir / "dsb_chart_median_output_ms.png",
    )
    _single_bar_chart(
        labels,
        att,
        "DSB: Average total pipeline time (ms)",
        "ms",
        out_dir / "dsb_chart_avg_total_time_ms.png",
    )


if __name__ == "__main__":
    main()
