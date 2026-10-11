"""
澳門消費券記錄系統 - Macau Consumption Voucher Record System
Flask 後端應用程式
"""

import json
import itertools
import os
import sys
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timezone
from functools import wraps
import secrets

app = Flask(__name__)

app.config["SECRET_KEY"] = "macau-coupons-secret-key-2026"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///coupons.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

PLATFORMS = [
    "工商銀行",
    "國際銀行",
    "支付寶",
    "大豐銀行",
    "UEpay",
    "廣發銀行",
    "Mpay",
    "中國銀行",
]

# 平台 → 手機 app 連結（前端會將平台名變成可點連結，收銀時一按就開到對應 app）。
#
# scheme_ios：iOS 自訂 URL scheme。有填＝一按直接開 app；
#             留空＝未經實測證實，改用 store（App Store 連結，入到去再㩒「開啟」）。
#             ⚠️ 呢啲澳門 app 嘅 scheme 大多冇公開文件（MPay 官方 SDK 文件都只講
#             「scheme 由澳門通提供」），胡亂填會令 Safari 彈「無法打開網頁」，
#             所以留空比亂填好。想填之前，先喺 iPhone Safari 網址欄打個 scheme
#             試下有冇開到 app，實測得到先填。
#             2026-10-11 實測：支付寶用 alipay:// 按落去冇反應（偉仔報），
#             所以暫時八個平台一律用 App Store 連結。
# store：App Store 頁（已用 iTunes Search API 核對過開發者係邊間機構）。
PLATFORM_APPS = {
    "Mpay": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id1092594338"},
    "UEpay": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id1262244387"},
    "支付寶": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id333206289"},
    "中國銀行": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id479179008"},
    "工商銀行": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id584398176"},
    "大豐銀行": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id500132293"},
    "國際銀行": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id1014923812"},
    "廣發銀行": {"scheme_ios": "", "store": "https://apps.apple.com/mo/app/id1002337256"},
}

# 2026-10-10：抽獎唔再出「0 元」選項，改為 12 元消費券。
# 舊有 amount = 0 嘅記錄會由 run_migrations() 一次性改成 12（其他欄位一律不變）。
COUPON_AMOUNTS = [10, 12, 20, 50, 100, 200]

# 「禮遇券」：非現金獎品，冇面額。內部用 -1 代表（唔可以用 0，因為遷移會將 0 當舊資料）。
# 佢會計入張數，但唔會計入任何金額總和（見 get_summary 嘅 money case）。
COURTESY_AMOUNT = -1

# 下拉選項＝現金券面額 + 禮遇券
COUPON_OPTIONS = COUPON_AMOUNTS + [COURTESY_AMOUNT]
VALID_AMOUNTS = set(COUPON_OPTIONS)


def amount_label(amount):
    """獎項顯示名：禮遇券 / $12券 / N元（前端 app.js 嘅 amountLabel 要一致）。"""
    if amount == COURTESY_AMOUNT:
        return "禮遇券"
    return "$12券" if amount == 12 else f"{amount}元"


AMOUNT_LABELS = {a: amount_label(a) for a in COUPON_OPTIONS}


# ── 消費計算器規則（2026-10-11）─────────────────────────────────────
# 偉仔確認嘅實際規則：
#   1. 一般券（10/20/50/100/200）：整筆消費嘅「券總值 × 3」唔可以超過消費額
#      （即係每張券背後要有 3 倍消費支撐；疊用時睇總值，例：消費 60 最多用 20 元券）
#   2. 12 元券係例外：改為「消費滿 100 元」＋「商舖允許」先可以用，
#      但仍然計入上面嘅券總值上限（唔係額外豁免）
#   3. 券可以疊用，跨平台分開支付都可以疊
SPEND_MULTIPLIER = 3
SPECIAL_AMOUNT = 12
SPECIAL_MIN_SPEND = 100
MAX_CALC_AMOUNT = 1_000_000


def minimum_spend_for(value):
    """單張券嘅最低消費：禮遇券 0、12 元券 100（另需商舖允許）、其餘＝面額 × 3。"""
    if value == COURTESY_AMOUNT:
        return 0
    if value == SPECIAL_AMOUNT:
        return SPECIAL_MIN_SPEND
    return value * SPEND_MULTIPLIER


