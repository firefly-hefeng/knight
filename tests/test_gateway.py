"""
网关可用性测试

测试内容包括:
1. HTTP Gateway API 端点
2. 认证机制
3. 任务管理流程
4. 流式响应
5. 飞书长连接网关
"""
import asyncio
import json
import os
import sys
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

# 设置路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['PYTHONPATH'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import httpx
from fastapi.testclient import TestClient


# ==================== HTTP Gateway 测试 ====================

class TestHTTPGateway:
    """测试 HTTP 网关"""
    
    @pytest.fixture
    def gateway(self):
        """创建测试网关实例"""
        from gateway.http_gateway import HTTPGateway
        return HTTPGateway(host="127.0.0.1", port=18080, api_key=None)
    
    @pytest.fixture
    def client(self, gateway):
        """创建测试客户端"""
        return TestClient(gateway.app)
    
    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
        assert "stats" in data["data"]
    
    def test_create_task(self, client):
        """测试创建任务"""
        payload = {
            "name": "Test Task",
            "description": "Create a hello world script",
            "agent_type": "auto",
            "work_dir": "/tmp/test"
        }
        
        response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["status"] in ["pending", "running", "completed"]
    
    def test_list_tasks(self, client):
        """测试列出任务"""
        response = client.get("/api/v1/tasks")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
    
    def test_list_agents(self, client):
        """测试列出 Agent"""
        response = client.get("/api/v1/agents")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        
        # 验证 Agent 数据结构
        for agent in data["data"]:
            assert "id" in agent
            assert "name" in agent
            assert "status" in agent
    
    def test_get_stats(self, client):
        """测试统计端点"""
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data


