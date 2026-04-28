"""Summarize and visualize ultimate cache runs from res.jsonl."""
import json
import pathlib
import typing as t

import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "new_batch"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = ("#4C78A8", "#E45756", "#54A24B", "#B279A2")

RUNS = {
    "dsb": {
        "cold": ROOT / "my_rewriter" / "logs_ultimate_cold_dsb" / "dsb" / "res.jsonl",
        "hot": ROOT / "my_rewriter" / "logs_ultimate_hot_dsb" / "dsb" / "res.jsonl",
    },
    "tpch": {
        "cold": ROOT / "my_rewriter" / "logs_ultimate_cold_tpch" / "tpch" / "res.jsonl",
        "hot": ROOT / "my_rewriter" / "logs_ultimate_hot_tpch" / "tpch" / "res.jsonl",
    },
}


def _load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _ratio(num: int, den: int) -> t.Optional[float]:
    if den == 0:
        return None
    return num / den


def _stats(rows: list[dict]) -> dict:
    total = len(rows)
    improved = sum(1 for r in rows if float(r["input_cost"]) > float(r["output_cost"]))
    regressed = sum(1 for r in rows if float(r["input_cost"]) < float(r["output_cost"]))
    equal = total - improved - regressed
    hit = sum(1 for r in rows if r.get("cache_hit") is True)
    llm_invoked = sum(1 for r in rows if r.get("llm_invoked") is True)
    failed = sum(
        1 for r in rows if str(r.get("output_sql")) == "None" or float(r.get("output_cost", 0)) == -1
    )
    avg_rewrite_time_ms = sum(int(r.get("rewrite_time", 0)) for r in rows) / total if total else None
    median_rewrite_time_ms = (
        sorted(int(r.get("rewrite_time", 0)) for r in rows)[total // 2] if total else None
    )
    return {
        "total": total,
        "improved": improved,
        "regressed": regressed,
        "equal": equal,
        "improved_pct": _ratio(improved, total),
        "cache_hit_count": hit,
        "cache_hit_rate": _ratio(hit, total),
        "llm_invoked_count": llm_invoked,
        "failed_count": failed,
        "avg_rewrite_time_ms": avg_rewrite_time_ms,
        "median_rewrite_time_ms": median_rewrite_time_ms,
    }


def _bar_pair(labels, values, title, ylabel, out_path):
    fig, ax = plt.subplots(figsize=(4.8, 3.8))
    x = (0, 1)
    bars = ax.bar(x, values, color=(COLORS[0], COLORS[1]), width=0.55)
    ax.set_title(title, fontsize=11)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.set_xticks(list(x), labels, rotation=12, ha="right")
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", out_path.name)


def _bar_multi(labels, values, title, ylabel, out_path):
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=[COLORS[i % len(COLORS)] for i in x], width=0.6)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.set_xticks(x, labels, rotation=15, ha="right", fontsize=8)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.1f}%", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", out_path.name)


def _dataset_summary(dataset: str, cold_rows: list[dict], hot_rows: list[dict]) -> dict:
    cold = _stats(cold_rows)
    hot = _stats(hot_rows)
    reduction = None
    if cold["avg_rewrite_time_ms"] and hot["avg_rewrite_time_ms"] and cold["avg_rewrite_time_ms"] > 0:
        reduction = 1.0 - hot["avg_rewrite_time_ms"] / cold["avg_rewrite_time_ms"]
    result = {
        "dataset": dataset,
        "ultimate_cold": cold,
        "ultimate_hot": hot,
        "delta": {
            "avg_rewrite_time_reduction": reduction,
            "note": "1 - (hot avg_rewrite_time / cold avg_rewrite_time)",
        },
    }
    return result


def main() -> int:
    final = {}
    for dataset, paths in RUNS.items():
        cold_path, hot_path = paths["cold"], paths["hot"]
        if not cold_path.is_file() or not hot_path.is_file():
            print("skip", dataset, "(missing", cold_path.name, "or", hot_path.name, ")")
            continue

        cold_rows = _load_jsonl(cold_path)
        hot_rows = _load_jsonl(hot_path)
        summary = _dataset_summary(dataset, cold_rows, hot_rows)
        final[dataset] = summary

        out_json = OUT_DIR / f"{dataset}_ultimate_cache_summary.json"
        out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("Wrote", out_json.name)

        c_ms = summary["ultimate_cold"]["avg_rewrite_time_ms"]
        h_ms = summary["ultimate_hot"]["avg_rewrite_time_ms"]
        if c_ms is not None and h_ms is not None:
            _bar_pair(
                ("Ultimate cold", "Ultimate hot"),
                (c_ms, h_ms),
                f"{dataset.upper()} Ultimate: average rewrite time (ms)",
                "ms (rewrite_time in res.jsonl)",
                OUT_DIR / f"{dataset}_ultimate_cache_avg_rewrite_time.png",
            )

        labels = []
        vals = []
        reduction = summary["delta"]["avg_rewrite_time_reduction"]
        if reduction is not None:
            labels.append("Rewrite time\nreduction")
            vals.append(reduction * 100.0)
        hit_rate = summary["ultimate_hot"]["cache_hit_rate"]
        if hit_rate is not None:
            labels.append("Cache hit\nrate (hot)")
            vals.append(hit_rate * 100.0)
        improved_pct = summary["ultimate_hot"]["improved_pct"]
        if improved_pct is not None:
            labels.append("Plan improved\nrate")
            vals.append(improved_pct * 100.0)
        if labels and len(labels) == len(vals):
            _bar_multi(
                labels,
                vals,
                f"{dataset.upper()} Ultimate cache: key percentages",
                "percent",
                OUT_DIR / f"{dataset}_ultimate_cache_key_pct.png",
            )

    if not final:
        print("No dataset outputs found; run ultimate cold/hot first.")
        return 1
    all_out = OUT_DIR / "ultimate_cache_summary.json"
    all_out.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote", all_out.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
