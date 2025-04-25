import datetime
import time
import os
import re
from urllib.parse import urljoin
from tqdm import tqdm
import colorama
from playwright.sync_api import sync_playwright

def process_url(url, options, visited_urls=None, level=0, parent_url=None):
    """
    处理单个URL，截图并可选地递归处理其中的链接
    
    Args:
        url: 要处理的URL
        options: 选项字典
        visited_urls: 已访问URL集合（用于避免重复）
        level: 当前深度级别
        parent_url: 父URL（用于显示引用关系）
    
    Returns:
        包含处理结果的字典
    """
    if visited_urls is None:
        visited_urls = set()
    
    # 避免重复处理相同URL
    url_key = canonicalize_url(url)
    if url_key in visited_urls:
        logger.info(f"{colorama.Fore.YELLOW}⟲ {url} - 已处理，跳过{colorama.Style.RESET_ALL}")
        return None
    
    # 截断过长URL以便显示
    display_url = truncate_url(url, max_length=80)
    
    # 父URL 显示
    parent_info = ""
    if parent_url:
        parent_display = truncate_url(parent_url, max_length=50)
        parent_info = f"{colorama.Fore.BLUE}← {parent_display}{colorama.Style.RESET_ALL}"
    
    # 缩进和深度显示
    indent = "  " * level
    depth_marker = f"{colorama.Fore.CYAN}[深度:{level}]{colorama.Style.RESET_ALL}"
    
    logger.info(f"{indent}{depth_marker} {colorama.Fore.WHITE}🌐 处理: {colorama.Fore.GREEN}{display_url}{colorama.Style.RESET_ALL} {parent_info}")
    
    # 创建结果字典
    result = {
        'url': url,
        'referrer': parent_url,
        'timestamp': datetime.datetime.now().isoformat(),
        'depth_level': level
    }
    
    # 添加到已访问集合
    visited_urls.add(url_key)
    
    # 基本的异常处理，确保一个URL的失败不会导致整个爬虫停止
    try:
        # 创建浏览器上下文
        with sync_playwright() as p:
            browser_type = getattr(p, options.get('browser', 'chromium'))
            browser = browser_type.launch(headless=not options.get('non_headless', False))
            context = browser.new_context(
                viewport={'width': options.get('width', 1280), 'height': options.get('height', 720)},
                user_agent=options.get('user_agent')
            )
            
            # 创建新页面
            page = context.new_page()
            
            # 监听控制台消息
            if options.get('log_console', False):
                page.on("console", lambda msg: logger.debug(f"浏览器控制台: {msg.text}"))
            
            # 请求和响应拦截器，用于收集网络信息
            request_start_times = {}
            response_data = {}
            
            page.on("request", lambda request: request_start_times.update({request.url: time.time()}))
            
            def handle_response(response):
                url = response.url
                if url in request_start_times:
                    response_time = time.time() - request_start_times[url]
                    status = response.status
                    # 记录响应信息
                    response_data[url] = {
                        'status': status,
                        'time': response_time,
                        'content_type': response.headers.get('content-type', '')
                    }
            
            page.on("response", handle_response)
            
            # 设置超时
            timeout = options.get('timeout', 30000)  # 默认30秒
            
            # 导航到URL
            try:
                load_start = time.time()
                response = page.goto(url, timeout=timeout, wait_until=options.get('wait_until', 'networkidle'))
                load_time = time.time() - load_start
                
                # 获取响应状态码
                status_code = response.status if response else None
                status_text = f"{status_code} {response.status_text}" if response else "未知"
                
                # 根据状态码设置颜色
                if status_code and 200 <= status_code < 300:
                    status_color = f"{colorama.Fore.GREEN}✓ {status_text}{colorama.Style.RESET_ALL}"
                elif status_code and 300 <= status_code < 400:
                    status_color = f"{colorama.Fore.YELLOW}↪ {status_text}{colorama.Style.RESET_ALL}"
                elif status_code and status_code >= 400:
                    status_color = f"{colorama.Fore.RED}✗ {status_text}{colorama.Style.RESET_ALL}"
                else:
                    status_color = f"{colorama.Fore.MAGENTA}? 状态未知{colorama.Style.RESET_ALL}"
                
                # 记录状态和加载时间
                logger.info(f"{indent}  {status_color} 加载时间: {colorama.Fore.CYAN}{load_time:.2f}s{colorama.Style.RESET_ALL}")
                
                result['status_code'] = status_code
                result['status_text'] = response.status_text if response else "未知"
                result['load_time'] = load_time
                result['content_type'] = response.headers.get('content-type', '') if response else ""
                
                # 如果是重定向，记录最终URL
                final_url = page.url
                if final_url != url:
                    result['redirected_to'] = final_url
                    redirect_display = truncate_url(final_url, max_length=80)
                    logger.info(f"{indent}  {colorama.Fore.YELLOW}➤ 重定向到: {redirect_display}{colorama.Style.RESET_ALL}")
                
                # 等待额外时间
                extra_wait = options.get('extra_wait', 0)
                if extra_wait > 0:
                    page.wait_for_timeout(extra_wait)
                
                # 截图
                screenshot_path = None
                if options.get('screenshots', True):
                    screenshot_dir = options.get('screenshot_dir', 'screenshots')
                    os.makedirs(screenshot_dir, exist_ok=True)
                    
                    # 使用URL创建文件名
                    safe_filename = re.sub(r'[^\w\-_.]', '_', url_key)[:200]
                    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    screenshot_filename = f"{safe_filename}_{timestamp}.png"
                    screenshot_path = os.path.join(screenshot_dir, screenshot_filename)
                    
                    # 全页面截图
                    if options.get('full_page', False):
                        page.screenshot(path=screenshot_path, full_page=True)
                    else:
                        page.screenshot(path=screenshot_path)
                    
                    logger.info(f"{indent}  {colorama.Fore.BLUE}📸 截图保存到: {screenshot_path}{colorama.Style.RESET_ALL}")
                    result['screenshot'] = screenshot_path
                
                # 获取页面标题
                title = page.title()
                if title:
                    result['title'] = title
                    logger.info(f"{indent}  {colorama.Fore.WHITE}📄 标题: {colorama.Fore.CYAN}\"{title}\"{colorama.Style.RESET_ALL}")
                
                # 收集网络统计信息
                result['resources'] = []
                for res_url, res_data in response_data.items():
                    result['resources'].append({
                        'url': res_url,
                        'status': res_data.get('status'),
                        'time': res_data.get('time'),
                        'content_type': res_data.get('content_type')
                    })
                
                # 收集页面上的链接
                links = []
                if options.get('recursive', False) and level < options.get('max_depth', 1):
                    try:
                        # 获取所有链接
                        link_elements = page.query_selector_all('a[href]')
                        domain = extract_domain(url)
                        
                        for element in link_elements:
                            href = element.get_attribute('href')
                            if href:
                                # 尝试构建绝对URL
                                try:
                                    absolute_url = urljoin(url, href)
                                    link_domain = extract_domain(absolute_url)
                                    
                                    # 根据选项过滤链接
                                    if options.get('same_domain', True) and link_domain != domain:
                                        continue
                                    
                                    # 检查URL模式
                                    url_pattern = options.get('url_pattern')
                                    if url_pattern and not re.search(url_pattern, absolute_url):
                                        continue
                                    
                                    links.append(absolute_url)
                                except Exception as e:
                                    logger.warning(f"解析链接失败: {href} - {str(e)}")
                        
                        logger.info(f"{indent}  {colorama.Fore.YELLOW}🔗 发现 {len(links)} 个链接{colorama.Style.RESET_ALL}")
                        
                    except Exception as e:
                        logger.error(f"提取链接时出错: {str(e)}")
                
                # 关闭浏览器
                browser.close()
                
                # 递归处理链接
                child_results = []
                if links and options.get('recursive', False) and level < options.get('max_depth', 1):
                    logger.info(f"{indent}  {colorama.Fore.CYAN}▼ 开始处理子链接 ({len(links)}){colorama.Style.RESET_ALL}")
                    
                    # 显示进度条
                    with tqdm(total=len(links), desc=f"{indent}    链接进度", unit="链接", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]', disable=options.get('quiet', False)) as pbar:
                        for link in links:
                            child_result = process_url(link, options, visited_urls, level+1, url)
                            if child_result:
                                child_results.append(child_result)
                            pbar.update(1)
                    
                    logger.info(f"{indent}  {colorama.Fore.CYAN}▲ 子链接处理完成{colorama.Style.RESET_ALL}")
                
                result['child_urls'] = child_results
                
            except TimeoutError:
                logger.error(f"{indent}  {colorama.Fore.RED}⏱ 超时: {url}{colorama.Style.RESET_ALL}")
                result['error'] = "页面加载超时"
                browser.close()
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"{indent}  {colorama.Fore.RED}❌ 处理URL时出错: {error_msg}{colorama.Style.RESET_ALL}")
        result['error'] = error_msg
    
    return result 