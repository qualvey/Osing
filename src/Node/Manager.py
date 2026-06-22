from .service import Vlesst,UserContext
from Settings import settings
from database import db

config , ctx = settings.config,settings.ctx
vless_config  = config.vless_nodes


class NodeManager:
    def __int__(self):
        self.vless_node = Vlesst(vless_config)
    
    def vlesst(self, name: str):
        user_data = db.get_all_users_by_name(name)
        user_data = user_data[0]
        user = UserContext(user_data)
        return self.vless_node.new(user)
        