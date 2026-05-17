# -*- coding: utf-8 -*-
"""
自动售货机管理系统 — Web 界面
启动方式：python app.py
默认地址：http://localhost:5000
"""
import sys
import os
from functools import wraps

# --- 依赖检查 ---
try:
    from flask import Flask, render_template, request, jsonify, session
except ImportError:
    print("请先安装 Flask：pip install flask")
    sys.exit(1)

from vending_system import (
    Database, UserDAO, ProductDAO, MachineDAO,
    InventoryDAO, OrderDAO, StatisticsDAO,
    OperationLogDAO, WishlistDAO, hash_password
)

# --- Flask 应用 ---
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# --- 数据库初始化 ---
db = Database()
import io
import contextlib
with contextlib.redirect_stdout(io.StringIO()):
    db.init_all()

# --- DAO 实例 ---
user_dao = UserDAO(db)
product_dao = ProductDAO(db)
machine_dao = MachineDAO(db)
inventory_dao = InventoryDAO(db)
order_dao = OrderDAO(db)
stats_dao = StatisticsDAO(db)
log_dao = OperationLogDAO(db)
wishlist_dao = WishlistDAO(db)


# ============================================================
# 装饰器：登录验证
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify(ok=False, message="请先登录"), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify(ok=False, message="请先登录"), 401
        if session.get('role') != 'admin':
            return jsonify(ok=False, message="需要管理员权限"), 403
        return f(*args, **kwargs)
    return decorated


# ============================================================
# 页面入口
# ============================================================
@app.route('/')
def index():
    return render_template('index.html')


# ============================================================
# 认证 API
# ============================================================
@app.route('/api/session', methods=['GET'])
def api_session():
    if 'user_id' in session:
        user = user_dao.get_by_id(session['user_id'])
        if user:
            return jsonify(ok=True, data={
                'user_id': user['user_id'],
                'username': user['username'],
                'role': user['role'],
                'balance': float(user['balance']),
                'phone': user.get('phone'),
                'email': user.get('email')
            })
        session.clear()
    return jsonify(ok=True, data=None)


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify(ok=False, message="用户名和密码不能为空")
    user, msg = user_dao.login(username, password)
    if user is None:
        return jsonify(ok=False, message=msg)
    session['user_id'] = user['user_id']
    session['username'] = user['username']
    session['role'] = user['role']
    return jsonify(ok=True, data={
        'user_id': user['user_id'],
        'username': user['username'],
        'role': user['role'],
        'balance': float(user['balance'])
    })


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify(ok=False, message="用户名和密码不能为空")
    if len(password) < 4:
        return jsonify(ok=False, message="密码至少4位")
    phone = data.get('phone', '').strip() or None
    email = data.get('email', '').strip() or None
    ok, msg = user_dao.register(username, password, phone, email)
    return jsonify(ok=ok, message=msg)


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify(ok=True, message="已退出登录")


# ============================================================
# 用户 API
# ============================================================
@app.route('/api/user/profile', methods=['GET'])
@login_required
def api_profile():
    user = user_dao.get_by_id(session['user_id'])
    if not user:
        session.clear()
        return jsonify(ok=False, message="用户不存在")
    return jsonify(ok=True, data={
        'user_id': user['user_id'],
        'username': user['username'],
        'role': user['role'],
        'balance': float(user['balance']),
        'phone': user.get('phone'),
        'email': user.get('email'),
        'created_at': str(user['created_at'])
    })


@app.route('/api/user/recharge', methods=['POST'])
@login_required
def api_recharge():
    data = request.get_json()
    amount = data.get('amount', 0)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify(ok=False, message="请输入有效金额")
    ok, msg = user_dao.recharge(session['user_id'], amount)
    user = user_dao.get_by_id(session['user_id'])
    return jsonify(ok=ok, message=msg, balance=float(user['balance']) if user else 0)


@app.route('/api/user/password', methods=['PUT'])
@login_required
def api_change_password():
    data = request.get_json()
    old_pwd = data.get('old_password', '')
    new_pwd = data.get('new_password', '')
    if not new_pwd:
        return jsonify(ok=False, message="新密码不能为空")
    if len(new_pwd) < 4:
        return jsonify(ok=False, message="新密码至少4位")

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password FROM users WHERE user_id = %s",
                        (session['user_id'],))
            old_hash = cur.fetchone()[0]
            if old_hash != hash_password(old_pwd):
                return jsonify(ok=False, message="当前密码错误")
            cur.execute("UPDATE users SET password = %s WHERE user_id = %s",
                        (hash_password(new_pwd), session['user_id']))
        conn.commit()
        return jsonify(ok=True, message="密码修改成功")
    finally:
        conn.close()


