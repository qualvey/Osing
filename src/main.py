# 使用基础配置，这会直接作用于 "根(Root)日志器"
# 所有的子模块 logger 都会自动继承这个配置
#logging初始化要在最开头，下面的导包里如果也用了logging，就会抢先，下面的config就没有用了
import logging
import sys
import time
logging.basicConfig(
    level=logging.DEBUG, # 屏幕上只看 INFO 及以上
    format="%(asctime)s [%(levelname)s] (%(name)s)[%(funcName)s:%(lineno)d]%(message)s", # [%(name)s] 可以看出是哪个模块打印的
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout), # 输出到屏幕
        logging.FileHandler("app.log", encoding="utf-8") # 同时记录到文件
    ])
logger = logging.getLogger(__name__)

from user_manager    import UserManager
from Checker import ConfigChecker
from database.sqlite import db
from Settings import settings
import json
import jstyleson
import asyncio
import argparse
from rich.console import Console
from rich.table import Table
from pathlib import Path
import logging
from Service.serviceManager import UserService

domain:str  = settings.domain
transport_path = settings.transport_path

CONFIG_PATH = "/etc/sing-box/config.json"
ClientBasePath = settings.clientBasePath
BINARY_PATH = "/usr/bin/sing-box" # 建议写绝对路径，防止环境问题
SERVICE_NAME = "sing-box.service"

def get_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    return current.parent # 兜底返回

def get_user_datas_from_config(config_path: str):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = jstyleson.load(f)
    except Exception as e:
        logging.error(f"❌ 读取配置文件失败: {e}")
        return []
    
    user_datas = []
    for inbound in config.get("inbounds", []):
        if inbound.get("type") == "tuic":
            for u in inbound.get("users", []):
                user_datas.append(u)
    logging.info(f"从配置文件中获取到 {len(user_datas)} 个用户数据")
    return user_datas

def get_display_width(s):
    # 计算字符串的显示宽度：中文算2，英文算1
    return sum(2 if '\u4e00' <= c <= '\u9fff' else 1 for c in s)

def pad_string(s, width):
    # 根据实际显示宽度补齐空格
    diff = width - get_display_width(s)
    return s + " " * max(0, diff)

def load_template(filename: str):
    # 1. 获取指向文件的“路径对象”
    target = settings.templates_dir / filename
    
    # 2. 读取内容
    with open(target, "r", encoding="utf-8") as f:
        config = jstyleson.load(f)
    return config

