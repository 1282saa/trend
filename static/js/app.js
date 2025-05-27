// ===== Configuration =====
const API_BASE_URL = 'http://localhost:5000';
const SOCKET_URL = 'http://localhost:5000';
const UPDATE_INTERVAL = 300000; // 5 minutes

// ===== State Management =====
const state = {
    trends: [],
    insights: [],
    selectedPlatform: 'all',
    theme: localStorage.getItem('theme') || 'light',
    isLoading: false,
    socket: null
};

// ===== DOM Elements =====
const elements = {
    trendsGrid: document.getElementById('trendsGrid'),
    insightsGrid: document.getElementById('insightsGrid'),
    tickerItems: document.getElementById('tickerItems'),
    updatesTimeline: document.getElementById('updatesTimeline'),
    toastContainer: document.getElementById('toastContainer'),
    modal: document.getElementById('trendModal'),
    modalBody: document.getElementById('modalBody'),
    scrollTopBtn: document.getElementById('scrollTopBtn'),
    themeToggle: document.querySelector('.theme-toggle'),
    refreshBtn: document.querySelector('.refresh-btn'),
    platformFilters: document.querySelectorAll('.filter-chip')
};

// ===== Initialize App =====
document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    initializeEventListeners();
    initializeSocket();
    fetchInitialData();
    startCountAnimation();
    startAutoRefresh();
});

// ===== Theme Management =====
function initializeTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();
}

function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', state.theme);
    localStorage.setItem('theme', state.theme);
    updateThemeIcon();
}

function updateThemeIcon() {
    const sunIcon = elements.themeToggle.querySelector('.sun-icon');
    const moonIcon = elements.themeToggle.querySelector('.moon-icon');
    
    if (state.theme === 'light') {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
    } else {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
    }
}

// ===== Event Listeners =====
function initializeEventListeners() {
    // Theme toggle
    elements.themeToggle.addEventListener('click', toggleTheme);
    
    // Refresh button
    elements.refreshBtn.addEventListener('click', () => {
        showToast('새로고침 중...', 'info');
        fetchInitialData();
    });
    
    // Platform filters
    elements.platformFilters.forEach(filter => {
        filter.addEventListener('click', () => {
            elements.platformFilters.forEach(f => f.classList.remove('active'));
            filter.classList.add('active');
            state.selectedPlatform = filter.dataset.platform;
            renderTrends();
        });
    });
    
    // Scroll to top button
    window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
            elements.scrollTopBtn.classList.add('visible');
        } else {
            elements.scrollTopBtn.classList.remove('visible');
        }
    });
    
    elements.scrollTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    
    // Modal close
    elements.modal.querySelector('.modal-backdrop').addEventListener('click', closeModal);
    elements.modal.querySelector('.modal-close').addEventListener('click', closeModal);
    
    // Mobile menu toggle
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    const navMenu = document.querySelector('.nav-menu');
    
    mobileMenuToggle.addEventListener('click', () => {
        mobileMenuToggle.classList.toggle('active');
        navMenu.classList.toggle('mobile-active');
    });
    
    // Navigation smooth scroll
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href');
            if (targetId === '#home') {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else if (targetId === '#trends') {
                document.querySelector('.trends-grid').scrollIntoView({ behavior: 'smooth' });
            } else if (targetId === '#insights') {
                document.querySelector('.insights-section').scrollIntoView({ behavior: 'smooth' });
            } else if (targetId === '#saved') {
                showSavedItems();
            }
            
            // Update active state
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            // Close mobile menu
            mobileMenuToggle.classList.remove('active');
            navMenu.classList.remove('mobile-active');
        });
    });
}

// ===== Socket.io Connection =====
function initializeSocket() {
    state.socket = io(SOCKET_URL);
    
    state.socket.on('connect', () => {
        console.log('Socket connected');
        showToast('실시간 연결됨', 'success');
    });
    
    state.socket.on('trends_update', (data) => {
        console.log('Received trends update:', data);
        updateTrendsFromSocket(data);
    });
    
    state.socket.on('disconnect', () => {
        console.log('Socket disconnected');
        showToast('연결이 끊어졌습니다', 'error');
    });
    
    state.socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        showToast('서버 연결 오류가 발생했습니다', 'error');
    });
    
    // Handle reconnection
    state.socket.firstConnect = true;
    state.socket.on('connect', () => {
        if (!state.socket.firstConnect) {
            showToast('서버에 다시 연결되었습니다', 'success');
            fetchInitialData();
        }
        state.socket.firstConnect = false;
    });
}