# ============================================================
# 售货机 & 商品浏览 API
# ============================================================
@app.route('/api/machines', methods=['GET'])
@login_required
def api_machines():
    machines = machine_dao.list_online()
    return jsonify(ok=True, data=[
        {
            'machine_id': m['machine_id'],
            'name': m['name'],
            'location': m['location'],
            'status': m['status']
        } for m in machines
    ])


@app.route('/api/machines/<int:machine_id>/products', methods=['GET'])
@login_required
def api_machine_products(machine_id):
    items = inventory_dao.get_by_machine(machine_id)
    return jsonify(ok=True, data=[
        {
            'product_id': it['product_id'],
            'product_name': it['product_name'],
            'price': float(it['price']),
            'quantity': it['quantity']
        } for it in items
    ])


# ============================================================
# 订单 API
# ============================================================
@app.route('/api/orders', methods=['POST'])
@login_required
def api_create_order():
    data = request.get_json()
    machine_id = data.get('machine_id')
    items = data.get('items', [])  # [{product_id, quantity}, ...]
    if not items:
        return jsonify(ok=False, message="购买清单不能为空")
    cart = [(it['product_id'], it['quantity']) for it in items]
    try:
        ok, msg = order_dao.create_order(session['user_id'], machine_id, cart)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify(ok=False, message=f"服务器内部错误：{e}")
    user = user_dao.get_by_id(session['user_id'])
    balance = float(user['balance']) if user else 0
    resp = {'ok': ok, 'message': msg, 'balance': balance}
    if not ok and '余额不足' in msg:
        resp['error_code'] = 'insufficient_balance'
    return jsonify(resp)


@app.route('/api/orders/my', methods=['GET'])
@login_required
def api_my_orders():
    orders = order_dao.get_by_user(session['user_id'])
    return jsonify(ok=True, data=[
        {
            'order_id': o['order_id'],
            'machine_name': o['machine_name'],
            'total_amount': float(o['total_amount']),
            'status': o['status'],
            'created_at': str(o['created_at'])
        } for o in orders
    ])


@app.route('/api/orders/<int:order_id>', methods=['GET'])
@login_required
def api_order_detail(order_id):
    order, details = order_dao.get_detail(order_id)
    if not order:
        return jsonify(ok=False, message="订单不存在")
    return jsonify(ok=True, data={
        'order': {
            'order_id': order['order_id'],
            'username': order['username'],
            'machine_name': order['machine_name'],
            'total_amount': float(order['total_amount']),
            'status': order['status'],
            'created_at': str(order['created_at'])
        },
        'details': [
            {
                'product_name': d['product_name'],
                'quantity': d['quantity'],
                'unit_price': float(d['unit_price'])
            } for d in details
        ]
    })


# ============================================================
# 心愿单 API
# ============================================================
@app.route('/api/wishlist', methods=['POST'])
@login_required
def api_add_wish():
    data = request.get_json()
    product_name = data.get('product_name', '').strip()
    category = data.get('category', '').strip() or None
    description = data.get('description', '').strip() or None
    ok, msg = wishlist_dao.add(session['user_id'], product_name, category, description)
    return jsonify(ok=ok, message=msg)


@app.route('/api/wishlist/my', methods=['GET'])
@login_required
def api_my_wishes():
    wishes = wishlist_dao.get_by_user(session['user_id'])
    status_map = {'pending': '待审核', 'approved': '已采纳', 'rejected': '已拒绝'}
    return jsonify(ok=True, data=[
        {
            'wish_id': w['wish_id'],
            'product_name': w['product_name'],
            'category': w['category'],
            'description': w['description'],
            'status': w['status'],
            'status_text': status_map.get(w['status'], w['status']),
            'admin_note': w['admin_note'],
            'created_at': str(w['created_at'])
        } for w in wishes
    ])


@app.route('/api/admin/wishlist', methods=['GET'])
@admin_required
def api_admin_wishes():
    wishes = wishlist_dao.list_all()
    status_map = {'pending': '待审核', 'approved': '已采纳', 'rejected': '已拒绝'}
    return jsonify(ok=True, data=[
        {
            'wish_id': w['wish_id'],
            'username': w['username'],
            'product_name': w['product_name'],
            'category': w['category'],
            'description': w['description'],
            'status': w['status'],
            'status_text': status_map.get(w['status'], w['status']),
            'admin_note': w['admin_note'],
            'created_at': str(w['created_at'])
        } for w in wishes
    ])


