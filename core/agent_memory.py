"""
Agent Memory — 跨会话持久化记忆系统

三个作用域（参考 CC agentMemory.ts）:
  - user:    全局记忆，所有项目共享 (~/.knight/MEMORY.md)
  - project: 项目级记忆，Git 仓库级别 ({project}/.knight/MEMORY.md)
  - local:   机器级记忆，不进版本控制 ({project}/.knight/local/MEMORY.md)

记忆格式：Markdown，便于人类阅读和编辑。
记忆注入：在构建 agent prompt 时自动注入相关记忆。
"""
import os
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MEMORY_FILENAME = "MEMORY.md"
USER_MEMORY_DIR = os.path.expanduser("~/.knight")
MEMORY_HEADER = "# Knight Memory\n\n"
MAX_MEMORY_TOKENS = 2000
CHARS_PER_TOKEN = 3


@dataclass
class MemoryEntry:
    """单条记忆"""
    content: str
    scope: str                                      # user | project | local
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    source: str = ""                                # 哪个任务/Agent 产生的


class AgentMemory:
    """
    跨会话持久化记忆管理器

    使用：
        memory = AgentMemory(project_dir="/path/to/project")
        memory.add("Always use pytest for testing", scope="project", tags=["testing"])
        context = memory.build_context(tags=["testing"])
    """

    def __init__(self, project_dir: Optional[str] = None):
        self.project_dir = project_dir
        self._entries: Dict[str, List[MemoryEntry]] = {
            "user": [],
            "project": [],
            "local": [],
        }
        self._load_all()

    # ==================== 路径管理 ====================

    def _get_path(self, scope: str) -> str:
        if scope == "user":
            return os.path.join(USER_MEMORY_DIR, MEMORY_FILENAME)
        elif scope == "project" and self.project_dir:
            return os.path.join(self.project_dir, ".knight", MEMORY_FILENAME)
        elif scope == "local" and self.project_dir:
            return os.path.join(self.project_dir, ".knight", "local", MEMORY_FILENAME)
        return ""

    # ==================== 读写 ====================

    def _load_all(self):
        """从磁盘加载所有记忆"""
        for scope in ("user", "project", "local"):
            path = self._get_path(scope)
            if path and os.path.exists(path):
                self._entries[scope] = self._parse_file(path, scope)

    def _parse_file(self, path: str, scope: str) -> List[MemoryEntry]:
        """解析 MEMORY.md 文件"""
        entries = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read memory file {path}: {e}")
            return []

        # 解析格式: - content [tags: tag1, tag2] (source: task-123)
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('- '):
                line = line[2:]

            # 提取 tags
            tags = []
            tag_match = re.search(r'\[tags?:\s*([^\]]+)\]', line)
            if tag_match:
                tags = [t.strip() for t in tag_match.group(1).split(',')]
                line = line[:tag_match.start()].strip()

            # 提取 source
            source = ""
            src_match = re.search(r'\(source:\s*([^)]+)\)', line)
            if src_match:
                source = src_match.group(1).strip()
                line = line[:src_match.start()].strip()

            if line:
                entries.append(MemoryEntry(
                    content=line, scope=scope, tags=tags, source=source
                ))
        return entries

    def _save_scope(self, scope: str):
        """保存某个作用域到磁盘"""
        path = self._get_path(scope)
        if not path:
            return

        os.makedirs(os.path.dirname(path), exist_ok=True)

        scope_labels = {"user": "User (Global)", "project": "Project", "local": "Local (Machine)"}
        lines = [MEMORY_HEADER]
        lines.append(f"## {scope_labels.get(scope, scope)} Memory\n\n")

        for entry in self._entries[scope]:
            line = f"- {entry.content}"
            if entry.tags:
                line += f" [tags: {', '.join(entry.tags)}]"
            if entry.source:
                line += f" (source: {entry.source})"
            lines.append(line)

        lines.append("")  # trailing newline

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except Exception as e:
            logger.warning(f"Failed to save memory file {path}: {e}")

    # ==================== CRUD ====================

    def add(self, content: str, scope: str = "project",
            tags: Optional[List[str]] = None, source: str = "") -> None:
        """添加一条记忆"""
        if scope not in self._entries:
            scope = "project"

        # 去重：如果内容已存在，跳过
        for entry in self._entries[scope]:
            if entry.content == content:
                return

        entry = MemoryEntry(
            content=content, scope=scope,
            tags=tags or [], source=source,
        )
        self._entries[scope].append(entry)
        self._save_scope(scope)
        logger.debug(f"Memory added [{scope}]: {content[:80]}")

    def remove(self, content: str, scope: Optional[str] = None) -> bool:
        """移除一条记忆"""
        scopes = [scope] if scope else ["user", "project", "local"]
        removed = False
        for s in scopes:
            before = len(self._entries[s])
            self._entries[s] = [e for e in self._entries[s] if e.content != content]
            if len(self._entries[s]) < before:
                self._save_scope(s)
                removed = True
        return removed

    def search(self, query: str, scope: Optional[str] = None) -> List[MemoryEntry]:
        """搜索记忆"""
        query_lower = query.lower()
        results = []
        scopes = [scope] if scope else ["user", "project", "local"]
        for s in scopes:
            for entry in self._entries.get(s, []):
                if (query_lower in entry.content.lower()
                        or any(query_lower in t.lower() for t in entry.tags)):
                    results.append(entry)
        return results

    def get_all(self, scope: Optional[str] = None) -> List[MemoryEntry]:
        """获取所有记忆"""
        if scope:
            return list(self._entries.get(scope, []))
        result = []
        for s in ("user", "project", "local"):
            result.extend(self._entries[s])
        return result

    def clear(self, scope: str) -> int:
        """清空某个作用域"""
        count = len(self._entries.get(scope, []))
        self._entries[scope] = []
        self._save_scope(scope)
        return count

    # ==================== 上下文构建 ====================

    def build_context(self, tags: Optional[List[str]] = None,
                      max_tokens: int = MAX_MEMORY_TOKENS) -> str:
        """
        构建记忆上下文 — 注入到 Agent prompt 中

        优先级：project > local > user
        如果指定 tags，只包含匹配的记忆
        """
        all_entries = []
        for scope in ("project", "local", "user"):
            for entry in self._entries.get(scope, []):
                if tags:
                    if any(t in entry.tags for t in tags):
                        all_entries.append((scope, entry))
                else:
                    all_entries.append((scope, entry))

        if not all_entries:
            return ""

        lines = ["## Project Memory (accumulated knowledge)\n"]
        total_chars = 0
        max_chars = max_tokens * CHARS_PER_TOKEN

        for scope, entry in all_entries:
            line = f"- [{scope}] {entry.content}"
            if total_chars + len(line) > max_chars:
                lines.append(f"\n(... {len(all_entries) - len(lines) + 1} more memories omitted)")
                break
            lines.append(line)
            total_chars += len(line)

        return '\n'.join(lines)

    def build_context_for_task(self, task_description: str,
                               max_tokens: int = MAX_MEMORY_TOKENS) -> str:
        """
        为特定任务构建记忆上下文 — 基于相关性过滤

        简单关键词匹配；未来可用 embedding 向量检索。
        """
        keywords = set(task_description.lower().split())
        # 去掉太常见的词
        stop_words = {"the", "a", "an", "is", "are", "to", "of", "in", "for", "and", "or",
                      "that", "this", "it", "with", "on", "at", "by", "from", "as", "be"}
        keywords -= stop_words

        scored: List[Tuple[float, str, MemoryEntry]] = []
        for scope in ("project", "local", "user"):
            for entry in self._entries.get(scope, []):
                entry_words = set(entry.content.lower().split()) | set(t.lower() for t in entry.tags)
                overlap = len(keywords & entry_words)
                if overlap > 0:
                    # 分数 = 关键词重叠数 + 作用域权重
                    scope_bonus = {"project": 0.3, "local": 0.2, "user": 0.1}.get(scope, 0)
                    score = overlap + scope_bonus
                    scored.append((score, scope, entry))

        if not scored:
            # 没有匹配的，返回全部（截断）
            return self.build_context(max_tokens=max_tokens)

        scored.sort(key=lambda x: x[0], reverse=True)

        lines = ["## Relevant Project Memory\n"]
        total_chars = 0
        max_chars = max_tokens * CHARS_PER_TOKEN

        for score, scope, entry in scored:
            line = f"- [{scope}] {entry.content}"
            if total_chars + len(line) > max_chars:
                break
            lines.append(line)
            total_chars += len(line)

        return '\n'.join(lines)

    # ==================== 从 Agent 输出中提取记忆 ====================

    def extract_from_output(self, output: str, task_id: str = "") -> List[str]:
        """
        从 Agent 输出中自动提取值得记住的信息

        查找明确的 "Remember:" 或 "Note:" 标记。
        """
        extracted = []
        patterns = [
            r'(?:Remember|REMEMBER|Note|NOTE|Important|IMPORTANT):\s*(.+?)(?:\n|$)',
            r'(?:Key finding|KEY FINDING):\s*(.+?)(?:\n|$)',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, output):
                content = match.group(1).strip()
                if len(content) > 10:  # 忽略太短的
                    self.add(content, scope="project", tags=["auto-extracted"], source=task_id)
                    extracted.append(content)
        return extracted

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, int]:
        return {
            scope: len(entries)
            for scope, entries in self._entries.items()
        }
