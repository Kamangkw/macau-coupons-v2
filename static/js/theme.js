/**
 * 主題引擎：隨機顏色組合（每個用戶記住最後一次抽到嘅組合）
 *
 * 設計原則：
 *   - 只改 CSS 變數（:root 嘅 --bg-1/--surface/--accent…），唔碰任何排版
 *   - 隨機只抽「色相 + 明暗模式」，飽和度／亮度由公式控制，確保文字永遠夠對比
 *   - 組合本身極細（mode + 兩個色相），存喺後端 users.theme，登入即還原
 */
'use strict';

const THEME_KEY = 'mc_theme_v1';

/** 所有會被主題覆寫嘅 CSS 變數（清走時用） */
const THEME_VARS = [
    '--bg-1', '--bg-2', '--panel-1', '--panel-2',
    '--surface', '--surface-2', '--fg', '--text',
    '--muted', '--muted-2', '--line',
    '--accent', '--accent-2', '--accent-rgb', '--on-accent', '--on-panel',
    '--secondary', '--secondary-dark',
    '--danger', '--danger-dark',
    '--success', '--success-dark', '--success-bg', '--success-fg',
    '--warning-bg', '--warning-fg'
];

function hslToRgb(h, s, l) {
    s /= 100; l /= 100;
    const k = n => (n + h / 30) % 12;
    const a = s * Math.min(l, 1 - l);
    const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return [f(0), f(8), f(4)].map(v => Math.round(v * 255));
}

function hslToRgbTriplet(h, s, l) {
    return hslToRgb(h, s, l).join(', ');
}

/** 相對亮度（WCAG） */
function hslLuminance(h, s, l) {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const rgb = hslToRgb(h, s, l);
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
}

/**
 * 自動揀按鈕上嘅字色：亮底用深字、暗底用白字。
 * 咁樣任何色相（尤其係黃／橙呢類天生高亮度嘅色）都夠對比，
 * 唔需要為咗對比而將主色壓到暗啞。
 */
function onAccentColor(h, s, l) {
    return hslLuminance(h, s, l) > 0.19 ? `hsl(${h}, 45%, 8%)` : '#ffffff';
}

/**
 * 避開「對比死區」：亮度介乎 0.183 同 0.225 之間時，
 * 白字同深字都達唔到 4.5:1，所以微調主色亮度跳出呢個區間。
 */
function tuneAccentLightness(h, s, l) {
    for (let i = 0; i < 8; i++) {
        const L = hslLuminance(h, s, l);
        if (L <= 0.1833 || L >= 0.2245) break;
        l += L > 0.20 ? 2 : -2;
    }
    return Math.max(20, Math.min(70, Math.round(l)));
}

const norm360 = x => ((Math.round(x) % 360) + 360) % 360;

/** 主題（mode + hue + accentHue）轉成 CSS 變數 */
function themeToVars(t) {
    const bgH = norm360(t.hue);
    const acH = norm360(t.accentHue);

    if (t.mode === 'dark') {
        const acL_d = tuneAccentLightness(acH, 68, 58);
        return {
            '--bg-1': `hsl(${bgH}, 22%, 15%)`,
            '--bg-2': `hsl(${norm360(t.hue + 25)}, 26%, 8%)`,
            '--panel-1': `hsl(${bgH}, 26%, 12%)`,
            '--panel-2': `hsl(${norm360(t.hue + 200)}, 28%, 9%)`,
            '--surface': `hsl(${bgH}, 18%, 15%)`,
            '--surface-2': `hsl(${bgH}, 16%, 21%)`,
            '--fg': `hsl(${bgH}, 12%, 96%)`,
            '--text': `hsl(${bgH}, 12%, 89%)`,
            '--muted': `hsl(${bgH}, 10%, 69%)`,
            '--muted-2': `hsl(${bgH}, 8%, 56%)`,
            '--line': `hsl(${bgH}, 14%, 28%)`,
            '--accent': `hsl(${acH}, 68%, ${acL_d}%)`,
            '--accent-2': `hsl(${norm360(t.accentHue + 24)}, 60%, ${acL_d - 14}%)`,
            '--accent-rgb': hslToRgbTriplet(acH, 68, acL_d),
            '--on-accent': onAccentColor(acH, 68, acL_d),
            '--on-panel': `hsl(${bgH}, 10%, 97%)`,
            '--secondary': `hsl(${bgH}, 10%, 42%)`,
            '--secondary-dark': `hsl(${bgH}, 10%, 35%)`,
            '--danger': `hsl(2, 65%, 60%)`,
            '--danger-dark': `hsl(2, 58%, 48%)`,
            '--success': `hsl(145, 45%, 52%)`,
            '--success-dark': `hsl(145, 48%, 40%)`,
            '--success-bg': `hsl(145, 30%, 18%)`,
            '--success-fg': `hsl(145, 45%, 78%)`,
            '--warning-bg': `hsl(45, 35%, 19%)`,
            '--warning-fg': `hsl(45, 70%, 74%)`
        };
    }

    // 淺色：accent 42% 保持鮮明，字色由 onAccentColor() 自動揀（暖色用深字）
    const acL_l = tuneAccentLightness(acH, 62, 42);
    return {
        '--bg-1': `hsl(${bgH}, 58%, 66%)`,
        '--bg-2': `hsl(${norm360(t.hue + 32)}, 46%, 52%)`,
        '--panel-1': `hsl(${norm360(t.hue + 215)}, 40%, 14%)`,
        '--panel-2': `hsl(${norm360(t.hue + 235)}, 42%, 22%)`,
        '--surface': '#ffffff',
        '--surface-2': `hsl(${bgH}, 45%, 97%)`,
        '--fg': `hsl(${acH}, 32%, 17%)`,
        '--text': `hsl(${bgH}, 14%, 24%)`,
        '--muted': `hsl(${bgH}, 10%, 42%)`,
        '--muted-2': `hsl(${bgH}, 8%, 58%)`,
        '--line': `hsl(${bgH}, 20%, 88%)`,
        '--accent': `hsl(${acH}, 62%, ${acL_l}%)`,
        '--accent-2': `hsl(${norm360(t.accentHue + 26)}, 54%, ${acL_l - 10}%)`,
        '--accent-rgb': hslToRgbTriplet(acH, 62, acL_l),
        '--on-accent': onAccentColor(acH, 62, acL_l),
        '--on-panel': '#ffffff',
        '--secondary': '#6c757d',
        '--secondary-dark': '#5a6268',
        '--danger': '#e74c3c',
        '--danger-dark': '#c0392b',
        '--success': '#27ae60',
        '--success-dark': '#218838',
        '--success-bg': '#d4edda',
        '--success-fg': '#155724',
        '--warning-bg': '#fff3cd',
        '--warning-fg': '#856404'
    };
}

