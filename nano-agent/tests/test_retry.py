"""Tests for Agent.run_with_retry()."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import patch, MagicMock
from nano_agent.agent import Agent
from nano_agent.tools import Tool


def _make_agent():
    """Create a minimal agent without LLM backend."""
    agent = Agent.__new__(Agent)
    agent.name = "test"
    agent.verbose = False
    agent.tools = []
    agent.memory = MagicMock()
    agent._conversation_history = []
    return agent


class TestRunWithRetry:
    def test_success_first_attempt(self):
        agent = _make_agent()
        agent.run = MagicMock(return_value="ok")
        result = agent.run_with_retry("hello", max_retries=3)
        assert result["success"] is True
        assert result["response"] == "ok"
        assert result["attempts"] == 1
        assert result["errors"] == []

    def test_success_after_retries(self):
        agent = _make_agent()
        agent.run = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])
        result = agent.run_with_retry("hello", max_retries=3, backoff=0.01)
        assert result["success"] is True
        assert result["response"] == "ok"
        assert result["attempts"] == 3
        assert len(result["errors"]) == 2

    def test_all_retries_fail(self):
        agent = _make_agent()
        agent.run = MagicMock(side_effect=ValueError("persistent"))
        result = agent.run_with_retry("hello", max_retries=3, backoff=0.01)
        assert result["success"] is False
        assert result["response"] is None
        assert result["attempts"] == 3
        assert len(result["errors"]) == 3

    def test_retryable_errors_filter(self):
        agent = _make_agent()
        agent.run = MagicMock(side_effect=ValueError("rate_limit_exceeded"))
        result = agent.run_with_retry("hello", max_retries=3, backoff=0.01,
                                      retryable_errors=["rate_limit"])
        # Should retry because "rate_limit" is in error
        assert result["attempts"] == 3

    def test_non_retryable_stops_immediately(self):
        agent = _make_agent()
        agent.run = MagicMock(side_effect=ValueError("auth_failed"))
        result = agent.run_with_retry("hello", max_retries=5, backoff=0.01,
                                      retryable_errors=["timeout", "rate_limit"])
        # "auth_failed" doesn't match any retryable keyword
        assert result["attempts"] == 1
        assert result["success"] is False

    def test_exponential_backoff(self):
        """Verify backoff times increase exponentially."""
        agent = _make_agent()
        agent.run = MagicMock(side_effect=ValueError("fail"))
        sleeps = []
        original_sleep = __import__('time').sleep
        def mock_sleep(t):
            sleeps.append(t)
        with patch('time.sleep', side_effect=mock_sleep):
            agent.run_with_retry("hello", max_retries=4, backoff=1.0)
        # Attempts: 1 (fail, sleep 1), 2 (fail, sleep 2), 3 (fail, sleep 4), 4 (fail, stop)
        assert sleeps == [1.0, 2.0, 4.0]

    def test_no_retries(self):
        agent = _make_agent()
        agent.run = MagicMock(side_effect=ValueError("fail"))
        result = agent.run_with_retry("hello", max_retries=1)
        assert result["attempts"] == 1
        assert result["success"] is False

    def test_retryable_none_means_all_retryable(self):
        agent = _make_agent()
        agent.run = MagicMock(side_effect=ValueError("any error"))
        result = agent.run_with_retry("hello", max_retries=2, backoff=0.01,
                                      retryable_errors=None)
        assert result["attempts"] == 2
