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
import re
import traceback

from tqdm import tqdm
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

def read_urls(file_path: str) -> List[str]:
    """从文件中读取URL列表"""
    logger = logging.getLogger("eyeurl")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"正在打开URL文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"成功读取文件，共 {len(lines)} 行")
            
            # 过滤注释和空行
            urls = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
            if logger.isEnabledFor(logging.DEBUG):
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


async def wait_for_render_complete(page, logger: logging.Logger, max_wait_time: int = 15, check_interval: float = 0.5) -> bool:
    """等待页面渲染完成，通过检测DOM结构是否稳定来判断"""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("等待页面渲染稳定...")
    
    try:
        start_time = time.time()
        last_dom_size = 0
        stable_count = 0
        
        # 获取初始DOM大小
        last_dom_size = await get_dom_size(page)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"初始DOM大小: {last_dom_size}")
        
        while time.time() - start_time < max_wait_time:
            # 等待一小段时间
            await page.wait_for_timeout(check_interval * 1000)
            
            # 检查当前DOM大小
            current_dom_size = await get_dom_size(page)
            
            # 计算变化百分比
            if last_dom_size > 0:
                change_percent = abs(current_dom_size - last_dom_size) / last_dom_size * 100
            else:
                change_percent = 100 if current_dom_size > 0 else 0
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"当前DOM大小: {current_dom_size}, 变化: {change_percent:.2f}%")
            
            # 如果DOM大小变化很小，增加稳定计数
            if change_percent < 1.0:  # 变化小于1%
                stable_count += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"DOM结构稳定中 ({stable_count}/3)")
                if stable_count >= 3:  # 连续3次检查都稳定，认为渲染完成
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("页面渲染已稳定")
                    return True
            else:
                # 如果发现变化，重置稳定计数
                if stable_count > 0 and logger.isEnabledFor(logging.DEBUG):
                    logger.debug("DOM结构发生变化，重置稳定计数")
                stable_count = 0
            
            # 更新上次DOM大小
            last_dom_size = current_dom_size
        
        # 如果达到最大等待时间，返回当前状态
        elapsed = time.time() - start_time
        logger.info(f"等待渲染稳定超时，已等待 {elapsed:.1f} 秒，稳定计数: {stable_count}/3")
        return stable_count > 0  # 如果有任何稳定迹象，也算部分成功
    except Exception as e:
        logger.error(f"等待渲染完成时出错: {str(e)}")
        return False


async def take_screenshot(page, path, width, height, quality=80):
    """
    截取页面截图
    
    Args:
        page: 浏览器页面对象
        path: 截图保存路径
        width: 视窗宽度
        height: 视窗高度
        quality: 图片质量(1-100)
        
    Returns:
        bool: 截图是否成功
    """
    logger = logging.getLogger("eyeurl")
    
    try:
        # 设置视窗大小
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"设置视窗大小: {width}x{height}")
        await page.set_viewport_size({"width": width, "height": height})
        
        # 截取屏幕
        await page.screenshot(path=path, full_page=True, quality=quality)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"截图成功: {path}")
        return True
    except Exception as e:
        logger.error(f"截图失败: {str(e)}")
        return False


async def check_images_loaded(page, logger, timeout=5):
    """检查页面上的图片是否加载完成"""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("检查页面图片是否加载完成...")
    
    try:
        # 获取所有图片
        loaded_count, total_count = await get_image_loading_state(page)
        
        if total_count == 0:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("页面上没有找到图片元素")
            return True
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"图片加载状态: {loaded_count}/{total_count} 已加载")
        
        # 如果图片已全部加载，直接返回
        if loaded_count == total_count:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("所有图片已加载完成")
            return True
        
        # 尝试等待图片加载完成
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 短暂等待让更多图片加载
            await page.wait_for_timeout(500)
            
            # 再次检查图片加载状态
            new_loaded_count, new_total_count = await get_image_loading_state(page)
            
            # 如果图片数量或加载数量发生变化，更新日志
            if new_loaded_count != loaded_count or new_total_count != total_count:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"图片加载进度更新: {new_loaded_count}/{new_total_count}")
                loaded_count, total_count = new_loaded_count, new_total_count
            
            # 如果所有图片已加载，返回成功
            if loaded_count == total_count and total_count > 0:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"所有图片已加载完成，共 {total_count} 张")
                return True
            
        # 超时后，返回当前状态
        logger.info(f"图片加载超时，当前已加载 {loaded_count}/{total_count} 张图片")
        return loaded_count > 0 and loaded_count / total_count >= 0.8  # 如果80%以上的图片已加载，认为基本成功
    except Exception as e:
        logger.error(f"检查图片加载状态时出错: {str(e)}")
        return False


