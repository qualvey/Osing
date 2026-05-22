#!/bin/env bash
tar -czf backend.tar.gz  --exclude=__pycache__ --exclude=*.pyc --exclude=.git --exclude=backend.tar.gz  --transform 's,^\.,backend,'   .
echo "打包完成，正在上传到服务器..."
scp backend.tar.gz osaka:/home/linuxuser/
echo "上传成功，正在解压..."
ssh osaka "cd /home/linuxuser && tar -xf backend.tar.gz && rm backend.tar.gz && cd backend && uv run list"