'''
负责sing-box服务端的配置文件管理
'''
from Settings import settings
from Node import ServiceNode
import jstyleson
import shutil
import os
import subprocess
import logging
from pathlib import Path
import signal

# from pydbus import SystemBus
# from gi.repository import GLib
logger = logging.getLogger(__name__)

domain = settings.domain
transport_path = settings.transport_path
config_path = Path(settings.server_config_path)
bak_path = config_path.with_suffix(".json.bak")
tmp_path = "/tmp/sing-box-config.json"

class UserService:
    def __init__(self,user_data: dict) -> None:
        self.user = user_data
        self.config_path = config_path
        self.node = ServiceNode(user_data)
        self.service_name = "sing-box.service"
        self.bak_path = bak_path
    
    #TODO 全新的服务器部署
    @staticmethod
    def init():
        my_bak_path = settings.project_root / "config.json.bak"
        try:
            if config_path.exists():
                shutil.copy2(config_path, my_bak_path)
                logger.info(f"📦 [Service] 已建立安全的原始配置备份: {my_bak_path}")
            else:
                pass                
        except Exception as e:
            logger.error(f"❌ [Service] 备份主配置文件失败，放弃后续操作: {e}")
            raise e # 往外抛，阻止事务继续
        
        template = settings.templates_dir / "server.json"
        config = jstyleson.load(template.open("r", encoding="utf-8"))
        provider = config.get("certificate_providers")[0]
        provider["domain"] = [domain]
        provider["default_server_name"] = domain
        provider["email"] = settings.email
        provider["dns01_challenge"]["api_token"] = settings.cloudflare_key
        logger.debug(f"Certificate provider config: {provider}")
        
        with open(tmp_path, "w", encoding="utf-8") as f:
            jstyleson.dump(config, f, indent=4, ensure_ascii=False)
        # 3. 精准提权：只在把文件搬进 /etc 的一瞬间使用 sudo
        try:
            # 这一步相当于以 root 身份执行了 mv 命令，会正常触发终端的密码输入
            subprocess.run(["sudo", "mv", tmp_path, config_path], check=True)
            
            # 顺便把服务也重启动了
            subprocess.run(["sudo", "systemctl", "restart", "sing-box"], check=True)
            print("🎉 写入并重启成功！")
            
        except subprocess.CalledProcessError:
            print("❌ 授权失败，配置未生效。")
        
        
    def merge(self):
        try:
            if self.config_path.exists():
                shutil.copy2(self.config_path, self.bak_path)
                logger.info(f"📦 [Service] 已建立安全的原始配置备份: {self.bak_path}")
            else:
                # 如果总配置文件压根不存在，直接抛错，不能继续往下
                raise FileNotFoundError(f"找不到 sing-box 主配置文件: {self.config_path}")
        except Exception as e:
            logger.error(f"❌ [Service] 备份主配置文件失败，放弃后续操作: {e}")
            raise e # 往外抛，阻止事务继续
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
                
                if config["experimental"].get("v2ray_api"):
                    config["experimental"]["v2ray_api"]["stats"]["users"].append(self.user.get("name"))
                else: 
                    v2ray_api = {
                        "listen": "127.0.0.1:8080",
                        "stats": {
                            "enabled": True,
                            "users": [
                                self.user.get("name")
                            ]
                        }
                    }
                    config["experimental"]["v2ray_api"] = v2ray_api
                    
                
                # 确保 inbounds 字典存在
            if "inbounds" not in config:
                config["inbounds"] = []
            nodes = self.node.generate()
            
            for node in nodes:
                config["inbounds"].append(node)
             # 3. 写回文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                jstyleson.dump(config, f, indent=4, ensure_ascii=False)
            self.reload()
            
            logger.info(f"✅ [Service] 服务端主配置文件已成功更新。")
            
        except Exception as e:
            logger.error(f"❌ [Service] 合并写入配置中途崩溃: {e}，正在尝试就地单线救灾...")
            # 如果在读写、解析 JSON 时崩了，立刻在内部调用自己的 rollback 先把文件换回来
            self.rollback()
            raise e # 依然要往外抛，告诉上层 UserManager：我这里挂了，请回滚数据库和客户端！
        
    def rollback(self):
        """
        供外部或内部调用的回滚方法：如果备份文件存在，瞬间还原它
        """
        logger.warning("↩️ [Service] 触发回滚流：正在尝试还原服务端主配置...")
        try:
            if self.bak_path.exists():
                # 用备份文件强行覆盖掉被污染的 config 文件
                shutil.copy(str(self.bak_path), str(self.config_path))
                logger.info("✅ [Service] 成功！服务端主配置文件已完好还原。")
            else:
                logger.warning("⚠️ [Service] 未找到备份文件，可能修改尚未开始，无需还原。")
        except Exception as e:
            logger.error(f"🚨 [Service] 致命错误：还原备份文件时失败！原因: {e}") 
            
    def purge(self):
        try:
            if self.config_path.exists():
                shutil.copy2(self.config_path, self.bak_path)
                logger.info(f"📦 [Service] 已建立安全的原始配置备份: {self.bak_path}")
            else:
                # 如果总配置文件压根不存在，直接抛错，不能继续往下
                raise FileNotFoundError(f"找不到 sing-box 主配置文件: {self.config_path}")
        except Exception as e:
            logger.error(f"❌ [Service] 备份主配置文件失败，放弃后续操作: {e}")
            raise e # 往外抛，阻止事务继续
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
            try:
                # 1. 顺藤摸瓜，拿到存储用户名的真实列表引用
                users_list = config["experimental"]["v2ray_api"]["stats"]["users"]
                username_to_remove = self.user.get("name")
                # 2. 确保它确实是个列表，且我们要删的用户确实在里面
                if isinstance(users_list, list) and username_to_remove in users_list:
                    # 核心反操作：只保留不等于当前用户名的元素（相当于把它彻底过滤掉）
                    config["experimental"]["v2ray_api"]["stats"]["users"] = [
                        user for user in users_list if user != username_to_remove
                    ]
                    logger.info(f"✂️ [Service] 成功从 API 统计中踢除用户: {username_to_remove}")
            except KeyError:
                # 如果主配置里压根没有配置 experimental、v2ray_api 或者 stats
                # 说明该用户的统计项本来就不存在，温柔略过，不需要报错破坏流水线
                logger.warning("⚠️ [Service] 服务端配置中未发现 experimental.v2ray_api 统计节点，无需清理")
                pass
                
                # 确保 inbounds 字典存在
            if "inbounds" not in config:
                config["inbounds"] = []
            nodes = self.node.generate()
            user_tags_blacklist = {node.get("tag") for node in nodes if node.get("tag")}
            logger.info(f"🔍 [Service] 该用户拥有的全部 Tag 标签: {user_tags_blacklist}")
            # 3. 走出节点循环，只对 inbounds 进行【一次性】精准清洗
            if "inbounds" in config and isinstance(config["inbounds"], list):
                orig_len = len(config["inbounds"])
                
                # 核心行：只要 inbound 的 tag 在黑名单里，就直接剔除
                config["inbounds"] = [
                    inbound for inbound in config["inbounds"]
                    if inbound.get("tag") not in user_tags_blacklist
                ]
                
                logger.info(f"✂️ [Service] 过滤完成，从 inbound 中清除了 {orig_len - len(config['inbounds'])} 个该用户的节点")
             # 3. 写回文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                jstyleson.dump(config, f, indent=4, ensure_ascii=False)
            logger.info(f"✅ [Service] 服务端主配置文件已成功更新。")
            self.reload()
        except Exception as e:
            logger.error(f"❌ [Service] 合并写入配置中途崩溃: {e}，正在尝试就地单线救灾...")
            # 如果在读写、解析 JSON 时崩了，立刻在内部调用自己的 rollback 先把文件换回来
            self.rollback()
            raise e # 依然要往外抛，告诉上层 UserManager：我这里挂了，请回滚数据库和客户端！
        
    def _remove_from_config_file(self, target_uuid: str):
        """内部方法：从 config.json 移除用户 (根据 UUID)"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
            
            found = False
            for inbound in config.get("inbounds", []):
                if inbound.get("type") == "tuic":
                    users = inbound.get("users", [])
                    original_count = len(users)
                    # 过滤掉该用户
                    inbound["users"] = [u for u in users if u.get("uuid") != target_uuid]
                    if len(inbound["users"]) < original_count:
                        found = True
                        break
            
            if found:
                # 备份
                try:
                    shutil.copy2(self.config_path, f"{self.config_path}.bak")
                except Exception as e:
                    print(f"⚠️ 备份失败: {e}")

                # 写入
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    jstyleson.dump(config, f, indent=4, ensure_ascii=False)
                print(f"✅ 配置文件已更新: UUID {target_uuid} 已移除")
            else:
                print(f"⚠️ 配置文件中未找到 UUID {target_uuid}")

        except Exception as e:
            print(f"❌ 修改配置文件失败: {e}")
            
    def _find_user_in_config(self, username: str) -> dict | None:
        """内部方法：在 config.json 中查找用户信息"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
            for inbound in config.get("inbounds", []):
                if inbound.get("type") == "tuic":
                    for u in inbound.get("users", []):
                        if u.get("name") == username:
                            return u
        except Exception:
            pass
        return None

    def validate_config(self):
        """
        运行 sing-box check，捕获输出。
        返回: (bool, str) -> (是否通过, 错误信息/成功信息)
        """
        try:
            # 架构师注意：capture_output=True 是关键，我们需要拿到 stderr
            # text=True 让输出变成字符串而不是 bytes
            result = subprocess.run(
                ["sing-box", "check", "-c", self.config_path],
                capture_output=True,
                text=True,
                check=False # 不要自动抛异常，我们要自己处理 returncode
            )

            if result.returncode == 0:
                return True, "配置校验通过"
            else:
                # 返回 stderr，因为报错信息通常在这里
                return False, result.stderr.strip()

        except FileNotFoundError:
            return False, f"找不到 sing-box 可执行文件:"
        except Exception as e:
            return False, f"执行检查时发生未知错误: {str(e)}"

        #检查配置文件是否有语法错误，然后安全地重载服务
        
    def reload(self):
        # 1. 严格校验
        valid = self.validate_config()
        if not valid:
            logger.warning("[Reload] 新配置校验失败，正在启动回滚流程...")
            self.rollback()
            # 🎯 核心修复：校验失败并回滚后，必须立刻中断，阻止后面的重载动作！
            return False

        # 2. 核心重载
        try:
            # 🎯 步骤 A：直接通过 pgrep 获取 sing-box 的最老主进程 PID (-o 代表 earliest 进程)
            # 这样可以 100% 避开 systemd 的内部状态卡死问题
            pid_process = subprocess.run(
                ["pgrep", "-o", "sing-box"],
                capture_output=True,
                text=True
            )
            
            if pid_process.returncode == 0 and pid_process.stdout.strip():
                pid = int(pid_process.stdout.strip())
                
                # 🎯 步骤 B：直接向进程发送 SIGHUP (等同于 kill -HUP <PID>)
                # sing-box 收到这个原生信号会立刻在内部平滑热重载配置，Systemd 连拦截的机会都没有
                os.kill(pid, signal.SIGHUP)
                logger.info(f"[Success] 绕过 Systemd 状态机，成功通过原生 SIGHUP 信号热重载进程 (PID: {pid})！")
                return True
                
            else:
                # 🎯 步骤 C：如果系统里连进程都没找到，说明真的没开，直接冷启动
                logger.warning("[Reload] 进程不存在，执行冷启动...")
                subprocess.run(
                    ["sudo", "systemctl", "start", "sing-box"],
                    check=True, capture_output=True, text=True
                )
                logger.info("[Success] sing-box 服务已成功全新冷启动！")
                return True
            
        except subprocess.CalledProcessError as e:
            # 1. 记录底层错误
            logger.error(f"[Panic] sing-box 重载命令执行失败！错误码: {e.returncode}")
            logger.error(f"[Detail] 错误详情: {e.stderr.strip()}")
            
            # 2. 本地尽力回滚配置文件，防止脏配置留在硬盘上
            logger.warning("[Panic] 正在尝试回滚至上一个稳定配置...")
            try:
                self.rollback()
            except Exception as rollback_err:
                logger.critical(f"[Fatal] 硬盘配置回滚也失败了！: {str(rollback_err)}")
            
            # 🎯 3. 核心修复：绝对不要 return False！直接向上抛出自定义异常（或者原样抛出）
            # from e 可以保持完整的错误堆栈追踪，上层事务感知到异常后会自动 ROLLBACK 数据库
            raise RuntimeError("sing-box 服务热重载遭遇致命失败，上层业务必须中断并回滚事务！") from e
            
        except Exception as e:
            # 捕获可能出现的系统级异常（例如：sudo 权限没了、没装 systemctl、甚至内存溢出等）
            logger.critical(f"[System Error] 遭遇非预期的系统级故障: {str(e)}")
            return False

if __name__ == "__main__":
    logger.info("正在测试 ServiceManager 的配置校验和重载功能...")