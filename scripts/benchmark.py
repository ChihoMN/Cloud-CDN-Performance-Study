from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import requests

from .common import (
    ensure_directory,
    load_config,
    read_csv,
    resolve_project_path,
    slugify,
    timestamp_slug,
    utc_timestamp,
    write_csv,
    write_json,
)


BENCHMARK_FIELDS = [
    "run_id",
    "recorded_at_utc",
    "round_index",
    "mode",
    "endpoint",
    "cache_profile",
    "size_label",
    "size_bytes",
    "request_index",
    "object_key",
    "url",
    "status_code",
    "success",
    "ttfb_ms",
    "total_time_ms",
    "bytes_read",
    "throughput_mib_s",
    "x_cache",
    "age_header",
    "error_message",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark S3 and CloudFront object fetches.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON.")
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional path to the uploaded object manifest CSV.",
    )
    parser.add_argument(
        "--endpoint",
        choices=["s3", "cloudfront", "both"],
        default="both",
        help="Which endpoint(s) to benchmark.",
    )
    parser.add_argument(
        "--mode",
        choices=["single-hot", "hotspot", "distributed"],
        default="distributed",
        help="How to select objects during the experiment.",
    )
    parser.add_argument(
        "--profile",
        default="baseline",
        help="Cache profile to benchmark. Must exist in the uploaded manifest.",
    )
    parser.add_argument(
        "--size-label",
        nargs="+",
        help="Optional subset of size labels to benchmark.",
    )
    parser.add_argument(
        "--requests-per-size",
        type=int,
        help="How many requests to issue per size label in each round.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        help="How many rounds to repeat for each size label.",
    )
    parser.add_argument("--seed", type=int, default=5296, help="Random seed for reproducible sequences.")
    parser.add_argument(
        "--sleep",
        type=float,
        default=None,
        help="Optional sleep between requests in seconds.",
    )
    parser.add_argument(
        "--result-dir",
        default=None,
        help="Optional result directory. Defaults to result/<timestamp>__<params>/",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional benchmark CSV path. This overrides the default result/<run>/benchmark.csv path.",
    )
    return parser


def load_manifest_rows(manifest_path: Path, profile: str, allowed_sizes: set[str] | None) -> list[dict]:
    rows = read_csv(manifest_path)
    # benchmark 只关心当前 profile 和指定尺寸范围内的对象。
    filtered = [
        row for row in rows
        if row["cache_profile"] == profile and (allowed_sizes is None or row["size_label"] in allowed_sizes)
    ]
    if not filtered:
        raise ValueError(
            f"No uploaded objects found for profile '{profile}' in {manifest_path}"
        )
    return filtered


def group_by_size(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["size_label"], []).append(row)
    # 固定对象顺序，保证 single-hot 模式在不同轮次下可复现。
    for size_rows in grouped.values():
        size_rows.sort(key=lambda row: int(row["file_index"]))
    return grouped


def build_sequence(
    objects_for_size: list[dict],
    mode: str,
    requests_per_size: int,
    rng: random.Random,
    hotspot_ratio: float,
    hotspot_pool_size: int,
) -> list[dict]:
    if mode == "single-hot":
        # 始终访问同一个对象，用来触发明显的 Miss/Hit 对比。
        return [objects_for_size[0] for _ in range(requests_per_size)]

    if mode == "hotspot":
        # 热点模式下，大部分请求命中少数热门对象，少量请求访问完整对象池。
        hot_pool = objects_for_size[: max(1, min(hotspot_pool_size, len(objects_for_size)))]
        sequence = []
        for _ in range(requests_per_size):
            if rng.random() < hotspot_ratio:
                sequence.append(rng.choice(hot_pool))
            else:
                sequence.append(rng.choice(objects_for_size))
        return sequence

    return [rng.choice(objects_for_size) for _ in range(requests_per_size)]


def endpoint_order(endpoint: str, rng: random.Random) -> list[str]:
    if endpoint == "both":
        # 同一批对象既测 S3 又测 CloudFront，并随机化顺序降低固定先后偏差。
        names = ["s3", "cloudfront"]
        rng.shuffle(names)
        return names
    return [endpoint]


def size_scope_slug(size_labels: set[str] | None) -> str:
    if not size_labels:
        return "all-sizes"
    ordered = sorted(size_labels)
    return slugify("sizes-" + "_".join(ordered), max_length=64)


def default_run_dir(result_root: Path, args: argparse.Namespace, requests_per_size: int, rounds: int) -> Path:
    # 结果目录名直接编码实验参数，后续查看结果时不需要再回头查命令行。
    run_name = "__".join(
        [
            timestamp_slug(),
            f"profile-{slugify(args.profile)}",
            f"mode-{slugify(args.mode)}",
            f"endpoint-{slugify(args.endpoint)}",
            size_scope_slug(set(args.size_label) if args.size_label else None),
            f"req-{requests_per_size}",
            f"rounds-{rounds}",
        ]
    )
    return result_root / run_name


