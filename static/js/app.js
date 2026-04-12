/**
 * 澳門消費券記錄系統 - 前端應用程式
 */

const API_BASE = '/api';

let currentPage = 1;
let totalPages = 1;

document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus();
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('coupon-form').addEventListener('submit', handleCouponSubmit);
    const now = new Date();
    const macauTime = new Date(now.toLocaleString('zh-TW', { timeZone: 'Asia/Hong_Kong' }));
    document.getElementById('coupon-date').valueAsDate = macauTime;
});

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
    return container;
}

function setLoading(element, isLoading) {
    if (isLoading) {
        element.disabled = true;
        element.dataset.originalText = element.textContent;
        element.textContent = '載入中...';
    } else {
        element.disabled = false;
        element.textContent = element.dataset.originalText || element.textContent;
    }
}

async function checkLoginStatus() {
    try {
        const response = await fetch('/api/current-user');
        const data = await response.json();
        if (data && data.name) {
            showAppScreen(data.name);
        } else {
            showLoginScreen();
        }
    } catch (error) {
        showLoginScreen();
    }
}

function showLoginScreen() {
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('app-screen').style.display = 'none';
}

function showAppScreen(userName) {
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app-screen').style.display = 'block';
    document.getElementById('user-name-display').textContent = userName;
    loadSummary();
    loadCoupons();
    loadSectionState();
}

async function loadSectionState() {
    try {
        const response = await fetch(API_BASE + '/user-settings');
        if (response.ok) {
            const data = await response.json();
            if (data.form_collapsed) {
                document.getElementById('lottery-content').classList.add('collapsed');
                document.getElementById('lottery-toggle').textContent = '▶';
            }
            if (data.trends_collapsed) {
                document.getElementById('trends-content').classList.add('collapsed');
                document.getElementById('trends-toggle').textContent = '▶';
            }
        }
    } catch (error) {
        console.error('載入狀態失敗:', error);
    }
}

async function toggleSection(section) {
    const content = document.getElementById(section + '-content');
    const toggle = document.getElementById(section + '-toggle');
    content.classList.toggle('collapsed');
    const isCollapsed = content.classList.contains('collapsed');
    toggle.textContent = isCollapsed ? '▶' : '▼';
    try {
        await fetch(API_BASE + '/user-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ form_collapsed: isCollapsed })
        });
    } catch (error) {
        console.error('保存狀態失敗:', error);
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const name = document.getElementById('login-name').value.trim();
    const submitBtn = event.target.querySelector('button[type="submit"]');
    if (!name) {
        showToast('請輸入姓名', 'error');
        return;
    }
    setLoading(submitBtn, true);
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (response.ok) {
            const data = await response.json();
            showAppScreen(data.name);
            showToast('登入成功');
        } else {
            showToast('登入失敗，請稍後再試', 'error');
        }
    } catch (error) {
        console.error('登入失敗:', error);
        showToast('登入失敗，請稍後再試', 'error');
    } finally {
        setLoading(submitBtn, false);
    }
}

async function logout() {
    if (!confirm('確定要登出嗎？')) return;
    try {
        await fetch('/logout', { method: 'POST' });
        showLoginScreen();
    } catch (error) {
        console.error('登出失敗:', error);
    }
}

async function loadSummary() {
    try {
        const response = await fetch(API_BASE + '/summary');
        if (response.status === 401) {
            showLoginScreen();
            return;
        }
        const data = await response.json();
        renderSummary(data);
    } catch (error) {
        console.error('載入摘要失敗:', error);
    }
}

function renderSummary(data) {
    const grid = document.getElementById('summary-grid');
    grid.innerHTML = '';
    document.getElementById('total-unused').textContent = data.total_unused + ' 元';
    data.platforms.forEach(item => {
        const card = document.createElement('div');
        card.className = 'summary-card';
        card.innerHTML = '<h3>' + item.platform + (item.platform === 'UEpay' ? ' 🗑️' : '') + '</h3>' +
            '<div class="summary-stat"><span class="label">總券額</span><span class="value">' + item.platform_total + ' 元</span></div>' +
            '<div class="summary-stat"><span class="label">未使用</span><span class="value highlight">' + item.total_coupon + ' 元</span></div>';
        grid.appendChild(card);
    });
}

async function loadCoupons(page = 1) {
    const tbody = document.getElementById('coupons-tbody');
    const platform = document.getElementById('filter-platform')?.value || '';
    const status = document.getElementById('filter-status')?.value || '';
    
    tbody.innerHTML = '<tr><td colspan="4" class="loading-state">載入中...</td></tr>';
    
    try {
        let url = API_BASE + '/coupons?page=' + page + '&per_page=20';
        const response = await fetch(url);
        if (response.status === 401) {
            showLoginScreen();
            return;
        }
        const result = await response.json();
        
        currentPage = result.current_page;
        totalPages = result.pages;
        
        let data = result.coupons;
        if (platform) data = data.filter(c => c.platform === platform);
        if (status === 'used') data = data.filter(c => c.is_used);
        else if (status === 'unused') data = data.filter(c => !c.is_used);
        
        renderCoupons(data);
        renderPagination();
    } catch (error) {
        console.error('載入優惠券失敗:', error);
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">載入失敗</td></tr>';
    }
}

