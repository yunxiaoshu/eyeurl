#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EyeURL - 网页批量截图工具
主程序模块负责命令行参数处理和程序流程控制
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

from eyeurl.capture import read_urls, capture_urls_parallel
from eyeurl.report import generate_report

# 定义控制台颜色和符号
class ConsoleColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GRAY = '\033[90m'

class Symbols:
    INFO = "ℹ️ "
    SUCCESS = "✅ "
    ERROR = "❌ "
    WARNING = "⚠️ "
    ARROW = "➤ "
    STAR = "★ "
    DOT = "• "
    ROCKET = "🚀 "
    HOURGLASS = "⏳ "
    FINISH = "🏁 "
    URL = "🔗 "
    TIME = "⏱️ "
    FILE = "📄 "
    DIR = "📁 "
    CONFIG = "⚙️ "
    INIT = "🔧 "
    LOAD = "📥 "
    PROCESS = "⚙️ "
    SAVE = "💾 "
    START = "▶️ "
    END = "⏹️ "
    BROWSER = "🌐 "
    SCREENSHOT = "📸 "
    GEAR = "⚙️ "
    LOG = "📝 "
    PHASE = "📌 "

class ColoredFormatter(logging.Formatter):
    """美化彩色日志格式化"""
    FORMATS = {
        logging.DEBUG: ConsoleColors.GRAY + "[%(asctime)s] " + Symbols.DOT + " %(message)s" + ConsoleColors.ENDC,
        logging.INFO: ConsoleColors.GREEN + "[%(asctime)s] " + Symbols.INFO + " %(message)s" + ConsoleColors.ENDC,
        logging.WARNING: ConsoleColors.YELLOW + "[%(asctime)s] " + Symbols.WARNING + " %(message)s" + ConsoleColors.ENDC,
        logging.ERROR: ConsoleColors.RED + "[%(asctime)s] " + Symbols.ERROR + " %(message)s" + ConsoleColors.ENDC,
        logging.CRITICAL: ConsoleColors.RED + ConsoleColors.BOLD + "[%(asctime)s] " + Symbols.ERROR + " %(message)s" + ConsoleColors.ENDC
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        
        # 为ERROR和CRITICAL级别添加额外的模块和行号信息
        if record.levelno >= logging.ERROR:
            record.message = record.getMessage()
            file_info = f"[{record.filename}:{record.lineno}] "
            record.msg = f"{file_info}{record.msg}"
        
        return formatter.format(record)

def setup_logging(output_dir: Path) -> logging.Logger:
    """设置日志系统"""
    # 确保日志目录存在
    log_dir = output_dir / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # 创建日志文件名
    log_file = log_dir / "eyeurl.log"
    
    # 自定义日志格式，文件日志详细，控制台输出简洁
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = ColoredFormatter()
    
    # 文件处理器 - 记录所有详细信息 (DEBUG级别)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # 文件日志保持DEBUG级别
    
    # 控制台处理器 - 只显示重要信息 (默认INFO级别及以上)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    
    # 过滤掉一些特定的警告和调试消息
    class WarningFilter(logging.Filter):
        def filter(self, record):
            # 过滤掉以下内容:
            # - 等待页面可见性检查超时
            # - 尝试使用domcontentloaded策略
            # - navigating to, waiting until
            # - 页面加载失败
            # - 超时相关错误
            msg = record.getMessage().lower()
            filtered_phrases = [
                "等待页面可见性检查超时",
                "尝试使用domcontentloaded策略",
                "navigating to",
                "waiting until",
                "wait_for_selector",
                "页面加载失败",
                "加载失败",
                "超时",
                "timeout",
                "处理url时出错",
                "处理完成: 失败",
                "call log",
                "exceeded"
            ]
            return not any(phrase in msg for phrase in filtered_phrases)
    
    # 应用过滤器到控制台处理器
    console_handler.addFilter(WarningFilter())
    console_handler.setLevel(logging.INFO)  # 控制台只显示INFO及以上级别
    
    # 配置日志记录器
    logger = logging.getLogger("eyeurl")
    logger.setLevel(logging.DEBUG)  # 主记录器设置为DEBUG，可以捕获所有信息
    
    # 确保没有重复的处理器
    logger.handlers = []
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 只在文件中记录初始化信息
    logger.debug(f"日志系统初始化完成，日志文件: {log_file}")
    logger.debug(f"日志级别设置: 文件={logging.getLevelName(file_handler.level)}, 控制台={logging.getLevelName(console_handler.level)}")
    
    return logger

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="EyeURL - 高性能网页批量截图工具",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "-f", "--file", 
        required=True,
        help="包含URL列表的文本文件，每行一个URL"
    )
    
    parser.add_argument(
        "-o", "--output", 
        default="report",
        help="输出目录，用于保存截图和报告"
    )
    
    parser.add_argument(
        "--width", 
        type=int, 
        default=1280,
        help="浏览器窗口宽度"
    )
    
    parser.add_argument(
        "--height", 
        type=int, 
        default=800,
        help="浏览器窗口高度"
    )
    
    parser.add_argument(
        "--timeout", 
        type=int, 
        default=30,
        help="页面加载超时时间（秒）"
    )
    
    parser.add_argument(
        "--network-timeout", 
        type=int, 
        default=3,
        help="网络等待超时时间（秒），较小的值适用于复杂网页"
    )
    
    parser.add_argument(
        "--retry", 
        type=int, 
        default=1,
        help="失败时重试次数"
    )
    
    parser.add_argument(
        "--wait", 
        type=float, 
        default=0,
        help="页面加载后的额外等待时间（秒），可用于等待动态内容加载"
    )
    
    parser.add_argument(
        "--threads", 
        type=int, 
        default=5,
        help="并行处理的线程数"
    )
    
    parser.add_argument(
        "--full-page", 
        action="store_true",
        help="截取完整页面而非仅可见区域"
    )
    
    parser.add_argument(
        "--user-agent", 
        help="自定义User-Agent字符串"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="显示详细日志输出"
    )
    
    return parser.parse_args()

