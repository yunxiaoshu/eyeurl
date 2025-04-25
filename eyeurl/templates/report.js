// 全局变量
let allData = [];
let filteredData = [];
let currentPage = 1;
let itemsPerPage = 20; // 改为变量，不再使用常量
let startTime = null;
let endTime = null;
let dataLoadAttempts = 0;
const MAX_LOAD_ATTEMPTS = 3;
let totalPages = 1;

// 控制台日志助手函数 - 调整日志级别，减少控制台输出
const logger = {
    // 生产环境是否启用调试
    debugEnabled: false,
    
    info: (message) => console.log(`[INFO] ${message}`),
    debug: (message) => {
        // 仅在调试模式下输出debug日志
        if (logger.debugEnabled) {
            console.log(`[DEBUG] ${message}`);
        }
    },
    warn: (message) => console.warn(`[WARNING] ${message}`),
    error: (message, error) => {
        console.error(`[ERROR] ${message}`, error);
        // 可选：在页面上显示错误消息
        // showErrorAlert(message);
    }
};

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    logger.info("报告页面加载完成，开始初始化...");
    
    // 设置所有事件监听器
    setupEventListeners();
    
    // 添加鼠标悬停图片动画效果
    try {
        setupImageAnimations();
        logger.debug("图片动画效果设置完成");
    } catch (e) {
        logger.warn("设置图片动画效果时出错", e);
    }
    
    // 初始化代码高亮
    try {
        setupCodeHighlighting();
        logger.debug("代码高亮初始化完成");
    } catch (e) {
        logger.warn("初始化代码高亮时出错", e);
    }
    
    // 使用加载数据函数，支持重试机制
    loadReportData();
    
    logger.info("报告页面初始化完成");
});

// 初始化代码高亮
function setupCodeHighlighting() {
    // 检查highlight.js是否可用
    if (typeof hljs !== 'undefined') {
        logger.info("初始化代码高亮 (highlight.js)");
        
        // 高亮所有pre code元素
        document.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
        
        // 添加自动高亮
        hljs.configure({
            ignoreUnescapedHTML: true
        });
        hljs.highlightAll();
        
        logger.debug("代码高亮设置完成");
    } else {
        logger.warn("highlight.js未找到，代码高亮功能不可用");
    }
}

// 加载报告数据，支持重试机制
function loadReportData() {
    // 显示加载状态
    updateLoadingStatus("加载数据中，请稍候...", "loading");
    
    // 优先使用内联数据
    if (window.reportData && Array.isArray(window.reportData) && window.reportData.length > 0) {
        logger.info(`使用内联数据加载报告 (${window.reportData.length}条记录)`);
        processData(window.reportData);
        updateLoadingStatus("数据加载完成", "success");
        return;
    }
    
    // 如果没有内联数据，检查是否超过最大尝试次数
    if (dataLoadAttempts >= MAX_LOAD_ATTEMPTS) {
        logger.error(`加载数据失败，已尝试 ${MAX_LOAD_ATTEMPTS} 次`);
        updateLoadingStatus(`加载数据失败: 请刷新页面或检查网络连接`, "error");
        return;
    }
    
    // 后备方案：尝试从外部文件加载
    logger.info(`尝试从data.json加载报告数据 (尝试 ${dataLoadAttempts + 1}/${MAX_LOAD_ATTEMPTS})`);
    dataLoadAttempts++;
    
    fetch('data.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP请求失败: 状态码 ${response.status}`);
            }
            logger.debug(`成功获取data.json，大小约 ${Math.round(response.headers.get('content-length') / 1024)} KB`);
            return response.json();
        })
        .then(data => {
            if (!data || !Array.isArray(data) || data.length === 0) {
                throw new Error("数据格式无效或为空");
            }
            logger.info(`成功解析JSON数据 (${data.length}条记录)`);
            processData(data);
            updateLoadingStatus("数据加载完成", "success");
        })
        .catch(error => {
            logger.warn(`加载数据失败，将在 1 秒后尝试重新加载 (尝试 ${dataLoadAttempts}/${MAX_LOAD_ATTEMPTS})`, error);
            
            // 显示重试状态
            updateLoadingStatus(`加载数据失败，正在重试... (${dataLoadAttempts}/${MAX_LOAD_ATTEMPTS})`, "retrying");
            
            // 添加延迟重试，避免立即重试导致同样的错误
            setTimeout(() => {
                // 检查是否在重试等待期间已经成功加载了数据
                if ((!window.reportData || !window.reportData.length) && (!allData || !allData.length)) {
                    loadReportData();
                }
            }, 1000);
        });
}