@app.route('/api/admin/wishlist/<int:wish_id>', methods=['PUT'])
@admin_required
def api_admin_update_wish(wish_id):
    data = request.get_json()
    status = data.get('status', '').strip()
    admin_note = data.get('admin_note', '').strip() or None
    ok, msg = wishlist_dao.update_status(wish_id, status, admin_note)
    if ok:
        log_dao.record(session['user_id'], '处理心愿', f'wish_id={wish_id}', msg)
    return jsonify(ok=ok, message=msg)


# ============================================================
# 管理员 — 商品管理 API
# ============================================================
@app.route('/api/admin/products', methods=['GET'])
@admin_required
def api_admin_products():
    products = product_dao.list_all()
    return jsonify(ok=True, data=[
        {
            'product_id': p['product_id'],
            'name': p['name'],
            'category': p['category'],
            'description': p['description'],
            'price': float(p['price'])
        } for p in products
    ])


@app.route('/api/admin/products', methods=['POST'])
@admin_required
def api_admin_add_product():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify(ok=False, message="商品名称不能为空")
    category = data.get('category', '').strip()
    description = data.get('description', '').strip()
    try:
        price = float(data.get('price', 0))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="请输入有效单价")
    ok, msg = product_dao.add(name, category, description, price)
    if ok:
        log_dao.record(session['user_id'], '添加商品', name, msg)
    return jsonify(ok=ok, message=msg)


@app.route('/api/admin/products/<int:product_id>', methods=['PUT'])
@admin_required
def api_admin_update_product(product_id):
    data = request.get_json()
    name = data.get('name', '').strip()
    category = data.get('category', '').strip()
    description = data.get('description', '').strip()
    try:
        price = float(data.get('price', 0))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="请输入有效单价")
    if not name:
        return jsonify(ok=False, message="商品名称不能为空")
    ok, msg = product_dao.update(product_id, name, category, description, price)
    if ok:
        log_dao.record(session['user_id'], '修改商品', f'product_id={product_id}', msg)
    return jsonify(ok=ok, message=msg)