async def wait_for_page_load(page, timeout=30, wait_time=1.0, network_timeout=30):
    """
    等待页面加载完成
    
    Args:
        page: 浏览器页面对象
        timeout: 页面加载超时时间(秒)
        wait_time: 额外等待时间(秒)
        network_timeout: 网络空闲超时时间(秒)
        
    Returns:
        bool: 页面是否加载成功
    """
    logger = logging.getLogger("eyeurl")
    
    try:
        # 等待页面基本内容加载完成
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("等待DOMContentLoaded事件...")
            await page.wait_for_event('domcontentloaded', timeout=timeout * 1000)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("DOMContentLoaded事件已触发")
        except TimeoutError:
            logger.warning(f"等待DOMContentLoaded超时（{timeout}秒）")
            return False

        # 等待网络空闲
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"等待网络空闲（超时: {network_timeout}秒）...")
            await page.wait_for_load_state('networkidle', timeout=network_timeout * 1000)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("网络已空闲")
        except TimeoutError:
            logger.info("网络空闲等待超时，继续处理")
            # 这里不返回False，因为很多网站可能永远不会达到完全networkidle状态

        # 等待额外的时间，让页面渲染完成
        if wait_time > 0:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"额外等待 {wait_time} 秒让页面渲染...")
            await page.wait_for_timeout(wait_time * 1000)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("额外等待完成")

        # 等待load事件
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("等待Load事件...")
            await page.wait_for_load_state('load', timeout=timeout * 1000)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Load事件已触发")
        except TimeoutError:
            logger.warning(f"等待Load事件超时（{timeout}秒），但继续处理")
            # 继续处理，因为有些网站可能不会正确触发load事件

        return True
    except Exception as e:
        logger.error(f"等待页面加载时出错: {str(e)}")
        return False


async def get_image_loading_state(page):
    """获取页面图片加载状态"""
    return await page.evaluate("""() => {
        const images = Array.from(document.querySelectorAll('img'));
        const loadedImages = images.filter(img => img.complete);
        return [loadedImages.length, images.length];
    }""")


async def get_dom_size(page):
    """获取页面DOM大小"""
    return await page.evaluate("""() => {
        return document.documentElement.outerHTML.length;
    }""")