// 更新加载状态显示
function updateLoadingStatus(message, status) {
    const loadingStatus = document.getElementById('loading-status');
    const statusMessage = document.getElementById('status-message');
    
    if (!loadingStatus || !statusMessage) return;
    
    // 更新状态消息
    statusMessage.textContent = message;
    
    // 更新加载状态样式
    switch (status) {
        case 'loading':
            loadingStatus.className = 'bg-light';
            loadingStatus.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span id="status-message" class="ms-2">${message}</span>
            `;
            break;
        case 'error':
            loadingStatus.className = 'bg-danger text-white';
            loadingStatus.innerHTML = `
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                <span id="status-message">${message}</span>
            `;
            break;
        case 'retrying':
            loadingStatus.className = 'bg-warning';
            loadingStatus.innerHTML = `
                <div class="spinner-border text-dark" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span id="status-message" class="ms-2">${message}</span>
            `;
            break;
        case 'success':
            // 成功加载后，隐藏加载状态
            loadingStatus.style.display = 'none';
            break;
    }
    
    // 同时更新表格状态（如果为空）
    const tableBody = document.getElementById('results-body');
    if (tableBody && tableBody.children.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-4">
                    <p class="mb-0">${message}</p>
                </td>
            </tr>
        `;
    }
}

// 更新状态统计
function updateStatusStats(data) {
    // 成功URL数量（优先使用success标记，若不存在则判断状态码或无error）
    const successCount = data.filter(item => 
        item.success === true || 
        ((item.status_code && item.status_code >= 200 && item.status_code < 300) && !item.error)
    ).length;
    
    // 错误URL数量（优先使用success标记，若不存在则判断状态码或有error）
    const errorCount = data.filter(item => 
        item.success === false || 
        (item.error && item.success !== true)
    ).length;
    
    // 更新UI
    document.getElementById('success-count').textContent = successCount;
    document.getElementById('error-count').textContent = errorCount;
    
    // 获取捕获时间
    if (data.length > 0 && data[0].timestamp) {
        const captureDate = new Date(data[0].timestamp);
        document.getElementById('capture-time').textContent = captureDate.toLocaleString();
    }
    
    // 获取批处理总耗时
    let totalTime = 0;
    
    // 优先使用batch_info中的总耗时（从控制台获取的完整任务耗时）
    if (data.length > 0 && data[0].meta_data && data[0].meta_data.batch_info && 
        data[0].meta_data.batch_info.batch_time && 
        data[0].meta_data.batch_info.batch_time.total_time_seconds) {
        // 使用控制台中的总耗时
        totalTime = data[0].meta_data.batch_info.batch_time.total_time_seconds;
        logger.debug(`使用控制台总耗时: ${totalTime}秒`);
        
        if (data[0].meta_data.batch_info.batch_time.total_time_formatted) {
            // 如果有格式化的时间，直接使用
            document.getElementById('total-time').textContent = 
                data[0].meta_data.batch_info.batch_time.total_time_formatted;
            return;
        }
    } else {
        // 后备：累加所有URL的处理时间
        totalTime = data.reduce((sum, item) => sum + (item.processing_time || 0), 0);
        logger.debug(`使用累加URL处理时间: ${totalTime}秒`);
    }
    
    // 显示总耗时
    document.getElementById('total-time').textContent = formatTime(totalTime);
}

// 设置所有事件监听器
function setupEventListeners() {
    // 搜索按钮
    const searchButton = document.getElementById('search-button');
    if (searchButton) {
        searchButton.addEventListener('click', performSearch);
    }
    
    // 搜索输入框回车事件
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                performSearch();
            }
        });
    }
    
    // 排序按钮
    const sortButton = document.getElementById('sort-button');
    if (sortButton) {
        sortButton.addEventListener('click', performSort);
    }
    
    // 状态码过滤器
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            filterByStatus(this.value);
        });
    }
    
    // 具体状态码筛选
    const specificStatus = document.getElementById('specific-status');
    const applyStatusFilter = document.getElementById('apply-status-filter');
    
    if (specificStatus && applyStatusFilter) {
        // 回车键筛选
        specificStatus.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                filterBySpecificStatus();
            }
        });
        
        // 点击按钮筛选
        applyStatusFilter.addEventListener('click', filterBySpecificStatus);
    }
    
    // 自动应用排序
    const sortField = document.getElementById('sort-field');
    const sortDirection = document.getElementById('sort-direction');
    
    if (sortField) {
        sortField.addEventListener('change', performSort);
    }
    
    if (sortDirection) {
        sortDirection.addEventListener('change', performSort);
    }
}

