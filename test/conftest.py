import os
import shutil
import pytest
from Settings import settings

@pytest.fixture(scope="function")
def prepare_sandbox():
    """
    🎯 核心沙盒：专门拦截全局配置，为集成测试伪造真实硬盘战场
    """
    # 1. 拦截并保存原本的生产/开发路径
    old_db_path = settings.sqlite_db_path
    old_config_path = settings.server_config_path
    
    # 2. 强行改成测试专用的沙盒路径
    settings.sqlite_db_path = "test_proxy_users.db"
    settings.server_config_path = "test_server_config.json"
    
    # 3. 真刀真枪在硬盘上 cp 出这两个用于测试的空白母本
    # 🚨 注意：请确保你项目里有对应的母本文件，或者用 db._init_db() 凭空生成
    if os.path.exists("templates/template.db"):
        shutil.copy("templates/template.db", "test_proxy_users.db")
    else:
        # 如果没有母本，直接实例化一个新的，迫使其自动 _init_db() 吐出干净的表结构
        from database.sqlite import ProxyUserDB
        tmp = ProxyUserDB(db_path="test_proxy_users.db")
        
    shutil.copy("templates/base.jsonc", "test_server_config.json")
    
    yield  # 🚀 停在这里！控制权交给 test/integration/ 下的具体集成测试用例
    
    # 4. 勘察完“物理尸体”后，无情销毁测试期间产生的垃圾文件
    for f in ["test_proxy_users.db", "test_server_config.json"]:
        if os.path.exists(f):
            os.remove(f)
            
    # 5. 完璧归赵，把原路径还给 settings
    settings.sqlite_db_path = old_db_path
    settings.server_config_path = old_config_path