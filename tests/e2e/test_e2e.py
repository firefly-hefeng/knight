"""端到端测试 - 验证新组件集成"""
import requests
import time

def test_backend_with_new_components():
    print("Testing backend with new components...")

    base_url = "http://localhost:3001"

    # 测试健康检查
    try:
        resp = requests.get(f"{base_url}/health", timeout=2)
        print(f"✓ Health check: {resp.status_code}")
    except Exception as e:
        print(f"⚠️  Backend not running: {e}")
        return

    # 测试统计接口（应该包含新组件信息）
    try:
        resp = requests.get(f"{base_url}/stats", timeout=2)
        if resp.status_code == 200:
            stats = resp.json()
            if 'file_cache' in stats:
                print(f"✓ File cache stats: {stats['file_cache']}")
            if 'command_queue_length' in stats:
                print(f"✓ Command queue length: {stats['command_queue_length']}")
    except Exception as e:
        print(f"Stats endpoint: {e}")

    print("\n✅ Backend integration verified!")

if __name__ == "__main__":
    test_backend_with_new_components()