async def capture_url(
    browser_config,
    url: str,
    output_dir: Path,
    filename: str = None,
    width: int = 1280,
    height: int = 800,
    wait_time: int = 2000,
    quality: int = 90,
    get_metadata: bool = True,
    timeout: int = 60000,
) -> dict:
    """
    访问URL并截取屏幕截图
    
    Args:
        browser_config: 浏览器配置
        url: 目标URL
        output_dir: 输出目录
        filename: 截图文件名（可选，默认使用URL的安全文件名）
        width: 视窗宽度
        height: 视窗高度
        wait_time: 额外等待时间(毫秒)
        quality: 图片质量(1-100)
        get_metadata: 是否获取页面元数据
        timeout: 总超时时间(毫秒)
        
    Returns:
        dict: 包含截图路径和状态的字典
    """
    logger = logging.getLogger("eyeurl")
    start_time = time.time()
    
    # 记录开始处理URL
    logger.info(f"处理URL: {url}")
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 如果没有提供文件名，使用URL生成安全的文件名
    if not filename:
        safe_url = re.sub(r'[^\w\-_.]', '_', url.replace('://', '_').replace('/', '_'))
        filename = f"{safe_url[:240]}.jpg"  # 限制文件名长度，避免路径过长问题
    
    # 设置截图保存路径
    screenshot_path = output_dir / filename
    
    # 初始化元数据
    metadata = {
        "url": url,
        "screenshot": str(screenshot_path),
        "timestamp": datetime.now().isoformat(),
        "success": False
    }
    
    browser = None
    page = None
    
    try:
        # 创建浏览器实例
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("创建浏览器上下文")
        browser = await sync_playwright().chromium.launch(**browser_config)
        context = await browser.new_context(viewport={"width": width, "height": height})
        
        # 创建新页面
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("创建新页面")
        page = await context.new_page()
        
        # 设置页面超时
        page.set_default_timeout(timeout)
        
        # 导航到URL
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"导航到URL: {url}")
        response = await page.goto(url, wait_until="commit", timeout=timeout)
        
        if not response:
            logger.error(f"无法加载页面: {url}")
            return metadata
        
        status = response.status
        metadata["status_code"] = status
        
        if status >= 400:
            logger.warning(f"页面返回错误状态码: {status}")
        
        # 等待页面加载 - 使用多级等待策略
        # 1. 首先等待DOM内容加载
        if not await wait_for_page_load(page, timeout=30, wait_time=1.0, network_timeout=30):
            logger.warning("DOM内容加载超时，尝试备选加载策略")
        
        # 2. 然后等待网络活动停止
        if not await wait_for_page_load(page, timeout=30, wait_time=1.0, network_timeout=30):
            logger.warning("等待网络活动停止超时，尝试备选加载策略")
        
        # 3. 最后等待load事件
        if not await wait_for_page_load(page, timeout=30, wait_time=1.0, network_timeout=30):
            logger.warning("等待load事件超时")
            
        # 等待body元素可见
        try:
            await page.wait_for_selector("body", state="visible", timeout=10000)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("等待body元素完成")
        except Exception as e:
            logger.warning(f"等待body元素超时: {str(e)}")
        
        # 检查页面可见性
        try:
            visible = await page.evaluate("""() => {
                return document.visibilityState === 'visible';
            }""")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"页面可见性状态: {'可见' if visible else '不可见'}")
        except Exception as e:
            logger.warning(f"检查页面可见性失败: {str(e)}")
        
        # 处理懒加载内容 - 滚动页面以触发懒加载
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("处理懒加载内容 - 滚动页面")
            await page.evaluate("""() => {
                return new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 300;
                    const scrollDown = () => {
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        
                        if (totalHeight >= document.body.scrollHeight) {
                            window.scrollTo(0, 0);  // 滚回顶部
                            resolve();
                        } else {
                            setTimeout(scrollDown, 100);
                        }
                    };
                    scrollDown();
                });
            }""")
        
        # 检查图片是否加载完成
        await check_images_loaded(page, logger)
        
        # 等待页面渲染稳定
        stable = await wait_for_render_complete(page, logger)
        if not stable:
            logger.warning("页面渲染未稳定，可能影响截图质量")
        
        # 额外等待一定时间，确保动画和其他视觉元素完成
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"额外等待 {wait_time}ms")
            await page.wait_for_timeout(wait_time)
        
        # 获取页面元数据
        if get_metadata:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("收集元数据")
            try:
                title = await page.title()
                metadata["title"] = title
                
                # 获取页面描述
                description = await page.evaluate("""() => {
                    const meta = document.querySelector('meta[name="description"]');
                    return meta ? meta.getAttribute('content') : '';
                }""")
                metadata["description"] = description
                
                # 获取favicon
                favicon = await page.evaluate("""() => {
                    const link = document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
                    return link ? link.href : '';
                }""")
                metadata["favicon"] = favicon
            except Exception as e:
                logger.warning(f"获取元数据失败: {str(e)}")
        
        # 截取屏幕截图
        success = await take_screenshot(page, str(screenshot_path), width, height, quality)
        metadata["success"] = success
        
        if success:
            logger.info(f"URL处理完成: {url}")
        else:
            logger.error(f"URL截图失败: {url}")
        
    except Exception as e:
        logger.error(f"处理URL时出错: {url}, 错误: {str(e)}")
        traceback.print_exc()
    finally:
        # 关闭页面和浏览器
        if page:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("关闭页面")
            await page.close()
        if browser:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("关闭浏览器")
            await browser.close()
        
        # 计算处理时间
        elapsed_time = time.time() - start_time
        metadata["processing_time"] = elapsed_time
        logger.info(f"URL处理耗时: {elapsed_time:.2f}秒 - {url}")
        
        return metadata


