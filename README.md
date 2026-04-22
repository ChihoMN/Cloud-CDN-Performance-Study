# CS5296 CDN Benchmark

Minimal experiment scaffold for comparing direct S3 access against Amazon CloudFront.

## Environment

- Region: `us-east-1`
- S3 bucket: `cs5296-cdn-ziang-personal-20260422`
- CloudFront domain: `d1kkjdyyhst5i6.cloudfront.net`

## Install

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## Workflow

1. Generate local files:

```bash
.venv/bin/python main.py generate-files --overwrite
```

2. Upload objects to S3.
This step needs local AWS credentials that can write to the bucket.

```bash
.venv/bin/python main.py upload-files
```

3. Run a benchmark.
Example: compare S3 and CloudFront for the `baseline` profile using the distributed access pattern.

```bash
.venv/bin/python main.py benchmark --endpoint both --mode distributed --profile baseline
```

Each benchmark run creates a separate folder under `result/`.
The folder name includes the timestamp and experiment parameters, for example:

```text
result/20260422T090000Z__profile-baseline__mode-distributed__endpoint-both__all-sizes__req-20__rounds-3/
```

Inside each run folder you will get:

- `benchmark.csv`
- `metadata.json`
- `summary.csv` after analysis
- `figures/` after analysis

4. Summarize results and generate plots:

```bash
.venv/bin/python main.py analyze
```

## Output Locations

- Local test files: `data/test_files/`
- Uploaded object manifest: `data/processed/uploaded_objects.csv`
- Experiment run folders: `result/`

## Experiment Notes

- Upload profiles in `config.json` map to different `Cache-Control` headers.
- `baseline`, `short_ttl`, and `long_ttl` are ready for later cache-policy experiments.
- `data/test_files/mutable/update_test.txt` is reserved for content update visibility tests.
