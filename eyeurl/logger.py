#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志模块 - 配置和管理日志记录
"""

import logging
from pathlib import Path


def setup_logger(log_dir: Path) -> logging.Logger:
    """设置日志记录器"""
    logger = logging.getLogger("eyeurl")
    
    # 确保不会重复添加处理器
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_format)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_dir / "eyeurl.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    
    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger 