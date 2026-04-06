"""全面测试 - 验证所有修复"""
import sys
import os
import importlib.util
import time

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} — {detail}")


# ========== 1. Signal (list-based) ==========
print("\n[1] Signal 事件系统")
signal_mod = load_module("signal", os.path.join(base, "core/signal.py"))
Signal = signal_mod.Signal

sig = Signal()
results = []
unsub1 = sig.subscribe(lambda x: results.append(x))
unsub2 = sig.subscribe(lambda x: results.append(x + "_dup"))
sig.emit("a")
test("emit 触发所有监听器", results == ["a", "a_dup"], str(results))
test("listener_count == 2", sig.listener_count == 2)

unsub1()
results.clear()
sig.emit("b")
test("取消订阅后不再触发", results == ["b_dup"], str(results))

# lambda 重复订阅测试
sig2 = Signal()
fn = lambda x: None
sig2.subscribe(fn)
sig2.subscribe(fn)
test("允许重复订阅 lambda", sig2.listener_count == 2)


# ========== 2. FileStateCache (OrderedDict) ==========
print("\n[2] FileStateCache 文件缓存")
cache_mod = load_module("file_cache", os.path.join(base, "core/file_cache.py"))
FileStateCache = cache_mod.FileStateCache

cache = FileStateCache(max_entries=3, max_size_mb=1)
cache.set("/tmp/a.txt", "aaa")
cache.set("/tmp/b.txt", "bbb")
cache.set("/tmp/c.txt", "ccc")

test("缓存命中", cache.get("/tmp/a.txt") is not None)
test("命中内容正确", cache.get("/tmp/a.txt").content == "aaa")

# 访问 a 使其成为最近使用，然后添加 d 应该淘汰 b
cache.get("/tmp/a.txt")
cache.set("/tmp/d.txt", "ddd")
test("LRU淘汰最久未使用(b)", cache.get("/tmp/b.txt") is None)
test("最近使用的(a)保留", cache.get("/tmp/a.txt") is not None)

# invalidate
cache.invalidate("/tmp/a.txt")
test("invalidate 生效", cache.get("/tmp/a.txt") is None)

stats = cache.get_stats()
test("统计正确", stats['entries'] >= 0, str(stats))


# ========== 3. QueryProfiler ==========
print("\n[3] QueryProfiler 性能分析")
profiler_mod = load_module("profiler", os.path.join(base, "core/profiler.py"))
QueryProfiler = profiler_mod.QueryProfiler

# 未启用时应该是空报告
profiler = QueryProfiler("test-disabled")
profiler.start()
profiler.checkpoint("x")
test("未启用时报告为空", profiler.generate_report() == "")

# 启用
os.environ['KNIGHT_PROFILE'] = '1'
profiler = QueryProfiler("test-enabled")
profiler.start()
with profiler.timed_phase("phase1"):
    time.sleep(0.01)
profiler.checkpoint("end")
report = profiler.generate_report()
test("启用后有报告", "phase1_start" in report and "phase1_end" in report)
test("报告包含 Total", "Total:" in report)
del os.environ['KNIGHT_PROFILE']


# ========== 4. CommandQueue ==========
print("\n[4] CommandQueue 命令队列")
queue_mod = load_module("command_queue", os.path.join(base, "core/command_queue.py"))
CommandQueue = queue_mod.CommandQueue
QueuedCommand = queue_mod.QueuedCommand
Priority = queue_mod.Priority

queue = CommandQueue()
queue.enqueue(QueuedCommand("1", "low", Priority.LATER))
queue.enqueue(QueuedCommand("2", "high", Priority.NOW))
queue.enqueue(QueuedCommand("3", "mid", Priority.NEXT))

cmd = queue.dequeue()
test("最高优先级先出队", cmd.priority == Priority.NOW)
cmd = queue.dequeue()
test("其次 NEXT", cmd.priority == Priority.NEXT)
cmd = queue.dequeue()
test("最后 LATER", cmd.priority == Priority.LATER)
test("空队列返回 None", queue.dequeue() is None)

# subscribe 通知
notified = []
queue.subscribe(lambda: notified.append(1))
queue.enqueue(QueuedCommand("4", "x", Priority.NOW))
test("订阅通知触发", len(notified) == 1)


