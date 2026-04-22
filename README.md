# CS5296 CDN Benchmark

This project measures the performance difference between direct Amazon S3 access and Amazon CloudFront delivery for the same set of static objects.

## Environment

- Region: `us-east-1`
- S3 bucket: `cs5296-cdn-ziang-personal-20260422`
- CloudFront domain: `d1kkjdyyhst5i6.cloudfront.net`

## Repository Layout

```text
main.py
config.json
requirements.txt
README.md
CODE_EXPLANATION_CN.md
ARTIFACT_APPENDIX_EN.md
ARTIFACT_APPENDIX_CN.md
run_all_experiments.sh
scripts/
data/
result/
```

## Install

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## Commands

`main.py` provides these subcommands:

- `generate-files`
- `upload-files`
- `benchmark`
- `analyze`
- `update-visibility`

## Recommended Full Experiment Run

The current repository is prepared for a full batch run with existing uploaded objects.
Before running the batch script, make sure `data/processed/uploaded_objects.csv` already exists and the referenced objects are available in S3 and CloudFront.

Run:

```bash
./run_all_experiments.sh
```

The script performs the following experiments in one batch:

- `baseline + single-hot + both`
- `baseline + hotspot + both`
- `baseline + distributed + both`
- `short_ttl + distributed + cloudfront`
- `long_ttl + distributed + cloudfront`
- `update-visibility`

Each execution creates one batch directory:

```text
result/<timestamp>__full-project-run/
```

Inside the batch directory, each benchmark case gets its own folder with:

- `benchmark.csv`
- `metadata.json`
- `summary.csv`
- `figures/`

The update visibility experiment writes:

- `update_visibility/update_visibility.csv`
- `update_visibility/metadata.json`

## Manual Workflow

If the dataset or uploaded manifest needs to be rebuilt, use the manual commands below.

Generate local test files:

```bash
.venv/bin/python main.py generate-files --overwrite
```

Upload objects to S3:

```bash
.venv/bin/python main.py upload-files
```

Run one benchmark case:

```bash
.venv/bin/python main.py benchmark --endpoint both --mode distributed --profile baseline
```

Analyze one run:

```bash
.venv/bin/python main.py analyze
```

Run only the update visibility experiment:

```bash
.venv/bin/python main.py update-visibility
```

## Dataset and Profiles

The default dataset defined in `config.json` contains:

- `10kb`
- `100kb`
- `1mb`
- `5mb`

The upload profiles are:

- `baseline`
- `short_ttl`
- `long_ttl`

The mutable object used for content update visibility is:

- `mutable/update_test.txt`

## Output Locations

- Local test files: `data/test_files/`
- Local file manifest: `data/processed/local_files.csv`
- Uploaded object manifest: `data/processed/uploaded_objects.csv`
- Experiment results: `result/`

## Result Notes

- `benchmark.csv` stores request-level measurements such as TTFB, total time, throughput, HTTP status, and `X-Cache`.
- `summary.csv` stores grouped statistics such as sample count, success rate, cache hit rate, mean, median, and p95.
- `result/` is ignored by Git, so experiment outputs stay local unless exported separately.
