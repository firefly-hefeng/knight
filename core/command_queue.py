"""命令队列管理"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict
from enum import Enum
import time

class Priority(Enum):
    NOW = 0
    NEXT = 1
    LATER = 2

@dataclass
class QueuedCommand:
    id: str
    value: str
    priority: Priority = Priority.NEXT
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

class CommandQueue:
    """优先级命令队列"""

    def __init__(self):
        self._queue: List[QueuedCommand] = []
        self._subscribers: List[Callable] = []

    def _notify(self):
        for sub in self._subscribers:
            try:
                sub()
            except Exception:
                pass

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def enqueue(self, command: QueuedCommand):
        self._queue.append(command)
        self._notify()

    def dequeue(self, filter_fn: Optional[Callable[[QueuedCommand], bool]] = None) -> Optional[QueuedCommand]:
        if not self._queue:
            return None

        best_idx = -1
        best_priority = float('inf')

        for i, cmd in enumerate(self._queue):
            if filter_fn and not filter_fn(cmd):
                continue
            if cmd.priority.value < best_priority:
                best_idx = i
                best_priority = cmd.priority.value

        if best_idx == -1:
            return None

        cmd = self._queue.pop(best_idx)
        self._notify()
        return cmd

    def clear(self):
        self._queue.clear()
        self._notify()

    @property
    def length(self) -> int:
        return len(self._queue)