// ===== Data Fetching =====
async function fetchInitialData() {
    state.isLoading = true;
    showLoadingState();
    
    try {
        // Fetch hot keywords
        const keywordsResponse = await fetch(`${API_BASE_URL}/api/keywords/hot`);
        const keywordsData = await keywordsResponse.json();
        
        // Fetch topics
        const topicsResponse = await fetch(`${API_BASE_URL}/api/topics`);
        const topicsData = await topicsResponse.json();
        
        if (keywordsData.success) {
            state.trends = keywordsData.data;
            renderTrends();
            updateTicker();
            updateStats(keywordsData.data.length);
        }
        
        if (topicsData.success) {
            state.insights = topicsData.data;
            renderInsights();
            updateStats(null, topicsData.data.length);
        }
        
        addUpdateToTimeline('데이터 업데이트 완료');
        
    } catch (error) {
        console.error('Error fetching data:', error);
        showToast('데이터를 불러올 수 없습니다', 'error');
    } finally {
        state.isLoading = false;
        hideLoadingState();
    }
}

// ===== Rendering Functions =====
function renderTrends() {
    const filteredTrends = state.selectedPlatform === 'all' 
        ? state.trends 
        : state.trends.filter(trend => trend.sources?.includes(state.selectedPlatform));
    
    if (filteredTrends.length === 0) {
        elements.trendsGrid.innerHTML = `
            <div class="empty-state">
                <p>트렌드 데이터가 없습니다.</p>
            </div>
        `;
        return;
    }
    
    elements.trendsGrid.innerHTML = filteredTrends.map((trend, index) => `
        <div class="trend-card" data-trend='${JSON.stringify(trend).replace(/'/g, "&#39;")}'>
            <div class="card-header">
                <div class="trend-rank">#${index + 1}</div>
                <div class="trend-change ${getChangeClass()}">
                    ${getChangeIcon()}
                    <span>${getChangeText()}</span>
                </div>
            </div>
            <h3 class="trend-title">${trend.keyword}</h3>
            <div class="trend-platforms">
                ${(trend.sources || []).map(source => `
                    <span class="platform-badge">${getPlatformName(source)}</span>
                `).join('')}
            </div>
            <div class="trend-score">
                <span>관심도 점수:</span>
                <strong>${trend.score || 0}</strong>
            </div>
            <div class="trend-actions">
                <button class="action-btn primary" onclick="event.stopPropagation(); openOriginalLinks('${trend.keyword}')">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z"/>
                        <path d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z"/>
                    </svg>
                    원본 보기
                </button>
                <button class="action-btn secondary" onclick="event.stopPropagation(); showTrendDetail('${trend.keyword}')">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M8 4.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM2.5 8a5.5 5.5 0 1 1 11 0 5.5 5.5 0 0 1-11 0z"/>
                        <path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"/>
                    </svg>
                    상세 보기
                </button>
            </div>
            <div class="trend-chart">
                <canvas id="chart-${index}"></canvas>
            </div>
        </div>
    `).join('');
    
    // Render mini charts
    setTimeout(() => {
        filteredTrends.forEach((trend, index) => {
            renderMiniChart(`chart-${index}`, trend.keyword);
        });
    }, 100);
}

function renderInsights() {
    if (state.insights.length === 0) {
        elements.insightsGrid.innerHTML = `
            <div class="empty-state">
                <p>AI 인사이트가 아직 생성되지 않았습니다.</p>
            </div>
        `;
        return;
    }
    
    elements.insightsGrid.innerHTML = state.insights.map((insight, index) => `
        <div class="insight-card">
            <div class="insight-icon">
                ${getInsightIcon(index)}
            </div>
            <h3 class="insight-title">${insight.topic}</h3>
            <div class="insight-keywords">
                ${(insight.keywords || []).map(keyword => `
                    <span class="keyword-tag">${keyword}</span>
                `).join('')}
            </div>
            <div class="insight-hooks">
                ${(insight.hook_copies || []).map(hook => `
                    <div class="hook-item">
                        ${hook}
                        <button class="copy-btn" onclick="copyToClipboard('${hook.replace(/'/g, "\\'")}')">
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                                <path d="M5.333 5.333V3.467c0-.587 0-.88.114-1.103a1.067 1.067 0 01.467-.467c.223-.114.516-.114 1.103-.114h5.516c.587 0 .88 0 1.103.114.196.1.367.271.467.467.114.223.114.516.114 1.103v5.516c0 .587 0 .88-.114 1.103a1.067 1.067 0 01-.467.467c-.223.114-.516.114-1.103.114H10.667" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                <rect x="2.667" y="5.333" width="8" height="8" rx="1.333" stroke="currentColor" stroke-width="1.5"/>
                            </svg>
                        </button>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function updateTicker() {
    const topTrends = state.trends.slice(0, 10);
    const tickerHTML = topTrends.map((trend, index) => `
        <div class="ticker-item">
            <span class="ticker-rank">${index + 1}</span>
            <span>${trend.keyword}</span>
        </div>
    `).join('');
    
    // Duplicate for seamless loop
    elements.tickerItems.innerHTML = tickerHTML + tickerHTML;
}

function addUpdateToTimeline(message) {
    const now = new Date();
    const timeString = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    
    const updateHTML = `
        <div class="update-item">
            <div class="update-time">${timeString}</div>
            <div class="update-content">
                <div class="update-title">${message}</div>
                <div class="update-desc">실시간 트렌드 데이터가 업데이트되었습니다.</div>
            </div>
        </div>
    `;
    
    elements.updatesTimeline.insertAdjacentHTML('afterbegin', updateHTML);
    
    // Keep only last 10 updates
    const updates = elements.updatesTimeline.querySelectorAll('.update-item');
    if (updates.length > 10) {
        updates[updates.length - 1].remove();
    }
}

// ===== Chart Functions =====
function renderMiniChart(canvasId, keyword) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Generate dummy data for demo
    const data = Array(7).fill(0).map(() => Math.floor(Math.random() * 100));
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['6일전', '5일전', '4일전', '3일전', '2일전', '어제', '오늘'],
            datasets: [{
                data: data,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

// ===== Utility Functions =====
function showLoadingState() {
    elements.trendsGrid.innerHTML = `
        <div class="skeleton-card">
            <div class="skeleton skeleton-rank"></div>
            <div class="skeleton skeleton-title"></div>
            <div class="skeleton skeleton-tags"></div>
            <div class="skeleton skeleton-chart"></div>
        </div>
    `.repeat(6);
}

function hideLoadingState() {
    // Loading state will be replaced by actual content
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        ${getToastIcon(type)}
        <span>${message}</span>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    // Add entrance animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function showTrendDetail(keyword) {
    const trend = state.trends.find(t => t.keyword === keyword);
    if (!trend) return;
    
    // 상세 정보 로딩 표시
    elements.modalBody.innerHTML = `
        <h2>${trend.keyword}</h2>
        <div class="loading-detail">
            <div class="spinner"></div>
            <p>상세 정보를 불러오는 중...</p>
        </div>
    `;
    
    elements.modal.classList.add('active');
    
    try {
        // API에서 상세 정보 가져오기
        const response = await fetch(`${API_BASE_URL}/api/keywords/details/${encodeURIComponent(keyword)}`);
        const data = await response.json();
        
        let detailHtml = `
            <h2>${trend.keyword}</h2>
            <div class="modal-stats">
                <div class="stat">
                    <span>관심도 점수</span>
                    <strong>${trend.score || 0}</strong>
                </div>
                <div class="stat">
                    <span>출현 플랫폼</span>
                    <strong>${(trend.sources || []).length}개</strong>
                </div>
                <div class="stat">
                    <span>관련 링크</span>
                    <strong>${data.success ? data.data.urls.length : 0}개</strong>
                </div>
                <div class="stat">
                    <span>총 점수</span>
                    <strong>${data.success ? data.data.total_score : trend.score}</strong>
                </div>
            </div>
            <div class="modal-platforms">
                ${(trend.sources || []).map(source => `
                    <span class="platform-badge large">${getPlatformName(source)}</span>
                `).join('')}
            </div>
        `;
        
        // 원본 링크가 있는 경우 표시
        if (data.success && data.data.urls && data.data.urls.length > 0) {
            detailHtml += `
                <div class="modal-links">
                    <h3>관련 원본 링크</h3>
                    <div class="links-preview">
                        ${data.data.urls.slice(0, 3).map(url => `
                            <div class="link-preview" onclick="window.open('${url}', '_blank')">
                                <div class="link-icon">🔗</div>
                                <div class="link-text">
                                    <div class="link-domain">${getDomainFromUrl(url)}</div>
                                    <div class="link-url-short">${url.substring(0, 50)}${url.length > 50 ? '...' : ''}</div>
                                </div>
                            </div>
                        `).join('')}
                        ${data.data.urls.length > 3 ? `
                            <div class="link-more" onclick="openOriginalLinks('${keyword}')">
                                +${data.data.urls.length - 3}개 더 보기
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        // 메타데이터가 있는 경우 표시
        if (data.success && data.data.metadata && Object.keys(data.data.metadata).length > 0) {
            detailHtml += `
                <div class="modal-metadata">
                    <h3>추가 정보</h3>
                    <div class="metadata-grid">
                        ${Object.entries(data.data.metadata).map(([key, value]) => `
                            <div class="metadata-item">
                                <span class="metadata-key">${getMetadataLabel(key)}</span>
                                <span class="metadata-value">${formatMetadataValue(key, value)}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        detailHtml += `
            <div class="modal-chart">
                <canvas id="modalChart"></canvas>
            </div>
            <div class="modal-actions" style="display: flex; gap: 10px; margin-top: 20px;">
                <button class="primary-btn" onclick="openOriginalLinks('${keyword}')">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z"/>
                        <path d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z"/>
                    </svg>
                    원본 링크 열기
                </button>
                <button class="secondary-btn" onclick="saveTrend(${JSON.stringify(trend).replace(/"/g, '&quot;')})">
                    <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" style="margin-right: 8px;">
                        <path d="M10 2l2.39 4.84 5.34.78-3.86 3.77.91 5.31L10 14.14 5.22 16.7l.91-5.31L2.27 7.62l5.34-.78L10 2z"/>
                    </svg>
                    저장하기
                </button>
                <button class="secondary-btn" onclick="fetchKeywordHistory('${keyword}')">
                    📈 분석 보기
                </button>
            </div>
        `;
        
        elements.modalBody.innerHTML = detailHtml;
        
        // Render detailed chart
        setTimeout(() => {
            renderDetailedChart('modalChart', keyword);
        }, 100);
        
    } catch (error) {
        console.error('Error fetching trend details:', error);
        
        // 에러 시 기본 정보만 표시
        elements.modalBody.innerHTML = `
            <h2>${trend.keyword}</h2>
            <div class="modal-stats">
                <div class="stat">
                    <span>관심도 점수</span>
                    <strong>${trend.score || 0}</strong>
                </div>
                <div class="stat">
                    <span>출현 플랫폼</span>
                    <strong>${(trend.sources || []).length}개</strong>
                </div>
            </div>
            <div class="modal-platforms">
                ${(trend.sources || []).map(source => `
                    <span class="platform-badge large">${getPlatformName(source)}</span>
                `).join('')}
            </div>
            <div class="modal-chart">
                <canvas id="modalChart"></canvas>
            </div>
            <div class="modal-actions" style="display: flex; gap: 10px; margin-top: 20px;">
                <button class="primary-btn" onclick="openOriginalLinks('${keyword}')">
                    원본 링크 열기
                </button>
                <button class="secondary-btn" onclick="saveTrend(${JSON.stringify(trend).replace(/"/g, '&quot;')})">
                    저장하기
                </button>
            </div>
        `;
        
        setTimeout(() => {
            renderDetailedChart('modalChart', keyword);
        }, 100);
    }
}

// 메타데이터 라벨 변환
function getMetadataLabel(key) {
    const labels = {
        'channel': '채널',
        'views': '조회수',
        'description': '설명',
        'published_at': '게시일',
        'duration': '재생시간',
        'thumbnail': '썸네일'
    };
    return labels[key] || key;
}

// 메타데이터 값 포맷팅
function formatMetadataValue(key, value) {
    switch (key) {
        case 'views':
            return Number(value).toLocaleString() + '회';
        case 'published_at':
            return new Date(value).toLocaleDateString('ko-KR');
        case 'description':
            return value.length > 100 ? value.substring(0, 100) + '...' : value;
        case 'thumbnail':
            return value ? '<img src="' + value + '" style="max-width: 100px; border-radius: 4px;">' : '없음';
        default:
            return value;
    }
}

function closeModal() {
    elements.modal.classList.remove('active');
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('클립보드에 복사되었습니다', 'success');
    } catch (err) {
        showToast('복사에 실패했습니다', 'error');
    }
}

function updateStats(keywords, topics) {
    if (keywords !== null) {
        animateNumber(document.querySelector('[data-count="0"]'), keywords);
    }
    if (topics !== null) {
        animateNumber(document.querySelectorAll('[data-count="0"]')[1], topics);
    }
}

function animateNumber(element, target) {
    if (!element) return;
    
    const duration = 1000;
    const start = parseInt(element.textContent) || 0;
    const increment = (target - start) / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        element.textContent = Math.floor(current);
    }, 16);
}

function startCountAnimation() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                updateStats(30, 5); // Default values for demo
                observer.unobserve(entry.target);
            }
        });
    });
    
    const statsElement = document.querySelector('.hero-stats');
    if (statsElement) {
        observer.observe(statsElement);
    }
}

// ===== Helper Functions =====
function getPlatformName(platform) {
    const names = {
        google: 'Google',
        youtube: 'YouTube',
        naver: '네이버',
        news: '뉴스',
        twitter: 'Twitter',
        reddit: 'Reddit',
        daum: '다음'
    };
    return names[platform] || platform;
}

function getChangeClass() {
    const classes = ['up', 'down', 'same'];
    return classes[Math.floor(Math.random() * classes.length)];
}

function getChangeIcon() {
    const icons = {
        up: '↑',
        down: '↓',
        same: '→'
    };
    const changeClass = getChangeClass();
    return icons[changeClass] || '';
}

function getChangeText() {
    const texts = ['상승', '하락', '유지'];
    return texts[Math.floor(Math.random() * texts.length)];
}

function getInsightIcon(index) {
    const icons = ['💡', '🚀', '🎯', '📊', '🔥'];
    return icons[index % icons.length];
}

function getToastIcon(type) {
    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️'
    };
    return icons[type] || '';
}

// ===== Socket Update Handler =====
function updateTrendsFromSocket(data) {
    if (data.hot_keywords) {
        state.trends = data.hot_keywords;
        renderTrends();
        updateTicker();
    }
    
    if (data.topics) {
        state.insights = data.topics;
        renderInsights();
    }
    
    addUpdateToTimeline('실시간 업데이트 수신');
    showToast('새로운 트렌드가 업데이트되었습니다', 'info');
}

