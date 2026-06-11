# 使用基础配置，这会直接作用于 "根(Root)日志器"
# 所有的子模块 logger 都会自动继承这个配置
#logging初始化要在最开头，下面的导包里如果也用了logging，就会抢先，下面的config就没有用了
import logging
import sys
import time
from typing import Union
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
import jstyleson
import asyncio
import argparse
from rich.console import Console
from rich.table import Table
from pathlib import Path
import logging
from aioconsole import ainput
from Service.serviceManager import UserService

domain:str  = settings.domain
transport_path = settings.transport_path

CONFIG_PATH = "/etc/sing-box/config.json"
ClientBasePath = settings.clientBasePath
BINARY_PATH = "/usr/bin/sing-box" # 建议写绝对路径，防止环境问题
SERVICE_NAME = "sing-box.service"


async def interact_and_resolve_user(name: str, current_db) -> Union[dict, str, None]:
    """
    🎯 职责：只负责终端查重和挑人
    返回值：
      - dict: 锁定的老用户数据
      - "NEW": 明确要开新号
      - None: 彻底取消当前用户
    """
    if not current_db.exists_by_name(name):
        return "NEW"

    existing_users = current_db.get_all_users_by_name(name)
    print(f"\n\033[93m⚠️ 发现系统中已存在 {len(existing_users)} 个同名用户:\033[0m")
    for idx, user in enumerate(existing_users):
        print(f"  [\033[1;36m{idx}\033[0m] 拼音: {user.get('pinyin','无')} | UUID: {user.get('uuid')[-8:]} | 备注: {user.get('comment','')}")
    print(f"  [\033[1;32mn\033[0m] \033[32m另起炉灶：创建一个全新的同名独立账号\033[0m")
    print(f"  [\033[1;31mq\033[0m] \033[31m取消退出\033[0m")

    try:
        choice = (await ainput("\n👉 请输入序号选择操作 [q]: ")).strip().lower()
        if choice in ('q', ''): return None
        if choice == 'n': return "NEW"
        if choice.isdigit() and int(choice) < len(existing_users):
            return existing_users[int(choice)]
    except (asyncio.CancelledError, KeyboardInterrupt):
        return None
    
    print("\n[!] 输入错误，放弃当前用户。")
    return None
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
        user = UserManager.create_from_data(user_data)
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
    # remove
    parser_remove = subparsers.add_parser("remove", help="Remove a user")
    parser_remove.add_argument("usernames", nargs='+', help="Usernames to remove")
    # get info
    parser_get = subparsers.add_parser("get", help="Get user data")
    parser_get.add_argument("username", help="Username to get info")
    #stop
    parser_stop = subparsers.add_parser("disable", help="Stop a user")
    parser_stop.add_argument("usernames", nargs='+', help="Usernames to stop")

    # enable
    parser_enable = subparsers.add_parser("enable", help="Enable a stopped user")
    parser_enable.add_argument("usernames", nargs='+', help="Usernames to enable")

    # update
    parser_update = subparsers.add_parser("update", help="Update user credentials")
    parser_update.add_argument("usernames", nargs='+', help="Usernames to update")

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

    match args.command:
        
        case "list":
            await _list()
            
        case "disable":
            for username in args.usernames:
                user_datas = db.get_all_users_by_name(username)
                for user_data in user_datas:
                    user = UserManager.create_from_data(user_data=user_data)
                    if user is not None:
                        user.disable()
                    
        case "enable":
            for username in args.usernames:
                user_datas = db.get_all_users_by_name(username)
                for user_data in user_datas:
                    user = UserManager.create_from_data(user_data=user_data)
                    if user is not None:
                        await user.enable()
        case "remove":
            for username in args.usernames: 
                user_datas = db.get_all_users_by_name(username)
                for user_data in user_datas:
                    user = UserManager.create_from_data(user_data=user_data)
                    if user is not None:
                        user.perge()
                else:
                    logger.error(f"❌ 用户 {username} 不存在")
        case "renew":
            username = args.username
            user_datas = db.get_all_users_by_name(username)
            for user_data in user_datas:
                user = UserManager.create_from_data(user_data=user_data)
                if user is not None:
                    user.service.merge()
        case "get":
            username = args.username
            user_datas = db.get_all_users_by_name(username)
            for user_data in user_datas:
                    user = UserManager.create_from_data(user_data=user_data)
                    if user:
                        info =  user.userData
                        print(info)
                
        case "add" | "update":
            print(f"DEBUG: 接收到的所有用户名列表是 -> {args.usernames}")
            
            for name in args.usernames:
                logger.info(f"准备用户: {name}")
                
                # 1. 扔给查重交互函数，拿到明确的意图
                resolution = await interact_and_resolve_user(name, db)
                
                # 情况 A：取消或输入错误，安全跳过当前，处理下一个
                if resolution is None:
                    continue
                
                # 情况 B：成功锁定老用户
                if isinstance(resolution, dict):
                    logger.info(f"👉 成功锁定老用户 {name}，开始拉取实例...")
                    user = UserManager.create_from_data(resolution)
                    # 接下来你可以根据是 "update" 还是 "add" 决定对这个老用户做什么
                    # user.update_something() / user.save()
                    continue

                # 情况 C：明确要创建全新账号 (resolution == "NEW")
                try:
                    user_input = await ainput(f"\n👉 请输入用户 [{name}] 的备注（输入 q 退出）: ")
                    clean_input = user_input.strip()
                    if clean_input.lower() == 'q':
                        continue
                    comment = clean_input
                except (asyncio.CancelledError, KeyboardInterrupt):
                    print("\n[!] 检测到中断信号，操作已取消。")
                    continue

                # 2. 调用精简后的 UserManager 组装厂
                user = UserManager.new(name, comment=comment)
                if user and user.save():
                    logger.info(f"🎉 用户 {name} 全线配置成功！")
                    
        case "refreshAll":
            users = db.get_all_users()
            for user in users:
                logger.debug(f"get user {user}")
                user =  UserManager.create_from_data(user)
                assert user is not None, f"panic, 无法绑定用户 {user.get('name')}"

                user.client.add()
                user.save()
                logging.info(f"已刷新用户配置: {user.name}")
                
        case "refresh":
            logging.info(f"正在刷新用户配置: {args.username}")
            users = db.get_all_users_by_name(args.username[0])
            
            for user_data in users:
                user =  UserManager.create_from_data(user_data)
                assert user is not None, f"panic, 无法绑定用户 {args.username[0]}"
                user.save()
        
        case  "init":
            logger.info("初始化，将会:\n覆盖/etc/sing-box/config.json为初始模板")
            UserService.init()
        case "modify":
            pinyin_name = args.pinyin_name
            await manager.modify(pinyin_name)
            
        case "sync-service":
            #从数据库读数据，写入服务端的config
            all_user_data = db.get_all_users()
            for user_data  in all_user_data:
                user = UserManager.create_from_data(user_data)
                user.service.merge()

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