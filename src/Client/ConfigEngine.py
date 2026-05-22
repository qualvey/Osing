import jstyleson # type: ignore
import copy
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import os
import logging
from Settings import settings
# 获取当前模块的 logger
logger = logging.getLogger(__name__)
from Settings import settings
import copy
BASE_DIR = "/srv/configurations"
Enable_exlude_package = settings.enable_exlude_package
# ==========================================
# 1. 静态数据定义 (配置常量)
# ==========================================
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

class ClientEgine:
    def __init__(self):
        pass

    def Android(self, config: Dict[str, Any]) -> Dict[str, Any]:
        comment = "// 这是为 SFA (Android) 定制的配置文件"
        logging.info("-> 处理 SFA 配置...")

        # 1. 修改 Tun 入站
        tun = config.get("inbounds", [{}]).get("tun")
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
            
        return config

    def Windows(self, config: Dict[str, Any]) -> Dict[str, Any]:
        comment = "// 这是为 Windows 定制的配置文件"
        logging.info("-> 处理 Windows 配置...")
        config = copy.deepcopy(config)
        tun = config.get("inbounds", [{}]).get("tun")
        if tun:
            # Windows 也需要移除 auto_redirect
            if tun.pop("auto_redirect", None):
                logging.info("   [Win] 已移除 auto_redirect")
        return config

