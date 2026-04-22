from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from .common import ensure_directory, load_config, read_csv, resolve_project_path, slugify, timestamp_slug, write_csv


SUMMARY_FIELDS = [
    "mode",
    "cache_profile",
    "endpoint",
    "size_label",
    "size_bytes",
    "sample_count",
    "success_rate",
    "cache_hit_rate",
    "mean_ttfb_ms",
    "median_ttfb_ms",
    "p95_ttfb_ms",
    "mean_total_time_ms",
    "median_total_time_ms",
    "p95_total_time_ms",
    "mean_throughput_mib_s",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize benchmark CSV files.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON.")
    parser.add_argument(
        "--input",
        nargs="+",
        help="One or more benchmark CSV files. Defaults to the newest file in data/raw.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional summary CSV path. Defaults to data/processed/summary_<timestamp>.csv.",
    )
    return parser


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return math.nan
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = math.ceil((pct / 100) * len(ordered)) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def success_flag(row: dict) -> bool:
    return row["success"] == "1" or row["success"] == 1


def cache_hit_flag(row: dict) -> bool:
    header = row.get("x_cache", "").lower()
    return "hit from cloudfront" in header


def choose_input_files(raw_dir: Path, requested: list[str] | None) -> list[Path]:
    if requested:
        resolved = []
        for item in requested:
            path = resolve_project_path(item)
            # 既支持直接传 benchmark.csv，也支持直接传某一轮实验目录。
            if path.is_dir():
                resolved.append(path / "benchmark.csv")
            else:
                resolved.append(path)
        return resolved
    candidates = sorted(raw_dir.glob("*/benchmark.csv"))
    if not candidates:
        raise FileNotFoundError(f"No benchmark CSV files found in {raw_dir}")
    return [candidates[-1]]


def compute_summary(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        # 汇总维度固定为 mode/profile/endpoint/size，和实验矩阵保持一致。
        key = (
            row["mode"],
            row["cache_profile"],
            row["endpoint"],
            row["size_label"],
            row["size_bytes"],
        )
        grouped[key].append(row)

    summaries = []
    for key in sorted(grouped):
        mode, cache_profile, endpoint, size_label, size_bytes = key
        group_rows = grouped[key]
        successful_rows = [row for row in group_rows if success_flag(row)]
        ttfb_values = [float(row["ttfb_ms"]) for row in successful_rows if row["ttfb_ms"]]
        total_values = [float(row["total_time_ms"]) for row in successful_rows if row["total_time_ms"]]
        throughput_values = [
            float(row["throughput_mib_s"]) for row in successful_rows if row["throughput_mib_s"]
        ]
        summaries.append(
            {
                "mode": mode,
                "cache_profile": cache_profile,
                "endpoint": endpoint,
                "size_label": size_label,
                "size_bytes": size_bytes,
                "sample_count": len(group_rows),
                "success_rate": round(len(successful_rows) / len(group_rows), 4),
                "cache_hit_rate": round(
                    sum(1 for row in group_rows if cache_hit_flag(row)) / len(group_rows), 4
                ),
                "mean_ttfb_ms": round(mean(ttfb_values), 3) if ttfb_values else "",
                "median_ttfb_ms": round(median(ttfb_values), 3) if ttfb_values else "",
                "p95_ttfb_ms": round(percentile(ttfb_values, 95), 3) if ttfb_values else "",
                "mean_total_time_ms": round(mean(total_values), 3) if total_values else "",
                "median_total_time_ms": round(median(total_values), 3) if total_values else "",
                "p95_total_time_ms": round(percentile(total_values, 95), 3) if total_values else "",
                "mean_throughput_mib_s": round(mean(throughput_values), 3) if throughput_values else "",
            }
        )
    return summaries


def maybe_generate_plots(summary_rows: list[dict], figures_dir: Path, output_stem: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed; skipping plot generation.")
        return

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in summary_rows:
        grouped[(row["mode"], row["cache_profile"])].append(row)

    figures_dir.mkdir(parents=True, exist_ok=True)
    for (mode, cache_profile), rows in grouped.items():
        rows.sort(key=lambda item: int(item["size_bytes"]))
        sizes = list(dict.fromkeys(row["size_label"] for row in rows if row["endpoint"] == "s3"))
        if not sizes:
            sizes = list(dict.fromkeys(row["size_label"] for row in rows))

        def values_for(endpoint: str, metric: str) -> list[float]:
            mapping = {row["size_label"]: row for row in rows if row["endpoint"] == endpoint}
            values = []
            for size in sizes:
                value = mapping.get(size, {}).get(metric, "")
                values.append(float(value) if value != "" else 0.0)
            return values

        x_positions = list(range(len(sizes)))
        width = 0.35

        for metric, ylabel in [
            ("mean_ttfb_ms", "Mean TTFB (ms)"),
            ("mean_total_time_ms", "Mean total time (ms)"),
        ]:
            # 目前只画最核心的两张对比图，保证输出足够直接易读。
            plt.figure(figsize=(8, 5))
            plt.bar(
                [x - width / 2 for x in x_positions],
                values_for("s3", metric),
                width=width,
                label="S3",
            )
            plt.bar(
                [x + width / 2 for x in x_positions],
                values_for("cloudfront", metric),
                width=width,
                label="CloudFront",
            )
            plt.xticks(x_positions, sizes)
            plt.ylabel(ylabel)
            plt.title(f"{ylabel} by size ({mode}, {cache_profile})")
            plt.legend()
            plt.tight_layout()
            output_path = figures_dir / f"{output_stem}_{mode}_{cache_profile}_{metric}.png"
            plt.savefig(output_path, dpi=200)
            plt.close()
            print(f"Saved plot to {output_path}")


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    benchmark = config["benchmark"]
    result_root = resolve_project_path(benchmark["result_root"])
    input_files = choose_input_files(result_root, args.input)

    rows = []
    for input_file in input_files:
        rows.extend(read_csv(input_file))

    summary_rows = compute_summary(rows)
    if args.output:
        output_path = resolve_project_path(args.output)
        figures_dir = output_path.parent / "figures"
    elif len(input_files) == 1:
        # 单轮分析默认把 summary 和图写回原实验目录。
        output_path = input_files[0].parent / "summary.csv"
        figures_dir = input_files[0].parent / "figures"
    else:
        # 多轮合并分析则单独创建一个 merged 目录保存结果。
        merged_dir = result_root / (
            f"{timestamp_slug()}__merged-analysis__inputs-{slugify(str(len(input_files)))}"
        )
        ensure_directory(merged_dir)
        output_path = merged_dir / "summary.csv"
        figures_dir = merged_dir / "figures"

    write_csv(output_path, SUMMARY_FIELDS, summary_rows)
    print(f"Summary written to {output_path}")
    maybe_generate_plots(summary_rows, figures_dir=figures_dir, output_stem=output_path.stem)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
