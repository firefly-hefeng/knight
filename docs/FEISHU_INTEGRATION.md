# 飞书长连接集成指南

本文档介绍如何在 Knight System 中使用飞书（Feishu/Lark）长连接功能，将飞书机器人与 Knight Agent 集群连接起来。

## 概述

飞书长连接是一种 WebSocket 全双工通信方式，允许 Knight 系统：

- **实时接收消息**：无需公网 IP 或内网穿透
- **双向通信**：同时支持接收和发送消息
- **安全可靠**：内置加密和鉴权机制
- **本地部署友好**：适合开发和生产环境

## 架构

```
┌─────────────┐      WebSocket      ┌─────────────┐
│  飞书用户    │ ◄─────────────────► │   飞书云端   │
└─────────────┘                     └──────┬──────┘
                                           │
                                    WebSocket
                                    长连接
                                           │
                                    ┌──────▼──────┐
                                    │ Knight 飞书 │
                                    │   网关      │
                                    └──────┬──────┘
                                           │
                                    ┌──────▼──────┐
                                    │ Knight Core │
                                    │  任务调度   │
                                    └──────┬──────┘
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                    ┌──────────┐    ┌──────────┐    ┌──────────┐
                    │  Claude  │    │   Kimi   │    │  其他Agent│
                    └──────────┘    └──────────┘    └──────────┘
```

## 快速开始

### 1. 安装依赖

```bash
# 安装飞书 SDK
pip install lark-oapi

# 或使用 requirements.txt
pip install -r api/requirements.txt
```

### 2. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 创建「企业自建应用」
3. 在「应用能力」→「机器人」中启用机器人
4. 在「事件与回调」中：
   - 选择「使用长连接接收事件」
   - 添加事件 `im.message.receive_v1`
5. 在「权限管理」中申请权限：
   - `im:message`
   - `im:message.p2p_msg:readonly`
   - `im:message:send_as_bot`
6. 在「凭证与基础信息」中获取 App ID 和 App Secret
7. 发布应用

### 3. 配置环境变量

```bash
export FEISHU_APP_ID="cli_xxxxxxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### 4. 启动飞书网关

```bash
# 方式 1: 使用环境变量
python launch.py feishu

# 方式 2: 命令行参数
python launch.py feishu --app-id cli_xxx --app-secret xxx

# 方式 3: 直接运行
python -m gateway.feishu_gateway
```

## 使用指南

### 基本命令

用户可以在飞书中对机器人发送以下命令：

| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/status` | 查看系统状态 | `/status` |
| `/agents` | 查看可用 Agent | `/agents` |
| `/task <描述>` | 创建新任务 | `/task 创建一个Python脚本` |
| `<任意文本>` | 直接创建任务 | `帮我写个排序算法` |

### 消息格式

#### 接收消息

当用户发送消息时，系统会解析为 `FeishuMessage` 对象：

```python
@dataclass
class FeishuMessage:
    message_id: str      # 消息唯一 ID
    message_type: str    # 消息类型 (text, image, etc.)
    content: str         # 消息内容
    sender_id: str       # 发送者 ID
    sender_name: str     # 发送者名称
    chat_id: str         # 聊天 ID
    chat_type: str       # 聊天类型 (p2p, group)
    create_time: datetime
```

#### 发送回复

```python
from adapters.feishu_adapter import FeishuReply

# 普通文本回复
reply = FeishuReply(content="收到您的消息！")

# @用户的回复
reply = FeishuReply(content="任务完成！", at_user_id="ou_xxx")

# Markdown 格式
reply = FeishuReply(content="# 标题\n内容", msg_type="markdown")
```

## 高级用法

### 自定义消息处理器

