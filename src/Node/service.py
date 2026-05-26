from typing import Dict, Any
import logging
logger = logging.getLogger(__name__)
import copy
import socket
from Settings import settings
host = settings.domain

#TODO 应该在这里同时产生service 和 client 双端的节点json

class ServiceNode:
    def __init__(self,user_data: Dict[str, Any]):
        self.user_data = user_data
        # 这里可以存放一些全局默认配置，如果需要的话
        # 🛡️ 甚至可以在这里顺手做一层强类型安全保障，后面拼接时 Pylance 绝对不报红线
        tag_val = user_data.get("tag")
        assert isinstance(tag_val, str), "panic tag must be str"
        self.tag: str = tag_val
        
    def generate(self):
        nodes = copy.deepcopy(settings.nodes)
        for node in nodes:
            if node.get("type") == "vless":
                yield self._vless(node)
            if node.get("type") == "tuic":
                yield self._tuic(node)
                
    def _get_available_port(self, raw_port) -> int:
        """获取 8000-10000 之间且未被占用的端口"""
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            # 如果原始值不是合法数字，默认从 8000 开始找
            port = 8000

        # 1. 如果大于 10000，将其映射到 8000-10000 之间
        if port > 10000:
            # 方案 A（确定性映射）：利用取模，让大端口均匀分布在 8000-10000 之间
            port = 8000 + (port % 2001)  # 2001 是因为 10000 - 8000 + 1
            
            # 方案 B（随机映射）：如果你更倾向于随机分配，可以解开下方注释
            # port = random.randint(8000, 10000)

        # 如果调整后的端口小于 8000，也强制拉回 8000
        if port < 8000:
            port = 8000

        # 2. 循环检查端口是否被占用，如果被占用则递增查找
        start_port = port
        while self._is_port_in_use(port):
            port += 1
            if port > 10000:
                port = 8000  # 如果超出范围，绕回 8000 继续找
                
            # 死循环保护：如果 8000-10000 全部被占满了，触发异常
            if port == start_port:
                raise RuntimeError("🚨 CRITICAL PANIC: 8000-10000 之间的所有端口已被占满！")

        return port
    
    def _is_port_in_use(self,port: int) -> bool:
        """检查本地端口是否已被监听"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # try to bind to the port; if it fails, the port is in use
            return s.connect_ex(('127.0.0.1', port)) == 0

        
    def _reality(self):
        return       {
                    "enabled": True,
                    "public_key": "_S5PE1iTZXZ2UmlmOoPEmib54zHv7zH7m9xbsA-gbBc",
                    "short_id": "0123456789abcdef"
                }
  
    def _transport(self):
        if settings.transport.get("type") == "httpupgrade":
            return  {
                    "type": "httpupgrade",
                    "host": host,
                    "path": self.user_data.get("tag"),
                    "headers": {
                        "Server": "apache",
                        "X-Content-Type-Options": "nosniff"
                    }
                }
            
    def _vless(self,base:Dict[str,Any]) -> Dict:
        """
        生成 VLESS 协议的节点配置
        """
        user_data = self.user_data
        tls = {
            "enabled": True,
            "server_name": host
        }
        users = [
            {
            "name": user_data.get("name"),
            "uuid": user_data.get("uuid")
            }
        ]
        base["tag"] = self.tag+"vless"
        base["listen_port"] = self._get_available_port(self.user_data.get("listen_port"))
        base["users"] = users
        base["tls"] = tls

        if settings.transport.get("enable"):
            base["listen"] = "127.0.0.1"
            
            base["transport"] = self._transport()
            base["tls"]["certificate_provider"] = settings.certificate_provider
            logger.debug("Making transport enabled")
            

        if settings.reality.get("enable"):
            base["listen"] = "0.0.0.0"
            
            base["tls"]["reality"] = self._reality()
            base["tls"]["alpn"] = [
                    "http/1.1"
                ]
            base["tls"]["host"] = settings.reality.get("host")
            
        return  base
        
    def _tuic(self,base:Dict[str,Any]) -> Dict[str, Any]:
        """
        生成 TUIC 协议的节点配置
                    "tls": {
                "enabled": true,
                "alpn": [
                    "h3"
                ],
                "certificate_provider": "letsencrypt",
                "ech": {
                    "enabled": true,
                    "key": [
                        "-----BEGIN ECH KEYS-----",
                        "ACAPIRG89ufWACOTOrydfByA1Z1mFpsC9Vhm1qTTVTbg5wBJ/g0ARQAAIAAgjPnr",
                        "ClvBoabXh2upBJxuI5NzfDh7GIP9yH/sy14yBiIADAABAAEAAQACAAEAAwAOZmx5",
                        "Lndvd29oYS50b3AAAA==",
                        "-----END ECH KEYS-----"
                    ]
                }
            }
        one_port
        dependent port
        """
        user_data = self.user_data
        user = {
            "name": user_data.get("name"),
            "uuid": user_data.get("uuid"),
            "password": user_data.get("password")
        }
        tls = {
            "enabled": True,
            "alpn": [
                "h3"
            ],
            "certificate_provider": "letsencrypt"
        }
        base["listen"] = "0.0.0.0"
        
        base["tag"] = self.tag+"tuic"
        base["listen_port"] = user_data.get("listen_port")
        base["users"] = [user]
        base["tls"] = tls
        
        return base