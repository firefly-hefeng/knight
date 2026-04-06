"""
Context Manager - 场景化智能上下文管理

设计哲学：
  1. 压缩不是截断 — 截断破坏信息，压缩保留信息密度
  2. 场景决定策略 — 代码/错误/数据/日志各有不同的信息密度模式
  3. 目标长度是引导而非硬限 — 告诉 LLM "大约 N tokens"，由它判断取舍
  4. 全量持久化 + 按需回溯 — 磁盘存原文，内存存摘要
  5. 上下文总量感知 — 追踪总预算，依赖多时压缩更紧凑

压缩管线：
  原始输出 → 磁盘持久化 → 场景分类 → 微压缩(去冗余) → LLM 场景化压缩
"""
import os
import hashlib
import logging
import re
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from .state_manager import StateManager
from .orchestrator_prompts import (
    CONTEXT_SUMMARY_PROMPT,
    COMPRESS_CODE_OUTPUT, COMPRESS_ERROR_OUTPUT,
    COMPRESS_DATA_OUTPUT, COMPRESS_LOG_OUTPUT, COMPRESS_GENERAL,
)

if TYPE_CHECKING:
    from .task_dag import SubTask, TaskDAG

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 3
DEFAULT_CONTEXT_BUDGET_TOKENS = 8000
MICROCOMPACT_THRESHOLD = 2000
LLM_COMPRESS_THRESHOLD = 4000


# ==================== 场景分类 ====================

class OutputScene:
    """输出场景 — 决定压缩策略和目标长度"""
    CODE = "code"
    ERROR = "error"
    DATA = "data"
    LOG = "log"
    GENERAL = "general"

    # 各场景的压缩比（目标长度 / 原始长度）
    # 错误信息压缩比最保守（信息密度高），日志最激进（冗余多）
    COMPRESSION_RATIOS = {
        CODE: 0.4,      # 代码输出：保留 40%
        ERROR: 0.6,     # 错误信息：保留 60%（错误细节不能丢）
        DATA: 0.35,     # 数据分析：保留 35%（去掉原始数据，保留结论）
        LOG: 0.2,       # 执行日志：保留 20%（大量冗余）
        GENERAL: 0.35,  # 通用：保留 35%
    }

    # 各场景的最小保留 token 数（即使压缩比算出来更少，也至少保留这么多）
    MIN_TOKENS = {
        CODE: 300,
        ERROR: 500,     # 错误信息最少保留 500 tokens
        DATA: 200,
        LOG: 150,
        GENERAL: 200,
    }

    # 各场景的最大保留 token 数（防止压缩后仍然过长）
    MAX_TOKENS = {
        CODE: 2000,
        ERROR: 2500,
        DATA: 1500,
        LOG: 800,
        GENERAL: 1500,
    }

    PROMPT_MAP = {
        CODE: COMPRESS_CODE_OUTPUT,
        ERROR: COMPRESS_ERROR_OUTPUT,
        DATA: COMPRESS_DATA_OUTPUT,
        LOG: COMPRESS_LOG_OUTPUT,
        GENERAL: COMPRESS_GENERAL,
    }


def classify_output(text: str) -> str:
    """根据内容特征自动分类输出场景"""
    text_lower = text[:3000].lower()

    # 错误优先检测（最重要的场景）
    error_signals = ['error', 'exception', 'traceback', 'failed', 'fatal', 'panic']
    error_count = sum(1 for s in error_signals if s in text_lower)
    if error_count >= 2 or 'traceback' in text_lower:
        return OutputScene.ERROR

    # 代码特征
    code_signals = ['def ', 'class ', 'import ', 'function ', 'const ', 'return ', '```', '{', '}']
    code_count = sum(1 for s in code_signals if s in text_lower)
    if code_count >= 3:
        return OutputScene.CODE

    # 数据特征
    data_signals = ['total', 'count', 'average', 'mean', 'rows', 'columns', 'json', 'csv', '|']
    data_count = sum(1 for s in data_signals if s in text_lower)
    if data_count >= 3:
        return OutputScene.DATA

    # 日志特征
    log_signals = ['info', 'debug', 'warn', '[', ']', 'timestamp', '2024', '2025', '2026']
    log_count = sum(1 for s in log_signals if s in text_lower)
    if log_count >= 3:
        return OutputScene.LOG

    return OutputScene.GENERAL