@app.route('/api/admin/products/<int:product_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_product(product_id):
    ok, msg = product_dao.delete(product_id)
    if ok:
        log_dao.record(session['user_id'], '删除商品', f'product_id={product_id}', msg)
    return jsonify(ok=ok, message=msg)


# ============================================================
# 管理员 — 售货机管理 API
# ============================================================
@app.route('/api/admin/machines', methods=['GET'])
@admin_required
def api_admin_machines():
    machines = machine_dao.list_all()
    return jsonify(ok=True, data=[
        {
            'machine_id': m['machine_id'],
            'name': m['name'],
            'location': m['location'],
            'status': m['status'],
            'capacity': m['capacity']
        } for m in machines
    ])


@app.route('/api/admin/machines', methods=['POST'])
@admin_required
def api_admin_add_machine():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify(ok=False, message="售货机名称不能为空")
    location = data.get('location', '').strip()
    capacity = data.get('capacity', 100)
    ok, msg = machine_dao.add(name, location, capacity)
    if ok:
        log_dao.record(session['user_id'], '添加售货机', name, msg)
    return jsonify(ok=ok, message=msg)


@app.route('/api/admin/machines/<int:machine_id>/status', methods=['PUT'])
@admin_required
def api_admin_update_machine_status(machine_id):
    data = request.get_json()
    status = data.get('status', '').strip()
    ok, msg = machine_dao.update_status(machine_id, status)
    if ok:
        log_dao.record(session['user_id'], '修改售货机状态',
                       f'machine_id={machine_id}', msg)
    return jsonify(ok=ok, message=msg)


# ============================================================
# 管理员 — 库存管理 API
# ============================================================
@app.route('/api/admin/inventory', methods=['GET'])
@admin_required
def api_admin_inventory():
    machine_id = request.args.get('machine_id')
    if machine_id:
        items = inventory_dao.get_by_machine(int(machine_id))
    else:
        items = []
    return jsonify(ok=True, data=[
        {
            'inventory_id': it.get('inventory_id'),
            'machine_id': it['machine_id'],
            'product_id': it['product_id'],
            'product_name': it['product_name'],
            'price': float(it['price']),
            'quantity': it['quantity'],
            'max_quantity': it['max_quantity'],
            'warning_threshold': it.get('warning_threshold', 10)
        } for it in items
    ])


@app.route('/api/admin/inventory/stock', methods=['PUT'])
@admin_required
def api_admin_update_stock():
    data = request.get_json()
    machine_id = data.get('machine_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 0)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify(ok=False, message="请输入有效数量")
    ok, msg = inventory_dao.update_stock(machine_id, product_id, quantity)
    if ok:
        log_dao.record(session['user_id'], '更新库存',
                       f'machine={machine_id},product={product_id}', msg)
    return jsonify(ok=ok, message=msg)


@app.route('/api/admin/inventory/restock', methods=['POST'])
@admin_required
def api_admin_restock():
    data = request.get_json()
    machine_id = data.get('machine_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 0)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify(ok=False, message="请输入有效数量")
    if quantity <= 0:
        return jsonify(ok=False, message="数量必须大于0")
    ok, msg = inventory_dao.add_or_update(machine_id, product_id, quantity)
    if ok:
        log_dao.record(session['user_id'], '补货',
                       f'machine={machine_id},product={product_id}', msg)
    return jsonify(ok=ok, message=msg)


@app.route('/api/admin/inventory/threshold', methods=['PUT'])
@admin_required
def api_admin_update_threshold():
    data = request.get_json()
    machine_id = data.get('machine_id')
    product_id = data.get('product_id')
    threshold = data.get('threshold', 10)
    ok, msg = inventory_dao.set_warning_threshold(machine_id, product_id, threshold)
    if ok:
        log_dao.record(session['user_id'], '设置预警阈值',
                       f'machine={machine_id},product={product_id}', msg)
    return jsonify(ok=ok, message=msg)


# ============================================================
# 管理员 — 统计数据 API
# ============================================================
@app.route('/api/admin/stats/products', methods=['GET'])
@admin_required
def api_admin_stats_products():
    start = request.args.get('start')
    end = request.args.get('end')
    rows = stats_dao.sales_by_product(start, end)
    return jsonify(ok=True, data=[
        {
            'product_id': r['product_id'],
            'product_name': r['product_name'],
            'total_quantity': int(r['total_quantity'] or 0),
            'total_revenue': float(r['total_revenue'] or 0)
        } for r in rows
    ])


@app.route('/api/admin/stats/time', methods=['GET'])
@admin_required
def api_admin_stats_time():
    start = request.args.get('start')
    end = request.args.get('end')
    rows = stats_dao.sales_by_time(start, end)
    return jsonify(ok=True, data=[
        {
            'stat_date': str(r['stat_date']),
            'total_quantity': int(r['total_quantity'] or 0),
            'total_revenue': float(r['total_revenue'] or 0)
        } for r in rows
    ])


# ============================================================
# 管理员 — 日志 & 用户 & 订单 API
# ============================================================
@app.route('/api/admin/logs', methods=['GET'])
@admin_required
def api_admin_logs():
    logs = log_dao.list_recent(50)
    return jsonify(ok=True, data=[
        {
            'log_id': l['log_id'],
            'username': l['username'],
            'action': l['action'],
            'target': l['target'],
            'details': l['details'],
            'created_at': str(l['created_at'])
        } for l in logs
    ])


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_admin_users():
    users = user_dao.list_all()
    return jsonify(ok=True, data=[
        {
            'user_id': u['user_id'],
            'username': u['username'],
            'role': u['role'],
            'balance': float(u['balance']),
            'phone': u.get('phone'),
            'email': u.get('email'),
            'created_at': str(u['created_at'])
        } for u in users
    ])


@app.route('/api/admin/orders', methods=['GET'])
@admin_required
def api_admin_all_orders():
    orders = order_dao.list_all()
    return jsonify(ok=True, data=[
        {
            'order_id': o['order_id'],
            'username': o['username'],
            'machine_name': o['machine_name'],
            'total_amount': float(o['total_amount']),
            'status': o['status'],
            'created_at': str(o['created_at'])
        } for o in orders
    ])


@app.route('/api/admin/low-stock', methods=['GET'])
@admin_required
def api_admin_low_stock():
    items = inventory_dao.list_low_stock()
    return jsonify(ok=True, data=[
        {
            'machine_id': it['machine_id'],
            'machine_name': it['machine_name'],
            'product_id': it['product_id'],
            'product_name': it['product_name'],
            'quantity': it['quantity'],
            'warning_threshold': it['warning_threshold']
        } for it in items
    ])


# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    print("\n" + "=" * 52)
    print("  自动售货机管理系统 — Web 界面")
    print("  访问地址：http://localhost:5000")
    print("  默认管理员：admin / admin123")
    print("  默认用户：test / test123")
    print("=" * 52 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
