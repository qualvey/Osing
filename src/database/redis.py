import json
import shutil
import logging
import datetime
from typing import Optional, List, Dict, Any
import redis.asyncio as aioredis  # 使用异步 Redis 库
import jstyleson

# 配置基本的日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RedisProxyDB:
    def __init__(
        self, 
        config_path: str = "config.json", 
        redis_url: str = "redis://127.0.0.1:6379/0"
    ) -> None:
        self.config_path = config_path
        # 初始化异步 Redis 客户端，设置 decode_responses=True 避免繁琐的 bytes.decode()
        self.r = aioredis.from_url(redis_url, decode_responses=True)


    async def _sync_to_redis(self, user_data: dict) -> None:
        """内部方法：将数据同步到 Redis (利用 Pipeline 实现事务语义)"""
        uuid_str = user_data.get('uuid')
        pinyin_name = user_data.get('pinyin_name')
        real_name = user_data.get('name')

        auth_key = f"token:{uuid_str}"
        info_key = f"user:{pinyin_name}"
        index_key = "idx:name_to_pinyin"  # 用于解决 name -> alldata 高效查询的辅助索引

        try:
            logging.info(f"🔄 正在同步用户到 Redis: {real_name} (UUID: {uuid_str})")
            
            # 使用异步管道，减少网络 RTT 延迟，接近事务原子性
            async with self.r.pipeline(transaction=True) as pipe:
                # 1. 鉴权索引: UUID -> PinyinName (用于鉴权脚本 O(1) 快速响应)
                pipe.set(auth_key, pinyin_name)
                # 2. 用户详情: PinyinName -> Full Info
                pipe.set(info_key, json.dumps(user_data, ensure_ascii=False))
                # 3. 辅助索引: 建立 RealName -> PinyinName 的映射，告别遍历 scan
                pipe.hset(index_key, real_name, pinyin_name)
                
                await pipe.execute()
                
            logging.info(f"✅ Redis 同步完成: {real_name}")
        except Exception as e:
            logging.error(f"❌ Redis 同步失败: {e}")
            raise e

    async def _find_user_in_redis(self, username: str) -> Optional[dict]:
        """通过真实姓名直接定位全量数据 (已优化为 O(1) 复杂度)"""
        try:
            # 1. 先从哈希索引中一步到位拿到对应的拼音后缀名
            pinyin_name = await self.r.hget("idx:name_to_pinyin", username)
            if not pinyin_name:
                return None
                
            # 2. 直接获取详情数据
            data = await self.r.get(f"user:{pinyin_name}")
            return json.loads(data) if data else None
        except Exception as e:
            logging.error(f"❌ Redis 用户查询失败 [{username}]: {e}")
            return None

    async def get_all_user_data(self) -> List[dict]:
        """获取所有用户数据，包含 Redis 中的所有活跃用户"""
        all_users = []
        try:
            # 遍历所有 user:* 键
            async for key in self.r.scan_iter("user:*"):
                try:
                    val = await self.r.get(key)
                    if val:
                        all_users.append(json.loads(str(val)))
                except Exception as val_err:
                    logging.warning(f"⚠️ 解析单个用户数据失败, Key: {key}, Error: {val_err}")
                    continue
        except Exception as e:
            logging.error(f"❌ 批量读取 Redis 数据失败: {e}")
        return all_users

    def tuic_update(self, config: dict, user_data: dict) -> None:
        """待实现的 tuic 配置更新逻辑"""
        # TODO: 根据你的 config 格式，将 user_data 注入到 tuic 入站中
        pass

    def vless_update(self, config: dict, user_data: dict) -> None:
        """待实现的 vless 配置更新逻辑"""
        # TODO: 根据你的 config 格式，将 user_data 注入到 vless 入站中
        pass

    async def sync_from_redis(self) -> None:
        """从 Redis 读取所有用户并刷新回本地 config.json 配置文件 (附带安全备份)"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
        except FileNotFoundError:
            logging.error(f"❌ 错误: 找不到配置文件 {self.config_path}")
            return
        except Exception as e:
            logging.error(f"❌ 读取/解析配置文件失败: {e}")
            return

        # 从 Redis 获取全量数据
        user_infos = await self.get_all_user_data()
        if not user_infos:
            logging.warning("⚠️ Redis 中未发现任何用户数据，跳过配置更新。")
            return

        # 更新配置树
        for user in user_infos:
            self.tuic_update(config, user)
            self.vless_update(config, user)

        # 触发安全备份
        try:
            shutil.copy2(self.config_path, f"{self.config_path}.bak")
            logging.info(f"📦 已安全备份配置文件至: {self.config_path}.bak")
        except Exception as e:
            logging.warning(f"⚠️ 备份原文件失败 (仍将尝试写入新配置): {e}")

        # 写回文件
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                jstyleson.dump(config, f, indent=4, ensure_ascii=False)
            logging.info(f"✅ 配置文件成功与 Redis 同步更新: {self.config_path}")
        except Exception as e:
            logging.error(f"❌ 写入新配置文件失败: {e}")

    async def sync_config_2_redis(self, data: dict) -> None:
        """将配置文件中的单条用户数据规范化并同步到 Redis，适用于重启后状态恢复"""
        username = data.get("name")
        if not isinstance(username, str):
            raise TypeError(f"Expected string for 'name', got {type(username).__name__}")
            
        user_uuid = data.get("uuid")
        if not isinstance(user_uuid, str):
            raise TypeError(f"Expected string for 'uuid', got {type(user_uuid).__name__}")

        # 生成规范化的全局唯一拼音后缀标识
        base_pinyin = self._to_pinyin(username)
        pinyin_name = f"{base_pinyin}_{user_uuid[:4]}"

        # 重新打包，确保写入 Redis 的数据结构严谨、统一
        user_data = {
            "name": username,
            "pinyin_name": pinyin_name,
            "uuid": user_uuid,
            "password": data.get("password"),
            "comment": data.get("comment", ""),
            "created_at": data.get("created_at", datetime.datetime.now().isoformat())
        }
        
        await self._sync_to_redis(user_data)

    async def close(self) -> None:
        """关闭连接，释放 Redis 资源"""
        await self.r.close()