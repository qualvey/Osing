
import logging
import re
import bcrypt  
from typing import Optional, Tuple
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request, status, Depends
from fastapi.responses import FileResponse
from database import db
from Settings import settings
from Client.manager import ClientManager
from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from urllib.parse import quote
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware
logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="backend 容器化客户端分发中心")
# 在创建 app = FastAPI() 之后立即添加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://vite.wowoha.top"], # 👈 显式允许你的前端域名访问
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 初始化密码加密上下文（使用安全标准的 bcrypt 算法）
class UserLoginSchema(BaseModel):
    username: str
    password: str

class LoginResponseSchema(BaseModel):
    message: str
    token: str  # 这里的 token 实际上就是用户的 UUID
    username: str
    

@app.post("/login")
async def login(login_data: UserLoginSchema, request: Request):
    logger.info(f"🔐 登录尝试：用户名 [{login_data.username}]，来自 IP: [{request.client.host if request.client else '未知'}]")
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "127.0.0.1")
    
    # 1. 直接获取完整的用户数据字典
    user = db.get_alldata_by_name(login_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 2. 安全取出密码（哪怕没加字段，上面加了兜底，这里也是 None）
    db_password_hash = user.get("password_hash")
    if not db_password_hash:
        logger.error(f"❌ 账户异常：用户 [{login_data.username}] 在数据库中尚未配置 password_hash")
        raise HTTPException(status_code=500, detail="该账户未设置密码，请联系管理员")

    # 3. ─── 核心修改：改用原生 bcrypt 校验密码，避开 Python 3.13 兼容坑 ───
    try:
        is_password_correct = bcrypt.checkpw(
            login_data.password.encode('utf-8'),      # 前端传过来的明文密码
            db_password_hash.encode('utf-8')          # 数据库存的 $2b$12$... 哈希串
        )
    except Exception as e:
        logger.error(f"❌ 密码哈希校验时发生非预期错误: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")

    if not is_password_correct:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
        
    # 4. 验证通过，直接返回他原本就在使用的 UUID
    logger.info(f"🚀 登录成功：用户 [{user['name']}] 已验证通过，分发 UUID。")
    return {
        "message": "登录成功",
        "token": user["uuid"],  # 直接从字典里拿已有的 uuid 丢给前端
        "username": user["name"]
    }
    
def get_version(version_str: str) -> Tuple[int, ...]:
    """版本号精确解析器"""
    try:
        return tuple(map(int, version_str.split('.')))
    except (ValueError, AttributeError):
        logger.warning(f"无法解析的版本号字符串: '{version_str}'")
        return (0, 0, 0)

def Which_file(ua: str) -> str:
    """卫语句重构：根据 UA 纯粹、无冲突地决定物理文件名"""
    ua_lower = ua.lower()

    # 策略 A: iOS 独立分支
    if "sfi" in ua_lower or "iphone" in ua_lower:
        match = re.search(r"SFI/([\d\.]+)", ua, re.IGNORECASE)
        if match and get_version(match.group(1)) > (1, 12, 0):
            return "ios_latest.json"
        return "ios.json"

    # 策略 B: Android 独立分支
    if "sfa" in ua_lower or "android" in ua_lower:
        match = re.search(r"SFA/([\d\.]+)", ua, re.IGNORECASE)
        if match and get_version(match.group(1)) > (1, 12, 0):
            return "android.json"
        return "sfa_1.11.json"

    # 策略 C: Linux 分支
    if "linux" in ua_lower:
        return "config.json"

    # 终极兜底: Windows / 其余客户端
    return "windows.json"

# 3. 依赖注入：门禁卡人肉掏出和查表逻辑，剥离成独立高内聚函数
async def get_authenticated_user(
    request: Request,
    
    token: Optional[str] = Query(None),
    x_token: Optional[str] = Header(None, alias="X-Token"),
    x_real_ip: Optional[str] = Header(None, alias="X-Real-IP")
) -> Tuple[ClientManager, str]:
    """门禁校验依赖项：不通过直接丢 403 炸弹"""
    auth_token = x_token or token
    client_ip = x_real_ip

    # 2. 如果反向代理没传，再去找连接本身的 client
    if not client_ip:
        if request.client:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"  # 终极内网物理兜底，防止程序挂掉
    if not auth_token:
        logger.warning(f"🔒 拦截：匿名访问试图窥探接口，来自 IP: [{client_ip}]")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

    user = db.get_user_by_uuid(auth_token)
    if not user:
        logger.warning(f"🚫 拒绝：无效或已过期的 Token [{auth_token[:8]}...]，拦截自 IP: [{client_ip}]")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication token")
    logger.info(f"✅ 认证成功：用户 [{user['name']}]，UUID [{user['uuid']}], 来自 IP: [{client_ip}]")
    clientM = ClientManager(user)

    return clientM, client_ip

@app.get("/{full_path:path}")
async def check_auth(
    file: Optional[str] = Query(None),
    MetaData: Tuple[ClientManager, str] = Depends(get_authenticated_user),
    user_agent: str = Header("", alias="User-Agent")
    # 1. 延续我们上一节聊的生命周期：直接Depends拿到合法的 clientM 实例
):
    """主认证分发端点：安全解析 Path 对象并流式返回"""
    clientM , client_ip = MetaData
    # 2. 根据 UA 决定具体的文件名（返回字符串，例如 "sfa.json"）
    if file:
        # 优先级最高：如果用户传了 ?file=xxx，直接用它
        target_file = clientM.directory / file
        logger.info(f"用户指定了文件参数: '{file}', 将直接尝试访问: {target_file}")
        
        
        # 🔍 核心防错机制：检查文件在硬盘上是否存在，且必须是文件（而不是目录）
        if not target_file.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"请求的配置文件 '{file}' 未找到"
            )
        
        logger.info(f"from: {client_ip},UUID [{clientM.user_data.get('uuid')}], 用户名: {clientM.user_data.get('name')}, 返回文件: {target_file}")
        
        # --- 🛠️ 核心修改：针对 clash.yaml 动态注入 Clash 规范响应头 ---
        custom_headers = {}
        
        if file == "clash.yaml":
            # 1. 配置文件名（支持中文，防止客户端乱码）
            profile_name = "自由以太"
            encoded_name = quote(profile_name)
            custom_headers["content-disposition"] = f"attachment; filename*=UTF-8''{encoded_name}"
            
            # 2. 自动更新周期（单位：小时）
            custom_headers["profile-update-interval"] = "24"
            
            # # 3. 流量与到期信息（动态从 clientM 读取或设为固定值，单位：Byte）
            # # 这里的 100GB 只是举例，你可以从 clientM.user_data 动态算出来
            # upload = 10 * 1024 * 1024 * 1024
            # download = 40 * 1024 * 1024 * 1024
            # total = 500 * 1024 * 1024 * 1024
            # expire = 1780000000
            # custom_headers["subscription-userinfo"] = f"upload={upload}; download={download}; total={total}; expire={expire}"
            
            # 4. 右键卡片点击首页跳转的 URL
            custom_headers["profile-web-page-url"] = "https://cn2.ryugo.org"
            
            logger.info(f"已成功为 '{file}' 注入 Clash 订阅规范响应头。")

        # 返回文件时，把 custom_headers 传给 headers 参数
        return FileResponse(
            path=str(target_file),
            filename=target_file.name,
            headers=custom_headers if custom_headers else None
        )
    else:
        logger.info(f"用户未指定文件参数，启用 UA 卫语句策略解析目标文件。User-Agent: '{user_agent}'")
        # 优先级次之：如果没有传 file 参数，走你的 UA 卫语句策略
        target_file = Which_file(user_agent)
    
    # 3. 硬核 Path 拼接：利用 pathlib.Path 的 / 符号在内存中安全拼装
    # clientM.directory 是 Path 对象，real_file_name 是字符串，两者用 / 拼装后，依然是个完美的 Path 对象
    config_file_path = clientM.directory / target_file

    # 4. 物理防御防御：确保文件真实存在（Path 对象自带 .exists() 方法，极度优雅）
    if not config_file_path.exists():
        logger.error(f"❌ [文件缺失] 用户路径鉴权成功，但物理配置文件不存在: {config_file_path}")
        raise HTTPException(status_code=404, detail="Configuration file missing")

    logger.info(f"from: {client_ip},UUID [{clientM.user_data.get('uuid')}], 用户名: {clientM.user_data.get('name')}, 返回文件: {config_file_path}")
    
    # 5. 转换类型并丢给 FileResponse 倒水
    return FileResponse(
        path=str(config_file_path),          # 👈 将 Path 对象转换为标准的纯字符串路径
        filename=config_file_path.name,      # 👈 Path 对象自带 .name 属性，直接拿文件名，彻底免去 os.path.basename 的麻烦！
        media_type="application/json"
    )

def serve():
    logger.info(f"⚡ 订阅分发中心已就绪。根目录: {settings.client_base_dir}，正在监听 0.0.0.0:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="debug")

if __name__ == "__main__":
    serve()