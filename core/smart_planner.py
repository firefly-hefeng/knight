"""Smart Task Planner - 智能任务分解"""
from typing import List
from .state_manager import TaskState
import uuid


class SmartTaskPlanner:
    """智能任务规划器"""

    def __init__(self, pool):
        self.pool = pool

    async def plan(self, user_request: str, work_dir: str) -> List[TaskState]:
        """使用Agent进行任务分解"""
        decompose_prompt = f"""Break this into 3-5 sequential implementation steps:
"{user_request}"

Output format (numbered list only):
1. First step
2. Second step
3. Third step"""

        result = await self.pool.execute(
            agent_type='claude',
            prompt=decompose_prompt,
            work_dir=work_dir
        )

        if not result.success:
            return self._fallback_single_task(user_request, work_dir)

        # 解析任务
        tasks = []
        prev_id = None

        for line in result.output.strip().split('\n'):
            line = line.strip()
            if not line or not (line[0].isdigit() or line.startswith('-')):
                continue

            # 提取任务文本
            task_text = line.lstrip('0123456789.-) ').strip()
            if len(task_text) < 5:
                continue

            task_id = str(uuid.uuid4())
            tasks.append(TaskState(
                task_id=task_id,
                status='pending',
                prompt=task_text,
                agent_type='claude',
                work_dir=work_dir,
                dependencies=[prev_id] if prev_id else []
            ))
            prev_id = task_id

        return tasks if tasks else self._fallback_single_task(user_request, work_dir)

    def _fallback_single_task(self, request: str, work_dir: str) -> List[TaskState]:
        """回退到单任务"""
        return [TaskState(
            task_id=str(uuid.uuid4()),
            status='pending',
            prompt=request,
            agent_type='claude',
            work_dir=work_dir
        )]
