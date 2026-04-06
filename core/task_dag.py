"""
Task DAG - 有向无环图任务编排数据结构

支持任务分解、依赖管理、并行执行、质量评估、重试追踪
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


# ==================== 评估与重试 ====================

@dataclass
class EvaluationResult:
    """质量评估结果（保留供向后兼容）"""
    passed: bool
    score: float                                    # 0.0 ~ 1.0
    criteria_results: Dict[str, bool] = field(default_factory=dict)
    failure_reasons: List[str] = field(default_factory=list)
    recommended_action: str = "accept"              # accept | retry_same | retry_different | decompose | escalate
    evaluator_reasoning: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'EvaluationResult':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def success(cls) -> 'EvaluationResult':
        return cls(passed=True, score=1.0, recommended_action="accept")

    @classmethod
    def from_exit_code(cls, success: bool) -> 'EvaluationResult':
        """降级：仅根据退出码判断"""
        return cls(
            passed=success,
            score=1.0 if success else 0.0,
            recommended_action="accept" if success else "retry_same",
            evaluator_reasoning="Fallback: evaluated by exit code only",
        )


@dataclass
class ReviewVerdict:
    """
    协调者审阅裁定 — 替代机械打分的智能审阅

    LLM 理解输出内容后产出的行动计划，不再是 pass/fail 二元判断，
    而是对输出各部分的语义理解和下一步的具体指令。
    """
    # 输出理解
    understanding: str = ""                         # LLM 对输出内容的理解总结
    usable_parts: List[str] = field(default_factory=list)    # 可用的输出片段/要点
    problematic_parts: List[str] = field(default_factory=list)  # 有问题的部分及原因

    # 行动决策（LLM 自主决定）
    decision: str = "proceed"                       # proceed | rework | partial_rework | decompose | escalate | abort
    reasoning: str = ""                             # 为什么做这个决定

    # 下游指令
    forward_context: str = ""                       # 应传递给下游 agent 的精炼上下文
    rework_instructions: str = ""                   # 如果 rework，具体要修改什么
    rework_agent: Optional[str] = None              # 如果需要换 agent
    new_subtasks: Optional[List[dict]] = None       # 如果 decompose，LLM 设计的子任务
    plan_adjustments: Optional[List[str]] = None    # 对后续计划的调整建议

    # 完成条件判断
    goal_progress: str = ""                         # 对整体目标的推进程度描述
    ready_for_next: bool = True                     # 是否满足推进到下一步的条件

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ReviewVerdict':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_evaluation_result(self) -> EvaluationResult:
        """向后兼容：转换为旧的 EvaluationResult"""
        passed = self.decision in ("proceed", "partial_rework")
        score = {"proceed": 1.0, "partial_rework": 0.7, "rework": 0.3,
                 "decompose": 0.2, "escalate": 0.1, "abort": 0.0}.get(self.decision, 0.5)
        return EvaluationResult(
            passed=passed, score=score,
            failure_reasons=self.problematic_parts,
            recommended_action=self.decision,
            evaluator_reasoning=self.reasoning,
        )


@dataclass
class AttemptRecord:
    """单次执行尝试记录"""
    attempt_number: int
    agent_type: str
    prompt_used: str
    result_output: str = ""
    result_success: bool = False
    evaluation: Optional[EvaluationResult] = None
    strategy_used: str = "initial"                  # initial | refined_prompt | switched_agent | decomposed
    duration_ms: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'AttemptRecord':
        data = dict(data)
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data.get('evaluation'), dict):
            data['evaluation'] = EvaluationResult.from_dict(data['evaluation'])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ==================== 失败分析与重试策略 ====================

@dataclass
class FailureAnalysis:
    """失败根因分析"""
    root_cause: str             # prompt_issue | agent_limitation | external_failure | task_too_complex | missing_context
    explanation: str = ""
    confidence: float = 0.5


@dataclass
class RetryStrategy:
    """重试策略"""
    action: str                                     # retry_same | retry_different | decompose | escalate | skip
    refined_prompt: Optional[str] = None
    new_agent_type: Optional[str] = None
    new_subtasks: Optional[List[dict]] = None       # 分解时使用
    additional_context: Optional[str] = None


# ==================== 子任务 ====================

@dataclass
class SubTask:
    """DAG 中的子任务节点"""
    id: str
    description: str
    agent_type: str                                 # claude | kimi
    acceptance_criteria: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    risk_level: str = "low"                         # low | medium | high
    is_checkpoint: bool = False
    max_retries: int = 3
    status: str = "pending"                         # pending | running | completed | failed | skipped
    result: Optional[str] = None
    result_summary: Optional[str] = None
    evaluation: Optional[EvaluationResult] = None
    attempt_history: List[AttemptRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def attempts(self) -> int:
        return len(self.attempt_history)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        d['updated_at'] = self.updated_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'SubTask':
        data = dict(data)
        for ts_field in ('created_at', 'updated_at'):
            if isinstance(data.get(ts_field), str):
                data[ts_field] = datetime.fromisoformat(data[ts_field])
        if isinstance(data.get('evaluation'), dict):
            data['evaluation'] = EvaluationResult.from_dict(data['evaluation'])
        if data.get('attempt_history'):
            data['attempt_history'] = [
                AttemptRecord.from_dict(a) if isinstance(a, dict) else a
                for a in data['attempt_history']
            ]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ==================== 任务 DAG ====================

@dataclass
class TaskDAG:
    """有向无环图 — 任务编排的核心数据结构"""
    id: str
    goal: str
    subtasks: Dict[str, SubTask] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)  # (from_id, to_id)
    checkpoints: List[str] = field(default_factory=list)
    version: int = 1
    plan_history: List[str] = field(default_factory=list)       # JSON snapshots
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def get_ready_subtasks(self) -> List[SubTask]:
        """返回所有依赖已满足的 pending 子任务"""
        ready = []
        for st in self.subtasks.values():
            if st.status != "pending":
                continue
            deps_met = all(
                self.subtasks[dep_id].status in ("completed", "skipped")
                for dep_id in st.dependencies
                if dep_id in self.subtasks
            )
            if deps_met:
                ready.append(st)
        return ready

    def is_complete(self) -> bool:
        return all(st.status in ("completed", "skipped") for st in self.subtasks.values())

    def has_failed_terminal(self) -> bool:
        """存在无法继续的失败任务（已耗尽重试）"""
        return any(
            st.status == "failed" and st.attempts >= st.max_retries
            for st in self.subtasks.values()
        )

    def mark_complete(self, subtask_id: str, result: str, summary: Optional[str] = None) -> None:
        st = self.subtasks[subtask_id]
        st.status = "completed"
        st.result = result
        st.result_summary = summary
        st.updated_at = datetime.now()
        self.updated_at = datetime.now()

    def mark_failed(self, subtask_id: str, error: str) -> None:
        st = self.subtasks[subtask_id]
        st.status = "failed"
        st.result = error
        st.updated_at = datetime.now()
        self.updated_at = datetime.now()

    def mark_running(self, subtask_id: str) -> None:
        st = self.subtasks[subtask_id]
        st.status = "running"
        st.updated_at = datetime.now()

    def add_subtask(self, subtask: SubTask, after: Optional[List[str]] = None, before: Optional[List[str]] = None) -> None:
        """动态添加子任务（用于重规划和任务分解）"""
        self.subtasks[subtask.id] = subtask
        for dep_id in (after or []):
            self.edges.append((dep_id, subtask.id))
            if dep_id not in subtask.dependencies:
                subtask.dependencies.append(dep_id)
        for target_id in (before or []):
            self.edges.append((subtask.id, target_id))
            target = self.subtasks.get(target_id)
            if target and subtask.id not in target.dependencies:
                target.dependencies.append(subtask.id)
        if subtask.is_checkpoint and subtask.id not in self.checkpoints:
            self.checkpoints.append(subtask.id)
        self.updated_at = datetime.now()

    def remove_subtask(self, subtask_id: str) -> None:
        self.subtasks.pop(subtask_id, None)
        self.edges = [(a, b) for a, b in self.edges if a != subtask_id and b != subtask_id]
        for st in self.subtasks.values():
            if subtask_id in st.dependencies:
                st.dependencies.remove(subtask_id)
        if subtask_id in self.checkpoints:
            self.checkpoints.remove(subtask_id)
        self.updated_at = datetime.now()

    def reset_subtask(self, subtask_id: str) -> None:
        """重置子任务为 pending（用于重试）"""
        st = self.subtasks[subtask_id]
        st.status = "pending"
        st.result = None
        st.result_summary = None
        st.evaluation = None
        st.updated_at = datetime.now()

    def snapshot(self) -> None:
        """保存当前计划快照（用于版本追踪）"""
        self.plan_history.append(self.to_json())
        self.version += 1

    @property
    def progress(self) -> int:
        if not self.subtasks:
            return 0
        done = sum(1 for st in self.subtasks.values() if st.status in ("completed", "skipped"))
        return int(done / len(self.subtasks) * 100)

    @property
    def total_cost(self) -> float:
        return sum(a.cost_usd for st in self.subtasks.values() for a in st.attempt_history)

    @property
    def total_attempts(self) -> int:
        return sum(st.attempts for st in self.subtasks.values())

    def to_json(self) -> str:
        data = {
            "id": self.id, "goal": self.goal,
            "subtasks": {k: v.to_dict() for k, v in self.subtasks.items()},
            "edges": self.edges, "checkpoints": self.checkpoints,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        return json.dumps(data, ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, raw: str) -> 'TaskDAG':
        data = json.loads(raw)
        subtasks = {k: SubTask.from_dict(v) for k, v in data.get("subtasks", {}).items()}
        edges = [tuple(e) for e in data.get("edges", [])]
        return cls(
            id=data["id"], goal=data["goal"], subtasks=subtasks, edges=edges,
            checkpoints=data.get("checkpoints", []),
            version=data.get("version", 1),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


# ==================== 编排配置与结果 ====================

@dataclass
class OrchestrationConfig:
    """编排配置"""
    max_rounds: int = 5
    max_retries_per_subtask: int = 3
    enable_checkpoints: bool = True
    enable_dynamic_replan: bool = True
    global_timeout_seconds: int = 1800              # 30 分钟
    checkpoint_mode: str = "on_high_risk"           # always | on_high_risk | never


@dataclass
class OrchestrationResult:
    """编排最终结果"""
    success: bool
    final_output: str
    dag: Optional[TaskDAG] = None
    total_duration_ms: int = 0
    total_cost_usd: float = 0.0
    total_agent_calls: int = 0
    summary: str = ""
