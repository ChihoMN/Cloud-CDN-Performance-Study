# 代码说明

## 1. 文档目的

本文档用于说明当前仓库中的代码结构、配置方式、运行流程以及各个脚本的职责，帮助阅读者快速理解整个实验框架的组成。

## 2. 项目概览

当前项目实现了一个基于 Amazon S3 和 Amazon CloudFront 的实验框架，用于比较同一批静态对象通过以下两条访问路径时的性能表现：

- `S3 Direct URL`
- `CloudFront URL`

整套代码围绕以下流程组织：

1. 生成测试文件
2. 上传对象到 S3
3. 运行基准测试
4. 汇总实验结果
5. 输出图表和统计信息

## 3. 根目录结构

当前根目录中与代码相关的主要文件如下：

```text
main.py
config.json
requirements.txt
README.md
CODE_EXPLANATION_CN.md
scripts/
data/
```

各部分含义如下：

- `main.py`：统一命令入口
- `config.json`：实验配置文件
- `requirements.txt`：Python 依赖列表
- `README.md`：英文运行说明
- `CODE_EXPLANATION_CN.md`：中文代码说明文档
- `scripts/`：核心脚本目录
- `data/`：本地测试文件和中间数据目录

## 4. 入口文件说明

入口文件是 [main.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/main.py:1)。

该文件不直接执行实验逻辑，而是根据命令行参数把任务分发给不同脚本。当前支持的子命令包括：

- `generate-files`
- `upload-files`
- `benchmark`
- `analyze`

因此，整个项目的调用方式是：

```bash
python main.py <command> [options]
```

## 5. 配置文件说明

配置文件是 [config.json](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/config.json:1)。

### 5.1 AWS 相关配置

配置文件中记录了当前实验环境：

- `region`
- `bucket_name`
- `s3_base_url`
- `cloudfront_domain`

这些字段决定了脚本如何定位当前实验所使用的 S3 bucket 和 CloudFront 分发地址。

### 5.2 数据集配置

`dataset` 部分定义了：

- 本地测试文件根目录
- 本地文件 manifest 路径
- 已上传对象 manifest 路径
- 文件大小梯度
- 每种大小生成的文件数量
- 上传 profile
- `mutable_object`

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
- 自定义 User-Agent

这些参数决定了 benchmark 的默认行为。

## 6. scripts 目录说明

当前 `scripts/` 目录包含以下文件：

- `common.py`
- `generate_files.py`
- `upload_files.py`
- `benchmark.py`
- `analyze.py`

### 6.1 common.py

[scripts/common.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/common.py:1) 提供多个脚本共享的基础函数，包括：

- 读取配置
- 解析项目相对路径
- 创建目录
- 生成 UTC 时间戳
- 生成适合目录名的参数字符串
- 读写 CSV
- 写 JSON
- 生成 URL

这个文件主要用于减少重复代码，使其余脚本保持统一的路径和输出风格。

### 6.2 generate_files.py

[scripts/generate_files.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/generate_files.py:1) 用于生成本地测试文件。

其主要功能包括：

- 根据 `config.json` 中定义的文件大小批量生成随机二进制文件
- 按大小分类保存到 `data/test_files/`
- 生成本地文件清单 `local_files.csv`
- 生成一个 `mutable/update_test.txt`

该脚本输出的 `local_files.csv` 是后续上传步骤的输入。

### 6.3 upload_files.py

[scripts/upload_files.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/upload_files.py:1) 用于将本地测试文件上传到 S3。

其主要功能包括：

- 读取 `local_files.csv`
- 根据不同 `upload_profiles` 上传对象
- 为对象写入对应的 `Cache-Control`
- 生成 `uploaded_objects.csv`

`uploaded_objects.csv` 中记录了每个对象的：

- 文件大小
- 文件名
- 本地路径
- S3 key
- S3 URL
- CloudFront URL
- 缓存 profile

这个文件是 benchmark 的直接输入。

### 6.4 benchmark.py

[scripts/benchmark.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/benchmark.py:1) 是项目中的核心测试脚本。

它的主要职责是：

