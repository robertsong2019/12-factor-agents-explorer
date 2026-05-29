"""Tests for Config and Logger utilities."""
import logging
import tempfile
from pathlib import Path

from utils.config import Config
from utils.logger import Logger


class TestConfig:
    def test_default_empty(self):
        c = Config()
        assert c.config == {}

    def test_get_existing_key(self):
        c = Config({"a": 1})
        assert c.get("a") == 1

    def test_get_missing_key_returns_default(self):
        c = Config()
        assert c.get("missing", "fallback") == "fallback"

    def test_set_and_get(self):
        c = Config()
        c.set("key", "val")
        assert c.get("key") == "val"

    def test_set_overwrite(self):
        c = Config({"x": 1})
        c.set("x", 2)
        assert c.get("x") == 2

    def test_load_from_file_returns_config(self):
        c = Config.load_from_file(Path("/nonexistent"))
        assert isinstance(c, Config)

    def test_config_with_nested_dict(self):
        c = Config({"db": {"host": "localhost", "port": 5432}})
        assert c.get("db")["host"] == "localhost"


class TestLogger:
    def test_get_logger_returns_logger(self):
        log = Logger.get_logger("test_basic")
        assert isinstance(log, logging.Logger)

    def test_get_logger_same_name_returns_same(self):
        a = Logger.get_logger("test_same")
        b = Logger.get_logger("test_same")
        assert a is b

    def test_logger_level_is_info(self):
        log = Logger.get_logger("test_level")
        assert log.level == logging.INFO

    def test_logger_has_handler(self):
        log = Logger.get_logger("test_handler")
        assert len(log.handlers) >= 1

    def test_different_names_different_loggers(self):
        a = Logger.get_logger("test_diff_a")
        b = Logger.get_logger("test_diff_b")
        assert a is not b