// 设置页面大小选择器
function setupPageSizeSelector() {
    const pageSizeSelect = document.getElementById('page-size-select');
    if (!pageSizeSelect) {
        logger.warn('未找到页面大小选择器元素');
        return;
    }
    
    // 尝试从localStorage获取之前保存的每页显示数量
    const savedPageSize = localStorage.getItem('reportPageSize');
    if (savedPageSize) {
        // 检查该值是否在选择框中存在
        const optionExists = Array.from(pageSizeSelect.options).some(option => option.value === savedPageSize);
        if (optionExists) {
            pageSizeSelect.value = savedPageSize;
            itemsPerPage = parseInt(savedPageSize);
        }
    }
    
    // 添加变化事件监听器
    pageSizeSelect.addEventListener('change', function() {
        const newPageSize = parseInt(this.value);
        itemsPerPage = newPageSize;
        
        // 将选择保存到localStorage
        localStorage.setItem('reportPageSize', newPageSize);
        
        // 重新计算总页数
        totalPages = Math.ceil(filteredData.length / itemsPerPage);
        
        // 如果当前页超出新的总页数，重置为第一页
        if (currentPage > totalPages) {
            currentPage = 1;
        }
        
        // 重新显示数据并更新分页控件
        displayData(filteredData, currentPage);
        updatePaginationControls();
        updatePaginationInfo(filteredData.length);
        
        logger.debug(`每页显示数量已更改为: ${newPageSize}`);
    });
}

// 更新分页信息
function updatePaginationInfo(totalItems) {
    const paginationInfo = document.getElementById('pagination-info');
    if (!paginationInfo) return;
    
    if (totalItems === 0) {
        paginationInfo.textContent = '没有匹配的结果';
        return;
    }
    
    const start = (currentPage - 1) * itemsPerPage + 1;
    const end = Math.min(currentPage * itemsPerPage, totalItems);
    
    paginationInfo.textContent = `显示 ${start} - ${end} 项，共 ${totalItems} 项`;
}

// 修复模态框问题
function setupModalFix() {
    // 获取模态框元素
    const modal = document.getElementById('screenshotModal');
    if (!modal) {
        logger.warn('未找到截图模态框');
        return;
    }
    
    // 监听模态框关闭事件
    modal.addEventListener('hidden.bs.modal', function() {
        logger.debug('模态框关闭，清理资源');
        
        // 清除模态框图片引用
        const modalImage = document.getElementById('modalImage');
        if (modalImage) {
            modalImage.src = '';
        }
        
        // 清除URL引用
        const openUrlBtn = document.getElementById('openUrlBtn');
        if (openUrlBtn) {
            openUrlBtn.href = '#';
        }
    });
    
    logger.debug('模态框修复设置完成');
}

// 设置图片动画效果 - 减少延迟，确保直接显示
function setupImageAnimations() {
    // 为所有图片添加立即显示属性
    document.addEventListener('DOMNodeInserted', (e) => {
        if (e.target.tagName === 'IMG' && e.target.classList.contains('thumbnail-img')) {
            // 立即设置为可见
            e.target.style.opacity = '1';
        }
    });
}

// 图片预加载函数
function preloadImages(data) {
    logger.debug(`开始预加载 ${data.length} 张截图`);
    let loadedCount = 0;
    
    data.forEach(item => {
        if (item.screenshot) {
            const img = new Image();
            img.onload = () => {
                loadedCount++;
                if (loadedCount % 10 === 0) {
                    logger.debug(`已预加载 ${loadedCount} 张截图`);
                }
            };
            img.src = `screenshots/${item.screenshot}`;
        }
    });
}