def denomination_rules(amount, allow_special=False):
    """呢筆消費之下，每個面額用唔用得同所需最低消費。"""
    rows = []
    for value in COUPON_AMOUNTS:
        required = minimum_spend_for(value)
        if value == SPECIAL_AMOUNT:
            usable = amount >= required and allow_special
        else:
            usable = amount >= required
        rows.append(
            {
                "amount": value,
                "label": amount_label(value),
                "usable": usable,
                "required_spend": required,
                "special": value == SPECIAL_AMOUNT,
                "reason": reason_for(value, amount, allow_special, usable),
            }
        )
    return rows


def reason_for(value, amount, allow_special, usable):
    """唔可用時解釋點解，可用時畀個簡短原因（前端顯示用）。"""
    if usable:
        return "已符合條件"
    if value == SPECIAL_AMOUNT:
        # 12 元券嘅條件係「單一平台支付滿 100」（唔係全單滿 100）
        needs = [f"單一平台支付滿 {SPECIAL_MIN_SPEND} 元"]
        if not allow_special:
            needs.append("商舖允許")
        return "＋".join(needs)
    return f"需消費滿 {minimum_spend_for(value)} 元"


def coupon_eligible(coupon, amount, allow_special):
    """呢張券喺呢筆消費之下用唔用得（禮遇券唔參與金額計算）。"""
    if coupon.amount == COURTESY_AMOUNT:
        return False
    if coupon.amount == SPECIAL_AMOUNT:
        return amount >= SPECIAL_MIN_SPEND and allow_special
    return True


def best_within(coupons, cap):
    """0/1 背包：喺 cap 之內揀最大券值；同樣總值之下揀較少張數。

    回傳 (總值, [Coupon…])。輸入次序＝偏好次序（最早抽到嗰張喺最前）。
    """
    dp = {0: []}
    for c in coupons:
        for total in sorted(dp, reverse=True):
            nxt = total + c.amount
            if nxt > cap:
                continue
            cand = dp[total] + [c]
            current = dp.get(nxt)
            if current is None or len(cand) < len(current):
                dp[nxt] = cand
    best = max(dp)
    return best, dp[best]


def subset_options(coupons, amount):
    """一個平台嘅可選組合清單：[(支付總數, 券值, [Coupon…], 用完？), …]

    支付總數＝呢個平台最少要支付幾多：
      • 一般券：3 × 券總值（消費滿 3 倍先可以用）
      • 有 12 元券：max(3 × 券總值, 100)（12 元券要「單一平台支付滿 100」）
        ← 注意：當平台本身已經要支付 ≥100（3 倍 ≥100），12 元券係「免費搭車」

    第 4 個元素「用完？」＝呢個組合會唔會用光該平台所有合資格未用券
    （用光＝以後唔使再為呢個平台開 app）。

    假設：同一個平台嘅支付最多用 1 張 12 元券（滿減券一般每筆一次；
    如果實際可以疊多張，改 SPECIAL_MAX_PER_PAY 就得）。
    """
    general = [c for c in coupons if c.amount != SPECIAL_AMOUNT]
    specials = [c for c in coupons if c.amount == SPECIAL_AMOUNT]

    # 一般券：可行券值總和 → 最少張數組合（總和上限 = amount // 3）
    limit = amount // SPEND_MULTIPLIER
    sums = {0: []}
    for c in general:
        for total in sorted(sums, reverse=True):
            nxt = total + c.amount
            if nxt > limit:
                continue
            cand = sums[total] + [c]
            current = sums.get(nxt)
            if current is None or len(cand) < len(current):
                sums[nxt] = cand

    options = [(0, 0, [], False)]
    for total, combo in sums.items():
        if total == 0:
            continue
        options.append(
            (total * SPEND_MULTIPLIER, total, list(combo), len(combo) == len(coupons))
        )
    if specials:
        for total, combo in sums.items():
            cost = max(total * SPEND_MULTIPLIER, SPECIAL_MIN_SPEND)
            if cost > amount:
                continue
            picked = list(combo) + [specials[0]]
            options.append(
                (cost, total + SPECIAL_AMOUNT, picked, len(picked) == len(coupons))
            )
    return options