def ensure_content_loaded(page: Page):
    """使用更智能的方法确保页面内容加载完成（包括懒加载）"""
    logger = logging.getLogger("eyeurl")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("执行页面滚动以加载懒加载内容")
    
    try:
        # 改进：增强的内容加载检查
        # 1. 先执行页面滚动以激活懒加载内容
        page.evaluate("""() => {
            return new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 300;
                const maxTime = 3000; // 延长到3秒
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
        }""")
        
        # 2. 等待图片和背景图片资源加载完成 - 增强版
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("等待图片资源加载，包括背景图片")
            page.evaluate("""() => {
                return new Promise((resolve) => {
                    const maxWaitTime = 10000; // 增加到10秒
                    const startTime = Date.now();
                    
                    // 收集页面上所有元素的背景图片URLs
                    const getBackgroundImageUrls = () => {
                        const urls = new Set();
                        const allElements = document.querySelectorAll('*');
                        
                        for (const el of allElements) {
                            const style = window.getComputedStyle(el);
                            const bgImage = style.backgroundImage;
                            
                            if (bgImage && bgImage !== 'none') {
                                // 解析url("...")格式
                                const match = bgImage.match(/url\\(['"]?([^'"\\)]+)['"]?\\)/i);
                                if (match && match[1]) {
                                    urls.add(match[1]);
                                }
                            }
                        }
                        
                        return Array.from(urls);
                    };
                    
                    // 检查图片是否已加载
                    const checkAllImagesLoaded = () => {
                        // 检查<img>标签
                        const imgs = Array.from(document.images);
                        const pendingImgs = imgs.filter(img => !img.complete);
                        
                        // 检查CSS背景图片
                        let backgroundImgsPending = false;
                        try {
                            const bgUrls = getBackgroundImageUrls();
                            if (bgUrls.length > 0) {
                                // 如果有背景图片，简单等待，因为无法直接检查它们的加载状态
                                // 这里我们假设，如果DOM已稳定且主要图片已加载，背景图片也大概加载了
                                backgroundImgsPending = (Date.now() - startTime < 2000); // 至少等待2秒给背景图片
                            }
                        } catch (e) {
                            console.log('背景图片检查出错:', e);
                        }
                        
                        // 检查是否有pending的资源（仅在开发者工具开启时可用）
                        let hasPendingResources = false;
                        if (window.performance && window.performance.getEntriesByType) {
                            try {
                                const resources = window.performance.getEntriesByType('resource');
                                const imageResources = resources.filter(r => 
                                    r.initiatorType === 'img' || 
                                    (r.name && (r.name.endsWith('.jpg') || r.name.endsWith('.jpeg') || 
                                              r.name.endsWith('.png') || r.name.endsWith('.gif') ||
                                              r.name.endsWith('.webp')))
                                );
                                
                                // 检查是否所有图片资源都已完成加载
                                const incompleteResources = imageResources.filter(r => 
                                    r.responseEnd === 0 || !r.responseEnd
                                );
                                
                                hasPendingResources = incompleteResources.length > 0;
                            } catch (e) {
                                console.log('资源加载检查出错:', e);
                            }
                        }
                        
                        return pendingImgs.length === 0 && !backgroundImgsPending && !hasPendingResources;
                    };
                    
                    // 定期检查图片加载状态
                    const checkInterval = setInterval(() => {
                        // 超时检查
                        if (Date.now() - startTime > maxWaitTime) {
                            clearInterval(checkInterval);
                            console.log('图片加载等待超时，继续处理');
                            resolve();
                            return;
                        }
                        
                        // 检查图片是否都已加载
                        if (checkAllImagesLoaded()) {
                            clearInterval(checkInterval);
                            console.log('所有图片资源已加载完成');
                            resolve();
                        }
                    }, 300);
                });
            }""", timeout=12000)  // 超时增加到12秒
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("所有图片资源加载完成")
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"等待图片资源加载时超时或出错: {str(e)}")
        
        # 3. 等待动画完成
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("等待页面动画完成")
            page.evaluate("""() => {
                return new Promise((resolve) => {
                    // 给页面上的动画更多时间完成
                    setTimeout(resolve, 800);  // 增加到800ms
                });
            }""")
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"等待动画完成时出错: {str(e)}")
            
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("页面内容加载检查完成，已回到顶部")
    except Exception as e:
        # 降级为DEBUG级别
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"检查页面内容加载时出错: {str(e)}")
        # 忽略过程中的错误，继续执行


