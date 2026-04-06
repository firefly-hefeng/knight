"""Tests for core/json_extract.py — robust JSON extraction from LLM responses."""
import pytest
from core.json_extract import extract_json, _extract_balanced_braces


class TestExtractJson:
    def test_clean_json(self):
        text = '{"key": "value", "num": 42}'
        assert extract_json(text) == {"key": "value", "num": 42}

    def test_json_with_whitespace(self):
        text = '  \n  {"a": 1}  \n  '
        assert extract_json(text) == {"a": 1}

    def test_fenced_json(self):
        text = '''Here's the result:
```json
{"verdict": "PASS", "confidence": 0.9}
```
That's my analysis.'''
        r = extract_json(text)
        assert r["verdict"] == "PASS"
        assert r["confidence"] == 0.9

    def test_fenced_without_json_label(self):
        text = '''Result:
```
{"decision": "proceed"}
```'''
        r = extract_json(text)
        assert r["decision"] == "proceed"

    def test_json_with_preamble(self):
        text = '''After careful analysis, I conclude:
{"root_cause": "prompt_issue", "explanation": "too vague"}'''
        r = extract_json(text)
        assert r["root_cause"] == "prompt_issue"

    def test_json_with_postamble(self):
        text = '''{"success": true, "output": "hello"}

That completes the analysis.'''
        r = extract_json(text)
        assert r["success"] is True

    def test_natural_language_braces_before_json(self):
        """The O-1 bug: { in natural language before JSON should not confuse parser."""
        text = '''The function uses {curly braces} for scope.
Here is the structured result:
{"verdict": "FAIL", "reasoning": "Missing error handling"}'''
        r = extract_json(text)
        assert r is not None
        assert r["verdict"] == "FAIL"

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}, "name": "test"}'
        r = extract_json(text)
        assert r["outer"]["inner"] == [1, 2, 3]

    def test_json_with_escaped_braces_in_strings(self):
        text = '{"code": "function() { return \\"{}\\\"; }", "ok": true}'
        r = extract_json(text)
        assert r is not None
        assert r["ok"] is True

    def test_empty_string(self):
        assert extract_json("") is None
        assert extract_json("   ") is None

    def test_no_json(self):
        text = "This is just plain text with no JSON at all."
        assert extract_json(text) is None

    def test_invalid_json(self):
        text = '{"key": value_without_quotes}'
        assert extract_json(text) is None

    def test_multiple_json_objects_returns_first(self):
        text = '{"first": 1} some text {"second": 2}'
        r = extract_json(text)
        assert r["first"] == 1

    def test_deeply_nested(self):
        text = '{"a": {"b": {"c": {"d": "deep"}}}}'
        r = extract_json(text)
        assert r["a"]["b"]["c"]["d"] == "deep"

    def test_json_array_not_extracted(self):
        """We only extract objects, not arrays."""
        text = '[1, 2, 3]'
        assert extract_json(text) is None

    def test_real_world_planning_response(self):
        """Simulated real LLM planning output."""
        text = '''I'll break this task into subtasks for the AI agents.

```json
{
    "subtasks": [
        {"id": "s1", "description": "Design the API schema", "agent_type": "claude"},
        {"id": "s2", "description": "Implement endpoints", "agent_type": "claude", "dependencies": ["s1"]}
    ],
    "edges": [["s1", "s2"]]
}
```

This plan has two sequential subtasks.'''
        r = extract_json(text)
        assert r is not None
        assert len(r["subtasks"]) == 2
        assert r["edges"] == [["s1", "s2"]]

    def test_real_world_review_response(self):
        """Simulated review with mixed text."""
        text = '''Looking at the agent's output, I see that the implementation addresses the core requirements.

{
    "understanding": "Agent implemented a REST API with 3 endpoints",
    "usable_parts": ["GET /users", "POST /users"],
    "problematic_parts": ["DELETE /users has no auth check"],
    "decision": "partial_rework",
    "reasoning": "Missing authentication on delete endpoint",
    "rework_instructions": "Add auth middleware to DELETE /users"
}'''
        r = extract_json(text)
        assert r["decision"] == "partial_rework"
        assert "auth" in r["rework_instructions"].lower()


class TestExtractBalancedBraces:
    def test_simple(self):
        assert _extract_balanced_braces('{"a": 1}') == '{"a": 1}'

    def test_nested(self):
        assert _extract_balanced_braces('{"a": {"b": 2}}') == '{"a": {"b": 2}}'

    def test_with_prefix(self):
        r = _extract_balanced_braces('prefix {"a": 1} suffix')
        assert r == '{"a": 1}'

    def test_braces_in_string(self):
        r = _extract_balanced_braces('{"code": "x = {1, 2}"}')
        assert r is not None

    def test_no_braces(self):
        assert _extract_balanced_braces("no braces here") is None

    def test_unbalanced(self):
        assert _extract_balanced_braces("{ open but never closed") is None

    def test_natural_language_then_json(self):
        text = 'Use {curly} braces. {"real": "json"}'
        r = _extract_balanced_braces(text)
        # Should return the first balanced block
        assert r is not None
