# Sing-box 节点管理系统
为了快速配置vless和tuic节点，并产生分发订阅
订阅功能需要配合nginx做前置代理

## Prerequisites
- uv
- libsystemd-dev

```bash
sudo apt update
sudo apt install libgirepository-2.0-dev gobject-introspection cmake libcairo2-dev build-essential pkg-config libsystemd-dev
```

## Install

```bash
git clone this repo
cd repo_dir
uv sync
```

## Config Required

`config.json`

```json
    "domain": "us.ryugo.org",
```

## How to use

## Init

```bash
uv run src/main.py init
```

### Add user

```bash
uv run src/main.py username
```
### Client config server

```bash
uv run src/serve.py
```
listen in 9000,
