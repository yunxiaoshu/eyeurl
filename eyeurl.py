#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EyeURL - 网页批量截图工具

使用方法:
    python eyeurl.py -f <URL文件> [选项]

选项:
    -f, --file            包含URL列表的文本文件，每行一个URL（必需）
    -o, --output          输出目录，用于保存截图和报告（默认: report）
    --width               浏览器窗口宽度（默认: 1280）
    --height              浏览器窗口高度（默认: 800）
    --timeout             页面加载超时时间（秒）（默认: 30）
    --network-timeout     网络等待超时时间（秒）（默认: 3）
    --retry               失败时重试次数（默认: 1）
    --wait                页面加载后的额外等待时间（秒）（默认: 0）
    --threads             并行处理的线程数（默认: 4）
    --full-page           截取完整页面而非仅可见区域
    --user-agent          自定义User-Agent字符串

功能特性:
    - 自动检测URL可访问性，只对可访问的URL进行截图
    - 将不可访问的URL及原因记录到inaccessible_urls.txt文件
    - 只有连接超时和连接错误的URL被视为不可访问，其他状态码(包括404、403、500等)都会进行截图
    - 多线程并行处理，提高效率
    - 生成美观的HTML报告

示例:
    python eyeurl.py -f testurl.txt --threads 5 --wait 3 --full-page
    python eyeurl.py -f sites.txt --timeout 60 --network-timeout 5 --retry 2
"""

import sys
from eyeurl.main import main

if __name__ == "__main__":
    sys.exit(main()) 