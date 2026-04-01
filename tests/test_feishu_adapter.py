"""
飞书适配器测试

测试内容包括:
1. 数据结构解析 (FeishuMessage, FeishuReply)
2. API 客户端 (FeishuAPIClient)
3. WebSocket 网关 (FeishuWebSocketGateway)
4. Knight 桥接器 (FeishuKnightBridge)

注意: 需要真实飞书凭证的测试标记为 @require_credentials
"""
import asyncio
import json
import os
import sys
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置 Python 路径环境变量
os.environ['PYTHONPATH'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 检查 lark_oapi 是否可用
try:
    import lark_oapi as lark
    LARK_AVAILABLE = True
except ImportError:
    LARK_AVAILABLE = False
    print("Warning: lark_oapi not installed, skipping Feishu tests")


# ==================== Fixtures ====================

@pytest.fixture
def mock_lark_module():
    """模拟 lark_oapi 模块"""
    if not LARK_AVAILABLE:
        pytest.skip("lark_oapi not installed")
    return lark


@pytest.fixture
def sample_message_data():
    """示例飞书消息数据"""
    return {
        "event": {
            "message": {
                "message_id": "om_1234567890",
                "message_type": "text",
                "content": '{"text": "Hello Knight"}',
                "chat_id": "oc_1234567890",
                "chat_type": "p2p"
            },
            "sender": {
                "sender_id": {
                    "user_id": "ou_1234567890"
                }
            }
        }
    }


@pytest.fixture
def mock_knight_core():
    """模拟 KnightCore"""
    core = Mock()
    core.create_task = AsyncMock(return_value=Mock(
        task_id="task_123",
        status="pending"
    ))
    core.start_task = AsyncMock()
    core.get_stats = Mock(return_value={
        "pending_tasks": 0,
        "running_tasks": 0,
        "completed_tasks": 5
    })
    core.list_agents = AsyncMock(return_value=[
        Mock(id="claude", name="Claude", type=Mock(value="claude"), 
             status="idle", capabilities=["coding", "writing"]),
        Mock(id="kimi", name="Kimi", type=Mock(value="kimi"),
             status="busy", capabilities=["search"])
    ])
    return core


# ==================== 单元测试: 数据结构 ====================

@pytest.mark.skipif(not LARK_AVAILABLE, reason="lark_oapi not installed")
class TestFeishuDataStructures:
    """测试飞书数据结构"""
    
    def test_feishu_reply_text(self):
        """测试文本回复构造"""
        from adapters.feishu_adapter import FeishuReply
        
        reply = FeishuReply(content="Hello World")
        payload = reply.to_api_payload()
        
        assert payload["msg_type"] == "text"
        assert "Hello World" in payload["content"]
    
    def test_feishu_reply_with_at(self):
        """测试带 @ 的回复"""
        from adapters.feishu_adapter import FeishuReply
        
        reply = FeishuReply(content="Hello", at_user_id="ou_123")
        payload = reply.to_api_payload()
        
        assert payload["msg_type"] == "text"
        content_dict = json.loads(payload["content"])
        assert "<at user_id=" in content_dict["text"]
    
    def test_feishu_reply_markdown(self):
        """测试 Markdown 回复"""
        from adapters.feishu_adapter import FeishuReply
        
        reply = FeishuReply(content="# Title\nContent", msg_type="markdown")
        payload = reply.to_api_payload()
        
        assert payload["msg_type"] == "interactive"
        assert "card" in payload


# ==================== 单元测试: API 客户端 ====================

@pytest.mark.skipif(not LARK_AVAILABLE, reason="lark_oapi not installed")
class TestFeishuAPIClient:
    """测试飞书 API 客户端"""
    
    @pytest.mark.asyncio
    async def test_token_caching(self):
        """测试令牌缓存"""
        from adapters.feishu_adapter import FeishuAPIClient
        
        client = FeishuAPIClient("test_id", "test_secret")
        
        # 模拟初始状态
        assert client._token is None
        
        # 手动设置令牌
        client._token = "cached_token"
        client._token_expire_time = float('inf')
        
        # 应该返回缓存的令牌
        token = await client._get_access_token()
        assert token == "cached_token"
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """测试客户端初始化"""
        from adapters.feishu_adapter import FeishuAPIClient
        
        client = FeishuAPIClient("cli_test", "secret_test")
        
        assert client.app_id == "cli_test"
        assert client.app_secret == "secret_test"
        assert client._token is None
        
        await client.close()


# ==================== 单元测试: WebSocket 网关 ====================

@pytest.mark.skipif(not LARK_AVAILABLE, reason="lark_oapi not installed")
class TestFeishuWebSocketGateway:
    """测试飞书 WebSocket 网关"""
    
    def test_gateway_initialization(self):
        """测试网关初始化"""
        from adapters.feishu_adapter import FeishuWebSocketGateway
        
        gateway = FeishuWebSocketGateway(
            app_id="cli_test",
            app_secret="secret_test"
        )
        
        assert gateway.app_id == "cli_test"
        assert gateway.app_secret == "secret_test"
        assert gateway._running is False
        assert len(gateway._message_handlers) == 0
        
        # 统计
        stats = gateway.get_stats()
        assert stats["running"] is False
        assert stats["messages_received"] == 0
    
    def test_register_handlers(self):
        """测试处理器注册"""
        from adapters.feishu_adapter import FeishuWebSocketGateway
        
        gateway = FeishuWebSocketGateway("cli_test", "secret_test")
        
        # 注册消息处理器
        async def handler(msg, gw):
            pass
        
        gateway.register_message_handler(handler)
        assert len(gateway._message_handlers) == 1
        
        # 注册错误处理器
        def error_handler(e):
            pass
        
        gateway.register_error_handler(error_handler)
        assert len(gateway._error_handlers) == 1
    
    @pytest.mark.asyncio
    async def test_reply_message(self):
        """测试回复消息"""
        from adapters.feishu_adapter import FeishuWebSocketGateway
        
        gateway = FeishuWebSocketGateway("cli_test", "secret_test")
        
        # 模拟 API 调用
        with patch.object(
            gateway.api_client, 
            'reply_message', 
            return_value={"code": 0, "msg": "ok"}
        ) as mock_reply:
            result = await gateway.reply("msg_123", "Hello")
            
            assert result["code"] == 0
            assert gateway._stats["messages_sent"] == 1
            mock_reply.assert_called_once()


# ==================== 集成测试: Knight 桥接器 ====================

@pytest.mark.skipif(not LARK_AVAILABLE, reason="lark_oapi not installed")
class TestFeishuKnightBridge:
    """测试飞书-Knight 桥接器"""
    
    def test_bridge_initialization(self, mock_knight_core):
        """测试桥接器初始化"""
        from adapters.feishu_adapter import FeishuKnightBridge
        
        bridge = FeishuKnightBridge(
            app_id="cli_test",
            app_secret="secret_test",
            knight_core=mock_knight_core
        )
        
        assert bridge.app_id == "cli_test"
        assert bridge.knight_core == mock_knight_core
        assert bridge.feishu_gateway is not None
    
    @pytest.mark.asyncio
    async def test_handle_help_command(self, mock_knight_core):
        """测试帮助命令处理"""
        from adapters.feishu_adapter import FeishuKnightBridge, FeishuMessage
        
        bridge = FeishuKnightBridge(
            app_id="cli_test",
            app_secret="secret_test",
            knight_core=mock_knight_core
        )
        
        # 模拟消息
        message = FeishuMessage(
            message_id="msg_123",
            message_type="text",
            content="/help",
            sender_id="user_123"
        )
        
        # 模拟回复
        with patch.object(
            bridge.feishu_gateway,
            'reply',
            return_value={"code": 0}
        ) as mock_reply:
            await bridge._handle_command("/help", message, bridge.feishu_gateway)
            
            mock_reply.assert_called_once()
            call_args = mock_reply.call_args
            assert "msg_123" in str(call_args)
            assert "帮助" in str(call_args) or "help" in str(call_args).lower()
    
    @pytest.mark.asyncio
    async def test_handle_status_command(self, mock_knight_core):
        """测试状态命令处理"""
        from adapters.feishu_adapter import FeishuKnightBridge, FeishuMessage
        
        bridge = FeishuKnightBridge(
            app_id="cli_test",
            app_secret="secret_test",
            knight_core=mock_knight_core
        )
        
        message = FeishuMessage(
            message_id="msg_123",
            message_type="text",
            content="/status",
            sender_id="user_123"
        )
        
        with patch.object(
            bridge.feishu_gateway,
            'reply',
            return_value={"code": 0}
        ) as mock_reply:
            await bridge._handle_command("/status", message, bridge.feishu_gateway)
            
            mock_knight_core.get_stats.assert_called_once()
            mock_reply.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_agents_command(self, mock_knight_core):
        """测试 Agent 列表命令"""
        from adapters.feishu_adapter import FeishuKnightBridge, FeishuMessage
        
        bridge = FeishuKnightBridge(
            app_id="cli_test",
            app_secret="secret_test",
            knight_core=mock_knight_core
        )
        
        message = FeishuMessage(
            message_id="msg_123",
            message_type="text",
            content="/agents",
            sender_id="user_123"
        )
        
        with patch.object(
            bridge.feishu_gateway,
            'reply',
            return_value={"code": 0}
        ) as mock_reply:
            await bridge._handle_command("/agents", message, bridge.feishu_gateway)
            
            mock_knight_core.list_agents.assert_called_once()
            mock_reply.assert_called_once()


# ==================== 端到端测试 ====================

@pytest.mark.skipif(not LARK_AVAILABLE, reason="lark_oapi not installed")
@pytest.mark.integration
class TestFeishuIntegration:
    """集成测试 - 需要真实凭证"""
    
    @pytest.fixture
    def credentials(self):
        """获取飞书凭证"""
        app_id = os.environ.get("FEISHU_APP_ID")
        app_secret = os.environ.get("FEISHU_APP_SECRET")
        
        if not app_id or not app_secret:
            pytest.skip("Feishu credentials not configured")
        
        return app_id, app_secret
    
    @pytest.mark.asyncio
    async def test_real_gateway_connection(self, credentials):
        """测试真实网关连接（短暂）"""
        from adapters.feishu_adapter import FeishuWebSocketGateway
        
        app_id, app_secret = credentials
        
        gateway = FeishuWebSocketGateway(
            app_id=app_id,
            app_secret=app_secret
        )
        
        # 注册测试处理器
        received_messages = []
        
        async def test_handler(msg, gw):
            received_messages.append(msg)
        
        gateway.register_message_handler(test_handler)
        
        # 验证初始化
        assert gateway.get_stats()["handlers_registered"] == 1
        
        # 注意：不实际启动连接，因为这会阻塞
        print(f"\nGateway initialized with App ID: {app_id[:10]}...")


# ==================== 模拟测试: 完整流程 ====================

@pytest.mark.asyncio
@pytest.mark.skipif(not LARK_AVAILABLE, reason="lark_oapi not installed")
async def test_full_flow_mock():
    """测试完整流程（模拟）"""
    from adapters.feishu_adapter import (
        FeishuKnightBridge, FeishuMessage, FeishuWebSocketGateway
    )
    
    # 创建模拟的 KnightCore
    mock_core = Mock()
    mock_core.create_session = AsyncMock(return_value=Mock(id="session_123"))
    mock_core.create_task = AsyncMock(return_value=Mock(task_id="task_123"))
    mock_core.start_task = AsyncMock()
    
    # 模拟流式输出
    async def mock_stream(task_id):
        yield Mock(type="text", content="Processing...")
        yield Mock(type="done", content="Task completed!")
    
    mock_core.stream_task = mock_stream
    
    # 创建桥接器
    bridge = FeishuKnightBridge(
        app_id="cli_test",
        app_secret="secret_test",
        knight_core=mock_core
    )
    
    # 模拟消息
    message = FeishuMessage(
        message_id="msg_123",
        message_type="text",
        content="Create a hello world Python script",
        sender_id="user_123",
        chat_id="chat_123"
    )
    
    # 模拟回复
    with patch.object(
        bridge.feishu_gateway,
        'reply',
        return_value={"code": 0}
    ) as mock_reply:
        # 处理任务
        await bridge._handle_task(message.content, message, bridge.feishu_gateway)
        
        # 验证调用
        mock_core.create_session.assert_called_once()
        mock_core.create_task.assert_called_once()
        mock_core.start_task.assert_called_once_with("task_123")
        
        # 应该有确认消息和结果消息
        assert mock_reply.call_count >= 2


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
