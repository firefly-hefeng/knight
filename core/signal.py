"""轻量级信号系统 - 用于事件通知"""
from typing import Callable, TypeVar, Generic, List

T = TypeVar('T')


class Signal(Generic[T]):
    """轻量级信号系统 - 纯事件，无状态存储

    使用 list 存储监听器（支持 lambda 和重复订阅）
    """

    def __init__(self):
        self._listeners: List[Callable[[T], None]] = []

    def subscribe(self, listener: Callable[[T], None]) -> Callable[[], None]:
        """订阅信号，返回取消订阅函数"""
        self._listeners.append(listener)

        def unsubscribe():
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass  # 已经取消

        return unsubscribe

    def emit(self, value: T):
        """触发信号"""
        for listener in list(self._listeners):  # 复制防止迭代中修改
            try:
                listener(value)
            except Exception as e:
                print(f"Signal listener error: {e}")

    def clear(self):
        """清除所有监听器"""
        self._listeners.clear()

    @property
    def listener_count(self) -> int:
        return len(self._listeners)
