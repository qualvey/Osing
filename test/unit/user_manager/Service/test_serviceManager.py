


# import unittest
# from unittest.mock import patch, mock_open, MagicMock
# from pathlib import Path


# class TestUserService(unittest.TestCase):

#     def setUp(self):
#         """每个测试用例执行前的初始化"""
#         self.user_data  = {
#             "name": "我",
#             "tag": "wo_2094",
#             "uuid": "20945af4-5be3-4338-b20a-7b49acd0bfd1",
#             "password": "AiCu6lLk2iHH8VNKnb3fSg",
#             "listen_port": 10004,
#             "comment": "",
#             "created_at": "2026-05-21T18:41:43.359066"
# }
        
#         # 💡 模拟全局 settings 对象，防止它去读真实的路径
#         self.patcher_settings = patch('service.settings') # 替换为实际导入 settings 的模块名
#         self.mock_settings = self.patcher_settings.start()
#         self.mock_settings.server_config_path = "/fake/path/config.json"
        
#         # 💡 模拟 ServiceNode 及其 generate 方法
#         self.patcher_node = patch('service.ServiceNode')
#         self.mock_node_cls = self.patcher_node.start()
#         self.mock_node_instance = MagicMock()
#         self.mock_node_cls.return_value = self.mock_node_instance
        
#         # 让 generate() 返回一个模拟的生成器，产出一个节点配置字典
#         self.mock_node_instance.generate.return_value = [
#             {"type": "vless", "tag": "vless_node"}
#         ]

#     def tearDown(self):
#         """每个测试用例执行后的清理，释放 mock 状态"""
#         self.patcher_settings.stop()
#         self.patcher_node.stop()

#     @patch('service.shutil.copy2')
#     @patch('service.jstyleson')
#     def test_merge_success(self, mock_jstyleson, mock_copy2):
#         """测试用例 1：成功读取、备份并写入配置文件的完整流程"""
        
#         # 1. 准备：模拟原始的 sing-box 配置 JSON
#         fake_initial_config = {"inbounds": [], "outbounds": []}
#         mock_jstyleson.load.return_value = fake_initial_config

#         # 2. 模拟文件读取与写入的核心：使用 mock_open 拦截内置 open
#         # read_data 模拟读出来的空内容，因为我们已经 mock 了 jstyleson.load，所以这里只作为文件句柄
#         m_open = mock_open(read_data="{}")
        
#         with patch('builtins.open', m_open):
#             from service import UserService
#             service = UserService(self.user_data)
#             service.merge()

#         # 3. 断言（Assert）：验证关键的工程流是否被正确触发执行
        
#         # 验证是否正确打开了我们指定的伪造路径
#         m_open.assert_any_call("/fake/path/config.json", 'r', encoding='utf-8')
#         m_open.assert_any_call("/fake/path/config.json", 'w', encoding='utf-8')
        
#         # 验证备份动作是否带着正确参数执行了
#         mock_copy2.assert_called_once_with(
#             "/fake/path/config.json", 
#             "/fake/path/config.json.bak"
#         )
        
#         # 验证最终写回的动作是否被触发
#         mock_jstyleson.dump.assert_called_once()

#     @patch('builtins.open', side_effect=FileNotFoundError)
#     def test_merge_file_not_found(self, mock_open_err):
#         """测试用例 2：当配置文件不存在时，应该优雅打印错误并中断，不触发备份"""
#         from Service import UserService
        
#         # 拦截控制台输出，验证用户是否看到了 ❌ 错误提示
#         with patch('builtins.print') as mock_print:
#             service = UserService(self.user_data)
#             service.merge()
            
#             # 断言：第一行打印出来的东西包含错误提示
#             mock_print.assert_any_call("❌ 错误: 找不到配置文件 /fake/path/config.json")

# if __name__ == '__main__':
#     unittest.main()