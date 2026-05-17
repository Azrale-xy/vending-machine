# -*- coding: utf-8 -*-
"""
自动售货机管理系统 — 数据库课程大作业
技术栈：Python 3.x + MySQL (pymysql)
使用方法：
  1. 安装依赖：pip install pymysql
  2. 修改下方 DB_CONFIG 中的 host、user、password
  3. 确保 MySQL 服务已启动
  4. 运行：python vending_system.py
"""

import hashlib
import sys
from datetime import datetime
from getpass import getpass

# ============================================================
# 数据库配置 — 请根据你的环境修改以下参数
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",        # ← 改成你的 MySQL 用户名
    "password": "123456",  # ← 改成你的 MySQL 密码
    "charset": "utf8mb4",
    "cursorclass": None,   # 使用默认 cursor
}

DATABASE_NAME = "vending_machine_db"

# ============================================================
# 数据库连接管理
# ============================================================
try:
    import pymysql
except ImportError:
    print("错误：未安装 pymysql 模块，请执行：pip install pymysql")
    sys.exit(1)


class Database:
    """数据库连接管理类，负责连接获取与数据库/表的自动初始化"""

    # ---------- 连接与数据库级操作 ----------
    def get_raw_connection(self):
        """获取不指定数据库的裸连接（用于创建数据库）"""
        return pymysql.connect(**DB_CONFIG)

    def get_connection(self):
        """获取已指定数据库的连接，每次调用返回新连接（调用方负责关闭）"""
        cfg = DB_CONFIG.copy()
        cfg["database"] = DATABASE_NAME
        return pymysql.connect(**cfg)

    def create_database(self):
        """创建数据库（如已存在则跳过）"""
        conn = self.get_raw_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            conn.commit()
            print(f"[OK] 数据库 '{DATABASE_NAME}' 已就绪")
        finally:
            conn.close()

    # ---------- 表结构初始化 ----------
    def create_tables(self):
        """执行 DDL，创建全部6张表（如已存在则跳过）"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # ---- 1. 用户表 ----
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id     INT AUTO_INCREMENT PRIMARY KEY
                            COMMENT '用户唯一ID',
                        username    VARCHAR(50)  NOT NULL UNIQUE
                            COMMENT '登录用户名',
                        password    VARCHAR(255) NOT NULL
                            COMMENT 'SHA256哈希后的密码',
                        role        ENUM('user','admin') NOT NULL DEFAULT 'user'
                            COMMENT '角色：user-普通用户 / admin-管理员',
                        balance     DECIMAL(10,2) NOT NULL DEFAULT 0.00
                            COMMENT '账户余额（元）',
                        phone       VARCHAR(20)  DEFAULT NULL
                            COMMENT '手机号码',
                        email       VARCHAR(100) DEFAULT NULL
                            COMMENT '电子邮箱',
                        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            COMMENT '注册时间'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                       COMMENT='用户表'
                """)

                # ---- 2. 售货机表 ----
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vending_machines (
                        machine_id  INT AUTO_INCREMENT PRIMARY KEY
                            COMMENT '售货机唯一ID',
                        name        VARCHAR(100) NOT NULL
                            COMMENT '售货机名称',
                        location    VARCHAR(255) DEFAULT NULL
                            COMMENT '摆放位置',
                        status      ENUM('online','offline','maintenance')
                            NOT NULL DEFAULT 'online'
                            COMMENT '状态：online-在线 / offline-离线 / maintenance-维护中',
                        capacity    INT NOT NULL DEFAULT 100
                            COMMENT '最大货道容量（件）',
                        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            COMMENT '创建时间'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                       COMMENT='售货机表'
                """)

                # ---- 3. 商品表 ----
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        product_id  INT AUTO_INCREMENT PRIMARY KEY
                            COMMENT '商品唯一ID',
                        name        VARCHAR(100) NOT NULL
                            COMMENT '商品名称',
                        category    VARCHAR(50)  DEFAULT NULL
                            COMMENT '商品分类',
                        description TEXT          DEFAULT NULL
                            COMMENT '商品描述',
                        price       DECIMAL(10,2) NOT NULL
                            COMMENT '商品单价（元）',
                        image_url   VARCHAR(255) DEFAULT NULL
                            COMMENT '商品图片URL',
                        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            COMMENT '创建时间'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                       COMMENT='商品表'
                """)

                # ---- 4. 库存表（售货机 ↔ 商品 的多对多关系） ----
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS inventory (
                        inventory_id INT AUTO_INCREMENT PRIMARY KEY
                            COMMENT '库存记录ID',
                        machine_id   INT NOT NULL
                            COMMENT '售货机ID（外键）',
                        product_id   INT NOT NULL
                            COMMENT '商品ID（外键）',
                        quantity     INT NOT NULL DEFAULT 0
                            COMMENT '当前库存数量',
                        max_quantity INT NOT NULL DEFAULT 50
                            COMMENT '该货道最大容量',
                        FOREIGN KEY (machine_id)
                            REFERENCES vending_machines(machine_id)
                            ON DELETE CASCADE,
                        FOREIGN KEY (product_id)
                            REFERENCES products(product_id)
                            ON DELETE CASCADE,
                        UNIQUE KEY uk_machine_product (machine_id, product_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                       COMMENT='库存表（售货机与商品的多对多关系）'
                """)

                # ---- 5. 订单表 ----
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id     INT AUTO_INCREMENT PRIMARY KEY
                            COMMENT '订单唯一ID',
                        user_id      INT NOT NULL
                            COMMENT '下单用户ID（外键）',
                        machine_id   INT NOT NULL
                            COMMENT '售货机ID（外键）',
                        total_amount DECIMAL(10,2) NOT NULL
                            COMMENT '订单总金额（元）',
                        status       ENUM('pending','completed','cancelled')
                            NOT NULL DEFAULT 'pending'
                            COMMENT '订单状态',
                        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            COMMENT '下单时间',
                        FOREIGN KEY (user_id)
                            REFERENCES users(user_id),
                        FOREIGN KEY (machine_id)
                            REFERENCES vending_machines(machine_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                       COMMENT='订单表'
                """)

                # ---- 6. 订单明细表 ----
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS order_details (
                        detail_id  INT AUTO_INCREMENT PRIMARY KEY
                            COMMENT '明细唯一ID',
                        order_id   INT NOT NULL
                            COMMENT '订单ID（外键）',
                        product_id INT NOT NULL
                            COMMENT '商品ID（外键）',
                        quantity   INT NOT NULL
                            COMMENT '购买数量',
                        unit_price DECIMAL(10,2) NOT NULL
                            COMMENT '购买时单价（元）',
                        FOREIGN KEY (order_id)
                            REFERENCES orders(order_id)
                            ON DELETE CASCADE,
                        FOREIGN KEY (product_id)
                            REFERENCES products(product_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                       COMMENT='订单明细表'
                """)
            conn.commit()
            print("[OK] 全部6张数据表已就绪")
        finally:
            conn.close()

    # ---------- 初始化入口 ----------
    def init_all(self):
        """初始化数据库 + 表结构 + 默认数据"""
        self.create_database()
        self.create_tables()
        self._seed_default_data()

    def _seed_default_data(self):
        """插入默认管理员和示例数据（幂等操作）"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # 默认管理员：admin / admin123
                admin_pwd = hashlib.sha256("admin123".encode()).hexdigest()
                cur.execute(
                    "INSERT IGNORE INTO users (username, password, role, balance) "
                    "VALUES (%s, %s, 'admin', 0.00)",
                    ("admin", admin_pwd),
                )

                # 默认普通测试用户：test / test123
                user_pwd = hashlib.sha256("test123".encode()).hexdigest()
                cur.execute(
                    "INSERT IGNORE INTO users (username, password, role, balance) "
                    "VALUES (%s, %s, 'user', 100.00)",
                    ("test", user_pwd),
                )

                # 示例售货机
                cur.execute(
                    "INSERT IGNORE INTO vending_machines (machine_id, name, location) "
                    "VALUES (1, '教学楼A座售货机', '教学楼A座一楼大厅')"
                )
                cur.execute(
                    "INSERT IGNORE INTO vending_machines (machine_id, name, location) "
                    "VALUES (2, '图书馆售货机', '图书馆二楼走廊')"
                )

                # 示例商品
                sample_products = [
                    (1, "可口可乐", "饮料", "330ml罐装", 3.50),
                    (2, "农夫山泉", "饮料", "550ml瓶装", 2.00),
                    (3, "奥利奥饼干", "零食", "原味97g", 6.50),
                    (4, "乐事薯片", "零食", "原味75g", 7.00),
                    (5, "康师傅方便面", "食品", "红烧牛肉面105g", 4.50),
                ]
                for pid, name, cat, desc, price in sample_products:
                    cur.execute(
                        "INSERT IGNORE INTO products "
                        "(product_id, name, category, description, price) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (pid, name, cat, desc, price),
                    )

                # 示例库存：售货机1包含全部5种商品，售货机2包含前3种
                for pid in range(1, 6):
                    cur.execute(
                        "INSERT IGNORE INTO inventory "
                        "(machine_id, product_id, quantity, max_quantity) "
                        "VALUES (1, %s, 30, 50)", (pid,)
                    )
                for pid in range(1, 4):
                    cur.execute(
                        "INSERT IGNORE INTO inventory "
                        "(machine_id, product_id, quantity, max_quantity) "
                        "VALUES (2, %s, 20, 50)", (pid,)
                    )
            conn.commit()
            print("[OK] 默认示例数据已就绪（管理员 admin/admin123，普通用户 test/test123）")
        finally:
            conn.close()


# ============================================================
# 辅助工具函数
# ============================================================
def hash_password(pwd: str) -> str:
    """SHA256 哈希密码"""
    return hashlib.sha256(pwd.encode()).hexdigest()


# ============================================================
# 用户数据访问层 (UserDAO)
# ============================================================
class UserDAO:
    """用户表数据操作"""

    def __init__(self, db: Database):
        self.db = db

    def register(self, username: str, password: str, phone: str = None,
                 email: str = None) -> tuple:
        """注册新用户，返回 (成功?, 消息)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # 检查用户名是否已存在
                cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    return False, f"用户名 '{username}' 已被占用"
                # 插入新用户
                cur.execute(
                    "INSERT INTO users (username, password, phone, email) "
                    "VALUES (%s, %s, %s, %s)",
                    (username, hash_password(password), phone, email),
                )
            conn.commit()
            return True, f"用户 '{username}' 注册成功"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def login(self, username: str, password: str) -> tuple:
        """用户登录验证，返回 (用户字典或None, 消息)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM users WHERE username = %s", (username,)
                )
                user = cur.fetchone()
                if not user:
                    return None, "用户不存在"
                if user["password"] != hash_password(password):
                    return None, "密码错误"
                return user, "登录成功"
        except pymysql.Error as e:
            return None, f"数据库错误：{e}"
        finally:
            conn.close()

    def get_by_id(self, user_id: int) -> dict:
        """根据 ID 查询用户"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                return cur.fetchone()
        finally:
            conn.close()

    def recharge(self, user_id: int, amount: float) -> tuple:
        """给用户充值，返回 (成功?, 消息)"""
        if amount <= 0:
            return False, "充值金额必须大于0"
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET balance = balance + %s WHERE user_id = %s",
                    (amount, user_id),
                )
                if cur.rowcount == 0:
                    return False, "用户不存在"
            conn.commit()
            return True, f"充值成功，金额：¥{amount:.2f}"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def list_all(self) -> list:
        """查询全部用户列表"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT user_id, username, role, balance, phone, email, created_at "
                    "FROM users ORDER BY user_id"
                )
                return cur.fetchall()
        finally:
            conn.close()


# ============================================================
# 商品数据访问层 (ProductDAO)
# ============================================================
class ProductDAO:
    """商品表数据操作"""

    def __init__(self, db: Database):
        self.db = db

    def add(self, name: str, category: str, description: str, price: float) -> tuple:
        """添加商品，返回 (成功?, 消息)"""
        if price <= 0:
            return False, "商品单价必须大于0"
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO products (name, category, description, price) "
                    "VALUES (%s, %s, %s, %s)",
                    (name, category, description, price),
                )
            conn.commit()
            return True, f"商品 '{name}' 添加成功"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def update(self, product_id: int, name: str, category: str,
               description: str, price: float) -> tuple:
        """更新商品信息，返回 (成功?, 消息)"""
        if price <= 0:
            return False, "商品单价必须大于0"
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE products SET name=%s, category=%s, description=%s, "
                    "price=%s WHERE product_id=%s",
                    (name, category, description, price, product_id),
                )
                if cur.rowcount == 0:
                    return False, "商品不存在"
            conn.commit()
            return True, "商品信息更新成功"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def delete(self, product_id: int) -> tuple:
        """删除商品，返回 (成功?, 消息)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # 先检查是否有关联库存
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM inventory WHERE product_id = %s",
                    (product_id,),
                )
                if cur.fetchone()[0] > 0:
                    return False, "该商品关联了库存记录，请先清除对应库存后再删除"
                cur.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
                if cur.rowcount == 0:
                    return False, "商品不存在"
            conn.commit()
            return True, "商品删除成功"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def list_all(self) -> list:
        """查询全部商品"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute("SELECT * FROM products ORDER BY product_id")
                return cur.fetchall()
        finally:
            conn.close()


