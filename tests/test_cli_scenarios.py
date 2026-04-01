#!/usr/bin/env python3
"""
Knight CLI 场景测试
运行方式: cd /mnt/d/lancer && python3 knight/test_cli_scenarios.py
"""
import subprocess
import sys
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# 获取项目路径
SCRIPT_DIR = Path(__file__).parent.absolute()  # /mnt/d/lancer/knight
PROJECT_DIR = SCRIPT_DIR.parent  # /mnt/d/lancer
KNIGHT_PACKAGE = SCRIPT_DIR  # knight 包目录

def run_knight(prompt, work_dir=None, timeout=120):
    """
    调用 Knight CLI 执行任务
    
    Args:
        prompt: 任务描述
        work_dir: 工作目录（可选）
        timeout: 超时时间（秒）
    
    Returns:
        dict: {success, stdout, stderr, duration, files_created}
    """
    # 构建命令
    cmd = [sys.executable, "-m", "knight", prompt]
    
    # 环境变量
    env = os.environ.copy()
    if work_dir:
        env['KNIGHT_WORK_DIR'] = work_dir
    
    start = datetime.now()
    
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,  # 必须从父目录运行
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        duration = (datetime.now() - start).total_seconds()
        
        # 检查工作目录生成的文件
        files_created = []
        if work_dir and os.path.exists(work_dir):
            for item in os.listdir(work_dir):
                item_path = os.path.join(work_dir, item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    files_created.append(f"{item} ({size} bytes)")
                elif os.path.isdir(item_path):
                    count = len(os.listdir(item_path))
                    files_created.append(f"{item}/ ({count} items)")
        
        return {
            "success": result.returncode == 0 and len(result.stdout) > 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "duration": duration,
            "files_created": files_created
        }
        
    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start).total_seconds()
        return {
            "success": False,
            "error": f"Timeout after {timeout}s",
            "duration": duration,
            "files_created": []
        }
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        return {
            "success": False,
            "error": str(e),
            "duration": duration,
            "files_created": []
        }


# ============ 测试场景定义 ============

SCENARIOS = [
    {
        "id": "S1",
        "name": "📝 单文件脚本 - Todo CLI",
        "description": "创建一个简单的待办事项命令行工具",
        "prompt": """Create a Python CLI todo list manager with these requirements:
1. Can add tasks: python todo.py add "Buy milk"
2. Can list tasks: python todo.py list
3. Can mark complete: python todo.py done 1
4. Store data in todo.json file
5. Include proper error handling
Save all code in a single file named todo.py""",
        "timeout": 120,
        "check_files": ["todo.py"]
    },
    {
        "id": "S2",
        "name": "📦 Python包 - Calculator",
        "description": "创建多文件 Python 包项目",
        "prompt": """Create a Python package named 'calculator' with this structure:
1. calculator/__init__.py - exports main functions
2. calculator/core.py - add, subtract, multiply, divide functions
3. calculator/cli.py - command line interface with argparse
4. tests/test_calculator.py - pytest test cases
5. setup.py - package configuration
Make divide() handle division by zero gracefully.""",
        "timeout": 180,
        "check_files": ["calculator/__init__.py", "calculator/core.py", "calculator/cli.py"]
    },
    {
        "id": "S3",
        "name": "📊 数据分析脚本",
        "description": "创建 CSV 数据分析工具",
        "prompt": """Create a Python script 'data_analyzer.py' that:
1. Reads a sample CSV file with columns: name, age, city
2. Calculates average age
3. Counts people per city
4. Outputs a summary report
5. Include a function to generate sample data
Save the script and create a sample data file.""",
        "timeout": 120,
        "check_files": ["data_analyzer.py"]
    },
    {
        "id": "S4",
        "name": "🔧 代码重构",
        "description": "分析和改进现有代码",
        "prompt": """Read the file at /mnt/d/lancer/knight/core/workflow_engine.py, analyze it and:
1. Identify 2 design patterns used
2. Suggest 2 concrete improvements  
3. Provide improved code examples
Output your analysis as structured markdown.""",
        "timeout": 60,
        "work_dir": "/mnt/d/lancer/knight",  # 使用固定目录
        "check_files": []  # 不需要创建文件
    },
]