// 初始化图片缩放功能
function setupImageZoom() {
    const modalImage = document.getElementById('modalImage');
    let isZoomed = false;
    
    modalImage.addEventListener('click', function() {
        if (!isZoomed) {
            // 放大图片
            this.style.maxHeight = 'none';
            this.style.maxWidth = 'none';
            this.style.cursor = 'zoom-out';
            document.querySelector('.modal-body').style.overflow = 'auto';
        } else {
            // 恢复原始大小
            this.style.maxHeight = '75vh';
            this.style.maxWidth = '100%';
            this.style.cursor = 'zoom-in';
            document.querySelector('.modal-body').style.overflow = 'hidden';
        }
        isZoomed = !isZoomed;
    });
    
    // 添加缩放提示
    const zoomHint = document.createElement('div');
    zoomHint.className = 'zoom-hint';
    zoomHint.innerHTML = '<i class="bi bi-zoom-in"></i> 点击图片放大/缩小';
    document.querySelector('.image-container').appendChild(zoomHint);
    
    // 3秒后隐藏提示
    setTimeout(() => {
        zoomHint.style.opacity = '0';
    }, 3000);
    
    logger.debug('图片缩放功能已设置');
}

// 显示特定索引的图片在模态框中
function showImageInModal(data, index) {
    // 确保索引在有效范围内
    if (index < 0) index = 0;
    if (index >= data.length) index = data.length - 1;
    
    const item = data[index];
    if (!item) {
        logger.error(`无法显示索引为 ${index} 的图片，数据项不存在`);
        return;
    }
    
    if (!item.screenshot) {
        logger.warn(`索引为 ${index} 的数据项没有截图`);
        return;
    }
    
    // 缓存当前查看的图片索引
    window.currentImageIndex = index;
    window.currentImageData = data;
    
    // 设置模态框内容
    document.getElementById('modalTitle').textContent = item.title || item.url;
    
    // 添加加载指示器
    const modalImage = document.getElementById('modalImage');
    modalImage.style.opacity = '0.5';
    document.getElementById('modalLoading').style.display = 'block';
    
    // 加载图片
    const newImage = new Image();
    newImage.onload = function() {
        modalImage.src = this.src;
        modalImage.style.opacity = '1';
        document.getElementById('modalLoading').style.display = 'none';
    };
    newImage.src = `screenshots/${item.screenshot}`; // 直接使用文件名，现在在capture.py中已经只存储文件名
    
    // 设置打开URL按钮
    const openUrlBtn = document.getElementById('openUrlBtn');
    if (openUrlBtn) {
        openUrlBtn.href = item.url;
        openUrlBtn.title = item.url;
    }
    
    // 设置导航按钮状态
    document.getElementById('prevImageBtn').disabled = (index <= 0);
    document.getElementById('nextImageBtn').disabled = (index >= data.length - 1);
    
    // 设置状态信息
    let statusText = '';
    
    if (item.status_code) {
        const statusCode = parseInt(item.status_code);
        let badgeClass = 'bg-secondary';
        
        if (statusCode >= 200 && statusCode < 300) {
            badgeClass = 'bg-success';
        } else if (statusCode >= 300 && statusCode < 400) {
            badgeClass = 'bg-info';
        } else if (statusCode >= 400 && statusCode < 500) {
            badgeClass = 'bg-warning text-dark';
        } else if (statusCode >= 500) {
            badgeClass = 'bg-danger';
        }
        
        statusText += `<span class="badge ${badgeClass} me-2">状态码: ${item.status_code}</span>`;
    }
    
    // 添加警告信息（如果有）
    if (item.warning) {
        statusText += `<span class="badge bg-warning text-dark me-2">警告: ${item.warning}</span>`;
    }
    
    if (item.content_size) {
        statusText += `<span class="badge bg-info me-2">大小: ${formatSize(item.content_size)}</span>`;
    }
    
    if (item.processing_time) {
        statusText += `<span class="badge bg-secondary">处理时间: ${item.processing_time.toFixed(2)}秒</span>`;
    }
    
    // 添加索引信息
    statusText += `<div class="mt-2 text-muted small">图片 ${index + 1} / ${data.length}</div>`;
    
    document.getElementById('modalStatus').innerHTML = statusText;
    
    // 重置缩放状态
    modalImage.style.maxHeight = '75vh';
    modalImage.style.maxWidth = '100%';
    modalImage.style.cursor = 'zoom-in';
    document.querySelector('.modal-body').style.overflow = 'hidden';
}