function renderCoupons(coupons) {
    const tbody = document.getElementById('coupons-tbody');
    if (coupons.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">暫時未有抽獎記錄<br>填寫上方表單開始記錄</td></tr>';
        return;
    }
    tbody.innerHTML = coupons.map(coupon =>
        '<tr><td>' + coupon.platform + '</td><td>' + coupon.amount + '元 <span class="status-badge ' + (coupon.is_used ? 'status-used' : 'status-unused') + '">' + (coupon.is_used ? '已用' : '未用') + '</span></td><td>' + formatDateShort(coupon.draw_date) + '</td><td>' +
        (coupon.is_used ? '<button class="btn btn-small btn-secondary" onclick="confirmUnmark(' + coupon.id + ')">未用</button>' : '<button class="btn btn-small btn-primary" onclick="confirmRedeem(' + coupon.id + ')">兌換</button>') +
        '<button class="btn btn-danger btn-small" onclick="confirmDelete(' + coupon.id + ')">刪</button></td></tr>'
    ).join('');
}

function renderPagination() {
    const pagination = document.getElementById('pagination');
    if (!pagination) return;
    
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    let html = '';
    if (currentPage > 1) {
        html += '<button class="btn btn-small" onclick="loadCoupons(' + (currentPage - 1) + ')">上一頁</button>';
    }
    html += '<span class="page-info">第 ' + currentPage + ' / ' + totalPages + ' 頁</span>';
    if (currentPage < totalPages) {
        html += '<button class="btn btn-small" onclick="loadCoupons(' + (currentPage + 1) + ')">下一頁</button>';
    }
    pagination.innerHTML = html;
}

async function handleCouponSubmit(event) {
    event.preventDefault();
    const platform = document.getElementById('coupon-platform').value;
    const date = document.getElementById('coupon-date').value;
    const amountEntries = document.querySelectorAll('.coupon-amount');
    const submitBtn = event.target.querySelector('.btn-save');
    
    if (!platform) {
        showToast('請選擇支付平臺', 'error');
        return;
    }
    const coupons = [];
    amountEntries.forEach(entry => {
        const value = entry.value;
        if (value !== '') {
            coupons.push({ platform: platform, amount: parseInt(value), draw_date: date });
        }
    });
    if (coupons.length === 0) {
        showToast('請至少選擇一個券面額', 'error');
        return;
    }
    
    setLoading(submitBtn, true);
    try {
        const response = await fetch(API_BASE + '/coupons', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coupons })
        });
        if (response.ok) {
            showToast('🎉 記錄已保存！');
            document.getElementById('coupon-platform').value = '';
            amountEntries.forEach(entry => entry.value = '');
            const now = new Date();
            const macauTime = new Date(now.toLocaleString('zh-TW', { timeZone: 'Asia/Hong_Kong' }));
            document.getElementById('coupon-date').valueAsDate = macauTime;
            loadCoupons(currentPage);
            loadSummary();
        } else {
            const data = await response.json();
            showToast(data.error || '新增失敗，請稍後再試', 'error');
        }
    } catch (error) {
        console.error('新增失敗:', error);
        showToast('新增失敗，請稍後再試', 'error');
    } finally {
        setLoading(submitBtn, false);
    }
}

function confirmRedeem(id) { showConfirmModal('確認兌換', '確定要將此券標記為已使用嗎？\n（請確保已消費滿最低金額要求）', () => toggleCouponStatus(id, true)); }
function confirmUnmark(id) { showConfirmModal('確認取消', '確定要將此券標記為未使用嗎？', () => toggleCouponStatus(id, false)); }
function confirmDelete(id) { showConfirmModal('確認刪除', '確定要刪除這筆記錄嗎？\n此操作無法撤銷。', () => deleteCoupon(id)); }
function confirmClearAll() { showConfirmModal('⚠️ 確認清空', '確定要刪除所有歷史記錄嗎？\n此操作無法撤銷！', () => clearAllCoupons()); }

function showConfirmModal(title, message, onConfirm) {
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').textContent = message;
    document.getElementById('confirm-btn').onclick = () => { closeConfirmModal(); onConfirm(); };
    document.getElementById('confirm-modal').classList.add('active');
}

function closeConfirmModal() { document.getElementById('confirm-modal').classList.remove('active'); }
document.addEventListener('click', (e) => { if (e.target.classList.contains('modal')) closeConfirmModal(); });

async function toggleCouponStatus(id, isUsed) {
    try {
        const response = await fetch(API_BASE + '/coupons/' + id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_used: isUsed })
        });
        if (response.ok) {
            loadCoupons(currentPage);
            loadSummary();
            showToast(isUsed ? '已標記為已使用' : '已標記為未使用');
        }
    } catch (error) {
        console.error('更新失敗:', error);
        showToast('更新失敗', 'error');
    }
}

async function deleteCoupon(id) {
    try {
        const response = await fetch(API_BASE + '/coupons/' + id, { method: 'DELETE' });
        if (response.ok) {
            loadCoupons(currentPage);
            loadSummary();
            showToast('已刪除');
        }
    } catch (error) {
        console.error('刪除失敗:', error);
        showToast('刪除失敗', 'error');
    }
}

async function clearAllCoupons() {
    try {
        const response = await fetch(API_BASE + '/coupons/clear-all', { method: 'POST' });
        if (response.ok) {
            loadCoupons(1);
            loadSummary();
            showToast('已清空所有記錄');
        }
    } catch (error) {
        console.error('清空失敗:', error);
        showToast('清空失敗', 'error');
    }
}

function formatDateShort(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit' });
}
