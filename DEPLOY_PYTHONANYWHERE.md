# 🚀 部署到 PythonAnywhere

## 快速參考

| 步驟 | 命令/操作 |
|------|-----------|
| 拉取代碼 | `git clone https://github.com/Kamangkw/macau-coupons.git` |
| 安裝套件 | `pip install --user Flask Flask-SQLAlchemy` |
| 更新代碼 | `cd ~/macau-coupons && git pull` |
| 重啟網站 | 點擊 Web 頁面的 "Reload web app" |

---

## 完整安裝步驟

### 第一步：創建 PythonAnywhere 帳戶

1. 去 https://www.pythonanywhere.com/ 
2. 選擇 "Hacker" (免費)
3. 創建帳戶

### 第二步：開啟 Bash 並拉取代碼

```bash
git clone https://github.com/Kamangkw/macau-coupons.git
cd macau-coupons
pip install --user Flask Flask-SQLAlchemy
```

### 第三步：設置 Web 應用

1. Web → Add a new web app → Flask → Python 3.x
2. Path 輸入 `main.py`

### 第四步：修改 WSGI 配置

找到 WSGI configuration file，替換為：

```python
import sys
import os

path = '/home/kamangkw/macau-coupons'
if path not in sys.path:
    sys.path.insert(0, path)

from main import app as application
```

### 第五步：完成！

訪問：`https://kamangkw.pythonanywhere.com`

---

## 🔄 如何更新代碼

當你在本地修改了代碼後，需要按以下步驟更新到 PythonAnywhere：

### 方法一：使用 Git Pull（推薦）

1. **在本地更新代碼**（在你電腦的 `python_project` 資料夾）
2. **推送更新到 GitHub**：
   ```cmd
   cd Desktop\git\python_project
   git add .
   git commit -m "你的更新說明"
   git push
   ```
3. **在 PythonAnywhere 更新**：
   - 開啟 Bash
   - 輸入：
   ```bash
   cd ~/macau-coupons
   git pull
   ```
4. **點擊 "Reload web app"**

---

### 方法二：手動上傳

如果 Git pull 有問題：

1. 在 PythonAnywhere 開啟 **Files** 頁面
2. 進入 `macau-coupons` 資料夾
3. 點擊每個檔案旁邊的 ✏️ 編輯
4. 複製貼上你本地的最新代碼
5. 點擊 "Reload web app"

---

## 📁 需要更新的檔案

| 檔案 | 說明 |
|------|------|
| `main.py` | Flask 後端程式 |
| `templates/index.html` | 網頁介面 |
| `static/css/style.css` | 樣式表 |
| `static/js/app.js` | 前端 JavaScript |

---

## ⚠️ 常見問題

**Q: git pull 失敗？**
A: 嘗試 `cd ~/macau-coupons && git stash && git pull`

**Q: 網頁還是舊版？**
A: 確保點擊了 "Reload web app" 按鈕

**Q: 出現錯誤？**
A: 在 Bash 中重新安裝套件：
```bash
pip install --user Flask Flask-SQLAlchemy
```