// 设置图片导航
function setupImageNavigation() {
    // 前一张图片按钮
    document.getElementById('prevImageBtn').addEventListener('click', function() {
        if (window.currentImageIndex > 0) {
            showImageInModal(window.currentImageData, window.currentImageIndex - 1);
        }
    });
    
    // 下一张图片按钮
    document.getElementById('nextImageBtn').addEventListener('click', function() {
        if (window.currentImageIndex < window.currentImageData.length - 1) {
            showImageInModal(window.currentImageData, window.currentImageIndex + 1);
        }
    });
    
    // 为模态框添加键盘导航
    document.getElementById('screenshotModal').addEventListener('keydown', function(e) {
        // 左箭头：上一张图片
        if (e.key === 'ArrowLeft') {
            if (window.currentImageIndex > 0) {
                showImageInModal(window.currentImageData, window.currentImageIndex - 1);
            }
        } 
        // 右箭头：下一张图片
        else if (e.key === 'ArrowRight') {
            if (window.currentImageIndex < window.currentImageData.length - 1) {
                showImageInModal(window.currentImageData, window.currentImageIndex + 1);
            }
        }
        // ESC键：关闭模态框
        else if (e.key === 'Escape') {
            const modal = bootstrap.Modal.getInstance(document.getElementById('screenshotModal'));
            if (modal) modal.hide();
        }
    });
    
    logger.debug('图片导航功能已设置');
}

// 处理数据
function processData(data) {
    logger.debug("开始处理数据", data);
    
    if (!data || !Array.isArray(data) || data.length === 0) {
        logger.error("没有数据可以显示或数据格式不正确");
        updateLoadingStatus("没有可显示的数据", true);
        return;
    }
    
    try {
        // 为每个数据项添加原始索引，以便按原始顺序排序时能够恢复
        data.forEach((item, index) => {
            item.originalIndex = index;
        });
        
        allData = data;
        filteredData = [...data];  // 初始时，筛选后的数据与全部数据相同
        
        // 更新URL总数统计
        document.getElementById('total-urls').textContent = data.length;
        
        // 计算成功和错误的URL数量 - 使用状态码判断而不是仅依赖success属性
        // 成功URL数量（状态码2xx）
        const successCount = data.filter(item => 
            (item.status_code && item.status_code >= 200 && item.status_code < 300) || 
            (item.success === true)
        ).length;
        
        // 错误URL数量
        const errorCount = data.length - successCount;
        
        document.getElementById('success-count').textContent = successCount;
        document.getElementById('error-count').textContent = errorCount;
        
        // 调用updateStatusStats来更新更详细的统计信息
        updateStatusStats(data);
        
        // 设置页面大小选择器
        setupPageSizeSelector();
        
        // 设置分页事件监听器（只设置一次）
        if (!window.paginationEventsSet) {
            setupPaginationEvents();
            window.paginationEventsSet = true;
        }
        
        // 设置模态框修复
        setupModalFix();
        
        // 设置图片动画
        setupImageAnimations();
        
        // 设置代码高亮
        setupCodeHighlighting();
        
        // 设置事件监听器，只需要设置一次
        setupEventListeners();
        
        // 初始化分页
        currentPage = 1;
        totalPages = Math.ceil(filteredData.length / itemsPerPage);
        
        // 显示所有数据
        displayData(filteredData, currentPage);
        updatePaginationControls();
        updatePaginationInfo(filteredData.length);
        
        logger.debug("数据处理完成，已显示第一页数据");
    } catch (error) {
        logger.error("处理数据时出错:", error);
        updateLoadingStatus("数据处理出错: " + error.message, true);
    }
}

