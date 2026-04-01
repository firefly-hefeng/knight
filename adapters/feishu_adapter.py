"""
飞书长连接适配器 - 基于 WebSocket 的事件订阅

使用 lark-oapi SDK 与飞书开放平台建立 WebSocket 长连接，
实现实时接收和发送消息，无需公网 IP 或内网穿透。

特性:
- WebSocket 长连接: 实时双向通信
- 自动重连: 连接断开后自动恢复
- 消息转换: 飞书消息格式与 Knight 内部格式互转
- 事件驱动: 基于事件的异步消息处理
"""
import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List, AsyncGenerator
from datetime import datetime

from .claude_adapter import TaskResult

logger = logging.getLogger(__name__)

# 尝试导入 lark_oapi
try:
    import lark_oapi as lark
    from lark_oapi import EventDispatcherHandler, ws, JSON, im, LogLevel
    LARK_AVAILABLE = True
except ImportError:
    LARK_AVAILABLE = False
    logger.warning("lark_oapi not installed. Feishu adapter will not work.")


@dataclass
class FeishuMessage:
    """飞书消息数据结构"""
    message_id: str
    message_type: str  # text, image, file, etc.
    content: str
    sender_id: str
    sender_name: Optional[str] = None
    chat_id: Optional[str] = None
    chat_type: Optional[str] = None  # p2p, group
    create_time: datetime = field(default_factory=datetime.now)
    mention_users: List[str] = field(default_factory=list)
    
    @classmethod
    def from_p2_im_message(cls, data: Any) -> "FeishuMessage":
        """从飞书 P2ImMessageReceiveV1 事件解析消息"""
        try:
            event_data = json.loads(JSON.marshal(data))
            message = event_data.get("event", {}).get("message", {})
            sender = event_data.get("event", {}).get("sender", {})
            
            # 解析消息内容
            content_str = message.get("content", "{}")
            try:
                content_dict = json.loads(content_str)
                text_content = content_dict.get("text", "")
            except:
                text_content = content_str
            
            return cls(
                message_id=message.get("message_id", ""),
                message_type=message.get("message_type", "text"),
                content=text_content,
                sender_id=sender.get("sender_id", {}).get("user_id", ""),
                chat_id=message.get("chat_id"),
                chat_type=message.get("chat_type"),
                create_time=datetime.now()
            )
        except Exception as e:
            logger.error(f"Failed to parse Feishu message: {e}")
            return cls(
                message_id="",
                message_type="text",
                content="",
                sender_id=""
            )


@dataclass
class FeishuReply:
    """飞书回复消息结构"""
    content: str
    msg_type: str = "text"
    at_user_id: Optional[str] = None
    
    def to_api_payload(self) -> Dict[str, Any]:
        """转换为飞书 API 请求体"""
        if self.msg_type == "text":
            text_content = self.content
            if self.at_user_id:
                text_content = f'<at user_id="{self.at_user_id}"></at> {text_content}'
            return {
                "msg_type": "text",
                "content": json.dumps({"text": text_content})
            }
        elif self.msg_type == "markdown":
            return {
                "msg_type": "interactive",
                "card": {
                    "schema": "2.0",
                    "elements": [{
                        "tag": "markdown",
                        "content": self.content
                    }]
                }
            }
        return {"msg_type": "text", "content": json.dumps({"text": self.content})}


