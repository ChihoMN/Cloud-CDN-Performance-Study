# 当前代码说明

## 1. 项目目标

当前代码实现了一个最小可运行的 CDN 性能实验框架，用来比较同一批静态对象通过以下两条路径访问时的差异：

- `S3 Direct URL`
- `CloudFront URL`

项目的核心目标是：

- 生成不同大小的测试文件
- 上传到同一个 S3 bucket
- 同时对 S3 和 CloudFront 发起请求
- 记录性能数据
- 生成汇总结果和图表

## 2. 当前目录结构

```text
main.py
config.json
requirements.txt
README.md
CODE_EXPLANATION_CN.md
scripts/
  common.py
  generate_files.py
  upload_files.py
  benchmark.py
  analyze.py
data/
  raw/
  processed/
  test_files/
```

说明：

- `main.py`：统一命令入口
- `config.json`：集中管理实验配置
- `scripts/`：核心功能脚本
- `data/test_files/`：本地测试文件
- `data/processed/`：中间 manifest 文件
- `result/`：每轮实验结果目录，运行时自动生成

## 3. 配置文件说明

`config.json` 里已经写入了当前实验环境：

- `region`: `us-east-1`
- `bucket_name`: `cs5296-cdn-ziang-personal-20260422`
- `s3_base_url`: 当前 S3 直连地址前缀
- `cloudfront_domain`: 当前 CloudFront 域名

除此之外，它还定义了：

- 本地测试文件保存位置
- 本地文件 manifest 路径
- 已上传对象 manifest 路径
- 文件大小梯度和每档文件数量
- 上传 profile 和对应的 `Cache-Control`
- benchmark 默认请求次数、轮数、超时和热点比例

## 4. 当前已实现的功能

### 4.1 生成测试文件

脚本：`scripts/generate_files.py`

功能：

- 按配置生成多组随机二进制文件
- 当前默认文件大小为：
  - `10KB`
  - `100KB`
  - `1MB`
  - `5MB`
- 每个大小默认生成 `5` 个文件
- 额外生成一个 `mutable/update_test.txt`，为后续更新可见性实验预留
- 生成本地 manifest：`data/processed/local_files.csv`

### 4.2 上传到 S3

脚本：`scripts/upload_files.py`

功能：

- 读取 `local_files.csv`
- 按 profile 上传到 S3
- 自动写入对象的 `Cache-Control`
- 自动生成 `uploaded_objects.csv`

当前默认 profile：

- `baseline`
- `short_ttl`
- `long_ttl`

每个已上传对象都会记录：

- 文件大小
- 本地路径
- S3 key
- S3 URL
- CloudFront URL
- 缓存 profile

### 4.3 运行基准测试

脚本：`scripts/benchmark.py`

功能：

- 读取 `uploaded_objects.csv`
- 对 S3 / CloudFront / 两者同时发起请求
- 按不同访问模式生成请求序列
- 对每次请求记录详细结果

当前支持的测试端点：

- `s3`
- `cloudfront`
- `both`

当前支持的访问模式：

- `single-hot`
  - 连续请求同一个对象，适合观察 CloudFront 的 Miss 和 Hit
- `hotspot`
  - 大部分请求集中在少数热门对象
- `distributed`
  - 在对象集合中随机访问

### 4.4 结果记录字段

`benchmark.csv` 当前会记录以下主要字段：

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

### 4.5 异常处理

当前 benchmark 对异常请求做了保护：

- 超时不会让程序崩掉
- 请求异常会被捕获
- 错误信息会写入 `error_message`
- 同时保留本次请求对应的时间和基本上下文

### 4.6 结果目录

每次运行 benchmark 时，程序会自动在根目录 `result/` 下创建一个独立文件夹。

目录名会包含：

- 时间戳
- profile
- mode
- endpoint
- size 范围
- 每组请求数
- 轮数

例如：

```text
result/20260422T090000Z__profile-baseline__mode-distributed__endpoint-both__all-sizes__req-20__rounds-3/
```

该目录中默认包含：

- `benchmark.csv`
- `metadata.json`

## 5. 结果分析功能

脚本：`scripts/analyze.py`

功能：

- 读取某一轮或多轮 benchmark 结果
- 按 `mode / cache_profile / endpoint / size` 分组统计
- 生成 `summary.csv`
- 如果环境中安装了 `matplotlib`，则自动画图

当前统计指标包括：

- `sample_count`
- `success_rate`
- `cache_hit_rate`
- `mean / median / p95` 的 `ttfb`
- `mean / median / p95` 的 `total_time`
- `mean_throughput_mib_s`

当前图表包括：

- `Mean TTFB`
- `Mean total time`

## 6. 当前运行流程

### 第一步：生成测试文件

```bash
.venv/bin/python main.py generate-files --overwrite
```

### 第二步：上传到 S3

```bash
.venv/bin/python main.py upload-files
```

### 第三步：执行 benchmark

```bash
.venv/bin/python main.py benchmark --endpoint both --mode distributed --profile baseline
```

### 第四步：生成汇总结果

```bash
.venv/bin/python main.py analyze
```

## 7. 当前代码已经覆盖的实验能力

当前代码已经支持：

- S3 和 CloudFront 双路径对比
- 多文件大小测试
- 多访问模式测试
- 多次重复请求
- Cache Hit / Miss 的间接观测
- 原始结果持久化
- 结果汇总和图表生成

## 8. 当前代码仍未完全实现的部分

以下内容在当前代码中还没有完全展开成独立模块：

- 专门的“内容更新可见性”实验脚本
- 单独的成本估算模块
- 更严格定义的 throughput 计算公式
- 更贴合 proposal 的文件大小梯度（例如 50KB / 500KB / 5MB）

也就是说，当前代码已经完成了实验框架和主流程，但还没有把所有扩展实验都补满。

## 9. 总结

从当前实现来看，这个仓库已经具备一个课程项目所需的核心 artifact 结构：

- 有配置文件
- 有文件生成
- 有对象上传
- 有 benchmark
- 有结果保存
- 有分析脚本
- 有运行文档

它已经可以支持你继续跑正式实验，只是后续还可以根据 proposal 再补一些更细的实验模块。
