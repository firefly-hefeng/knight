"""查询性能分析器"""
import time
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Checkpoint:
    name: str
    timestamp: float
    delta_ms: float = 0

class QueryProfiler:
    """性能分析器 - 追踪执行耗时"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.checkpoints: List[Checkpoint] = []
        self.start_time: Optional[float] = None
        self.enabled = os.environ.get('KNIGHT_PROFILE') == '1'

    def start(self):
        if not self.enabled:
            return
        self.start_time = time.perf_counter()
        self.checkpoint('start')

    def checkpoint(self, name: str):
        if not self.enabled or self.start_time is None:
            return

        now = time.perf_counter()
        relative_ms = (now - self.start_time) * 1000
        delta_ms = 0
        if self.checkpoints:
            delta_ms = relative_ms - self.checkpoints[-1].timestamp

        self.checkpoints.append(Checkpoint(name, relative_ms, delta_ms))

    @contextmanager
    def timed_phase(self, name: str):
        """测量代码块耗时"""
        if not self.enabled:
            yield
            return
        self.checkpoint(f"{name}_start")
        try:
            yield
        finally:
            self.checkpoint(f"{name}_end")

    def generate_report(self) -> str:
        """生成报告"""
        if not self.enabled or not self.checkpoints:
            return ""

        lines = [f"=== Profiling: {self.session_id} ==="]
        for cp in self.checkpoints:
            warning = " ⚠️" if cp.delta_ms > 100 else ""
            lines.append(f"[+{cp.timestamp:>8.1f}ms] (+{cp.delta_ms:>6.1f}ms) {cp.name}{warning}")

        total = self.checkpoints[-1].timestamp
        lines.append(f"Total: {total:.1f}ms")
        return "\n".join(lines)

    def log_report(self):
        if self.enabled:
            print(self.generate_report())
