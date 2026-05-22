import pathlib
import shutil
import json
from typing import Optional, Dict, Any
from Settings import settings
from Node import ClientNode
import jstyleson
import logging
logger = logging.getLogger(__name__)
from .ConfigEngine import ClientEgine
EXCLUDE_PACKAGES = [
    "cmb.pb",
    "cn.gov.pbc.dcep",
    "com.MobileTicket",
    "com.adguard.android",
    "com.ainemo.dragoon",
    "com.alibaba.android.rimet",
    "com.alicloud.databox",
    "com.amazing.cloudisk.tv",
    "com.autonavi.minimap",
    "com.bilibili.app.in",
    "com.bishua666.luxxx1",
    "com.cainiao.wireless",
    "com.chebada",
    "com.chinamworld.main",
    "com.cmbchina.ccd.pluto.cmbActivity",
    "com.coolapk.market",
    "com.ctrip.ct",
    "com.dianping.v1",
    "com.douban.frodo",
    "com.eg.android.AlipayGphone",
    "com.farplace.qingzhuo",
    "com.hanweb.android.zhejiang.activity",
    "com.leoao.fitness",
    "com.lucinhu.bili_you",
    "com.mikrotik.android.tikapp",
    "com.moji.mjweather",
    "com.motorola.cn.calendar",
    "com.motorola.cn.lrhealth",
    "com.netease.cloudmusic",
    "com.sankuai.meituan",
    "com.sina.weibo",
    "com.smartisan.notes",
    "com.sohu.inputmethod.sogou.moto",
    "com.sonelli.juicessh",
    "com.ss.android.article.news",
    "com.ss.android.lark",
    "com.ss.android.ugc.aweme",
    "com.tailscale.ipn",
    "com.taobao.idlefish",
    "com.taobao.taobao",
    "com.tencent.mm",
    "com.tencent.mp",
    "com.tencent.soter.soterserver",
    "com.tencent.wemeet.app",
    "com.tencent.weread",
    "com.tencent.wework",
    "com.ttxapps.wifiadb",
    "com.unionpay",
    "com.unnoo.quan",
    "com.wireguard.android",
    "com.xingin.xhs",
    "com.xunmeng.pinduoduo",
    "com.zui.zhealthy",
    "ctrip.android.view",
    "io.kubenav.kubenav",
    "org.geekbang.geekTime",
    "tv.danmaku.bili"
        ]

WIFI_RULE = {
    "type": "logical",
    "mode": "or",
    "rules": [
        {"wifi_bssid": ["d0:76:e7:e3:c0:bd"]},
        {"wifi_ssid": ["CIA.LAN", "TP-LINK.5G"]}
    ],
    "outbound": "direct"
}