def compute_target_tokens(text: str, scene: str, budget_override: Optional[int] = None) -> int:
    """计算场景化的目标压缩 token 数"""
    raw_tokens = len(text) // CHARS_PER_TOKEN
    ratio = OutputScene.COMPRESSION_RATIOS[scene]
    min_t = OutputScene.MIN_TOKENS[scene]
    max_t = OutputScene.MAX_TOKENS[scene]

    if budget_override:
        max_t = min(max_t, budget_override)

    target = int(raw_tokens * ratio)
    return max(min_t, min(target, max_t))


# ==================== 产物注册表 ====================

class ArtifactRegistry:
    """产物注册表 — 用引用代替内容传递"""

    def __init__(self):
        self._artifacts: Dict[str, dict] = {}

    def register(self, key: str, artifact_type: str, path: str,
                 description: str, producer_task_id: str) -> None:
        self._artifacts[key] = {
            "type": artifact_type,
            "path": path,
            "description": description,
            "producer": producer_task_id,
        }

    def get(self, key: str) -> Optional[dict]:
        return self._artifacts.get(key)

    def find_by_producer(self, task_id: str) -> List[dict]:
        return [a for a in self._artifacts.values() if a["producer"] == task_id]

    def to_context_block(self) -> str:
        if not self._artifacts:
            return ""
        lines = ["## Available Artifacts"]
        for key, a in self._artifacts.items():
            lines.append(f"- [{a['type']}] {key}: {a['description']} → {a['path']}")
        return "\n".join(lines)


# ==================== 主管理器 ====================

