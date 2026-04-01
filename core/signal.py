"""轻量级信号系统 - 用于事件通知"""
from typing import Callable, Set, TypeVar, Generic, List

T = TypeVar('T')

class Signal(Generic[T]):
    """轻量级信号系统 - 纯事件，无状态存储"""

    def __init__(self):
        self._listeners: Set[Callable[[T], None]] = set()

    def subscribe(self, listener: Callable[[T], None]) -> Callable[[], None]:
        """订阅信号，返回取消订阅函数"""
        self._listeners.add(listener)

        def unsubscribe():
            self._listeners.discard(listener)

        return unsubscribe

    def emit(self, value: T):
        """触发信号"""
        for listener in list(self._listeners):
            try:
                listener(value)
            except Exception as e:
                print(f"Signal listener error: {e}")

    def clear(self):
        """清除所有监听器"""
        self._listeners.clear()
