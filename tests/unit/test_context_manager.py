"""Tests for core/context_manager.py — scene classification, compression, artifacts."""
import os
import tempfile
import pytest

from core.context_manager import (
    classify_output, compute_target_tokens, OutputScene,
    ContextManager, ArtifactRegistry,
    CHARS_PER_TOKEN, MICROCOMPACT_THRESHOLD,
)
from core.state_manager import StateManager


# ==================== classify_output ====================

class TestClassifyOutput:
    def test_error_output(self):
        text = """Traceback (most recent call last):
  File "app.py", line 42, in main
    result = process(data)
TypeError: expected str, got NoneType

The above exception was the direct cause of the following error:
RuntimeError: processing failed
"""
        assert classify_output(text) == OutputScene.ERROR

    def test_code_output(self):
        text = """import os
from typing import List

class DataProcessor:
    def __init__(self):
        self.data = []

    def process(self, items: List[str]) -> dict:
        return {item: len(item) for item in items}
"""
        assert classify_output(text) == OutputScene.CODE

    def test_log_output(self):
        text = """[2026-04-06 10:23:01] INFO Starting server on port 8080
[2026-04-06 10:23:02] DEBUG Loading configuration
[2026-04-06 10:23:03] INFO Server ready
[2026-04-06 10:23:04] WARN High memory usage detected
"""
        assert classify_output(text) == OutputScene.LOG

    def test_data_output(self):
        text = """Results Summary:
Total records: 1500
Average score: 82.3
Mean response time: 245ms
Columns: id, name, score, timestamp
Rows processed: 1500 of 1500
"""
        assert classify_output(text) == OutputScene.DATA

    def test_general_output(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert classify_output(text) == OutputScene.GENERAL

    def test_error_takes_priority(self):
        """Error detection should win even if code signals exist."""
        text = """def process():
    raise ValueError("invalid input")
Traceback (most recent call last):
  File "test.py", line 1
ValueError: invalid input
"""
        assert classify_output(text) == OutputScene.ERROR


# ==================== compute_target_tokens ====================

class TestComputeTargetTokens:
    def test_code_ratio(self):
        text = "x" * 30000  # 10000 tokens
        target = compute_target_tokens(text, OutputScene.CODE)
        # ratio 0.4 * 10000 = 4000, but max is 2000
        assert target == 2000

    def test_error_preserves_more(self):
        text = "x" * 9000  # 3000 tokens
        target = compute_target_tokens(text, OutputScene.ERROR)
        # ratio 0.6 * 3000 = 1800
        assert target == 1800

    def test_log_compresses_aggressively(self):
        text = "x" * 9000  # 3000 tokens
        target = compute_target_tokens(text, OutputScene.LOG)
        # ratio 0.2 * 3000 = 600
        assert target == 600

    def test_minimum_enforcement(self):
        text = "x" * 300  # 100 tokens
        target = compute_target_tokens(text, OutputScene.ERROR)
        # ratio 0.6 * 100 = 60, but min is 500
        assert target == OutputScene.MIN_TOKENS[OutputScene.ERROR]

    def test_maximum_enforcement(self):
        text = "x" * 300000  # 100000 tokens
        target = compute_target_tokens(text, OutputScene.GENERAL)
        assert target == OutputScene.MAX_TOKENS[OutputScene.GENERAL]

    def test_budget_override(self):
        text = "x" * 30000  # 10000 tokens
        target = compute_target_tokens(text, OutputScene.CODE, budget_override=500)
        # budget_override=500 caps max_t to 500, ratio*tokens=4000 > 500
        assert target == 500


# ==================== ArtifactRegistry ====================

class TestArtifactRegistry:
    def test_register_and_get(self):
        reg = ArtifactRegistry()
        reg.register("config.yaml", "file", "/tmp/config.yaml", "App config", "task-1")
        a = reg.get("config.yaml")
        assert a is not None
        assert a["type"] == "file"
        assert a["producer"] == "task-1"

    def test_get_missing(self):
        reg = ArtifactRegistry()
        assert reg.get("nonexistent") is None

    def test_find_by_producer(self):
        reg = ArtifactRegistry()
        reg.register("a.py", "file", "/a.py", "Script A", "task-1")
        reg.register("b.py", "file", "/b.py", "Script B", "task-1")
        reg.register("c.py", "file", "/c.py", "Script C", "task-2")
        found = reg.find_by_producer("task-1")
        assert len(found) == 2

    def test_to_context_block_empty(self):
        reg = ArtifactRegistry()
        assert reg.to_context_block() == ""

    def test_to_context_block_non_empty(self):
        reg = ArtifactRegistry()
        reg.register("output.json", "file", "/tmp/output.json", "Results", "t1")
        block = reg.to_context_block()
        assert "Available Artifacts" in block
        assert "output.json" in block


# ==================== ContextManager.microcompact ====================

class TestMicrocompact:
    def setup_method(self):
        state = StateManager(enable_persistence=False)
        self.cm = ContextManager(state, agent_pool=None, storage_dir=tempfile.mkdtemp())

    def test_short_text_unchanged(self):
        text = "Hello world"
        assert self.cm.microcompact(text) == text

    def test_removes_consecutive_empty_lines(self):
        text = "line1\n\n\n\n\nline2"
        # Need to be above threshold
        text = text + "\n" + "x" * MICROCOMPACT_THRESHOLD
        result = self.cm.microcompact(text)
        # Should not have more than one consecutive empty line
        assert "\n\n\n" not in result

    def test_removes_progress_bars(self):
        lines = [f"{i}% complete" for i in range(0, 100, 5)]
        text = "\n".join(lines) + "\n" + "x" * MICROCOMPACT_THRESHOLD
        result = self.cm.microcompact(text)
        assert len(result) < len(text)

    def test_deduplicates_repeated_lines(self):
        text = "\n".join(["Installing package xyz..."] * 10) + "\n" + "x" * MICROCOMPACT_THRESHOLD
        result = self.cm.microcompact(text)
        # Only 2 copies should remain (threshold is > 2)
        assert result.count("Installing package xyz...") <= 2

    def test_compresses_repetitive_blocks(self):
        lines = [f"Installing package-{i}..." for i in range(20)]
        text = "\n".join(lines) + "\n" + "x" * MICROCOMPACT_THRESHOLD
        result = self.cm.microcompact(text)
        assert "similar lines" in result


# ==================== ContextManager storage ====================

class TestContextManagerStorage:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        state = StateManager(enable_persistence=False)
        self.cm = ContextManager(state, agent_pool=None, storage_dir=self.tmpdir)

    def test_store_and_load_raw_output(self):
        self.cm.store_raw_output("task-1", "raw content here")
        loaded = self.cm.load_raw_output("task-1")
        assert loaded == "raw content here"

    def test_load_missing_output(self):
        assert self.cm.load_raw_output("nonexistent") is None

    def test_knowledge_base(self):
        self.cm.record_knowledge("api_version", "v2.1")
        assert self.cm._knowledge_base["api_version"] == "v2.1"

    def test_failed_approaches(self):
        self.cm.record_failed_approach("s1", "Tried direct query but timed out")
        self.cm.record_failed_approach("s1", "Used batch but exceeded memory")
        assert len(self.cm._failed_approaches["s1"]) == 2

    def test_extract_artifacts(self):
        output = """Created /tmp/output.json with results.
Wrote /tmp/report.md with the summary.
Generated /tmp/chart.png for visualization."""
        self.cm.extract_artifacts_from_output("task-1", output)
        assert self.cm.artifacts.get("output.json") is not None
        assert self.cm.artifacts.get("report.md") is not None
        assert self.cm.artifacts.get("chart.png") is not None