# ============================================================
# 售货机数据访问层 (MachineDAO)
# ============================================================
class MachineDAO:
    """售货机表数据操作"""

    def __init__(self, db: Database):
        self.db = db

    def add(self, name: str, location: str, capacity: int = 100) -> tuple:
        """添加售货机"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vending_machines (name, location, capacity) "
                    "VALUES (%s, %s, %s)",
                    (name, location, capacity),
                )
            conn.commit()
            return True, f"售货机 '{name}' 添加成功"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def update_status(self, machine_id: int, status: str) -> tuple:
        """更新售货机状态"""
        if status not in ("online", "offline", "maintenance"):
            return False, "无效的状态值，可选：online / offline / maintenance"
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vending_machines SET status=%s WHERE machine_id=%s",
                    (status, machine_id),
                )
                if cur.rowcount == 0:
                    return False, "售货机不存在"
            conn.commit()
            return True, f"售货机 #{machine_id} 状态已更新为 '{status}'"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def list_all(self) -> list:
        """查询全部售货机"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute("SELECT * FROM vending_machines ORDER BY machine_id")
                return cur.fetchall()
        finally:
            conn.close()

    def list_online(self) -> list:
        """查询在线的售货机"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM vending_machines WHERE status='online' "
                    "ORDER BY machine_id"
                )
                return cur.fetchall()
        finally:
            conn.close()


# ============================================================
# 库存数据访问层 (InventoryDAO)
# ============================================================
class InventoryDAO:
    """库存表数据操作"""

    def __init__(self, db: Database):
        self.db = db

    def add_or_update(self, machine_id: int, product_id: int,
                      quantity: int, max_quantity: int = 50) -> tuple:
        """向售货机添加商品库存（如已存在则更新数量），返回 (成功?, 消息)"""
        if quantity < 0 or max_quantity <= 0:
            return False, "库存数量不能为负数，最大容量必须大于0"
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO inventory (machine_id, product_id, quantity, max_quantity) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE quantity = quantity + %s, max_quantity = %s",
                    (machine_id, product_id, quantity, max_quantity,
                     quantity, max_quantity),
                )
            conn.commit()
            return True, "库存更新成功"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def update_stock(self, machine_id: int, product_id: int,
                     quantity: int) -> tuple:
        """直接设置库存数量"""
        if quantity < 0:
            return False, "库存数量不能为负数"
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE inventory SET quantity = %s "
                    "WHERE machine_id = %s AND product_id = %s",
                    (quantity, machine_id, product_id),
                )
                if cur.rowcount == 0:
                    return False, "未找到该库存记录"
            conn.commit()
            return True, "库存更新成功"
        except pymysql.Error as e:
            return False, f"数据库错误：{e}"
        finally:
            conn.close()

    def get_by_machine(self, machine_id: int) -> list:
        """查询指定售货机的全部库存（JOIN 商品表显示名称和单价）"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT i.inventory_id, i.machine_id, i.product_id, "
                    "p.name AS product_name, p.price, i.quantity, i.max_quantity "
                    "FROM inventory i "
                    "JOIN products p ON i.product_id = p.product_id "
                    "WHERE i.machine_id = %s "
                    "ORDER BY i.product_id",
                    (machine_id,),
                )
                return cur.fetchall()
        finally:
            conn.close()

    def check_stock(self, machine_id: int, product_id: int,
                    needed: int) -> tuple:
        """检查某售货机中某商品的库存是否充足，返回 (充足?, 当前库存量)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT quantity FROM inventory "
                    "WHERE machine_id = %s AND product_id = %s",
                    (machine_id, product_id),
                )
                row = cur.fetchone()
                if not row:
                    return False, 0
                return row[0] >= needed, row[0]
        finally:
            conn.close()


# ============================================================
# 订单数据访问层 (OrderDAO) —— 核心：带事务保障的订单创建
# ============================================================
class OrderDAO:
    """
    订单数据操作。
    创建订单是系统的核心业务，必须在事务中完成以下步骤：
      1. 计算订单总金额（基于当前商品单价）
      2. 校验用户余额是否足够
      3. 逐项校验库存是否足够
      4. 扣减用户余额
      5. 扣减各商品库存
      6. 写入 orders 表
      7. 写入 order_details 表
    如果任一步骤失败，则回滚整个事务，保证数据一致性。
    """

    def __init__(self, db: Database):
        self.db = db

    def create_order(self, user_id: int, machine_id: int,
                     items: list) -> tuple:
        """
        创建订单（事务保障）。
        参数:
            user_id     - 下单用户ID
            machine_id  - 售货机ID
            items       - [(product_id, quantity), ...] 购买清单
        返回:
            (成功?, 订单ID或错误消息)
        """
        if not items:
            return False, "购买清单不能为空"

        conn = self.db.get_connection()
        try:
            # ---- 关闭自动提交，显式开启事务 ----
            conn.begin()

            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                # ---- 步骤1：获取用户余额 ----
                cur.execute(
                    "SELECT balance FROM users WHERE user_id = %s FOR UPDATE",
                    (user_id,),
                )
                user_row = cur.fetchone()
                if not user_row:
                    conn.rollback()
                    return False, "用户不存在"
                balance = user_row["balance"]

                # ---- 步骤2：计算总金额并校验库存 ----
                total = 0.0
                stock_checks = []  # 暂存库存扣减信息
                for product_id, qty in items:
                    if qty <= 0:
                        conn.rollback()
                        return False, "购买数量必须大于0"

                    # 获取商品单价
                    cur.execute(
                        "SELECT name, price FROM products WHERE product_id = %s",
                        (product_id,),
                    )
                    prod = cur.fetchone()
                    if not prod:
                        conn.rollback()
                        return False, f"商品 #{product_id} 不存在"

                    # 获取该售货机中该商品的库存（加行锁防止并发）
                    cur.execute(
                        "SELECT quantity FROM inventory "
                        "WHERE machine_id = %s AND product_id = %s FOR UPDATE",
                        (machine_id, product_id),
                    )
                    inv = cur.fetchone()
                    if not inv:
                        conn.rollback()
                        return False, f"售货机中不存在商品 '{prod['name']}'"
                    if inv["quantity"] < qty:
                        conn.rollback()
                        return False, (
                            f"商品 '{prod['name']}' 库存不足 "
                            f"(需要{qty}件，剩余{inv['quantity']}件)"
                        )

                    total += prod["price"] * qty
                    stock_checks.append((product_id, qty))

                # ---- 步骤3：校验余额 ----
                if balance < total:
                    conn.rollback()
                    return False, (
                        f"账户余额不足（需要 ¥{total:.2f}，"
                        f"当前余额 ¥{balance:.2f}）"
                    )

                # ---- 步骤4：扣减余额 ----
                cur.execute(
                    "UPDATE users SET balance = balance - %s WHERE user_id = %s",
                    (total, user_id),
                )

                # ---- 步骤5：逐项扣减库存 ----
                for product_id, qty in stock_checks:
                    cur.execute(
                        "UPDATE inventory SET quantity = quantity - %s "
                        "WHERE machine_id = %s AND product_id = %s",
                        (qty, machine_id, product_id),
                    )

                # ---- 步骤6：写入订单主表 ----
                cur.execute(
                    "INSERT INTO orders (user_id, machine_id, total_amount, status) "
                    "VALUES (%s, %s, %s, 'completed')",
                    (user_id, machine_id, total),
                )
                order_id = cur.lastrowid

                # ---- 步骤7：写入订单明细 ----
                for product_id, qty in stock_checks:
                    # 再次查询单价（快照到订单明细中）
                    cur.execute(
                        "SELECT price FROM products WHERE product_id = %s",
                        (product_id,),
                    )
                    unit_price = cur.fetchone()["price"]
                    cur.execute(
                        "INSERT INTO order_details "
                        "(order_id, product_id, quantity, unit_price) "
                        "VALUES (%s, %s, %s, %s)",
                        (order_id, product_id, qty, unit_price),
                    )

            # ---- 全部成功，提交事务 ----
            conn.commit()
            return True, f"订单创建成功！订单号：#{order_id}，总金额：¥{total:.2f}"
        except pymysql.Error as e:
            conn.rollback()
            return False, f"订单创建失败（事务已回滚）：{e}"
        finally:
            conn.close()

    def get_by_user(self, user_id: int) -> list:
        """查询某用户的全部订单"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT o.order_id, o.machine_id, m.name AS machine_name, "
                    "o.total_amount, o.status, o.created_at "
                    "FROM orders o "
                    "JOIN vending_machines m ON o.machine_id = m.machine_id "
                    "WHERE o.user_id = %s "
                    "ORDER BY o.created_at DESC",
                    (user_id,),
                )
                return cur.fetchall()
        finally:
            conn.close()

    def get_detail(self, order_id: int) -> tuple:
        """查询订单详情（主表 + 明细列表）"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                # 主表
                cur.execute(
                    "SELECT o.*, u.username, m.name AS machine_name "
                    "FROM orders o "
                    "JOIN users u ON o.user_id = u.user_id "
                    "JOIN vending_machines m ON o.machine_id = m.machine_id "
                    "WHERE o.order_id = %s",
                    (order_id,),
                )
                order = cur.fetchone()
                if not order:
                    return None, []
                # 明细
                cur.execute(
                    "SELECT od.*, p.name AS product_name "
                    "FROM order_details od "
                    "JOIN products p ON od.product_id = p.product_id "
                    "WHERE od.order_id = %s",
                    (order_id,),
                )
                details = cur.fetchall()
                return order, details
        finally:
            conn.close()

    def list_all(self) -> list:
        """查询全部订单（管理员用）"""
        conn = self.db.get_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT o.order_id, u.username, m.name AS machine_name, "
                    "o.total_amount, o.status, o.created_at "
                    "FROM orders o "
                    "JOIN users u ON o.user_id = u.user_id "
                    "JOIN vending_machines m ON o.machine_id = m.machine_id "
                    "ORDER BY o.created_at DESC "
                    "LIMIT 50"
                )
                return cur.fetchall()
        finally:
            conn.close()


# ============================================================
# 系统初始化
# ============================================================
def init_system():
    """连接 MySQL 并初始化数据库"""
    db = Database()
    print("=" * 56)
    print("  自动售货机管理系统 — 数据库初始化")
    print("=" * 56)
    try:
        db.init_all()
    except pymysql.err.OperationalError as e:
        print(f"\n[FAIL] 无法连接 MySQL，请检查：")
        print(f"  1. MySQL 服务是否已启动")
        print(f"  2. DB_CONFIG 中的 host/user/password 是否正确")
        print(f"  原始错误：{e}")
        sys.exit(1)
    print("=" * 56)
    return db


# ============================================================
# 命令行交互界面
# ============================================================

def _input_int(prompt: str, default: int = None) -> int:
    """读取整数输入"""
    try:
        s = input(prompt).strip()
        if s == "" and default is not None:
            return default
        return int(s)
    except ValueError:
        return None


def _input_float(prompt: str) -> float:
    """读取浮点数输入"""
    try:
        return float(input(prompt).strip())
    except ValueError:
        return None


# ---------- 管理员菜单 ----------
def admin_menu(db: Database, user: dict):
    """管理员功能界面"""
    product_dao = ProductDAO(db)
    machine_dao = MachineDAO(db)
    inventory_dao = InventoryDAO(db)
    order_dao = OrderDAO(db)
    user_dao = UserDAO(db)

    while True:
        print("\n" + "-" * 48)
        print(f"  管理员菜单 | 当前用户：{user['username']}(admin)")
        print("-" * 48)
        print("  1. 商品管理（添加/修改/删除/查看）")
        print("  2. 售货机管理（添加/修改状态/查看）")
        print("  3. 库存管理（补货/查看）")
        print("  4. 查看所有订单")
        print("  5. 查看所有用户")
        print("  0. 退出登录")
        print("-" * 48)
        choice = input("请选择操作：").strip()

        if choice == "1":
            _admin_product_menu(product_dao)
        elif choice == "2":
            _admin_machine_menu(machine_dao)
        elif choice == "3":
            _admin_inventory_menu(inventory_dao, product_dao, machine_dao)
        elif choice == "4":
            orders = order_dao.list_all()
            print("\n[订单列表]（最近50条）")
            print(f"{'订单号':<8}{'用户':<14}{'售货机':<22}{'金额':<10}{'状态':<12}{'时间'}")
            print("-" * 90)
            for o in orders:
                print(f"#{o['order_id']:<7}{o['username']:<14}"
                      f"{o['machine_name']:<22}¥{o['total_amount']:<9.2f}"
                      f"{o['status']:<12}{str(o['created_at'])}")
            if not orders:
                print("  （暂无订单记录）")
        elif choice == "5":
            users = user_dao.list_all()
            print("\n[用户列表]")
            print(f"{'ID':<6}{'用户名':<16}{'角色':<8}{'余额':<10}{'手机号':<14}{'邮箱'}")
            print("-" * 80)
            for u in users:
                print(f"{u['user_id']:<6}{u['username']:<16}{u['role']:<8}"
                      f"¥{u['balance']:<9.2f}{u['phone'] or '-':<14}{u['email'] or '-'}")
        elif choice == "0":
            print("已退出管理员登录。\n")
            break
        else:
            print("无效选项，请重新输入。")


def _admin_product_menu(product_dao: ProductDAO):
    """管理员 - 商品管理子菜单"""
    while True:
        print("\n  >>> 商品管理")
        print("    1. 查看全部商品    2. 添加商品")
        print("    3. 修改商品        4. 删除商品")
        print("    0. 返回上级")
        sub = input("  请选择：").strip()
        if sub == "1":
            products = product_dao.list_all()
            print(f"\n  {'ID':<6}{'名称':<16}{'分类':<12}{'单价':<10}{'描述'}")
            print("  " + "-" * 64)
            for p in products:
                print(f"  {p['product_id']:<6}{p['name']:<16}{p['category'] or '-':<12}"
                      f"¥{p['price']:<9.2f}{p['description'] or '-'}")
            if not products:
                print("  （暂无商品）")
        elif sub == "2":
            name = input("  商品名称：").strip()
            if not name:
                print("  名称不能为空")
                continue
            cat = input("  商品分类：").strip()
            desc = input("  商品描述：").strip()
            price = _input_float("  商品单价：")
            if price is None or price <= 0:
                print("  单价必须为正数")
                continue
            ok, msg = product_dao.add(name, cat, desc, price)
            print(f"  {'[OK]' if ok else '[FAIL]'} {msg}")
        elif sub == "3":
            pid = _input_int("  要修改的商品ID：")
            if pid is None:
                continue
            name = input("  新名称（留空不修改）：").strip()
            cat = input("  新分类（留空不修改）：").strip()
            desc = input("  新描述（留空不修改）：").strip()
            price_str = input("  新单价（留空不修改）：").strip()
            # 先读取旧值
            products = product_dao.list_all()
            old = next((p for p in products if p["product_id"] == pid), None)
            if not old:
                print("  商品不存在")
                continue
            name = name or old["name"]
            cat = cat or old["category"]
            desc = desc or old["description"]
            price = float(price_str) if price_str else old["price"]
            ok, msg = product_dao.update(pid, name, cat, desc, price)
            print(f"  {'[OK]' if ok else '[FAIL]'} {msg}")
        elif sub == "4":
            pid = _input_int("  要删除的商品ID：")
            if pid is None:
                continue
            ok, msg = product_dao.delete(pid)
            print(f"  {'[OK]' if ok else '[FAIL]'} {msg}")
        elif sub == "0":
            break
        else:
            print("  无效选项")


def _admin_machine_menu(machine_dao: MachineDAO):
    """管理员 - 售货机管理子菜单"""
    while True:
        print("\n  >>> 售货机管理")
        print("    1. 查看全部售货机  2. 添加售货机")
        print("    3. 修改状态        0. 返回上级")
        sub = input("  请选择：").strip()
        if sub == "1":
            machines = machine_dao.list_all()
            print(f"\n  {'ID':<6}{'名称':<22}{'位置':<24}{'状态':<14}{'容量'}")
            print("  " + "-" * 72)
            for m in machines:
                print(f"  {m['machine_id']:<6}{m['name']:<22}{m['location'] or '-':<24}"
                      f"{m['status']:<14}{m['capacity']}")
        elif sub == "2":
            name = input("  售货机名称：").strip()
            if not name:
                print("  名称不能为空")
                continue
            loc = input("  摆放位置：").strip()
            cap = _input_int("  最大容量（默认100）：", 100)
            ok, msg = machine_dao.add(name, loc, cap)
            print(f"  {'[OK]' if ok else '[FAIL]'} {msg}")
        elif sub == "3":
            mid = _input_int("  售货机ID：")
            if mid is None:
                continue
            print("  可选状态：online(在线) / offline(离线) / maintenance(维护中)")
            status = input("  新状态：").strip()
            ok, msg = machine_dao.update_status(mid, status)
            print(f"  {'[OK]' if ok else '[FAIL]'} {msg}")
        elif sub == "0":
            break
        else:
            print("  无效选项")


def _admin_inventory_menu(inv_dao: InventoryDAO, prod_dao: ProductDAO,
                          machine_dao: MachineDAO):
    """管理员 - 库存管理子菜单"""
    while True:
        print("\n  >>> 库存管理")
        print("    1. 查看售货机库存   2. 补货/上架")
        print("    3. 直接设置库存     0. 返回上级")
        sub = input("  请选择：").strip()
        if sub == "1":
            mid = _input_int("  售货机ID：")
            if mid is None:
                continue
            items = inv_dao.get_by_machine(mid)
            print(f"\n  售货机 #{mid} 库存：")
            print(f"  {'商品ID':<8}{'商品名称':<18}{'单价':<10}{'库存':<8}{'最大容量'}")
            print("  " + "-" * 54)
            for it in items:
                print(f"  {it['product_id']:<8}{it['product_name']:<18}"
                      f"¥{it['price']:<9.2f}{it['quantity']:<8}{it['max_quantity']}")
            if not items:
                print("  （该售货机暂无库存记录）")
        elif sub == "2":
            mid = _input_int("  售货机ID：")
            if mid is None:
                continue
            pid = _input_int("  商品ID：")
            if pid is None:
                continue
            qty = _input_int("  补货数量：")
            if qty is None or qty <= 0:
                print("  数量必须为正整数")
                continue
            ok, msg = inv_dao.add_or_update(mid, pid, qty)
            print(f"  {'[OK]' if ok else '[FAIL]'} {msg}")
        elif sub == "3":
            mid = _input_int("  售货机ID：")
            if mid is None:
                continue
            pid = _input_int("  商品ID：")
            if pid is None:
                continue
            qty = _input_int("  新库存数量：")
            if qty is None or qty < 0:
                print("  数量不能为负数")
                continue
            ok, msg = inv_dao.update_stock(mid, pid, qty)
            print(f"  {'[OK]' if ok else '[FAIL]'} {msg}")
        elif sub == "0":
            break
        else:
            print("  无效选项")


# ---------- 普通用户菜单 ----------
def user_menu(db: Database, user: dict):
    """普通用户功能界面"""
    product_dao = ProductDAO(db)
    machine_dao = MachineDAO(db)
    inventory_dao = InventoryDAO(db)
    order_dao = OrderDAO(db)
    user_dao = UserDAO(db)

    while True:
        # 刷新用户余额
        current_user = user_dao.get_by_id(user["user_id"])
        balance = current_user["balance"] if current_user else 0.0

        print("\n" + "-" * 48)
        print(f"  用户菜单 | {current_user['username']} | 余额：¥{balance:.2f}")
        print("-" * 48)
        print("  1. 浏览售货机商品")
        print("  2. 购买商品（核心事务演示）")
        print("  3. 查看我的订单")
        print("  4. 查看订单详情")
        print("  5. 账户充值")
        print("  6. 修改密码")
        print("  0. 退出登录")
        print("-" * 48)
        choice = input("请选择操作：").strip()

        if choice == "1":
            machines = machine_dao.list_online()
            if not machines:
                print("\n当前没有在线的售货机。")
                continue
            print(f"\n{'ID':<6}{'名称':<22}{'位置'}")
            print("-" * 52)
            for m in machines:
                print(f"{m['machine_id']:<6}{m['name']:<22}{m['location'] or '-'}")
            mid = _input_int("\n请输入售货机ID查看商品（0返回）：")
            if mid is None or mid == 0:
                continue
            items = inventory_dao.get_by_machine(mid)
            if not items:
                print("该售货机暂无商品。")
                continue
            print(f"\n{'商品ID':<8}{'名称':<18}{'单价':<10}{{'库存'}}")
            print("-" * 44)
            for it in items:
                print(f"{it['product_id']:<8}{it['product_name']:<18}"
                      f"¥{it['price']:<9.2f}{it['quantity']}件")

        elif choice == "2":
            # ===== 核心：购买商品（带事务保障） =====
            machines = machine_dao.list_online()
            if not machines:
                print("\n当前没有在线的售货机。")
                continue
            print(f"\n可用的售货机：")
            for m in machines:
                print(f"  #{m['machine_id']} - {m['name']} ({m['location'] or '-'})")
            mid = _input_int("请输入售货机ID：")
            if mid is None:
                continue

            # 展示该售货机的商品
            items = inventory_dao.get_by_machine(mid)
            if not items:
                print("该售货机暂无商品。")
                continue
            print(f"\n{'商品ID':<8}{'名称':<18}{'单价':<10}{'库存'}")
            print("-" * 44)
            for it in items:
                print(f"{it['product_id']:<8}{it['product_name']:<18}"
                      f"¥{it['price']:<9.2f}{it['quantity']}件")

            # 构建购买清单
            print("\n请输入购买清单（每行：商品ID 数量），输入空行结束：")
            print("示例：")
            print("  1 2   （表示购买商品1共2件）")
            print("  3 1")
            cart = []
            while True:
                line = input("  > ").strip()
                if not line:
                    break
                parts = line.split()
                if len(parts) != 2:
                    print("  格式错误，请重新输入（商品ID 数量）")
                    continue
                pid = _input_int_value(parts[0])
                qty = _input_int_value(parts[1])
                if pid is None or qty is None or qty <= 0:
                    print("  输入无效，请重新输入")
                    continue
                cart.append((pid, qty))
            if not cart:
                print("购买清单为空，已取消。")
                continue

            # 确认购买
            print(f"\n购买清单共 {len(cart)} 种商品，确认购买？(y/n)：", end="")
            if input().strip().lower() != "y":
                print("已取消购买。")
                continue

            # 执行事务型订单创建
            ok, msg = order_dao.create_order(user["user_id"], mid, cart)
            print(f"\n{'*** [事务成功]' if ok else '!!! [事务失败/回滚]'} {msg}")

        elif choice == "3":
            orders = order_dao.get_by_user(user["user_id"])
            print(f"\n{'订单号':<8}{'售货机':<22}{'金额':<10}{'状态':<12}{'时间'}")
            print("-" * 76)
            for o in orders:
                print(f"#{o['order_id']:<7}{o['machine_name']:<22}"
                      f"¥{o['total_amount']:<9.2f}{o['status']:<12}{str(o['created_at'])}")
            if not orders:
                print("  （暂无订单记录）")

        elif choice == "4":
            oid = _input_int("请输入订单号：")
            if oid is None:
                continue
            order, details = order_dao.get_detail(oid)
            if not order:
                print("订单不存在。")
                continue
            print(f"\n订单 #{oid} 详情：")
            print(f"  用户：{order['username']}")
            print(f"  售货机：{order['machine_name']}")
            print(f"  金额：¥{order['total_amount']:.2f}")
            print(f"  状态：{order['status']}")
            print(f"  时间：{order['created_at']}")
            print(f"\n  {'商品名称':<20}{'数量':<8}{'单价':<10}{'小计'}")
            print("  " + "-" * 48)
            for d in details:
                subtotal = d["quantity"] * d["unit_price"]
                print(f"  {d['product_name']:<20}{d['quantity']:<8}"
                      f"¥{d['unit_price']:<9.2f}¥{subtotal:.2f}")

        elif choice == "5":
            amount = _input_float("请输入充值金额：")
            if amount is None or amount <= 0:
                print("充值金额必须为正数。")
                continue
            ok, msg = user_dao.recharge(user["user_id"], amount)
            print(f"{'[OK]' if ok else '[FAIL]'} {msg}")

        elif choice == "6":
            old_pwd = getpass("  当前密码：")
            new_pwd = getpass("  新密码：")
            if not new_pwd:
                print("  密码不能为空")
                continue
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT password FROM users WHERE user_id = %s",
                        (user["user_id"],),
                    )
                    old_hash = cur.fetchone()[0]
                    if old_hash != hash_password(old_pwd):
                        print("  当前密码错误")
                    else:
                        cur.execute(
                            "UPDATE users SET password = %s WHERE user_id = %s",
                            (hash_password(new_pwd), user["user_id"]),
                        )
                        conn.commit()
                        print("  密码修改成功")
            finally:
                conn.close()

        elif choice == "0":
            print("已退出登录。\n")
            break
        else:
            print("无效选项，请重新输入。")


def _input_int_value(s: str) -> int:
    """字符串转整数，失败返回 None"""
    try:
        return int(s)
    except ValueError:
        return None


# ---------- 主入口 ----------
def main():
    """主函数：初始化系统 -> 登录 -> 角色分流"""
    db = init_system()
    user_dao = UserDAO(db)

    while True:
        print("\n" + "=" * 48)
        print("  自动售货机管理系统")
        print("=" * 48)
        print("  1. 用户登录")
        print("  2. 用户注册")
        print("  0. 退出系统")
        print("=" * 48)
        choice = input("请选择：").strip()

        if choice == "1":
            username = input("用户名：").strip()
            password = getpass("密码：")
            user, msg = user_dao.login(username, password)
            if user is None:
                print(f"登录失败：{msg}")
            else:
                print(f"登录成功！欢迎 {user['username']}（{user['role']}）")
                if user["role"] == "admin":
                    admin_menu(db, user)
                else:
                    user_menu(db, user)

        elif choice == "2":
            username = input("请输入用户名：").strip()
            if not username:
                print("用户名不能为空")
                continue
            password = getpass("请输入密码：")
            if not password:
                print("密码不能为空")
                continue
            phone = input("手机号（可选）：").strip() or None
            email = input("邮箱（可选）：").strip() or None
            ok, msg = user_dao.register(username, password, phone, email)
            print(f"{'[OK]' if ok else '[FAIL]'} {msg}")

        elif choice == "0":
            print("感谢使用自动售货机管理系统，再见！")
            sys.exit(0)
        else:
            print("无效选项，请重新输入。")


if __name__ == "__main__":
    main()
