#!/usr/bin/env python3
"""
Knight CLI 场景测试 - 简化版
直接使用 python -m knight 运行
"""
import subprocess
import sys
import os
import tempfile
import shutil
from datetime import datetime

KNIGHT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(KNIGHT_DIR)

TEST_SCENARIOS = [
    {
        "id": "S1",
        "name": "单文件Python脚本",
        "prompt": "Create a Python CLI todo list manager that can add, list, and complete tasks. Save data to a JSON file.",
        "timeout": 120
    },
    {
        "id": "S2", 
        "name": "Python包项目",
        "prompt": "Create a Python package named 'calculator' with __init__.py, core.py (add/subtract/multiply/divide), cli.py with argparse.",
        "timeout": 180
    },
]


def run_cli(prompt, timeout):
    """直接调用 knight CLI"""
    cmd = [sys.executable, "-m", "knight", prompt]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=KNIGHT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout", "stdout": "", "stderr": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": ""}


def main():
    print("🏰 Knight System CLI 快速测试\n")
    
    for scenario in TEST_SCENARIOS:
        print(f"\n{'='*60}")
        print(f"📝 {scenario['id']}: {scenario['name']}")
        print(f"{'='*60}")
        print(f"提示: {scenario['prompt'][:80]}...")
        
        start = datetime.now()
        result = run_cli(scenario['prompt'], scenario['timeout'])
        duration = (datetime.now() - start).total_seconds()
        
        if result['success']:
            print(f"\n✅ 成功 ({duration:.1f}s)")
            print(f"输出: {result['stdout'][:300]}...")
        else:
            print(f"\n❌ 失败 ({duration:.1f}s)")
            if 'error' in result:
                print(f"错误: {result['error']}")
            if result['stderr']:
                print(f"stderr: {result['stderr'][:200]}")


if __name__ == '__main__':
    main()
