from __future__ import annotations

import argparse
import os
from pathlib import Path

from .common import ensure_directory, load_config, resolve_project_path, utc_timestamp, write_csv


LOCAL_MANIFEST_FIELDS = [
    "local_path",
    "size_label",
    "size_bytes",
    "file_index",
    "file_name",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate local test files for CDN experiments.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing test files if they already exist.",
    )
    return parser


def write_random_file(path: Path, size_bytes: int, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        return
    ensure_directory(path.parent)
    chunk_size = 1024 * 1024
    remaining = size_bytes
    with path.open("wb") as handle:
        while remaining > 0:
            next_chunk = min(chunk_size, remaining)
            handle.write(os.urandom(next_chunk))
            remaining -= next_chunk


def write_mutable_probe(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        return
    ensure_directory(path.parent)
    path.write_text(
        "This object is used for update-visibility tests.\n"
        f"Generated at: {utc_timestamp()}\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    dataset = config["dataset"]
    local_root = resolve_project_path(dataset["local_root"])
    manifest_path = resolve_project_path(dataset["local_manifest"])
    mutable_path = resolve_project_path(dataset["mutable_object"]["local_path"])

    ensure_directory(local_root)

    rows = []
    for file_set in dataset["file_sets"]:
        size_label = file_set["label"]
        size_bytes = int(file_set["size_bytes"])
        count = int(file_set["count"])
        for index in range(1, count + 1):
            file_name = f"file_{index:02d}.bin"
            local_path = local_root / size_label / file_name
            write_random_file(local_path, size_bytes, overwrite=args.overwrite)
            rows.append(
                {
                    "local_path": str(local_path.relative_to(resolve_project_path("."))),
                    "size_label": size_label,
                    "size_bytes": size_bytes,
                    "file_index": index,
                    "file_name": file_name,
                }
            )

    write_mutable_probe(mutable_path, overwrite=args.overwrite)
    write_csv(manifest_path, LOCAL_MANIFEST_FIELDS, rows)

    print(f"Generated {len(rows)} test files under {local_root}")
    print(f"Local manifest written to {manifest_path}")
    print(f"Mutable probe written to {mutable_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
