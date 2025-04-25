#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
截图模块 - 处理网页截图和信息获取
"""

import time
import logging
import multiprocessing
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

from tqdm import tqdm
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

def read_urls(file_path: str) -> List[str]:
    """从文件中读取URL列表"""
    logger = logging.getLogger("eyeurl")
    logger.debug(f"正在打开URL文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            logger.debug(f"成功读取文件，共 {len(lines)} 行")
            
            # 过滤注释和空行
            urls = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
            logger.debug(f"过滤后有效URL: {len(urls)} 个")
            
            # 检查URL格式
            for i, url in enumerate(urls):
                if not (url.startswith('http://') or url.startswith('https://')):
                    logger.warning(f"URL格式警告: 第 {i+1} 行URL不以http://或https://开头: {url}")
                    # 我们不自动修改URL，只是提醒
            
            return urls
    except Exception as e:
        logger.error(f"读取URL文件失败: {str(e)}")
        raise


def capture_url(
    url: str, 
    screenshot_dir: Path, 
    timeout: int,
    width: int,
    height: int,
    wait_time: float,
    full_page: bool,
    user_agent: Optional[str] = None,
    network_timeout: int = 3,
    logger: Optional[logging.Logger] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """捕获单个URL的信息和截图"""
    if logger is None:
        logger = logging.getLogger("eyeurl")
    
    # 为每个URL生成唯一会话ID，便于在日志中跟踪
    session_id = int(time.time() * 1000) % 10000
    log_prefix = f"[URL-{session_id}]"
    
    logger.info(f"{log_prefix} 开始处理: {url}")
    start_time = time.time()
    
    result = {
        "url": url,
        "title": "",
        "status_code": 0,
        "content_size": 0,
        "screenshot": "",
        "timestamp": datetime.now().isoformat(),
        "error": "",
        "response_headers": {},
        "meta_data": {},
        "processing_time": 0
    }
    
    # 启动Playwright
    logger.debug(f"{log_prefix} 初始化Playwright浏览器")
    with sync_playwright() as playwright:
        # 启动浏览器
        browser_start = time.time()
        logger.debug(f"{log_prefix} 启动Chromium浏览器")
        browser = playwright.chromium.launch(headless=True)
        logger.debug(f"{log_prefix} 浏览器启动完成，耗时: {time.time() - browser_start:.2f}秒")
        
        # 创建上下文，设置视窗大小和User-Agent
        context_options = {"viewport": {"width": width, "height": height}}
        if user_agent:
            context_options["user_agent"] = user_agent
            logger.debug(f"{log_prefix} 使用自定义User-Agent: {user_agent}")
        else:
            logger.debug(f"{log_prefix} 使用默认User-Agent")
        
        logger.debug(f"{log_prefix} 创建浏览器上下文，视窗大小: {width}x{height}")
        context = browser.new_context(**context_options)
        logger.debug(f"{log_prefix} 创建新页面")
        page = context.new_page()
        
        try:
            # 设置页面超时
            page.set_default_timeout(timeout * 1000)
            logger.debug(f"{log_prefix} 设置页面超时: {timeout}秒")
            
            # 改进的导航策略
            goto_strategies = [
                {"strategy": "load", "timeout": min(15000, timeout * 1000)},
                {"strategy": "domcontentloaded", "timeout": min(20000, timeout * 1000)},
                {"strategy": "commit", "timeout": timeout * 1000}
            ]
            
            logger.info(f"{log_prefix} 开始加载页面: {url}")
            response = None
            last_error = None
            
            # 尝试多种加载策略，如果前一种失败则使用下一种
            for i, strategy_config in enumerate(goto_strategies):
                strategy = strategy_config["strategy"]
                strategy_timeout = strategy_config["timeout"]
                
                if i > 0:
                    logger.debug(f"{log_prefix} 尝试备选加载策略 {i+1}/{len(goto_strategies)}: {strategy}")
                
                try:
                    goto_start = time.time()
                    response = page.goto(url, wait_until=strategy, timeout=strategy_timeout)
                    logger.debug(f"{log_prefix} 页面加载成功(使用{strategy}策略)，耗时: {time.time() - goto_start:.2f}秒")
                    break
                except Exception as e:
                    last_error = e
                    # 只记录到DEBUG级别，不出现在控制台
                    logger.debug(f"{log_prefix} {strategy}策略加载失败: {str(e)}")
                    # 继续尝试下一个策略
            
            # 如果所有策略都失败了但尚未引发异常
            if response is None and last_error is not None:
                # 降级到DEBUG级别以减少控制台输出
                logger.debug(f"{log_prefix} 所有页面加载策略均失败: {str(last_error)}")
                # 继续尝试处理，因为页面可能已部分加载
            
            if response:
                status_code = response.status
                content_size = len(response.body())
                headers = dict(response.headers)
                result["status_code"] = status_code
                result["content_size"] = content_size
                result["response_headers"] = headers
                
                logger.info(f"{log_prefix} 页面加载结果: 状态码={status_code}, 大小={format_bytes(content_size)}")
                
                if verbose:
                    logger.debug(f"{log_prefix} 响应头信息:")
                    for key, value in headers.items():
                        logger.debug(f"{log_prefix}   - {key}: {value}")
            else:
                logger.debug(f"{log_prefix} 未能获取页面响应对象")
            
            # 改进：更健壮的等待策略
            load_state_success = False
            try:
                # 等待DOM内容加载完成 - 使用更短的超时
                logger.debug(f"{log_prefix} 等待DOM内容加载完成")
                page.wait_for_load_state("domcontentloaded", timeout=min(8000, timeout * 1000))
                logger.debug(f"{log_prefix} DOM内容加载完成")
                load_state_success = True
            except Exception as e:
                # 降级为DEBUG级别
                logger.debug(f"{log_prefix} 等待DOM内容超时: {str(e)}")
                # 忽略超时，继续处理
            
            # 如果DOM加载成功，则尝试等待网络活动
            if load_state_success:
                try:
                    # 使用较短的网络等待超时
                    network_wait_ms = min(network_timeout * 1000, 5000)  # 最多5秒
                    logger.debug(f"{log_prefix} 等待网络活动停止，超时: {network_wait_ms/1000}秒")
                    network_wait_start = time.time()
                    page.wait_for_load_state("networkidle", timeout=network_wait_ms)
                    logger.debug(f"{log_prefix} 网络活动已停止，耗时: {time.time() - network_wait_start:.2f}秒")
                except Exception as e:
                    # 降级为DEBUG级别
                    logger.debug(f"{log_prefix} 等待网络活动停止超时: {str(e)}")
                    # 忽略超时，继续处理
            
            # 更健壮的可见性检查
            try:
                logger.debug(f"{log_prefix} 检查页面可见性")
                # 使用非阻塞方式检查body是否存在
                has_body = page.query_selector("body") is not None
                
                if has_body:
                    logger.debug(f"{log_prefix} 等待body元素可见")
                    # 增加超时时间到8000ms（8秒）
                    page.wait_for_selector("body", state="visible", timeout=8000)
                    logger.debug(f"{log_prefix} body元素已可见")
                else:
                    logger.debug(f"{log_prefix} 未找到body元素")
                    # 使用延迟等待代替
                    time.sleep(1.5)  # 等待1.5秒
            except Exception as e:
                # 降级为DEBUG级别
                logger.debug(f"{log_prefix} 等待页面可见性检查超时: {str(e)}")
                # 等待更长时间让页面渲染
                logger.debug(f"{log_prefix} 等待2000ms让页面继续渲染")
                time.sleep(2.0)  # 增加等待时间到2秒
                
            # 额外等待时间（可选，用于特殊情况）
            if wait_time > 0:
                logger.debug(f"{log_prefix} 执行额外等待: {wait_time}秒")
                time.sleep(wait_time)
                logger.debug(f"{log_prefix} 额外等待完成")
                
            # 自动处理懒加载内容，但使用try-except避免阻塞
            try:
                logger.debug(f"{log_prefix} 尝试处理懒加载内容")
                lazy_start = time.time()
                ensure_content_loaded(page)
                logger.debug(f"{log_prefix} 懒加载内容处理完成，耗时: {time.time() - lazy_start:.2f}秒")
            except Exception as e:
                # 降级为DEBUG级别
                logger.debug(f"{log_prefix} 处理懒加载内容出错: {str(e)}")
                # 忽略懒加载过程中的错误
            
            # 获取页面标题
            try:
                title = page.title()
                result["title"] = title
                logger.info(f"{log_prefix} 页面标题: \"{title}\"")
            except Exception as e:
                # 降级为DEBUG级别
                logger.debug(f"{log_prefix} 获取页面标题失败: {str(e)}")
                result["title"] = url  # 如果无法获取标题，使用URL作为替代
            
            # 收集元数据
            try:
                logger.debug(f"{log_prefix} 收集页面元数据")
                meta_start = time.time()
                meta_data = collect_page_metadata(page)
                result["meta_data"] = meta_data
                logger.debug(f"{log_prefix} 元数据收集完成，耗时: {time.time() - meta_start:.2f}秒")
                
                if verbose and meta_data:
                    logger.debug(f"{log_prefix} 页面元数据:")
                    for key, value in meta_data.items():
                        if isinstance(value, str) and len(value) > 100:
                            value = value[:100] + "..."
                        logger.debug(f"{log_prefix}   - {key}: {value}")
            except Exception as e:
                # 降级为DEBUG级别
                logger.debug(f"{log_prefix} 收集元数据失败: {str(e)}")
                result["meta_data"] = {}
            
            # 生成截图文件名
            safe_url = url.replace("://", "_").replace("/", "_").replace(":", "_").replace("?", "_")
            if len(safe_url) > 100:
                safe_url = safe_url[:100]  # 避免文件名过长
            
            screenshot_path = screenshot_dir / f"{safe_url}.png"
            logger.debug(f"{log_prefix} 截图文件路径: {screenshot_path}")
            
            # 添加额外的安全检查 - 确保页面至少有一些内容
            force_visible_area_screenshot = False
            try:
                has_content = page.evaluate("""() => {
                    return document.body && (
                        document.body.innerText.length > 0 || 
                        document.body.getElementsByTagName('img').length > 0 ||
                        document.body.getElementsByTagName('svg').length > 0
                    );
                }""")
                
                if not has_content:
                    logger.debug(f"{log_prefix} 页面内容为空，将仅尝试截取可视区域")
                    force_visible_area_screenshot = True
            except Exception as e:
                logger.debug(f"{log_prefix} 检查页面内容失败: {str(e)}")
                # 继续尝试截图
            
            # 截取全页面或可视区域，使用较短的超时
            try:
                actual_full_page = full_page and not force_visible_area_screenshot
                logger.info(f"{log_prefix} 开始截图 ({'全页面' if actual_full_page else '可视区域'})")
                screenshot_start = time.time()
                page.screenshot(path=screenshot_path, full_page=actual_full_page, timeout=min(8000, timeout * 1000))
                screenshot_time = time.time() - screenshot_start
                logger.info(f"{log_prefix} 截图完成，耗时: {screenshot_time:.2f}秒")
                
                # 记录截图文件名
                result["screenshot"] = screenshot_path.name
                
                # 记录截图尺寸
                result["meta_data"]["screenshot_size"] = os.path.getsize(screenshot_path)
                
                # 添加成功标记，明确表示截图成功
                result["success"] = True
            except Exception as e:
                # 降级为DEBUG级别，避免控制台显示错误
                logger.debug(f"{log_prefix} 截图失败: {str(e)}")
                # 如果全页面截图失败，尝试只截取可视区域
                if full_page:
                    try:
                        logger.debug(f"{log_prefix} 尝试回退到可视区域截图")
                        screenshot_start = time.time()
                        page.screenshot(path=screenshot_path, full_page=False)
                        screenshot_time = time.time() - screenshot_start
                        logger.info(f"{log_prefix} 可视区域截图完成，耗时: {screenshot_time:.2f}秒")
                        
                        result["screenshot"] = screenshot_path.name
                        # 不将这视为错误，而是仅在日志中记录
                        logger.debug(f"{log_prefix} 全页面截图失败，已使用可视区域截图代替: {str(e)}")
                        
                        # 添加部分成功标记和警告说明
                        result["success"] = True  # 截图最终成功了，只是不是完整页面
                        result["warning"] = "全页面截图失败，已使用可视区域截图代替"
                        result["meta_data"]["screenshot_type"] = "visible_only"
                        result["meta_data"]["screenshot_size"] = os.path.getsize(screenshot_path)
                    except Exception as inner_e:
                        # 降级到DEBUG级别
                        logger.debug(f"{log_prefix} 可视区域截图也失败: {str(inner_e)}")
                        result["error"] = f"截图失败: {str(inner_e)}"
                        result["success"] = False
                else:
                    result["error"] = f"截图失败: {str(e)}"
                    result["success"] = False
            
        except Exception as e:
            error_msg = str(e)
            # 降级为DEBUG级别以避免在控制台显示详细错误
            logger.debug(f"{log_prefix} 处理URL时出错: {error_msg}")
            # 简化控制台显示的错误信息
            logger.info(f"{log_prefix} 页面加载失败")
            result["error"] = error_msg
        finally:
            # 关闭浏览器
            logger.debug(f"{log_prefix} 关闭浏览器")
            browser_close_start = time.time()
            browser.close()
            logger.debug(f"{log_prefix} 浏览器已关闭，耗时: {time.time() - browser_close_start:.2f}秒")
        
    # 计算总处理时间
    processing_time = time.time() - start_time
    result["processing_time"] = processing_time
    
    # 记录最终结果状态，降级控制台详细错误为简洁提示
    if result["error"]:
        # 详细错误记录在DEBUG级别
        logger.debug(f"{log_prefix} 处理完成: 失败 - {result['error']} (耗时: {processing_time:.2f}秒)")
        # 控制台只显示简洁信息
        logger.info(f"{log_prefix} 处理完成: 失败 (耗时: {processing_time:.2f}秒)")
    else:
        logger.info(f"{log_prefix} 处理完成: 成功 (耗时: {processing_time:.2f}秒)")
    
    return result


def ensure_content_loaded(page: Page):
    """使用更智能的方法确保页面内容加载完成（包括懒加载）"""
    logger = logging.getLogger("eyeurl")
    logger.debug("执行页面滚动以加载懒加载内容")
    
    try:
        # 执行自动滚动，触发懒加载内容，但限制滚动时间
        page.evaluate("""() => {
            return new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 300;
                const maxTime = 2000; // 最多滚动2秒
                const startTime = Date.now();
                
                const timer = setInterval(() => {
                    const scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    
                    // 如果已滚动到底部或超过时间限制，则停止
                    if(totalHeight >= scrollHeight || (Date.now() - startTime > maxTime)){
                        clearInterval(timer);
                        window.scrollTo(0, 0);  // 回到顶部
                        resolve();
                    }
                }, 100);
            });
        }""")  # 移除timeout参数，这是导致错误的原因
        logger.debug("页面滚动完成，已回到顶部")
    except Exception as e:
        logger.debug(f"滚动页面加载内容时出错: {str(e)}")  # 将warning改为debug级别
        # 忽略滚动过程中的错误


def collect_page_metadata(page: Page) -> Dict[str, Any]:
    """收集页面元数据"""
    logger = logging.getLogger("eyeurl")
    logger.debug("从页面收集元数据")
    
    try:
        meta_data = page.evaluate("""() => {
            const meta = {};
            
            // 收集meta标签信息
            document.querySelectorAll('meta').forEach(m => {
                if (m.name) meta[m.name] = m.content;
                else if (m.property) meta[m.property] = m.content;
            });
            
            // 收集页面基本信息
            meta.domain = window.location.hostname;
            meta.links = document.links.length;
            meta.images = document.images.length;
            meta.scripts = document.scripts.length;
            meta.forms = document.forms.length;
            meta.iframes = document.getElementsByTagName('iframe').length;
            
            // 收集性能指标
            if (window.performance) {
                const perf = window.performance;
                if (perf.timing) {
                    meta.load_time = perf.timing.loadEventEnd - perf.timing.navigationStart;
                    meta.dom_ready_time = perf.timing.domContentLoadedEventEnd - perf.timing.navigationStart;
                    meta.dns_time = perf.timing.domainLookupEnd - perf.timing.domainLookupStart;
                    meta.connect_time = perf.timing.connectEnd - perf.timing.connectStart;
                }
            }
            
            return meta;
        }""")
        
        logger.debug(f"元数据收集完成，包含 {len(meta_data)} 项信息")
        return meta_data
    except Exception as e:
        # 降级为DEBUG级别
        logger.debug(f"收集元数据时出错: {str(e)}")
        return {}


def worker_process(args: dict) -> Dict[str, Any]:
    """工作进程函数"""
    url = args["url"]
    screenshot_dir = args["screenshot_dir"]
    timeout = args["timeout"]
    width = args["width"]
    height = args["height"]
    wait_time = args["wait_time"]
    full_page = args["full_page"]
    user_agent = args["user_agent"]
    retry_count = args.get("retry_count", 1)
    network_timeout = args.get("network_timeout", 3)
    verbose = args.get("verbose", False)
    logger = args.get("logger")
    
    if logger is None:
        logger = logging.getLogger("eyeurl")
    
    # 为工作进程创建一个唯一标识符
    worker_id = args.get("worker_id", int(time.time() * 1000) % 10000)
    logger.debug(f"[Worker-{worker_id}] 开始处理URL: {url}")
    
    # 改进重试机制 - 增加随机回退
    import random
    
    # 实现重试机制
    for attempt in range(retry_count):
        if attempt > 0:
            logger.info(f"[Worker-{worker_id}] 第 {attempt + 1}/{retry_count} 次尝试处理: {url}")
        
        result = capture_url(
            url=url,
            screenshot_dir=screenshot_dir,
            timeout=timeout,
            width=width,
            height=height,
            wait_time=wait_time,
            full_page=full_page,
            user_agent=user_agent,
            network_timeout=network_timeout,
            logger=logger,
            verbose=verbose
        )
        
        # 如果成功或者已经是最后一次重试，则返回结果
        if not result["error"] or attempt == retry_count - 1:
            if attempt > 0 and not result["error"]:
                result["meta_data"]["retry_attempts"] = attempt + 1
                logger.info(f"[Worker-{worker_id}] 重试成功，总共尝试 {attempt + 1} 次")
            
            logger.debug(f"[Worker-{worker_id}] 完成处理: {url}")
            return result
            
        # 否则等待一段时间再重试，添加随机因子，避免同时重试
        retry_wait = 1 + attempt + random.uniform(0.5, 2.0)  # 增加随机等待时间
        logger.info(f"[Worker-{worker_id}] 处理失败，将在 {retry_wait:.1f} 秒后重试: {url}")
        time.sleep(retry_wait)
    
    # 这里不应该执行到，因为最后一次重试结果已经在循环中返回
    return result


def truncate_url(url, max_length=60):
    """截断URL以保持日志输出美观"""
    if len(url) <= max_length:
        return url
    
    # 保留开头和结尾，中间用...替代
    prefix_len = max_length // 2 - 2
    suffix_len = max_length - prefix_len - 3
    
    return f"{url[:prefix_len]}...{url[-suffix_len:]}"


def format_status_code(status_code):
    """格式化状态码，添加颜色标识"""
    from eyeurl.main import ConsoleColors
    
    if status_code >= 200 and status_code < 300:
        return f"{ConsoleColors.GREEN}{status_code}{ConsoleColors.ENDC}"
    elif status_code >= 300 and status_code < 400:
        return f"{ConsoleColors.YELLOW}{status_code}{ConsoleColors.ENDC}"
    elif status_code >= 400:
        return f"{ConsoleColors.RED}{status_code}{ConsoleColors.ENDC}"
    else:
        return f"{ConsoleColors.GRAY}未知{ConsoleColors.ENDC}"


def format_bytes(size_bytes):
    """格式化字节大小为可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.2f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"


