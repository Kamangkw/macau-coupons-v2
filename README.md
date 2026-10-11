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
pip install --user Flask Flask-SQLAlchemy
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

## 💡 消費券規則（2026-10-11 更新）

| 券面額 | 最低消費 | 備註 |
|--------|----------|------|
| 10 元 | 30 元 | |
| 12 元 | 100 元 | ⚠️ 例外：仲要「商舖允許」先用得 |
| 20 元 | 60 元 | |
| 50 元 | 150 元 | |
| 100 元 | 300 元 | |
| 200 元 | 600 元 | |

**可以疊用**：一筆消費可以用多張券（跨平台分開支付都可以疊）。限制係
**「每個平台嘅支付總數」**：

- 一般券：該平台支付 × 1/3 ≥ 券值（即係支付 3 倍先可以用）
- $12 券：改為「**單一平台支付滿 100 元**」＋商舖允許（唔跟 3 倍規則）
- 所以消費 100 元用唔到「$20 券（要支付 60）＋ $12 券（要支付 100）」＝ 160 > 100

### 🧮 消費計算器

應用程式底部有計算器：輸入消費金額（可 tick「商舖允許用 $12 券」），即刻顯示
可用券組合、**每個平台要支付幾多**、現金實付，同每個面額用唔用得同原因。

**推薦排序目標（依次）：① 券值最大 → ② 平台數最少 → ③ 用完（清零）嘅平台最多 → ④ 張數最少**
「平台數最少」係因為喺收銀處每轉一個支付平台就要開多個 app／分開付款。
**偉仔 2026-10-11 確認：少開一個 app 優先過清倉**（就算要放棄清倉，
都唔想為咗清倉而多開一個 app）。「用完嘅平台最多」係次要考慮，例如：

```
工商銀行：$20 / $20 / $10      消費 $120
Mpay：    $20 / $20            → 兩邊都做到 $40，但會推薦 Mpay
                                 （一次過用光 Mpay，之後唔使再開）
```

輸出每個平台一行，主角係「平台 + 支付金額」（收銀時最關鍵）：

```
Mpay                            支付 $60
$20 券 · 現金 $40

UEpay                           支付 $40
$10 券 · 現金 $30

現金實付 $70　（消費 $100）
用券 $30
```

- 「支付總數」＝該平台實際要支付幾多；**最後一個平台會加上零頭**，
  令各平台支付總數加起來**剛剛好等於消費金額**
- **平台名係可點連結**：一按就開對應嘅手機 app。iOS 有實測證實嘅 URL scheme
  就直接開 app；未有 scheme 嘅會開 App Store 頁（app 已裝嘅話，嗰度有「開啟」）。
  ⚠️ 呢啲澳門 app 嘅 scheme 大多冇公開文件（MPay 官方 SDK 文件都只講「scheme 由
  澳門通提供」），所以只填證實咗嘅（支付寶 `alipay://`），其餘留空用 App Store 做後備 —
  改 `main.py` 嘅 `PLATFORM_APPS` 一行就加得
- 最底細字「用券 $X」只作記錄（唔係重點）
- 只會用你記錄為「未使用」嘅券；禮遇券唔參與金額計算
- 同一面額會用最早抽到嗰張（FIFO）
- 只讀，唔會改動任何記錄

> 2026-10-10 更新：抽獎唔再出「0 元」選項，改為 12 元消費券（介面顯示為「$12券」）；
> 舊有 0 元記錄會喺部署後首次啟動時自動改成 12 元（其他欄位不變）。
>
> 2026-10-11 更新：加入消費計算器；修正 12 元券嘅最低消費（由 36 元改為 100 元 ＋ 商舖允許）。

---

## 📱 本地使用方式

如果你想在本地運行：

```bash
cd Desktop\git\macau-coupons-v2
pip install Flask Flask-SQLAlchemy
python main.py
```

然後打開瀏覽器：http://localhost:5000

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
