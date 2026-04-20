"""Tests for RalphOrchestrator"""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Create stub modules that orchestrator.py imports but don't exist
agent_registry_mod = types.ModuleType("core.agent_registry")
agent_registry_mod.AgentRegistry = MagicMock
agent_registry_mod.Agent = MagicMock
sys.modules["core.agent_registry"] = agent_registry_mod

version_control_mod = types.ModuleType("plugins")
sys.modules["plugins"] = types.ModuleType("plugins")
version_control_sub = types.ModuleType("plugins.version_control")
version_control_sub.VersionControl = MagicMock
sys.modules["plugins.version_control"] = version_control_sub

from core.orchestrator import RalphOrchestrator, IterationResult, SessionStats


class TestIterationResult:
    def test_defaults(self):
        r = IterationResult(story_id="s1", story_title="t", success=True, duration=1.0)
        assert r.commit_hash is None
        assert r.error_message is None
        assert r.artifacts == []

    def test_with_values(self):
        r = IterationResult(
            story_id="s1", story_title="t", success=False, duration=2.5,
            error_message="boom", commit_hash="abc123", artifacts=["f.py"]
        )
        assert r.error_message == "boom"
        assert r.commit_hash == "abc123"
        assert r.artifacts == ["f.py"]


class TestSessionStats:
    def test_defaults(self):
        s = SessionStats(total_iterations=0, successful_iterations=0,
                         failed_iterations=0, total_duration=0.0, average_iteration_time=0.0)
        assert s.stories_completed == []
        assert s.commits_made == []


class TestRalphOrchestratorInit:
    def test_default_init(self):
        orch = RalphOrchestrator.__new__(RalphOrchestrator)
        # Can't fully init due to missing modules, but test dataclass fields
        stats = SessionStats(total_iterations=0, successful_iterations=0,
                             failed_iterations=0, total_duration=0.0, average_iteration_time=0.0)
        assert stats.total_iterations == 0

    def test_session_stats_initial_values(self):
        stats = SessionStats(
            total_iterations=5, successful_iterations=3,
            failed_iterations=2, total_duration=10.0, average_iteration_time=2.0
        )
        assert stats.total_iterations == 5
        assert stats.successful_iterations == 3


class TestGetSessionSummary:
    def test_no_iterations(self):
        """get_session_summary returns no_iterations when nothing has run"""
        # Build a minimal orchestrator-like object
        orch = RalphOrchestrator.__new__(RalphOrchestrator)
        orch.session_stats = SessionStats(
            total_iterations=0, successful_iterations=0,
            failed_iterations=0, total_duration=0.0, average_iteration_time=0.0
        )
        orch.current_session_id = None
        orch.prd_manager = MagicMock()
        result = orch.get_session_summary()
        assert result["status"] == "no_iterations"

    def test_with_iterations(self):
        orch = RalphOrchestrator.__new__(RalphOrchestrator)
        orch.session_stats = SessionStats(
            total_iterations=4, successful_iterations=3,
            failed_iterations=1, total_duration=12.0, average_iteration_time=3.0,
            stories_completed=["s1", "s2", "s3"],
            commits_made=["c1", "c2", "c3"]
        )
        orch.current_session_id = "session-123"
        orch.prd_manager = MagicMock()
        orch.prd_manager.get_all_stories.return_value = []
        
        result = orch.get_session_summary()
        assert result["session_id"] == "session-123"
        assert result["total_iterations"] == 4
        assert result["successful_iterations"] == 3
        assert result["success_rate"] == 0.75
        assert result["remaining_stories"] == 0


class TestExecuteIteration:
    def test_no_active_session_raises(self):
        orch = RalphOrchestrator.__new__(RalphOrchestrator)
        orch.current_session_id = None
        with pytest.raises(ValueError, match="No active session"):
            orch.execute_iteration()


class TestEndSession:
    def test_end_resets_state(self):
        orch = RalphOrchestrator.__new__(RalphOrchestrator)
        orch.current_session_id = "session-456"
        orch.iteration_count = 5
        orch.session_stats = SessionStats(
            total_iterations=0, successful_iterations=0,
            failed_iterations=0, total_duration=0.0, average_iteration_time=0.0
        )
        orch.prd_manager = MagicMock()
        orch.memory_manager = MagicMock()
        orch.logger = MagicMock()
        
        orch.end_session()
        assert orch.current_session_id is None
        assert orch.iteration_count == 0


class TestIsComplete:
    def test_all_passes(self):
        orch = RalphOrchestrator.__new__(RalphOrchestrator)
        orch.prd_manager = MagicMock()
        story1 = MagicMock(); story1.passes = True
        story2 = MagicMock(); story2.passes = True
        orch.prd_manager.get_all_stories.return_value = [story1, story2]
        assert orch.is_complete() is True

    def test_incomplete(self):
        orch = RalphOrchestrator.__new__(RalphOrchestrator)
        orch.prd_manager = MagicMock()
        story1 = MagicMock(); story1.passes = True
        story2 = MagicMock(); story2.passes = False
        orch.prd_manager.get_all_stories.return_value = [story1, story2]
        assert orch.is_complete() is False