- 读取 `uploaded_objects.csv`
- 按实验参数挑选对象
- 生成访问序列
- 对 S3 和 CloudFront 发起请求
- 记录每次请求的详细结果
- 将结果保存到独立实验目录

#### 支持的端点

- `s3`
- `cloudfront`
- `both`

#### 支持的访问模式

- `single-hot`
- `hotspot`
- `distributed`

#### 记录的主要字段

每次请求会写入 `benchmark.csv`，主要字段包括：

- `run_id`
- `recorded_at_utc`
- `round_index`
- `mode`
- `endpoint`
- `cache_profile`
- `size_label`
- `size_bytes`
- `request_index`
- `object_key`
- `url`
- `status_code`
- `success`
- `ttfb_ms`
- `total_time_ms`
- `bytes_read`
- `throughput_mib_s`
- `x_cache`
- `age_header`
- `error_message`

#### 实验结果目录

每次运行 benchmark 时，程序会在根目录 `result/` 下创建独立实验目录。

目录名由以下信息组成：

- 时间戳
- profile
- mode
- endpoint
- 文件大小范围
- 每组请求数
- 轮数

目录中默认会生成：

- `benchmark.csv`
- `metadata.json`

### 6.5 analyze.py

[scripts/analyze.py](/Users/cza/Documents/CS5296_CC/project/CS5296_Project/scripts/analyze.py:1) 用于对 benchmark 结果进行汇总分析。

它的主要功能包括：

- 读取一轮或多轮实验结果
- 按固定维度进行分组统计
- 输出 `summary.csv`
- 输出图表

分组维度为：

- `mode`
- `cache_profile`
- `endpoint`
- `size_label`
- `size_bytes`

当前汇总统计包括：

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

如果环境中安装了 `matplotlib`，脚本会自动生成柱状图，图表输出到实验目录下的 `figures/`。

## 7. data 目录说明

`data/` 目录用于保存本地测试文件和中间数据。

### 7.1 data/test_files

该目录保存本地生成的测试文件，按尺寸分类组织，例如：

- `10kb/`
- `100kb/`
- `1mb/`
- `5mb/`
- `mutable/`

### 7.2 data/processed

该目录保存中间 manifest 文件，包括：

- `local_files.csv`
- `uploaded_objects.csv`

### 7.3 data/raw

该目录预留给原始结果类文件使用。

## 8. 运行流程说明

### 8.1 生成测试文件

```bash
.venv/bin/python main.py generate-files --overwrite
```

执行后将生成：

- 本地测试文件
- `data/processed/local_files.csv`

### 8.2 上传对象到 S3

```bash
.venv/bin/python main.py upload-files
```

执行后将生成：

- `data/processed/uploaded_objects.csv`

### 8.3 执行 benchmark

示例：

```bash
.venv/bin/python main.py benchmark --endpoint both --mode distributed --profile baseline
```

执行后将在 `result/` 下生成一轮独立实验目录，并写入：

- `benchmark.csv`
- `metadata.json`

### 8.4 执行分析

```bash
.venv/bin/python main.py analyze
```

执行后会在结果目录中生成：

- `summary.csv`
- `figures/`

## 9. 当前代码中的实验组织方式

当前代码按照以下实验维度组织测试：

- 访问路径：`S3`、`CloudFront`
- 文件大小：多档尺寸
- 缓存 profile：`baseline`、`short_ttl`、`long_ttl`
- 访问模式：`single-hot`、`hotspot`、`distributed`
- 请求轮数与每组样本量：由配置和命令行参数共同决定

所有实验结果均以目录的形式进行区分和保存，每轮实验目录中包含原始数据、元数据、汇总结果与图表。

## 10. 输出结果说明

当前代码的输出结果主要分为三类：

### 10.1 中间数据

- `local_files.csv`
- `uploaded_objects.csv`

### 10.2 原始实验结果

- `benchmark.csv`

### 10.3 汇总结果

- `summary.csv`
- 图表文件

这些文件共同组成当前实验代码的完整输出。

## 11. 总结

当前代码由统一入口、集中配置、文件生成、对象上传、基准测试和结果分析几个部分组成。  
整个项目通过 `main.py` 协调不同脚本，利用 `config.json` 管理实验参数，并通过 `result/` 目录组织每轮实验的输出结果。
