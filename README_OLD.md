# 🏰 Knight System

**Multi-Agent Task Orchestration Framework**

基于商用Agent(Claude Code/Kimi Code)的智能任务编排系统,通过CLI调用实现复杂工作流自动化。

---

## ✨ 核心特性

- 🤖 **智能分解**: 自动将复杂任务分解为3-5个可执行子任务
- 🔄 **工作流模式**: Chain、Group、Map-Reduce编排
- 🚀 **高并发**: 10+任务并行,6.6任务/秒吞吐
- 🎯 **多Agent协作**: Claude(复杂逻辑) + Kimi(快速操作)
- 🔁 **持续测试**: 自动测试并修复代码
- 📊 **可观测性**: 实时监控任务状态
- 🌐 **Web界面**: 深色主题UI

---

## 📦 前置要求

```bash
# 安装Claude Code
npm install -g @anthropic-ai/claude-code

# 安装Kimi Code (可选)
# 参考: https://kimi.moonshot.cn
```

---

## 🚀 快速开始

### 1. 基础使用

```python
import asyncio
from knight import WorkflowEngine

async def main():
    engine = WorkflowEngine()
    result = await engine.execute(
        "Create a Python calculator with add/subtract",
        work_dir="/tmp/project"
    )
    print(result)

asyncio.run(main())
```

### 2. 运行测试

```bash
# 端到端测试
python3 tests/integration/test_e2e.py

# 多Agent协作
python3 tests/integration/test_multi_agent.py

# 大规模并行
python3 tests/integration/test_scale.py
```

### 3. Web界面

```bash
待设计中
```

---

## 📁 项目结构

```
lancer/
├── knight/                 # 核心系统
│   ├── adapters/          # Agent适配器(Claude/Kimi)
│   └── core/              # 核心模块(14个)
├── tests/                 # 测试套件
│   └── integration/       # 集成测试(12个场景)
├── examples/              # 使用示例
├── web/                   # Web界面
│── icons/                 # 可以使用的图标
├── docs/                  # 文档
└── reference/             # 参考资料
```

---

## 🧩 核心模块

### Agent适配器
- `claude_adapter.py` - Claude Code CLI封装
- `kimi_adapter.py` - Kimi Code CLI封装

### 核心编排(14个模块)
- `workflow_engine.py` - 工作流引擎
- `smart_planner.py` - 智能任务分解
- `task_coordinator.py` - 任务协调器
- `agent_pool.py` - Agent池管理
- `workflow_patterns.py` - 工作流模式
- `continuous_tester.py` - 持续测试
- `long_running_task.py` - 长期任务
- `observability.py` - 可观测性
- 更多...

---

## 📊 测试覆盖

✅ 单任务执行
✅ 并行任务(3个)
✅ 依赖链(3级)
✅ 实际项目(Python包)
✅ 智能分解(5任务)
✅ Map-Reduce模式
✅ TODO应用生成
✅ 多Agent协作
✅ 错误恢复
✅ 大规模并行(10任务)
✅ 持续测试
✅ 长期监控

**成功率: 100%**

---

## 🎯 性能指标

- 并行吞吐: 6.6任务/秒
- 支持任务数: 10+并行
- 智能分解: 3-5个子任务
- 代码质量: 生产可用

---

## 📖 文档

- [快速开始](docs/QUICK_START.md)
- [项目结构](docs/PROJECT_STRUCTURE.md)
- [架构设计](docs/ARCHITECTURE_FINAL.md)
- [测试报告](docs/EXTENDED_TEST_REPORT.md)

---

## 🤝 贡献

欢迎提交Issue和PR

---

## 📄 许可

MIT License
