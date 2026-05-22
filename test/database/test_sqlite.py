import pytest
import json
import sqlite3
import os
from database.sqlite import ProxyUserDB

MOCK_USERS_DATA = [
    {
        'name': '民', 
        'tag': 'min_c775', 
        'uuid': 'c7753614-fb38-4e0d-8fdf-2ea5fb8d362f', 
        'password': 'v_dGg4Ycw_6oUUaYlPJlGA', 
        'listen_port': 10000, 
        'comment': '', 
        'enabled': True, 
        
        'created_at': '2026-05-19T20:40:55.566756'
    },
        {
        'name': '工', 
        'tag': 'aa_c775', 
        'uuid': 'c7753914-fb38-4e0d-8fdf-2ea5fb8d362f', 
        'password': 'v_dGg4Ycw_6oUUaYlPJlGA', 
        'listen_port': 10800, 
        'comment': '', 
        'enabled': True, 
    
        'created_at': '2026-05-19T20:40:55.566756'
    }
]

@pytest.fixture
def db_session(tmp_path):
    """
    不跳过任何逻辑，跑完全套业务代码初始化。
    如果遇到隐式回滚，这里会直接捕获并打印核心元凶！
    """
    test_db_file = tmp_path / "full_integration_test.db"
    db_path_str = str(test_db_file)
    
    # 1. 尝试完整运行业务的 __init__ 和 _init_db
    try:
        db = ProxyUserDB(db_path=db_path_str)
    except Exception as e:
        print(f"\n❌ [初始化阶段崩溃] 你的 _init_db 内部报错了: {repr(e)}")
        raise e
        
    # 2. 如果初始化没崩，但表还是没了，说明发生了隐式回滚。
    # 我们直接连进去自检，看看到底卡在什么状态
    with sqlite3.connect(db_path_str) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\n🔍 [自检] 此时数据库内实际存在的表: {tables}")
        
        # 3. 如果表在，我们再亲手把测试数据灌进去
        if ('users',) in tables:
            for user in MOCK_USERS_DATA:
                cursor.execute(
                    """
                    INSERT INTO users (uuid, name, tag, password, listen_port, comment, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user['uuid'], user['name'], user['tag'], user['password'],
                        user['listen_port'], user['comment'], user['created_at']
                    )
                )
            conn.commit()
            
    return db


def test_get_all_users_full_flow(db_session):
    """全流程集成测试：验证真实建表、自检、注入数据、最终读取的闭环"""
    result = db_session.get_all_users()
    assert len(result) == 2
    assert result[0]['name'] == '民'
    assert result[1]['name'] == '工'