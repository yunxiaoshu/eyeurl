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

# 添加父目录到sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 现在可以导入eyeurl模块
from eyeurl.capture import read_urls, capture_urls_parallel
from eyeurl.report import generate_report
from eyeurl.config import DEFAULT_CONFIG

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

def setup_logging(log_level=None, log_dir=None):
    """
    设置日志系统，配置输出格式和日志级别
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件目录，如不指定则只输出到控制台
        
    Returns:
        logger: 配置好的日志对象
    """
    import logging
    import sys
    import os
    from datetime import datetime
    
    # 创建日志目录（如果需要）
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # 设置默认日志级别
    if not log_level:
        log_level = "INFO"
    
    # 将字符串日志级别转换为常量
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"无效的日志级别: {log_level}")
        numeric_level = logging.INFO
    
    # 创建根日志器
    logger = logging.getLogger("eyeurl")
    logger.setLevel(numeric_level)
    
    # 清除现有处理器
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    
    # 创建用于过滤不太重要的DEBUG日志的过滤器
    class WarningFilter(logging.Filter):
        def __init__(self, filtered_phrases=None):
            super().__init__()
            self.filtered_phrases = filtered_phrases or []
            
        def filter(self, record):
            if record.levelno == logging.DEBUG:
                # 过滤掉包含特定短语的DEBUG日志
                message = record.getMessage()
                for phrase in self.filtered_phrases:
                    if phrase in message:
                        return False
            return True
    
    # 需要从控制台过滤的低重要性DEBUG日志短语列表
    filter_phrases = [
        "创建浏览器上下文",
        "创建新页面",
        "导航到URL",
        "设置视窗大小",
        "检查图片资源加载状态",
        "所有图片资源已加载完成",
        "等待body元素完成",
        "页面可见性状态",
        "处理懒加载内容",
        "执行页面滚动以加载懒加载内容",
        "等待图片资源加载",
        "等待页面动画完成",
        "页面内容加载检查完成",
        "从页面收集元数据",
        "元数据收集完成",
        "额外等待",
        "关闭页面",
        "关闭浏览器",
        "创建进程池",
        "初始化多进程共享管理器",
        "启动进程池",
        "截图成功",
        "DOM内容加载完成",
        "网络活动已停止",
        "页面加载完成",
        "开始检查页面渲染稳定性",
        "页面渲染已稳定",
        "渲染稳定性检查超时",
        "收集元数据",
        "等待load事件超时",
        "等待body元素超时",
        "获取页面标题失败",
        "页面body元素可见",
        "页面滚动超时或出错",
        "等待DOM内容加载超时",
        "等待网络空闲超时"
    ]
    
    # 为控制台处理器添加过滤器
    console_handler.addFilter(WarningFilter(filter_phrases))
    
    # 设置控制台处理器级别 - 确保控制台只显示WARNING及以上级别
    console_handler.setLevel(max(numeric_level, logging.WARNING))
    
    # 创建格式化器
    console_format = ColoredFormatter()
    console_handler.setFormatter(console_format)
    
    # 添加控制台处理器到日志器
    logger.addHandler(console_handler)
    
    # 如果指定了日志目录，添加文件处理器
    if log_dir:
        # 创建带有时间戳的日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"eyeurl_{timestamp}.log")
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别的日志
        
        # 创建格式化器 (文件格式更详细)
        file_format = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        
        # 添加文件处理器到日志器
        logger.addHandler(file_handler)
        logger.info(f"日志文件: {log_file}")
    
    logger.info(f"日志级别设置为: {log_level}")
    return logger

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='EyeURL - 高性能网页批量截图工具',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # 必选参数
    parser.add_argument('file', help='包含URL列表的文本文件路径')
    
    # 可选参数
    parser.add_argument('--output', '-o', dest='output', default='report',
                        help='输出目录路径')
    
    parser.add_argument('--width', '-w', dest='width', type=int, 
                        default=DEFAULT_CONFIG['width'],
                        help='浏览器视窗宽度(像素)')
    
    parser.add_argument('--height', '-H', dest='height', type=int, 
                        default=DEFAULT_CONFIG['height'],
                        help='浏览器视窗高度(像素)')
    
    parser.add_argument('--timeout', '-t', dest='timeout', type=int, 
                        default=DEFAULT_CONFIG['timeout'],
                        help='页面加载超时时间(秒)')
    
    parser.add_argument('--network-timeout', '-n', dest='network_timeout', type=int, 
                        default=DEFAULT_CONFIG['network_timeout'],
                        help='网络活动停止等待时间(秒)')
    
    parser.add_argument('--wait', '-W', dest='wait', type=float, 
                        default=DEFAULT_CONFIG['wait_time'],
                        help='页面加载后额外等待时间(秒)')
    
    parser.add_argument('--threads', '-T', dest='threads', type=int, 
                        default=DEFAULT_CONFIG['threads'],
                        help='并行处理的线程数')
    
    parser.add_argument('--retry', '-r', dest='retry', type=int, 
                        default=DEFAULT_CONFIG['retry_count'],
                        help='失败后重试次数，特别是处理网络连接错误')
    
    parser.add_argument('--full-page', '-f', dest='full_page', action='store_true',
                        default=DEFAULT_CONFIG['full_page'],
                        help='截取整个页面而非仅视窗大小(实验性)')
    
    parser.add_argument('--user-agent', '-u', dest='user_agent',
                        default=DEFAULT_CONFIG['user_agent'],
                        help='自定义User-Agent')
    
    parser.add_argument('--ignore-ssl-errors', '-S', dest='ignore_ssl_errors',
                        action='store_true',
                        default=DEFAULT_CONFIG['ignore_ssl_errors'],
                        help='忽略SSL证书错误，允许访问无效证书的网站')
    
    parser.add_argument('--verbose', '-v', dest='verbose', 
                        action='store_true', default=False,
                        help='输出更详细的信息')

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
    logger = setup_logging(log_dir=output_dir)
    logger.info(f"{Symbols.START} EyeURL 截图工具启动 - 版本 1.1.0")
    
    # 记录系统信息和配置信息，但只在DEBUG级别记录，不显示在控制台
    logger.debug(f"{Symbols.INIT} 系统信息:")
    logger.debug(f"  - 操作系统: {os.name} {sys.platform}")
    logger.debug(f"  - Python版本: {sys.version}")
    logger.debug(f"  - 进程ID: {os.getpid()}")
    logger.debug(f"  - 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
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
    logger.debug(f"  - 忽略SSL错误: {'是' if args.ignore_ssl_errors else '否'}")
    if args.user_agent:
        logger.debug(f"  - 自定义UA: {args.user_agent}")
    logger.debug(f"  - 详细日志: {'是' if args.verbose else '否'}")
    
    try:
        # 记录开始读取URL列表
        logger.info(f"{Symbols.PHASE} 阶段1: 读取URL列表 - 开始")
        
        # 读取URL列表
        start_read = time.time()
        urls = read_urls(args.file)
        end_read = time.time()
        
        # 记录读取完成的日志
        logger.info(f"{Symbols.PHASE} 阶段1: 读取URL列表 - 完成 ({end_read - start_read:.2f}秒)")
        logger.info(f"从 {args.file} 读取了 {len(urls)} 个URL")
        
        # 输出URL示例，但仅在verbose和debug模式下
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
            verbose=args.verbose,
            ignore_ssl_errors=args.ignore_ssl_errors
        )
        capture_end = time.time()
        
        # 记录截图完成的日志
        capture_time = capture_end - capture_start
        logger.info(f"{Symbols.PHASE} 阶段2: 执行批量截图 - 完成 ({capture_time:.2f}秒)")
        
        # 使用results中的batch_info来获取实际的平均处理时间
        if results and len(results) > 0 and "meta_data" in results[0] and "batch_info" in results[0]["meta_data"]:
            batch_info = results[0]["meta_data"]["batch_info"]
            average_url_time = batch_info["batch_time"]["average_url_time"]
            theoretical_serial_time = batch_info["batch_time"]["processing_time"]
            parallel_efficiency = batch_info["batch_time"]["parallel_efficiency"]
            logger.info(f"平均每URL处理时间: {average_url_time:.2f}秒")
        else:
            # 如果没有batch_info，则使用理论计算值
            total_processing_time = sum(r.get("processing_time", 0) for r in results)
            average_url_time = total_processing_time / len(results) if results else 0
            theoretical_serial_time = total_processing_time
            parallel_efficiency = (capture_time / total_processing_time) * 100 if total_processing_time > 0 else 0
            logger.info(f"平均每URL处理时间: {average_url_time:.2f}秒")
        
        # 统计成功和失败数量 - 基于截图成功与否，而非状态码
        success_count = sum(1 for r in results if r.get("success") is True or (r.get("screenshot") and not r.get("error")))
        failed_count = sum(1 for r in results if r.get("success") is False or (r.get("error") and r.get("success") is not True))
        logger.info(f"截图结果: 成功={success_count}, 失败={failed_count}, 总计={len(results)}")
        
        # 分隔线
        print(f"\n{ConsoleColors.BLUE}{Symbols.FINISH} 处理完成{ConsoleColors.ENDC}")
        
        # 记录开始生成报告
        logger.info(f"{Symbols.PHASE} 阶段3: 生成结果报告 - 开始")
        
        # 保存结果到JSON文件
        results_file = output_dir / "data.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 生成HTML报告
        report_start = time.time()
        report_file = output_dir / "index.html"
        generate_report(results, report_file, screenshots_dir)
        report_end = time.time()
        
        # 记录报告生成完成 - 精简输出，避免重复
        logger.info(f"{Symbols.PHASE} 阶段3: 生成结果报告 - 完成 ({report_end - report_start:.2f}秒)")
        # 统计成功/失败率
        success_rate = success_count/len(results)*100
        logger.info(f"{Symbols.FILE} 报告统计: {len(results)}个URL, 成功率: {success_rate:.1f}%")
        # 输出文件路径 - 合并为一条信息
        logger.info(f"{Symbols.FILE} 报告路径: {report_file}")
        logger.info(f"{Symbols.DIR} 截图路径: {screenshots_dir}")
        
        # 计算总耗时
        elapsed_time = time.time() - start_time
        logger.info(f"{Symbols.END} 任务完成，总耗时: {elapsed_time:.2f} 秒")
        
        # 将总耗时添加到所有结果的元数据中，确保报告使用控制台相同的总耗时
        for result in results:
            if "meta_data" not in result:
                result["meta_data"] = {}
            if "batch_info" not in result["meta_data"]:
                result["meta_data"]["batch_info"] = {}
            if "batch_time" not in result["meta_data"]["batch_info"]:
                result["meta_data"]["batch_info"]["batch_time"] = {}
                
            # 使用控制台的总耗时覆盖批处理时间信息
            result["meta_data"]["batch_info"]["batch_time"]["total_time_seconds"] = elapsed_time
            result["meta_data"]["batch_info"]["batch_time"]["total_time_formatted"] = format_time(elapsed_time)
        
        # 结果统计
        print(f"\n{ConsoleColors.CYAN}{ConsoleColors.BOLD}{'='*30} 任务统计 {'='*30}{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.GREEN}{Symbols.SUCCESS} 成功截图: {success_count}/{len(urls)}{ConsoleColors.ENDC}")
        if failed_count > 0:
            print(f"{ConsoleColors.RED}{Symbols.ERROR} 失败截图: {failed_count}/{len(urls)}{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.YELLOW}{Symbols.TIME} 总耗时: {elapsed_time:.2f} 秒{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.YELLOW}{Symbols.TIME} 平均处理时间: {average_url_time:.2f} 秒/URL{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.YELLOW}{Symbols.TIME} 并行效率: {parallel_efficiency:.2f}%{ConsoleColors.ENDC}")
        print(f"{ConsoleColors.CYAN}{ConsoleColors.BOLD}{'='*60}{ConsoleColors.ENDC}\n")
        
        # 将详细统计信息保留在DEBUG级别，减少日志输出
        logger.debug(f"{Symbols.FINISH} 详细统计信息:")
        logger.debug(f"  - URL总数: {len(urls)}")
        logger.debug(f"  - 成功截图: {success_count}")
        logger.debug(f"  - 失败截图: {failed_count}")
        logger.debug(f"  - 成功率: {(success_count/len(urls)*100):.1f}%")
        logger.debug(f"  - 读取URLs时间: {end_read - start_read:.2f}秒")
        logger.debug(f"  - 截图处理时间: {capture_time:.2f}秒")
        logger.debug(f"  - 理论串行时间: {theoretical_serial_time:.2f}秒")
        logger.debug(f"  - 平均每URL处理时间: {average_url_time:.2f}秒")
        logger.debug(f"  - 并行效率: {parallel_efficiency:.2f}%")
        logger.debug(f"  - 报告生成时间: {report_end - report_start:.2f}秒")
        logger.debug(f"  - 总耗时: {elapsed_time:.2f}秒")
            
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

def format_time(seconds):
    """格式化秒数为人类可读格式"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        seconds = seconds % 60
        return f"{minutes}分{seconds:.0f}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}小时{minutes}分"

if __name__ == "__main__":
    sys.exit(main()) 