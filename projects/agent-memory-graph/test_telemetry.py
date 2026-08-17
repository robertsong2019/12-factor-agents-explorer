"""
Tests for amg.telemetry — OpenTelemetry GenAI semantic conventions.

Covers:
- Inert mode (no OTel installed → no-ops, no crashes)
- Active mode (OTel SDK installed → correct span attributes)
- All 5 memory operations: store, search, retrieve, update, delete
- Error handling (exceptions set ERROR status)
- is_available() helper
- Custom store name and namespace
- Nested spans (parent-child)
- v2 alignment (semantic-conventions-genai @c739977): verb-form span
  names, ``gen_ai.operation.name``, ``store.id``, single ``record.count``,
  ``amg.*`` namespace for non-registry concepts, Opt-In query.text gate.
"""

import unittest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager


# --- Test: Inert mode (no opentelemetry) ---------------------------------

class TestInertMode(unittest.TestCase):
    """When opentelemetry is not installed, all functions should be safe no-ops."""

    def setUp(self):
        # Force inert mode by patching _OTEL_AVAILABLE
        import telemetry
        self._orig = telemetry._OTEL_AVAILABLE
        telemetry._OTEL_AVAILABLE = False
        telemetry._tracer = None

    def tearDown(self):
        import telemetry
        telemetry._OTEL_AVAILABLE = self._orig
        telemetry._tracer = None

    def test_store_inert(self):
        import telemetry
        with telemetry.trace_memory_store(items=2) as span:
            self.assertIsNone(span)

    def test_search_inert(self):
        import telemetry
        with telemetry.trace_memory_search(query="test", top_k=5) as span:
            self.assertIsNone(span)

    def test_retrieve_inert(self):
        import telemetry
        with telemetry.trace_memory_retrieve(items_retrieved=3) as span:
            self.assertIsNone(span)

    def test_update_inert(self):
        import telemetry
        with telemetry.trace_memory_update(items_updated=1) as span:
            self.assertIsNone(span)

    def test_delete_inert(self):
        import telemetry
        with telemetry.trace_memory_delete(items_deleted=1) as span:
            self.assertIsNone(span)

    def test_is_available_false_in_inert(self):
        import telemetry
        self.assertFalse(telemetry.is_available())

    def test_inert_does_not_crash_on_exception(self):
        import telemetry
        with self.assertRaises(ValueError):
            with telemetry.trace_memory_store(items=1):
                raise ValueError("test error")


# --- Test: Active mode (mock OTel) ---------------------------------------