class FeishuAPIClient:
    """飞书 API 客户端 - 用于发送消息"""
    
    TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    REPLY_URL_TEMPLATE = "https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
    SEND_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[str] = None
        self._token_expire_time: Optional[float] = None
        self._lock = asyncio.Lock()
        
        # 尝试导入 aiohttp
        try:
            import aiohttp
            self._session = aiohttp.ClientSession()
            self._has_aiohttp = True
        except ImportError:
            self._has_aiohttp = False
            logger.warning("aiohttp not installed, using requests")
    
    async def close(self):
        """关闭客户端"""
        if self._has_aiohttp and hasattr(self, '_session'):
            await self._session.close()
    
    async def _get_access_token(self) -> str:
        """获取访问令牌（带缓存）"""
        async with self._lock:
            now = time.time()
            if self._token and self._token_expire_time and now < self._token_expire_time - 60:
                return self._token
            
            headers = {"Content-Type": "application/json; charset=utf-8"}
            data = {"app_id": self.app_id, "app_secret": self.app_secret}
            
            if self._has_aiohttp:
                async with self._session.post(
                    self.TOKEN_URL, 
                    headers=headers, 
                    json=data
                ) as resp:
                    result = await resp.json()
            else:
                import requests
                resp = requests.post(self.TOKEN_URL, headers=headers, json=data)
                result = resp.json()
            
            self._token = result.get("tenant_access_token")
            expire = result.get("expire", 7200)
            self._token_expire_time = now + expire
            
            return self._token
    
    async def reply_message(self, message_id: str, reply: FeishuReply) -> Dict[str, Any]:
        """回复消息"""
        token = await self._get_access_token()
        url = self.REPLY_URL_TEMPLATE.format(message_id=message_id)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        payload = reply.to_api_payload()
        
        try:
            if self._has_aiohttp:
                async with self._session.post(url, headers=headers, json=payload) as resp:
                    return await resp.json()
            else:
                import requests
                resp = requests.post(url, headers=headers, json=payload)
                return resp.json()
        except Exception as e:
            logger.error(f"Failed to reply message: {e}")
            return {"code": -1, "msg": str(e)}
    
    async def send_message(self, chat_id: str, reply: FeishuReply) -> Dict[str, Any]:
        """主动发送消息到聊天"""
        token = await self._get_access_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        payload = reply.to_api_payload()
        payload["receive_id"] = chat_id
        
        try:
            if self._has_aiohttp:
                async with self._session.post(
                    self.SEND_URL, 
                    headers=headers, 
                    json=payload,
                    params={"receive_id_type": "chat_id"}
                ) as resp:
                    return await resp.json()
            else:
                import requests
                resp = requests.post(
                    self.SEND_URL, 
                    headers=headers, 
                    json=payload,
                    params={"receive_id_type": "chat_id"}
                )
                return resp.json()
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {"code": -1, "msg": str(e)}


