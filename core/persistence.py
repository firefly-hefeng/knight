"""Persistence - SQLite持久化"""
import sqlite3
import json
from typing import Optional, List
from datetime import datetime
from .state_manager import TaskState, TaskStatus


class TaskPersistence:
    """任务持久化"""

    def __init__(self, db_path: str = "knight.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                prompt TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                work_dir TEXT NOT NULL,
                dependencies TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def save_task(self, task: TaskState):
        """保存任务"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.task_id, task.status, task.prompt, task.agent_type,
            task.work_dir, json.dumps(task.dependencies),
            task.result, task.error,
            task.created_at.isoformat(), task.updated_at.isoformat()
        ))
        conn.commit()
        conn.close()

    def load_task(self, task_id: str) -> Optional[TaskState]:
        """加载任务"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        conn.close()

        if not row:
            return None

        return TaskState(
            task_id=row[0], status=row[1], prompt=row[2],
            agent_type=row[3], work_dir=row[4],
            dependencies=json.loads(row[5]) if row[5] else [],
            result=row[6], error=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9])
        )

    def load_all_tasks(self) -> List[TaskState]:
        """加载所有任务"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        conn.close()

        tasks = []
        for row in rows:
            tasks.append(TaskState(
                task_id=row[0], status=row[1], prompt=row[2],
                agent_type=row[3], work_dir=row[4],
                dependencies=json.loads(row[5]) if row[5] else [],
                result=row[6], error=row[7],
                created_at=datetime.fromisoformat(row[8]),
                updated_at=datetime.fromisoformat(row[9])
            ))
        return tasks