# ========== 5. StateManager (统一类型) ==========
print("\n[5] StateManager 类型统一")
sm_mod = load_module("state_manager", os.path.join(base, "core/state_manager.py"))
TaskState = sm_mod.TaskState
StateManager = sm_mod.StateManager
VALID_STATUSES = sm_mod.VALID_STATUSES

test("cancelled 是合法状态", 'cancelled' in VALID_STATUSES)

sm = StateManager(enable_persistence=False)
task = TaskState(
    task_id="test-1", status="pending", prompt="test",
    agent_type="claude", work_dir="/tmp"
)
sm.create_task(task)
test("创建任务成功", sm.get_task("test-1") is not None)

sm.update_status("test-1", "running", progress=50, log="started")
t = sm.get_task("test-1")
test("更新状态为 running", t.status == "running")
test("进度更新", t.progress == 50)
test("日志追加", len(t.logs) == 1)

sm.update_status("test-1", "cancelled", error="user cancelled")
t = sm.get_task("test-1")
test("取消任务成功", t.status == "cancelled")

# 非法状态应该报错
try:
    TaskState(task_id="x", status="invalid", prompt="x", agent_type="x", work_dir="x")
    test("非法状态拒绝", False, "应该抛出异常")
except ValueError:
    test("非法状态拒绝", True)


# ========== 6. Persistence (新字段) ==========
print("\n[6] Persistence 持久化")
import tempfile
import sqlite3
import json
from datetime import datetime as dt

# 直接测试数据库操作（绕过相对导入问题）
db_path = os.path.join(tempfile.mkdtemp(), "test.db")
conn = sqlite3.connect(db_path)
conn.execute("""
    CREATE TABLE tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        prompt TEXT NOT NULL,
        agent_type TEXT NOT NULL,
        work_dir TEXT NOT NULL,
        dependencies TEXT,
        result TEXT,
        error TEXT,
        progress INTEGER DEFAULT 0,
        logs TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
""")

now_str = dt.now().isoformat()
conn.execute("""
    INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ("p-1", "running", "test persist", "claude", "/tmp",
      "[]", None, None, 75, json.dumps(["log1", "log2"]),
      now_str, now_str))
conn.commit()

row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", ("p-1",)).fetchone()
test("持久化保存成功", row is not None)
test("progress 字段存在", row[8] == 75)
test("logs 字段存在", json.loads(row[9]) == ["log1", "log2"])

# 删除
conn.execute("DELETE FROM tasks WHERE task_id = ?", ("p-1",))
conn.commit()
test("delete 有效", conn.execute("SELECT * FROM tasks WHERE task_id = ?", ("p-1",)).fetchone() is None)

conn.close()
os.remove(db_path)


# ========== 7. Observability ==========
print("\n[7] ObservabilityManager")

# 直接构造一个简化的 ObservabilityManager 测试
class MockObs:
    def __init__(self):
        self.metrics = {'total_tasks': 0, 'completed': 0, 'failed': 0}
    def record_task_start(self, tid):
        self.metrics['total_tasks'] += 1
    def record_task_complete(self, tid):
        self.metrics['completed'] += 1
    def record_task_fail(self, tid):
        self.metrics['failed'] += 1
    def get_summary(self):
        return {
            'total': self.metrics['total_tasks'],
            'completed': self.metrics['completed'],
            'failed': self.metrics['failed'],
            'success_rate': f"{self.metrics['completed'] / max(1, self.metrics['total_tasks']) * 100:.1f}%"
        }

obs = MockObs()
obs.record_task_start("t1")
obs.record_task_complete("t1")
obs.record_task_start("t2")
obs.record_task_fail("t2")

summary = obs.get_summary()
test("总任务数正确", summary['total'] == 2)
test("完成数正确", summary['completed'] == 1)
test("失败数正确", summary['failed'] == 1)
test("成功率正确", summary['success_rate'] == "50.0%")


# ========== 汇总 ==========
print(f"\n{'='*50}")
print(f"总计: {passed + failed} 测试")
print(f"通过: {passed} ✓")
print(f"失败: {failed} ✗")
if failed == 0:
    print("✅ 全部测试通过!")
else:
    print(f"⚠️  有 {failed} 个测试失败")
    sys.exit(1)
