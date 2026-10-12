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
    initCalculator();
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
            // 還原呢個用戶上次抽到嘅顏色組合（null = 預設）
            applyTheme(data.theme || null);
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
        refreshCalculator();   // 券有變動時，計算器跟住更新
    } catch (error) {
        console.error('載入摘要失敗:', error);
    }
}

function renderSummary(data) {
    rememberPlatformApps(data.platform_apps);
    document.getElementById('total-unused').textContent = data.total_unused + ' 元';
    
    const grid = document.getElementById('summary-grid');
    grid.innerHTML = '';
    
    data.platforms.forEach(item => {
        if (item.total_count > 0) {
            const card = document.createElement('div');
            card.className = 'summary-card';
            
            let couponsHtml = item.coupons.map(c => {
                const statusClass = c.is_used ? 'status-used' : 'status-unused';
                const actionBtn = c.is_used 
                    ? `<button class="btn btn-small btn-secondary" onclick="toggleCouponStatus(${c.id}, false)">未</button>`
                    : `<button class="btn btn-small btn-primary" onclick="toggleCouponStatus(${c.id}, true)">✓</button>`;
                return `<div class="coupon-item ${statusClass}">
                    <span class="coupon-amt">${amountLabel(c.amount)}</span>
                    <span class="coupon-date">${formatDateShort(c.draw_date)}</span>
                    <div class="coupon-actions">
                        ${actionBtn}
                        <button class="btn btn-danger btn-small" onclick="confirmDelete(${c.id})">×</button>
                    </div>
                </div>`;
            }).join('');
            
            card.innerHTML = `
                <h3>${platformNameHtml(item.platform, data.platform_apps)}</h3>
                <div class="card-totals">
                    <span class="total-unused">未: ${item.total_coupon}元</span>
                    <span class="total-used">已: ${item.platform_total}元</span>
                </div>
                <div class="coupon-list">${couponsHtml}</div>
            `;
            grid.appendChild(card);
        }
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

/** 獎項顯示名：禮遇券 / $12券 / N元（要同後端 amount_label 一致；禮遇券內部值係 -1） */
function amountLabel(amount) {
    if (amount === -1) return '禮遇券';
    return amount === 12 ? '$12券' : amount + '元';
}

/* ── 消費計算器（2026-10-11）─────────────────────────────────
   規則同後端 main.py 保持一致：
     • 一般券：整筆消費嘅「券總值 × 3」唔可以超過消費額
     • $12 券例外：要消費滿 100 元（而且商舖允許，用 checkbox 控制）
     • 可以疊用、跨平台分開支付疊用；只用「未使用」嘅券
   後端負責砌最佳組合，前端只負責顯示。 */
const CALC_DEBOUNCE_MS = 250;
let calcTimer = null;
let calcTicket = 0;

function initCalculator() {
    const input = document.getElementById('calc-amount');
    const toggle = document.getElementById('calc-allow-special');
    if (!input || !toggle) return;
    input.addEventListener('input', () => {
        clearTimeout(calcTimer);
        calcTimer = setTimeout(refreshCalculator, CALC_DEBOUNCE_MS);
    });
    toggle.addEventListener('change', refreshCalculator);
}

function calcAmount() {
    const input = document.getElementById('calc-amount');
    const value = Number(input ? input.value : '');
    return Number.isFinite(value) && value > 0 ? value : 0;
}

async function refreshCalculator() {
    const box = document.getElementById('calc-result');
    if (!box) return;

    const amount = calcAmount();
    if (!amount) {
        box.innerHTML = '<p class="calc-placeholder">輸入消費金額，即刻睇今次可以用幾多券</p>';
        return;
    }

    const allowSpecial = document.getElementById('calc-allow-special').checked;
    const ticket = ++calcTicket;
    try {
        const response = await fetch(API_BASE + '/calculator', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: amount, allow_special: allowSpecial })
        });
        const data = await response.json();
        if (ticket !== calcTicket) return;   // 只認最新一次請求，避免打字時舊結果蓋新結果
        if (!response.ok) {
            box.innerHTML = '<p class="calc-error">' + (data.error || '計唔到，請再試') + '</p>';
            return;
        }
        renderCalculator(data);
    } catch (error) {
        console.error('計算器失敗:', error);
        if (ticket === calcTicket) {
            box.innerHTML = '<p class="calc-error">網絡問題，請再試</p>';
        }
    }
}

// 平台名變成可點連結：iOS 有 scheme 就一按直接開 app，否則去 App Store
// （App Store 頁面如果 app 已裝，會顯示「開啟」，㩒一下就用得）
// mapping 由 /api/summary 或 /api/calculator 帶落嚟，cache 住共用。
let PLATFORM_APPS = {};

function rememberPlatformApps(apps) {
    if (apps && Object.keys(apps).length) {
        PLATFORM_APPS = apps;
    }
}

function platformLink(platform, apps) {
    const a = (apps && Object.keys(apps).length ? apps : PLATFORM_APPS)[platform];
    if (!a) return null;
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    if (isIOS && a.scheme_ios) return { href: a.scheme_ios, external: false };
    if (a.store) return { href: a.store, external: true };
    return null;
}

// 冇連結就照舊純文字
function platformNameHtml(platform, apps, className) {
    const cls = className || 'plat-name';
    const link = platformLink(platform, apps);
    if (!link) return '<span class="' + cls + '">' + platform + '</span>';
    return '<a class="' + cls + ' plat-link" href="' + link.href + '"' +
        (link.external ? ' target="_blank" rel="noopener"' : '') + '>' + platform + '</a>';
}


function renderCalculator(d) {
    const box = document.getElementById('calc-result');
    const combo = d.combo || [];
    const groups = d.by_platform || [];
    const money = (n) => '$' + n;

    // 每個平台一行：主角係「平台 + 支付總數」（收銀時最關鍵），
    // 券同現金退為下面一行細字
    const comboHtml = groups.length
        ? '<ul class="calc-combo">' + groups.map((g) => {
            const same = g.amounts.every((a) => a === g.amounts[0]);
            const label = (same && g.count > 1)
                ? money(g.amounts[0]) + ' 券 ×' + g.count
                : g.amounts.map(money).join(' ＋ ') + ' 券';
            const nameHtml = platformNameHtml(g.platform, d.platform_apps, 'calc-plat-name');
            return '<li>' +
                '<span class="calc-row-main">' +
                    nameHtml +
                    '<span class="calc-pay-total">支付 ' + money(g.pay_total) + '</span>' +
                '</span>' +
                '<span class="calc-row-sub">' + label + ' · 現金 ' + money(g.cash) + '</span>' +
            '</li>';
        }).join('') + '</ul>'
        : '';

    // 用券總額唔係重點（偉仔講嘅）→ 降做最底一行細字；平台行才係主角
    const caption = combo.length
        ? '<p class="calc-caption">用券 ' + money(d.max_value) + '</p>'
        : '<p class="calc-caption">今次用唔到券，全部現金支付</p>';

    const payHtml = '<p class="calc-pay">現金實付 <strong>' + money(d.pay_after) +
        '</strong>　（消費 ' + money(d.amount) + '）</p>';

    // 12 元商戶券係先減賬單，所以要講清楚「消費額 → 扣減後賬單」
    const discountHtml = d.special_applied
        ? '<p class="calc-discount">' + money(d.special_value) + ' 商戶券先減賬單：' +
          money(d.bill) + ' 減至 ' + money(d.base) + '</p>'
        : '';

    box.innerHTML = discountHtml + comboHtml + payHtml + caption;
}
