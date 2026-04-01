# Knight System - 快速开始

## 基础使用

### 1. 简单任务

```python
import asyncio
from knight import WorkflowEngine

async def main():
    engine = WorkflowEngine()
    result = await engine.execute(
        "Create a hello.py file",
        work_dir="/tmp/test"
    )
    print(result)

asyncio.run(main())
```

### 2. 智能分解

系统自动将复杂任务分解为子任务:

```python
from knight.core import AgentPool, StateManager, TaskCoordinator
from knight.core.smart_planner import SmartTaskPlanner

pool = AgentPool()
planner = SmartTaskPlanner(pool)

tasks = await planner.plan(
    "Create a REST API with Flask",
    "/tmp/api"
)
# 自动生成3-5个子任务
```

### 3. 工作流模式

```python
from knight.core.workflow_patterns import WorkflowPattern

# Map-Reduce
tasks = WorkflowPattern.map_reduce(map_tasks, reduce_task)
```

## 运行测试

```bash
cd tests/integration
python3 test_e2e.py
```
