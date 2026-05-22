# 业务逻辑

## 1.定义新用户数据

```  json
username: ""
uuid: ""
passwd: ""
```

## 2.将用户数据放进redis

- 作用是给后端python程序做鉴权以及获取token对应的username，这里你可以设计一下。注意，redis里面的值不用中文，名字有中文用拼音替代，为了防止重名，可以用加上uuid的后四位

## 3.操作service_config,添加user,参考代码如下

``` python
import json
new_user = {
    "name": new_name,
    "uuid": new_uuid,
    "password": new_pass
}
with open ......
found = False
for inbound in config.get("inbounds", []):
    if inbound.get("type") == "tuic":
        inbound["users"].append(new_user)
        found = True
        print(f"成功添加用户: {new_name} (UUID: {new_uuid})")
        break
if not found:
    print("未找到类型为 tuic 的 inbound 配置")
```

## 4.从一个模板文件base.jsonc生成client_config,，该文件已经存在，核心结构如下

``` json
{
  "outbounds": [
               {
            "type": "tuic",
            "tag": "\ud83c\uddef\ud83c\uddf5 osaka",
            "server": "ssh.ryugo.org",
            "server_port": 8443,
            "uuid": "",
            "password": "",
            "congestion_control": "bbr",
            "udp_relay_mode": "native",
            "udp_over_stream": false,
            "zero_rtt_handshake": false,
            "heartbeat": "3s",
            "tls": {
                "enabled": true,
                "disable_sni": false,
                "server_name": "ssh.ryugo.org",
                "alpn": [
                    "h3"
                ],
                "insecure": false
            }
        }
        ]  
      }
```

要求把uuid和password换成前面产生的值

## 5.执行另一个python程序，参数是client_config,会生成两个文件

## 5.创建文件夹。路径为/srv/configrations/$redis_token对应的name,把client_config和生成的两个文件放进去
