"""Kimi Code Adapter - 封装Kimi Code CLI调用"""
import asyncio
import json
from typing import Optional
from .claude_adapter import TaskResult


class KimiAdapter:
    """Kimi Code适配器 - 最小化实现"""

    async def execute(
        self,
        prompt: str,
        work_dir: str,
        timeout: int = 300
    ) -> TaskResult:
        """执行任务"""
        cmd = [
            'kimi', '--print', '-p', prompt,
            '--output-format', 'stream-json',
            '--work-dir', work_dir
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            # 解析stream-json输出
            output_lines = stdout.decode().strip().split('\n')
            final_output = []

            for line in output_lines:
                if line:
                    msg = json.loads(line)
                    if msg.get('role') == 'assistant':
                        content = msg.get('content', [])
                        for c in content:
                            if c.get('type') == 'text':
                                final_output.append(c.get('text', ''))

            return TaskResult(
                success=True,
                output='\n'.join(final_output),
                cost_usd=0.0  # Kimi免费
            )

        except asyncio.TimeoutError:
            return TaskResult(success=False, output='', error='Timeout')
        except Exception as e:
            return TaskResult(success=False, output='', error=str(e))
