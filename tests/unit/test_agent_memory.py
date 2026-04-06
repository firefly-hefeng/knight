"""Tests for core/agent_memory.py — persistent memory system."""
import os
import tempfile
import pytest

from core.agent_memory import AgentMemory, MemoryEntry
from core import agent_memory as agent_memory_mod


class TestAgentMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Use isolated user dir to avoid cross-test contamination
        self._orig_user_dir = agent_memory_mod.USER_MEMORY_DIR
        agent_memory_mod.USER_MEMORY_DIR = os.path.join(self.tmpdir, "user_memory")
        self.memory = AgentMemory(project_dir=self.tmpdir)

    def teardown_method(self):
        agent_memory_mod.USER_MEMORY_DIR = self._orig_user_dir

    def test_add_and_get(self):
        self.memory.add("Use pytest for testing", scope="project", tags=["testing"])
        entries = self.memory.get_all("project")
        assert len(entries) == 1
        assert entries[0].content == "Use pytest for testing"
        assert "testing" in entries[0].tags

    def test_add_deduplication(self):
        self.memory.add("Same content", scope="project")
        self.memory.add("Same content", scope="project")
        assert len(self.memory.get_all("project")) == 1

    def test_add_different_scopes(self):
        self.memory.add("Global rule", scope="user")
        self.memory.add("Project rule", scope="project")
        self.memory.add("Local rule", scope="local")
        assert len(self.memory.get_all()) == 3
        assert len(self.memory.get_all("user")) == 1
        assert len(self.memory.get_all("project")) == 1
        assert len(self.memory.get_all("local")) == 1

    def test_remove(self):
        self.memory.add("To remove", scope="project")
        assert self.memory.remove("To remove") is True
        assert len(self.memory.get_all("project")) == 0

    def test_remove_nonexistent(self):
        assert self.memory.remove("Ghost") is False

    def test_search_by_content(self):
        self.memory.add("Always use type hints", scope="project")
        self.memory.add("Prefer async IO", scope="project")
        results = self.memory.search("type hints")
        assert len(results) == 1
        assert "type hints" in results[0].content

    def test_search_by_tag(self):
        self.memory.add("Use black formatter", scope="project", tags=["formatting", "python"])
        self.memory.add("Use eslint", scope="project", tags=["formatting", "javascript"])
        results = self.memory.search("python")
        assert len(results) == 1

    def test_persistence(self):
        """Memory survives reload."""
        self.memory.add("Persistent fact", scope="project", tags=["test"])
        # Create new memory instance pointing to same dir
        memory2 = AgentMemory(project_dir=self.tmpdir)
        entries = memory2.get_all("project")
        assert len(entries) == 1
        assert entries[0].content == "Persistent fact"
        assert "test" in entries[0].tags

    def test_clear(self):
        self.memory.add("A", scope="project")
        self.memory.add("B", scope="project")
        count = self.memory.clear("project")
        assert count == 2
        assert len(self.memory.get_all("project")) == 0

    def test_build_context_empty(self):
        ctx = self.memory.build_context()
        assert ctx == ""

    def test_build_context_with_entries(self):
        self.memory.add("Rule 1: use pytest", scope="project")
        self.memory.add("Rule 2: no print()", scope="user")
        ctx = self.memory.build_context()
        assert "Rule 1" in ctx
        assert "Rule 2" in ctx
        assert "[project]" in ctx
        assert "[user]" in ctx

    def test_build_context_with_tags(self):
        self.memory.add("Use pytest", scope="project", tags=["testing"])
        self.memory.add("Use black", scope="project", tags=["formatting"])
        ctx = self.memory.build_context(tags=["testing"])
        assert "pytest" in ctx
        assert "black" not in ctx

    def test_build_context_for_task(self):
        self.memory.add("Always validate user input", scope="project", tags=["security"])
        self.memory.add("Use React hooks pattern", scope="project", tags=["frontend"])
        self.memory.add("Database uses PostgreSQL", scope="project", tags=["database"])

        ctx = self.memory.build_context_for_task("Fix the user input validation bug")
        assert "validate" in ctx.lower() or "input" in ctx.lower()

    def test_extract_from_output(self):
        output = """
        Implemented the feature.
        Remember: The API requires authentication headers.
        Note: Rate limit is 100 req/min.
        Done.
        """
        extracted = self.memory.extract_from_output(output, task_id="t1")
        assert len(extracted) == 2
        assert any("authentication" in e for e in extracted)
        assert any("Rate limit" in e for e in extracted)

    def test_extract_from_output_no_markers(self):
        output = "Just some regular output without any memory markers."
        extracted = self.memory.extract_from_output(output)
        assert len(extracted) == 0

    def test_get_stats(self):
        self.memory.add("A", scope="project")
        self.memory.add("B", scope="user")
        stats = self.memory.get_stats()
        assert stats["project"] == 1
        assert stats["user"] == 1
        assert stats["local"] == 0

    def test_memory_file_format(self):
        self.memory.add("Test entry", scope="project", tags=["tag1", "tag2"], source="task-1")
        path = self.memory._get_path("project")
        with open(path, 'r') as f:
            content = f.read()
        assert "Test entry" in content
        assert "tag1" in content
        assert "task-1" in content
