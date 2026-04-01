# 核心工程组件使用指南

## 已实现的组件

### 1. Signal - 轻量级事件系统

```python
from core.signal import Signal

# 创建信号
task_changed = Signal[str]()

# 订阅
unsub = task_changed.subscribe(lambda task_id: print(f"Task {task_id} changed"))

# 触发
task_changed.emit("task_123")

# 取消订阅
unsub()
```

### 2. FileStateCache - 文件缓存

```python
from core.file_cache import FileStateCache

cache = FileStateCache(max_entries=100, max_size_mb=25)

# 缓存文件
cache.set("/path/to/file.txt", "content")

# 获取缓存
state = cache.get("/path/to/file.txt")
if state:
    print(state.content)

# 查看统计
print(cache.get_stats())
```

### 3. QueryProfiler - 性能分析

```python
from core.profiler import QueryProfiler
import os

# 启用 profiling
os.environ['KNIGHT_PROFILE'] = '1'

profiler = QueryProfiler("task_123")
profiler.start()

# 记录检查点
profiler.checkpoint("load_data")

# 测量代码块
with profiler.timed_phase("processing"):
    # 你的代码
    pass

# 生成报告
profiler.log_report()
```

### 4. CommandQueue - 优先级队列

```python
from core.command_queue import CommandQueue, QueuedCommand, Priority

queue = CommandQueue()

# 入队
queue.enqueue(QueuedCommand("1", "urgent_cmd", Priority.NOW))
queue.enqueue(QueuedCommand("2", "normal_cmd", Priority.NEXT))

# 出队（按优先级）
cmd = queue.dequeue()
print(cmd.value)
```

## 在 KnightCore 中的集成

所有组件已集成到 `KnightCore` 中：

```python
core = KnightCore()

# 文件缓存
core.file_cache.set(path, content)

# 命令队列
core.command_queue.enqueue(cmd)

# 信号订阅
core.task_status_changed.subscribe(handler)

# 查看统计
stats = core.get_stats()
print(stats['file_cache'])
```

## 测试

运行组件测试：
```bash
python3 tests/test_new_components.py
```

## 环境变量

- `KNIGHT_PROFILE=1` - 启用性能分析

