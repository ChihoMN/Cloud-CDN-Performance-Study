import requests
import time


def measure_performance(url):
    start_time = time.perf_counter()
    response = requests.get(url, stream=True)

    # 采集 TTFB (Time to First Byte)
    ttfb = time.perf_counter() - start_time

    # 下载整个文件
    content = response.content
    total_time = time.perf_counter() - start_time

    return {
        "status": response.status_code,
        "ttfb": ttfb,
        "total_time": total_time,
        "hit_status": response.headers.get('X-Cache', 'N/A')  # CloudFront 命中状态
    }

# 示例：对比 S3 和 CloudFront
# res_s3 = measure_performance("https://your-bucket.s3.amazonaws.com/test.jpg")
# res_cf = measure_performance("https://your-dist.cloudfront.net/test.jpg")