# from pydbus import SystemBus
# from gi.repository import GLib
import subprocess
from Settings import settings

binary_path =  "/usr/bin/sing-box"
service_name = "sing-box"
config_path: str = "/etc/sing-box/config.json"
 
class LogColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
# methods:
#  validate(config_path) -> (bool, str)
#  reload_service(config_path) -> bool
class ConfigChecker:
    def __init__(self):
        self.binary_path = binary_path
        self.service_name = service_name
        self.passed = False
        self.config_path = config_path
        
    def validate(self):
        """
        运行 sing-box check，捕获输出。
        返回: (bool, str) -> (是否通过, 错误信息/成功信息)
        """
        try:
            # 架构师注意：capture_output=True 是关键，我们需要拿到 stderr
            # text=True 让输出变成字符串而不是 bytes
            result = subprocess.run(
                [self.binary_path, "check", "-c", self.config_path],
                capture_output=True,
                text=True,
                check=False # 不要自动抛异常，我们要自己处理 returncode
            )

            if result.returncode == 0:
                self.passed = True
                return True, "配置校验通过"
            else:
                # 返回 stderr，因为报错信息通常在这里
                return False, result.stderr.strip()

        except FileNotFoundError:
            return False, f"找不到 sing-box 可执行文件: {self.binary_path}"
        except Exception as e:
            return False, f"执行检查时发生未知错误: {str(e)}"

    #检查配置文件是否有语法错误，然后安全地重载服务
    