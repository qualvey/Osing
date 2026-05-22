from user_manager import UserManager
from Client import ConfigGenerator
from importlib import resources
import jstyleson
def load_template():
    # 1. 获取指向文件的“路径对象”
    # 'sing_manager' 是包名，'base.jsonc' 是文件名
    pkg_resource = resources.files("sing_manager") / "test.jsonc"
    
    # 2. 读取内容
    with pkg_resource.open("r", encoding="utf-8") as f:
        config = jstyleson.load(f)
    return config

test_config_path = '../src/test.jsonc'
