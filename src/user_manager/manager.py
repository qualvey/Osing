import json
import uuid
import secrets
import datetime
import re
import os
import sys
import logging
from pypinyin import pinyin, Style
# from gi.repository import GLib
from typing import Optional, Dict, Any
import asyncio
from database.sqlite import db

import logging
from aioconsole import ainput
logger = logging.getLogger(__name__)

from Client import ClientManager
from  Service import UserService

from Settings import settings
CONFIG_PATH = settings.server_config_path
domain:str  = settings.domain
transport_path = settings.transport_path

class UserNotFoundError(Exception):
    """自定义业务异常：当数据库/缓存中找不到必须存在的用户时触发"""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Critical Error: User '{name}' must exist but was not found in Redis.")

class UserManager:
    def __init__(self, *, _from_factory: bool = False):
        # 🚨 依然保留坚固的防御：禁止外部直接调用 UserManager()
        if not _from_factory:
            raise RuntimeError(
                "❌ 危险操作：禁止直接实例化 UserManager！"
                "请使用安全的工厂方法: await UserManager.bind(...) 或 await UserManager.bind_with_uuid(...)"
            )
        
        # 💡 这里初始化所有的默认空白属性
        self.name: str = ""
        self.config_path = CONFIG_PATH
        self.userData: Dict[str, Any] = {}
        self.service: UserService
        self.client: ClientManager
        self.is_persisted: bool = False  # 顺便加上状态：是老用户还是新用户
        
    @classmethod
    async def add(cls, name: str):
    
        '''只生成数据，不写入，写入用save'''
        logger.info(f"准备用户: {name}")
        
        if db.exists_by_name(name):
            existing_users = db.get_all_users_by_name(name)
            print(f"\n\033[93m⚠️ 发现系统中已存在 {len(existing_users)} 个同名用户:\033[0m")
            for idx, user in enumerate(existing_users):
                pinyin = user.get("pinyin", "无")
                uuid = user.get("uuid", "无")
                comment = user.get("comment", "")
                comment_str = f" | 备注: {comment}" if comment else ""
                print(f"  [\033[1;36m{idx}\033[0m] 拼音: {pinyin} | UUID: {uuid[-8:]}{comment_str}")
            
            print(f"  [\033[1;32mn\033[0m] \033[32m另起炉灶：不理会它们，创建一个全新的同名独立账号\033[0m")
            print(f"  [\033[1;31mq\033[0m] \033[31m取消退出\033[0m")
            try:
                choice = await ainput("\n👉 请输入序号选择操作 [q]: ")
                choice = choice.strip().lower()
                
                # 情况 A：取消操作
                if choice == 'q' or choice == '':
                    logger.info("操作已取消。")
                    return None
                    
                # 情况 B：不覆盖，直接开新号
                elif choice == 'n':
                    logger.info(f"准备为 {name} 创建全新的独立分身账号...")
                    # 走纯新建流程：跳出 if 块，继续往下跑生成新数据的逻辑
                    pass
                    
                # 情况 C：输入了数字，选择绑定现有的其中一个老用户
                elif choice.isdigit() and int(choice) < len(existing_users):
                    selected_user_data = existing_users[int(choice)]
                    
                    logger.info(f"👉 成功锁定老用户，但是不能在add方法中返回")
                    # 💡 妙招：直接调用刚才设计好的 bind_with_uuid 拿到实例，原地返回！
                    return None
                    
                else:
                    print("\n[!] 输入错误，操作已取消。")
                    return None
                    
            except (asyncio.CancelledError, KeyboardInterrupt):
                print("\n[!] 操作已取消。")
                return None
            
            # 2. 【全新创建的路线】只有管理员选了 'n' 或者本身就没有同名用户时，才会走到这里
        instance = cls(_from_factory=True)
        instance.name = name
        instance.is_persisted = False
        try:
            user_input = await ainput("\n👉 请输入用户备注（输入 q 退出）: ")
            clean_input = user_input.strip()
            
            # 💡 1. 拦截退出指令
            if clean_input.lower() == 'q':
                logger.info("用户主动输入 'q'，操作已取消。")
                return None  # 优雅返回 None，不留脏数据
                
            # 2. 如果直接敲回车，就给个默认空字符串，继续往下走
            comment = clean_input or ""
            
        except (asyncio.CancelledError, KeyboardInterrupt):
            # 💡 3. 拦截 Ctrl+C
            print("\n[!] 检测到中断信号，操作已取消。")
            return None
        # 纯内存生成新数据的逻辑（不再带有查重污染）
        user_data =  instance._generate_credentials(comment) 
        if user_data is None:
            return None
            
        instance.userData = user_data
        instance.service = UserService(user_data)
        instance.client = ClientManager(user_data)
        
        return instance
    
    @classmethod
    async def bind_with_uuid(cls, uuid: str):
        logger.info(f"binding user {uuid}")
        userdata = db.get_user_by_uuid(uuid)
        if userdata is None:
            logger.warning("⚠️ 用户不存在")
            return 
        
        instance = cls(_from_factory=True)
        
        instance.userData = userdata
        
        instance.service = UserService(userdata)
        instance.client = ClientManager(userdata)
        instance.is_persisted = True
        
        return instance
    
    @classmethod
    async def get_user_by_name(cls, input_name: str) -> Optional["UserManager"]:
        """
        🎯 核心映射器：谁来把 name -> uuid 完成映射？就是我！
        它负责把人类输入的模糊名字，映射成内存中唯一的、绑定的用户对象。
        """
        # 1. 查数据库：拿着这个模糊的 name，去档案柜里翻出所有的记录
        existing_users = db.get_all_users_by_name(input_name)
        
        # 2. 如果查出来空空如也，映射失败
        if not existing_users:
            logger.warning(f"❌ 系统中不存在名为 [{input_name}] 的用户")
            return None
            
        # 3. 如果刚好只有一个，天注定的缘分，直接完成映射！
        if len(existing_users) == 1:
            target_user_data = existing_users[0]
            # 默默提取出它的唯一 UUID
            target_uuid = target_user_data["uuid"] 
            
            # 实例化对象，并用它自己的 UUID 现成数据灌满它，返回出去！
            return await cls.bind_with_uuid(target_uuid)
            
        # 4. 🚨 重点：如果有多个同名用户！映射陷入混乱，开始寻求操作人（管理员）的选择
        print(f"\n⚠️ 发现系统中存在多个名为 [{input_name}] 的用户，请精准锁定：")
        for idx, u in enumerate(existing_users):
            print(f"  [{idx}] 拼音: {u['tag']} | UUID 尾号: {u['uuid'][-8:]} | 备注: {u['comment']}")
            
        try:
            choice = await ainput("\n👉 请输入数字序号选择要操作的用户: ")
            if choice.isdigit() and int(choice) < len(existing_users):
                # 操作人指定了其中一个档案
                selected_data = existing_users[int(choice)]
                
                # 💡 映射完成！我们拿到了无可辩驳的唯一 UUID！
                target_uuid = selected_data["uuid"]
                
                # 调用 uuid 绑定工厂，安全诞生出这个特定用户的实例
                return await cls.bind_with_uuid(target_uuid)
            else:
                print("输入无效，放弃操作。")
                return None
        except (asyncio.CancelledError, KeyboardInterrupt):
            return None
    
    def perge(self):
        uuid = self.userData.get("uuid")
        assert isinstance(uuid, str), "panic"
        
        db.delete_by_uuid(uuid)
        self.service.purge()
        self.client.purge()
        #TODO DELETE client config and service node both
        
    def _generate_credentials(self, comment: str = "") -> dict:
        #还有listen_port,怎么生成和保存
        assigned_port = db.get_next_available_port(start_port=10000)
        # 转换为拼音列表，不带声调
        py_list = pinyin(self.name, style=Style.NORMAL)
        # 扁平化并连接
        py_str = "".join([item[0] for item in py_list])
        # 只保留字母、数字和下划线，防止非法路径字符
        pinyin_name = re.sub(r'[^a-zA-Z0-9_]', '', py_str).lower()

        user_uuid = str(uuid.uuid4())
        tag = f"{pinyin_name}_{user_uuid[:4]}"
        
        return {
            "name": self.name,
            "tag": tag,
            "uuid": user_uuid,
            "password": secrets.token_urlsafe(16), # 生成高强度密码
            "listen_port": assigned_port,
            "comment": comment,
            "created_at": datetime.datetime.now().isoformat()
        }
        
    @classmethod
    def new_user_from_data( cls,user_data: dict) -> "UserManager":
        instance = cls(_from_factory=True)
        
        instance.userData = user_data
        instance.service = UserService(user_data)
        instance.client = ClientManager(user_data)
        instance.is_persisted = True
        
        return instance

    def save(self):
        service_merged = False
        client_added = False
        assert self.service is not None, "ServiceManager 未初始化！"
        try:
            with db.transaction() as conn:
                db.save_inside_transaction(conn, self.userData)
                self.service.merge()
                service_merged = True
                self.client.add()
                client_added = True

            self.is_persisted = True
            logger.info(f"🎉 [UserManager] 用户 {self.userData.get('name')} 的铁三角原子配置全线成功！")
            return True
        except Exception as e:
            logger.error(f"事务回滚: {e}")
            if service_merged:
                try:
                    # 假定你有恢复方法，或者在 service 内部做备份还原
                    # self.service.rollback_merge() 
                    logger.info("↩️ [回滚] 已复原服务端配置文件污染")
                    self.service.rollback()
                except Exception as se:
                    logger.error(f"服务端文件回滚失败: {se}")
                    
            if client_added or True: # 只要文件夹建了就顺手扬了它
                try:
                    self.client.purge()
                except Exception as ce:
                    logger.error(f"客户端物理文件清理失败: {ce}")
            
            # 告诉上层调用者这次 save 失败了
            return False
    
    def disable(self):
        """停止用户：仅从配置文件移除，保留 Redis 数据"""
        logger.info(f"Disable User {self.name}")
        uuid = self.userData.get("uuid")
        # 断言 uuid 绝对不能为 None，否则直接 panic 并打印后面的错误信息
        assert isinstance(uuid, str), "panic"
        db.set_user_enabled(uuid, False)

    async def enable(self):
        """启用用户：从 Redis 恢复数据到配置文件"""
        logger.info(f"Enable User {self.name}")
        uuid = self.userData.get("uuid")
        assert isinstance(uuid, str), "panic"
        
        db.set_user_enabled(uuid, True)

    async def list_all_users(self):
        """列出所有用户及其状态"""
        all_users = []
        db.get_all_users_by_name()

    #把一个用户的data结构（和sing-box tuic的user结构一样)，写入redis
    #如果存在name相同的用户，现在的逻辑是只命中第一个找到的用户
    #应该做处理，比如提示有几个name相等的user,然后选择pinyinname来唯一定位用户，或者直接禁止创建同名用户。
    #pinyin_name依然存在duplicate的可能，但概率极低，如果name和uuid的前4位都一样的话。
    #todo: 可以删除全部，和删除多个。比如*代表删除全部同名用户，输入1,2,3代表删除对应的用户,多个以逗号分隔。删除时也要提示用户，避免误删。
    async def remove_user(self, user_data: dict):
        """删除用户：移除配置、Redis 数据及文件"""
        print(f"-> 正在删除用户: {user_data.get('name')}")
        
        # 1. 查找所有匹配的用户 (Redis + Config)
        candidates = []
        seen_uuids = set()

        # # 1.1 Search Redis
        # try:
        #     async for key in self.r.scan_iter("user:*"):
        #         try:
        #             data = await self.r.get(key)
        #             if data:
        #                 u = json.loads(str(data))
        #                 if u.get("name") == username:
        #                     if u.get("uuid") not in seen_uuids:
        #                         candidates.append(u)
        #                         seen_uuids.add(u.get("uuid"))
        #         except:
        #             continue
        # except Exception as e:
        #     print(f"⚠️ Redis 查找出错: {e}")

        # # 1.2 Search Config
        # try:
        #     with open(self.config_path, 'r', encoding='utf-8') as f:
        #         config = jstyleson.load(f)
        #     for inbound in config.get("inbounds", []):
        #         for u in inbound.get("users", []):
        #             if u.get("name") == username:
        #                 if u.get("uuid") not in seen_uuids:
        #                     candidates.append(u)
        #                     seen_uuids.add(u.get("uuid"))
        # except Exception:
        #     pass
        
        # if not candidates:
        #     print(f"❌ 错误: 找不到用户 {username}")
        #     return

        # target_users = []
        # if len(candidates) == 1:
        #     target_users = [candidates[0]]
        # else:
        #     print(f"⚠️ 找到 {len(candidates)} 个名为 '{username}' 的用户:")
        #     print(f"{'序号':<5} {'UUID':<38} {'Pinyin':<20}")
        #     print("-" * 65)
        #     for i, u in enumerate(candidates):
        #         pinyin = u.get('pinyin_name', 'N/A')
        #         print(f"{i+1:<5} {u.get('uuid'):<38} {pinyin:<20}")
            
        #     choice = input("\n请输入要删除的用户序号 (支持多选如 1,3; 输入 * 删除全部; 输入 q 取消): ").strip()
        #     if choice.lower() == 'q':
        #         print("操作已取消")
        #         return
            
        #     if choice == '*':
        #         target_users = candidates
        #     else:
        #         try:
        #             # 支持中文逗号
        #             raw_indices = [int(x.strip()) - 1 for x in choice.replace('，', ',').split(',') if x.strip()]
        #             seen_indices = set()
        #             for idx in raw_indices:
        #                 if idx not in seen_indices and 0 <= idx < len(candidates):
        #                     target_users.append(candidates[idx])
        #                     seen_indices.add(idx)
        #                 elif idx not in seen_indices:
        #                     print(f"⚠️ 忽略无效序号: {idx + 1}")
        #         except ValueError:
        #             print("❌ 输入格式无效")
        #             return
            
        #     if not target_users:
        #         print("❌ 未选择任何有效用户")
        #         return

        #     # 二次确认
        #     print(f"\n即将删除以下 {len(target_users)} 个用户:")
        #     for u in target_users:
        #          print(f" - {u.get('name')} (UUID: {u.get('uuid')})")
            
        #     confirm = input("⚠️ 确定继续吗? (yes/no): ").strip().lower()
        #     if confirm != "yes":
        #         print("操作已取消")
        #         return

        # 2. 执行用户侧删除
        user = ClientManager(user_data)
        user.purge()
        # database 侧
        uuid = user_data.get("uuid")
        # 断言 uuid 绝对不能为 None，否则直接 panic 并打印后面的错误信息
        assert uuid is not None, "Panic: user_data 缺少必填的 uuid 参数！"
        db.delete_by_uuid(uuid)
    
    #先用交互式,用pinyin_name
    async def modify(self, pinyin_name: str) -> bool:

        user_data = await self.r.get(f"user:{pinyin_name}")
        user_data = json.loads(user_data) if user_data else None
        print(f"正在修改用户: {user_data}")
        if not user_data:
            logging.error(f"用户 {pinyin_name} 不存在于 Redis 中")
            return False
        #￥最优雅、最“运维范儿”的写法是使用“校验映射表（Validator Map）”
        #用dict来映射每个字段到一个专门的校验函数，这样就能把校验逻辑和交互逻辑分离开来，代码更清晰、更易维护。
        #uuid最好不要动,只动name和comment和password，修改name的话要注意pinyin_name和uuid的前4位也要跟着变。修改密码的话可以直接生成新的密码，不需要用户输入。
        for key, value in user_data.items():
            while True:
                response = input(f"是否修改{key}: {value}，[yes/no] [no]: ").strip().lower()
                if response in ["yes", "y"]:
                    new_value = input(f"请输入新的值: ")
                    
                    user_data[key] = new_value
                    break
                elif response in ["no", "n", ""]:
                    break
                else:
                    print("请输入 'yes' 或 'no'")
                    
        if not self._check_config_user_exists_with_uuid(user_data.get("uuid")):
            logging.info(f"用户 {pinyin_name} 不在配置文件中，是否启用? (yes/no) [no]: ")
        #user status
        return True
    async  def get_user_info(self,name: str) -> dict :
        db = ProxyUserDB()
        user_data = db.get_alldata_by_name(name)
        # user_data = await self._find_user_in_redis(name)
        if not user_data:
            logging.warning(f"User '{name}' not found in Redis.")
            return {}
        return user_data

