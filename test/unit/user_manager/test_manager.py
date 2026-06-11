# from user_manager import UserManager
# from database import ProxyUserDB

# name = "你好"
# db = ProxyUserDB('test.db')
# user = UserManager.new(name,db)
# user.save

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Any

# 导入你的业务类（请根据实际目录调整 import 路径）
from user_manager import UserManager

# ==========================================
# 🎁 Fixtures (测试夹具)：专门用来制造测试所需的假环境
# ==========================================

@pytest.fixture
def mock_db():
    """制造一个完全受控的虚拟数据库实例"""
    db_instance = MagicMock()
    # 模拟事务上下文管理器
    db_instance.transaction.return_value.__enter__ = MagicMock(return_value="fake_conn")
    db_instance.transaction.return_value.__exit__ = MagicMock(return_value=None)
    return db_instance

@pytest.fixture
def fake_user_data() -> Dict[str, Any]:
    """制造一份标准的合法老用户字典"""
    return {
        "name": "张三",
        "uuid": "7f8a9b0c-1234-5678-abcd-ef1234567890",
        "tag": "zhangsan_7f8a",
        "password": "secure_password_123",
        "listen_port": 10086,
        "comment": "测试备注"
    }

# ==========================================
# 🧪 正式测试用例
# ==========================================

def test_user_manager_new_factory_should_init_triangle(mock_db):
    """
    🎯 测试点 1：验证 UserManager.new() 是否能正确初始化纯内存的“铁三角”组件
    并且确保它的 is_persisted 状态为 False（草稿状态）
    """
    # 模拟数据库端口分配方法
    mock_db.get_next_available_port.return_value = 12345
    
    # 执行要测试的方法
    user = UserManager.new(name="李四", comment="新员工", db_instance=mock_db)
    
    # 验证与断言
    assert user is not None
    assert user.name == "李四"
    assert user.is_persisted is False  # 草稿不应该算作已持久化
    assert user.userData["listen_port"] == 12345
    
    # 核心：验证铁三角组件是否在内部被顺利 new 出来了
    assert user.service is not None
    assert user.client is not None


def test_user_save_transaction_failure_should_rollback(mock_db, fake_user_data):
    """
    🎯 测试点 2：极其关键的“铁三角原子性保存”测试
    验证当底层组件（如 ClientManager）添加失败时，系统是否会触发 purge 物理文件清理
    """
    # 1. 灌入老数据生成用户实例
    user = UserManager.create_from_data(fake_user_data, db_instance=mock_db)
    
    # 2. 把铁三角组件拦截并换成我们的 Mock
    user.service = MagicMock()
    user.client = MagicMock()
    
    # 3. 故意让外部文件写入（client.add）抛出严重异常（例如磁盘满了）
    user.client.add.side_effect = Exception("Disk Full: 磁盘空间不足，物理文件写入失败！")
    
    # 4. 执行保存动作
    save_result = user.save()
    
    # 5. 见证奇迹的断言
    assert save_result is False  # save() 必须向外界返回 False，表示保存失败
    
    # 核心保障：即使崩了，也必须调用底层 client.purge() 把刚刚建了一半的垃圾文件夹给“扬了”
    user.client.purge.assert_called_once()
    # 核心保障：必须调用数据内层事务方法保存了数据
    mock_db.save_inside_transaction.assert_called_once()


def test_user_disable_logic(mock_db, fake_user_data):
    """
    🎯 测试点 3：测试禁用逻辑
    验证调用 disable 时，是否能在切断配置文件的同时，正确更新数据库内的标记
    """
    # 1. 组装用户
    user = UserManager.create_from_data(fake_user_data, db_instance=mock_db)
    user.service = MagicMock()
    
    # 2. 执行禁用
    user.disable()
    
    # 3. 断言
    # 验证底层数据库对应的 set_user_enabled 方法被调用，且传入了正确的参数
    user.db.set_user_enabled.assert_called_once_with(fake_user_data["uuid"], False)
    # 验证服务配置文件（sing-box inbound）被无情刷新并清理掉了
    user.service.purge.assert_called_once()