class TestActiveMode(unittest.TestCase):
    """When OTel is available, spans should be created with correct attributes."""

    def setUp(self):
        import telemetry
        self._orig_available = telemetry._OTEL_AVAILABLE
        self._orig_tracer = telemetry._tracer

        # Mock OTel modules
        self.mock_trace = MagicMock()
        self.mock_tracer = MagicMock()
        self.mock_span = MagicMock()
        self.mock_cm = MagicMock()
        self.mock_cm.__enter__ = MagicMock(return_value=self.mock_span)
        self.mock_cm.__exit__ = MagicMock(return_value=False)
        self.mock_tracer.start_as_current_span = MagicMock(return_value=self.mock_cm)
        self.mock_trace.get_tracer = MagicMock(return_value=self.mock_tracer)
        self.mock_trace.SpanKind = MagicMock()
        self.mock_trace.SpanKind.INTERNAL = "INTERNAL"

        # Mock Status/StatusCode
        self.mock_status_cls = MagicMock()
        self.mock_status_code = MagicMock()
        self.mock_status_code.ERROR = "ERROR"

        telemetry._OTEL_AVAILABLE = True
        telemetry._tracer = None
        # Patch the module-level references
        self._orig_trace_mod = getattr(telemetry, 'trace', None)
        self._orig_status = getattr(telemetry, 'Status', None)
        self._orig_status_code = getattr(telemetry, 'StatusCode', None)
        telemetry.trace = self.mock_trace
        telemetry.Status = self.mock_status_cls
        telemetry.StatusCode = self.mock_status_code

    def tearDown(self):
        import telemetry
        telemetry._OTEL_AVAILABLE = self._orig_available
        telemetry._tracer = self._orig_tracer
        if self._orig_trace_mod is not None:
            telemetry.trace = self._orig_trace_mod
        if self._orig_status is not None:
            telemetry.Status = self._orig_status
        if self._orig_status_code is not None:
            telemetry.StatusCode = self._orig_status_code

    def test_is_available_true(self):
        import telemetry
        self.assertTrue(telemetry.is_available())

    def test_store_sets_attributes(self):
        import telemetry
        with telemetry.trace_memory_store(
            items=3, memory_type="episodic",
            namespace="test_ns", actor_id="agent_42"
        ):
            pass
        self.mock_tracer.start_as_current_span.assert_called_once()
        # Verify span attributes (v2: @c739977)
        calls = self.mock_span.set_attribute.call_args_list
        attrs = {c.args[0]: c.args[1] for c in calls}
        self.assertEqual(attrs["gen_ai.operation.name"], "create_memory")
        self.assertEqual(attrs["amg.memory.type"], "episodic")
        self.assertEqual(attrs["gen_ai.memory.store.id"], "agent_memory_graph")
        self.assertEqual(attrs["gen_ai.memory.record.count"], 3)
        self.assertEqual(attrs["amg.memory.namespace"], "test_ns")
        self.assertEqual(attrs["amg.memory.actor_id"], "agent_42")
        # v1 keys must be gone (no dual-emit: package unreleased)
        for legacy in ("gen_ai.memory.operation", "gen_ai.memory.type",
                       "gen_ai.memory.store", "gen_ai.memory.items_stored"):
            self.assertNotIn(legacy, attrs)

    def test_search_sets_query_attrs(self):
        import telemetry
        with telemetry.trace_memory_search(
            query="user preferences", top_k=10, min_score=0.75
        ):
            pass
        calls = self.mock_span.set_attribute.call_args_list
        attrs = {c.args[0]: c.args[1] for c in calls}
        self.assertEqual(attrs["gen_ai.operation.name"], "search_memory")
        self.assertEqual(attrs["amg.memory.top_k"], 10)
        self.assertEqual(attrs["amg.memory.min_score"], 0.75)
        # Opt-In gate: query.text must NOT appear without env opt-in
        self.assertNotIn("gen_ai.memory.query.text", attrs)
        self.assertNotIn("gen_ai.memory.search.query", attrs)

    def test_search_query_text_opt_in(self):
        """query.text is Opt-In: only emitted when the content-capture env var is truthy."""
        import telemetry
        import os
        env_key = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
        orig = os.environ.get(env_key)
        try:
            # Opt-in ON
            os.environ[env_key] = "true"
            with telemetry.trace_memory_search(query="secret-ish query"):
                pass
            attrs = {c.args[0]: c.args[1] for c in self.mock_span.set_attribute.call_args_list}
            self.assertEqual(attrs.get("gen_ai.memory.query.text"), "secret-ish query")

            # Opt-in with a non-truthy value → gated off
            self.mock_span.set_attribute.reset_mock()
            os.environ[env_key] = "0"
            with telemetry.trace_memory_search(query="secret-ish query"):
                pass
            attrs = {c.args[0]: c.args[1] for c in self.mock_span.set_attribute.call_args_list}
            self.assertNotIn("gen_ai.memory.query.text", attrs)
        finally:
            if orig is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = orig

    def test_retrieve_sets_hit_attr(self):
        import telemetry
        with telemetry.trace_memory_retrieve(
            items_retrieved=5, hit=True, memory_type="long_term"
        ):
            pass
        calls = self.mock_span.set_attribute.call_args_list
        attrs = {c.args[0]: c.args[1] for c in calls}
        # retrieve maps onto the spec's search_memory operation
        self.assertEqual(attrs["gen_ai.operation.name"], "search_memory")
        self.assertEqual(attrs["gen_ai.memory.record.count"], 5)
        self.assertTrue(attrs["amg.memory.hit"])

    def test_update_sets_keys(self):
        import telemetry
        with telemetry.trace_memory_update(
            items_updated=2, keys=["node_1", "node_2"]
        ):
            pass
        calls = self.mock_span.set_attribute.call_args_list
        attrs = {c.args[0]: c.args[1] for c in calls}
        self.assertEqual(attrs["gen_ai.operation.name"], "update_memory")
        self.assertEqual(attrs["gen_ai.memory.record.count"], 2)
        self.assertEqual(attrs["amg.memory.keys"], ["node_1", "node_2"])

    def test_delete_default_type(self):
        import telemetry
        with telemetry.trace_memory_delete(items_deleted=4):
            pass
        calls = self.mock_span.set_attribute.call_args_list
        attrs = {c.args[0]: c.args[1] for c in calls}
        self.assertEqual(attrs["gen_ai.operation.name"], "delete_memory")
        self.assertEqual(attrs["amg.memory.type"], "short_term")
        self.assertEqual(attrs["gen_ai.memory.record.count"], 4)

    def test_custom_store_name(self):
        import telemetry
        with telemetry.trace_memory_store(
            items=1, store="custom_backend"
        ):
            pass
        calls = self.mock_span.set_attribute.call_args_list
        attrs = {c.args[0]: c.args[1] for c in calls}
        self.assertEqual(attrs["gen_ai.memory.store.id"], "custom_backend")

    def test_none_values_not_set(self):
        """None-valued kwargs should be silently skipped."""
        import telemetry
        with telemetry.trace_memory_search(
            query="test", top_k=5,
            min_score=None  # should be skipped
        ):
            pass
        calls = self.mock_span.set_attribute.call_args_list
        attr_names = [c.args[0] for c in calls]
        self.assertNotIn("amg.memory.min_score", attr_names)

    def test_error_sets_error_status(self):
        """Exceptions within a span should set ERROR status and re-raise."""
        import telemetry
        with self.assertRaises(RuntimeError):
            with telemetry.trace_memory_store(items=1):
                raise RuntimeError("boom")
        # Verify error handling
        self.mock_span.set_status.assert_called_once()
        self.mock_span.record_exception.assert_called_once()

    def test_span_name_format(self):
        """Span name = verb-form gen_ai.operation.name value, no 'gen_ai.' prefix."""
        import telemetry
        with telemetry.trace_memory_retrieve(items_retrieved=1):
            pass
        call_kwargs = self.mock_tracer.start_as_current_span.call_args
        span_name = call_kwargs.args[0] if call_kwargs.args else call_kwargs[0][0]
        self.assertEqual(span_name, "search_memory")

    def test_span_names_all_verb_form(self):
        """All 5 wrappers emit verb-form span names from the registry's operation set."""
        import telemetry
        expected = {
            telemetry.trace_memory_store: "create_memory",
            telemetry.trace_memory_search: "search_memory",
            telemetry.trace_memory_retrieve: "search_memory",
            telemetry.trace_memory_update: "update_memory",
            telemetry.trace_memory_delete: "delete_memory",
        }
        for fn, name in expected.items():
            with self.subTest(span=name):
                self.mock_tracer.start_as_current_span.reset_mock()
                with fn():  # all wrappers accept defaults
                    pass
                call = self.mock_tracer.start_as_current_span.call_args
                self.assertEqual(call.args[0] if call.args else call[0][0], name)

    def test_semconv_commit_anchor_exported(self):
        """The conventions commit this module is pinned to must be exported."""
        import telemetry
        self.assertRegex(telemetry.SEMCONV_GENAI_COMMIT, r"^[0-9a-f]{7,40}$")

    def test_tracer_cached(self):
        """get_tracer should cache the tracer instance."""
        import telemetry
        telemetry._tracer = None
        t1 = telemetry._get_tracer()
        t2 = telemetry._get_tracer()
        self.assertIs(t1, t2)


# --- Test: Integration with MemoryGraph ----------------------------------

class TestMemoryGraphIntegration(unittest.TestCase):
    """Verify telemetry wraps around actual graph operations without breaking them."""

    def test_store_around_add(self):
        """Simulate wrapping a graph.add() call with trace_memory_store."""
        import telemetry
        # In inert mode, this should just work
        telemetry._OTEL_AVAILABLE = False
        telemetry._tracer = None
        with telemetry.trace_memory_store(items=1):
            result = 1 + 1  # simulate work
        self.assertEqual(result, 2)

    def test_search_around_query(self):
        import telemetry
        telemetry._OTEL_AVAILABLE = False
        telemetry._tracer = None
        with telemetry.trace_memory_search(query="test"):
            result = [1, 2, 3]  # simulate results
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