def _combo_score(state):
    """組合排序分數：① 券值最大 ② 平台數最少 ③ 用完（清零）嘅平台最多 ④ 張數最少。

    第 ③ 條係偉仔要求：同樣券值同平台數之下，寧願揀一個「今次可以用光」
    嘅平台，因為用光之後就唔使再為佢開 app（例：A 有 $20/$20/$10、
    B 只有 $20/$20，消費 $120 → 揀 B，B 清倉）。
    """
    value, plats, cleared, count = state[0], state[1], state[2], state[3]
    return (value, -plats, cleared, -count)


def pick_best_combo(unused_coupons, amount, allow_special):
    """砌出最佳券組合，目標：① 券值最大 ② 平台數最少 ③ 用完嘅平台最多 ④ 張數最少。

    限制係「每個平台嘅支付總數」：一個平台支付 $X 只可以支撐
    3X 以內嘅一般券，或者（有 12 元券時）X 要去到 100。
    所以 $100 消費用唔到「$20 券（要支付 60）＋ $12 券（要支付 100）」＝ 160。

    回傳 dict（picked / total_value / platform_count / groups / unused_eligible）。
    """
    empty = {
        "picked": [],
        "total_value": 0,
        "platform_count": 0,
        "groups": [],
        "unused_eligible": 0,
    }
    pool = [c for c in unused_coupons if coupon_eligible(c, amount, allow_special)]
    if not pool or amount <= 0:
        return empty

    # FIFO：最早抽到嘅排最前
    pool.sort(key=lambda c: (c.draw_date or date.min, c.id))

    by_platform = {}
    for c in pool:
        by_platform.setdefault(c.platform, []).append(c)

    options = {}
    for platform, coupons in by_platform.items():
        usable = [o for o in subset_options(coupons, amount) if o[0] <= amount]
        if len(usable) > 1:
            options[platform] = usable

    if not options:
        return empty

    # 分組背包：cost → (券值, 平台數, 用完平台數, 張數, 指派)。每個平台最多揀一個選項。
    # 平台次序跟「最早抽到嘅券」，令同樣券值時 FIFO 決定邊個平台先。
    platform_order = sorted(
        options,
        key=lambda p: (
            min(c.draw_date or date.min for c in by_platform[p]),
            p,
        ),
    )
    best = {0: (0, 0, 0, 0, {})}
    for platform in platform_order:
        updated = dict(best)
        for cost, (value, plats, cleared, count, assign) in best.items():
            for ocost, ovalue, ocombo, ocleared in options[platform]:
                if ocost == 0:
                    continue
                ncost = cost + ocost
                if ncost > amount:
                    continue
                cand = (
                    value + ovalue,
                    plats + 1,
                    cleared + (1 if ocleared else 0),
                    count + len(ocombo),
                    {**assign, platform: (ocost, ovalue, ocombo, ocleared)},
                )
                current = updated.get(ncost)
                if current is None or _combo_score(cand) > _combo_score(current):
                    updated[ncost] = cand
        best = updated

    best_cost = max(best, key=lambda c: _combo_score(best[c]))
    value, platform_count, _cleared, _count, assign = best[best_cost]

    groups = []
    picked = []
    # 券值大嘅平台排前面；最後一個負責吸收零頭
    for platform in sorted(assign, key=lambda p: (-assign[p][1], p)):
        ocost, ovalue, ocombo, ocleared = assign[platform]
        picked.extend(ocombo)
        groups.append(
            {
                "platform": platform,
                "count": len(ocombo),
                "total": ovalue,
                "amounts": sorted((c.amount for c in ocombo), reverse=True),
                "pay_min": ocost,        # 規則上最少要支付幾多（3 倍／100）
                "pay_total": ocost,      # 實際支付總數（下面會加零頭）
                "cash": ocost - ovalue,
                "cleared": ocleared,     # 呢個平台嘅券今次係唔係全部用光
            }
        )

    # 零頭撥入最後一個平台，令各平台支付總數加起來剛剛好等於消費金額
    if groups:
        remainder = amount - best_cost
        if remainder > 0:
            last = groups[-1]
            last["pay_total"] += remainder
            last["cash"] = last["pay_total"] - last["total"]

    return {
        "picked": picked,
        "total_value": value,
        "platform_count": platform_count,
        "groups": groups,
        "unused_eligible": len(pool) - len(picked),
    }



