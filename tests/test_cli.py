#!/usr/bin/env python3
"""CLI 场景测试脚本"""
import sys
import os
import asyncio
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# 必须在工作目录运行
KNIGHT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(KNIGHT_DIR)

# 使用 -m 方式导入
sys.path.insert(0, KNIGHT_DIR)

# 场景定义
TEST_SCENARIOS = [
    {
        "id": "S1",
        "name": "单文件Python脚本",
        "description": "创建一个简单的 Python 待办事项管理脚本",
        "prompt": "Create a Python CLI todo list manager that can add, list, and complete tasks. Save data to a JSON file. Include a main function with command line argument parsing.",
        "work_dir": None,
        "timeout": 120
    },
    {
        "id": "S2", 
        "name": "多文件项目结构",
        "description": "创建一个简单的 Python 包项目结构",
        "prompt": "Create a Python package named 'calculator' with: 1) __init__.py, 2) core.py with add/subtract/multiply/divide functions, 3) cli.py with argparse interface, 4) test_calculator.py with pytest tests. Include setup.py.",
        "work_dir": None,
        "timeout": 180
    },
    {
        "id": "S3",
        "name": "代码分析与改进",
        "description": "分析现有代码并提出改进建议",
        "prompt": "Read the file at /mnt/d/lancer/knight/core/workflow_engine.py, analyze its design patterns, and suggest 3 concrete improvements with code examples.",
        "work_dir": "/mnt/d/lancer/knight",
        "timeout": 60
    },
    {
        "id": "S4",
        "name": "文档生成",
        "description": "为项目生成 API 文档",
        "prompt": "Read all Python files in the current directory and generate a comprehensive API documentation in Markdown format, including: module descriptions, class hierarchies, function signatures.",
        "work_dir": "/mnt/d/lancer/knight/core",
        "timeout": 120
    },
]


async def run_with_engine(prompt, work_dir, timeout):
    """使用 knight 模块运行任务"""
    # 动态导入，确保路径正确
    import importlib.util
    spec = importlib.util.spec_from_file_location("knight", os.path.join(KNIGHT_DIR, "__init__.py"))
    knight = importlib.util.module_from_spec(spec)
    
    # 手动设置子模块
    sys.modules['knight'] = knight
    sys.modules['knight.core'] = __import__('core', fromlist=[''])
    
    spec.loader.exec_module(knight)
    
    engine = knight.WorkflowEngine()
    return await asyncio.wait_for(
        engine.execute(prompt, work_dir=work_dir),
        timeout=timeout
    )


