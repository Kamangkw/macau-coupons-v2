# 澳門消費券記錄系統 - 繁體中文使用指南

一個用於記錄澳門政府消費券的網頁應用程式。

---

## 🚀 部署到 PythonAnywhere（免費）

### 第一步：創建 GitHub 帳戶

1. 去 https://github.com/ 點擊 "Sign up"
2. 輸入用戶名、郵箱、密碼
3. 完成驗證

### 第二步：創建代碼倉庫

1. 登入 GitHub 後，點擊右上角 "+" → "New repository"
2. Repository name 輸入：`macau-coupons`
3. 選擇 "Private"（私人倉庫）
4. 點擊 "Create repository"

### 第三步：上傳代碼到 GitHub

1. 在你電腦上打開命令提示字元（Win + R → 輸入 `cmd`）
2. 進入專案資料夾：
```cmd
cd Desktop\git\python_project
```

3. 初始化 Git（如果還沒有的話）：
```cmd
git init
```

4. 添加所有文件：
```cmd
git add .
```

5. 提交：
```cmd
git commit -m "Initial commit"
```

6. 連接 GitHub：
```cmd
git remote add origin https://github.com/你的用戶名/macau-coupons.git
```

7. 上傳：
```cmd
git branch -M main
git push -u origin main
```

⚠️ 它會要求你輸入 GitHub 用戶名和密碼（Personal Access Token）

### 第四步：創建 PythonAnywhere 帳戶

1. 去 https://www.pythonanywhere.com/ 點擊 "Pricing"
2. 選擇 "Hacker" 免費計劃（可以建立一個 Flask 應用）
3. 點擊 "Create a Beginner account"
4. 輸入郵箱、密碼
5. 完成驗證

### 第五步：從 GitHub 拉取代碼

1. 登入 PythonAnywhere
2. 點擊 "Dashboard" → " consoles" → "Bash"
3. 輸入：
```bash
git clone https://github.com/你的用戶名/macau-coupons.git
```

4. 進入資料夾：
```bash
cd macau-coupons
```

### 第六步：安裝依賴

在 Bash 輸入：
```bash
pip install --user Flask Flask-SQLAlchemy cohere
```

### 第七步：設置 Web 應用

1. 點擊 "Dashboard" → "Web" → "Add a new web app"
2. 點擊 "Next" 直到選擇框架，選擇 "Flask"
3. Python 版本選擇 "Python 3.10" 或最新
4. 設定完成後，點擊進入 Web 應用設定

### 第八步：修改 WSGI 配置

1. 在 Web 頁面找到 "WSGI configuration file"，點擊進入
2. 刪除所有內容，替換為：

```python
import sys
import os

# 添加你的應用路徑
path = '/home/你的用戶名/macau-coupons'
if path not in sys.path:
    sys.path.insert(0, path)

from main import app as application
```

3. 點擊 "Save"

### 第九步：重啟應用

1. 返回 Web 頁面
2. 點擊 "Reload web app" 按鈕

### 第十步：完成！ 🎉

在瀏覽器打開 `https://你的用戶名.pythonanywhere.com`

---

## 💡 消費券規則

| 券面額 | 最低消費 | 實付金額 |
|--------|----------|----------|
| 10 元 | 30 元 | 20 元 |
| 20 元 | 60 元 | 40 元 |
| 50 元 | 150 元 | 100 元 |
| 100 元 | 300 元 | 200 元 |
| 200 元 | 600 元 | 400 元 |

---

## 📱 本地使用方式

如果你想在本地運行：

```bash
cd Desktop\git\macau-coupons-v2
pip install Flask Flask-SQLAlchemy cohere
python main.py
```

然後打開瀏覽器：http://localhost:5000

---

## 💬 AI 助手功能

系統內建 AI 助手，可以回答關於澳門消費券的問題。

### 使用方式

1. 點擊右下角的 💬 AI 助手按鈕
2. 直接輸入問題即可

### AI 可回答的問題

- 如何使用消費券？
- 最低消費是多少？
- 哪些支付平臺可以使用？
- 什麼時候可以抽獎？
- 消費券有效期？

---

## ⚠️ PythonAnywhere 免費版限制

- 只能有**一個** Web 應用
- 沒有 HTTPS（但可以正常使用）
- 國外伺服器，速度可能比香港伺服器慢
- 休眠後需要等待才能重新訪問

---

## ❓ 常見問題

**Q: 出現 "Module not found" 錯誤？**
A: 確保在 Bash 中執行了 `pip install Flask Flask-SQLAlchemy`

**Q: 網頁顯示 404？**
A: 檢查 WSGI 配置中的路徑是否正確，確保資料夾名稱匹配

**Q: 如何更新代碼？**
A: 修改本地代碼 → GitHub → PythonAnywhere Bash → `git pull`

---

## 技術棧

- **後端**：Flask (Python)
- **資料庫**：SQLite
- **前端**：HTML5 + CSS3 + JavaScript
- **AI**：Cohere (command-r-plus)