// 显示数据
function displayData(data, page = 1) {
    const tableBody = document.getElementById('results-body');
    if (!tableBody) {
        logger.error('未找到结果表格主体元素');
        return;
    }
    
    tableBody.innerHTML = '';
    
    // 检查数据是否为空
    if (!data || data.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-4">
                    <i class="bi bi-info-circle me-2"></i> 没有符合条件的数据
                </td>
            </tr>
        `;
        
        // 更新分页信息和控件
        updatePaginationInfo(0);
        updatePaginationControls();
        
        return;
    }
    
    // 确保当前页有效
    if (page < 1) page = 1;
    totalPages = Math.ceil(data.length / itemsPerPage);
    if (page > totalPages) page = totalPages;
    currentPage = page;
    
    // 计算分页
    const start = (page - 1) * itemsPerPage;
    const end = Math.min(start + itemsPerPage, data.length);
    const pageData = data.slice(start, end);
    
    // 添加数据行
    pageData.forEach((item, index) => {
        const row = document.createElement('tr');
        
        // 根据状态码设置行样式类
        if (item.error) {
            // 有错误字段，设置为危险样式
            row.classList.add('table-danger');
        } else if (item.status_code >= 200 && item.status_code < 300 || item.success === true) {
            row.classList.add('table-success');
        } else if (item.status_code >= 300 && item.status_code < 400) {
            row.classList.add('table-warning');
        } else if (item.status_code >= 400) {
            row.classList.add('table-danger');
        } else {
            // 没有状态码或其他情况，设为中性样式
            row.classList.add('table-secondary');
        }
        
        // 创建状态徽章
        let statusBadge = '';
        const statusCode = item.status_code || 0;
        
        if (item.success === false || (item.error && item.success !== true)) {
            // 错误项，显示红色标记
            statusBadge = `<span class="badge bg-danger">失败</span>`;
        } else if (item.warning) {
            // 带警告的成功项
            statusBadge = `<span class="badge bg-warning text-dark" title="${item.warning}">部分成功</span>`;
        } else if (statusCode >= 200 && statusCode < 300) {
            // 2xx 成功状态码
            statusBadge = `<span class="badge bg-success">${statusCode}</span>`;
        } else if (statusCode >= 300 && statusCode < 400) {
            // 3xx 重定向状态码
            statusBadge = `<span class="badge bg-info">${statusCode}</span>`;
        } else if (statusCode >= 400 && statusCode < 500) {
            // 4xx 客户端错误
            statusBadge = `<span class="badge bg-warning text-dark">${statusCode}</span>`;
        } else if (statusCode >= 500) {
            // 5xx 服务器错误
            statusBadge = `<span class="badge bg-danger">${statusCode}</span>`;
        } else if (item.success === true) {
            // 无状态码但标记为成功
            statusBadge = `<span class="badge bg-success">成功</span>`;
        } else {
            // 无状态码
            statusBadge = `<span class="badge bg-secondary">未知</span>`;
        }
        
        // 填充行内容
        row.innerHTML = `
            <td>${start + index + 1}</td>
            <td title="${item.url}">
                <a href="${item.url}" target="_blank" class="d-inline-block w-100 word-break-all">
                    ${item.url}
                </a>
            </td>
            <td title="${item.title || '无标题'}">
                <span class="d-inline-block w-100 word-break-all">
                    ${item.title || '<span class="text-muted">无标题</span>'}
                </span>
            </td>
            <td>${statusBadge}</td>
            <td>${formatSize(item.content_size)}</td>
            <td>
                ${item.screenshot && (item.success === true || !item.error) ? 
                    `<div class="thumbnail-container">
                        <img src="screenshots/${item.screenshot}" alt="截图" class="thumbnail-img" 
                            data-url="${item.url}" data-title="${item.title || '无标题'}" 
                            data-status="${item.status_code || 'unknown'}" 
                            data-size="${item.content_size || 0}"
                            data-index="${start + index}">
                        <i class="bi bi-zoom-in position-absolute" style="right: 3px; bottom: 2px; font-size: 10px; color: white; text-shadow: 0 0 2px #000;"></i>
                        ${item.warning ? `<div class="position-absolute bottom-0 w-100 p-1 bg-warning bg-opacity-75 text-dark small"><i class="bi bi-exclamation-triangle-fill"></i> ${item.warning}</div>` : ''}
                    </div>` : 
                    `<span class="text-danger">
                        <i class="bi bi-exclamation-triangle-fill"></i> 
                        ${item.error || '截图失败'}
                    </span>`
                }
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // 绑定截图点击事件
    document.querySelectorAll('.thumbnail-img').forEach(img => {
        img.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            showImageInModal(data, index);
            
            // 显示模态框
            const myModal = new bootstrap.Modal(document.getElementById('screenshotModal'));
            myModal.show();
            
            // 设置模态框的tabindex以支持键盘事件
            document.getElementById('screenshotModal').setAttribute('tabindex', '-1');
            document.getElementById('screenshotModal').focus();
        });
    });
    
    // 如果数据少于每页数量，确保分页信息正确显示
    if (data.length <= itemsPerPage) {
        document.getElementById('pagination-info').textContent = `显示 1 - ${data.length} 项，共 ${data.length} 项`;
    }
}