def capture_urls_parallel(
    urls: List[str],
    screenshots_dir: Path, 
    timeout: int,
    width: int,
    height: int,
    wait_time: float,
    full_page: bool,
    threads: int,
    user_agent: Optional[str],
    logger: logging.Logger,
    retry_count: int = 1,
    network_timeout: int = 3,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """并行批量捕获URL的信息和截图"""
    # 初始化结果列表
    all_results = []
    
    logger.info(f"开始并行处理 {len(urls)} 个URL，使用 {threads} 个线程")
    
    # 创建进程池
    pool_size = min(threads, len(urls))
    logger.debug(f"创建进程池，大小: {pool_size}")
    
    # 准备参数列表
    args_list = []
    for i, url in enumerate(urls):
        args = {
            "url": url,
            "screenshot_dir": screenshots_dir,
            "timeout": timeout,
            "width": width,
            "height": height,
            "wait_time": wait_time,
            "full_page": full_page,
            "user_agent": user_agent,
            "retry_count": retry_count,
            "network_timeout": network_timeout,
            "verbose": verbose,
            "logger": logger,
            "worker_id": i + 1  # 使用递增的worker_id
        }
        args_list.append(args)
    
    # 创建共享管理器，用于在进程间共享进度
    logger.debug("初始化多进程共享管理器")
    progress_dict = multiprocessing.Manager().dict()
    progress_dict["completed"] = 0
    progress_dict["total"] = len(urls)
    progress_dict["success"] = 0
    progress_dict["failed"] = 0
    
    # 创建进程池
    logger.debug(f"启动进程池，开始处理 {len(urls)} 个URL")
    with multiprocessing.Pool(processes=pool_size) as pool:
        # 创建回调函数来更新计数
        def update_result_callback(result):
            # 更新完成计数
            progress_dict["completed"] = progress_dict["completed"] + 1
            
            # 根据结果更新成功/失败计数
            if result.get("error"):
                progress_dict["failed"] = progress_dict.get("failed", 0) + 1
            else:
                progress_dict["success"] = progress_dict.get("success", 0) + 1
        
        # 启动进程，使用新的回调函数
        result_objects = [pool.apply_async(worker_process, (args,), callback=update_result_callback) 
                         for args in args_list]
        
        logger.info(f"已分配 {len(urls)} 个任务到进程池")
        
        # 显示进度条
        with tqdm(total=len(urls), desc="正在截图", unit="URL", 
                 bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
            
            last_completed = 0
            avg_times = []
            
            while progress_dict["completed"] < len(urls):
                # 更新进度条
                completed = progress_dict["completed"]
                new_completed = completed - last_completed
                
                if new_completed > 0:
                    # 计算平均处理时间
                    current_time = time.time()
                    if 'last_update_time' in progress_dict:
                        elapsed = current_time - progress_dict['last_update_time']
                        avg_time_per_url = elapsed / new_completed
                        avg_times.append(avg_time_per_url)
                        # 保留最近10个样本计算平均值
                        if len(avg_times) > 10:
                            avg_times.pop(0)
                    
                    progress_dict['last_update_time'] = current_time
                    last_completed = completed
                
                pbar.n = completed
                
                # 添加成功/失败计数到进度条描述
                success = progress_dict.get("success", 0)
                failed = progress_dict.get("failed", 0)
                
                # 计算估计剩余时间
                if avg_times:
                    avg_time = sum(avg_times) / len(avg_times)
                    remaining_urls = len(urls) - completed
                    estimated_time = remaining_urls * avg_time
                    time_str = format_time(estimated_time)
                    pbar.set_description(f"正在截图 [成功: {success}, 失败: {failed}, 预计: {time_str}]")
                else:
                    pbar.set_description(f"正在截图 [成功: {success}, 失败: {failed}]")
                
                pbar.refresh()
                
                # 暂停一下，避免过度刷新
                time.sleep(0.1)
            
            # 确保进度条显示100%
            pbar.n = len(urls)
            
            # 更新最终的成功/失败计数
            success = progress_dict.get("success", 0)
            failed = progress_dict.get("failed", 0)
            if success > 0 or failed > 0:
                pbar.set_description(f"截图完成 [成功: {success}, 失败: {failed}]")
            
            pbar.refresh()
        
        # 收集结果
        logger.debug("正在收集并整理处理结果")
        results = []
        for i, result_obj in enumerate(result_objects):
            try:
                result = result_obj.get()
                results.append(result)
                
                # 只记录日志，不再更新计数（计数已经在回调函数中更新）
                url = urls[i]
                truncated_url = truncate_url(url)
                
                if result["error"]:
                    # 不再更新计数: progress_dict["failed"] = progress_dict.get("failed", 0) + 1
                    logger.error(f"截图失败: {truncated_url} - {result['error']}")
                else:
                    # 不再更新计数: progress_dict["success"] = progress_dict.get("success", 0) + 1
                    status_code = format_status_code(result["status_code"])
                    logger.debug(f"截图成功: {truncated_url} - 状态码: {status_code} - 耗时: {result['processing_time']:.2f}秒")
                
            except Exception as e:
                logger.error(f"处理URL时出错: {truncate_url(urls[i])} - {str(e)}")
                # 创建错误结果
                error_result = {
                    "url": urls[i],
                    "title": "",
                    "status_code": 0,
                    "content_size": 0,
                    "screenshot": "",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                    "response_headers": {},
                    "meta_data": {},
                    "processing_time": 0
                }
                results.append(error_result)
                # 这里还需要更新计数，因为这是在回调之后发生的异常
                progress_dict["failed"] = progress_dict.get("failed", 0) + 1
        
        # 现在计数已正确更新，输出URL处理完成日志
        logger.info(f"所有URL处理完成，成功: {progress_dict.get('success', 0)}，失败: {progress_dict.get('failed', 0)}")
    
        logger.debug(f"处理完成，总共 {len(results)} 个结果")
        avg_time = sum(r.get("processing_time", 0) for r in results) / len(results) if results else 0
        logger.info(f"处理完成，平均每URL耗时: {avg_time:.2f}秒")
    
    return results


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