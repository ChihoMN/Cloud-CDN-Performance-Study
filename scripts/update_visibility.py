from __future__ import annotations

import argparse
import hashlib
import time

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .common import ensure_directory, load_config, quoted_url, resolve_project_path, timestamp_slug, utc_timestamp, write_csv, write_json


UPDATE_FIELDS = [
    "recorded_at_utc",
    "phase",
    "poll_index",
    "endpoint",
    "url",
    "status_code",
    "success",
    "ttfb_ms",
    "total_time_ms",
    "x_cache",
    "age_header",
    "observed_version",
    "body_sha256",
    "body_preview",
    "error_message",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Observe S3 and CloudFront update visibility for one mutable object.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON.")
    parser.add_argument(
        "--result-dir",
        default=None,
        help="Optional result directory. Defaults to result/<timestamp>__update-visibility/",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Seconds between polls after the object is updated.",
    )
    parser.add_argument(
        "--poll-count",
        type=int,
        default=12,
        help="How many polls to perform after the object is updated.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=10.0,
        help="HTTP connect timeout in seconds.",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=60.0,
        help="HTTP read timeout in seconds.",
    )
    return parser


def default_result_dir(config: dict) -> str:
    result_root = resolve_project_path(config["benchmark"]["result_root"])
    return str(result_root / f"{timestamp_slug()}__update-visibility")


def build_body(version_label: str) -> bytes:
    return (
        f"version={version_label}\n"
        f"generated_at_utc={utc_timestamp()}\n"
    ).encode("utf-8")


def upload_bytes(s3_client, bucket_name: str, key: str, body: bytes, cache_control: str) -> None:
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=body,
        CacheControl=cache_control,
        ContentType="text/plain; charset=utf-8",
    )


def extract_version(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("version="):
            return line.split("=", 1)[1]
    return ""


def fetch_text(session: requests.Session, url: str, connect_timeout: float, read_timeout: float) -> dict:
    start = time.perf_counter()
    body_chunks: list[bytes] = []
    try:
        response = session.get(url, stream=True, timeout=(connect_timeout, read_timeout))
        header_time = time.perf_counter()
        first_chunk_time = None
        for chunk in response.iter_content(chunk_size=4096):
            if not chunk:
                continue
            if first_chunk_time is None:
                first_chunk_time = time.perf_counter()
            body_chunks.append(chunk)
        end = time.perf_counter()
        response.close()

        body = b"".join(body_chunks)
        text = body.decode("utf-8", errors="replace")
        return {
            "status_code": response.status_code,
            "success": 1 if 200 <= response.status_code < 400 else 0,
            "ttfb_ms": round(((first_chunk_time or header_time) - start) * 1000, 3),
            "total_time_ms": round((end - start) * 1000, 3),
            "x_cache": response.headers.get("X-Cache", ""),
            "age_header": response.headers.get("Age", ""),
            "observed_version": extract_version(text),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "body_preview": text[:120].replace("\n", "\\n"),
            "error_message": "",
        }
    except requests.RequestException as error:
        end = time.perf_counter()
        return {
            "status_code": "",
            "success": 0,
            "ttfb_ms": "",
            "total_time_ms": round((end - start) * 1000, 3),
            "x_cache": "",
            "age_header": "",
            "observed_version": "",
            "body_sha256": "",
            "body_preview": "",
            "error_message": str(error),
        }


def record_pair(records: list[dict], session: requests.Session, phase: str, poll_index: int, s3_url: str, cloudfront_url: str, connect_timeout: float, read_timeout: float) -> None:
    for endpoint, url in [("s3", s3_url), ("cloudfront", cloudfront_url)]:
        measurement = fetch_text(session, url, connect_timeout=connect_timeout, read_timeout=read_timeout)
        records.append(
            {
                "recorded_at_utc": utc_timestamp(),
                "phase": phase,
                "poll_index": poll_index,
                "endpoint": endpoint,
                "url": url,
                **measurement,
            }
        )


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    aws = config["aws"]
    mutable = config["dataset"]["mutable_object"]
    result_dir = resolve_project_path(args.result_dir or default_result_dir(config))
    ensure_directory(result_dir)

    s3_url = quoted_url(aws["s3_base_url"], mutable["key"])
    cloudfront_url = quoted_url(f"https://{aws['cloudfront_domain']}", mutable["key"])
    session = requests.Session()
    session.headers.update({"User-Agent": config["benchmark"]["user_agent"]})
    s3_client = boto3.client("s3", region_name=aws["region"])

    records: list[dict] = []
    old_version = f"old-{timestamp_slug()}"
    new_version = f"new-{timestamp_slug()}"

    try:
        upload_bytes(
            s3_client=s3_client,
            bucket_name=aws["bucket_name"],
            key=mutable["key"],
            body=build_body(old_version),
            cache_control=mutable["cache_control"],
        )
        time.sleep(2)
        # 先访问旧版本，确保 CloudFront 已缓存旧内容。
        record_pair(
            records=records,
            session=session,
            phase="prime_old_version",
            poll_index=0,
            s3_url=s3_url,
            cloudfront_url=cloudfront_url,
            connect_timeout=args.connect_timeout,
            read_timeout=args.read_timeout,
        )

        upload_bytes(
            s3_client=s3_client,
            bucket_name=aws["bucket_name"],
            key=mutable["key"],
            body=build_body(new_version),
            cache_control=mutable["cache_control"],
        )

        for poll_index in range(1, args.poll_count + 1):
            record_pair(
                records=records,
                session=session,
                phase="after_update_poll",
                poll_index=poll_index,
                s3_url=s3_url,
                cloudfront_url=cloudfront_url,
                connect_timeout=args.connect_timeout,
                read_timeout=args.read_timeout,
            )
            if poll_index < args.poll_count:
                time.sleep(args.poll_interval)

    except (NoCredentialsError, BotoCoreError, ClientError) as error:
        print("Update visibility experiment failed while talking to AWS.")
        print(f"Error: {error}")
        return 1
    finally:
        session.close()

    output_csv = result_dir / "update_visibility.csv"
    write_csv(output_csv, UPDATE_FIELDS, records)
    write_json(
        result_dir / "metadata.json",
        {
            "created_at_utc": utc_timestamp(),
            "experiment": "update_visibility",
            "bucket_name": aws["bucket_name"],
            "s3_url": s3_url,
            "cloudfront_url": cloudfront_url,
            "mutable_key": mutable["key"],
            "cache_control": mutable["cache_control"],
            "poll_interval_seconds": args.poll_interval,
            "poll_count": args.poll_count,
            "old_version": old_version,
            "new_version": new_version,
            "output_csv": str(output_csv),
        },
    )
    print(f"Update visibility data written to {output_csv}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
