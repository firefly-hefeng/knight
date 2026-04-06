"""Tests for core/verification_agent.py — adversarial verification."""
import pytest

from core.verification_agent import VerificationAgent, VerificationVerdict
from core.task_dag import SubTask, ReviewVerdict


class TestVerificationVerdict:
    def test_pass_to_review(self):
        v = VerificationVerdict(
            verdict="PASS", confidence=0.9,
            evidence=["All tests pass"], reasoning="Solid implementation"
        )
        rv = v.to_review_verdict()
        assert rv.decision == "proceed"
        assert rv.ready_for_next is True

    def test_fail_to_review(self):
        v = VerificationVerdict(
            verdict="FAIL", confidence=0.8,
            vulnerabilities=["SQL injection possible"],
            suggestions=["Use parameterized queries"],
            reasoning="Critical security flaw",
        )
        rv = v.to_review_verdict()
        assert rv.decision == "rework"
        assert rv.ready_for_next is False
        assert "parameterized" in rv.rework_instructions

    def test_partial_to_review(self):
        v = VerificationVerdict(
            verdict="PARTIAL", confidence=0.6,
            evidence=["Core logic correct"],
            vulnerabilities=["Missing error handling"],
            suggestions=["Add try/except blocks"],
        )
        rv = v.to_review_verdict()
        assert rv.decision == "partial_rework"
        assert rv.ready_for_next is False

    def test_to_dict(self):
        v = VerificationVerdict(verdict="PASS", confidence=0.95)
        d = v.to_dict()
        assert d["verdict"] == "PASS"
        assert d["confidence"] == 0.95

    def test_from_dict(self):
        d = {"verdict": "FAIL", "confidence": 0.8, "vulnerabilities": ["bug"]}
        v = VerificationVerdict.from_dict(d)
        assert v.verdict == "FAIL"
        assert v.vulnerabilities == ["bug"]


class TestVerificationAgentParsing:
    def setup_method(self):
        self.agent = VerificationAgent(agent_pool=None)

    def test_parse_clean_json(self):
        response = '''{
            "verdict": "PASS",
            "confidence": 0.9,
            "tested_aspects": ["correctness", "edge cases"],
            "evidence": ["All assertions pass"],
            "vulnerabilities": [],
            "suggestions": [],
            "reasoning": "Implementation is correct"
        }'''
        v = self.agent._parse_verdict(response)
        assert v.verdict == "PASS"
        assert v.confidence == 0.9
        assert "correctness" in v.tested_aspects

    def test_parse_json_in_code_block(self):
        response = '''Here is my analysis:
```json
{
    "verdict": "FAIL",
    "confidence": 0.85,
    "vulnerabilities": ["Buffer overflow in line 42"],
    "reasoning": "Critical bug found"
}
```'''
        v = self.agent._parse_verdict(response)
        assert v.verdict == "FAIL"
        assert len(v.vulnerabilities) == 1

    def test_parse_invalid_verdict_normalized(self):
        response = '{"verdict": "maybe", "confidence": 0.5}'
        v = self.agent._parse_verdict(response)
        assert v.verdict == "PARTIAL"  # normalized

    def test_parse_invalid_json(self):
        response = "This output has problems but I can't structure my response."
        v = self.agent._parse_verdict(response)
        assert v.verdict in ("PASS", "FAIL", "PARTIAL")

    def test_infer_verdict_fail(self):
        text = "There is a vulnerability in the authentication. The bug causes incorrect results."
        v = self.agent._infer_verdict(text)
        assert v.verdict == "FAIL"

    def test_infer_verdict_pass(self):
        text = "Everything is correct and complete. The implementation is valid and secure."
        v = self.agent._infer_verdict(text)
        assert v.verdict == "PASS"

    def test_infer_verdict_mixed(self):
        text = "The core logic is correct and the output is good, but there's a minor missing edge case."
        v = self.agent._infer_verdict(text)
        assert v.verdict == "PARTIAL"