// ===== Fetch Keyword History =====
async function fetchKeywordHistory(keyword) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/keywords/history/${encodeURIComponent(keyword)}`);
        const data = await response.json();
        
        if (data.success) {
            // Handle history data
            console.log('Keyword history:', data.data);
            showToast('상세 분석을 불러왔습니다', 'success');
        }
    } catch (error) {
        console.error('Error fetching keyword history:', error);
        showToast('분석 데이터를 불러올 수 없습니다', 'error');
    }
}

// ===== Detailed Chart =====
function renderDetailedChart(canvasId, keyword) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Generate more detailed dummy data
    const labels = Array(24).fill(0).map((_, i) => `${i}시`);
    const data = Array(24).fill(0).map(() => Math.floor(Math.random() * 100));
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '관심도',
                data: data,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// ===== Auto Refresh Functions =====
function startAutoRefresh() {
    // Clear existing timer
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    
    // Set up auto refresh every 5 minutes
    refreshTimer = setInterval(() => {
        fetchInitialData();
        showToast('데이터가 자동으로 새로고침되었습니다', 'info');
    }, UPDATE_INTERVAL);
}

// ===== Saved Items Functions =====
function showSavedItems() {
    try {
        const savedItems = JSON.parse(localStorage.getItem('savedTrends') || '[]');
        
        if (savedItems.length === 0) {
            elements.trendsGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; text-align: center; padding: 60px 20px;">
                    <div style="font-size: 48px; margin-bottom: 16px;">📌</div>
                    <h3 style="font-size: 1.5rem; margin-bottom: 8px;">저장된 트렌드가 없습니다</h3>
                    <p style="color: var(--text-secondary);">트렌드 카드의 북마크 버튼을 클릭하여 저장하세요</p>
                </div>
            `;
            return;
        }
        
        // Render saved trends
        elements.trendsGrid.innerHTML = savedItems.map((trend, index) => `
            <div class="trend-card saved-item" onclick="showTrendDetail('${trend.keyword}')">
                <div class="card-header">
                    <div class="trend-rank">#${index + 1}</div>
                    <button class="bookmark-btn active" onclick="event.stopPropagation(); removeSavedItem('${trend.id}')">
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M10 2l2.39 4.84 5.34.78-3.86 3.77.91 5.31L10 14.14 5.22 16.7l.91-5.31L2.27 7.62l5.34-.78L10 2z"/>
                        </svg>
                    </button>
                </div>
                <h3 class="trend-title">${trend.keyword}</h3>
                <div class="trend-platforms">
                    ${(trend.sources || []).map(source => `
                        <span class="platform-badge">${getPlatformName(source)}</span>
                    `).join('')}
                </div>
                <div class="saved-date" style="margin-top: 8px; font-size: 0.875rem; color: var(--text-secondary);">
                    저장일: ${new Date(trend.savedAt).toLocaleDateString('ko-KR')}
                </div>
            </div>
        `).join('');
        
        // Stop auto refresh when viewing saved items
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
        
        // Update page title
        addUpdateToTimeline('저장된 트렌드 보기');
    } catch (error) {
        console.error('Error showing saved items:', error);
        showToast('저장된 항목을 불러오는데 실패했습니다', 'error');
    }
}

