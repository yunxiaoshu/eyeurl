#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告模块 - 负责生成HTML报告
"""

import os
import json
import shutil
import logging
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


# 定义资源文件清单，与download_resources.py中保持一致
RESOURCE_FILES = [
    {"local_path": "css/bootstrap.min.css", "cdn_url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css"},
    {"local_path": "css/bootstrap-icons.css", "cdn_url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.3/font/bootstrap-icons.css"},
    {"local_path": "js/bootstrap.bundle.min.js", "cdn_url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"},
    {"local_path": "css/fonts/bootstrap-icons.woff", "cdn_url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.3/font/fonts/bootstrap-icons.woff"},
    {"local_path": "css/fonts/bootstrap-icons.woff2", "cdn_url": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.3/font/fonts/bootstrap-icons.woff2"},
    # 添加美化相关的库文件
    {"local_path": "js/highlight.min.js", "cdn_url": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"},
    {"local_path": "css/highlight.min.css", "cdn_url": "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css"}
]

# 需要确保本地复制的JS文件列表
LOCAL_JS_FILES = [
    {"source": "report.js", "target": "js/report.js"},
]


def generate_report(results: List[Dict[str, Any]], report_file: Path, screenshots_dir: Path) -> None:
    """生成HTML报告
    
    Args:
        results: 截图结果列表
        report_file: 报告HTML文件路径
        screenshots_dir: 截图目录路径
    """
    logger = logging.getLogger("eyeurl")
    start_time = time.time()
    
    logger.debug(f"开始生成HTML报告: {report_file}")
    logger.debug(f"处理 {len(results)} 个结果项 ({sum(1 for r in results if r.get('success') is True or (not r.get('error') and r.get('status_code', 0) >= 200 and r.get('status_code', 0) < 300))} 成功, {sum(1 for r in results if r.get('success') is False or (r.get('error') and r.get('success') is not True))} 失败)")
    
    report_dir = report_file.parent
    
    # 获取模板文件路径
    template_dir = Path(__file__).parent / "templates"
    logger.debug(f"使用模板目录: {template_dir}")
    
    # 检查模板文件是否存在
    html_template = template_dir / "report.html"
    js_template = template_dir / "report.js"
    
    if not html_template.exists():
        logger.error(f"HTML模板文件不存在: {html_template}")
        raise FileNotFoundError(f"HTML模板文件不存在: {html_template}")
    
    if not js_template.exists():
        logger.error(f"JS模板文件不存在: {js_template}")
        raise FileNotFoundError(f"JS模板文件不存在: {js_template}")
    
    # 检查本地资源文件是否完整
    resources_complete = True
    missing_resources = []
    
    # 检查RESOURCE_FILES中的资源
    for resource in RESOURCE_FILES:
        resource_path = template_dir / resource["local_path"]
        if not resource_path.exists():
            resources_complete = False
            missing_resources.append(resource["local_path"])
    
    # 检查LOCAL_JS_FILES中的资源
    for js_file in LOCAL_JS_FILES:
        source_path = template_dir / js_file["source"]
        if not source_path.exists():
            resources_complete = False
            missing_resources.append(js_file["source"])
    
    if not resources_complete:
        logger.warning(f"以下本地资源文件不存在: {', '.join(missing_resources)}")
        logger.warning("请运行 python -m eyeurl.download_resources 下载这些资源")
        logger.warning("将使用CDN资源作为备选")
    
    logger.debug(f"模板文件检查通过，开始复制文件")
    
    # 确保报告目录存在
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制模板文件到报告目录
    logger.debug(f"复制HTML模板: {html_template} -> {report_file}")
    shutil.copy(html_template, report_file)
    
    # 确保js目录存在
    js_dir = report_dir / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制自定义JS文件到js子目录
    for js_file in LOCAL_JS_FILES:
        source_path = template_dir / js_file["source"]
        target_path = report_dir / js_file["target"]
        
        # 确保目标目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        if source_path.exists():
            logger.debug(f"复制JS文件: {source_path} -> {target_path}")
            shutil.copy(source_path, target_path)
        else:
            logger.warning(f"自定义JS文件不存在: {source_path}")
    
    # 复制CSS和JS资源文件到报告目录
    for resource in RESOURCE_FILES:
        src_file = template_dir / resource["local_path"]
        dst_file = report_dir / resource["local_path"]
        
        # 确保目标目录存在
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        
        if src_file.exists():
            logger.debug(f"复制资源文件: {src_file} -> {dst_file}")
            shutil.copy(src_file, dst_file)
    
    # 确保data.json存在
    data_file = report_dir / "data.json"
    logger.debug(f"准备写入数据到JSON文件: {data_file}")
    
    # 统计要写入的数据大小
    data_size = len(json.dumps(results, ensure_ascii=False).encode('utf-8'))
    logger.debug(f"JSON数据大小: {format_file_size(data_size)} ({len(results)} 个结果项)")
    
    # 写入JSON数据
    with open(data_file, 'w', encoding='utf-8') as f:
        # 解决JS读取问题：确保数据是合法的JSON格式并添加CORS头
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.debug(f"JSON数据文件创建成功: {data_file} (大小: {format_file_size(data_size)})")
    
    # 修改报告HTML文件，添加内联数据脚本
    logger.debug(f"准备修改HTML报告文件，添加内联数据脚本并使用本地资源")
    
    # 测量内联数据的大小
    inline_data_size = len(json.dumps(results, ensure_ascii=False).encode('utf-8'))
    logger.debug(f"内联数据大小: {format_file_size(inline_data_size)}")
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
            logger.debug(f"成功读取HTML模板，大小: {format_file_size(len(html_content.encode('utf-8')))}")
        
        # 1. 创建内联数据脚本
        data_script = f"""
    <script>
        // 预加载数据，避免fetch请求失败
        window.reportData = {json.dumps(results, ensure_ascii=False)};
        console.log("数据预加载完成 - {len(results)}个结果");
    </script>
    """
        logger.debug(f"创建内联数据脚本，大小: {format_file_size(len(data_script.encode('utf-8')))}")
        
        # 2. 替换CDN引用为本地资源
        for resource in RESOURCE_FILES:
            cdn_url = resource["cdn_url"]
            local_path = resource["local_path"]
            
            # 检查资源文件是否存在于报告目录
            if (report_dir / local_path).exists():
                # 存在本地资源，使用相对路径
                if cdn_url in html_content:
                    html_content = html_content.replace(cdn_url, local_path)
                    logger.debug(f"已将CDN资源 {cdn_url} 替换为本地资源 {local_path}")
            else:
                logger.warning(f"本地资源文件不存在: {local_path}，将使用CDN链接")
        
        # 3. 在</head>前添加内联数据脚本
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', f'{data_script}\n</head>')
            logger.debug(f"已在</head>标签前添加内联数据")
        else:
            logger.warning(f"HTML模板中未找到</head>标签，尝试其他方法注入内联数据")
            if '<body>' in html_content:
                html_content = html_content.replace('<body>', f'{data_script}\n<body>')
                logger.debug(f"已在<body>标签前添加内联数据")
            else:
                logger.error(f"HTML模板中既未找到</head>也未找到<body>标签，无法注入内联数据")
                raise ValueError("无效的HTML模板格式")
        
        # 写入修改后的内容
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
            new_size = len(html_content.encode('utf-8'))
            original_html_size = len(open(html_template, 'r', encoding='utf-8').read().encode('utf-8'))
            size_diff = new_size - original_html_size
            logger.debug(f"已保存修改后的HTML报告，大小: {format_file_size(new_size)} (增加了 {format_file_size(size_diff)})")
        
    except Exception as e:
        logger.error(f"修改HTML报告文件失败: {str(e)}")
        raise
    
    # 验证文件写入成功
    logger.debug(f"验证文件是否成功创建")
    if not report_file.exists():
        logger.error(f"无法创建报告文件: {report_file}")
        raise FileNotFoundError(f"无法创建报告文件: {report_file}")
    
    if not (report_dir / "js" / "report.js").exists():
        logger.error(f"无法创建报告JS文件: {report_dir / 'js' / 'report.js'}")
        raise FileNotFoundError(f"无法创建报告JS文件: {report_dir / 'js' / 'report.js'}")
    
    # 确保文件权限正确
    try:
        logger.debug(f"设置文件权限为0644")
        report_file.chmod(0o644)
        (report_dir / "js" / "report.js").chmod(0o644)
        data_file.chmod(0o644)
        
        # 设置资源文件的权限
        for resource in RESOURCE_FILES:
            resource_file = report_dir / resource["local_path"]
            if resource_file.exists():
                resource_file.chmod(0o644)
        
        logger.debug(f"文件权限设置成功")
    except Exception as e:
        logger.warning(f"设置文件权限时出错: {e}")
        print(f"警告: 设置文件权限时出错: {e}")
    
    # 统计成功/失败数量
    success_count = sum(1 for r in results if r.get("success") is True or (not r.get("error") and r.get("status_code", 0) >= 200 and r.get("status_code", 0) < 300))
    failed_count = sum(1 for r in results if r.get("success") is False or (r.get("error") and r.get("success") is not True))
    
    # 计算状态码分布
    status_counts = {}
    for result in results:
        if result.get("status_code", 0) > 0:
            status_group = str(result["status_code"])[0] + "xx"
            status_counts[status_group] = status_counts.get(status_group, 0) + 1
    
    # 计算平均处理时间
    total_time = sum(r.get("processing_time", 0) for r in results)
    avg_time = total_time / len(results) if results else 0
    
    # 计算报告生成耗时
    elapsed_time = time.time() - start_time
    
    # 将这些日志从INFO改为DEBUG级别，避免在控制台重复显示
    logger.debug(f"HTML报告生成完成，耗时: {elapsed_time:.2f}秒")
    logger.debug(f"报告统计: {len(results)}个URL, 成功率: {success_count/len(results)*100:.1f}%")
    
    # 仅在DEBUG级别记录详细信息，避免在INFO级别产生太多输出
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"详细统计:")
        logger.debug(f"  - 总URL数: {len(results)}")
        logger.debug(f"  - 成功截图: {success_count} ({success_count/len(results)*100:.1f}%)")
        logger.debug(f"  - 失败截图: {failed_count} ({failed_count/len(results)*100:.1f}%)")
        
        if status_counts:
            logger.debug(f"  - 状态码分布:")
            for status, count in sorted(status_counts.items()):
                logger.debug(f"    - {status}: {count}个 ({count/len(results)*100:.1f}%)")
        
        logger.debug(f"  - 报告文件: {report_file}")
        logger.debug(f"  - JSON数据: {data_file}")


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.2f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB" 