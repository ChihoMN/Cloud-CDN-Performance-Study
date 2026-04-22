#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BATCH_DIR="$ROOT_DIR/result/${TIMESTAMP}__full-project-run"

# 主性能实验使用 30 次样本，TTL 和更新可见性实验共用同一批次目录。
REQUESTS_PER_SIZE="${REQUESTS_PER_SIZE:-30}"
ROUNDS="${ROUNDS:-1}"
UPDATE_POLL_INTERVAL="${UPDATE_POLL_INTERVAL:-10}"
UPDATE_POLL_COUNT="${UPDATE_POLL_COUNT:-12}"

mkdir -p "$BATCH_DIR"

echo "Batch result directory: $BATCH_DIR"
echo "Using python: $PYTHON_BIN"

if [[ ! -f "$ROOT_DIR/data/processed/uploaded_objects.csv" ]]; then
  echo "Missing data/processed/uploaded_objects.csv"
  echo "Please prepare the uploaded object manifest first."
  exit 1
fi

run_benchmark() {
  local profile="$1"
  local mode="$2"
  local endpoint="$3"
  local run_dir="$BATCH_DIR/${profile}_${mode}_${endpoint}"

  echo "Running benchmark: profile=$profile mode=$mode endpoint=$endpoint"
  "$PYTHON_BIN" "$ROOT_DIR/main.py" benchmark \
    --profile "$profile" \
    --mode "$mode" \
    --endpoint "$endpoint" \
    --requests-per-size "$REQUESTS_PER_SIZE" \
    --rounds "$ROUNDS" \
    --result-dir "$run_dir"

  "$PYTHON_BIN" "$ROOT_DIR/main.py" analyze --input "$run_dir"
}

# 基线实验：覆盖 Miss/Hit、热点访问和分散访问。
run_benchmark baseline single-hot both
run_benchmark baseline hotspot both
run_benchmark baseline distributed both

# 缓存策略实验：比较短 TTL 和长 TTL 在 CloudFront 上的表现。
run_benchmark short_ttl distributed cloudfront
run_benchmark long_ttl distributed cloudfront

echo "Running update visibility experiment"
"$PYTHON_BIN" "$ROOT_DIR/main.py" update-visibility \
  --poll-interval "$UPDATE_POLL_INTERVAL" \
  --poll-count "$UPDATE_POLL_COUNT" \
  --result-dir "$BATCH_DIR/update_visibility"

echo "All experiments completed."
echo "Results are available under: $BATCH_DIR"
