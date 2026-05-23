from typing import Dict, Any
import logging
logger = logging.getLogger(__name__)
import copy
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
        base["listen_port"] = user_data.get("listen_port")
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