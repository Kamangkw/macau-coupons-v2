"""
澳門消費券記錄系統 - Macau Consumption Voucher Record System
Flask 後端應用程式
"""

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timezone
from functools import wraps
import secrets

app = Flask(__name__)

SECRET_KEY_FILE = os.path.join(os.path.dirname(__file__), ".secret_key")

if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "r") as f:
        SECRET_KEY = f.read().strip()
else:
    SECRET_KEY = secrets.token_hex(16)
    with open(SECRET_KEY_FILE, "w") as f:
        f.write(SECRET_KEY)

if os.environ.get("FLASK_ENV") == "production":
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or SECRET_KEY
    if not app.config["SECRET_KEY"]:
        raise ValueError("SECRET_KEY environment variable must be set in production")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///coupons.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_ENABLED"] = True
else:
    app.config["SECRET_KEY"] = SECRET_KEY
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

COUPON_AMOUNTS = [0, 10, 20, 50, 100, 200]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    form_collapsed = db.Column(db.Boolean, default=False)
    trends_collapsed = db.Column(db.Boolean, default=False)
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
            "minimum_spend": self.amount * 3,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


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
        db.session.commit()
    except Exception:
        db.session.rollback()


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
        coupon_amounts=COUPON_AMOUNTS,
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

    return jsonify(
        {
            "form_collapsed": user.form_collapsed if user.form_collapsed else False,
            "trends_collapsed": user.trends_collapsed
            if hasattr(user, "trends_collapsed") and user.trends_collapsed
            else False,
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
    if "trends_collapsed" in data:
        user.trends_collapsed = data["trends_collapsed"]
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

    created = []
    for item in coupons_data:
        coupon = Coupon(
            user_id=user_id,
            platform=item["platform"],
            amount=int(item["amount"]),
            draw_date=datetime.strptime(item["draw_date"], "%Y-%m-%d").date(),
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
        coupon.amount = int(data["amount"])
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

    for platform in PLATFORMS:
        result = (
            db.session.query(
                db.func.sum(
                    db.case((Coupon.is_used == False, Coupon.amount), else_=0)
                ).label("unused_total"),
                db.func.sum(
                    db.case((Coupon.is_used == True, Coupon.amount), else_=0)
                ).label("used_total"),
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
