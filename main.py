"""
澳門消費券記錄系統 - Macau Consumption Voucher Record System
Flask 後端應用程式
"""

import json
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
            # 禮遇券冇最低消費（唔可以將 -1 乘 3）
            "minimum_spend": 0
            if self.amount == COURTESY_AMOUNT
            else self.amount * 3,
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

    return jsonify({"platforms": summary, "total_unused": total_unused})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