// 搜索功能
function performSearch() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();
    
    if (searchTerm === '') {
        // 如果搜索框为空，显示所有数据
        filteredData = [...allData];
    } else {
        // 过滤匹配的数据
        filteredData = allData.filter(item => 
            (item.url && item.url.toLowerCase().includes(searchTerm)) || 
            (item.title && item.title.toLowerCase().includes(searchTerm))
        );
    }
    
    // 应用当前状态码过滤
    const statusFilter = document.getElementById('status-filter').value;
    if (statusFilter !== 'all') {
        filterByStatus(statusFilter, false); // 传递false表示不重新计算filteredData
        return; // filterByStatus函数会更新UI
    }
    
    // 重置到第一页
    currentPage = 1;
    
    // 重新计算总页数
    totalPages = Math.ceil(filteredData.length / itemsPerPage);
    
    // 更新显示
    displayData(filteredData, currentPage);
    // 确保按顺序调用更新函数
    updatePaginationControls();
    updatePaginationInfo(filteredData.length);
    
    logger.debug(`搜索: "${searchTerm}", 找到 ${filteredData.length} 条记录`);
}

// 执行排序
function performSort() {
    const sortField = document.getElementById('sort-field').value;
    const sortDirection = document.getElementById('sort-direction').value;
    const isAscending = sortDirection === 'asc';
    
    logger.debug(`排序: 字段=${sortField}, 方向=${sortDirection}`);
    
    if (!filteredData || filteredData.length === 0) {
        logger.warn('没有数据可排序');
        return;
    }
    
    filteredData.sort((a, b) => {
        let comparison = 0;
        
        switch (sortField) {
            case 'status_code':
                // 处理状态码为null或undefined的情况
                const codeA = a.status_code || 0;
                const codeB = b.status_code || 0;
                comparison = codeA - codeB;
                break;
                
            case 'content_size':
                // 处理内容大小可能为null的情况
                const sizeA = a.content_size !== null ? a.content_size : 0;
                const sizeB = b.content_size !== null ? b.content_size : 0;
                comparison = sizeA - sizeB;
                break;
                
            case 'title':
                // 处理标题可能为null的情况
                const titleA = (a.title || '').toLowerCase();
                const titleB = (b.title || '').toLowerCase();
                comparison = titleA.localeCompare(titleB);
                break;
                
            case 'url':
                // 处理URL可能为null的情况
                const urlA = (a.url || '').toLowerCase();
                const urlB = (b.url || '').toLowerCase();
                comparison = urlA.localeCompare(urlB);
                break;
                
            case 'index':
            default:
                // 回退到原始顺序
                comparison = a.originalIndex - b.originalIndex;
                break;
        }
        
        // 根据排序方向返回结果
        return isAscending ? comparison : -comparison;
    });
    
    // 重置到第一页
    currentPage = 1;
    
    // 重新计算总页数
    totalPages = Math.ceil(filteredData.length / itemsPerPage);
    
    // 更新显示
    displayData(filteredData, currentPage);
    // 确保按顺序调用更新函数
    updatePaginationControls();
    updatePaginationInfo(filteredData.length);
    
    logger.debug(`排序完成，显示第一页数据`);
}

// 格式化文件大小
function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + sizes[i];
}

// 格式化时间
function formatTime(seconds) {
    if (!seconds || seconds === 0) return '0 秒';
    
    if (seconds < 60) {
        return seconds.toFixed(1) + ' 秒';
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes} 分 ${remainingSeconds.toFixed(0)} 秒`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours} 小时 ${minutes} 分`;
    }
}

