"""
Agent Registry — 动态 Agent 注册与管理

设计：
  - 基于配置驱动，支持 YAML/dict 注册新 Agent
  - 每个 Agent 定义：name, command, args_template, output_parser, concurrency, capabilities
  - 运行时可添加/移除 Agent，无需改代码
  - 内置 CLI adapter（通用）：拼接命令行 → subprocess → 解析输出
"""
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Protocol, runtime_checkable

from adapters.claude_adapter import TaskResult

logger = logging.getLogger(__name__)


# ==================== Agent 定义 ====================

@dataclass
class AgentDefinition:
    """Agent 定义 — 描述如何调用一个 Agent"""
    name: str                                       # 唯一标识：claude, kimi, codex, ...
    command: str                                    # CLI 命令：claude, kimi, codex, ...
    args_template: List[str] = field(default_factory=list)  # 参数模板
    concurrency: int = 2                            # 并发上限
    capabilities: List[str] = field(default_factory=list)   # coding, search, analysis, ...
    cost_per_call_usd: float = 0.0                  # 预估单次调用成本
    output_format: str = "raw"                      # raw | stream-json | json
    health_command: Optional[str] = None            # 健康检查命令，默认 "{command} --version"
    enabled: bool = True
    description: str = ""
    max_timeout: int = 600                          # 最大超时秒数

    def __post_init__(self):
        if not self.health_command:
            self.health_command = f"{self.command} --version"


# ==================== 输出解析器 ====================

def parse_raw(stdout: str, stderr: str, returncode: int) -> TaskResult:
    """原始输出解析（Claude 风格）"""
    return TaskResult(
        success=returncode == 0,
        output=stdout.strip(),
        error=stderr if returncode != 0 else None,
    )


def parse_stream_json(stdout: str, stderr: str, returncode: int) -> TaskResult:
    """Stream JSON 解析（Kimi 风格）"""
    output_lines = stdout.strip().split('\n')
    final_output = []
    for line in output_lines:
        if line.strip():
            try:
                msg = json.loads(line)
                if msg.get('role') == 'assistant':
                    for c in msg.get('content', []):
                        if c.get('type') == 'text':
                            final_output.append(c.get('text', ''))
            except json.JSONDecodeError:
                final_output.append(line)
    return TaskResult(
        success=True,
        output='\n'.join(final_output),
        cost_usd=0.0,
    )


def parse_json_output(stdout: str, stderr: str, returncode: int) -> TaskResult:
    """JSON 输出解析（通用）"""
    try:
        data = json.loads(stdout.strip())
        return TaskResult(
            success=data.get("success", returncode == 0),
            output=data.get("output", stdout),
            error=data.get("error"),
            cost_usd=data.get("cost_usd", 0.0),
        )
    except json.JSONDecodeError:
        return parse_raw(stdout, stderr, returncode)


OUTPUT_PARSERS = {
    "raw": parse_raw,
    "stream-json": parse_stream_json,
    "json": parse_json_output,
}


# ==================== Agent 健康状态 ====================

@dataclass
class AgentHealth:
    """Agent 健康状态"""
    name: str
    healthy: bool = True
    last_check: float = 0.0                         # timestamp
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    avg_latency_ms: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    total_cost_usd: float = 0.0


# ==================== Agent Registry ====================

