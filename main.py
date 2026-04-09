"""
澳門消費券記錄系統 - Macau Consumption Voucher Record System
Flask 後端應用程式
"""

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import secrets

app = Flask(__name__)

# 生產環境配置
if os.environ.get('FLASK_ENV') == 'production':
    # PythonAnywhere 配置
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///coupons.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
else:
    # 本地開發配置
    app.config['SECRET_KEY'] = secrets.token_hex(16)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///coupons.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 支付平臺清單
PLATFORMS = [
    "工商銀行",
    "國際銀行",
    "支付寶",
    "大豐銀行",
    "UEpay",
    "廣發銀行",
    "Mpay",
    "中國銀行"
]

# 平臺 Deep Link（iOS App 連結）
PLATFORM_LINKS = {
    "MPay": "mpay://",
    "支付寶": "alipay://"
}

# 券面額選項
COUPON_AMOUNTS = [0, 10, 20, 50, 100, 200]


class User(db.Model):
    """用戶資料表"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    form_collapsed = db.Column(db.Boolean, default=False)  # 表單折疊狀態
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    coupons = db.relationship('Coupon', backref='user', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'form_collapsed': self.form_collapsed,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Coupon(db.Model):
    """優惠券資料表"""
    __tablename__ = 'coupons'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)  # 支付平臺
    amount = db.Column(db.Integer, nullable=False)      # 券面額
    draw_date = db.Column(db.Date, nullable=False)       # 抽獎日期
    is_used = db.Column(db.Boolean, default=False)      # 是否已使用
    used_date = db.Column(db.Date, nullable=True)        # 使用日期
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'platform': self.platform,
            'amount': self.amount,
            'draw_date': self.draw_date.isoformat() if self.draw_date else None,
            'is_used': self.is_used,
            'used_date': self.used_date.isoformat() if self.used_date else None,
            'minimum_spend': self.amount * 3,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


def init_db():
    """初始化數據庫並處理遷移"""
    with app.app_context():
        # 創建所有表
        db.create_all()
        
        # 檢查並添加缺失的欄位（遷移處理）
        try:
            # 檢查 users 表是否有 form_collapsed 欄位
            result = db.session.execute(db.text("PRAGMA table_info(users)")).fetchall()
            columns = [r[1] for r in result]
            
            if 'form_collapsed' not in columns:
                # 添加 form_collapsed 欄位
                db.session.execute(db.text("ALTER TABLE users ADD COLUMN form_collapsed BOOLEAN DEFAULT 0"))
                db.session.commit()
        except Exception as e:
            print(f"Migration error: {e}")
            db.session.rollback()


# 初始化數據庫
init_db()


@app.route('/')
def index():
    """首頁"""
    user_name = session.get('user_name')
    return render_template('index.html', platforms=PLATFORMS, coupon_amounts=COUPON_AMOUNTS,
                           platform_links=PLATFORM_LINKS, user_name=user_name)


@app.route('/login', methods=['POST'])
def login():
    """用戶登入"""
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': '請輸入姓名'}), 400
    
    # 查找或創建用戶
    user = User.query.filter_by(name=name).first()
    if not user:
        user = User(name=name)
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    session['user_name'] = user.name
    
    return jsonify(user.to_dict())


@app.route('/logout', methods=['POST'])
def logout():
    """用戶登出"""
    session.clear()
    return jsonify({'message': '已登出'})


@app.route('/api/current-user')
def get_current_user():
    """獲取當前登入用戶"""
    user_name = session.get('user_name')
    user_id = session.get('user_id')
    if user_name:
        return jsonify({'id': user_id, 'name': user_name})
    return jsonify(None)


@app.route('/api/user-settings', methods=['GET'])
def get_user_settings():
    """獲取用戶設置"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用戶不存在'}), 404
    
    return jsonify({
        'form_collapsed': user.form_collapsed if user.form_collapsed else False
    })


@app.route('/api/user-settings', methods=['POST'])
def update_user_settings():
    """更新用戶設置"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用戶不存在'}), 404
    
    data = request.get_json()
    
    try:
        if 'form_collapsed' in data:
            user.form_collapsed = data['form_collapsed']
        db.session.commit()
        return jsonify({'message': '設置已保存'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


def get_user_id():
    """獲取當前用戶ID，如果未登入則返回None"""
    return session.get('user_id')


@app.route('/api/coupons', methods=['GET'])
def get_coupons():
    """獲取所有優惠券"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    coupons = Coupon.query.filter_by(user_id=user_id).order_by(Coupon.draw_date.desc()).all()
    return jsonify([c.to_dict() for c in coupons])


@app.route('/api/coupons', methods=['POST'])
def create_coupon():
    """新增優惠券（支援一次新增多達3條）"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    data = request.get_json()
    coupons_data = data.get('coupons', [])
    
    if not coupons_data or len(coupons_data) > 3:
        return jsonify({'error': '一次最多新增3條記錄'}), 400
    
    created = []
    try:
        for item in coupons_data:
            coupon = Coupon(
                user_id=user_id,
                platform=item['platform'],
                amount=int(item['amount']),
                draw_date=datetime.strptime(item['draw_date'], '%Y-%m-%d').date()
            )
            db.session.add(coupon)
            created.append(coupon)
        db.session.commit()
        return jsonify([c.to_dict() for c in created]), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/coupons/<int:id>', methods=['PUT'])
def update_coupon(id):
    """更新優惠券"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    coupon = Coupon.query.filter_by(id=id, user_id=user_id).first_or_404()
    data = request.get_json()
    
    try:
        if 'platform' in data:
            coupon.platform = data['platform']
        if 'amount' in data:
            coupon.amount = int(data['amount'])
        if 'draw_date' in data:
            coupon.draw_date = datetime.strptime(data['draw_date'], '%Y-%m-%d').date()
        if 'is_used' in data:
            coupon.is_used = data['is_used']
            if data['is_used']:
                coupon.used_date = date.today()
            else:
                coupon.used_date = None
        db.session.commit()
        return jsonify(coupon.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/coupons/<int:id>', methods=['DELETE'])
def delete_coupon(id):
    """刪除優惠券"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    coupon = Coupon.query.filter_by(id=id, user_id=user_id).first_or_404()
    db.session.delete(coupon)
    db.session.commit()
    return jsonify({'message': 'Deleted successfully'})


@app.route('/api/coupons/clear-all', methods=['POST'])
def clear_all_coupons():
    """刪除用戶所有優惠券"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    try:
        Coupon.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({'message': 'All coupons deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """獲取各平臺統計摘要"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': '請先登入'}), 401
    
    summary = []
    total_unused = 0
    
    for platform in PLATFORMS:
        # 獲取該平臺未使用的券
        coupons = Coupon.query.filter_by(user_id=user_id, platform=platform, is_used=False).all()
        total_coupon = sum(c.amount for c in coupons)
        
        # 計算已使用和未使用的券數量
        used_count = Coupon.query.filter_by(user_id=user_id, platform=platform, is_used=True).count()
        unused_count = len(coupons)
        
        # 計算該平臺所有券的總額
        all_coupons = Coupon.query.filter_by(user_id=user_id, platform=platform).all()
        platform_total = sum(c.amount for c in all_coupons)
        
        total_unused += total_coupon
        
        summary.append({
            'platform': platform,
            'total_coupon': total_coupon,
            'platform_total': platform_total,
            'used_count': used_count,
            'unused_count': unused_count,
            'total_count': used_count + unused_count
        })
    
    return jsonify({
        'platforms': summary,
        'total_unused': total_unused
    })


# 僅在本地運行時使用
if __name__ == '__main__':
    app.run(debug=True, port=5000)
