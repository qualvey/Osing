import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List
import os


logger = logging.getLogger(__name__)

class Setup:
    """用于读取和解析项目根目录下 JSON 配置文件的类。"""
    transport: Dict[str, Any]
    reality: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    def __init__(self, filename: str = "config.json"):
        
        self.filename = filename
        # 通过当前文件(__file__)逆向找到项目根目录
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.file_path = self.project_root / self.filename
        self._load_json()
        
        self.templates_dir = self.project_root / "templates"
        
        # 存储原始解析后的参数
        self._config_data: Dict[str, Any] = {}
        
        # 初始化时自动加载
        # 属性挂载和必填项解析完毕后，进行整体合法性校验
        self.check_settings()
        
    def check_settings(self):
        """核心校验逻辑：transport 和 reality 不能同时为 True"""
        transport = self._config_data.get("transport", {})
        reality = self._config_data.get("reality", {})
        
        transport_enabled = transport.get("enable", False)
        reality_enabled = reality.get("enable", False)
        
        if transport_enabled and reality_enabled:
            raise ValueError(
                "❌ 配置错误：'transport' 和 'reality' 不能同时启用 (enable 均为 true)。"
            )
            
    def _get_required_str(self, key: str) -> str:
        """核心工具方法：强行获取一个 str 类型的配置。如果缺失或类型不对，直接触发 Panic。"""
        val = self._config_data.get(key)
        if not isinstance(val, str):
            raise RuntimeError(
                f"🚨 CRITICAL PANIC: 配置项 '{key}' 缺失或类型错误！\n"
                f"期望类型: str, 实际获取: {type(val).__name__}"
            )
        # 防止用户在 JSON 中写了 "domain": "  example.com  " 这种带空格的值，自动帮他 trim 一下
        return val.strip()
        
    def _load_json(self) -> None:
        """读取并解析 JSON 文件。"""
        if not self.file_path.exists():
            logger.error(f"配置文件未找到: {self.file_path}")
            raise FileNotFoundError(f"Missing configuration file at {self.file_path}")

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._config_data = json.load(f)
                
                # --- 1. 核心改进：把第一层的所有配置动态挂载到实例属性上 ---
                for key, value in self._config_data.items():
                    setattr(self, key, value)
                
                # --- 2. 修正原代码中与 config.json 键名不匹配的 Bug ---
                self.domain = self._get_required_str("domain")
                
                # config.json 里是 "client_base_dir"，帮你想办法映射到了 clientBasePath
                self.client_base_dir = self._get_required_str("client_base_dir")
                self.clientBasePath = self.client_base_dir 
                
                # 默认值处理
                self.server_config_path = self._config_data.get("server_config_path") or "/etc/sing-box/config.json"
                self.enable_exlude_package = self._config_data.get("enable_exlude_package") or False
                
                # 特殊处理：原代码提取了 transport_path，但 json 里它在嵌套的 transport 内部
                transport_dict = self._config_data.get("transport", {})
                if isinstance(transport_dict, dict):
                    self.transport_path = transport_dict.get("path", "")
                else:
                    self.transport_path = ""
                
                logger.info(f"成功加载配置文件: {self.file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 格式解析失败: {e}")
            raise ValueError(f"Invalid JSON format in {self.filename}") from e

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """获取第一层参数的值。如果键不存在，返回默认值。"""
        return self._config_data.get(key, default)

    def get_nested(self, *keys: str, default: Optional[Any] = None) -> Any:
        """获取嵌套 JSON 的安全方法。"""
        current = self._config_data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @property
    def all_config(self) -> Dict[str, Any]:
        """以只读属性暴露完整的配置字典。"""
        return self._config_data

# 初始化
# 1. 获取名为 SCONFIG 的环境变量（如果不存在，默认返回 None）
sconfig_env = os.environ.get("SCONFIG")

# 2. 如果环境变量存在，将其传给配置初始化函数
if sconfig_env:
    # 假设你的 Setup 类接受这个参数
    settings = Setup(sconfig_env)
    logger.info(f"⚡ 已通过环境变量 SCONFIG 加载配置: {sconfig_env}")
    logger.debug(f"当前配置内容: {settings.domain}")
else:
    logger.info("⚡ 环境变量 SCONFIG 未设置，使用默认配置文件路径config.json")
    # 如果没有环境变量，走默认的系统路径（比如 /etc/sing-box/config.json）
    settings = Setup()