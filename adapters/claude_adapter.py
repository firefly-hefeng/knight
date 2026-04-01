"""Claude Code Adapter - 封装Claude Code CLI调用"""
import asyncio
import json
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    cost_usd: float = 0.0
    duration_ms: int = 0


class ClaudeAdapter:
    """Claude Code适配器 - 最小化实现"""

    async def execute(
        self,
        prompt: str,
        work_dir: str,
        timeout: int = 300
    ) -> TaskResult:
        """执行任务"""
        # 确保工作目录存在
        os.makedirs(work_dir, exist_ok=True)

        cmd = [
            'claude', '--print', prompt,
            '--add-dir', work_dir,
            '--allowedTools', 'Write,Read,Bash,Edit'
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            output = stdout.decode().strip()
            return TaskResult(
                success=proc.returncode == 0,
                output=output,
                error=stderr.decode() if proc.returncode != 0 else None
            )

        except asyncio.TimeoutError:
            return TaskResult(success=False, output='', error='Timeout')
        except Exception as e:
            return TaskResult(success=False, output='', error=str(e))