def parse_theme(raw):
    """驗證前端抽到嘅顏色組合，回傳 (ok, 可以儲存嘅 JSON 字串或 None)。

    只存「配方」（明暗模式 + 底色色相 + 主色色相），唔存實際色值，
    所以日後調整配色公式，舊用戶抽到嘅組合會自動跟住更新。
    """
    if raw is None:
        return True, None
    if not isinstance(raw, dict) or raw.get("mode") not in ("light", "dark"):
        return False, None
    out = {"mode": raw["mode"]}
    for key in ("hue", "accentHue"):
        if key not in raw:           # 缺欄位一律當無效，唔可以靜靜當 0
            return False, None
        try:
            value = int(raw[key])
        except (TypeError, ValueError):
            return False, None
        if not 0 <= value <= 359:
            return False, None
        out[key] = value
    return True, json.dumps(out, separators=(",", ":"))


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    form_collapsed = db.Column(db.Boolean, default=False)
    # 舊「全澳抽獎趨勢」模組已於 2026-10-10 移除。呢個欄位保留唔刪，
    # 避免改動現有資料庫結構；程式已唔再讀寫佢。
    trends_collapsed = db.Column(db.Boolean, default=False)
    # 隨機抽到嘅顏色組合（JSON 字串，例 {"mode":"dark","hue":210,"accentHue":275}）。
    # NULL = 用預設紫色。
    theme = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    coupons = db.relationship("Coupon", backref="user", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "form_collapsed": self.form_collapsed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Coupon(db.Model):
    __tablename__ = "coupons"
    __table_args__ = (
        db.Index("idx_coupon_user_platform", "user_id", "platform"),
        db.Index("idx_coupon_user_used", "user_id", "is_used"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    draw_date = db.Column(db.Date, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "platform": self.platform,
            "amount": self.amount,
            "draw_date": self.draw_date.isoformat() if self.draw_date else None,
            "is_used": self.is_used,
            "used_date": self.used_date.isoformat() if self.used_date else None,
            # 最低消費：禮遇券 0、12 元券 $100（另需商舖允許）、其餘＝面額 × 3。
            # 同消費計算器用同一個規則函式，避免兩邊唔一致。
            "minimum_spend": minimum_spend_for(self.amount),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── 一次性資料遷移（2026-10-10）─────────────────────────────────────
# 舊「0 元」抽獎選項已改為 12 元消費券。只更新 amount = 0 嘅記錄；
# id / user_id / platform / draw_date / is_used / used_date / created_at 一律唔動。
# 注意：禮遇券用 -1，所以唔會被呢句誤中。
_migration_done = False


def run_migrations():
    """每個 process 只跑一次；冇 0 元記錄時影響 0 行，重複執行都安全。"""
    global _migration_done
    if _migration_done:
        return
    try:
        result = db.session.execute(
            db.text("UPDATE coupons SET amount = 12 WHERE amount = 0")
        )
        db.session.commit()
        if result.rowcount:
            print(
                f"[migration] 0 元 → 12 元：更新咗 {result.rowcount} 筆記錄",
                file=sys.stderr,
            )
        _migration_done = True
    except Exception as exc:  # 失敗就唔設旗標，下個請求會再試
        db.session.rollback()
        print(f"[migration] 失敗（會再試）：{exc}", file=sys.stderr)


@app.before_request
def ensure_db():
    db.create_all()
    try:
        result = db.session.execute(db.text("PRAGMA table_info(users)")).fetchall()
        columns = [r[1] for r in result]
        if "form_collapsed" not in columns:
            db.session.execute(
                db.text("ALTER TABLE users ADD COLUMN form_collapsed BOOLEAN DEFAULT 0")
            )
        if "trends_collapsed" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE users ADD COLUMN trends_collapsed BOOLEAN DEFAULT 0"
                )
            )
        if "theme" not in columns:
            db.session.execute(
                db.text("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT NULL")
            )
        db.session.commit()
    except Exception:
        db.session.rollback()

    run_migrations()


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "請求格式錯誤"}), 400


