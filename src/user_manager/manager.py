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

import logging
from aioconsole import ainput
logger = logging.getLogger(__name__)

from Client import ClientManager
from  Service import UserService

from Settings import settings
domain:str  = settings.domain
transport_path = settings.transport_path

class UserNotFoundError(Exception):
    """自定义业务异常：当数据库/缓存中找不到必须存在的用户时触发"""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Critical Error: User '{name}' must exist but was not found in Redis.")

class UserManager:
    
    def _generate_credentials(self, comment: str = "") -> dict:
        #还有listen_port,怎么生成和保存
        assigned_port = self.db.get_next_available_port(start_port=10000)
        logger.debug(f"为用户 {self.name} 分配了端口: {assigned_port}")
        # 转换为拼音列表，不带声调
        py_list = pinyin(self.name, style=Style.NORMAL)
        # 扁平化并连接
        py_str = "".join([item[0] for item in py_list])
        # 只保留字母、数字和下划线，防止非法路径字符
        pinyin_name = re.sub(r'[^a-zA-Z0-9_]', '', py_str).lower()

        user_uuid = str(uuid.uuid4())
        tag = f"{pinyin_name}_{user_uuid[:4]}"
        data = {
            "name": self.name,
            "tag": tag,
            "uuid": user_uuid,
            "password": secrets.token_urlsafe(16), # 生成高强度密码
            "listen_port": assigned_port,
            "comment": comment,
            "created_at": datetime.datetime.now().isoformat()
        }
        logger.debug(f"生成的用户数据: {data}")
        return data
        
    def __init__(self, name:str, *, _from_factory: bool = False,db_instance=None):
        # 🚨 依然保留坚固的防御：禁止外部直接调用 UserManager()
        if not _from_factory:
            raise RuntimeError(
                "❌ 危险操作：禁止直接实例化 UserManager！"
                "请使用安全的工厂方法: await UserManager.bind(...) 或 await UserManager.bind_with_uuid(...)"
            )
        if db_instance is None:
            from database import db
            self.db = db
        else:
            self.db = db_instance
        # 💡 这里初始化所有的默认空白属性
        self.name: str = name

        self.userData: Dict[str, Any] = {}
        self.service: UserService
        self.client: ClientManager
        self.is_persisted: bool = False  # 顺便加上状态：是老用户还是新用户
        
    @classmethod
    def new(cls, name: str, comment: str = "", db_instance=None) -> "UserManager":
        logger.info(f"Creating new user with name: {name}")
        
        # 1. 临时建一个极简对象，仅仅为了调用内部的 _generate_credentials 算数据
        temp_instance = cls(name=name, _from_factory=True, db_instance=db_instance)
        raw_user_data = temp_instance._generate_credentials(comment=comment)
        
        # 2. 🌟 妙招：把算好的数据直接喂给 create_from_data 组装！用新变量接住它！
        instance = cls.create_from_data(raw_user_data, db_instance=db_instance)
        
        # 3. 因为是新生成的草稿，还没落库，纠正持久化状态为 False
        instance.is_persisted = False 
        
        logger.debug(f"Generated user data for {name}: {instance.userData}")
        return instance  # 返回这个被完美组装好的、带铁三角的新实例

    @classmethod
    def create_from_data( cls,user_data: dict, db_instance=None) -> "UserManager":
        name = user_data.get("name")
        if not name or not user_data.get("uuid"):
            raise ValueError("用户数据必须包含 'name' 和 'uuid' 字段")
        instance = cls(name, _from_factory=True, db_instance=db_instance)
        
        instance.userData = user_data
        instance.service = UserService(user_data)
        instance.client = ClientManager(user_data)
        instance.is_persisted = True
        
        return instance

    def perge(self):
        uuid = self.userData.get("uuid")
        assert isinstance(uuid, str), "panic"
        
        self.db.delete_by_uuid(uuid)
        self.service.purge()
        self.client.purge()
        #TODO DELETE client config and service node both
        
    def save(self):
        service_merged = False
        client_added = False
        assert self.service is not None, "ServiceManager 未初始化！"
        try:
            with self.db.transaction() as conn:
                self.db.save_inside_transaction(conn, self.userData)
                self.service.merge()
                service_merged = True
                self.client.add()
                client_added = True

            self.is_persisted = True
            logger.info(f"用户 {self.userData.get('name')} 的铁三角原子配置全线成功！")
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
        """在数据库写入禁用标记，并清理服务端配置，但不删除数据库记录，保留用户数据以备将来启用"""
        logger.info(f"Disable User {self.name}")
        uuid = self.userData.get("uuid")
        # 断言 uuid 绝对不能为 None，否则直接 panic 并打印后面的错误信息
        assert isinstance(uuid, str), "panic"
        self.db.set_user_enabled(uuid, False)
        self.service.purge()

    async def enable(self):
        """启用用户：数据库enabled写1"""
        logger.info(f"Enable User {self.name}")
        uuid = self.userData.get("uuid")
        assert isinstance(uuid, str), "panic"
        
        self.db.set_user_enabled(uuid, True)
        self.service.merge()