def collect_page_metadata(page: Page) -> Dict[str, Any]:
    """收集页面元数据"""
    logger = logging.getLogger("eyeurl")
    if logger.isEnabledFor(logging.DEBUG):
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
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"元数据收集完成，包含 {len(meta_data)} 项信息")
        return meta_data
    except Exception as e:
        # 降级为DEBUG级别
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"收集元数据时出错: {str(e)}")
        return {}


def capture_url_sync(
    url: str,
    screenshot_dir: Path,
    timeout: int = 30,
    width: int = 1280,
    height: int = 800,
    wait_time: float = 0,
    full_page: bool = False,
    user_agent: Optional[str] = None,
    network_timeout: int = 3,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """
    访问URL并截取屏幕截图（同步版本）
    
    Args:
        url: 目标URL
        screenshot_dir: 截图保存目录
        timeout: 页面加载超时时间(秒)
        width: 视窗宽度
        height: 视窗高度
        wait_time: 额外等待时间(秒)
        full_page: 是否截取整个页面
        user_agent: 自定义User-Agent
        network_timeout: 网络空闲超时时间(秒)
        logger: 日志记录器
        
    Returns:
        dict: 包含截图路径和状态的字典
    """
    if logger is None:
        logger = logging.getLogger("eyeurl")
    
    start_time = time.time()
    # 设置绝对超时保护 - 无论如何，一个URL最多处理这么长时间
    absolute_timeout = min(120, timeout * 3)  # 最多2分钟或3倍timeout
    
    # 记录开始处理URL
    logger.info(f"处理URL: {url}")
    
    # 确保输出目录存在
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成安全的文件名
    safe_url = re.sub(r'[^\w\-_.]', '_', url.replace('://', '_').replace('/', '_'))
    filename = f"{safe_url[:240]}.jpg"  # 限制文件名长度，避免路径过长问题
    
    # 设置截图保存路径
    screenshot_path = screenshot_dir / filename
    
    # 初始化元数据
    metadata = {
        "url": url,
        "screenshot": filename,  # 只存储文件名，不包含路径
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "meta_data": {}
    }
    
    try:
        with sync_playwright() as playwright:
            # 创建浏览器实例
            browser_options = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                "timeout": timeout * 1000  # 设置浏览器启动超时
            }
            
            # 添加自定义UA（如果提供）
            if user_agent:
                browser_options["user_agent"] = user_agent
            
            browser = playwright.chromium.launch(**browser_options)
            
            # 使用小的超时为context设置
            context = browser.new_context(
                viewport={"width": width, "height": height},
                # 减少内存使用，提高稳定性
                has_touch=False,
                java_script_enabled=True,
                bypass_csp=True  # 绕过内容安全策略
            )
            
            # 创建新页面
            page = context.new_page()
            page.set_default_timeout(timeout * 1000)  # 毫秒
            
            # 设置请求超时
            page.set_default_navigation_timeout(timeout * 1000)
            
            # 导航到URL，使用try-except捕获可能的错误
            try:
                response = page.goto(
                    url, 
                    wait_until="commit", 
                    timeout=timeout * 1000
                )
                
                if not response:
                    logger.error(f"无法加载页面: {url}")
                    metadata["error"] = "页面无响应"
                    return metadata
                
                status_code = response.status
                metadata["status_code"] = status_code
                
                if status_code >= 400:
                    if logger.isEnabledFor(logging.INFO):
                        logger.info(f"页面返回错误状态码: {status_code}")
                    metadata["error"] = f"HTTP错误: {status_code}"
            except Exception as e:
                logger.error(f"导航到URL时出错: {url} - {str(e)}")
                metadata["error"] = f"导航错误: {str(e)}"
                return metadata
            
            # 使用更有弹性的等待策略
            load_success = True
            
            # 等待页面基本内容加载完成
            try:
                page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("DOM内容加载完成")
            except Exception as e:
                load_success = False
                if logger.isEnabledFor(logging.INFO):
                    logger.info(f"等待DOM内容加载超时: {str(e)}")
            
            # 检查是否已经超过绝对超时，如果是则提前返回
            if time.time() - start_time > absolute_timeout:
                logger.warning(f"处理URL超过最大允许时间({absolute_timeout}秒)，提前终止: {url}")
                metadata["error"] = f"处理超时: 超过{absolute_timeout}秒"
                return metadata
            
            # 等待网络活动停止 - 使用较短的超时
            try:
                page.wait_for_load_state("networkidle", timeout=network_timeout * 1000)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("网络活动已停止")
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"等待网络空闲超时: {str(e)}")
            
            # 再次检查是否已经超过绝对超时
            if time.time() - start_time > absolute_timeout:
                logger.warning(f"处理URL超过最大允许时间({absolute_timeout}秒)，提前终止: {url}")
                metadata["error"] = f"处理超时: 超过{absolute_timeout}秒"
                return metadata
            
            # 等待load事件
            try:
                page.wait_for_load_state("load", timeout=min(10, timeout) * 1000)  # 最多等待10秒
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("页面加载完成")
            except Exception as e:
                if logger.isEnabledFor(logging.INFO):
                    logger.info(f"等待load事件超时: {str(e)}")
            
            # 等待body元素可见 - 减少超时时间
            try:
                page.wait_for_selector("body", state="visible", timeout=5000)  # 降低到5秒
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("页面body元素可见")
            except Exception as e:
                # 降低日志级别，避免控制台垃圾信息
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"等待body元素超时")
            
            # 滚动页面以加载懒加载内容，但设置最大执行时间
            try:
                # 使用带超时的evaluate
                page.evaluate("""() => {
                    return new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 300;
                        const maxTime = 5000; // 最多5秒
                        const startTime = Date.now();
                        
                        const scrollDown = () => {
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            
                            // 如果已滚动到底部或超过时间限制，则停止
                            if (totalHeight >= document.body.scrollHeight || (Date.now() - startTime > maxTime)) {
                                window.scrollTo(0, 0);  // 滚回顶部
                                resolve();
                            } else {
                                setTimeout(scrollDown, 100);
                            }
                        };
                        scrollDown();
                    });
                }""", timeout=7000)  # 7秒超时
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"页面滚动超时或出错")
            
            # 检查是否已经超过绝对超时
            if time.time() - start_time > absolute_timeout:
                logger.warning(f"处理URL超过最大允许时间({absolute_timeout}秒)，提前终止: {url}")
                metadata["error"] = f"处理超时: 超过{absolute_timeout}秒"
                # 尝试在超时前截图
                try:
                    page.screenshot(path=str(screenshot_path), full_page=full_page, timeout=5000)
                    metadata["success"] = True
                    metadata["partial"] = True  # 标记为部分完成
                    logger.info(f"在超时前获取了部分截图: {url}")
                except Exception:
                    pass
                return metadata
            
            # 额外等待，但不超过指定时间
            actual_wait_time = min(wait_time, 5.0)  # 最多等待5秒
            if actual_wait_time > 0:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"额外等待 {actual_wait_time} 秒")
                time.sleep(actual_wait_time)
            
            # 获取页面标题
            try:
                title = page.title()
                metadata["title"] = title
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"获取页面标题失败")
            
            # 截图
            try:
                page.screenshot(path=str(screenshot_path), full_page=full_page, timeout=10000)
                metadata["success"] = True
                logger.info(f"截图成功: {url}")
            except Exception as e:
                logger.error(f"截图失败: {url} - {str(e)}")
                metadata["error"] = f"截图错误: {str(e)}"
            
            # 关闭资源
            try:
                page.close(timeout=5000)
            except:
                pass
                
            try:
                browser.close()
            except:
                pass
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"处理URL时出错: {url} - {error_msg}")
        metadata["error"] = error_msg
        
    # 计算处理时间
    elapsed_time = time.time() - start_time
    metadata["processing_time"] = elapsed_time
    
    # 如果处理时间过长，记录为警告
    if elapsed_time > timeout:
        logger.warning(f"URL处理耗时过长: {elapsed_time:.2f}秒 - {url}")
    else:
        logger.info(f"URL处理耗时: {elapsed_time:.2f}秒 - {url}")
    
    return metadata


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
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"[Worker-{worker_id}] 开始处理URL: {url}")
    
    # 改进重试机制 - 增加随机回退
    import random
    
    # 实现重试机制
    for attempt in range(retry_count):
        if attempt > 0:
            logger.info(f"[Worker-{worker_id}] 第 {attempt + 1}/{retry_count} 次尝试处理: {url}")
        
        # 使用同步版本的capture_url函数
        result = capture_url_sync(
            url=url,
            screenshot_dir=screenshot_dir,
            timeout=timeout,
            width=width,
            height=height,
            wait_time=wait_time,
            full_page=full_page,
            user_agent=user_agent,
            network_timeout=network_timeout,
            logger=logger
        )
        
        # 如果成功或者已经是最后一次重试，则返回结果
        if not result.get("error") or attempt == retry_count - 1:
            if attempt > 0 and not result.get("error"):
                if "meta_data" not in result:
                    result["meta_data"] = {}
                result["meta_data"]["retry_attempts"] = attempt + 1
                logger.info(f"[Worker-{worker_id}] 重试成功，总共尝试 {attempt + 1} 次")
            
            if logger.isEnabledFor(logging.DEBUG):
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
    
    # 记录总处理开始时间
    total_start_time = time.time()
    
    # 创建进程池
    pool_size = min(threads, len(urls))
    if logger.isEnabledFor(logging.DEBUG):
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
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("初始化多进程共享管理器")
    progress_dict = multiprocessing.Manager().dict()
    progress_dict["completed"] = 0
    progress_dict["total"] = len(urls)
    progress_dict["success"] = 0
    progress_dict["failed"] = 0
    progress_dict["batch_start_time"] = time.time()  # 记录批处理开始时间
    
    # 创建进程池
    if logger.isEnabledFor(logging.DEBUG):
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
            
            # 计算并更新当前的批处理总耗时
            progress_dict["current_batch_time"] = time.time() - progress_dict["batch_start_time"]
        
        # 启动进程，使用新的回调函数
        result_objects = [pool.apply_async(worker_process, (args,), callback=update_result_callback) 
                         for args in args_list]
        
        logger.info(f"已分配 {len(urls)} 个任务到进程池")
        
        # 显示进度条
        with tqdm(total=len(urls), desc="正在截图", unit="URL", 
                 bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
            
            last_completed = 0
            avg_times = []
            max_wait_time = 3 * 60  # 最多等待3分钟
            start_wait_time = time.time()
            
            # 循环等待任务完成，但设置最大等待时间
            while progress_dict["completed"] < len(urls):
                # 检查是否已等待太久
                if time.time() - start_wait_time > max_wait_time:
                    logger.warning(f"等待任务完成超过{max_wait_time}秒，提前退出等待")
                    break
                
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
                
                # 当前批处理耗时
                current_total_time = progress_dict.get("current_batch_time", time.time() - total_start_time)
                
                # 计算估计剩余时间
                if avg_times:
                    avg_time = sum(avg_times) / len(avg_times)
                    remaining_urls = len(urls) - completed
                    estimated_time = remaining_urls * avg_time
                    time_str = format_time(estimated_time)
                    total_time_str = format_time(current_total_time)
                    pbar.set_description(f"正在截图 [成功: {success}, 失败: {failed}, 已耗时: {total_time_str}, 剩余: {time_str}]")
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
                final_total_time = time.time() - total_start_time
                total_time_str = format_time(final_total_time)
                pbar.set_description(f"截图完成 [成功: {success}, 失败: {failed}, 总耗时: {total_time_str}]")
            
            pbar.refresh()
        
        # 收集结果
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("正在收集并整理处理结果")
        results = []
        total_processing_time = 0
        
        # 设置结果获取的超时
        result_timeout = 10  # 10秒
        
        for i, result_obj in enumerate(result_objects):
            try:
                # 使用超时获取结果，避免卡住
                result = result_obj.get(timeout=result_timeout)
                results.append(result)
                
                # 累计处理时间
                total_processing_time += result.get("processing_time", 0)
                
                # 只记录日志，不再更新计数（计数已经在回调函数中更新）
                url = urls[i]
                truncated_url = truncate_url(url)
                
                if result.get("error"):
                    logger.error(f"截图失败: {truncated_url} - {result.get('error')}")
                else:
                    if logger.isEnabledFor(logging.DEBUG):
                        status_code = format_status_code(result.get("status_code", 0))
                        logger.debug(f"截图成功: {truncated_url} - 状态码: {status_code} - 耗时: {result.get('processing_time', 0):.2f}秒")
                
            except multiprocessing.TimeoutError:
                logger.error(f"获取任务结果超时: {truncate_url(urls[i])}")
                # 创建超时错误结果
                error_result = {
                    "url": urls[i],
                    "title": "",
                    "status_code": 0,
                    "content_size": 0,
                    "screenshot": "",
                    "timestamp": datetime.now().isoformat(),
                    "error": "获取任务结果超时",
                    "response_headers": {},
                    "meta_data": {},
                    "processing_time": 0
                }
                results.append(error_result)
                
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
        
        # 如果结果数量少于URL数量，补充缺失的结果
        if len(results) < len(urls):
            logger.warning(f"结果数量({len(results)})少于预期({len(urls)})，补充缺失的结果")
            # 创建URL集合，找出缺失的URL
            processed_urls = {r["url"] for r in results}
            for url in urls:
                if url not in processed_urls:
                    error_result = {
                        "url": url,
                        "title": "",
                        "status_code": 0,
                        "content_size": 0,
                        "screenshot": "",
                        "timestamp": datetime.now().isoformat(),
                        "error": "任务结果丢失",
                        "response_headers": {},
                        "meta_data": {},
                        "processing_time": 0
                    }
                    results.append(error_result)
        
        # 计算实际总耗时 - 这是控制台输出的标准
        total_elapsed_time = time.time() - total_start_time
        
        # 创建用于报告的耗时数据字典 - 保持一致性
        batch_time_info = {
            "total_time_seconds": total_elapsed_time,  
            "total_time_formatted": format_time(total_elapsed_time),
            "processing_time": total_processing_time,
            "parallel_efficiency": (total_processing_time / (total_elapsed_time * pool_size)) * 100 if total_processing_time > 0 and total_elapsed_time > 0 else 0,
            "average_url_time": total_processing_time/len(results) if len(results) > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        # 只保留处理完成日志，删除详细的报告输出
        logger.info(f"所有URL处理完成，成功: {progress_dict.get('success', 0)}，失败: {progress_dict.get('failed', 0)}")
    
        # 创建批处理结果信息字典 - 将直接添加到结果中
        batch_info = {
            "total_urls": len(urls),
            "total_success": progress_dict.get("success", 0),
            "total_failed": progress_dict.get("failed", 0),
            "batch_time": batch_time_info  # 使用一致的时间信息
        }
        
        # 将批处理信息添加到结果中，便于报告生成
        for result in results:
            if "meta_data" not in result:
                result["meta_data"] = {}
            result["meta_data"]["batch_info"] = batch_info
    
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