def load_file_content(filepath: str):
    try:
        logger.info(f"正在加载文件: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            return jstyleson.load(f)
    except Exception as e:
        logger.error(f"❌ 读取文件失败: {e}")
        return None

async def _list():
    users = db.get_all_users()
    
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Username", width=10)
    table.add_column("pinyin", width=20)
    table.add_column("Enabled", width=8)
    table.add_column("UUID")
    table.add_column("passwd")
    table.add_column("Comment")
    for u in users:
        table.add_row(u.get('name'), u.get('tag'), str(u.get('enabled')), u.get('uuid'),u.get("password"), u.get('comment', ''))
    console.print(table)
    
def list():
    asyncio.run(_list())
    
#同步config中的user数据到redis中，供服务运行时读取
async def _sync():
    user_datas = get_user_datas_from_config(CONFIG_PATH)
    logging.info("base_url: https://www.ryugo.org/sub/config.json?token=")
    # for data in user_datas:
        
def sync():
    asyncio.run(_sync())
    
 # TODO 迁移用户   
def add_user_mannully():
    user_datas = []
    for user_data in user_datas:
        user = UserManager.new_user_from_data(user_data)
        user.save()
        time.sleep(1)

async def main():
    root_path = get_project_root()
    TEMPLATE_FILE = "base.jsonc"
    IOS_Template  = "ios.jsonc"
    TEMPLATE_Config = load_template(f"{root_path}/templates/{TEMPLATE_FILE}")
    IOS_Config      = load_template(f"{root_path}/templates/{IOS_Template}")
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Username", width=20)
    table.add_column("Status", width=10)
    table.add_column("UUID")
    table.add_column("Comment")
    # TODO 
    service_config_checker = ConfigChecker()

    # 命令行参数解析
    parser = argparse.ArgumentParser(description="Sing-box User Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # add
    parser_add = subparsers.add_parser("add", help="Add a new user")
    parser_add.add_argument("usernames", nargs='+', help="Usernames to add")
    parser_add.add_argument("-c", "--comment", help="Comment for the user(s)", default=None)
    
    #stop
    parser_stop = subparsers.add_parser("disable", help="Stop a user")
    parser_stop.add_argument("usernames", nargs='+', help="Usernames to stop")

    # enable
    parser_enable = subparsers.add_parser("enable", help="Enable a stopped user")
    parser_enable.add_argument("usernames", nargs='+', help="Usernames to enable")

    # remove
    parser_remove = subparsers.add_parser("remove", help="Remove a user")
    parser_remove.add_argument("usernames", nargs='+', help="Usernames to remove")

    # update
    parser_update = subparsers.add_parser("update", help="Update user credentials")
    parser_update.add_argument("usernames", nargs='+', help="Usernames to update")
    # get info
    parser_get = subparsers.add_parser("get", help="Get user info")
    parser_get.add_argument("usernames", nargs='+', help="Usernames to get info")
    # refreshAll
    parser_refreshAll = subparsers.add_parser("refreshAll", help="Refresh all user's configurations")
    parser_refresh    = subparsers.add_parser("refresh", help="Refresh a user's configuration")
    parser_refresh.add_argument("username", nargs='+', help="Username to refresh")

    # list
    parser_list = subparsers.add_parser("list", help="List all users")
    
    parser_modify = subparsers.add_parser("modify", help="Modify a user's information")
    parser_modify.add_argument("pinyin_name", help="Pinyin name of the user to modify")
    parser_modify.add_argument("-c", "--comment", help="New comment for the user")
    
    parser_init = subparsers.add_parser("init", help="Initialize the service (backup config, etc.)")
    
    parser_renew = subparsers.add_parser("renew", help="重新添加用户node")
    parser_renew.add_argument("username",  help="Usernames to add")
    

    parser_sync = subparsers.add_parser("sync", help="Sync from redis to /etc/sing-box/config.json")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.command == "list":
        await _list()
    elif args.command == "disable":
        for username in args.usernames:
            user = await UserManager.get_user_by_name(username)
            if user is not None:
                
                user.disable()
    elif args.command == "renew":
        username = args.username
        user = await UserManager.get_user_by_name(username)
        if user is not None:
            user.service.merge()
        
    elif args.command == "init":
        UserService.init()

    elif args.command == "enable":
        for username in args.usernames:
            user = await UserManager.get_user_by_name(username)
            if user is not None:
                await user.enable()

    elif args.command == "remove":
        for username in args.usernames:
            user = await UserManager.get_user_by_name(username)
            if user is not None:
                user.perge()
            else:
                logger.error(f"❌ 用户 {username} 不存在")
                
    elif args.command == "get":
        user = await UserManager.get_user_by_name(args.usernames[0])
        if user:
            info =  user.userData
            print(info)
            
    elif args.command in ["add", "update"]:
        print(f"DEBUG: 接收到的所有用户名列表是 -> {args.usernames}")
        for username in args.usernames:
            new_user = await UserManager.add(username)
            if new_user:
                new_user.save()
                new_user.service.reload()
                # service_config_checker.reload_service()
                
                print("-" * 30)
                print(f"最终生成的用户信息 ({username}):")
                print(json.dumps(new_user.userData, indent=4, ensure_ascii=False))
            else:
                logger.error("用户创建失败")
                
    elif args.command == "refreshAll":
        users = db.get_all_users()
        
        for user in users:
            uuid =user.get("uuid")
            assert isinstance(uuid,str), "panic, user has no uuid"
            user = await UserManager.bind_with_uuid(uuid)
            #db,service,client
            # TODO 
            user.client.add()
        
        # config_updater = ConfigUpdater(TEMPLATE_Config, IOS_Config, all_data)
        # config_updater.update()   
                 
    elif args.command == "refresh":
        logging.info(f"正在刷新用户配置: {args.username}")
        users = []
        for username in args.username:
            user_data = await manager.get_user_info(username)
            if user_data:
                users.append(user_data)
        for user_data in users:
            generator = ConfigGenerator(TEMPLATE_Config, IOS_Config, userdata=user_data)
            generator.run()
    elif args.command == "modify":
        pinyin_name = args.pinyin_name
        await manager.modify(pinyin_name)
    elif args.command == "sync":
        await manager.sync_from_redis()
            

def run ():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 当用户按下 Ctrl+C 时，直接打印一行友好的提示，并以状态码 130（Linux 信号退出标准）静默退出
        print("\n[!] 操作被用户取消。")
        try:
            sys.exit(130)
        except SystemExit:
            pass

if __name__ == "__main__":
    run()