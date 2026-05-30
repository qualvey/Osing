from typing import Dict, Any
import logging
logger = logging.getLogger(__name__)
import copy
from Settings import settings
host = settings.domain
path = settings.transport_path
node_tag= settings.node_tag
#TODO 应该在这里同时产生service 和 client 双端的节点json

class ClientNode:
    def __init__(self,user_data: Dict[str, Any]):
        self.user_data = user_data
        logger.debug(f"ClientNode initialized with user_data: {self.user_data}")
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
                    "path": path,
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
                "utls": {
                    "enabled": True,
                    "fingerprint": "chrome"
                }
            }
        base["server"] = settings.firstJump
        base["tag"] = node_tag +"vless"
        
        base["server_port"] = user_data.get("listen_port")        
        base["uuid"] = user_data.get("uuid")
        base["tls"] = tls
        base["tls"]["server_name"] = host

        if settings.transport.get("enable"):
            base["transport"] = self._transport()

        if settings.reality.get("enable"):
            base["tls"]["reality"] = self._reality()
            base["tls"]["alpn"] = [
                    "http/1.1"
                ]
            base["tls"]["host"] = settings.reality.get("host")
            
        return  base
        
    def _tuic(self,base:Dict[str,Any]) -> Dict[str, Any]:
        
        """
        生成 TUIC 协议的节点配置
                {
            "type": "tuic",
            "tag": "hk-tuic",
            "server": "hk.ryugo.org",
            "server_port": 8344,
            "uuid": "cdea3bae-bee1-4d02-bad9-5312ab3b21e0",
            "password": "UteiGTvPF9YcZ25ktt2RCg",
            "congestion_control": "bbr",
            "udp_relay_mode": "native",
            "tls": {
                "enabled": true,
                "server_name": "hk.ryugo.org",
                "alpn": [
                    "h3"
                ]
            },
            "domain_resolver": "ali"
        },
        """
        tls = {
            "enabled": True,
            "alpn": [
                "h3"
            ],
            "server_name": host
        }
        user_data = self.user_data
        base["server"] = settings.firstJump
        base["server_port"] = user_data.get("listen_port")
        base["uuid"]= user_data.get("uuid")
        
        base["password"]= user_data.get("password")
        logger.debug(f"生成 TUIC 节点配置，UUID: {base['uuid']}, Password: {base['password']}")
        base["tag"] = node_tag +"tuic"
        base["udp_relay_mode"] =  "native"
        base["tls"] = tls
        base["domain_resolver"] = "ali"   
        
        return base
        
        