"""
amg.telemetry — OpenTelemetry GenAI semantic conventions for agent-memory-graph.

Emits ``gen_ai.memory.*`` spans following the OTel GenAI semantic conventions
(v1.41 attribute names, ``gen_ai.memory.*`` RFC).

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
from typing import Any, Optional
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

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


@contextmanager
def _memory_span(
    operation: str,
    memory_type: str = "long_term",
    store: str = "agent_memory_graph",
    **extra: Any,
):
    """Context manager for a ``gen_ai.memory.*`` span.

    In inert mode (no OTel), yields None and does nothing.
    In active mode, creates an INTERNAL span with standard attributes.
    """
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return

    span_name = f"gen_ai.memory.{operation}"
    kind = trace.SpanKind.INTERNAL if hasattr(trace, "SpanKind") else None
    with tracer.start_as_current_span(span_name, kind=kind) as span:
        span.set_attribute("gen_ai.memory.operation", operation)
        span.set_attribute("gen_ai.memory.type", memory_type)
        span.set_attribute("gen_ai.memory.store", store)
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

    Emits a ``gen_ai.memory.store`` span with item count and metadata.
    """
    return _memory_span(
        "store",
        memory_type=memory_type,
        store=store,
        **{
            "gen_ai.memory.items_stored": items,
            "gen_ai.memory.namespace": namespace,
            "gen_ai.memory.actor_id": actor_id,
        },
    )


def trace_memory_search(
    query: Optional[str] = None,
    top_k: int = 10,
    min_score: Optional[float] = None,
    memory_type: str = "semantic",
    store: str = "agent_memory_graph",
):
    """Wrap ``MemoryGraph.search()`` / ``multi_hop_reason()`` / ``spreading_activation()`` calls."""
    return _memory_span(
        "search",
        memory_type=memory_type,
        store=store,
        **{
            "gen_ai.memory.search.query": query,
            "gen_ai.memory.search.top_k": top_k,
            "gen_ai.memory.search.min_score": min_score,
        },
    )


def trace_memory_retrieve(
    items_retrieved: Optional[int] = None,
    memory_type: str = "long_term",
    store: str = "agent_memory_graph",
    hit: Optional[bool] = None,
):
    """Wrap ``MemoryGraph.get()`` / ``neighbors()`` / PPR calls."""
    return _memory_span(
        "retrieve",
        memory_type=memory_type,
        store=store,
        **{
            "gen_ai.memory.items_retrieved": items_retrieved,
            "gen_ai.memory.hit": hit,
        },
    )


def trace_memory_update(
    items_updated: int = 1,
    keys: Optional[list[str]] = None,
    memory_type: str = "long_term",
    store: str = "agent_memory_graph",
):
    """Wrap ``MemoryGraph.update()`` / ``enrich_node()`` calls."""
    return _memory_span(
        "update",
        memory_type=memory_type,
        store=store,
        **{
            "gen_ai.memory.items_updated": items_updated,
            "gen_ai.memory.keys": keys,
        },
    )


def trace_memory_delete(
    items_deleted: int = 1,
    keys: Optional[list[str]] = None,
    store: str = "agent_memory_graph",
):
    """Wrap ``MemoryGraph.remove()`` calls."""
    return _memory_span(
        "delete",
        memory_type="short_term",
        store=store,
        **{
            "gen_ai.memory.items_deleted": items_deleted,
            "gen_ai.memory.keys": keys,
        },
    )
