"""Tests for core/evaluator.py — ReviewVerdict parsing, fallback, text inference."""
import pytest

from core.evaluator import QualityEvaluator
from core.task_dag import SubTask, ReviewVerdict


class TestParseReview:
    """Test QualityEvaluator._parse_review with various LLM response formats."""

    def setup_method(self):
        # We pass None for agent_pool since we only test synchronous parsing methods
        self.evaluator = QualityEvaluator(agent_pool=None)

    def test_clean_json(self):
        response = '''{
            "understanding": "Agent wrote correct Python code",
            "usable_parts": ["function implementation"],
            "problematic_parts": [],
            "decision": "proceed",
            "reasoning": "All criteria met",
            "forward_context": "def hello(): print('hi')",
            "goal_progress": "50% done",
            "ready_for_next": true
        }'''
        v = self.evaluator._parse_review(response)
        assert v.decision == "proceed"
        assert v.understanding == "Agent wrote correct Python code"
        assert v.usable_parts == ["function implementation"]
        assert v.ready_for_next is True

    def test_json_in_markdown_code_block(self):
        response = '''Here is my review:
```json
{
    "understanding": "Code has a bug",
    "decision": "rework",
    "reasoning": "Syntax error on line 5",
    "rework_instructions": "Fix the missing colon"
}
```'''
        v = self.evaluator._parse_review(response)
        assert v.decision == "rework"
        assert v.rework_instructions == "Fix the missing colon"

    def test_json_with_leading_text(self):
        response = '''After careful analysis, I conclude:
{"decision": "proceed", "understanding": "Good output", "forward_context": "result"}'''
        v = self.evaluator._parse_review(response)
        assert v.decision == "proceed"

    def test_invalid_json_falls_back_to_inference(self):
        response = "This output is correct and complete. The function works well."
        v = self.evaluator._parse_review(response)
        # _infer_from_text should detect positive words
        assert v.decision == "proceed"

    def test_missing_fields_get_defaults(self):
        response = '{"decision": "rework"}'
        v = self.evaluator._parse_review(response)
        assert v.decision == "rework"
        assert v.understanding == ""
        assert v.usable_parts == []
        assert v.ready_for_next is True  # default

    def test_all_decision_types_accepted(self):
        for decision in ["proceed", "rework", "partial_rework", "decompose", "escalate", "abort"]:
            response = f'{{"decision": "{decision}"}}'
            v = self.evaluator._parse_review(response)
            assert v.decision == decision


class TestInferFromText:
    def setup_method(self):
        self.evaluator = QualityEvaluator(agent_pool=None)

    def test_positive_text(self):
        v = self.evaluator._infer_from_text("The output is correct and complete. Good job.")
        assert v.decision == "proceed"

    def test_negative_text(self):
        v = self.evaluator._infer_from_text("There is an error in the output. The function fails.")
        assert v.decision == "rework"

    def test_mixed_text(self):
        v = self.evaluator._infer_from_text("The function is correct but there's an error in logging.")
        assert v.decision == "partial_rework"

    def test_neutral_text(self):
        v = self.evaluator._infer_from_text("The agent produced some output.")
        assert v.decision == "proceed"  # defaults to proceed when no signals


class TestFallbackReview:
    def setup_method(self):
        self.evaluator = QualityEvaluator(agent_pool=None)

    def test_success_fallback(self):
        v = self.evaluator._fallback_review("some output", success=True)
        assert v.decision == "proceed"
        assert v.ready_for_next is True
        assert "fallback" in v.understanding.lower()

    def test_failure_fallback(self):
        v = self.evaluator._fallback_review("error output", success=False)
        assert v.decision == "rework"
        assert v.ready_for_next is False
        assert v.rework_instructions != ""