class ClientManager:
    # 全局公共类变量：客户端配置的根目录
    BASE_PATH_str = settings.clientBasePath if settings.clientBasePath else ("/srv/configrations/")
    BASE_PATH = pathlib.Path(BASE_PATH_str).resolve()
    
    def __init__(self, user_data: Dict[str, Any]):
        """
        初始化大管家，每个实例专门负责这【一个用户】的客户端文件生命周期管理
        """
        # 从字典中提取核心元数据
        self.user_data = user_data
        self.username: Optional[str] = user_data.get("name")
        self.node = ClientNode(user_data)
        self.template = settings.templates_dir / "base.jsonc"
        self.engine = ClientEgine()
        # 你的设想非常对：每个用户有一个自己的文件夹（以唯一标识 tag 命名）
        # 如果没有 tag，就退一步用 name
        self.tag: Optional[str] = user_data.get("tag") or self.username
        
        # 动态算出该用户的物理文件夹路径
        self.directory: pathlib.Path = (
            (ClientManager.BASE_PATH / self.tag).resolve() if self.tag else ClientManager.BASE_PATH
        )

    @property
    def is_valid(self) -> bool:
        """
        [查/验证] 安全检查：确保用户目录合法存在，没有发生跨目录穿越攻击
        """
        if not self.tag or self.directory == ClientManager.BASE_PATH:
            return False
        
        # 核心防穿越：解析后的绝对路径必须确实属于 BASE_PATH 的子目录
        try:
            return self.directory.exists() and self.directory.is_dir() and self.directory.is_relative_to(ClientManager.BASE_PATH)
        except ValueError:
            return False
        
    def unix(self):
        """
        [改] 配置转换：针对 Unix 系统的客户端，进行特定的配置调整
        """
        # 这里可以放一些针对 Unix 客户端的特殊配置逻辑，例如调整路径格式、添加特定节点等
        # 目前暂时是个占位符，后续根据实际需求来填充
        try:
            with open(self.template, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
        except FileNotFoundError:
            logger.error(f"❌ 错误: 找不到配置文件 {self.template}")
            return False
        try:
        # 🎯 定点定向抓取，找不到会直接触发 StopIteration
            proxy_group = next(o for o in config["outbounds"] if o["tag"] == "Proxy")["outbounds"]
            urltest = next(o for o in config["outbounds"] if o["type"] == "urltest")["outbounds"]
            
            for node in self.nodes:
                proxy_group.append(node["tag"])
                urltest.append(node["tag"])
                config["outbounds"].append(node)     
            # 4. 将最终生成的 JSON 配置文件写入用户独立文件夹
            unix = self.directory / "config.json"
            with open(unix, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ [ClientManager] 创建Unix客户端配置失败: {e}")
            raise e
        
    def add(self) -> bool:
        
        """
        [增] 根据模板和底层生成的节点配置，合成专属于该用户的独立导入文件并落盘
        """
        
        if not self.tag:
            logger.error("❌ 错误: 用户元数据中缺失唯一 tag，无法创建配置")
            return False
        nodes = self.node.generate()
        self.nodes = list(nodes)
        

        # 1. 确保物理文件夹存在 (parents=True 类似 mkdir -p，exist_ok=True 防止目录已存在时报错)
        self.directory.mkdir(parents=True, exist_ok=True)
        
        self.unix()
        self._Android()
        self._iOS()
        self._windows()

        return True

    def _windows(self):
        try:
            with open(self.template, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
        except FileNotFoundError:
            logger.error(f"❌ 错误: 找不到配置文件 {self.template}")
            return False
        try:

        # 🎯 定点定向抓取，找不到会直接触发 StopIteration
            proxy_group = next(o for o in config["outbounds"] if o["tag"] == "Proxy")["outbounds"]
            urltest = next(o for o in config["outbounds"] if o["type"] == "urltest")["outbounds"]
            
            for node in self.nodes:
                proxy_group.append(node["tag"])
                urltest.append(node["tag"])
                config["outbounds"].append(node)     
                
            inbounds = config.get("inbounds", [])
            tun = None
            for inbound in inbounds:
                if inbound.get("type") == "tun":
                    tun = inbound
                    break
            if tun:
                # Windows 也需要移除 auto_redirect
                if tun.pop("auto_redirect", None):
                    logging.info("   [Win] 已移除 auto_redirect")
            # 4. 将最终生成的 JSON 配置文件写入用户独立文件夹
            file = self.directory / "windows.json"
            with open(file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ [ClientManager] 创建Unix客户端配置失败: {e}")
            raise e
        
    def _Android(self):
        try:
            with open(self.template, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
        except FileNotFoundError:
            logger.error(f"❌ 错误: 找不到配置文件 {self.template}")
            return False
        try:
        # 🎯 定点定向抓取，找不到会直接触发 StopIteration
            proxy_group = next(o for o in config["outbounds"] if o["tag"] == "Proxy")["outbounds"]
            urltest = next(o for o in config["outbounds"] if o["type"] == "urltest")["outbounds"]
            
            for node in self.nodes:
                proxy_group.append(node["tag"])
                urltest.append(node["tag"])
                config["outbounds"].append(node)     
            inbounds = config.get("inbounds", [])
            tun = None
            for inbound in inbounds:
                if inbound.get("type") == "tun":
                    tun = inbound
                    break
            if tun:
                # 移除 auto_redirect
                if tun.pop("auto_redirect", None):
                    logging.info("   [SFA] 已移除 auto_redirect")
                
                # 添加 exclude_package
                if settings.enable_exlude_package:
                    tun["exclude_package"] = EXCLUDE_PACKAGES
                logging.info(f"   [SFA] 已添加 exclude_package ({len(EXCLUDE_PACKAGES)} 个)")

            # 2. 添加 WiFi 规则
            dns_rule = config.get("dns").get("rules")
            try:
                # 直接通过 key 访问，如果键不存在会触发 KeyError
                route_rule = config["route"]["rules"]
                if not isinstance(route_rule, list):
                    raise TypeError("rules must be a list")
                route_rule.insert(1, WIFI_RULE)
                #根据业务逻辑决定是抛出异常还是初始化默认值
                logging.info("   [SFA] 已添加 WiFi 策略规则")
            except (KeyError, TypeError) as e:
                logging.error(f"route.rule数据结构错误: {e}")
            # 4. 将最终生成的 JSON 配置文件写入用户独立文件夹
            file = self.directory / "android.json"
            with open(file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ [ClientManager] 创建Unix客户端配置失败: {e}")
            raise e
        
    def _iOS(self):
        try:
            with open(self.template, 'r', encoding='utf-8') as f:
                config = jstyleson.load(f)
        except FileNotFoundError:
            logger.error(f"❌ 错误: 找不到配置文件 {self.template}")
            return False
        try:
            proxy_group = []
            for outbound in config["outbounds"]:
                if outbound["tag"] == "Proxy":
                    proxy_group = outbound.get("outbounds")
                    break

            for node in self.nodes:
                proxy_group.append(node["tag"])
                config["outbounds"].append(node)
            # 4. 将最终生成的 JSON 配置文件写入用户独立文件夹
            file = self.directory / "ios.json"
            with open(file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ [ClientManager] 创建Unix客户端配置失败: {e}")
            raise e

    def purge(self) -> bool:
        """
        [删] 毁灭这个配置包：彻底物理删除对应用户的独立文件夹
        """
        # 利用刚刚写的 leads（is_valid）进行前置校验
        if not self.is_valid:
            logger.warning(f"⚠️ 路径非法、目录不存在或没有操作权限，跳过文件清理: {self.directory}")
            return False
        
        try:
            # 斩草除根：递归删除整个用户目录
            shutil.rmtree(self.directory)
            print(f"✅ [ClientManager] 成功物理删除用户侧目录: {self.directory}")
            return True
        except OSError as e:
            print(f"❌ [ClientManager] 目录删除失败: {e}")
            return False
    def reload(self):
        pass