def measure_request(
    session: requests.Session,
    url: str,
    connect_timeout: float,
    read_timeout: float,
) -> dict:
    start = time.perf_counter()
    bytes_read = 0
    try:
        # stream=True 允许我们分别测量首字节时间和完整下载时间。
        response = session.get(url, stream=True, timeout=(connect_timeout, read_timeout))
        header_time = time.perf_counter()
        first_chunk_time = None
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            if first_chunk_time is None:
                first_chunk_time = time.perf_counter()
            bytes_read += len(chunk)
        end = time.perf_counter()
        response.close()

        ttfb = (first_chunk_time or header_time) - start
        total_time = end - start
        # 当前吞吐量按完整下载时间计算，便于直接和 total time 对应。
        throughput = (bytes_read / (1024 * 1024)) / total_time if total_time > 0 else 0.0
        status_code = response.status_code
        return {
            "status_code": status_code,
            "success": 1 if 200 <= status_code < 400 else 0,
            "ttfb_ms": round(ttfb * 1000, 3),
            "total_time_ms": round(total_time * 1000, 3),
            "bytes_read": bytes_read,
            "throughput_mib_s": round(throughput, 6),
            "x_cache": response.headers.get("X-Cache", ""),
            "age_header": response.headers.get("Age", ""),
            "error_message": "",
        }
    except requests.RequestException as error:
        end = time.perf_counter()
        # 出错时记录错误信息并继续执行，避免单个异常中断整轮实验。
        return {
            "status_code": "",
            "success": 0,
            "ttfb_ms": "",
            "total_time_ms": round((end - start) * 1000, 3),
            "bytes_read": bytes_read,
            "throughput_mib_s": "",
            "x_cache": "",
            "age_header": "",
            "error_message": str(error),
        }


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    dataset = config["dataset"]
    benchmark = config["benchmark"]
    manifest_path = resolve_project_path(args.manifest or dataset["uploaded_manifest"])
    result_root = resolve_project_path(benchmark["result_root"])
    allowed_sizes = set(args.size_label) if args.size_label else None
    rows = load_manifest_rows(manifest_path, profile=args.profile, allowed_sizes=allowed_sizes)
    rows_by_size = group_by_size(rows)

    requests_per_size = args.requests_per_size or benchmark["default_requests_per_size"]
    rounds = args.rounds or benchmark["default_rounds"]
    sleep_time = benchmark["sleep_between_requests_seconds"] if args.sleep is None else args.sleep
    hotspot_ratio = float(benchmark["hotspot_ratio"])
    hotspot_pool_size = int(benchmark["hotspot_pool_size"])
    connect_timeout = float(benchmark["connect_timeout_seconds"])
    read_timeout = float(benchmark["read_timeout_seconds"])
    rng = random.Random(args.seed)
    session = requests.Session()
    session.headers.update({"User-Agent": benchmark["user_agent"]})

    if args.output:
        output_path = resolve_project_path(args.output)
        run_dir = output_path.parent
    else:
        # 默认每轮实验都创建独立目录，避免多次运行互相覆盖结果。
        run_dir = resolve_project_path(args.result_dir) if args.result_dir else default_run_dir(
            result_root=result_root,
            args=args,
            requests_per_size=requests_per_size,
            rounds=rounds,
        )
        ensure_directory(run_dir)
        output_path = run_dir / "benchmark.csv"

    run_id = run_dir.name if not args.output else output_path.stem
    records = []

    try:
        for round_index in range(1, rounds + 1):
            for size_label in sorted(rows_by_size, key=lambda label: int(rows_by_size[label][0]["size_bytes"])):
                sequence = build_sequence(
                    objects_for_size=rows_by_size[size_label],
                    mode=args.mode,
                    requests_per_size=requests_per_size,
                    rng=rng,
                    hotspot_ratio=hotspot_ratio,
                    hotspot_pool_size=hotspot_pool_size,
                )
                for request_index, row in enumerate(sequence, start=1):
                    for endpoint_name in endpoint_order(args.endpoint, rng):
                        url = row["s3_url"] if endpoint_name == "s3" else row["cloudfront_url"]
                        # 每条记录都保留完整实验上下文，便于后续按维度切片分析。
                        measurement = measure_request(
                            session=session,
                            url=url,
                            connect_timeout=connect_timeout,
                            read_timeout=read_timeout,
                        )
                        records.append(
                            {
                                "run_id": run_id,
                                "recorded_at_utc": utc_timestamp(),
                                "round_index": round_index,
                                "mode": args.mode,
                                "endpoint": endpoint_name,
                                "cache_profile": row["cache_profile"],
                                "size_label": row["size_label"],
                                "size_bytes": row["size_bytes"],
                                "request_index": request_index,
                                "object_key": row["s3_key"],
                                "url": url,
                                **measurement,
                            }
                        )
                        if sleep_time > 0:
                            time.sleep(sleep_time)
    finally:
        session.close()

    write_csv(output_path, BENCHMARK_FIELDS, records)
    if not args.output:
        metadata_path = run_dir / "metadata.json"
        # 除原始 CSV 外，再单独保存一份元数据，方便结果目录脱离命令行单独查看。
        write_json(
            metadata_path,
            {
                "created_at_utc": utc_timestamp(),
                "run_id": run_id,
                "profile": args.profile,
                "mode": args.mode,
                "endpoint": args.endpoint,
                "size_labels": sorted(allowed_sizes) if allowed_sizes else "all",
                "requests_per_size": requests_per_size,
                "rounds": rounds,
                "seed": args.seed,
                "sleep_seconds": sleep_time,
                "manifest_path": str(manifest_path),
                "benchmark_csv": str(output_path),
            },
        )
        print(f"Run metadata written to {metadata_path}")
    print(f"Wrote {len(records)} measurements to {output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