@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "請先登入"}), 401


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "找不到資源"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "伺服器錯誤，請稍後再試"}), 500


def get_user_id():
    return session.get("user_id")


@app.route("/")
def index():
    user_name = session.get("user_name")
    return render_template(
        "index.html",
        platforms=PLATFORMS,
        coupon_options=COUPON_OPTIONS,
        amount_labels=AMOUNT_LABELS,
        user_name=user_name,
    )


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "請輸入姓名"}), 400

    user = User.query.filter_by(name=name).first()
    if not user:
        user = User(name=name)
        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.id
    session["user_name"] = user.name

    return jsonify(user.to_dict())


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "已登出"})


@app.route("/api/current-user")
def get_current_user():
    user_name = session.get("user_name")
    user_id = session.get("user_id")
    if user_name:
        return jsonify({"id": user_id, "name": user_name})
    return jsonify(None)


@app.route("/api/user-settings", methods=["GET"])
def get_user_settings():
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用戶不存在"}), 404

    theme = None
    if user.theme:
        try:
            theme = json.loads(user.theme)
        except (TypeError, ValueError):
            theme = None

    return jsonify(
        {
            "form_collapsed": user.form_collapsed if user.form_collapsed else False,
            "theme": theme,
        }
    )


@app.route("/api/user-settings", methods=["POST"])
def update_user_settings():
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用戶不存在"}), 404

    data = request.get_json()

    if "form_collapsed" in data:
        user.form_collapsed = data["form_collapsed"]
    if "theme" in data:
        ok, stored = parse_theme(data["theme"])
        if not ok:
            return jsonify({"error": "顏色組合格式錯誤"}), 400
        user.theme = stored
    db.session.commit()
    return jsonify({"message": "設置已保存"})


