# Artifact 附录

## 1. Artifact 概述

本仓库包含一个可复现实验 artifact，用于比较同一批静态对象通过 Amazon S3 直连和 Amazon CloudFront 分发时的性能表现。

该 artifact 支持：

- 多文件大小性能测试
- S3 与 CloudFront 路径对比
- Cache Hit 与 Cache Miss 观测
- 短 TTL 与长 TTL 对比
- 内容更新可见性观测

## 2. 仓库信息

- 仓库名称：`Cloud-CDN-Performance-Study`
- 统一入口：`main.py`
- 一键批量脚本：`run_all_experiments.sh`
- 主配置文件：`config.json`

## 3. 运行环境

当前实验环境为：

- AWS Region：`us-east-1`
- S3 bucket：`cs5296-cdn-ziang-personal-20260422`
- CloudFront 域名：`d1kkjdyyhst5i6.cloudfront.net`

该 artifact 设计为在支持 Python 3 和 shell 的 macOS 或 Linux 环境中运行。

## 4. 依赖安装

使用以下命令安装 Python 依赖：

```bash
.venv/bin/python -m pip install -r requirements.txt
```

所需 Python 依赖列在 `requirements.txt` 中。

## 5. 运行前输入条件

在推荐的一键运行流程中，需要提前具备以下条件：

- 已准备好安装依赖的 Python 环境
- 在需要上传对象时，可用的 AWS 凭证
- `data/processed/uploaded_objects.csv`
- `uploaded_objects.csv` 中引用的对象已经上传到 S3，并可正常访问
- 配置中的 CloudFront distribution 已部署完成并可访问

## 6. 主要命令

### 6.1 生成本地测试文件

```bash
.venv/bin/python main.py generate-files --overwrite
```

### 6.2 上传对象

```bash
.venv/bin/python main.py upload-files
```

### 6.3 运行单组 benchmark

```bash
.venv/bin/python main.py benchmark --endpoint both --mode distributed --profile baseline
```

### 6.4 分析单组 benchmark 结果

```bash
.venv/bin/python main.py analyze
```

### 6.5 运行更新可见性实验

```bash
.venv/bin/python main.py update-visibility
```

### 6.6 运行整套实验

```bash
./run_all_experiments.sh
```

## 7. 整套实验覆盖内容

一键脚本会执行以下实验集合：

- `baseline + single-hot + both`
- `baseline + hotspot + both`
- `baseline + distributed + both`
- `short_ttl + distributed + cloudfront`
- `long_ttl + distributed + cloudfront`
- `update-visibility`

该实验集合对应本项目所需的完整数据采集流程。

## 8. 输出结果

主要输出位于：

```text
result/<timestamp>__full-project-run/
```

每个 benchmark 子目录包含：

- `benchmark.csv`
- `metadata.json`
- `summary.csv`
- `figures/`

更新可见性子目录包含：

- `update_visibility.csv`
- `metadata.json`

附加的中间文件位于：

- `data/processed/local_files.csv`
- `data/processed/uploaded_objects.csv`

## 9. 预期实验现象

artifact 正常运行后，结果应体现出以下现象：

- 在重复访问场景下，CloudFront 的 TTFB 低于 S3 直连
- 在 `single-hot` 和 `hotspot` 模式下，CloudFront 具有较高的缓存命中率
- 对较大文件，CloudFront 通常具有更高的吞吐表现
- 对象更新后，CloudFront 会在一段时间内继续返回旧内容，并在 TTL 到期后刷新为新版本

## 10. 附加说明

- `result/` 目录默认被 Git 忽略，因此实验数据默认只保留在本地
- 一键脚本默认假设 `uploaded_objects.csv` 已经存在
- 用于更新可见性实验的对象是 `mutable/update_test.txt`