# ==========================================
# 业务调用示例
# ==========================================
if __name__ == "__main__":
    # 设置基础配置
    CONFIG_PATH = "/etc/sing-box/config.json"
    BINARY_PATH = "/usr/bin/sing-box" # 建议写绝对路径，防止环境问题
    SERVICE_NAME = "sing-box.service"
    # 获取脚本所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 配置文件路径 (假设在父目录)
    # SERVER_CONFIG = os.path.join(BASE_DIR, ".", "server_config.json")
    # 模板文件路径 (假设在当前目录)
    TEMPLATE_FILE = os.path.join(BASE_DIR, "base.jsonc")
    
    # 初始化管理器
    manager = UserManager(CONFIG_PATH, TEMPLATE_FILE)
    
    if len(sys.argv) > 1:
        username = sys.argv[1]
        new_user = manager.add_user(username)
        if new_user:
            print("-" * 30)
            print("最终生成的用户信息:")
            print(json.dumps(new_user, indent=4, ensure_ascii=False))
            
            # 修改配置后重载服务
            reload_service_safely(CONFIG_PATH)
    else:
        print("用法: python main.py <用户名>")
        print("示例: python main.py 新员工_李四")
    #     print(f"{LogColors.FAIL}[ERROR] 未知错误: {e}{LogColors.ENDC}")
    #     return False