class CLITester:
    """CLI 测试执行器"""
    
    def __init__(self):
        self.results = []
        self.temp_dirs = []
        
    async def run_scenario(self, scenario):
        """运行单个测试场景"""
        print(f"\n{'='*60}")
        print(f"📝 场景 {scenario['id']}: {scenario['name']}")
        print(f"{'='*60}")
        print(f"描述: {scenario['description']}")
        print(f"提示词: {scenario['prompt'][:100]}...")
        
        # 准备工作目录
        if scenario['work_dir']:
            work_dir = scenario['work_dir']
            is_temp = False
        else:
            work_dir = tempfile.mkdtemp(prefix=f"knight_test_{scenario['id']}_")
            self.temp_dirs.append(work_dir)
            is_temp = True
            
        print(f"工作目录: {work_dir} {'(临时)' if is_temp else '(固定)'}")
        os.makedirs(work_dir, exist_ok=True)
        
        # 执行测试
        start_time = datetime.now()
        
        try:
            result = await run_with_engine(
                scenario['prompt'], 
                work_dir, 
                scenario['timeout']
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            success = len(result) > 0
            
            # 列出生成的文件
            generated_files = []
            if os.path.exists(work_dir):
                for item in os.listdir(work_dir):
                    item_path = os.path.join(work_dir, item)
                    if os.path.isfile(item_path):
                        size = os.path.getsize(item_path)
                        generated_files.append(f"{item} ({size} bytes)")
                    else:
                        files_in_dir = len(os.listdir(item_path))
                        generated_files.append(f"{item}/ ({files_in_dir} items)")
            
            print(f"\n✅ 执行成功 ({duration:.1f}s)")
            print(f"📁 生成文件: {generated_files or 'None'}")
            print(f"📄 结果长度: {len(result)} 字符")
            print(f"预览: {result[:300]}...")
            
            self.results.append({
                "scenario": scenario,
                "success": success,
                "duration": duration,
                "result": result,
                "files": generated_files,
                "work_dir": work_dir
            })
            
            return True
            
        except asyncio.TimeoutError:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"\n⏱️ 执行超时 ({duration:.1f}s > {scenario['timeout']}s)")
            self.results.append({
                "scenario": scenario,
                "success": False,
                "duration": duration,
                "error": "Timeout",
                "work_dir": work_dir
            })
            return False
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"\n❌ 执行失败 ({duration:.1f}s): {e}")
            import traceback
            traceback.print_exc()
            self.results.append({
                "scenario": scenario,
                "success": False,
                "duration": duration,
                "error": str(e),
                "work_dir": work_dir
            })
            return False
    
    async def run_all(self, scenario_ids=None):
        """运行所有或指定场景"""
        scenarios = TEST_SCENARIOS
        if scenario_ids:
            scenarios = [s for s in scenarios if s['id'] in scenario_ids]
        
        print(f"\n🏰 Knight System CLI 场景测试")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试场景数: {len(scenarios)}")
        print(f"工作目录: {KNIGHT_DIR}")
        
        for scenario in scenarios:
            await self.run_scenario(scenario)
        
        self.print_report()
    
    def print_report(self):
        """打印测试报告"""
        print(f"\n{'='*60}")
        print("📊 测试报告")
        print(f"{'='*60}")
        
        total = len(self.results)
        success = sum(1 for r in self.results if r['success'])
        failed = total - success
        
        print(f"\n总计: {total} | ✅ 成功: {success} | ❌ 失败: {failed}")
        print(f"成功率: {success/total*100:.1f}%" if total > 0 else "N/A")
        
        print(f"\n详细结果:")
        for r in self.results:
            status = "✅" if r['success'] else "❌"
            s = r['scenario']
            print(f"\n  {status} {s['id']}: {s['name']} ({r['duration']:.1f}s)")
            if not r['success'] and 'error' in r:
                print(f"      错误: {r['error']}")
            if r.get('files'):
                print(f"      生成文件:")
                for f in r['files'][:5]:
                    print(f"        📄 {f}")
        
        if self.temp_dirs:
            print(f"\n临时目录位置:")
            for d in self.temp_dirs:
                print(f"  📁 {d}")
    
    def cleanup(self):
        """清理临时目录"""
        print(f"\n🧹 清理临时目录...")
        for d in self.temp_dirs:
            if os.path.exists(d):
                shutil.rmtree(d)
                print(f"  已删除: {d}")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Knight CLI 场景测试')
    parser.add_argument('--scenario', '-s', help='运行指定场景 (如: S1,S2)')
    parser.add_argument('--cleanup', '-c', action='store_true', help='测试后清理临时文件')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有场景')
    
    args = parser.parse_args()
    
    if args.list:
        print("\n📋 可用测试场景:")
        for s in TEST_SCENARIOS:
            print(f"\n  {s['id']}: {s['name']}")
            print(f"      描述: {s['description']}")
            print(f"      超时: {s['timeout']}s")
        return
    
    # 确定要运行的场景
    scenario_ids = None
    if args.scenario:
        scenario_ids = [id.strip() for id in args.scenario.split(',')]
    
    # 运行测试
    tester = CLITester()
    try:
        await tester.run_all(scenario_ids)
    finally:
        if args.cleanup:
            tester.cleanup()
        else:
            print(f"\n💡 使用 --cleanup 选项删除临时文件，或手动清理上述临时目录")


if __name__ == '__main__':
    asyncio.run(main())
