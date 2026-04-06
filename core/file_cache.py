"""文件状态缓存 - 防止重复读取"""
import os
import time
import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class FileState:
    content: str
    timestamp: float
    content_hash: str
    size_bytes: int


class FileStateCache:
    """文件状态缓存 - OrderedDict LRU + TTL"""

    def __init__(self, max_entries: int = 100, max_size_mb: int = 25, ttl_seconds: float = 300):
        self.max_entries = max_entries
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, FileState] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._current_size = 0

    def _normalize_path(self, path: str) -> str:
        return os.path.normpath(os.path.abspath(path))

    def _is_expired(self, state: FileState) -> bool:
        return time.time() - state.timestamp > self.ttl_seconds

    def _evict_if_needed(self, new_size: int):
        """LRU 淘汰 - O(1) 使用 OrderedDict"""
        while (len(self._cache) >= self.max_entries or
               self._current_size + new_size > self.max_size_bytes) and self._cache:
            _, removed = self._cache.popitem(last=False)  # 弹出最旧的
            self._current_size -= removed.size_bytes

    def get(self, path: str) -> Optional[FileState]:
        """获取缓存"""
        key = self._normalize_path(path)
        if key not in self._cache:
            self._misses += 1
            return None

        state = self._cache[key]
        if self._is_expired(state):
            del self._cache[key]
            self._current_size -= state.size_bytes
            self._misses += 1
            return None

        # 移到末尾（最近使用）- O(1)
        self._cache.move_to_end(key)
        self._hits += 1
        return state

    def set(self, path: str, content: str):
        """缓存文件"""
        key = self._normalize_path(path)
        size = len(content.encode('utf-8'))

        if key in self._cache:
            self._current_size -= self._cache[key].size_bytes
            del self._cache[key]

        self._evict_if_needed(size)

        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        self._cache[key] = FileState(content, time.time(), content_hash, size)
        self._cache.move_to_end(key)
        self._current_size += size

    def invalidate(self, path: str) -> bool:
        """使缓存失效"""
        key = self._normalize_path(path)
        if key in self._cache:
            removed = self._cache.pop(key)
            self._current_size -= removed.size_bytes
            return True
        return False

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        return {
            'entries': len(self._cache),
            'size_mb': round(self._current_size / 1024 / 1024, 4),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{self.hit_rate:.1%}"
        }
