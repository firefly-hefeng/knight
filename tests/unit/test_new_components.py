"""核心组件测试 - 直接导入"""
import sys
import os
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base = os.path.dirname(os.path.dirname(__file__))

# 测试 Signal
print("Testing Signal...")
signal_mod = load_module("signal", os.path.join(base, "core/signal.py"))
Signal = signal_mod.Signal

signal = Signal()
results = []
unsub = signal.subscribe(lambda x: results.append(x))
signal.emit("test1")
signal.emit("test2")
unsub()
signal.emit("test3")
assert results == ["test1", "test2"]
print("✓ Signal works")

# 测试 FileStateCache
print("\nTesting FileStateCache...")
cache_mod = load_module("file_cache", os.path.join(base, "core/file_cache.py"))
FileStateCache = cache_mod.FileStateCache

cache = FileStateCache(max_entries=2, max_size_mb=1)
cache.set("/tmp/test.txt", "content1")
state = cache.get("/tmp/test.txt")
assert state and state.content == "content1"
cache.set("/tmp/test2.txt", "content2")
cache.set("/tmp/test3.txt", "content3")
assert cache.get("/tmp/test.txt") is None
print(f"✓ FileStateCache - {cache.get_stats()}")

# 测试 QueryProfiler
print("\nTesting QueryProfiler...")
profiler_mod = load_module("profiler", os.path.join(base, "core/profiler.py"))
QueryProfiler = profiler_mod.QueryProfiler

os.environ['KNIGHT_PROFILE'] = '1'
profiler = QueryProfiler("test")
profiler.start()
import time
with profiler.timed_phase("phase1"):
    time.sleep(0.01)
profiler.checkpoint("end")
report = profiler.generate_report()
assert "phase1_start" in report
print("✓ QueryProfiler works")
del os.environ['KNIGHT_PROFILE']

# 测试 CommandQueue
print("\nTesting CommandQueue...")
queue_mod = load_module("command_queue", os.path.join(base, "core/command_queue.py"))
CommandQueue = queue_mod.CommandQueue
QueuedCommand = queue_mod.QueuedCommand
Priority = queue_mod.Priority

queue = CommandQueue()
queue.enqueue(QueuedCommand("1", "cmd1", Priority.LATER))
queue.enqueue(QueuedCommand("2", "cmd2", Priority.NOW))
queue.enqueue(QueuedCommand("3", "cmd3", Priority.NEXT))

cmd = queue.dequeue()
assert cmd and cmd.priority == Priority.NOW
cmd = queue.dequeue()
assert cmd and cmd.priority == Priority.NEXT
print("✓ CommandQueue works")

print("\n✅ All components passed!")
