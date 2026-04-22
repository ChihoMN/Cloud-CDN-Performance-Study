from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .common import (
    load_config,
    quoted_url,
    read_csv,
    resolve_project_path,
    utc_timestamp,
    write_csv,
)


UPLOADED_MANIFEST_FIELDS = [
    "uploaded_at_utc",
    "cache_profile",
    "cache_control",
    "size_label",
    "size_bytes",
    "file_index",
    "file_name",
    "local_path",
    "s3_key",
    "s3_url",
    "cloudfront_url",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload generated files to S3.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON.")
    parser.add_argument(
        "--profile",
        nargs="+",
        help="Upload only these cache profiles. Defaults to all profiles in the config.",
    )
    parser.add_argument(
        "--skip-mutable",
        action="store_true",
        help="Skip uploading the mutable probe object.",
    )
    return parser


def choose_profiles(config: dict, requested_profiles: list[str] | None) -> list[dict]:
    all_profiles = config["dataset"]["upload_profiles"]
    if not requested_profiles:
        return all_profiles

    requested = set(requested_profiles)
    selected = [profile for profile in all_profiles if profile["name"] in requested]
    if len(selected) != len(requested):
        missing = sorted(requested - {profile["name"] for profile in selected})
        raise ValueError(f"Unknown upload profile(s): {', '.join(missing)}")
    return selected


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def upload_local_file(
    s3_client,
    bucket_name: str,
    local_path: Path,
    key: str,
    cache_control: str,
) -> None:
    extra_args = {
        "CacheControl": cache_control,
        "ContentType": content_type_for(local_path),
    }
    s3_client.upload_file(str(local_path), bucket_name, key, ExtraArgs=extra_args)


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    aws = config["aws"]
    dataset = config["dataset"]
    local_manifest_path = resolve_project_path(dataset["local_manifest"])
    uploaded_manifest_path = resolve_project_path(dataset["uploaded_manifest"])
    selected_profiles = choose_profiles(config, args.profile)

    local_rows = read_csv(local_manifest_path)
    s3_client = boto3.client("s3", region_name=aws["region"])
    selected_names = {profile["name"] for profile in selected_profiles}

    output_rows = []
    try:
        for profile in selected_profiles:
            prefix = profile["prefix"].strip("/")
            cache_control = profile["cache_control"]
            for row in local_rows:
                local_path = resolve_project_path(row["local_path"])
                key = f"{prefix}/{row['size_label']}/{row['file_name']}"
                upload_local_file(
                    s3_client=s3_client,
                    bucket_name=aws["bucket_name"],
                    local_path=local_path,
                    key=key,
                    cache_control=cache_control,
                )
                output_rows.append(
                    {
                        "uploaded_at_utc": utc_timestamp(),
                        "cache_profile": profile["name"],
                        "cache_control": cache_control,
                        "size_label": row["size_label"],
                        "size_bytes": row["size_bytes"],
                        "file_index": row["file_index"],
                        "file_name": row["file_name"],
                        "local_path": row["local_path"],
                        "s3_key": key,
                        "s3_url": quoted_url(aws["s3_base_url"], key),
                        "cloudfront_url": quoted_url(
                            f"https://{aws['cloudfront_domain']}",
                            key,
                        ),
                    }
                )

        if not args.skip_mutable:
            mutable = dataset["mutable_object"]
            mutable_path = resolve_project_path(mutable["local_path"])
            upload_local_file(
                s3_client=s3_client,
                bucket_name=aws["bucket_name"],
                local_path=mutable_path,
                key=mutable["key"],
                cache_control=mutable["cache_control"],
            )

    except (NoCredentialsError, BotoCoreError, ClientError) as error:
        print("Upload failed.")
        print(
            "Make sure your local environment has valid AWS credentials for the "
            f"{aws['bucket_name']} bucket."
        )
        print(f"Error: {error}")
        return 1

    existing_rows = []
    if uploaded_manifest_path.exists():
        existing_rows = [
            row for row in read_csv(uploaded_manifest_path)
            if row["cache_profile"] not in selected_names
        ]

    write_csv(uploaded_manifest_path, UPLOADED_MANIFEST_FIELDS, existing_rows + output_rows)
    print(f"Uploaded {len(output_rows)} benchmark objects to s3://{aws['bucket_name']}")
    print(f"Uploaded manifest written to {uploaded_manifest_path}")
    if not args.skip_mutable:
        print(f"Mutable probe refreshed at s3://{aws['bucket_name']}/{dataset['mutable_object']['key']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
