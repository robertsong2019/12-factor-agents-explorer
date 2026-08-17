"""
amg.telemetry — OpenTelemetry GenAI semantic conventions for agent-memory-graph.

Emits memory-operation spans aligned with the OTel GenAI semantic conventions
as of semantic-conventions-genai commit ``c739977`` (2026-07-30; the GenAI
conventions moved out of the main registry in v1.42.0 and live in
https://github.com/open-telemetry/semantic-conventions-genai — no tagged
release exists yet, so the commit hash is the only stable reference).

Conventions applied:

- Span name = ``{gen_ai.operation.name}`` verb form (``create_memory``,
  ``search_memory``, ``update_memory``, ``delete_memory``) — no ``gen_ai.``
  prefix in the span *name*.
- ``gen_ai.operation.name`` is Required on every span.
- ``gen_ai.memory.store.id`` identifies the memory store.
- ``gen_ai.memory.record.count`` is the single recommended counter (semantics
  per operation: create = attempted creates, search = returned records, ...).
- ``gen_ai.memory.query.text`` is Opt-In content: only emitted when the
  ``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`` environment variable
  is set to a truthy value (spec-mandated content gate).
- amg-specific concepts with no registry equivalent (memory_type, top_k,
  min_score, hit, namespace, actor_id, keys) live under the reserved ``amg.*``
  namespace — the spec forbids inventing new ``gen_ai.*`` keys.
- SpanKind INTERNAL is allowed for in-process memory systems (spec: "MAY
  INTERNAL").

Zero-dependency by default. ``pip install opentelemetry-api`` to enable.
Without the SDK, all context managers are inert no-ops.

Usage::

    from telemetry import trace_memory_store, trace_memory_search

    with trace_memory_store(items=1, memory_type="episodic"):
        graph.add("concept", {"data": 42})

    with trace_memory_search(query="user prefs", top_k=5):
        results = graph.multi_hop_reason("user", depth=2)
"""

from __future__ import annotations
import os
from typing import Any, Optional
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

# Conventions anchor — pin the semantic-conventions-genai commit this module
# is aligned with. Update both together when re-pinning.
SEMCONV_GENAI_COMMIT = "c739977"

# --- Tracer --------------------------------------------------------------

_tracer: Optional[Any] = None


def _get_tracer():
    """Return a cached tracer instance, creating one on first call."""
    global _tracer
    if _tracer is None and _OTEL_AVAILABLE:
        _tracer = trace.get_tracer("agent-memory-graph", "1.0.0")
    return _tracer


def is_available() -> bool:
    """Return True if OpenTelemetry is installed and active."""
    return _OTEL_AVAILABLE


# --- Helpers -------------------------------------------------------------

def _set_attrs(span: Any, attrs: dict[str, Any]) -> None:
    """Set non-None attributes on a span."""
    for k, v in attrs.items():
        if v is not None:
            span.set_attribute(k, v)


def _capture_content_enabled() -> bool:
    """Opt-In content gate (spec: OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT).

    Content-bearing attributes (``gen_ai.memory.query.text``) must NOT be
    emitted unless the operator explicitly opts in.
    """
    return os.environ.get("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "").lower() in (
        "1", "true", "yes", "on",
    )


# v1 → v2 operation mapping: legacy local verb → spec operation.name.
_OPERATION_NAMES: dict[str, str] = {
    "store": "create_memory",
    "search": "search_memory",
    "retrieve": "search_memory",
    "update": "update_memory",
    "delete": "delete_memory",
}


@contextmanager
def _memory_span(
    operation: str,
    memory_type: str = "long_term",
    store: str = "agent_memory_graph",
    record_count: Optional[int] = None,
    **extra: Any,
):
    """Context manager for a GenAI-convention memory span.

    Span name is the verb-form ``gen_ai.operation.name`` value (e.g.
    ``search_memory``). In inert mode (no OTel), yields None and does nothing.
    """
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return

    op_name = _OPERATION_NAMES.get(operation, operation)
    span_name = op_name
    kind = trace.SpanKind.INTERNAL if hasattr(trace, "SpanKind") else None
    with tracer.start_as_current_span(span_name, kind=kind) as span:
        span.set_attribute("gen_ai.operation.name", op_name)
        span.set_attribute("gen_ai.memory.store.id", store)
        if memory_type is not None:
            span.set_attribute("amg.memory.type", memory_type)
        if record_count is not None:
            span.set_attribute("gen_ai.memory.record.count", record_count)
        _set_attrs(span, extra)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# --- Public API ----------------------------------------------------------

def trace_memory_store(
    items: int = 1,
    memory_type: str = "episodic",
    store: str = "agent_memory_graph",
    namespace: Optional[str] = None,
    actor_id: Optional[str] = None,
):
    """Wrap ``MemoryGraph.add()`` / ``record()`` calls.

    Emits a ``create_memory`` span (record.count = attempted creates).
    """
    return _memory_span(
        "store",
        memory_type=memory_type,
        store=store,
        record_count=items,
        **{
            "amg.memory.namespace": namespace,
            "amg.memory.actor_id": actor_id,
        },
    )


def trace_memory_search(
    query: Optional[str] = None,
    top_k: int = 10,
    min_score: Optional[float] = None,
    memory_type: str = "semantic",
    store: str = "agent_memory_graph",
):
    """Wrap ``MemoryGraph.search()`` / ``multi_hop_reason()`` / ``spreading_activation()`` calls.

    Emits a ``search_memory`` span. ``gen_ai.memory.query.text`` is only
    emitted when content capture is opted in via the
    ``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`` env var.
    """
    query_attrs: dict[str, Any] = {}
    if query is not None and _capture_content_enabled():
        query_attrs["gen_ai.memory.query.text"] = query
    return _memory_span(
        "search",
        memory_type=memory_type,
        store=store,
        **query_attrs,
        **{
            "amg.memory.top_k": top_k,
            "amg.memory.min_score": min_score,
        },
    )


def trace_memory_retrieve(
    items_retrieved: Optional[int] = None,
    memory_type: str = "long_term",
    store: str = "agent_memory_graph",
    hit: Optional[bool] = None,
):
    """Wrap ``MemoryGraph.get()`` / ``neighbors()`` / PPR calls.

    Emits a ``search_memory`` span (direct record fetch is a search with a
    known target; record.count = returned records).
    """
    return _memory_span(
        "retrieve",
        memory_type=memory_type,
        store=store,
        record_count=items_retrieved,
        **{
            "amg.memory.hit": hit,
        },
    )


def trace_memory_update(
    items_updated: int = 1,
    keys: Optional[list[str]] = None,
    memory_type: str = "long_term",
    store: str = "agent_memory_graph",
):
    """Wrap ``MemoryGraph.update()`` / ``enrich_node()`` calls.

    Emits an ``update_memory`` span (record.count = updated records).
    """
    return _memory_span(
        "update",
        memory_type=memory_type,
        store=store,
        record_count=items_updated,
        **{
            "amg.memory.keys": keys,
        },
    )


def trace_memory_delete(
    items_deleted: int = 1,
    keys: Optional[list[str]] = None,
    store: str = "agent_memory_graph",
):
    """Wrap ``MemoryGraph.remove()`` calls.

    Emits a ``delete_memory`` span (record.count = deleted records).
    """
    return _memory_span(
        "delete",
        memory_type="short_term",
        store=store,
        record_count=items_deleted,
        **{
            "amg.memory.keys": keys,
        },
    )