def main():
    """主程序入口"""
    start_time = time.time()
    
    # 打印精美的程序启动标题
    print(f"\n{ConsoleColors.CYAN}{ConsoleColors.BOLD}{'='*60}{ConsoleColors.ENDC}")
    print(f"{ConsoleColors.CYAN}{ConsoleColors.BOLD}{Symbols.ROCKET} EyeURL - 高性能网页批量截图工具{ConsoleColors.ENDC}")
    print(f"{ConsoleColors.CYAN}{ConsoleColors.BOLD}{'='*60}{ConsoleColors.ENDC}\n")
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 创建基础输出目录
    base_output_dir = Path(args.output)
    base_output_dir.mkdir(exist_ok=True, parents=True)
    
    # 创建以时间戳命名的任务子目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base_output_dir / f"report_{timestamp}"
    output_dir.mkdir(exist_ok=True)
    
    # 创建截图目录
    screenshots_dir = output_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # 设置日志
    logger = setup_logging(output_dir)
    logger.info(f"{Symbols.START} EyeURL 截图工具启动 - 版本 1.0.0")
    logger.info(f"{Symbols.TIME} 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 记录系统信息，但改为DEBUG级别
    logger.debug(f"{Symbols.INIT} 系统信息:")
    logger.debug(f"  - 操作系统: {os.name} {sys.platform}")
    logger.debug(f"  - Python版本: {sys.version}")
    logger.debug(f"  - 进程ID: {os.getpid()}")
    
    # 将任务配置详情记录改为DEBUG级别，不在控制台显示
    logger.debug(f"{Symbols.CONFIG} 任务配置详情:")
    logger.debug(f"  - URL文件: {args.file}")
    logger.debug(f"  - 输出目录: {output_dir}")
    logger.debug(f"  - 截图目录: {screenshots_dir}")
    logger.debug(f"  - 浏览器窗口: {args.width}x{args.height}像素")
    logger.debug(f"  - 页面超时: {args.timeout}秒")
    logger.debug(f"  - 网络超时: {args.network_timeout}秒")
    logger.debug(f"  - 重试次数: {args.retry}次")
    logger.debug(f"  - 线程数量: {args.threads}个")
    logger.debug(f"  - 额外等待: {args.wait}秒")
    logger.debug(f"  - 全页面截图: {'是' if args.full_page else '否'}")
    if args.user_agent:
        logger.debug(f"  - 自定义UA: {args.user_agent}")
    logger.debug(f"  - 详细日志: {'是' if args.verbose else '否'}")
    
    try:
        # 记录开始读取URL列表
        logger.info(f"{Symbols.PHASE} 阶段1: 读取URL列表 - 开始")
        logger.debug(f"  正在从文件读取URL: {args.file}")
        
        # 读取URL列表
        start_read = time.time()
        urls = read_urls(args.file)
        end_read = time.time()
        
        # 记录读取完成的日志
        logger.info(f"{Symbols.PHASE} 阶段1: 读取URL列表 - 完成 ({end_read - start_read:.2f}秒)")
        logger.info(f"  从 {args.file} 读取了 {len(urls)} 个URL")
        
        # 输出URL数量
        if args.verbose and urls:
            logger.debug(f"  URL示例:")
            for i, url in enumerate(urls[:min(6, len(urls))]):
                logger.debug(f"    - {url}")
            if len(urls) > 6:
                logger.debug(f"    - ... 及其他 {len(urls) - 6} 个URL")
        
        # 分隔线
        print(f"\n{ConsoleColors.BLUE}{Symbols.HOURGLASS} 开始处理 - 共 {len(urls)} 个URL{ConsoleColors.ENDC}\n")
        
        # 记录开始执行截图
        logger.info(f"{Symbols.PHASE} 阶段2: 执行批量截图 - 开始")
        logger.debug(f"  准备启动 {args.threads} 个并行处理线程")
        
        # 执行批量截图
        capture_start = time.time()
        results = capture_urls_parallel(
            urls=urls,
            screenshots_dir=screenshots_dir,
            timeout=args.timeout,
            width=args.width,
            height=args.height,
            wait_time=args.wait,
            full_page=args.full_page,
            threads=args.threads,
            user_agent=args.user_agent,
            logger=logger,
            retry_count=args.retry,
            network_timeout=args.network_timeout,
            verbose=args.verbose
        )
        capture_end = time.time()
        
        # 记录截图完成的日志
        capture_time = capture_end - capture_start
        logger.info(f"{Symbols.PHASE} 阶段2: 执行批量截图 - 完成 ({capture_time:.2f}秒)")
        logger.info(f"  平均每URL处理时间: {capture_time/len(urls):.2f}秒")
        
        # 统计成功和失败数量
        success_count = sum(1 for r in results if r.get("success") is True or (not r.get("error") and r.get("status_code", 0) >= 200 and r.get("status_code", 0) < 300))
        failed_count = sum(1 for r in results if r.get("success") is False or (r.get("error") and r.get("success") is not True))
        logger.info(f"  截图结果: 成功={success_count}, 失败={failed_count}, 总计={len(results)}")
        
        # 分隔线
        print(f"\n{ConsoleColors.BLUE}{Symbols.FINISH} 处理完成{ConsoleColors.ENDC}")
        
        # 记录开始生成报告
        logger.info(f"{Symbols.PHASE} 阶段3: 生成结果报告 - 开始")
        logger.debug(f"  正在准备JSON数据")
        
        # 保存结果到JSON文件
        results_file = output_dir / "data.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.debug(f"  结果数据已保存至: {results_file}")
        
        # 生成HTML报告
        logger.debug(f"  正在生成HTML报告")
        report_start = time.time()
        report_file = output_dir / "index.html"
        generate_report(results, report_file, screenshots_dir)
        report_end = time.time()
        
        # 记录报告生成完成 - 精简输出，避免重复
        logger.info(f"{Symbols.PHASE} 阶段3: 生成结果报告 - 完成 ({report_end - report_start:.2f}秒)")
        # 统计成功/失败率
        success_rate = success_count/len(results)*100
        logger.info(f"  报告统计: {len(results)}个URL, 成功率: {success_rate:.1f}%")
        # 输出文件路径 - 合并为一条信息
        logger.info(f"  {Symbols.FILE} 报告路径: {report_file}")
        logger.info(f"  {Symbols.DIR} 截图路径: {screenshots_dir}")
        
        # 计算总耗时
        elapsed_time = time.time() - start_time
        logger.info(f"{Symbols.END} 任务完成，总耗时: {elapsed_time:.2f} 秒")
        
        # 结果统计
        print(f"\n{ConsoleColors.CYAN}{ConsoleColors.BOLD}{'='*30} 任务统计 {'='*30}{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.GREEN}{Symbols.SUCCESS} 成功截图: {success_count}/{len(urls)}{ConsoleColors.ENDC}")
        if failed_count > 0:
            print(f"{ConsoleColors.RED}{Symbols.ERROR} 失败截图: {failed_count}/{len(urls)}{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.YELLOW}{Symbols.TIME} 总耗时: {elapsed_time:.2f} 秒{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.YELLOW}{Symbols.TIME} 平均耗时: {elapsed_time/len(urls):.2f} 秒/URL{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.CYAN}{ConsoleColors.BOLD}{'='*60}{ConsoleColors.ENDC}\n")
        
        # 记录详细统计信息到日志，但仅在DEBUG级别，避免INFO级别冗余信息
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"{Symbols.FINISH} 详细统计信息:")
            logger.debug(f"  - URL总数: {len(urls)}")
            logger.debug(f"  - 成功截图: {success_count}")
            logger.debug(f"  - 失败截图: {failed_count}")
            logger.debug(f"  - 成功率: {(success_count/len(urls)*100):.1f}%")
            logger.debug(f"  - 读取URLs时间: {end_read - start_read:.2f}秒")
            logger.debug(f"  - 截图处理时间: {capture_time:.2f}秒")
            logger.debug(f"  - 报告生成时间: {report_end - report_start:.2f}秒")
            logger.debug(f"  - 总耗时: {elapsed_time:.2f}秒")
            logger.debug(f"  - 平均每URL耗时: {elapsed_time/len(urls):.2f}秒")
            
            logger.debug(f"{Symbols.FILE} 文件路径信息:")
            logger.debug(f"  - JSON数据: {results_file}")
            logger.debug(f"  - HTML报告: {report_file}")
            logger.debug(f"  - 截图目录: {screenshots_dir}")
            logger.debug(f"  - 日志目录: {output_dir / 'logs'}")
        
        return 0
        
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}", exc_info=True)
        print(f"\n{ConsoleColors.RED}{ConsoleColors.BOLD}{Symbols.ERROR} 执行过程中出现错误:{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.RED}{str(e)}{ConsoleColors.ENDC}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 