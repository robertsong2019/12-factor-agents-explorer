"""
Tests for utils/logger.py — Logger utility class.

Covers:
- Logger creation and caching (singleton-per-name)
- Logger level configuration
- Handler attachment and formatter
- Multiple loggers coexistence
- Repeated get_logger returns same instance
"""

import logging
import sys

from utils.logger import Logger


class TestLoggerCreation:
    def test_get_logger_returns_logger_instance(self):
        logger = Logger.get_logger("test_basic")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_sets_name(self):
        logger = Logger.get_logger("test_named")
        assert logger.name == "test_named"

    def test_get_logger_sets_level_info(self):
        logger = Logger.get_logger("test_level")
        assert logger.level == logging.INFO


class TestLoggerCaching:
    def test_same_name_returns_same_instance(self):
        l1 = Logger.get_logger("test_cache_same")
        l2 = Logger.get_logger("test_cache_same")
        assert l1 is l2

    def test_different_names_return_different_instances(self):
        l1 = Logger.get_logger("test_cache_a")
        l2 = Logger.get_logger("test_cache_b")
        assert l1 is not l2
        assert l1.name != l2.name

    def test_logger_cached_in_class_dict(self):
        name = "test_class_dict"
        logger = Logger.get_logger(name)
        assert name in Logger._loggers
        assert Logger._loggers[name] is logger


class TestHandlerConfiguration:
    def test_logger_has_console_handler(self):
        logger = Logger.get_logger("test_handler")
        handlers = logger.handlers
        assert len(handlers) >= 1
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    def test_handler_level_is_info(self):
        logger = Logger.get_logger("test_handler_level")
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1
        assert stream_handlers[0].level == logging.INFO

    def test_handler_has_formatter(self):
        logger = Logger.get_logger("test_formatter")
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1
        fmt = stream_handlers[0].formatter
        assert fmt is not None
        # Format should include key fields
        format_str = fmt._fmt
        assert "%(name)s" in format_str
        assert "%(levelname)s" in format_str
        assert "%(message)s" in format_str

    def test_handler_writes_to_stdout(self):
        logger = Logger.get_logger("test_stdout")
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1
        # StreamHandler defaults to sys.stderr, but our logger sets sys.stdout
        assert stream_handlers[0].stream is sys.stdout


class TestMultipleLoggers:
    def test_multiple_loggers_independent(self):
        names = [f"test_multi_{i}" for i in range(5)]
        loggers = [Logger.get_logger(n) for n in names]
        assert len(set(id(l) for l in loggers)) == 5

    def test_multiple_loggers_all_functional(self):
        l1 = Logger.get_logger("test_func_1")
        l2 = Logger.get_logger("test_func_2")
        # Both should be able to log without errors
        l1.info("message from l1")
        l2.info("message from l2")
        assert l1.level == logging.INFO
        assert l2.level == logging.INFO


class TestLoggerBehavior:
    def test_logger_can_log_messages(self, capsys):
        logger = Logger.get_logger("test_log_msg")
        logger.info("test info message")
        captured = capsys.readouterr()
        assert "test info message" in captured.out

    def test_logger_includes_name_in_output(self, capsys):
        logger = Logger.get_logger("test_log_name_field")
        logger.info("hello")
        captured = capsys.readouterr()
        assert "test_log_name_field" in captured.out

    def test_logger_includes_level_in_output(self, capsys):
        logger = Logger.get_logger("test_log_level_field")
        logger.warning("warning msg")
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