// 根据状态码过滤数据
function filterByStatus(statusFilter, recalculate = true) {
    // 清空具体状态码输入框
    const specificStatus = document.getElementById('specific-status');
    if (specificStatus) {
        specificStatus.value = '';
    }
    
    // 如果需要重新计算，先从所有数据开始
    let dataToFilter = recalculate ? [...allData] : filteredData;
    
    if (statusFilter === 'all') {
        // 如果选择"全部"且需要重新计算，则恢复为所有数据
        if (recalculate) {
            filteredData = dataToFilter;
        }
    } else if (statusFilter === 'failed') {
        // 专门过滤失败的条目（带有error字段的）
        filteredData = dataToFilter.filter(item => item.error);
    } else {
        // 根据状态码过滤
        filteredData = dataToFilter.filter(item => {
            // 首先检查是否有错误标志，这些项应当归类为"客户端错误"
            if (statusFilter === 'client-error' && item.error) {
                return true;
            }
            
            const code = item.status_code;
            if (!code) return false;
            
            switch (statusFilter) {
                case 'success':
                    return code >= 200 && code < 300;
                case 'redirect':
                    return code >= 300 && code < 400;
                case 'client-error':
                    return code >= 400 && code < 500;
                case 'server-error':
                    return code >= 500;
                default:
                    return true;
            }
        });
    }
    
    // 重置到第一页
    currentPage = 1;
    
    // 重新计算总页数
    totalPages = Math.ceil(filteredData.length / itemsPerPage);
    
    // 更新显示
    displayData(filteredData, currentPage);
    // 确保按顺序调用更新函数
    updatePaginationControls();
    updatePaginationInfo(filteredData.length);
    
    logger.debug(`状态码过滤: ${statusFilter}, 找到 ${filteredData.length} 条记录`);
}

// 根据具体状态码筛选
function filterBySpecificStatus() {
    const specificStatus = document.getElementById('specific-status');
    if (!specificStatus || !specificStatus.value) {
        return;
    }
    
    const statusValue = parseInt(specificStatus.value.trim());
    if (isNaN(statusValue) || statusValue < 100 || statusValue > 599) {
        alert('请输入有效的HTTP状态码 (100-599)');
        return;
    }
    
    // 重置状态码下拉选择为"全部"
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) {
        statusFilter.value = 'all';
    }
    
    // 筛选匹配具体状态码的项目
    filteredData = allData.filter(item => item.status_code === statusValue);
    
    // 重置到第一页
    currentPage = 1;
    
    // 重新计算总页数
    totalPages = Math.ceil(filteredData.length / itemsPerPage);
    
    // 更新显示
    displayData(filteredData, currentPage);
    // 确保按顺序调用更新函数
    updatePaginationControls();
    updatePaginationInfo(filteredData.length);
    
    logger.debug(`具体状态码过滤: ${statusValue}, 找到 ${filteredData.length} 条记录`);
}

// 设置分页事件
function setupPaginationEvents() {
    // 前一页按钮
    const prevButton = document.getElementById('prev-page');
    if (prevButton) {
        prevButton.addEventListener('click', function() {
            if (currentPage > 1) {
                currentPage--;
                displayData(filteredData, currentPage);
                updatePaginationControls();
                updatePaginationInfo(filteredData.length);
                // 滚动到表格顶部
                document.getElementById('results-table').scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
    
    // 下一页按钮
    const nextButton = document.getElementById('next-page');
    if (nextButton) {
        nextButton.addEventListener('click', function() {
            if (currentPage < totalPages) {
                currentPage++;
                displayData(filteredData, currentPage);
                updatePaginationControls();
                updatePaginationInfo(filteredData.length);
                // 滚动到表格顶部
                document.getElementById('results-table').scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
}

// 更新分页控件
function updatePaginationControls() {
    const prevButton = document.getElementById('prev-page');
    const nextButton = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');
    
    if (!pageInfo || !prevButton || !nextButton) {
        logger.warn('未找到分页控件元素');
        return;
    }
    
    // 如果没有数据或者只有一页，隐藏分页控件
    const paginationContainer = document.querySelector('.pagination-container');
    if (totalPages <= 1) {
        if (paginationContainer) {
            paginationContainer.style.display = filteredData.length > 0 ? 'flex' : 'none';
        }
        pageInfo.textContent = filteredData.length > 0 ? 
            `第 1 页，共 1 页` : 
            `没有数据`;
        prevButton.disabled = true;
        nextButton.disabled = true;
        return;
    }
    
    // 显示分页控件
    if (paginationContainer) {
        paginationContainer.style.display = 'flex';
    }
    
    // 更新页数信息
    pageInfo.textContent = `第 ${currentPage} 页，共 ${totalPages} 页`;
    
    // 更新按钮状态
    prevButton.disabled = currentPage <= 1;
    nextButton.disabled = currentPage >= totalPages;
    
    // 添加适当的标签以提高可访问性
    prevButton.setAttribute('aria-label', `转到第 ${currentPage - 1} 页`);
    nextButton.setAttribute('aria-label', `转到第 ${currentPage + 1} 页`);
    
    logger.debug(`更新分页控件: 当前页=${currentPage}, 总页数=${totalPages}`);
} 