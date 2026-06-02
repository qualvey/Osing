#!/bin/bash

# ==================== 配置区域 ====================
# 定义你的服务名称（可自行修改）
SERVICE_NAME="sing-deliver"
# 获取当前脚本所在目录作为项目根目录
PROJECT_DIR=$(pwd)
# 获取当前运行脚本的用户名
CURRENT_USER=$(whoami)
# 自动查找 uv 的绝对路径
UV_PATH=$(which uv)
# 目标脚本
SCRIPT_PATH="src/serve.py"
# ==================================================

echo "🚀 开始配置 Systemd 常驻服务..."

# 1. 检查 uv 是否安装
if [ -z "$UV_PATH" ]; then
    echo "❌ 错误: 未找到 'uv' 命令，请确保 uv 已安装并已加入 PATH。"
    exit 1
fi

echo "📂 项目路径: $PROJECT_DIR"
echo "👤 运行用户: $CURRENT_USER"
echo "🛠️ UV 路径: $UV_PATH"

# 2. 检查目标 Python 脚本是否存在
if [ ! -f "$PROJECT_DIR/$SCRIPT_PATH" ]; then
    echo "❌ 错误: 未在 $PROJECT_DIR 中找到 $SCRIPT_PATH，请在项目根目录下运行此脚本。"
    exit 1
fi

# 3. 创建 Systemd 服务文件内容
SERVICE_FILE_CONTENT="[Unit]
Description=UV Python Serve Service ($SERVICE_NAME)
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$UV_PATH run $SCRIPT_PATH
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target"

# 4. 将配置写入临时文件，然后通过 sudo 移动到系统目录
echo "📝 正在生成服务配置文件..."
echo "$SERVICE_FILE_CONTENT" > /tmp/$SERVICE_NAME.service

sudo mv /tmp/$SERVICE_NAME.service /etc/systemd/system/$SERVICE_NAME.service

# 5. 刷新 Systemd 并启动服务
echo "🔄 正在加载并启动服务..."
sudo systemctl daemon-reload
sudo systemctl restart $SERVICE_NAME

echo "------------------------------------------------"
echo "✅ 服务 '$SERVICE_NAME' 已成功安装并启动！"
echo "------------------------------------------------"
echo "查看状态命令: sudo systemctl status $SERVICE_NAME"
echo "查看实时日志: journalctl -u $SERVICE_NAME -f"
echo "------------------------------------------------"

echo "正在开启bbr"
echo -e "net.core.default_qdisc=fq\nnet.ipv4.tcp_congestion_control=bbr" | sudo tee -a /etc/sysctl.conf && sudo sysctl -p
echo "✅ BBR 已成功开启！"