/** 套用主題；傳 null 即還原預設紫色 */
function applyTheme(t) {
    const root = document.documentElement;
    THEME_VARS.forEach(name => root.style.removeProperty(name));
    if (t && t.mode) {
        const vars = themeToVars(t);
        Object.keys(vars).forEach(name => root.style.setProperty(name, vars[name]));
        root.dataset.theme = t.mode;
    } else {
        root.dataset.theme = 'light';
    }
    try {
        if (t && t.mode) localStorage.setItem(THEME_KEY, JSON.stringify(t));
        else localStorage.removeItem(THEME_KEY);
    } catch (e) { /* 私密模式等情況就唔記 */ }
}

let lastTheme = null;

/** 隨機抽一個組合：模式 + 底色色相 + 主色色相（同色系 / 互補 / 完全隨機） */
function randomTheme() {
    const mode = Math.random() < 0.5 ? 'light' : 'dark';
    const hue = Math.floor(Math.random() * 360);
    const r = Math.random();
    let accentHue;
    if (r < 0.5) accentHue = hue + (Math.random() * 70 - 35);        // 同色系
    else if (r < 0.82) accentHue = hue + 180 + (Math.random() * 50 - 25); // 互補
    else accentHue = Math.floor(Math.random() * 360);                // 完全隨機
    const t = { mode, hue: norm360(hue), accentHue: norm360(accentHue) };
    // 避免連續兩次太似
    if (lastTheme && lastTheme.mode === t.mode && Math.abs(lastTheme.hue - t.hue) < 15) {
        t.hue = norm360(t.hue + 137);
    }
    lastTheme = t;
    return t;
}

async function drawRandomTheme() {
    const btn = document.getElementById('theme-btn');
    if (btn) {
        btn.classList.add('spin');
        setTimeout(() => btn.classList.remove('spin'), 520);
    }
    const t = randomTheme();
    applyTheme(t);
    try {
        const response = await fetch(API_BASE + '/user-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ theme: t })
        });
        if (response.status === 401) {
            showToast('請先登入', 'error');
        } else if (!response.ok) {
            showToast('換咗色，但記唔到落帳戶', 'error');
        } else {
            showToast('🎲 已換色，下次登入都會記住');
        }
    } catch (error) {
        console.error('儲存主題失敗:', error);
        showToast('換咗色，但記唔到落帳戶', 'error');
    }
}

/* 一載入就先用上次抽到嘅組合（避免先閃一下紫色），登入後再以後端為準 */
(function initTheme() {
    try {
        const cached = localStorage.getItem(THEME_KEY);
        if (cached) applyTheme(JSON.parse(cached));
    } catch (e) { /* ignore */ }

    const wire = () => {
        const btn = document.getElementById('theme-btn');
        if (btn) btn.addEventListener('click', drawRandomTheme);
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', wire);
    } else {
        wire();
    }
})();
