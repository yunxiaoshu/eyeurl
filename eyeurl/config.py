#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置模块 - 处理程序配置和命令行参数
"""

import argparse
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    """程序配置类"""
    url_file: str
    output_dir: str
    width: int
    height: int
    timeout: int
    threads: int
    wait_time: float
    full_page: bool
    user_agent: str


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="批量截图网页并生成报告")
    parser.add_argument("-f", "--file", required=True, help="包含URL列表的文本文件")
    parser.add_argument("-o", "--output", default="report", help="输出报告的目录，默认为'report'")
    parser.add_argument("--width", type=int, default=1920, help="浏览器视窗宽度，默认1920")
    parser.add_argument("--height", type=int, default=1080, help="浏览器视窗高度，默认1080")
    parser.add_argument("--timeout", type=int, default=30, help="页面加载超时时间(秒)，默认30秒")
    parser.add_argument("--threads", type=int, default=5, help="并行处理的线程数，默认5")
    parser.add_argument("--wait", type=float, default=2.0, help="页面加载后的额外等待时间(秒)，默认2秒")
    parser.add_argument("--full-page", action="store_true", help="截取整个页面，而不仅是可见区域")
    parser.add_argument("--user-agent", type=str, default=None, help="自定义User-Agent")
    
    args = parser.parse_args()
    
    # 检查URL文件是否存在
    if not os.path.exists(args.file):
        parser.error(f"URL文件不存在: {args.file}")
    
    return Config(
        url_file=args.file,
        output_dir=args.output,
        width=args.width,
        height=args.height,
        timeout=args.timeout,
        threads=args.threads,
        wait_time=args.wait,
        full_page=args.full_page,
        user_agent=args.user_agent
    ) 