class FeishuWebSocketGateway:
    """
    飞书 WebSocket 长连接网关
    
    与飞书开放平台建立 WebSocket 连接，实时接收和发送消息。
    无需公网 IP 或内网穿透工具。
    
    使用示例:
        gateway = FeishuWebSocketGateway(app_id="cli_xxx", app_secret="xxx")
        gateway.register_message_handler(my_handler)
        await gateway.start()
    """
    
    def __init__(
        self, 
        app_id: str, 
        app_secret: str,
        encrypt_key: str = "",
        verification_token: str = "",
        log_level: int = logging.INFO
    ):
        """
        初始化飞书 WebSocket 网关
        
        Args:
            app_id: 飞书应用 App ID (cli_xxx)
            app_secret: 飞书应用 App Secret
            encrypt_key: 加密密钥（可选）
            verification_token: 验证令牌（可选）
            log_level: 日志级别
        """
        if not LARK_AVAILABLE:
            raise RuntimeError(
                "lark_oapi is not installed. "
                "Please install it with: pip install lark-oapi"
            )
        
        self.app_id = app_id
        self.app_secret = app_secret
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token
        
        # 设置日志级别
        logging.basicConfig(level=log_level)
        
        # API 客户端
        self.api_client = FeishuAPIClient(app_id, app_secret)
        
        # WebSocket 客户端
        self._ws_client: Optional[ws.Client] = None
        self._event_handler: Optional[EventDispatcherHandler] = None
        
        # 消息处理器
        self._message_handlers: List[Callable[[FeishuMessage], asyncio.Future]] = []
        self._error_handlers: List[Callable[[Exception], None]] = []
        
        # 运行状态
        self._running = False
        self._connected = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        
        # 统计
        self._stats = {
            "messages_received": 0,
            "messages_sent": 0,
            "errors": 0,
            "connected_at": None
        }
        
        # 构建事件处理器
        self._build_event_handler()
    
    def _build_event_handler(self):
        """构建飞书事件处理器"""
        
        def handle_p2_im_message(data: im.v1.P2ImMessageReceiveV1) -> None:
            """处理接收到的消息"""
            try:
                message = FeishuMessage.from_p2_im_message(data)
                self._stats["messages_received"] += 1
                
                logger.info(f"Received message from {message.sender_id}: {message.content[:50]}...")
                
                # 异步处理消息
                for handler in self._message_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            asyncio.create_task(handler(message, self))
                        else:
                            handler(message, self)
                    except Exception as e:
                        logger.error(f"Message handler error: {e}")
                        
            except Exception as e:
                logger.error(f"Failed to handle message: {e}")
                self._stats["errors"] += 1
                for handler in self._error_handlers:
                    try:
                        handler(e)
                    except:
                        pass
        
        def handle_custom_event(data: lark.CustomizedEvent) -> None:
            """处理自定义事件"""
            logger.debug(f"Custom event received: {data}")
        
        # 构建事件处理器
        self._event_handler = EventDispatcherHandler.builder(
            self.verification_token, 
            self.encrypt_key
        ) \
            .register_p2_im_message_receive_v1(handle_p2_im_message) \
            .register_p1_customized_event("message", handle_custom_event) \
            .build()
    
    def register_message_handler(self, handler: Callable[[FeishuMessage, "FeishuWebSocketGateway"], Any]):
        """
        注册消息处理器
        
        Args:
            handler: 处理函数，接收 FeishuMessage 和 gateway 实例
        """
        self._message_handlers.append(handler)
    
    def register_error_handler(self, handler: Callable[[Exception], None]):
        """注册错误处理器"""
        self._error_handlers.append(handler)
    
    async def start(self, block: bool = True):
        """
        启动 WebSocket 连接
        
        Args:
            block: 是否阻塞当前线程
        """
        if self._running:
            logger.warning("Gateway is already running")
            return
        
        self._running = True
        
        # 创建 WebSocket 客户端
        self._ws_client = ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=self._event_handler,
            log_level=LogLevel.DEBUG if logging.getLogger().level == logging.DEBUG else LogLevel.INFO
        )
        
        logger.info(f"Starting Feishu WebSocket Gateway...")
        logger.info(f"App ID: {self.app_id[:10]}...")
        
        if block:
            # 在新线程中启动，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._ws_client.start)
        else:
            # 在后台线程启动
            threading.Thread(target=self._ws_client.start, daemon=True).start()
    
    async def stop(self):
        """停止网关"""
        self._running = False
        await self.api_client.close()
        logger.info("Feishu WebSocket Gateway stopped")
    
    async def reply(self, message_id: str, content: str, at_user: Optional[str] = None) -> Dict[str, Any]:
        """
        回复消息
        
        Args:
            message_id: 要回复的消息 ID
            content: 回复内容
            at_user: @ 用户的 ID（可选）
            
        Returns:
            API 响应结果
        """
        reply = FeishuReply(content=content, at_user_id=at_user)
        result = await self.api_client.reply_message(message_id, reply)
        if result.get("code") == 0:
            self._stats["messages_sent"] += 1
        return result
    
    async def send_to_chat(self, chat_id: str, content: str) -> Dict[str, Any]:
        """
        主动发送消息到聊天
        
        Args:
            chat_id: 聊天 ID
            content: 消息内容
            
        Returns:
            API 响应结果
        """
        reply = FeishuReply(content=content)
        result = await self.api_client.send_message(chat_id, reply)
        if result.get("code") == 0:
            self._stats["messages_sent"] += 1
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "running": self._running,
            "connected": self._connected,
            "handlers_registered": len(self._message_handlers)
        }


class FeishuKnightBridge:
    """
    飞书与 Knight Core 的桥接器
    
    将飞书消息转换为 Knight 任务，并将结果返回给飞书。
    """
    
    def __init__(
        self, 
        app_id: str, 
        app_secret: str,
        knight_core=None
    ):
        """
        初始化桥接器
        
        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            knight_core: KnightCore 实例（可选）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        
        # 获取 KnightCore 实例
        if knight_core is None:
            from ..core.knight_core import KnightCore
            self.knight_core = KnightCore()
        else:
            self.knight_core = knight_core
        
        # 创建飞书网关
        self.feishu_gateway = FeishuWebSocketGateway(app_id, app_secret)
        
        # 注册消息处理器
        self.feishu_gateway.register_message_handler(self._handle_message)
        
        # 会话映射
        self._user_sessions: Dict[str, str] = {}
    
    async def _handle_message(self, message: FeishuMessage, gateway: FeishuWebSocketGateway):
        """处理飞书消息"""
        user_id = message.sender_id
        content = message.content.strip()
        
        # 检查是否是命令
        if content.startswith("/"):
            await self._handle_command(content, message, gateway)
        else:
            # 普通消息，创建任务
            await self._handle_task(content, message, gateway)
    
    async def _handle_command(self, cmd: str, message: FeishuMessage, gateway: FeishuWebSocketGateway):
        """处理命令"""
        parts = cmd.split()
        command = parts[0].lower()
        
        if command == "/help":
            help_text = """🤖 Knight Bot 命令帮助