// Save trend function
function saveTrend(trend) {
    try {
        const savedItems = JSON.parse(localStorage.getItem('savedTrends') || '[]');
        
        // Check if already saved
        if (savedItems.some(item => item.keyword === trend.keyword)) {
            showToast('이미 저장된 트렌드입니다', 'info');
            return;
        }
        
        // Add saved timestamp
        trend.savedAt = new Date().toISOString();
        trend.id = `saved-${Date.now()}`;
        
        savedItems.push(trend);
        localStorage.setItem('savedTrends', JSON.stringify(savedItems));
        
        showToast('트렌드가 저장되었습니다', 'success');
    } catch (error) {
        console.error('Error saving trend:', error);
        showToast('저장에 실패했습니다', 'error');
    }
}

// Remove saved item
function removeSavedItem(itemId) {
    try {
        const savedItems = JSON.parse(localStorage.getItem('savedTrends') || '[]');
        const filteredItems = savedItems.filter(item => item.id !== itemId);
        
        localStorage.setItem('savedTrends', JSON.stringify(filteredItems));
        
        // Refresh saved items view
        showSavedItems();
        showToast('저장된 항목이 제거되었습니다', 'info');
    } catch (error) {
        console.error('Error removing saved item:', error);
        showToast('항목 제거에 실패했습니다', 'error');
    }
}

