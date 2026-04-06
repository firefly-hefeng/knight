"""Persistence - SQLite持久化（WAL模式，持久连接）"""
import sqlite3
import json
from typing import Optional, List
from datetime import datetime
from .state_manager import TaskState


class TaskPersistence:
    """任务持久化"""

    def __init__(self, db_path: str = "knight.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        c = self._conn
        c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                prompt TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                work_dir TEXT NOT NULL,
                dependencies TEXT,
                result TEXT,
                error TEXT,
                progress INTEGER DEFAULT 0,
                logs TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                parent_task_id TEXT,
                dag_json TEXT,
                checkpoint_data TEXT
            )
        """)
        # 迁移旧表
        for col, default in [
            ("progress", "INTEGER DEFAULT 0"),
            ("logs", "TEXT"),
            ("parent_task_id", "TEXT"),
            ("dag_json", "TEXT"),
            ("checkpoint_data", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE tasks ADD COLUMN {col} {default}")
            except sqlite3.OperationalError:
                pass

        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback_requests (
                task_id TEXT PRIMARY KEY,
                checkpoint_type TEXT NOT NULL,
                question TEXT NOT NULL,
                context TEXT,
                options TEXT,
                dag_snapshot TEXT,
                created_at TEXT NOT NULL,
                response_action TEXT,
                response_message TEXT,
                responded_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS attempt_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_task_id TEXT NOT NULL,
                subtask_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                agent_type TEXT NOT NULL,
                prompt_used TEXT,
                result_output TEXT,
                result_success INTEGER,
                evaluation_json TEXT,
                strategy TEXT,
                duration_ms INTEGER,
                cost_usd REAL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (parent_task_id) REFERENCES tasks(task_id)
            )
        """)
        c.commit()

    def save_task(self, task: TaskState):
        """保存任务"""
        self._conn.execute("""
            INSERT OR REPLACE INTO tasks
            (task_id, status, prompt, agent_type, work_dir, dependencies,
             result, error, progress, logs, created_at, updated_at,
             parent_task_id, dag_json, checkpoint_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.task_id, task.status, task.prompt, task.agent_type,
            task.work_dir, json.dumps(task.dependencies),
            task.result, task.error,
            task.progress, json.dumps(task.logs),
            task.created_at.isoformat(), task.updated_at.isoformat(),
            task.parent_task_id, task.dag_json, task.checkpoint_data,
        ))
        self._conn.commit()

    def _row_to_task(self, row) -> TaskState:
        """将数据库行转换为 TaskState"""
        def safe(idx, default=None):
            return row[idx] if len(row) > idx and row[idx] is not None else default

        return TaskState(
            task_id=row[0], status=row[1], prompt=row[2],
            agent_type=row[3], work_dir=row[4],
            dependencies=json.loads(row[5]) if row[5] else [],
            result=row[6], error=row[7],
            progress=safe(8, 0),
            logs=json.loads(safe(9, "[]")),
            created_at=datetime.fromisoformat(safe(10, datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(safe(11, datetime.now().isoformat())),
            parent_task_id=safe(12),
            dag_json=safe(13),
            checkpoint_data=safe(14),
        )

    def load_task(self, task_id: str) -> Optional[TaskState]:
        """加载任务"""
        row = self._conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def load_all_tasks(self) -> List[TaskState]:
        """加载所有任务"""
        rows = self._conn.execute("SELECT * FROM tasks").fetchall()
        tasks = []
        for row in rows:
            try:
                tasks.append(self._row_to_task(row))
            except Exception as e:
                print(f"Warning: Failed to load task from row: {e}")
        return tasks

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        cursor = self._conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ==================== 反馈请求 ====================

    def save_feedback_request(self, task_id: str, checkpoint_type: str,
                              question: str, context: str = "",
                              options: list = None, dag_snapshot: str = "") -> None:
        self._conn.execute("""
            INSERT OR REPLACE INTO feedback_requests
            (task_id, checkpoint_type, question, context, options, dag_snapshot, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, checkpoint_type, question, context,
              json.dumps(options or []), dag_snapshot, datetime.now().isoformat()))
        self._conn.commit()

    def save_feedback_response(self, task_id: str, action: str, message: str = "") -> None:
        self._conn.execute("""
            UPDATE feedback_requests
            SET response_action = ?, response_message = ?, responded_at = ?
            WHERE task_id = ?
        """, (action, message, datetime.now().isoformat(), task_id))
        self._conn.commit()

    def load_feedback_request(self, task_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM feedback_requests WHERE task_id = ? AND response_action IS NULL",
            (task_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "task_id": row[0], "checkpoint_type": row[1], "question": row[2],
            "context": row[3], "options": json.loads(row[4]) if row[4] else [],
            "dag_snapshot": row[5], "created_at": row[6],
        }

    # ==================== 尝试历史 ====================

    def save_attempt(self, parent_task_id: str, subtask_id: str,
                     attempt_number: int, agent_type: str,
                     prompt_used: str = "", result_output: str = "",
                     result_success: bool = False, evaluation_json: str = "",
                     strategy: str = "initial", duration_ms: int = 0,
                     cost_usd: float = 0.0) -> None:
        self._conn.execute("""
            INSERT INTO attempt_history
            (parent_task_id, subtask_id, attempt_number, agent_type,
             prompt_used, result_output, result_success, evaluation_json,
             strategy, duration_ms, cost_usd, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (parent_task_id, subtask_id, attempt_number, agent_type,
              prompt_used, result_output, int(result_success), evaluation_json,
              strategy, duration_ms, cost_usd, datetime.now().isoformat()))
        self._conn.commit()

    def load_attempts(self, parent_task_id: str) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM attempt_history WHERE parent_task_id = ? ORDER BY id",
            (parent_task_id,)
        ).fetchall()
        return [{
            "id": r[0], "parent_task_id": r[1], "subtask_id": r[2],
            "attempt_number": r[3], "agent_type": r[4], "prompt_used": r[5],
            "result_output": r[6], "result_success": bool(r[7]),
            "evaluation_json": r[8], "strategy": r[9],
            "duration_ms": r[10], "cost_usd": r[11], "timestamp": r[12],
        } for r in rows]

    def close(self):
        self._conn.close()
