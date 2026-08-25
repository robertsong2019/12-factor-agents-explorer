# Cycle 512: write-time embedding amortization (HEARTBEAT top dev
# target). The C506 side-channel re-embeds every haystack chunk per
# question (7.5s/q on the full-500 run). A content-addressed cache
# warmed at ingest time must (a) reproduce uncached scores exactly,
# (b) embed each unique chunk once, (c) survive adapter replacement
# (the run_eval per-question fresh-adapter protocol).
from test_amg_bench_quality import SIDECAR_SESSIONS, _StubEngine

import amg_bench_quality as abq
from amg_bench_quality import LongMemEvalAdapter, SidechannelCache

Q_EMBED = "any recommendations for guitar shopping?"


def _counting_engine(directions):
    """_StubEngine wrapped to count raw embed() texts."""
    inner = _StubEngine(directions)
    seen: list[str] = []

    class _Counting:
        tier = "stub"

        def embed(self, texts):
            seen.extend(texts)
            return inner.embed(texts)

    return _Counting(), seen


class TestSidechannelCache:
    def test_put_get_roundtrip(self):
        c = SidechannelCache()
        c.put("hello world", [0.5, 0.5])
        assert c.get("hello world") == [0.5, 0.5]

    def test_keyed_by_text_content(self):
        c = SidechannelCache()
        c.put("a", [1.0])
        assert c.get("a") == [1.0]
        assert c.get("b") is None

    def test_embed_missing_only_embeds_misses(self):
        engine, seen = _counting_engine({"x": [1, 0, 0, 0]})
        c = SidechannelCache()
        v1 = c.embed_missing(["x one", "x two"], engine)
        assert len(seen) == 2 and all(v is not None for v in v1)
        seen.clear()
        v2 = c.embed_missing(["x one", "x two", "fresh x"], engine)
        # Only the new text hits the engine; cached ones are reused.
        assert seen == ["fresh x"]
        assert v2[0] == v1[0] and v2[1] == v1[1]

    def test_eviction_fifo(self):
        c = SidechannelCache(maxsize=2)
        c.put("one", [1.0])
        c.put("two", [2.0])
        c.put("three", [3.0])
        assert c.get("one") is None      # oldest evicted
        assert c.get("two") == [2.0]
        assert c.get("three") == [3.0]

    def test_stats_counters(self):
        engine, _ = _counting_engine({"x": [1, 0, 0, 0]})
        c = SidechannelCache()
        c.embed_missing(["a x", "b x"], engine)
        c.embed_missing(["a x"], engine)          # pure hit
        s = c.stats()
        assert s["size"] == 2
        assert s["hits"] == 1 and s["misses"] == 2
        assert s["embed_calls"] == 2
        assert abs(s["hit_rate"] - 1 / 3) < 1e-9


SESSIONS_TURNS = [
    {"session_id": "a", "turns": [
        {"role": "user", "content": "pasta sauce simmering tonight"}]},
    {"session_id": "b", "turns": [
        {"role": "user", "content": "stratocaster versus les paul"}]},
]


class TestScoresCacheParity:
    def test_scores_identical_with_and_without_cache(self):
        engine = _StubEngine({"guitar": [1, 0, 0, 0],
                              "stratocaster": [1, 0, 0, 0],
                              "pasta": [0, 1, 0, 0]})
        plain = abq.session_embedding_scores(
            "stratocaster advice", SESSIONS_TURNS, engine)
        cached = abq.session_embedding_scores(
            "stratocaster advice", SESSIONS_TURNS, engine,
            cache=SidechannelCache())
        assert cached == plain

    def test_precompute_then_query_embeds_zero_chunks(self):
        engine, seen = _counting_engine({"guitar": [1, 0, 0, 0],
                                         "stratocaster": [1, 0, 0, 0],
                                         "pasta": [0, 1, 0, 0]})
        cache = SidechannelCache()
        warmed = cache.precompute_sessions(SESSIONS_TURNS, engine)
        assert warmed == 2                      # one chunk per session
        seen.clear()
        scores = abq.session_embedding_scores(
            "stratocaster advice", SESSIONS_TURNS, engine, cache=cache)
        # Only the question was embedded at query time.
        assert seen == ["stratocaster advice"]
        plain = abq.session_embedding_scores(
            "stratocaster advice", SESSIONS_TURNS, engine)
        assert scores == plain

    def test_precompute_accepts_ingest_shape(self):
        engine, seen = _counting_engine({"pasta": [0, 1, 0, 0]})
        cache = SidechannelCache()
        # ingest_sessions shape: "messages" instead of "turns".
        assert cache.precompute_sessions(SIDECAR_SESSIONS, engine) == 2
        assert len(seen) == 2


def _installed(**kw):
    a = LongMemEvalAdapter(max_context_tokens=2000, **kw)
    a.sidechannel = True
    a._side_engine = _StubEngine({"guitar": [1, 0, 0, 0],
                                  "stratocaster": [1, 0, 0, 0],
                                  "pasta": [0, 1, 0, 0]})
    a._side_probed = True
    return a


class TestAdapterWriteTimeAmortization:
    def test_ingest_precomputes_chunk_embeddings(self):
        a = _installed()
        stats = a.ingest_sessions(SIDECAR_SESSIONS)
        assert stats["chunks_embedded"] == 2
        _, meta = a.retrieve_context(Q_EMBED)
        assert meta["sidechannel"] == "embed"
        assert meta["sidecache"]["misses"] == 0   # all warm at query
        assert meta["sidecache"]["hits"] == 2

    def test_cold_cache_first_query_then_amortized(self):
        a = _installed()                          # engine installed,
        a.ingest_sessions(SIDECAR_SESSIONS)       # cache stays cold
        a.sidechannel_cache.forget()
        ctx1, m1 = a.retrieve_context(Q_EMBED)
        assert m1["sidecache"]["misses"] == 2
        ctx2, m2 = a.retrieve_context(Q_EMBED)
        assert m2["sidecache"]["misses"] == 0
        assert m2["sidecache"]["hits"] == 2
        assert ctx2 == ctx1                       # cache is invisible

    def test_shared_cache_crosses_adapters(self):
        # run_eval rebuilds a fresh adapter+graph per question —
        # amortization must survive via an external shared cache.
        cache = SidechannelCache()
        a1 = _installed(sidechannel_cache=cache)
        a1.ingest_sessions(SIDECAR_SESSIONS)
        a1.sidechannel_cache.forget()
        _, m1 = a1.retrieve_context(Q_EMBED)
        assert m1["sidecache"]["misses"] == 2
        a2 = _installed(sidechannel_cache=cache)
        a2.ingest_sessions(SIDECAR_SESSIONS)
        _, m2 = a2.retrieve_context(Q_EMBED)
        assert m2["sidecache"]["misses"] == 0
        assert m2["sidecache"]["hits"] == 2

    def test_cache_disabled_when_sidechannel_off(self):
        a = _installed(sidechannel=False)
        a.sidechannel = False
        a._side_engine = None
        a._side_probed = False
        stats = a.ingest_sessions(SIDECAR_SESSIONS)
        assert stats["chunks_embedded"] == 0