@app.route("/api/coupons", methods=["GET"])
def get_coupons():
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    page = request.args.get("page", 1, type=int)
    per_page = 25

    pagination = (
        Coupon.query.filter_by(user_id=user_id)
        .order_by(Coupon.draw_date.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify(
        {
            "coupons": [c.to_dict() for c in pagination.items],
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": page,
        }
    )


@app.route("/api/coupons", methods=["POST"])
def create_coupon():
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    data = request.get_json()
    coupons_data = data.get("coupons", [])

    if len(coupons_data) > 3:
        return jsonify({"error": "一次最多新增3條記錄"}), 400
    if len(coupons_data) == 0:
        return jsonify({"error": "請選擇券面額"}), 400

    # 先全部驗證，避免半途插入
    parsed = []
    for item in coupons_data:
        try:
            amount = int(item["amount"])
            platform = item["platform"]
            draw_date = datetime.strptime(item["draw_date"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "記錄格式錯誤"}), 400
        if amount not in VALID_AMOUNTS:
            return jsonify({"error": "券面額無效"}), 400
        parsed.append((platform, amount, draw_date))

    created = []
    for platform, amount, draw_date in parsed:
        coupon = Coupon(
            user_id=user_id,
            platform=platform,
            amount=amount,
            draw_date=draw_date,
        )
        db.session.add(coupon)
        created.append(coupon)
    db.session.commit()
    return jsonify([c.to_dict() for c in created]), 201


@app.route("/api/coupons/<int:id>", methods=["PUT"])
def update_coupon(id):
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    coupon = Coupon.query.filter_by(id=id, user_id=user_id).first_or_404()
    data = request.get_json()

    if "platform" in data:
        coupon.platform = data["platform"]
    if "amount" in data:
        try:
            amount = int(data["amount"])
        except (TypeError, ValueError):
            return jsonify({"error": "券面額無效"}), 400
        if amount not in VALID_AMOUNTS:
            return jsonify({"error": "券面額無效"}), 400
        coupon.amount = amount
    if "draw_date" in data:
        coupon.draw_date = datetime.strptime(data["draw_date"], "%Y-%m-%d").date()
    if "is_used" in data:
        coupon.is_used = data["is_used"]
        coupon.used_date = date.today() if data["is_used"] else None
    db.session.commit()
    return jsonify(coupon.to_dict())


@app.route("/api/coupons/<int:id>", methods=["DELETE"])
def delete_coupon(id):
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    coupon = Coupon.query.filter_by(id=id, user_id=user_id).first_or_404()
    db.session.delete(coupon)
    db.session.commit()
    return jsonify({"message": "Deleted successfully"})


@app.route("/api/coupons/clear-all", methods=["POST"])
def clear_all_coupons():
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    Coupon.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({"message": "All coupons deleted"})


@app.route("/api/summary", methods=["GET"])
def get_summary():
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    summary = []
    total_unused = 0

    # 禮遇券（-1）唔計錢，當 0 計；張數照計
    money = db.case((Coupon.amount == COURTESY_AMOUNT, 0), else_=Coupon.amount)

    for platform in PLATFORMS:
        result = (
            db.session.query(
                db.func.sum(db.case((Coupon.is_used == False, money), else_=0)).label(
                    "unused_total"
                ),
                db.func.sum(db.case((Coupon.is_used == True, money), else_=0)).label(
                    "used_total"
                ),
                db.func.count(db.case((Coupon.is_used == False, 1))).label(
                    "unused_count"
                ),
                db.func.count(db.case((Coupon.is_used == True, 1))).label("used_count"),
            )
            .filter(Coupon.user_id == user_id, Coupon.platform == platform)
            .first()
        )

        unused_total = result.unused_total or 0
        used_total = result.used_total or 0
        total_unused += unused_total

        coupons = (
            Coupon.query.filter_by(user_id=user_id, platform=platform)
            .order_by(Coupon.draw_date.desc())
            .all()
        )

        summary.append(
            {
                "platform": platform,
                "total_coupon": unused_total,
                "platform_total": used_total,
                "used_count": result.used_count or 0,
                "unused_count": result.unused_count or 0,
                "total_count": (result.used_count or 0) + (result.unused_count or 0),
                "coupons": [c.to_dict() for c in coupons],
            }
        )

    return jsonify(
        {
            "platforms": summary,
            "total_unused": total_unused,
            # 平台 → app 連結（前端將平台名變成可點連結）
            "platform_apps": PLATFORM_APPS,
        }
    )


@app.route("/api/calculator", methods=["POST"])
def calculate_spend():
    """消費計算器：輸入消費金額，計出可以用幾多券（可以疊用、跨平台分開支付）。

    規則：券總值 × SPEND_MULTIPLIER ≤ 消費額；12 元券例外，要消費滿
    SPECIAL_MIN_SPEND 而且商舖允許。組合由手上「未使用」嘅券砌出，同一券值
    之下會揀較少張數，實際用最早抽到嘅先（FIFO）。
    """
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    data = request.get_json(silent=True) or {}
    try:
        raw = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "請輸入有效嘅消費金額"}), 400
    if not 0 < raw <= MAX_CALC_AMOUNT:
        return jsonify({"error": "請輸入有效嘅消費金額"}), 400

    amount = int(raw)  # 澳門消費以元為單位，小數向下取整
    allow_special = bool(data.get("allow_special"))

    unused = (
        Coupon.query.filter_by(user_id=user_id, is_used=False)
        .order_by(Coupon.draw_date.asc(), Coupon.id.asc())
        .all()
    )
    result = pick_best_combo(unused, amount, allow_special)
    picked = result["picked"]

    inventory = {}
    for coupon in unused:
        key = str(coupon.amount)
        inventory[key] = inventory.get(key, 0) + 1

    return jsonify(
        {
            "amount": amount,
            "cap": amount // SPEND_MULTIPLIER,
            "max_value": result["total_value"],
            "pay_after": amount - result["total_value"],
            "combo": [c.to_dict() for c in picked],
            # 每個平台：券 + 實際支付總數（pay_total，最後一個已含零頭）同其中現金
            "by_platform": result["groups"],
            "platform_count": result["platform_count"],
            "unused_eligible": result["unused_eligible"],
            "denominations": denomination_rules(amount, allow_special),
            "inventory": inventory,
            "allow_special": allow_special,
            # 平台 → app 連結（前端將平台名變成可點連結）
            "platform_apps": PLATFORM_APPS,
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