// ===== Original Links Functions =====
async function openOriginalLinks(keyword) {
    try {
        // 해당 키워드의 모든 원본 링크 수집
        const trend = state.trends.find(t => t.keyword === keyword);
        if (!trend) {
            showToast('트렌드 정보를 찾을 수 없습니다', 'error');
            return;
        }

        // API에서 상세 정보 가져오기
        const response = await fetch(`${API_BASE_URL}/api/keywords/details/${encodeURIComponent(keyword)}`);
        const data = await response.json();
        
        if (data.success && data.data.urls && data.data.urls.length > 0) {
            // 여러 링크가 있는 경우 모달로 선택하게 하기
            if (data.data.urls.length > 1) {
                showLinksModal(keyword, data.data.urls);
            } else {
                // 하나의 링크만 있는 경우 바로 열기
                window.open(data.data.urls[0], '_blank');
                showToast('원본 페이지를 새 탭에서 열었습니다', 'success');
            }
        } else {
            // 기본 검색으로 대체
            const searchUrl = getSearchUrl(keyword, trend.sources[0]);
            window.open(searchUrl, '_blank');
            showToast(`${getPlatformName(trend.sources[0])}에서 검색결과를 열었습니다`, 'info');
        }
    } catch (error) {
        console.error('Error opening original links:', error);
        // 에러 시 기본 검색으로 대체
        const trend = state.trends.find(t => t.keyword === keyword);
        if (trend && trend.sources && trend.sources.length > 0) {
            const searchUrl = getSearchUrl(keyword, trend.sources[0]);
            window.open(searchUrl, '_blank');
            showToast(`${getPlatformName(trend.sources[0])}에서 검색결과를 열었습니다`, 'info');
        } else {
            showToast('원본 링크를 찾을 수 없습니다', 'error');
        }
    }
}

// 플랫폼별 검색 URL 생성
function getSearchUrl(keyword, platform) {
    const encodedKeyword = encodeURIComponent(keyword);
    
    switch (platform) {
        case 'youtube':
            return `https://www.youtube.com/results?search_query=${encodedKeyword}`;
        case 'naver':
            return `https://search.naver.com/search.naver?query=${encodedKeyword}`;
        case 'google':
            return `https://www.google.com/search?q=${encodedKeyword}`;
        case 'news':
            return `https://search.naver.com/search.naver?where=news&query=${encodedKeyword}`;
        case 'daum':
            return `https://search.daum.net/search?q=${encodedKeyword}`;
        default:
            return `https://www.google.com/search?q=${encodedKeyword}`;
    }
}

// 링크 선택 모달 표시
function showLinksModal(keyword, urls) {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-backdrop" onclick="closeLinksModal()"></div>
        <div class="modal-content">
            <button class="modal-close" onclick="closeLinksModal()">&times;</button>
            <div class="modal-body">
                <h2>${keyword}</h2>
                <p class="modal-subtitle">관련된 원본 링크들을 선택하세요</p>
                <div class="links-list">
                    ${urls.map((url, index) => `
                        <div class="link-item" onclick="openSingleLink('${url}')">
                            <div class="link-icon">
                                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                                    <path d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z"/>
                                    <path d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z"/>
                                </svg>
                            </div>
                            <div class="link-info">
                                <div class="link-title">${getDomainFromUrl(url)}</div>
                                <div class="link-url">${url.substring(0, 60)}${url.length > 60 ? '...' : ''}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <div class="modal-actions" style="margin-top: 20px;">
                    <button class="primary-btn" onclick="openAllLinks(['${urls.join("','")}'])">
                        모든 링크 열기
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// 단일 링크 열기
function openSingleLink(url) {
    window.open(url, '_blank');
    closeLinksModal();
    showToast('링크를 새 탭에서 열었습니다', 'success');
}

// 모든 링크 열기
function openAllLinks(urls) {
    urls.forEach(url => {
        window.open(url, '_blank');
    });
    closeLinksModal();
    showToast(`${urls.length}개의 링크를 새 탭에서 열었습니다`, 'success');
}

// 링크 모달 닫기
function closeLinksModal() {
    const modal = document.querySelector('.modal');
    if (modal) {
        modal.remove();
    }
}

// URL에서 도메인 추출
function getDomainFromUrl(url) {
    try {
        const domain = new URL(url).hostname;
        return domain.replace('www.', '');
    } catch {
        return 'Unknown';
    }
}