def run_scenario(scenario):
    """运行单个测试场景"""
    print(f"\n{'='*70}")
    print(f"🎯 场景 {scenario['id']}: {scenario['name']}")
    print(f"{'='*70}")
    print(f"描述: {scenario['description']}")
    print(f"提示词预览: {scenario['prompt'][:100]}...")
    
    # 准备工作目录
    if scenario.get('work_dir'):
        work_dir = scenario['work_dir']
        is_temp = False
        print(f"工作目录: {work_dir} (固定)")
    else:
        work_dir = tempfile.mkdtemp(prefix=f"knight_{scenario['id']}_")
        print(f"工作目录: {work_dir} (临时)")
        is_temp = True
    
    os.makedirs(work_dir, exist_ok=True)
    
    # 执行命令
    result = run_knight(scenario['prompt'], work_dir, scenario['timeout'])
    
    # 显示结果
    print(f"\n{'─'*70}")
    if result['success']:
        print(f"✅ 执行成功 ({result['duration']:.1f}s)")
        
        # 显示输出
        stdout = result['stdout']
        if stdout:
            print(f"\n📤 输出预览:")
            lines = stdout.strip().split('\n')
            # 跳过前两行（标题和空行），显示内容
            content_lines = [l for l in lines[2:] if l.strip()]
            for line in content_lines[:15]:
                print(f"   {line}")
            if len(content_lines) > 15:
                print(f"   ... ({len(content_lines) - 15} more lines)")
        
        # 显示生成的文件
        if result['files_created']:
            print(f"\n📁 生成的文件:")
            for f in result['files_created'][:10]:
                print(f"   ✓ {f}")
        
        # 验证期望的文件
        if scenario.get('check_files'):
            print(f"\n🔍 验证期望文件:")
            for expected in scenario['check_files']:
                path = os.path.join(work_dir, expected)
                exists = os.path.exists(path)
                icon = "✅" if exists else "❌"
                print(f"   {icon} {expected}")
                
    else:
        print(f"❌ 执行失败 ({result['duration']:.1f}s)")
        if 'error' in result:
            print(f"错误: {result['error']}")
        if result.get('stderr'):
            print(f"Stderr: {result['stderr'][:200]}")
    
    return {
        **result,
        "scenario": scenario,
        "work_dir": work_dir,
        "is_temp": is_temp
    }


def print_report(results):
    """打印测试报告"""
    print(f"\n\n{'='*70}")
    print("📊 测试报告摘要")
    print(f"{'='*70}")
    
    total = len(results)
    success = sum(1 for r in results if r['success'])
    failed = total - success
    total_time = sum(r['duration'] for r in results)
    
    print(f"\n总计: {total} 个场景")
    print(f"✅ 成功: {success}")
    print(f"❌ 失败: {failed}")
    print(f"⏱️  总耗时: {total_time:.1f}s")
    print(f"📈 成功率: {success/total*100:.1f}%")
    
    print(f"\n详细结果:")
    for r in results:
        status = "✅" if r['success'] else "❌"
        s = r['scenario']
        print(f"  {status} {s['id']}: {s['name']} ({r['duration']:.1f}s)")
    
    # 临时目录提示
    temp_dirs = [r['work_dir'] for r in results if r.get('is_temp')]
    if temp_dirs:
        print(f"\n📝 临时工作目录:")
        for d in temp_dirs:
            print(f"   {d}")
        print(f"\n💡 提示: 可以手动检查这些目录中的生成文件")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Knight CLI 场景测试')
    parser.add_argument('-s', '--scenario', help='运行指定场景ID (如: S1,S2)')
    parser.add_argument('-c', '--cleanup', action='store_true', help='清理临时目录')
    parser.add_argument('-l', '--list', action='store_true', help='列出场景')
    
    args = parser.parse_args()
    
    if args.list:
        print("\n📋 可用测试场景:")
        for s in SCENARIOS:
            print(f"\n  {s['id']}: {s['name']}")
            print(f"      描述: {s['description']}")
            print(f"      超时: {s['timeout']}s")
        return
    
    # 选择场景
    scenarios = SCENARIOS
    if args.scenario:
        ids = [id.strip() for id in args.scenario.split(',')]
        scenarios = [s for s in SCENARIOS if s['id'] in ids]
    
    # 验证目录
    if not os.path.exists(PROJECT_DIR / 'knight' / '__init__.py'):
        print(f"❌ 错误: 必须在 {PROJECT_DIR} 或其子目录运行此脚本")
        print(f"   正确运行方式: cd {PROJECT_DIR} && python3 knight/test_cli_scenarios.py")
        return 1
    
    # 运行测试
    print(f"🏰 Knight System CLI 场景测试")
    print(f"项目目录: {PROJECT_DIR}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    try:
        for scenario in scenarios:
            result = run_scenario(scenario)
            results.append(result)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    
    # 打印报告
    print_report(results)
    
    # 清理
    if args.cleanup:
        print(f"\n🧹 清理临时目录...")
        for r in results:
            if r.get('is_temp') and os.path.exists(r['work_dir']):
                shutil.rmtree(r['work_dir'])
                print(f"   已删除: {r['work_dir']}")
    
    return 0 if all(r['success'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