class AgentRegistry:
    """
    动态 Agent 注册表

    使用方式:
        registry = AgentRegistry()
        registry.register(AgentDefinition(name="codex", command="codex", ...))
        result = await registry.execute("codex", prompt, work_dir)
    """

    def __init__(self):
        self._agents: Dict[str, AgentDefinition] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._health: Dict[str, AgentHealth] = {}
        self._patrol_task: Optional[asyncio.Task] = None
        self._patrol_interval: int = 300            # 5 分钟

        # 注册内置 Agent
        self._register_builtins()

    def _register_builtins(self):
        """注册内置 Agent（Claude + Kimi）"""
        self.register(AgentDefinition(
            name="claude",
            command="claude",
            args_template=["--print", "{prompt}", "--add-dir", "{work_dir}",
                           "--allowedTools", "Write,Read,Bash,Edit"],
            concurrency=2,
            capabilities=["coding", "analysis", "writing", "long_context", "debugging"],
            cost_per_call_usd=0.05,
            output_format="raw",
            description="Advanced AI agent for coding, analysis, and long-context tasks",
        ))
        self.register(AgentDefinition(
            name="kimi",
            command="kimi",
            args_template=["--print", "-p", "{prompt}",
                           "--output-format", "stream-json",
                           "--work-dir", "{work_dir}"],
            concurrency=3,
            capabilities=["search", "translation", "fast_response", "chinese"],
            cost_per_call_usd=0.0,
            output_format="stream-json",
            description="Fast AI agent for search, translation, and quick responses",
        ))

    # ==================== 注册 / 注销 ====================

    def register(self, definition: AgentDefinition) -> None:
        """注册一个 Agent"""
        self._agents[definition.name] = definition
        self._semaphores[definition.name] = asyncio.Semaphore(definition.concurrency)
        self._health[definition.name] = AgentHealth(name=definition.name)
        logger.info(f"Agent registered: {definition.name} "
                    f"(concurrency={definition.concurrency}, caps={definition.capabilities})")

    def unregister(self, name: str) -> bool:
        """注销一个 Agent"""
        if name in self._agents:
            del self._agents[name]
            del self._semaphores[name]
            del self._health[name]
            logger.info(f"Agent unregistered: {name}")
            return True
        return False

    def register_from_config(self, configs: List[dict]) -> None:
        """从配置列表批量注册"""
        for cfg in configs:
            try:
                defn = AgentDefinition(**cfg)
                self.register(defn)
            except Exception as e:
                logger.warning(f"Failed to register agent from config: {e}")

    # ==================== 查询 ====================

    def get(self, name: str) -> Optional[AgentDefinition]:
        return self._agents.get(name)

    def list_agents(self) -> List[AgentDefinition]:
        return list(self._agents.values())

    def list_healthy(self) -> List[str]:
        """返回健康且启用的 Agent 名称"""
        return [
            name for name, defn in self._agents.items()
            if defn.enabled and self._health[name].healthy
        ]

    def get_health(self, name: str) -> Optional[AgentHealth]:
        return self._health.get(name)

    def get_all_health(self) -> Dict[str, AgentHealth]:
        return dict(self._health)

    def get_capabilities_map(self) -> Dict[str, List[str]]:
        """返回 {capability: [agent_names]} 映射"""
        cap_map: Dict[str, List[str]] = {}
        for name, defn in self._agents.items():
            if defn.enabled and self._health[name].healthy:
                for cap in defn.capabilities:
                    cap_map.setdefault(cap, []).append(name)
        return cap_map

    def find_by_capability(self, capability: str) -> List[str]:
        """找到具有指定能力的健康 Agent"""
        return [
            name for name, defn in self._agents.items()
            if capability in defn.capabilities
            and defn.enabled
            and self._health[name].healthy
        ]

    # ==================== 执行 ====================

    async def execute(
        self, agent_name: str, prompt: str, work_dir: str, timeout: int = 300
    ) -> TaskResult:
        """执行任务 — 通用 CLI 调用"""
        defn = self._agents.get(agent_name)
        if not defn:
            return TaskResult(success=False, output="", error=f"Unknown agent: {agent_name}")
        if not defn.enabled:
            return TaskResult(success=False, output="", error=f"Agent disabled: {agent_name}")

        health = self._health[agent_name]
        if not health.healthy:
            logger.warning(f"Agent {agent_name} is unhealthy, attempting anyway")

        timeout = min(timeout, defn.max_timeout)
        semaphore = self._semaphores[agent_name]

        async with semaphore:
            start = time.time()
            try:
                result = await self._run_cli(defn, prompt, work_dir, timeout)
                duration = int((time.time() - start) * 1000)
                result.duration_ms = duration
                result.cost_usd = defn.cost_per_call_usd

                # 更新健康统计
                health.total_calls += 1
                health.total_cost_usd += result.cost_usd
                if result.success:
                    health.consecutive_failures = 0
                    health.healthy = True
                else:
                    health.total_failures += 1
                # 滑动平均延迟
                health.avg_latency_ms = (health.avg_latency_ms * 0.8 + duration * 0.2) if health.avg_latency_ms else duration

                return result
            except Exception as e:
                health.total_calls += 1
                health.total_failures += 1
                health.consecutive_failures += 1
                if health.consecutive_failures >= 3:
                    health.healthy = False
                    health.last_error = str(e)
                return TaskResult(success=False, output="", error=str(e))

    async def _run_cli(
        self, defn: AgentDefinition, prompt: str, work_dir: str, timeout: int
    ) -> TaskResult:
        """通用 CLI 执行 — 带进程组杀死保证"""
        os.makedirs(work_dir, exist_ok=True)

        # 构建命令
        cmd = [defn.command]
        for arg in defn.args_template:
            cmd.append(arg.format(prompt=prompt, work_dir=work_dir))

        # 使用 start_new_session 创建新进程组，确保超时时能杀死所有子进程
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
            start_new_session=True,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            # 超时：杀死整个进程组（包括子进程）
            import signal as sig
            try:
                os.killpg(os.getpgid(proc.pid), sig.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            # 给 SIGTERM 1 秒的优雅退出时间
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                try:
                    os.killpg(os.getpgid(proc.pid), sig.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
            return TaskResult(success=False, output="", error=f"Timeout after {timeout}s")

        parser = OUTPUT_PARSERS.get(defn.output_format, parse_raw)
        return parser(stdout.decode(), stderr.decode(), proc.returncode or 0)

    async def execute_batch(self, tasks: List[tuple]) -> List[TaskResult]:
        """并行执行: tasks = [(agent, prompt, work_dir, timeout), ...]"""
        return await asyncio.gather(
            *(self.execute(a, p, w, t) for a, p, w, t in tasks),
            return_exceptions=False,
        )

    # ==================== 健康巡检 ====================

    async def check_health(self, agent_name: str) -> bool:
        """检查单个 Agent 健康"""
        defn = self._agents.get(agent_name)
        if not defn:
            return False
        health = self._health[agent_name]

        try:
            proc = await asyncio.create_subprocess_shell(
                defn.health_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=15)
            ok = proc.returncode == 0

            health.last_check = time.time()
            if ok:
                health.healthy = True
                health.consecutive_failures = 0
                health.last_error = None
            else:
                health.consecutive_failures += 1
                if health.consecutive_failures >= 3:
                    health.healthy = False
                    health.last_error = f"Health check failed (exit {proc.returncode})"
            return ok
        except Exception as e:
            health.last_check = time.time()
            health.consecutive_failures += 1
            health.last_error = str(e)
            if health.consecutive_failures >= 3:
                health.healthy = False
            return False

    async def check_all_health(self) -> Dict[str, bool]:
        """检查所有 Agent 健康"""
        results = {}
        for name in self._agents:
            results[name] = await self.check_health(name)
        return results

    def start_patrol(self, interval: int = 300) -> None:
        """启动定期健康巡检"""
        self._patrol_interval = interval
        if self._patrol_task is None or self._patrol_task.done():
            self._patrol_task = asyncio.create_task(self._patrol_loop())
            logger.info(f"Health patrol started (interval={interval}s)")

    def stop_patrol(self) -> None:
        """停止巡检"""
        if self._patrol_task and not self._patrol_task.done():
            self._patrol_task.cancel()
            logger.info("Health patrol stopped")

    async def _patrol_loop(self):
        """巡检循环"""
        while True:
            try:
                await asyncio.sleep(self._patrol_interval)
                results = await self.check_all_health()
                unhealthy = [n for n, ok in results.items() if not ok]
                if unhealthy:
                    logger.warning(f"Unhealthy agents: {unhealthy}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health patrol error: {e}")

    # ==================== 成本追踪 ====================

    def get_total_cost(self) -> float:
        """所有 Agent 的累计成本"""
        return sum(h.total_cost_usd for h in self._health.values())

    def get_cost_breakdown(self) -> Dict[str, float]:
        """按 Agent 分类的成本"""
        return {name: h.total_cost_usd for name, h in self._health.items()}

    def get_stats(self) -> Dict[str, Any]:
        """完整统计"""
        return {
            "agents": {
                name: {
                    "healthy": h.healthy,
                    "total_calls": h.total_calls,
                    "total_failures": h.total_failures,
                    "success_rate": f"{(1 - h.total_failures / max(1, h.total_calls)) * 100:.1f}%",
                    "avg_latency_ms": int(h.avg_latency_ms),
                    "total_cost_usd": round(h.total_cost_usd, 4),
                    "last_error": h.last_error,
                }
                for name, h in self._health.items()
            },
            "total_cost_usd": round(self.get_total_cost(), 4),
            "healthy_count": len(self.list_healthy()),
            "total_count": len(self._agents),
        }
