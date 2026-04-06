"""Tests for OrchestratorLoop._parse_plan — plan parsing from various LLM outputs."""
import pytest

from core.orchestrator import OrchestratorLoop
from core.evaluator import QualityEvaluator
from core.context_manager import ContextManager
from core.state_manager import StateManager


class TestParsePlan:
    """Test OrchestratorLoop._parse_plan with various LLM response formats."""

    def setup_method(self):
        state = StateManager(enable_persistence=False)
        ctx = ContextManager(state, agent_pool=None)
        ev = QualityEvaluator(agent_pool=None)
        self.orch = OrchestratorLoop(
            agent_pool=None, state=state,
            context_mgr=ctx, evaluator=ev,
        )

    def test_clean_json(self):
        response = '''{
            "subtasks": [
                {"id": "s1", "description": "Design API", "agent_type": "claude"},
                {"id": "s2", "description": "Implement API", "agent_type": "claude", "dependencies": ["s1"]},
                {"id": "s3", "description": "Write tests", "agent_type": "kimi", "dependencies": ["s2"]}
            ],
            "edges": [["s1", "s2"], ["s2", "s3"]]
        }'''
        dag = self.orch._parse_plan(response, "parent-1", "Build API")
        assert dag is not None
        assert len(dag.subtasks) == 3
        assert dag.subtasks["s1"].agent_type == "claude"
        assert dag.subtasks["s2"].dependencies == ["s1"]
        assert dag.edges == [("s1", "s2"), ("s2", "s3")]
        assert dag.goal == "Build API"

    def test_json_in_code_block(self):
        response = '''Here's my plan:
```json
{
    "subtasks": [
        {"id": "a", "description": "Step A", "agent_type": "claude"}
    ],
    "edges": []
}
```'''
        dag = self.orch._parse_plan(response, "p1", "goal")
        assert dag is not None
        assert len(dag.subtasks) == 1

    def test_json_with_preamble(self):
        response = '''I'll break this down into subtasks:
{"subtasks": [{"id": "x", "description": "Do X"}], "edges": []}'''
        dag = self.orch._parse_plan(response, "p1", "goal")
        assert dag is not None
        assert "x" in dag.subtasks

    def test_empty_subtasks_returns_none(self):
        response = '{"subtasks": [], "edges": []}'
        dag = self.orch._parse_plan(response, "p1", "goal")
        assert dag is None

    def test_invalid_json_returns_none(self):
        response = "I don't know how to plan this."
        dag = self.orch._parse_plan(response, "p1", "goal")
        assert dag is None

    def test_optional_fields_default(self):
        response = '''{
            "subtasks": [
                {"id": "s1", "description": "Do something"}
            ]
        }'''
        dag = self.orch._parse_plan(response, "p1", "goal")
        assert dag is not None
        st = dag.subtasks["s1"]
        assert st.agent_type == "claude"  # default
        assert st.risk_level == "low"  # default
        assert st.is_checkpoint is False  # default
        assert st.dependencies == []

    def test_checkpoint_subtask(self):
        response = '''{
            "subtasks": [
                {"id": "s1", "description": "Deploy", "is_checkpoint": true, "risk_level": "high"}
            ]
        }'''
        dag = self.orch._parse_plan(response, "p1", "goal")
        assert dag is not None
        assert dag.subtasks["s1"].is_checkpoint is True
        assert "s1" in dag.checkpoints
        assert dag.subtasks["s1"].risk_level == "high"

    def test_acceptance_criteria_preserved(self):
        response = '''{
            "subtasks": [
                {"id": "s1", "description": "Build", "acceptance_criteria": ["compiles", "no warnings"]}
            ]
        }'''
        dag = self.orch._parse_plan(response, "p1", "goal")
        st = dag.subtasks["s1"]
        assert st.acceptance_criteria == ["compiles", "no warnings"]
