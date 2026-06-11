import os
import json
import pytest
from pathlib import Path
import jstyleson
from typing import Generator

# 导入业务组件与全局配置
from user_manager import UserManager
from database import db
from Settings import settings

# ==========================================
# 🚀 集成测试沙盒环境：依靠上一步改好的 settings.sqlite_db_path 自动隔离
# ==========================================

@pytest.fixture(autouse=True)
def integration_sandbox() -> Generator[None, None, None]:
    """
    🎯 自动沙盒夹具：为每个集成测试用例隔离开真实的生产环境。
    """
    # 1. 拦截原有的物理路径
    old_db_path = settings.sqlite_db_path
    old_config_path = settings.server_config_path
    
    # 2. 强制将上下文重定向到当前目录下的“测试沙盒”文件
    settings.sqlite_db_path = "test_run_proxy.db"
    settings.server_config_path = "test_run_server_config.json"
    
    # 3. 凭空初始化一个干净的测试数据库结构
    from database.sqlite import ProxyUserDB
    test_db_instance = ProxyUserDB(db_path=settings.sqlite_db_path)
# 3. 🌟 破案核心：不再硬编码字典，直接加载真实的 server 基础模板！
    # 请核对你的模板文件名，如果是 base.jsonc 或 server.json，在这里替换
    template_file = Path(settings.templates_dir) / "server.json" 
    
    try:
        with open(template_file, "r", encoding="utf-8") as f:
            # 使用 jstyleson 完美兼容带注释的 jsonc 模板
            base_config = jstyleson.load(f)
    except Exception as e:
        pytest.fail(f"❌ 关键致命错误：集成测试无法加载基础配置模板 [{template_file}], 错误原因: {e}")
    with open(settings.server_config_path, "w", encoding="utf-8") as f:
        json.dump(base_config, f, indent=4)
        
    yield  # 🌟 真正的集成测试用例在这里执行
    
    # 5. 测试完毕，强行打扫战场，不留任何物理垃圾
    for f in [settings.sqlite_db_path, settings.server_config_path]:
        if os.path.exists(f):
            os.remove(f)
            
    # 6. 还原 Settings 的生存路径
    settings.sqlite_db_path = old_db_path
    settings.server_config_path = old_config_path


# ==========================================
# 🧪 真正的全链路集成测试用例（无 Mock 介入）
# ==========================================

def test_new_user_save_integration():
    """
    🎯 测试点 1：验证一个全新用户调用 new() 并 save() 后，
    数据是否成功插入 SQLite，且服务端配置文件中是否真的追加了该用户。
    """
    # 1. 制造内存新用户草稿
    user = UserManager.new(name="王五", comment="全链路集成测试")
    assert user.is_persisted is False  # 落库前状态应为 False
    
    # 2. 执行真刀真枪的原子落地
    success = user.save()
    assert success is True
    assert user.is_persisted is True  # 落地后状态自动刷新为 True
    
    # 3. 物理验证 A：直接查真实的测试 SQLite 数据库，确保记录存在
    user_in_db = db.get_user_by_uuid(user.userData["uuid"])
    assert user_in_db is not None
    assert user_in_db["name"] == "王五"
    
    # 4. 物理验证 B：直接读取生成的 test_run_server_config.json，验证 sing-box 用户是否写入
    with open(settings.server_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    print(json.dumps(config))
    inbound_users = config["inbounds"][0]["users"]
    # 验证生成的密码和 UUID 是否完好地进入了物理文件
    uploaded_uuids = [u["uuid"] for u in inbound_users]
    assert user.userData["uuid"] in uploaded_uuids


def test_user_save_failure_should_rollback_files():
    """
    🎯 测试点 2：高阶事务回滚集成测试
    人为在中间步骤（比如 client.add）制造故障，验证物理文件是否真的没有被污染。
    """
    user = UserManager.new(name="赵六", comment="回滚测试")
    
    # 💥 战术破坏：利用 monkeypatch 或直接猴子补丁破坏 client.add
    # 让它在保存中途突然抛出异常，触发 UserManager 第 106 行的 except 回滚
    def broken_add():
        raise IOError("Disk crash or Network error during client config generation!")
    user.client.add = broken_add
    
    # 执行保存
    success = user.save()
    assert success is False  # 应该返回失败状态
    
    # 物理验证：即便发生崩溃，物理配置文件里也绝对不能留下赵六的残留数据（脏数据）
    with open(settings.server_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    for node in config["inbounds"]:
        users = node.get("users",[])
        # 确保 users_list 是个列表，防止模板里这个字段写成了别的东西
        if isinstance(users, list):
            # 提取出当前节点下所有用户的名字
            names_in_this_node = [u.get("name") for u in users if isinstance(u, dict)]
            
            # 🚨 核心断言：赵六的名字绝对不能出现在任何节点的名单里！
            assert "赵六" not in names_in_this_node, f"❌ 发现脏数据残留：在节点 {node.get('tag')} 里找到了赵六！"


@pytest.mark.anyio
async def test_user_disable_and_enable_lifecycle():
    """
    🎯 测试点 3：全生命周期状态切换测试
    验证 disable() 和 enable() 时，数据库标记位和服务端配置文件是否保持同步撞击。
    """
    # 1. 先安全落库一个已知用户
    user = UserManager.new(name="钱七", comment="生命周期测试")
    user.save()
    
    # 2. ⚡ 执行禁用
    user.disable()
    
    # 验证 A：数据库中对应的 enabled 标记必须变为 False（0）
    user_in_db = db.get_user_by_uuid(user.userData["uuid"])
    assert user_in_db is not None
    assert bool(user_in_db["enabled"]) is False
    
    # 验证 B：此时读取服务端文件，该用户必须已经被彻底隔离踢出

    with open(settings.server_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    for node in config["inbounds"]:
        users = node.get("users",[])
        # 确保 users_list 是个列表，防止模板里这个字段写成了别的东西
        if isinstance(users, list):
            # 提取出当前节点下所有用户的名字
            names_in_this_node = [u.get("name") for u in users if isinstance(u, dict)]
            
            # 🚨 核心断言：赵六的名字绝对不能出现在任何节点的名单里！
            assert "钱七" not in names_in_this_node, f"❌ 发现脏数据残留：在节点 {node.get('tag')} 里找到了赵六！"
    # 3. ⚡ 再次重新启用
    await user.enable()
    
    # 验证 C：数据库重新写回 True（1）
    user_in_db_revived = db.get_user_by_uuid(user.userData["uuid"])
    assert user_in_db_revived is not None
    assert bool(user_in_db_revived["enabled"]) is True
    
    # 验证 D：服务端文件再次合并，用户重新回归复活
    with open(settings.server_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    for node in config["inbounds"]:
        users = node.get("users",[])
        # 确保 users_list 是个列表，防止模板里这个字段写成了别的东西
        if isinstance(users, list):
            # 提取出当前节点下所有用户的名字
            names_in_this_node = [u.get("name") for u in users if isinstance(u, dict)]
            
            # 🚨 核心断言：赵六的名字绝对不能出现在任何节点的名单里！
            assert "钱七"  in names_in_this_node, f"❌ 发现脏数据残留：在节点 {node.get('tag')} 里找到了赵六！"