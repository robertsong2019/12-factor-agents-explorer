"""Tests for utility modules: Config, PerformanceMonitor, Logger"""
import time
import logging
from utils.config import Config
from utils.monitor import PerformanceMonitor
from utils.logger import Logger


class TestConfig:
    def test_default_empty(self):
        c = Config()
        assert c.get("missing") is None
        assert c.get("missing", 42) == 42

    def test_get_set(self):
        c = Config({"key": "val"})
        assert c.get("key") == "val"
        c.set("key2", 99)
        assert c.get("key2") == 99

    def test_load_from_file(self):
        c = Config.load_from_file(None)
        assert isinstance(c, Config)
        assert c.config == {}


class TestPerformanceMonitor:
    def test_start_end(self):
        m = PerformanceMonitor()
        m.start("op")
        time.sleep(0.01)
        d = m.end("op")
        assert d > 0
        assert m.get_metrics()["op"]["duration"] == d

    def test_end_nonexistent(self):
        m = PerformanceMonitor()
        assert m.end("nope") == 0.0

    def test_get_metrics_empty(self):
        m = PerformanceMonitor()
        assert m.get_metrics() == {}


class TestLogger:
    def test_get_logger(self):
        log = Logger.get_logger("test_unit")
        assert isinstance(log, logging.Logger)

    def test_same_logger_returned(self):
        log1 = Logger.get_logger("test_dup")
        log2 = Logger.get_logger("test_dup")
        assert log1 is log2
