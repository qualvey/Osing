import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

class TestServiceNode(unittest.TestCase):

    def setUp(self):
        """每个测试运行前的桩数据（Stub）准备"""
        # 1. 模拟标准的输入 user 字典
        self.user_data = {
            "name": "我",
            "tag": "wo_2094",
            "uuid": "20945af4-5be3-4338-b20a-7b49acd0bfd1",
            "password": "AiCu6lLk2iHH8VNKnb3fSg",
            "listen_port": 10004
        }
        
        # 2. 集中劫持并 Mock 外部全局变量 settings 及其各种开关
        self.patcher_settings = patch('src.Node.service.settings')
        self.mock_settings = self.patcher_settings.start()
        
        # 模拟 settings 里的基础字符串
        self.mock_settings.domain = "ssh.ryugo.org"
        self.mock_settings.transport_path = "/newbee"
        
        # 模拟 settings 内层的 Dict 结构
        self.mock_settings.transport = {"enable": True, "type": "httpupgrade"}
        self.mock_settings.reality = {
            "enable": False,
            "public_key": "_S5PE1iTZXZ2UmlmOoPEmib54zHv7zH7m9xbsA-gbBc",
            "short_id": "0123456789abcdef",
            "host": "www.baidu.com"
        }
        
        # 模拟从 config.json 捞出来的两个基础 base 骨架节点
        self.mock_settings.nodes = [
        {
            "type": "vless",
            "listen": "127.0.0.1"
        },
        {
            "type": "tuic",
            "listen": "0.0.0.0",
            "congestion_control": "bbr"
        }
        ]

    def tearDown(self):
        """测试结束，安全关闭 Mock 劫持"""
        self.patcher_settings.stop()

    def test_generate_yields_correct_protocols(self):
        """测试 1：验证生成器能够正确识别 type 并吐出两套不同的协议配置"""
        from src.Node.service import ServiceNode
        service_node = ServiceNode(self.user_data)
        
        # 💡 核心技巧：使用 list() 把 yield 出来的生成器直接转化为标准列表
        generated_configs = list(service_node.generate())
        
        # 断言 1：应该产出 2 个节点配置（一个 vless，一个 tuic）
        self.assertEqual(len(generated_configs), 2)
        
        # 断言 2：验证第一个节点是 vless，且 tag 拼接正确
        self.assertEqual(generated_configs[0]["type"], "vless")
        self.assertEqual(generated_configs[0]["tag"], "wo_2094vless")
        
        # 断言 3：验证第二个节点是 tuic，且用户密码正确注入
        self.assertEqual(generated_configs[1]["type"], "tuic")
        self.assertEqual(generated_configs[1]["tag"], "wo_2094tuic")
        self.assertEqual(generated_configs[1]["users"][0]["password"], "AiCu6lLk2iHH8VNKnb3fSg")

    def test_vless_conditional_logic(self):
        """测试 2：验证当 reality 开关关闭时，vless 配置中不会携带 reality 字段"""
        # 💡 动态调整当前测试环境下的全局开关
        self.mock_settings.reality = {"enable": False}
        
        from src.Node.service import ServiceNode

        service_node = ServiceNode(self.user_data)
        generated_configs = list(service_node.generate())
        
        vless_config = generated_configs[0]
        
        # 断言：由于 reality.enable 是 False，tls 字典里绝对不应该有 "reality" 这个 key
        self.assertNotIn("reality", vless_config["tls"])
        
    def test_init_assert_triggered_on_invalid_tag(self):
        """测试 3：防御性测试。验证如果传入的 tag 不是字符串，是否如预期那样直接抛出 AssertionError 崩溃"""
        invalid_user = self.user_data.copy()
        invalid_user["tag"] = 12345  # ❌ 故意传一个数字类型的 tag
        
        from src.Node.service import ServiceNode

        
        # 断言：实例化时必然触发 AssertionError 崩溃
        with self.assertRaises(AssertionError) as context:
            ServiceNode(invalid_user)
            
        self.assertIn("panic tag must be str", str(context.exception))

if __name__ == '__main__':
    unittest.main()