"""测试API服务器"""
import requests
import json

def test_api():
    """测试API端点"""
    url = 'http://localhost:5000/api/execute'

    payload = {
        'prompt': 'Create a hello.py file that prints Hello World',
        'work_dir': '/tmp/knight_web_test'
    }

    print("🏰 Testing Knight API\n")
    print(f"Request: {payload['prompt']}\n")

    try:
        response = requests.post(url, json=payload, timeout=60)
        data = response.json()

        print(f"Status: {response.status_code}")
        print(f"Tasks: {len(data.get('tasks', []))}\n")

        for i, task in enumerate(data.get('tasks', []), 1):
            print(f"Task {i}:")
            print(f"  Status: {task['status']}")
            print(f"  Agent: {task['agent_type']}")
            print(f"  Prompt: {task['prompt'][:50]}...")

    except requests.exceptions.ConnectionError:
        print("❌ Error: Server not running")
        print("Start with: python web/api/server.py")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    test_api()