/task <描述> - 创建新任务
/status - 查看系统状态
/agents - 查看可用 Agent
/help - 显示此帮助信息

直接发送消息即可创建任务。"""
            await gateway.reply(message.message_id, help_text)
        
        elif command == "/status":
            stats = self.knight_core.get_stats()
            status_text = f"""📊 Knight 系统状态

待处理任务: {stats.get('pending_tasks', 0)}
运行中任务: {stats.get('running_tasks', 0)}
已完成任务: {stats.get('completed_tasks', 0)}
活跃会话: {stats.get('active_sessions', 0)}"""
            await gateway.reply(message.message_id, status_text)
        
        elif command == "/agents":
            agents = await self.knight_core.list_agents()
            agents_text = "🤖 可用 Agent\n\n"
            for agent in agents:
                status = "🟢" if agent.status == "idle" else "🔴"
                agents_text += f"{status} {agent.name} ({agent.type.value})\n"
                agents_text += f"   能力: {', '.join(agent.capabilities[:3])}\n\n"
            await gateway.reply(message.message_id, agents_text)
        
        elif command == "/task" and len(parts) > 1:
            task_desc = " ".join(parts[1:])
            await self._handle_task(task_desc, message, gateway)
        
        else:
            await gateway.reply(message.message_id, f"未知命令: {command}\n发送 /help 查看帮助")
    
    async def _handle_task(self, content: str, message: FeishuMessage, gateway: FeishuWebSocketGateway):
        """处理任务请求"""
        user_id = message.sender_id
        
        # 获取或创建会话
        if user_id not in self._user_sessions:
            session = await self.knight_core.create_session(metadata={"feishu_user": user_id})
            self._user_sessions[user_id] = session.id
        
        session_id = self._user_sessions[user_id]
        
        # 确认收到消息
        await gateway.reply(message.message_id, f"📝 已收到任务，正在处理...\n\n{content[:100]}{'...' if len(content) > 100 else ''}")
        
        try:
            # 创建任务
            from ..core.schemas import CreateTaskRequest, AgentType
            
            task_request = CreateTaskRequest(
                name=f"Feishu Task from {user_id[:8]}",
                description=content,
                agent_type=AgentType.AUTO,
                work_dir=f"/tmp/knight_feishu/{user_id}",
                session_id=session_id,
                metadata={
                    "source": "feishu",
                    "user_id": user_id,
                    "message_id": message.message_id
                }
            )
            
            task = await self.knight_core.create_task(task_request)
            
            # 启动任务
            await self.knight_core.start_task(task.task_id)
            
            # 等待任务完成并收集结果
            result_chunks = []
            async for chunk in self.knight_core.stream_task(task.task_id):
                if chunk.type == "text":
                    result_chunks.append(chunk.content)
                elif chunk.type == "done":
                    break
                elif chunk.type == "error":
                    await gateway.reply(message.message_id, f"❌ 任务执行出错: {chunk.content}")
                    return
            
            # 发送结果
            result_text = "".join(result_chunks)
            if result_text:
                # 截断过长的结果
                max_length = 2000
                if len(result_text) > max_length:
                    result_text = result_text[:max_length] + "\n\n... (结果已截断)"
                
                await gateway.reply(
                    message.message_id, 
                    f"✅ 任务完成\n\n{result_text}",
                    at_user=user_id
                )
            else:
                await gateway.reply(message.message_id, "✅ 任务已完成", at_user=user_id)
                
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await gateway.reply(message.message_id, f"❌ 任务执行失败: {str(e)}")
    
    async def start(self):
        """启动桥接器"""
        logger.info("Starting Feishu-Knight Bridge...")
        await self.feishu_gateway.start()
    
    async def stop(self):
        """停止桥接器"""
        await self.feishu_gateway.stop()


# 快捷启动函数
async def start_feishu_gateway(
    app_id: str,
    app_secret: str,
    knight_core=None,
    message_handler=None
) -> FeishuKnightBridge:
    """
    快速启动飞书网关
    
    Args:
        app_id: 飞书应用 ID
        app_secret: 飞书应用密钥
        knight_core: KnightCore 实例（可选）
        message_handler: 自定义消息处理器（可选）
        
    Returns:
        FeishuKnightBridge 实例
    """
    bridge = FeishuKnightBridge(app_id, app_secret, knight_core)
    
    if message_handler:
        bridge.feishu_gateway.register_message_handler(message_handler)
    
    await bridge.start()
    return bridge
