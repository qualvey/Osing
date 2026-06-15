import logging
from pathlib import Path
import json_repair
from typing import Dict, List, Optional
from pydantic import BaseModel,model_validator, Field
from dataclasses import dataclass
logger = logging.getLogger(__name__)


@dataclass
class RuntimeContext:
    project_root: Path
    template_dir: Path
    db_path: str = "user.db"
    
class TransportConfig(BaseModel):
    enable: bool
    path: str

class RealityConfig(BaseModel):
    enable: bool
    
class Node(BaseModel):
    type: str
    congestion_control: Optional[str] = None

class Server(BaseModel):
    domain: str
    node_tag: str
    email: str
    certificate_provider: str
    cf_key: str
    config_path: str = "/etc/sing-box/config.json"

class Client(BaseModel):
    client_path: str
    enable_exlude_package: bool = False
    
class Config(BaseModel):
    server: Server
    client: Client
    nodes: list[Node] = Field(
        default_factory=list
    )
    @model_validator(mode="after")
    def validate_settings(self):

        return self

'''

'''
from pathlib import Path
import json_repair

def load_config(filename: str = "config.json") -> tuple[Config,RuntimeContext]:

    project_root = Path(__file__).resolve().parent.parent.parent
    template_dir = project_root /"templates"

    file_path = project_root / filename
    with open(file_path, "r", encoding="utf-8") as f:
        data = json_repair.load(f)

    config = Config.model_validate(data)
    ctx = RuntimeContext(
        project_root=project_root,
        template_dir=template_dir
    )

    return config,ctx
class Settings:
    def __init__(self, config: Config, ctx: RuntimeContext):
        self.config = config
        self.ctx = ctx
        
config , ctx = load_config()
settings = Settings(config, ctx)
__all__ = ['settings']

# class Setup:
#     """用于读取和解析项目根目录下 JSON 配置文件的类。"""
#     transport: Dict[str, Any]
#     reality: Dict[str, Any]
#     nodes: List[Dict[str, Any]]
    
#     def __init__(self, filename: str = "config.json"):
        
#         self.filename = filename
#         # 通过当前文件(__file__)逆向找到项目根目录
#         self.project_root = Path(__file__).resolve().parent.parent.parent
#         self.file_path = self.project_root / self.filename
#         self._load_json()
        
#         self.templates_dir = self.project_root / "templates"
        
#         # 存储原始解析后的参数
#         self._config_data: Dict[str, Any] = {}
#         self.sqlite_db_path = "user.db"

#         # 初始化时自动加载
#         # 属性挂载和必填项解析完毕后，进行整体合法性校验
#         self.check_settings()
        
#     def check_settings(self):
#         """核心校验逻辑：transport 和 reality 不能同时为 True"""
#         transport = self._config_data.get("transport", {})
#         reality = self._config_data.get("reality", {})
        
#         transport_enabled = transport.get("enable", False)
#         reality_enabled = reality.get("enable", False)
        
#         if transport_enabled and reality_enabled:
#             raise ValueError(
#                 "❌ 配置错误：'transport' 和 'reality' 不能同时启用 (enable 均为 true)。"
#             )
            
#     def _get_required_str(self, key: str) -> str:
#         """核心工具方法：强行获取一个 str 类型的配置。如果缺失或类型不对，直接触发 Panic。"""
#         val = self._config_data.get(key)
#         if not isinstance(val, str):
#             raise RuntimeError(
#                 f"🚨 CRITICAL PANIC: 配置项 '{key}' 缺失或类型错误！\n"
#                 f"期望类型: str, 实际获取: {type(val).__name__}"
#             )
#         # 防止用户在 JSON 中写了 "domain": "  example.com  " 这种带空格的值，自动帮他 trim 一下
#         return val.strip()
        
#     def _load_json(self) -> None:
#         """读取并解析 JSON 文件。"""
#         if not self.file_path.exists():
#             logger.error(f"配置文件未找到: {self.file_path}")
#             raise FileNotFoundError(f"Missing configuration file at {self.file_path}")

#         try:
#             with open(self.file_path, "r", encoding="utf-8") as f:
#                 parsed_data = json_repair.load(f)
        
#                 # 2. 显式类型检查（Pylance 看到这里会自动将类型收窄为 dict）
#                 if not isinstance(parsed_data, dict):
#                     raise TypeError(
#                         f"🚨 配置解析错误：预期根节点为 JSON 对象(dict)，"
#                         f"实际解析得到了: {type(parsed_data).__name__}"
#                     )
#                 self._config_data = parsed_data  # 存储原始解析结果
                
#                 # --- 1. 核心改进：把第一层的所有配置动态挂载到实例属性上 ---
#                 for key, value in parsed_data.items():
#                     setattr(self, key, value)
                
#                 # --- 2. 修正原代码中与 config.json 键名不匹配的 Bug ---
#                 self.domain = self._get_required_str("domain")
                
#                 # config.json 里是 "client_base_dir"，帮你想办法映射到了 clientBasePath
#                 self.client_base_dir = self._get_required_str("client_base_dir")
#                 self.clientBasePath = self.client_base_dir 
                
#                 # 默认值处理
#                 self.server_config_path = self._config_data.get("server_config_path") or "/etc/sing-box/config.json"
#                 self.enable_exlude_package = self._config_data.get("enable_exlude_package") or False
#                 self.sqlite_db_path = self._config_data.get("sqlite_db_path")
#                 # 特殊处理：原代码提取了 transport_path，但 json 里它在嵌套的 transport 内部
#                 transport_dict = self._config_data.get("transport", {})
#                 if isinstance(transport_dict, dict):
#                     self.transport_path = transport_dict.get("path", "")
#                 else:
#                     self.transport_path = ""
                
#                 logger.info(f"成功加载配置文件: {self.file_path}")
#         except json.JSONDecodeError as e:
#             logger.error(f"JSON 格式解析失败: {e}")
#             raise ValueError(f"Invalid JSON format in {self.filename}") from e

#     def get(self, key: str, default: Optional[Any] = None) -> Any:
#         """获取第一层参数的值。如果键不存在，返回默认值。"""
#         return self._config_data.get(key, default)

#     def get_nested(self, *keys: str, default: Optional[Any] = None) -> Any:
#         """获取嵌套 JSON 的安全方法。"""
#         current = self._config_data
#         for key in keys:
#             if isinstance(current, dict) and key in current:
#                 current = current[key]
#             else:
#                 return default
#         return current

#     @property
#     def all_config(self) -> Dict[str, Any]:
#         """以只读属性暴露完整的配置字典。"""
#         return self._config_data

# # 初始化
# # 1. 获取名为 SCONFIG 的环境变量（如果不存在，默认返回 None）
# sconfig_env = os.environ.get("SCONFIG")

# # 2. 如果环境变量存在，将其传给配置初始化函数
# if sconfig_env:
#     # 假设你的 Setup 类接受这个参数
#     settings = Setup(sconfig_env)
#     logger.info(f"⚡ 已通过环境变量 SCONFIG 加载配置: {sconfig_env}")
#     logger.debug(f"当前配置内容: {settings.domain}")
# else:
#     logger.info("⚡ 环境变量 SCONFIG 未设置，使用默认配置文件路径config.json")
#     # 如果没有环境变量，走默认的系统路径（比如 /etc/sing-box/config.json）
#     settings = Setup()