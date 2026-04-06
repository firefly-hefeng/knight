"""Tests for core/agent_registry.py — dynamic agent registration, health, cost tracking."""
import asyncio
import pytest

from core.agent_registry import (
    AgentRegistry, AgentDefinition, AgentHealth,
    parse_raw, parse_stream_json, parse_json_output,
)


# ==================== Output Parsers ====================

class TestOutputParsers:
    def test_parse_raw_success(self):
        r = parse_raw("hello world", "", 0)
        assert r.success is True
        assert r.output == "hello world"

    def test_parse_raw_failure(self):
        r = parse_raw("", "error msg", 1)
        assert r.success is False
        assert r.error == "error msg"

    def test_parse_stream_json(self):
        stdout = (
            '{"role":"assistant","content":[{"type":"text","text":"Hello"}]}\n'
            '{"role":"assistant","content":[{"type":"text","text":" World"}]}\n'
        )
        r = parse_stream_json(stdout, "", 0)
        assert r.success is True
        assert "Hello" in r.output
        assert "World" in r.output

    def test_parse_stream_json_invalid_lines(self):
        stdout = "not json\n{bad"
        r = parse_stream_json(stdout, "", 0)
        assert r.success is True
        assert "not json" in r.output

    def test_parse_json_output(self):
        stdout = '{"success": true, "output": "result data", "cost_usd": 0.05}'
        r = parse_json_output(stdout, "", 0)
        assert r.success is True
        assert r.output == "result data"
        assert r.cost_usd == 0.05

    def test_parse_json_output_invalid(self):
        r = parse_json_output("not json", "err", 1)
        assert r.success is False  # falls back to parse_raw


# ==================== AgentDefinition ====================

class TestAgentDefinition:
    def test_defaults(self):
        d = AgentDefinition(name="test", command="test-cmd")
        assert d.concurrency == 2
        assert d.output_format == "raw"
        assert d.enabled is True
        assert d.health_command == "test-cmd --version"

    def test_custom_health_command(self):
        d = AgentDefinition(name="x", command="x", health_command="x --check")
        assert d.health_command == "x --check"


# ==================== AgentRegistry ====================

class TestAgentRegistry:
    def test_builtins_registered(self):
        reg = AgentRegistry()
        assert reg.get("claude") is not None
        assert reg.get("kimi") is not None
        assert len(reg.list_agents()) >= 2

    def test_register_custom(self):
        reg = AgentRegistry()
        reg.register(AgentDefinition(
            name="codex",
            command="codex",
            capabilities=["coding", "review"],
            concurrency=1,
        ))
        assert reg.get("codex") is not None
        assert "codex" in [a.name for a in reg.list_agents()]

    def test_unregister(self):
        reg = AgentRegistry()
        reg.register(AgentDefinition(name="temp", command="temp"))
        assert reg.unregister("temp") is True
        assert reg.get("temp") is None
        assert reg.unregister("temp") is False

    def test_register_from_config(self):
        reg = AgentRegistry()
        configs = [
            {"name": "agent_a", "command": "a-cmd", "capabilities": ["fast"]},
            {"name": "agent_b", "command": "b-cmd", "capabilities": ["slow"]},
        ]
        reg.register_from_config(configs)
        assert reg.get("agent_a") is not None
        assert reg.get("agent_b") is not None

    def test_list_healthy(self):
        reg = AgentRegistry()
        healthy = reg.list_healthy()
        assert "claude" in healthy
        assert "kimi" in healthy

        # Mark one unhealthy
        reg._health["claude"].healthy = False
        healthy = reg.list_healthy()
        assert "claude" not in healthy
        assert "kimi" in healthy

    def test_find_by_capability(self):
        reg = AgentRegistry()
        coders = reg.find_by_capability("coding")
        assert "claude" in coders

        searchers = reg.find_by_capability("search")
        assert "kimi" in searchers

    def test_capabilities_map(self):
        reg = AgentRegistry()
        cap_map = reg.get_capabilities_map()
        assert "coding" in cap_map
        assert "claude" in cap_map["coding"]

    def test_disabled_agent_excluded(self):
        reg = AgentRegistry()
        reg.register(AgentDefinition(name="off", command="off", enabled=False))
        assert "off" not in reg.list_healthy()
        assert "off" not in reg.find_by_capability("coding")

    def test_get_stats(self):
        reg = AgentRegistry()
        stats = reg.get_stats()
        assert "agents" in stats
        assert "total_cost_usd" in stats
        assert "healthy_count" in stats
        assert stats["healthy_count"] >= 2

    def test_cost_tracking(self):
        reg = AgentRegistry()
        reg._health["claude"].total_cost_usd = 1.5
        reg._health["kimi"].total_cost_usd = 0.0
        assert reg.get_total_cost() == 1.5
        breakdown = reg.get_cost_breakdown()
        assert breakdown["claude"] == 1.5
        assert breakdown["kimi"] == 0.0

    def test_health_tracking(self):
        reg = AgentRegistry()
        h = reg.get_health("claude")
        assert h is not None
        assert h.healthy is True
        assert h.total_calls == 0

        # Simulate calls
        h.total_calls = 10
        h.total_failures = 2
        h.total_cost_usd = 0.5

        stats = reg.get_stats()
        assert stats["agents"]["claude"]["total_calls"] == 10
        assert stats["agents"]["claude"]["success_rate"] == "80.0%"

    @pytest.mark.asyncio
    async def test_execute_unknown_agent(self):
        reg = AgentRegistry()
        result = await reg.execute("nonexistent", "test", "/tmp")
        assert result.success is False
        assert "Unknown agent" in result.error

    @pytest.mark.asyncio
    async def test_execute_disabled_agent(self):
        reg = AgentRegistry()
        reg.register(AgentDefinition(name="disabled", command="echo", enabled=False))
        result = await reg.execute("disabled", "test", "/tmp")
        assert result.success is False
        assert "disabled" in result.error.lower()
