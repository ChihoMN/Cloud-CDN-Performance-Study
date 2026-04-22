# 代码说明

## 1. 文档目的

本文档用于说明当前仓库中的代码结构、配置方式、脚本职责、运行流程以及实验结果的组织方式。

## 2. 项目概览

当前项目实现了一个基于 Amazon S3 和 Amazon CloudFront 的实验框架，用于比较同一批静态对象通过以下两条路径访问时的性能表现：

- `S3 Direct URL`
- `CloudFront URL`

当前代码覆盖的实验流程包括：

1. 生成测试文件
2. 上传对象到 S3
3. 运行基准测试
4. 汇总统计结果并生成图表
5. 运行内容更新可见性实验
6. 通过一键脚本批量执行整套实验

## 3. 根目录结构

当前根目录中与代码和运行流程直接相关的主要文件如下：

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

各部分含义如下：

- `main.py`：统一命令入口
- `config.json`：实验配置文件
- `requirements.txt`：Python 依赖列表
- `README.md`：英文运行说明
- `CODE_EXPLANATION_CN.md`：中文代码说明
- `ARTIFACT_APPENDIX_EN.md`：英文 artifact appendix
- `ARTIFACT_APPENDIX_CN.md`：中文 artifact appendix
- `run_all_experiments.sh`：一键批量实验脚本
- `scripts/`：核心脚本目录
- `data/`：测试文件与中间 manifest 目录
- `result/`：实验结果输出目录

## 4. 入口文件说明

入口文件是 [main.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/main.py:1)。

该文件不直接执行实验逻辑，而是根据命令行参数把任务分发到不同脚本。当前支持的子命令包括：

- `generate-files`
- `upload-files`
- `benchmark`
- `analyze`
- `update-visibility`

项目的基本调用形式为：

```bash
python main.py <command> [options]
```

## 5. 配置文件说明

配置文件是 [config.json](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/config.json:1)。

### 5.1 AWS 配置

配置文件中记录了当前实验环境：

- `region`
- `bucket_name`
- `s3_base_url`
- `cloudfront_domain`

这些字段决定了脚本访问的 S3 bucket 和 CloudFront 分发地址。

### 5.2 数据集配置

`dataset` 部分定义了：

- 本地测试文件根目录
- 本地文件 manifest 路径
- 已上传对象 manifest 路径
- 文件大小集合
- 每种大小生成的文件数量
- 上传 profile
- 用于更新可见性实验的 `mutable_object`

当前默认文件大小包括：

- `10KB`
- `100KB`
- `1MB`
- `5MB`

### 5.3 Benchmark 配置

`benchmark` 部分定义了：

- `result_root`
- 默认每组请求数
- 默认轮数
- 连接超时
- 读取超时
- 请求间隔
- 热点访问比例
- 热点对象池大小
- User-Agent

这些字段决定了 benchmark 和结果目录的默认行为。

## 6. 一键实验脚本

根目录脚本是 [run_all_experiments.sh](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/run_all_experiments.sh:1)。

该脚本用于在现有 `uploaded_objects.csv` 基础上批量执行完整实验集。脚本不会重新生成测试文件，也不会重新上传对象，而是直接使用已经准备好的对象清单。

脚本会创建一个批次目录：

```text
result/<timestamp>__full-project-run/
```

随后按顺序执行以下实验：

- `baseline + single-hot + both`
- `baseline + hotspot + both`
- `baseline + distributed + both`
- `short_ttl + distributed + cloudfront`
- `long_ttl + distributed + cloudfront`
- `update-visibility`

每个 benchmark 子实验结束后，脚本会自动调用 `analyze` 生成汇总和图表。

## 7. scripts 目录说明

当前 `scripts/` 目录包含以下文件：

- `common.py`
- `generate_files.py`
- `upload_files.py`
- `benchmark.py`
- `analyze.py`
- `update_visibility.py`

### 7.1 common.py

[scripts/common.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/common.py:1) 提供多个脚本共享的基础函数，包括：

- 读取配置
- 解析项目相对路径
- 创建目录
- 生成 UTC 时间戳
- 生成实验目录名片段
- 读写 CSV
- 写 JSON
- 拼接访问 URL

### 7.2 generate_files.py

[scripts/generate_files.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/generate_files.py:1) 用于生成本地测试文件。

主要输出包括：

- 各尺寸测试文件
- `data/processed/local_files.csv`
- `data/test_files/mutable/update_test.txt`

### 7.3 upload_files.py

[scripts/upload_files.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/upload_files.py:1) 用于将本地测试文件上传到 S3。

该脚本会：