class ContextManager:
    """
    场景化智能上下文管理器

    核心原则：
    - 压缩是信息提炼，不是信息丢弃
    - 不同场景用不同策略，不同目标长度
    - 上下文总量有预算，依赖多时每个分到的预算更紧凑
    - 永远可以回溯原文（磁盘持久化）
    """

    def __init__(self, state: StateManager, agent_pool=None, storage_dir: str = ".knight/context"):
        self.state = state
        self.pool = agent_pool
        self.storage_dir = storage_dir
        self._context: Dict[str, str] = {}

        # 存储层
        self._raw_paths: Dict[str, str] = {}
        self._microcompacted: Dict[str, str] = {}
        self._summaries: Dict[str, str] = {}
        self._scenes: Dict[str, str] = {}              # task_id -> scene classification

        # 知识系统
        self._knowledge_base: Dict[str, str] = {}
        self._failed_approaches: Dict[str, List[str]] = {}
        self.artifacts = ArtifactRegistry()

        os.makedirs(storage_dir, exist_ok=True)

    # ==================== Layer 1: 磁盘持久化 ====================

    def store_raw_output(self, task_id: str, output: str) -> str:
        filename = f"{task_id}_{hashlib.md5(task_id.encode()).hexdigest()[:8]}.txt"
        path = os.path.join(self.storage_dir, filename)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(output)
            self._raw_paths[task_id] = path
            return path
        except Exception as e:
            logger.warning(f"Failed to store raw output for {task_id}: {e}")
            return ""

    def load_raw_output(self, task_id: str) -> Optional[str]:
        path = self._raw_paths.get(task_id)
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    # ==================== Layer 2: 微压缩 ====================

    def microcompact(self, text: str) -> str:
        """
        微压缩 — 去除冗余，保留语义。不调用 LLM，纯规则。

        目标：去掉明显的噪音（重复行、进度条、空行），
        让后续 LLM 压缩处理更高信息密度的输入。
        """
        if len(text) < MICROCOMPACT_THRESHOLD:
            return text

        lines = text.split('\n')
        cleaned = []
        prev_empty = False
        progress_re = re.compile(r'^\s*[\d.]+%|^\s*\[=+|^\s*#+\s*$|^\s*-{3,}\s*$')
        seen: Dict[str, int] = {}

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if not prev_empty:
                    cleaned.append('')
                    prev_empty = True
                continue
            prev_empty = False

            if progress_re.match(stripped):
                continue

            if stripped in seen:
                seen[stripped] += 1
                if seen[stripped] > 2:
                    continue
            else:
                seen[stripped] = 1

            cleaned.append(line)

        result = '\n'.join(cleaned)
        result = self._compress_repetitive_blocks(result)
        return result

    def _compress_repetitive_blocks(self, text: str) -> str:
        patterns = [
            (r'((?:^.*(?:Installing|Downloading|Fetching|Resolving).*$\n){4,})',
             lambda m: f"[{len(m.group(0).strip().split(chr(10)))} similar lines: "
                       f"{m.group(0).strip().split(chr(10))[0].strip()}...]\n"),
        ]
        for pattern, replacement in patterns:
            try:
                text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
            except Exception:
                pass
        return text

    # ==================== Layer 3: 场景化 LLM 压缩 ====================

    async def summarize_result(self, task_id: str, result: str,
                               budget_tokens: Optional[int] = None) -> str:
        """
        三层压缩管线：
        1. 持久化原文到磁盘
        2. 微压缩去冗余
        3. 场景分类 → 场景化 LLM 压缩（带目标长度引导）
        """
        self.store_raw_output(task_id, result)

        if len(result) <= MICROCOMPACT_THRESHOLD:
            self._summaries[task_id] = result
            return result

        if task_id in self._summaries and not budget_tokens:
            return self._summaries[task_id]

        # 微压缩
        compacted = self.microcompact(result)
        self._microcompacted[task_id] = compacted

        if len(compacted) <= LLM_COMPRESS_THRESHOLD:
            self._summaries[task_id] = compacted
            return compacted

        # 场景分类
        scene = classify_output(compacted)
        self._scenes[task_id] = scene

        # 计算目标长度
        target_tokens = compute_target_tokens(compacted, scene, budget_tokens)

        # LLM 场景化压缩
        if self.pool:
            try:
                summary = await self._scene_compress(compacted, scene, target_tokens)
                if summary:
                    self._summaries[task_id] = summary
                    return summary
            except Exception as e:
                logger.warning(f"LLM compression failed for {task_id}: {e}")

        # 降级：微压缩结果（不截断）
        self._summaries[task_id] = compacted
        return compacted

    async def _scene_compress(self, text: str, scene: str, target_tokens: int) -> Optional[str]:
        """场景化 LLM 压缩 — 不同场景用不同提示词和目标长度"""
        prompt_template = OutputScene.PROMPT_MAP.get(scene, COMPRESS_GENERAL)

        # 给 LLM 的输入：如果极长，用结构化方式呈现头尾
        # （这不是截断 — 是告诉 LLM "中间是重复内容"）
        if len(text) > 20000:
            input_text = (
                text[:12000]
                + f"\n\n[... {(len(text) - 18000) // CHARS_PER_TOKEN} tokens of "
                + f"intermediate output omitted — mostly execution logs ...]\n\n"
                + text[-6000:]
            )
        else:
            input_text = text

        prompt = prompt_template.format(output=input_text, target_tokens=target_tokens)
        result = await self.pool.execute("claude", prompt, "/tmp", timeout=60)

        if result.success and result.output:
            compressed = result.output.strip()
            # 验证压缩质量：如果 LLM 输出比原文还长，说明没压缩
            if len(compressed) < len(text):
                return compressed
            logger.warning(f"LLM compression produced longer output ({len(compressed)} > {len(text)})")
        return None

    # ==================== 上下文构建 ====================

    async def build_subtask_prompt(self, subtask: 'SubTask', dag: 'TaskDAG') -> str:
        """
        为子任务构建 prompt — 上下文总量感知

        关键设计：
        - 总预算固定，依赖越多每个分到的预算越少
        - 依赖的压缩目标长度由预算动态决定
        - 知识库和产物注册表不占依赖预算（它们本身就是压缩后的引用）
        """
        parts = [subtask.description]

        total_budget = DEFAULT_CONTEXT_BUDGET_TOKENS
        # 预留给非依赖内容的预算
        overhead_tokens = 500  # 知识库、失败记录、验收标准等
        dep_budget = total_budget - (len(subtask.description) // CHARS_PER_TOKEN) - overhead_tokens

        direct_deps = [
            dag.subtasks.get(dep_id)
            for dep_id in subtask.dependencies
            if dag.subtasks.get(dep_id) and dag.subtasks[dep_id].result
        ]

        if direct_deps:
            per_dep_tokens = max(200, dep_budget // len(direct_deps))

            for dep in direct_deps:
                # 优先使用 ReviewVerdict 的 forward_context
                context = dep.result_summary or self._summaries.get(dep.id)

                if not context:
                    context = await self.summarize_result(
                        dep.id, dep.result, budget_tokens=per_dep_tokens
                    )

                # 如果已有摘要但超出当前预算，再压缩一次
                context_tokens = len(context) // CHARS_PER_TOKEN
                if context_tokens > per_dep_tokens * 1.5 and self.pool:
                    context = await self._recompress(context, per_dep_tokens)

                parts.append(f"\n## Context from [{dep.id}]: {dep.description}\n{context}")

        # 产物注册表（引用，不占大量空间）
        artifacts_block = self.artifacts.to_context_block()
        if artifacts_block:
            parts.append(f"\n{artifacts_block}")

        # 知识库
        if self._knowledge_base:
            kb_lines = [f"- {k}: {v}" for k, v in self._knowledge_base.items()]
            parts.append(f"\n## Known Facts\n" + "\n".join(kb_lines))

        # 已失败的方法
        failed = self._failed_approaches.get(subtask.id, [])
        if failed:
            parts.append(
                "\n## Previously Failed Approaches (DO NOT repeat these)\n"
                + "\n".join(f"- {f}" for f in failed)
            )

        # 验收标准
        if subtask.acceptance_criteria:
            parts.append(
                "\n## Acceptance Criteria\n"
                + "\n".join(f"- {c}" for c in subtask.acceptance_criteria)
            )

        return "\n".join(parts)

    async def _recompress(self, text: str, target_tokens: int) -> str:
        """对已有摘要进行二次压缩（当预算收紧时）"""
        if not self.pool:
            return text

        prompt = COMPRESS_GENERAL.format(output=text, target_tokens=target_tokens)
        try:
            result = await self.pool.execute("claude", prompt, "/tmp", timeout=30)
            if result.success and result.output and len(result.output) < len(text):
                return result.output.strip()
        except Exception:
            pass
        return text

    # ==================== 知识管理 ====================

    def record_knowledge(self, key: str, fact: str) -> None:
        self._knowledge_base[key] = fact

    def record_failed_approach(self, subtask_id: str, approach: str) -> None:
        if subtask_id not in self._failed_approaches:
            self._failed_approaches[subtask_id] = []
        self._failed_approaches[subtask_id].append(approach)

    def extract_artifacts_from_output(self, task_id: str, output: str) -> None:
        file_patterns = re.findall(
            r'(?:created|wrote|saved|generated|modified)\s+[`"]?([/\w._-]+\.\w+)',
            output, re.IGNORECASE
        )
        for path in file_patterns:
            key = os.path.basename(path)
            self.artifacts.register(key, "file", path, f"Produced by task {task_id}", task_id)

    # ==================== 旧接口（向后兼容） ====================

    def set_context(self, key: str, value: str) -> None:
        self._context[key] = value

    def get_context(self, key: str) -> Optional[str]:
        return self._context.get(key)

    def get_summary(self, task_id: str) -> Optional[str]:
        return self._summaries.get(task_id)

    def build_prompt_with_context(self, task_id: str) -> str:
        task = self.state.get_task(task_id)
        if not task:
            return ""
        prompt_parts = [task.prompt]
        for dep_id in task.dependencies:
            dep_task = self.state.get_task(dep_id)
            if dep_task and dep_task.result:
                summary = self._summaries.get(dep_id, dep_task.result)
                prompt_parts.append(f"\nContext from previous task: {summary}")
        return '\n'.join(prompt_parts)