```python
from adapters.feishu_adapter import FeishuWebSocketGateway, FeishuMessage

async def my_handler(message: FeishuMessage, gateway):
    """自定义消息处理器"""
    print(f"收到消息: {message.content}")
    
    # 根据内容做不同处理
    if "urgent" in message.content.lower():
        await gateway.reply(
            message.message_id,
            "🚨 收到紧急请求，优先处理！"
        )
    else:
        await gateway.reply(
            message.message_id,
            f"收到: {message.content}"
        )

# 创建网关并注册处理器
gateway = FeishuWebSocketGateway(
    app_id="cli_xxx",
    app_secret="xxx"
)
gateway.register_message_handler(my_handler)

# 启动
await gateway.start()
```

### 与 Knight Core 集成

```python
from adapters.feishu_adapter import FeishuKnightBridge

# 创建桥接器
bridge = FeishuKnightBridge(
    app_id="cli_xxx",
    app_secret="xxx"
)

# 启动（自动处理所有消息）
await bridge.start()
```

### API 客户端

```python
from adapters.feishu_adapter import FeishuAPIClient

client = FeishuAPIClient(app_id="cli_xxx", app_secret="xxx")

# 回复消息
result = await client.reply_message(
    message_id="om_xxx",
    reply=FeishuReply(content="回复内容")
)

# 主动发送消息
result = await client.send_message(
    chat_id="oc_xxx",
    reply=FeishuReply(content="主动消息")
)
```

## 配置选项

### 环境变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `FEISHU_APP_ID` | 是 | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 是 | 飞书应用密钥 |
| `FEISHU_ENCRYPT_KEY` | 否 | 加密密钥 |
| `FEISHU_VERIFICATION_TOKEN` | 否 | 验证令牌 |

### 启动参数

```bash
python launch.py feishu --help

# 输出：
# --app-id TEXT     Feishu App ID (用于飞书模式)
# --app-secret TEXT Feishu App Secret (用于飞书模式)
```

## 故障排除

### 常见问题

#### 1. 机器人无响应

- 检查应用是否已发布
- 确认事件订阅配置正确（使用长连接模式）
- 检查权限是否足够
- 查看日志：`tail -f logs/feishu.log`

#### 2. 连接断开

- 网络波动：长连接会自动重连
- 检查 API 凭证是否有效
- 确认没有其他客户端占用连接（每应用最多 50 个连接）

#### 3. 无法发送消息

- 确认机器人已被添加到聊天中
- 检查 `im:message:send_as_bot` 权限
- 验证 tenant_access_token 是否有效

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

gateway = FeishuWebSocketGateway(
    app_id="cli_xxx",
    app_secret="xxx",
    log_level=logging.DEBUG
)
```

## 接口范式

### 飞书长连接 vs HTTP Webhook

| 特性 | 长连接 | Webhook |
|------|--------|---------|
| 需要公网 IP | ❌ 否 | ✅ 是 |
| 需要内网穿透 | ❌ 否 | 本地开发时需要 |
| 消息加密 | ✅ 内置 | 需要手动处理 |
| 开发周期 | 5 分钟 | 1 周左右 |
| 连接数限制 | 50/应用 | 无限制 |

### 数据流

```
1. 用户发送消息 → 飞书服务器
2. 飞书服务器 → WebSocket 长连接
3. Knight 飞书网关 → 解析消息
4. Knight Core → 创建并执行任务
5. Knight Core → 返回结果
6. 飞书网关 → 调用飞书 API 回复
7. 用户收到回复
```

## 参考

- [飞书开放平台文档](https://open.feishu.cn/document/home/index)
- [飞书长连接指南](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case)
- [飞书 Python SDK](https://github.com/larksuite/oapi-sdk-python)

## 示例

### 完整示例

```python
import asyncio
from adapters.feishu_adapter import FeishuKnightBridge

async def main():
    # 创建桥接器
    bridge = FeishuKnightBridge(
        app_id="cli_xxxxxxxxxxxx",
        app_secret="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    )
    
    try:
        print("🚀 启动飞书网关...")
        await bridge.start()
    except KeyboardInterrupt:
        print("\n👋 正在关闭...")
        await bridge.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

运行后，用户可以在飞书中与机器人对话，所有消息都会被转发到 Knight Core 处理。