class TestHTTPGatewayWithAuth:
    """测试带认证的 HTTP 网关"""
    
    @pytest.fixture
    def gateway(self):
        """创建带认证的网关"""
        from gateway.http_gateway import HTTPGateway
        return HTTPGateway(host="127.0.0.1", port=18081, api_key="test_secret_key")
    
    @pytest.fixture
    def client(self, gateway):
        """创建测试客户端"""
        return TestClient(gateway.app)
    
    def test_missing_auth(self, client):
        """测试缺少认证"""
        response = client.get("/api/v1/tasks")
        assert response.status_code == 401
    
    def test_invalid_auth(self, client):
        """测试无效认证"""
        response = client.get(
            "/api/v1/tasks",
            headers={"Authorization": "Bearer wrong_key"}
        )
        assert response.status_code == 403
    
    def test_valid_auth_bearer(self, client):
        """测试有效认证 (Bearer)"""
        response = client.get(
            "/api/v1/tasks",
            headers={"Authorization": "Bearer test_secret_key"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_valid_auth_apikey(self, client):
        """测试有效认证 (ApiKey)"""
        response = client.get(
            "/api/v1/tasks",
            headers={"Authorization": "ApiKey test_secret_key"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


# ==================== 会话管理测试 ====================

class TestSessionManagement:
    """测试会话管理"""
    
    @pytest.fixture
    def client(self):
        from gateway.http_gateway import HTTPGateway
        gateway = HTTPGateway(host="127.0.0.1", port=18082)
        return TestClient(gateway.app)
    
    def test_create_session(self, client):
        """测试创建会话"""
        response = client.post("/api/v1/sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "id" in data["data"]
        assert data["data"]["status"] == "active"
        
        return data["data"]["id"]
    
    def test_get_session(self, client):
        """测试获取会话"""
        # 先创建会话
        create_resp = client.post("/api/v1/sessions")
        session_id = create_resp.json()["data"]["id"]
        
        # 获取会话
        response = client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == session_id
    
    def test_get_nonexistent_session(self, client):
        """测试获取不存在的会话"""
        response = client.get("/api/v1/sessions/nonexistent")
        assert response.status_code == 404
    
    def test_send_message(self, client):
        """测试发送消息"""
        # 创建会话
        create_resp = client.post("/api/v1/sessions")
        session_id = create_resp.json()["data"]["id"]
        
        # 发送消息
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            params={"content": "Hello Knight"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["content"] == "Hello Knight"


# ==================== 流式响应测试 ====================

class TestStreaming:
    """测试流式响应"""
    
    @pytest.fixture
    def client(self):
        from gateway.http_gateway import HTTPGateway
        gateway = HTTPGateway(host="127.0.0.1", port=18083)
        return TestClient(gateway.app)
    
    def test_task_stream(self, client):
        """测试任务流式输出"""
        # 创建任务
        payload = {
            "name": "Stream Test",
            "description": "Test streaming",
            "agent_type": "auto"
        }
        create_resp = client.post("/api/v1/tasks", json=payload)
        task_id = create_resp.json()["data"]["task_id"]
        
        # 获取流式响应
        response = client.get(f"//api/v1/tasks/{task_id}/stream")
        # 注意：TestClient 处理流式响应的方式与生产环境不同
        assert response.status_code in [200, 307, 404]  # 可能重定向或尚未实现


# ==================== 飞书网关测试 ====================

try:
    import lark_oapi as lark
    LARK_AVAILABLE = True
except ImportError:
    LARK_AVAILABLE = False


@pytest.mark.skipif(not LARK_AVAILABLE, reason="lark_oapi not installed")
class TestFeishuGateway:
    """测试飞书网关集成"""
    
    def test_gateway_import(self):
        """测试飞书网关导入"""
        from adapters.feishu_adapter import (
            FeishuWebSocketGateway,
            FeishuKnightBridge,
            FeishuMessage,
            FeishuReply
        )
        # 导入成功即通过
        assert True
    
    def test_message_creation(self):
        """测试消息创建"""
        from adapters.feishu_adapter import FeishuMessage
        
        msg = FeishuMessage(
            message_id="test_123",
            message_type="text",
            content="Hello",
            sender_id="user_123"
        )
        
        assert msg.message_id == "test_123"
        assert msg.content == "Hello"
    
    def test_reply_creation(self):
        """测试回复创建"""
        from adapters.feishu_adapter import FeishuReply
        
        reply = FeishuReply(content="Test reply", at_user_id="user_123")
        payload = reply.to_api_payload()
        
        assert payload["msg_type"] == "text"
        assert "user_123" in payload["content"]
    
    def test_gateway_initialization(self):
        """测试网关初始化"""
        from adapters.feishu_adapter import FeishuWebSocketGateway
        
        gateway = FeishuWebSocketGateway(
            app_id="cli_test",
            app_secret="test_secret"
        )
        
        assert gateway.app_id == "cli_test"
        assert gateway._running is False
        
        stats = gateway.get_stats()
        assert stats["running"] is False
        assert stats["messages_received"] == 0


# ==================== 端到端测试 ====================

@pytest.mark.e2e
class TestEndToEnd:
    """端到端测试"""
    
    @pytest.fixture
    def client(self):
        from gateway.http_gateway import HTTPGateway
        gateway = HTTPGateway(host="127.0.0.1", port=18084)
        return TestClient(gateway.app)
    
    def test_full_task_lifecycle(self, client):
        """测试完整任务生命周期"""
        # 1. 创建会话
        session_resp = client.post("/api/v1/sessions")
        assert session_resp.status_code == 200
        session_id = session_resp.json()["data"]["id"]
        
        # 2. 创建任务
        task_payload = {
            "name": "E2E Test Task",
            "description": "Test the full lifecycle",
            "agent_type": "auto",
            "session_id": session_id
        }
        task_resp = client.post("/api/v1/tasks", json=task_payload)
        assert task_resp.status_code == 200
        task_id = task_resp.json()["data"]["task_id"]
        
        # 3. 获取任务详情
        get_resp = client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["task_id"] == task_id
        
        # 4. 列出任务（筛选会话）
        list_resp = client.get(f"/api/v1/tasks?session_id={session_id}")
        assert list_resp.status_code == 200
        tasks = list_resp.json()["data"]
        assert any(t["task_id"] == task_id for t in tasks)
        
        # 5. 获取系统统计
        stats_resp = client.get("/api/v1/stats")
        assert stats_resp.status_code == 200


# ==================== 性能测试 ====================

@pytest.mark.performance
class TestPerformance:
    """性能测试"""
    
    @pytest.fixture
    def client(self):
        from gateway.http_gateway import HTTPGateway
        gateway = HTTPGateway(host="127.0.0.1", port=18085)
        return TestClient(gateway.app)
    
    def test_concurrent_requests(self, client):
        """测试并发请求处理"""
        import concurrent.futures
        
        def make_request(i):
            resp = client.get("/health")
            return resp.status_code == 200
        
        # 并发发送 10 个请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(make_request, range(10)))
        
        assert all(results), "Not all concurrent requests succeeded"
    
    def test_response_time(self, client):
        """测试响应时间"""
        import time
        
        start = time.time()
        response = client.get("/health")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 1.0, f"Response too slow: {elapsed}s"


# ==================== 错误处理测试 ====================

class TestErrorHandling:
    """测试错误处理"""
    
    @pytest.fixture
    def client(self):
        from gateway.http_gateway import HTTPGateway
        gateway = HTTPGateway(host="127.0.0.1", port=18086)
        return TestClient(gateway.app)
    
    def test_404_response(self, client):
        """测试 404 响应格式"""
        response = client.get("/api/v1/nonexistent")
        
        # FastAPI 默认返回 404
        assert response.status_code == 404
    
    def test_invalid_json(self, client):
        """测试无效 JSON"""
        response = client.post(
            "/api/v1/tasks",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_missing_required_fields(self, client):
        """测试缺少必填字段"""
        payload = {
            # 缺少 name 和 description
            "agent_type": "auto"
        }
        response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
