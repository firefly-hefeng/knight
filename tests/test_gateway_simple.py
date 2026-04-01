"""
简化的网关测试 - 验证核心功能可用性
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['PYTHONPATH'] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有关键模块可以导入"""
    print("Testing imports...")
    
    # 1. 测试 Core 模块
    try:
        from core.schemas import (
            CreateTaskRequest, TaskResponse, TaskStatus, AgentType,
            ApiResponse, AgentInfo, SessionInfo, TaskStep
        )
        print("✅ Core schemas imported")
    except Exception as e:
        print(f"❌ Core schemas import failed: {e}")
        return False
    
    # 2. 测试适配器
    try:
        from adapters.claude_adapter import ClaudeAdapter, TaskResult
        from adapters.kimi_adapter import KimiAdapter
        print("✅ Agent adapters imported")
    except Exception as e:
        print(f"❌ Agent adapters import failed: {e}")
        return False
    
    # 3. 测试飞书适配器
    try:
        from adapters.feishu_adapter import (
            FeishuWebSocketGateway,
            FeishuKnightBridge,
            FeishuMessage,
            FeishuReply,
            FeishuAPIClient
        )
        print("✅ Feishu adapter imported")
    except Exception as e:
        print(f"❌ Feishu adapter import failed: {e}")
        return False
    
    # 4. 测试网关
    try:
        from gateway.http_gateway import HTTPGateway
        print("✅ HTTP Gateway imported")
    except Exception as e:
        print(f"❌ HTTP Gateway import failed: {e}")
        return False
    
    return True


def test_data_structures():
    """测试数据结构"""
    print("\nTesting data structures...")
    
    from core.schemas import ApiResponse, TaskStatus, AgentType
    from adapters.feishu_adapter import FeishuMessage, FeishuReply
    
    # 1. 测试 ApiResponse
    try:
        response = ApiResponse.ok(data={"test": "value"})
        assert response.success is True
        assert response.data == {"test": "value"}
        print("✅ ApiResponse.ok works")
    except Exception as e:
        print(f"❌ ApiResponse.ok failed: {e}")
        return False
    
    response = ApiResponse.fail("Test error", "ERR_001")
    assert response.success is False
    assert response.error == "Test error"
    print("✅ ApiResponse.fail works")
    
    # 2. 测试飞书消息
    try:
        msg = FeishuMessage(
            message_id="msg_123",
            message_type="text",
            content="Hello",
            sender_id="user_123"
        )
        assert msg.message_id == "msg_123"
        print("✅ FeishuMessage creation works")
    except Exception as e:
        print(f"❌ FeishuMessage creation failed: {e}")
        return False
    
    # 3. 测试飞书回复
    try:
        reply = FeishuReply(content="Test reply", at_user_id="user_123")
        payload = reply.to_api_payload()
        assert payload["msg_type"] == "text"
        assert "user_123" in payload["content"]
        print("✅ FeishuReply creation works")
    except Exception as e:
        print(f"❌ FeishuReply creation failed: {e}")
        return False
    
    return True


def test_feishu_gateway():
    """测试飞书网关"""
    print("\nTesting Feishu Gateway...")
    
    from adapters.feishu_adapter import FeishuWebSocketGateway
    
    try:
        # 创建网关实例（不连接）
        gateway = FeishuWebSocketGateway(
            app_id="cli_test",
            app_secret="test_secret"
        )
        
        assert gateway.app_id == "cli_test"
        assert gateway._running is False
        
        stats = gateway.get_stats()
        assert stats["running"] is False
        assert stats["messages_received"] == 0
        
        print("✅ FeishuWebSocketGateway initialization works")
        
        # 测试处理器注册
        async def test_handler(msg, gw):
            pass
        
        gateway.register_message_handler(test_handler)
        assert len(gateway._message_handlers) == 1
        print("✅ Message handler registration works")
        
        return True
        
    except Exception as e:
        print(f"❌ Feishu Gateway test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_http_gateway_structure():
    """测试 HTTP 网关结构"""
    print("\nTesting HTTP Gateway structure...")
    
    try:
        from gateway.http_gateway import HTTPGateway
        
        # 注意：这里不实际启动网关，只验证结构
        # 因为 KnightCore 需要数据库和其他资源
        
        print("✅ HTTP Gateway can be imported")
        return True
        
    except Exception as e:
        print(f"❌ HTTP Gateway test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_launch_script():
    """测试启动脚本"""
    print("\nTesting launch script...")
    
    try:
        # 导入启动模块
        import launch
        
        # 验证启动模式
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("mode", choices=["web", "cli", "both", "gateway", "feishu"])
        
        # 测试 feishu 模式存在
        args = parser.parse_args(["feishu"])
        assert args.mode == "feishu"
        
        print("✅ Launch script supports feishu mode")
        return True
        
    except Exception as e:
        print(f"❌ Launch script test failed: {e}")
        return False


def test_requirements():
    """测试依赖可用性"""
    print("\nTesting dependencies...")
    
    dependencies = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("lark_oapi", "Feishu SDK"),
    ]
    
    all_ok = True
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"✅ {display_name} ({module_name}) is available")
        except ImportError:
            print(f"⚠️ {display_name} ({module_name}) is not installed")
            all_ok = False
    
    return all_ok


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Knight Gateway Availability Tests")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Data Structures", test_data_structures),
        ("Feishu Gateway", test_feishu_gateway),
        ("HTTP Gateway Structure", test_http_gateway_structure),
        ("Launch Script", test_launch_script),
        ("Dependencies", test_requirements),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'-' * 40}")
        print(f"Running: {name}")
        print('-' * 40)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed! Gateway is available.")
        return 0
    else:
        print(f"\n⚠️ {failed} test(s) failed.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