- 读取 `local_files.csv`
- 按 `baseline`、`short_ttl`、`long_ttl` 三组 profile 上传对象
- 为对象写入对应的 `Cache-Control`
- 生成 `data/processed/uploaded_objects.csv`

### 7.4 benchmark.py

[scripts/benchmark.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/benchmark.py:1) 是项目中的核心性能测试脚本。

它负责：

- 读取 `uploaded_objects.csv`
- 按 profile、访问模式和端点挑选对象
- 生成请求顺序
- 对 S3 或 CloudFront 发起请求
- 记录每次请求的详细结果
- 将原始结果写入独立实验目录

支持的端点包括：

- `s3`
- `cloudfront`
- `both`

支持的访问模式包括：

- `single-hot`
- `hotspot`
- `distributed`

每轮 benchmark 目录中会写入：

- `benchmark.csv`
- `metadata.json`

### 7.5 analyze.py

[scripts/analyze.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/analyze.py:1) 用于对 benchmark 结果进行统计汇总。

该脚本会输出：

- `summary.csv`
- `figures/`

当前汇总字段包括：

- `sample_count`
- `success_rate`
- `cache_hit_rate`
- `mean_ttfb_ms`
- `median_ttfb_ms`
- `p95_ttfb_ms`
- `mean_total_time_ms`
- `median_total_time_ms`
- `p95_total_time_ms`
- `mean_throughput_mib_s`

### 7.6 update_visibility.py

[scripts/update_visibility.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/update_visibility.py:1) 用于观察同一个可变对象在更新前后，S3 和 CloudFront 分别何时看到新版本。

该脚本会：

- 向同一个 key 写入旧版本内容
- 先访问一次 S3 和 CloudFront，使 CloudFront 缓存旧版本
- 用新版本覆盖同一个对象
- 按固定时间间隔轮询 S3 和 CloudFront
- 记录每次轮询看到的版本、`X-Cache`、`Age`、状态码和延迟

输出文件包括：

- `update_visibility.csv`
- `metadata.json`

## 8. data 目录说明

`data/` 目录用于保存测试文件和中间 manifest。

### 8.1 data/test_files

该目录保存本地生成的测试文件，按尺寸分类组织，例如：

- `10kb/`
- `100kb/`
- `1mb/`
- `5mb/`
- `mutable/`

### 8.2 data/processed

该目录保存中间 manifest 文件，包括：

- `local_files.csv`
- `uploaded_objects.csv`

### 8.3 data/raw

该目录保留为原始结果类文件的扩展目录。当前主要实验结果默认写入 `result/`。

## 9. 运行流程说明

### 9.1 推荐运行方式

如果 `uploaded_objects.csv` 已存在，并且对应对象已经上传到 S3，推荐直接运行：

```bash
./run_all_experiments.sh
```

执行后会在一个批次目录下得到整套实验结果。

### 9.2 手动生成测试文件

```bash
.venv/bin/python main.py generate-files --overwrite
```

### 9.3 手动上传对象

```bash
.venv/bin/python main.py upload-files
```

### 9.4 手动执行单组 benchmark

```bash
.venv/bin/python main.py benchmark --endpoint both --mode distributed --profile baseline
```

### 9.5 手动执行汇总分析

```bash
.venv/bin/python main.py analyze
```

### 9.6 手动执行更新可见性实验

```bash
.venv/bin/python main.py update-visibility
```

## 10. 实验结果组织方式

当前代码中的结果分为两级：

第一层是批次目录，例如：

```text
result/20260422T101533Z__full-project-run/
```

第二层是批次目录下的各实验子目录，例如：

- `baseline_single-hot_both/`
- `baseline_hotspot_both/`
- `baseline_distributed_both/`
- `short_ttl_distributed_cloudfront/`
- `long_ttl_distributed_cloudfront/`
- `update_visibility/`

其中：

- benchmark 子目录中包含 `benchmark.csv`、`metadata.json`、`summary.csv` 和 `figures/`
- 更新可见性子目录中包含 `update_visibility.csv` 和 `metadata.json`

## 11. 输出结果说明

当前代码的输出结果主要分为三类：

### 11.1 中间数据

- `local_files.csv`
- `uploaded_objects.csv`

### 11.2 原始实验结果

- `benchmark.csv`
- `update_visibility.csv`

### 11.3 汇总结果

- `summary.csv`
- 图表文件

## 12. 总结

当前代码由统一入口、集中配置、测试文件生成、对象上传、基准测试、统计分析、更新可见性实验和一键批量运行脚本组成。整个项目通过 `main.py` 协调不同命令，通过 `config.json` 管理实验参数，并通过 `result/` 目录组织每一轮实验输出。
