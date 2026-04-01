# Knight System - 项目结构

## 目录说明

```
knight/
├── adapters/              # Agent适配器层
│   ├── claude_adapter.py  # Claude Code CLI封装
│   └── kimi_adapter.py    # Kimi Code CLI封装
│
├── core/                  # 核心编排层(14个模块)
│   ├── agent_pool.py      # Agent池管理
│   ├── state_manager.py   # 任务状态管理
│   ├── task_coordinator.py # 任务执行协调
│   ├── smart_planner.py   # 智能任务分解
│   ├── workflow_engine.py # 工作流引擎
│   └── ...                # 其他核心模块
│
├── examples/              # 使用示例
│   └── basic_usage.py     # 基础示例
│
├── tests/                 # 测试套件
│   └── integration/       # 集成测试(12个)
│
├── web/                   # Web界面
│   ├── pages/             # Next.js页面
│   ├── api/               # Flask API
│   └── styles/            # 样式文件
│
└── docs/                  # 文档
    ├── ARCHITECTURE_FINAL.md
    ├── PROJECT_SUMMARY.md
    └── ...
```
