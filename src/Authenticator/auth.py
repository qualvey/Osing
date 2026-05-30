#校验uuid(token)，返回文件
#甚至可以做后台管理的API
import logging
import re
from typing import Optional, Tuple
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request, status, Depends
from fastapi.responses import FileResponse
from database.sqlite import db
from Settings import settings
from Client.manager import ClientManager

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="backend 容器化客户端分发中心")

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
        
        # 🔍 核心防错机制：检查文件在硬盘上是否存在，且必须是文件（而不是目录）
        if not target_file.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"请求的配置文件 '{file}' 未找到"
            )
        logger.info(f"from: {client_ip},UUID [{clientM.user_data.get('uuid')}], 用户名: {clientM.user_data.get('name')}, 返回文件: {target_file}")
        return FileResponse(
            path=str(target_file),
            filename=target_file.name
        )
    else:
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