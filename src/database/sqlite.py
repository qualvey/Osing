import json
import sqlite3
import socket
from typing import Optional, Dict, Any, List
import logging
import contextlib
logger = logging.getLogger(__name__)

#应该使用单例模式，整个项目只有一个db实例，不允许其他模块自己实例化本类

class ProxyUserDB:
    
    def __init__(self, db_path: str = "proxy_users.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库和表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 核心建表：listen_port 已经是 UNIQUE 了，无需在下方重复创建 UNIQUE INDEX
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uuid TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tag TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    listen_port INTEGER UNIQUE NOT NULL,
                    comment TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            # 2. 读取当前数据库里真实存在的所有列名（用于老版本兼容）
            cursor.execute("PRAGMA table_info(users)")
            current_columns = [row[1] for row in cursor.fetchall()]
            
            # ----------------------------------------------------
            # 补丁 A：检查并修复历史超老版本缺失的 listen_port 列
            # ----------------------------------------------------
            if "listen_port" not in current_columns:
                logger.warning("⚠️ 检测到老版本数据库缺少 'listen_port' 列，正在尝试动态升级...")
                cursor.execute("ALTER TABLE users ADD COLUMN listen_port INTEGER")
                conn.commit()
                
                cursor.execute("SELECT uuid FROM users")
                old_users = cursor.fetchall()
                for index, (old_uuid,) in enumerate(old_users):
                    fix_port = 10000 + index
                    cursor.execute("UPDATE users SET listen_port = ? WHERE uuid = ?", (fix_port, old_uuid))
                conn.commit()

            # ----------------------------------------------------
            # 补丁 B：检查并修复历史老版本缺失的 enabled 状态列
            # ----------------------------------------------------
            if "enabled" not in current_columns:
                logger.warning("⚠️ 检测到老版本数据库缺少 'enabled' 状态列，正在进行动态升级...")
                cursor.execute("ALTER TABLE users ADD COLUMN enabled BOOLEAN DEFAULT 1")
                cursor.execute("UPDATE users SET enabled = 1 WHERE enabled IS NULL")
                conn.commit()

            # ----------------------------------------------------
            # 3. 终极防御：仅创建普通优化索引（移除那个冲突的 UNIQUE 索引）
            # ----------------------------------------------------
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_name ON users(name)")
            conn.commit()
            
            logger.info("🚀 数据库结构自检完成，所有字段已处于最新状态！")
            
    @contextlib.contextmanager
    def transaction(self):
        """
        显式提供一个数据库事务上下文。
        如果在 with 块内发生任何异常，数据库将自动回滚，绝不保存脏数据。
        """
        # 注意：不要用 isolation_level=None，保持默认的事务行为
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # 开启一个显式事务
            conn.execute("BEGIN TRANSACTION;")
            yield conn  # 把 conn 抛给外面用（如果你需要的话）
            
            # 只有 outside 没有任何异常顺利执行完，才会走到这里
            conn.commit()
            logger.info("💾 [Database] 事务成功提交入库！")
        except Exception as e:
            # 只要中途报错（包括 service 报错、client 报错），立刻回滚
            conn.rollback()
            logger.error(f"↩️ [Database] 捕获到上层异常，数据库事务已全面回滚！原因: {e}")
            raise e  # 继续往外抛，通知你的业务逻辑层
        finally:
            conn.close()

    def save_inside_transaction(self, conn, user_data: Dict[str, Any]):
        """
        给外部事务调用的专用写入方法。
        注意：这里千万不能自己调 commit()，要用传入的 conn 句柄。
        """
        cursor = conn.cursor()
        # 根据你表的字段，执行插入或替换
        cursor.execute("""
            INSERT OR REPLACE INTO users (uuid, name, tag, password, listen_port, comment, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_data.get("uuid"),
            user_data.get("name"),
            user_data.get("tag"),
            user_data.get("password"),
            user_data.get("listen_port"),
            user_data.get("comment"),
            user_data.get("enabled", 1),
            user_data.get("created_at")
        ))
    def _is_port_in_use_by_system(self, port: int) -> bool:
        """内部方法：检测该端口在当前操作系统中是否已被占用"""
        # 创建一个 TCP 套接字
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # 尝试绑定到 0.0.0.0 的这个端口
                s.bind(("0.0.0.0", port))
                return False  # 绑定成功，说明端口干净，没有被其他软件占用
            except socket.error:
                return True   # 绑定失败（报错），说明端口已经被占用了
            
    def check_every_port_usable(self):
        pass
    
    def get_next_available_port(self, start_port: int = 10000) -> int:
            """
            核心方法：获取下一个【既不在数据库，也不在系统层】冲突的绝对安全端口
            """
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(listen_port) FROM users")
                row = cursor.fetchone()
                
                # 基础候选端口：如果数据库为空，用起始端口；否则用最大值 + 1
                candidate_port = start_port if row[0] is None else row[0] + 1

            # 🔄 双重校验循环：
            # 如果发现这个端口在系统层已经被其他软件（如 Nginx、MySQL等）占用了，
            # 就让端口号继续往上加 1，直到找到一个既安全又干净的端口为止。
            while self._is_port_in_use_by_system(candidate_port):
                candidate_port += 1

            return candidate_port
        
    def is_user_enabled(self, username: str) -> bool:
        """
        检查指定用户是否处于启用状态 (enabled = 1)
        如果没有找到该用户，默认返回 False
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 只需要查 enabled 这一个字段即可，极致的高效
            cursor.execute("SELECT enabled FROM users WHERE name = ? LIMIT 1", (username,))
            row = cursor.fetchone()
            
            # 如果没找到用户，row 是 None，直接返回 False
            if row is None:
                logger.warning(f"查询启用状态失败：用户 {username} 不存在")
                return False
                
            # row[0] 的值可能是 1(True) 或 0(False)
            # 优雅地用 bool() 强转一下，让返回结果更纯粹
            return bool(row[0])
        
    def set_user_enabled(self, uuid: str, enabled: bool) -> bool:
        """
        设置用户的启用/禁用状态
        :param uuid: 用户的 UUID
        :param enabled: True 代表启用 (1), False 代表禁用 (0)
        :return: True 代表修改成功, False 代表用户不存在，修改失败
        """
        # 将 Python 的 bool 值转为 SQLite 喜欢的 1 或 0
        status_value = 1 if enabled else 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 执行更新操作
            cursor.execute(
                "UPDATE users SET enabled = ? WHERE uuid = ?", 
                (status_value, uuid)
            )
            conn.commit()
            
            # 优雅小技巧：cursor.rowcount 可以直接拿到这次 SQL 实际影响/修改了多少行
            if cursor.rowcount == 0:
                logger.warning(f"更新状态失败：未找到 {uuid} 的用户")
                return False
                
            logger.info(f"成功将用户 {uuid} 的状态修改为: {'启用' if enabled else '禁用'}")
            return True
        
    def exists_by_name(self, username: str) -> bool:
        """
        检查指定的用户名是否存在于数据库中
        返回: True (存在) / False (不存在)
        """
        with sqlite3.connect(self.db_path) as conn:
            logger.info(f"检查用户名是否存在{username}")
            
            cursor = conn.cursor()
            # 使用 SELECT 1 和 LIMIT 1 达到极致性能
            cursor.execute("SELECT 1 FROM users WHERE name = ? LIMIT 1", (username,))
            row = cursor.fetchone()
            # 如果 row 不是 None，说明找到了匹配的数据，返回 True；否则返回 False
            return row is not None
        
    def save(self, user_data: dict[str, Any]):

        # 写入数据库
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (uuid, name, tag, password, listen_port, comment, created_at,  enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?,?)
                """,
                (
                    user_data["uuid"],
                    user_data["name"],
                    user_data["tag"],
                    user_data["password"],
                    user_data["listen_port"],
                    user_data["comment"],
                    user_data["created_at"],
                    1
                )
            )
            conn.commit()

    # --- 核心需求 1：通过 uuid -> name ---
    def get_name_by_uuid(self, user_uuid: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM users WHERE uuid = ?", (user_uuid,))
            row = cursor.fetchone()
            return row[0] if row else None
        
    def get_user_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE uuid = ?", (user_uuid,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # --- 核心需求 2：通过 name -> alldata ---
    def get_alldata_by_name(self, username: str) -> Optional[Dict[str, Any]]:
        """
        通过用户名获取用户的完整数据字典（对接登录系统）
        """
        with sqlite3.connect(self.db_path) as conn:
            # 允许通过列名访问：row['uuid'] 而不是 row[1]
            conn.row_factory = sqlite3.Row
            
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE name = ?", (username,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            # ─── 核心修复：将 sqlite3.Row 完美转换为标准 Python 字典 ───
            user_dict = dict(row)
            
            # ─── 健壮性防御：向后兼容机制 ───
            # 如果你还没来得及执行 ALTER TABLE 增加字段，代码也不会崩，
            # 它会自动垫一个 None，防止接下来的登录逻辑报 KeyError
            if "password_hash" not in user_dict:
                user_dict["password_hash"] = None
                
            return user_dict
        
    def get_all_users(self) -> List[Dict[str, Any]]:

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
    def get_all_users_by_name(self, username: str) -> List[Dict[str, Any]]:
        logger.info(f"getting users by name: {username}")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE name = ?", (username,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        # --- 核心需求 3：通过 uuid 删除用户 ---
    def delete_by_uuid(self, user_uuid: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE uuid = ?", (user_uuid,))
            conn.commit()  # 💡 必须 commit，否则删除不会生效
            
            # cursor.rowcount 会返回受影响的行数
            # 如果变动行数大于 0，说明成功删除了用户；如果为 0，说明原本就没有这个 uuid
            return cursor.rowcount > 0
        