#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
资源下载工具 - 下载生成HTML报告所需的CSS、JS和字体资源
"""

import os
import sys
import time
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional


# 配置日志输出
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# 资源列表
RESOURCES = [
    {
        "name": "Bootstrap CSS",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css",
        "local_path": "css/bootstrap.min.css"
    },
    {
        "name": "Bootstrap JS",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js",
        "local_path": "js/bootstrap.bundle.min.js"
    },
    {
        "name": "Bootstrap Icons CSS",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.3/font/bootstrap-icons.css",
        "local_path": "css/bootstrap-icons.css"
    },
    {
        "name": "Bootstrap Icons Font (WOFF)",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.3/font/fonts/bootstrap-icons.woff",
        "local_path": "css/fonts/bootstrap-icons.woff"
    },
    {
        "name": "Bootstrap Icons Font (WOFF2)",
        "url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.3/font/fonts/bootstrap-icons.woff2",
        "local_path": "css/fonts/bootstrap-icons.woff2"
    },
    {
        "name": "Highlight.js",
        "url": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js",
        "local_path": "js/highlight.min.js"
    },
    {
        "name": "Highlight.js CSS (Github Theme)",
        "url": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css",
        "local_path": "css/highlight.min.css"
    }
]


def download_file(url: str, destination: Path, timeout: int = 30) -> bool:
    """
    下载文件并保存到指定位置
    
    Args:
        url: 文件URL
        destination: 保存路径
        timeout: 超时时间（秒）
        
    Returns:
        bool: 下载是否成功
    """
    logger.info(f"下载文件: {url}")
    try:
        # 创建目标目录（如果不存在）
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # 下载文件
        start_time = time.time()
        
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()  # 如果请求失败则抛出异常
        
        # 获取文件大小
        file_size = int(response.headers.get('Content-Length', 0))
        
        # 写入文件
        with open(destination, 'wb') as f:
            if file_size:
                chunk_size = 8192
                chunks = 0
                total_chunks = file_size // chunk_size + 1
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                    chunks += 1
                    # 打印进度
                    if chunks % 10 == 0:
                        progress = (chunks / total_chunks) * 100
                        logger.debug(f"下载进度: {progress:.1f}%")
            else:
                f.write(response.content)
        
        # 计算下载时间和速度
        elapsed_time = time.time() - start_time
        file_size_mb = os.path.getsize(destination) / (1024 * 1024)
        download_speed = file_size_mb / elapsed_time if elapsed_time > 0 else 0
        
        logger.info(f"下载完成: {destination.name} ({file_size_mb:.2f}MB, {download_speed:.2f}MB/s)")
        return True
        
    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        if destination.exists():
            destination.unlink()  # 删除不完整的文件
        return False


def download_all_resources(target_dir: Path, retries: int = 3) -> bool:
    """
    下载所有资源文件
    
    Args:
        target_dir: 目标目录
        retries: 重试次数
        
    Returns:
        bool: 是否全部下载成功
    """
    logger.info(f"开始下载资源文件到: {target_dir}")
    
    success_count = 0
    failed_resources = []
    
    for resource in RESOURCES:
        name = resource["name"]
        url = resource["url"]
        local_path = resource["local_path"]
        destination = target_dir / local_path
        
        # 检查文件是否已存在
        if destination.exists():
            logger.info(f"资源已存在，跳过: {name} ({local_path})")
            success_count += 1
            continue
        
        # 下载文件，带重试
        success = False
        for attempt in range(retries):
            if attempt > 0:
                logger.info(f"重试下载 ({attempt+1}/{retries}): {name}")
            
            if download_file(url, destination):
                success = True
                success_count += 1
                break
            
            if attempt < retries - 1:
                retry_delay = 2 ** attempt  # 指数退避
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
        
        if not success:
            failed_resources.append(name)
    
    # 输出结果
    logger.info("-" * 60)
    logger.info(f"下载完成: {success_count}/{len(RESOURCES)} 个资源成功")
    
    if failed_resources:
        logger.error(f"以下资源下载失败: {', '.join(failed_resources)}")
        return False
    
    return True


def check_resources(target_dir: Path) -> tuple:
    """
    检查资源文件是否存在
    
    Args:
        target_dir: 目标目录
        
    Returns:
        tuple: (存在数量, 总数量, 缺失资源列表)
    """
    existing = 0
    missing = []
    
    for resource in RESOURCES:
        path = target_dir / resource["local_path"]
        if path.exists():
            existing += 1
        else:
            missing.append(resource["name"])
    
    return existing, len(RESOURCES), missing


def main():
    """主函数"""
    # 获取templates目录
    current_dir = Path(__file__).parent
    templates_dir = current_dir / "templates"
    
    # 检查目标目录是否存在
    if not templates_dir.exists():
        logger.error(f"模板目录不存在: {templates_dir}")
        logger.info(f"创建模板目录...")
        templates_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查资源
    existing, total, missing = check_resources(templates_dir)
    logger.info(f"发现 {existing}/{total} 个资源文件")
    
    if existing == total:
        logger.info("所有资源文件已存在，无需下载")
        return 0
    
    logger.info(f"需要下载 {total - existing} 个资源文件: {', '.join(missing)}")
    
    # 下载资源
    success = download_all_resources(templates_dir)
    
    if success:
        logger.info("所有资源下载成功")
        return 0
    else:
        logger.error("部分资源下载失败")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 