# Artifact Appendix

## 1. Artifact Overview

This repository contains a reproducible experiment artifact for comparing direct Amazon S3 access with Amazon CloudFront delivery for static content.

The artifact supports:

- multi-size file benchmarking
- S3 and CloudFront path comparison
- cache hit and cache miss observation
- short TTL and long TTL comparison
- content update visibility observation

## 2. Repository Information

- Repository: `Cloud-CDN-Performance-Study`
- Entry point: `main.py`
- Full batch script: `run_all_experiments.sh`
- Main configuration file: `config.json`

## 3. Runtime Environment

The current experiment environment is:

- AWS Region: `us-east-1`
- S3 bucket: `cs5296-cdn-ziang-personal-20260422`
- CloudFront domain: `d1kkjdyyhst5i6.cloudfront.net`

The artifact is designed to run on macOS or Linux with Python 3 and shell support.

## 4. Dependencies

Install Python dependencies with:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

The Python dependencies are listed in `requirements.txt`.

## 5. Required Inputs

The artifact expects the following inputs to exist before the recommended full run:

- local Python environment with installed dependencies
- valid AWS credentials for S3 access when upload-related commands are used
- `data/processed/uploaded_objects.csv`
- the referenced S3 objects already uploaded and accessible
- the configured CloudFront distribution already deployed and reachable

## 6. Main Commands

### 6.1 Prepare local files

```bash
.venv/bin/python main.py generate-files --overwrite
```

### 6.2 Upload objects

```bash
.venv/bin/python main.py upload-files
```

### 6.3 Run one benchmark case

```bash
.venv/bin/python main.py benchmark --endpoint both --mode distributed --profile baseline
```

### 6.4 Analyze one benchmark run

```bash
.venv/bin/python main.py analyze
```

### 6.5 Run the update visibility experiment

```bash
.venv/bin/python main.py update-visibility
```

### 6.6 Run the complete experiment batch

```bash
./run_all_experiments.sh
```

## 7. Full Experiment Coverage

The batch script runs the following experiment set:

- `baseline + single-hot + both`
- `baseline + hotspot + both`
- `baseline + distributed + both`
- `short_ttl + distributed + cloudfront`
- `long_ttl + distributed + cloudfront`
- `update-visibility`

This set collects the full dataset used by the project.

## 8. Outputs

The main outputs are stored under:

```text
result/<timestamp>__full-project-run/
```

Each benchmark subdirectory contains:

- `benchmark.csv`
- `metadata.json`
- `summary.csv`
- `figures/`

The update visibility subdirectory contains:

- `update_visibility.csv`
- `metadata.json`

Additional intermediate files are stored under:

- `data/processed/local_files.csv`
- `data/processed/uploaded_objects.csv`

## 9. Expected Observations

When the artifact runs successfully, the results should show:

- lower TTFB for CloudFront than direct S3 in repeated-access cases
- higher cache hit rate for CloudFront in `single-hot` and `hotspot` modes
- stronger throughput benefit for larger files under CloudFront
- stale content served by CloudFront for a short period after an object update, followed by refresh after TTL expiry

## 10. Notes

- The `result/` directory is ignored by Git and remains local by default.
- The batch script assumes the uploaded object manifest already exists.
- The mutable object used for update visibility is `mutable/update_test.txt`.
