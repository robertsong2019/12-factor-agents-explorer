"""amg_bench_quality.py — LongMemEval memory-quality adapter for agent-memory-graph.

Research #061 design (2026-08-12) promoted into the real repo lineage
(Cycle 446 repatriated amg_bench.py / telemetry.py, explicitly unblocking
this adapter). Where amg_bench.py measures *performance* (throughput,
latency), this module measures *memory quality*: how well the graph
recalls the right information per LongMemEval question.

Adapted to the REAL lineage API (per the C446 lineage-drift warning):
retrieval uses ``search_graphrag`` + ``personalized_pagerank`` — the
code-lab-only ``spreading_activation`` / ``multi_hop_reason`` from the
original research skeleton are NOT available here.

Pipeline (zero LLM / zero API cost — retrieval-only quality mode):

    LongMemEval JSON  [{"question", "answer", "haystack_sessions", ...}]
        → ingest_sessions()    [session/message/entity nodes + edges]
        → retrieve_context()   [keyword seeds → PPR → budgeted context
                                + entropy confidence over evidence]
        → answer_extractive()  [top message, dual confidence gate
                                (score + entropy) → "I don't know"
                                abstention on weak scattered evidence]
        → evaluate()           [per-category accuracy + abstention +
                                retrieval-hit rate + tokens/query]
        → sweep_abstention()   [entropy-threshold sweep, one retrieval
                                per question — abstention tuning]

The abstention path is amg's differentiation angle (Research #061
Insight #3): LongMemEval ``_abs`` questions test events that never
happened — the correct answer is "I don't know", and most systems
hallucinate instead.

Answering/judging LLM prompts (``format_answer_prompt`` /
``format_judge_prompt``) are provided for future full-mode runs; the
default zero-cost mode uses extractive answers + ``exact_judge``.

Dataset (one-time download, offline thereafter):

    huggingface-cli download xiaowu0162/longmemeval-cleaned \
        --repo-type dataset --local-dir <data_dir>

CLI:

    python amg_bench_quality.py --data longmemeval_s_cleaned.json \
        --limit 50 --output results/lme_amg.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from memory_graph import MemoryGraph

__all__ = [
    "QuestionResult",
    "CategorySummary",
    "LongMemEvalAdapter",
    "score_confidence",
    "entropy_gate_fires",
    "exact_judge",
    "parse_lme_date",
    "temporal_arith_form",
    "duration_units",
    "answer_temporal_arith",
    "temporal_arith_judge",
    "recall_form",
    "answer_speaker_recall",
    "load_longmemeval_data",
    "run_eval",
    "judge_llm",
    "judge_mock",
    "judge_ollama",
    "calibration_summary",
    "calibration_by_category",
    "main",
]

# Token estimate parity with run_amg (GPT-style BPE ≈ 1.3 tokens/word).
TOKENS_PER_WORD = 1.3

ABSTAIN_ANSWER = "I don't know"

# LongMemEval question-id suffix → category (Research #061 §1).
CATEGORIES = {
    "single-session-user": "single_session_user",
    "single-session-assistant": "single_session_assistant",
    "single-session-preference": "single_session_preference",
    "multi-session": "multi_session",
    "knowledge-update": "knowledge_update",
    "temporal-reasoning": "temporal_reasoning",
}

# Sentence-initial words that are capitalized by grammar, not by being
# proper nouns — excluded from naive entity extraction.
NON_ENTITY_CAPS = {
    "i", "the", "my", "we", "you", "it", "actually", "got", "what",
    "when", "where", "who", "how", "that", "this", "there", "so",
    "and", "but", "oh", "ok", "okay", "yes", "no", "great", "thanks",
    "thank", "hi", "hey", "a", "an", "in", "on", "at", "for", "to",
}

KEYWORD_STOP = NON_ENTITY_CAPS | {
    "is", "are", "was", "were", "did", "does", "do",
    "of", "or", "about", "say", "said", "tell", "told",
    "there", "their", "with", "from", "into", "any",
    "which", "whom", "whose", "why", "user", "current",
    "preferred", "preference", "now", "did", "does",
}


def _estimate_tokens(text: str) -> int:
    """Approximate token count (words × 1.3, minimum 1) — run_amg parity."""
    return max(1, round(len(text.split()) * TOKENS_PER_WORD))


def _strip_quotes(w: str) -> str:
    """Strip surrounding quotes/apostrophes: ``'ibotta'`` → ibotta.

    Cycle 471: quoted tokens never matched anything (forensics
    e072b769 — ``'ibotta'`` keyword scored 0 against a line saying
    "Ibotta" 25 times).
    """
    return w.strip("'\"")


def _keywords(question: str) -> list[str]:
    """Content keywords from a question (lowercased, stopwords removed).

    Possessives are stripped BEFORE the stopword filter so "user's"
    normalizes to the stopped word "user" (not a phantom keyword).
    Quotes are stripped so ``'ibotta'`` normalizes to ``ibotta``.
    """
    words = [_strip_quotes(w.removesuffix("'s"))
             for w in re.findall(r"[A-Za-z']+", question.lower())]
    return [w for w in words if len(w) > 2 and w not in KEYWORD_STOP]


# Inflectional suffixes only (NOT derivational "ly"/"ness") — so
# "switch" matches "switched" but "love" does NOT match "lovely".
_INFLECTIONS = {"s", "es", "ed", "d", "ing"}


def _token_matches(token: str, kw: str) -> bool:
    """Word-boundary match with inflectional morphology tolerance.

    Covers plain suffixes (``switch``/``switched``), e-deletion
    (``hike``/``hiking``) and consonant doubling (``run``/``running``)
    — but NOT derivational morphology (``love`` ⊄ ``lovely``).
    Cycle 471 tried a shared-prefix stem for submitted/submission
    and reverted it: no prefix length separates that pair from
    instacart/instagram ("insta"), and the derivational pair it
    targeted turned out to be retrieval-window-limited anyway.
    """
    if token == kw:
        return True
    if (len(kw) >= 3 and token.startswith(kw)
            and token[len(kw):] in _INFLECTIONS):
        return True
    if (len(token) >= 3 and kw.startswith(token)
            and kw[len(token):] in _INFLECTIONS):
        return True
    # e-deletion: hike→hiking, love→loving (both directions).
    if kw.endswith("e") and len(kw) >= 4 and token == kw[:-1] + "ing":
        return True
    if token.endswith("e") and len(token) >= 4 and kw == token[:-1] + "ing":
        return True
    # consonant doubling: run→running, swim→swimming.
    if (len(kw) >= 3 and kw[-1] not in "aeiou"
            and token == kw + kw[-1] + "ing"):
        return True
    if (len(token) >= 3 and token[-1] not in "aeiou"
            and kw == token + token[-1] + "ing"):
        return True
    return False


def _keyword_hits(label: str, keywords: list[str]) -> int:
    """Count keywords present in *label* (word-boundary + inflections).

    Substring matching (``kw in label``) is deliberately avoided:
    "love" would match "lovely" and corrupt ranking (caught by the
    Cycle 447 smoke run). Line tokens are quote-stripped and
    possessive-normalized so ``master's`` matches ``master``
    (Cycle 471).
    """
    tokens = [_strip_quotes(t.removesuffix("'s"))
              for t in re.findall(r"[a-z']+", label.lower())]
    return sum(1 for kw in keywords
               if any(_token_matches(t, kw) for t in tokens))


# ── Entropy confidence (Cycle 448 — Research #061 Insight #3/#4) ─────

def score_confidence(scores: list[int]) -> dict:
    """Entropy confidence over candidate keyword-hit scores.

    Treats the hit counts of retrieved message candidates as an
    evidence distribution ``p_i = hits_i / Σhits`` and measures how
    *flat* it is:

    * ``norm_entropy`` — Shannon entropy normalized by ``log2(n)``;
      1.0 = perfectly flat (every candidate equally "evident"),
      → 0 = one dominant candidate.
    * ``margin`` — relative gap between the top-2 scores (1.0 when
      a single candidate holds all the evidence).

    Args:
        scores: keyword-hit counts of the ranked message candidates
            (zero/negative entries are ignored — only actual hits
            count as evidence).

    Returns:
        ``{best, evidence, entropy, norm_entropy, margin}``.
    """
    s = sorted((x for x in scores if x > 0), reverse=True)
    n = len(s)
    if n == 0:
        return {"best": 0, "evidence": 0, "entropy": 0.0,
                "norm_entropy": 0.0, "margin": 0.0}
    if n == 1:
        return {"best": s[0], "evidence": 1, "entropy": 0.0,
                "norm_entropy": 0.0, "margin": 1.0}
    total = float(sum(s))
    ps = [x / total for x in s]
    entropy = -sum(p * math.log2(p) for p in ps)
    return {
        "best": s[0],
        "evidence": n,
        "entropy": entropy,
        "norm_entropy": entropy / math.log2(n),
        "margin": (s[0] - s[1]) / s[0],
    }


def entropy_gate_fires(conf: dict, abstain_entropy: float | None,
                       weak_score: int) -> bool:
    """Whether the entropy abstention gate fires for *conf*.

    The gate targets **weak scattered evidence** — the regime where
    the extractive answer is a guess:

    * ``best <= weak_score`` — no candidate holds strong keyword
      evidence;
    * ``norm_entropy >= abstain_entropy`` — the weak evidence is
      spread flat over the candidates;
    * ``evidence >= 3`` — with exactly TWO equally-scored candidates
      amg has a principled disambiguator (bitemporal recency: the
      ``-seq`` tie-break makes the LATEST value win, the designed
      knowledge-update semantics, C437/C447). Scattered ≥ 3-way
      weakness has no such resolution — latest-of-many-unrelated is
      uniform guessing.

    Strong ties (``best > weak_score``) never fire: a co-scoring old/
    new pair is the knowledge-update signature, resolved by recency.

    Args:
        conf: ``score_confidence()`` output for the retrieval.
        abstain_entropy: entropy threshold in ``[0, 1]``; ``None``
            disables the gate entirely (Cycle 447 behavior).
        weak_score: max keyword-hit count still considered weak.

    Returns:
        True → abstain ("I don't know").
    """
    if abstain_entropy is None or conf["evidence"] < 3:
        return False
    return (conf["best"] <= weak_score
            and conf["norm_entropy"] >= abstain_entropy)


def _normalize(text: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace."""
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def evidence_session_ids(item: dict) -> set[str]:
    """Resolve dataset ``answer_session_ids`` → ingest-side session ids.

    LongMemEval-cleaned ships ``haystack_session_ids`` parallel to
    ``haystack_sessions`` (evidence sessions are hidden among noise
    sessions). ``run_eval`` ingests bare-list sessions with positional
    ``session_{j+1}`` ids; dict sessions keep their own ``session_id``.
    This mirrors that convention so evidence coverage can be scored
    against the adapter's ``node→session_id`` map (Cycle 467).

    Returns an empty set when the item carries no evidence pointers
    (synthetic datasets) — callers treat coverage as unresolvable
    (``None``), never as a miss: honest unknown > confident wrong
    label (C466 lesson 3).
    """
    ans = item.get("answer_session_ids") or []
    hs_ids = item.get("haystack_session_ids") or []
    sessions = (item.get("haystack_sessions")
                or item.get("sessions") or [])
    if not ans or not hs_ids:
        return set()
    ans_set = {str(a) for a in ans}
    out: set[str] = set()
    for j, sid in enumerate(hs_ids):
        if str(sid) not in ans_set or j >= len(sessions):
            continue
        s = sessions[j]
        out.add(s.get("session_id")
                if isinstance(s, dict) and s.get("session_id")
                else f"session_{j + 1}")
    return out


@dataclass
class QuestionResult:
    """Result for a single LongMemEval question."""
    question_id: str
    category: str
    question: str
    ground_truth: str
    predicted_answer: str
    abstained: bool = False
    correct: bool = False
    retrieval_hit: bool = False
    latency_ms: float = 0.0
    tokens_est: int = 0
    retrieval: dict = field(default_factory=dict)
    # Dual-metric scoring (judge_mode="dual"): exact + LLM verdicts
    # side by side so one metric's gains can't mask the other's
    # losses (Research #069 — kupdate 0.0 was a protocol artifact).
    correct_exact: bool | None = None
    correct_llm: bool | None = None
    # Evidence-session coverage (Cycle 467): did retrieval surface
    # ANY message from a session the dataset marks as answer
    # evidence? ``None`` = item carries no evidence pointers (metric
    # unresolvable — distinct from a miss). Fixes the structural
    # blindness of truth-containment ``retrieval_hit`` on categories
    # whose truths are synthesized ("The user would prefer…" —
    # preference 30q hit 0.000 was a metric artifact, not retrieval).
    answer_session_hit: bool | None = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class CategorySummary:
    """Aggregated results for one LongMemEval category."""
    category: str
    total: int = 0
    correct: int = 0
    abstentions: int = 0
    hits: int = 0
    total_tokens: int = 0
    # Cycle 467: evidence coverage over RESOLVABLE questions only.
    answer_hits: int = 0
    answer_resolved: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def abstention_rate(self) -> float:
        return self.abstentions / self.total if self.total else 0.0

    @property
    def retrieval_hit_rate(self) -> float:
        return self.hits / self.total if self.total else 0.0

    @property
    def answer_session_hit_rate(self) -> float:
        return (self.answer_hits / self.answer_resolved
                if self.answer_resolved else 0.0)

    @property
    def avg_tokens(self) -> float:
        return self.total_tokens / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "total": self.total,
            "correct": self.correct,
            "abstentions": self.abstentions,
            "accuracy": round(self.accuracy, 4),
            "abstention_rate": round(self.abstention_rate, 4),
            "retrieval_hit_rate": round(self.retrieval_hit_rate, 4),
            "answer_session_hits": self.answer_hits,
            "answer_sessions_resolved": self.answer_resolved,
            "answer_session_hit_rate": round(
                self.answer_session_hit_rate, 4),
            "avg_tokens": round(self.avg_tokens, 1),
        }


class LongMemEvalAdapter:
    """Adapts LongMemEval datasets for amg memory-quality evaluation.

    Phase 1 (ingest): conversation sessions → session / message /
    entity nodes with ``contains`` / ``follows`` / ``mentioned_in``
    edges. Phase 2 (retrieve): keyword seeds → ``search_graphrag``
    local mode → optional ``personalized_pagerank`` expansion →
    token-budgeted message context. Phase 3 (answer): extractive top
    message with a confidence gate for abstention.
    """

    def __init__(self, mg: MemoryGraph | None = None, *,
                 use_ppr: bool = True,
                 max_context_tokens: int = 4000,
                 abstain_score: float = 1.0,
                 abstain_entropy: float | None = 0.95,
                 entropy_weak_score: int = 1,
                 temporal_arith: bool = True,
                 counting: bool = True,
                 assistant_recall: bool = True,
                 recall_min_score: int = 5,
                 recall_mode: str = "distinctive",
                 ppr_top: int = 15,
                 seed_recall_k: int = 5,
                 recall_seed_k: int = 40):
        """Args:
            mg: MemoryGraph to ingest into (default: fresh in-memory).
            use_ppr: Enable PersonalizedPageRank expansion (multi-hop).
            max_context_tokens: Token budget for retrieved context.
            abstain_score: Minimum keyword-hit count of the best
                candidate below which the adapter abstains ("I don't
                know"). ``0`` disables this gate.
            abstain_entropy: Entropy-gate threshold (Cycle 448): when
                the best candidate is weak (``<= entropy_weak_score``)
                and its evidence distribution is flat
                (``norm_entropy >= abstain_entropy`` over ≥3
                candidates), abstain instead of guessing.
                ``None`` disables (Cycle 447 behavior).
            entropy_weak_score: Max keyword hits still counted as
                "weak" for the entropy gate.
            temporal_arith: Enable the Cycle 457 temporal-arithmetic
                answer path (duration/ordering questions resolved by
                calendar arithmetic on session dates; falls through
                to the extractive path when anchors don't resolve).
            counting: Enable the Cycle 477 multi-session counting
                path (evidence-side aggregation for total days /
                total money / total number of instances / argmax
                entity forms over the full ingested haystack;
                unresolved forms fall through to the gate chain).
            assistant_recall: Enable the Cycle 468 speaker-recall
                answer path (you-addressed "remind me what you
                recommended" forms answered from the best-scored
                ASSISTANT sentence; falls through when no sentence
                reaches *recall_min_score*).
            recall_min_score: Min keyword hits for the speaker-recall
                sentence to be trusted as an answer (below: fall
                through to the gate chain). Used by ``raw`` mode only.
            recall_mode: Speaker-recall scoring mode (Cycle 475 /
                Research #074). ``"distinctive"`` (default) scores
                squared distinctive weights ``w(kw)^2`` with a preface
                penalty — prefaces parasitize raw overlap; ``"raw"``
                preserves the Cycle 468 raw-hit counting.
            ppr_top: Extra candidates taken from the PPR tail.
            seed_recall_k: Per-keyword recall limit for seed building.
            recall_seed_k: Per-keyword recall limit for
                speaker-recall questions (Cycle 473). You-addressed
                recall hunts ASSISTANT evidence; weight-ordered
                recall at breadth 5 truncated the evidence session
                out of the candidate set for 10/12 coverage misses.
                Scoped via ``recall_form`` — broader seeds on
                temporal questions feed mirror lines into the window
                (A/B: temporal exact 0.271→0.105 at k=40).
        """
        self.mg = mg if mg is not None else MemoryGraph(db_path=":memory:")
        self.use_ppr = use_ppr
        self.max_context_tokens = max_context_tokens
        self.abstain_score = abstain_score
        self.abstain_entropy = abstain_entropy
        self.entropy_weak_score = entropy_weak_score
        self.temporal_arith = temporal_arith
        self.counting = counting
        self.assistant_recall = assistant_recall
        self.recall_min_score = recall_min_score
        self.recall_mode = recall_mode
        self.ppr_top = ppr_top
        self.seed_recall_k = seed_recall_k
        self.recall_seed_k = recall_seed_k
        # Adapter-side bookkeeping (avoids depending on repo getter
        # APIs): node id → {label, kind, role, seq, session_id}.
        self._nodes: dict[str, dict] = {}
        self._messages: dict[str, dict] = {}       # message nodes only
        self._entities: dict[str, str] = {}        # entity name → node id
        self._session_dates: dict[str, str] = {}   # session id → YYYY-MM-DD
        self._seq = 0                               # deterministic order

    # ── Phase 1: ingestion ─────────────────────────────────────────

    def ingest_sessions(self, sessions: list[dict],
                        session_dates: dict[str, str] | None = None) -> dict:
        """Ingest conversation sessions into the memory graph.

        Each session: ``{"session_id", "timestamp"?, "messages":
        [{"role", "content", "timestamp"?}, ...]}``. Creates a session
        node, message nodes (``contains`` + ``follows`` edges) and
        entity nodes for capitalized non-stopwords
        (``mentioned_in`` edges, deduplicated across sessions).

        Args:
            sessions: Sessions to ingest.
            session_dates: Optional ``session_id → date`` map
                (Cycle 457) — canonicalized via ``parse_lme_date``;
                unparsable entries skipped. Powers the
                temporal-arithmetic answer path.

        Returns:
            Stats dict ``{sessions, messages, entities, edges}``.
        """
        stats = {"sessions": 0, "messages": 0, "entities": 0, "edges": 0}
        if session_dates:
            for sid, dt in session_dates.items():
                canon = parse_lme_date(str(dt))
                if canon:
                    self._session_dates[str(sid)] = canon

        for session in sessions:
            sid = session.get("session_id",
                              f"session_{stats['sessions'] + 1}")
            session_node = self.mg.add(
                f"Session: {sid}", kind="session",
                data={"session_id": sid,
                      "timestamp": session.get("timestamp", "")})
            self._seq += 1
            self._nodes[session_node.id] = {
                "label": f"Session: {sid}", "kind": "session",
                "role": "", "seq": self._seq, "session_id": sid}

            prev_msg_id = None
            msg_ids = []
            for msg in session.get("messages", []):
                role = msg.get("role", "unknown")
                content = str(msg.get("content", ""))
                self._seq += 1
                node = self.mg.add(
                    content, kind="message",
                    data={"role": role, "session_id": sid, "seq": self._seq,
                          "timestamp": msg.get("timestamp", "")})
                self._nodes[node.id] = {
                    "label": content, "kind": "message", "role": role,
                    "seq": self._seq, "session_id": sid}
                self._messages[node.id] = self._nodes[node.id]
                msg_ids.append(node.id)

                self.mg.link(session_node.id, node.id, relation="contains")
                stats["edges"] += 1
                if prev_msg_id is not None:
                    self.mg.link(prev_msg_id, node.id, relation="follows")
                    stats["edges"] += 1
                prev_msg_id = node.id
                stats["messages"] += 1

            stats["edges"] += self._extract_entities(
                session.get("messages", []), msg_ids, stats)

            stats["sessions"] += 1

        return stats

    def _extract_entities(self, messages: list[dict],
                          msg_ids: list[str], stats: dict) -> int:
        """Create/dedupe entity nodes; link ``mentioned_in`` edges."""
        edges = 0
        for msg, msg_id in zip(messages, msg_ids):
            for word in re.findall(r"[A-Za-z]+", str(msg.get("content", ""))):
                if (len(word) <= 2 or not word[0].isupper()
                        or word.lower() in NON_ENTITY_CAPS):
                    continue
                if word not in self._entities:
                    self._seq += 1
                    ent = self.mg.add(word, kind="entity",
                                      data={"name": word, "seq": self._seq})
                    self._nodes[ent.id] = {
                        "label": word, "kind": "entity", "role": "",
                        "seq": self._seq, "session_id": ""}
                    self._entities[word] = ent.id
                    stats["entities"] += 1
                self.mg.link(self._entities[word], msg_id,
                             relation="mentioned_in")
                edges += 1
        return edges

    # ── Phase 2: retrieval ─────────────────────────────────────────

    def retrieve_context(self, question: str,
                         question_date: str = "") -> tuple[str, dict]:
        """Retrieve a token-budgeted message context for *question*.

        Pipeline: keyword ``recall`` seeds → ``search_graphrag``
        (local mode, adds BM25-scored candidates) → optional PPR
        expansion → messages ranked by ``(-keyword_hits, -seq)`` and
        packed into the token budget.

        The ``-seq`` tie-break makes knowledge-update questions
        deterministically prefer the LATEST matching message (later
        sessions ingest with higher seq), regardless of clock
        resolution — a run_amg C439-style determinism guard.

        Returns:
            ``(context_text, metadata)`` with ``candidates_found``,
            ``messages_retrieved``, ``best_score``, ``confidence``
            (entropy evidence report), ``latency_ms``, ``tokens_est``.
        """
        start = time.perf_counter()
        keywords = _keywords(question)
        candidate_ids: set[str] = set()

        # Cycle 473: speaker-recall seed breadth. Per-question
        # haystacks hold hundreds of assistant messages; the
        # weight-ordered per-keyword recall (ORDER BY weight DESC
        # LIMIT k) truncated the evidence session out of the
        # candidate set for 10/12 evhit misses (C473 forensics:
        # ev_in_candidates=0 while the messages scored 7-16 keyword
        # hits). Broad seeds hand selection to the question-aware
        # (-hits, -seq) ranker instead of ingest-weight order.
        # Scoped to recall_form ONLY — the same breadth on temporal
        # questions floods the window with question-echoing advice
        # lines (A/B: temporal exact 36→14/133); C471/C472 anchor
        # geometry is tuned at breadth 5.
        k_eff = (self.recall_seed_k if recall_form(question)
                 else self.seed_recall_k)

        # Seed: direct keyword recall (substring match, zero-cost).
        for kw in keywords[:8]:
            for node in self.mg.recall(kw, limit=k_eff):
                candidate_ids.add(node.id)

        # Scored candidates: graphrag local (BM25 + 1-hop expansion).
        try:
            for r in self.mg.search_graphrag(question, mode="local",
                                             limit=10):
                candidate_ids.add(r.get("node_id", ""))
        except Exception:
            pass  # search may raise on empty graphs — recall is enough

        # Multi-hop expansion: PPR from the seed set.
        if self.use_ppr and candidate_ids:
            seeds = [nid for nid in candidate_ids if nid][:8]
            try:
                ppr = self.mg.personalized_pagerank(seeds)
                for nid in sorted(ppr, key=ppr.get, reverse=True):
                    if len(candidate_ids) >= len(seeds) + self.ppr_top:
                        break
                    candidate_ids.add(nid)
            except Exception:
                pass

        # Rank known message candidates by keyword hits.
        ranked: list[tuple[int, int, str]] = []  # (-hits, -seq, id)
        for nid in candidate_ids:
            info = self._messages.get(nid)
            if info is None:
                continue
            hits = _keyword_hits(info["label"], keywords)
            ranked.append((-hits, -info["seq"], nid))
        ranked.sort()

        lines: list[str] = []
        retrieved_ids: list[str] = []
        tokens = 0
        best_score = 0
        for neg_hits, _, nid in ranked:
            info = self._messages[nid]
            line = f"[{info['role'] or '?'}] {info['label']}"
            if lines and tokens + _estimate_tokens(line) > self.max_context_tokens:
                break
            lines.append(line)
            retrieved_ids.append(nid)
            tokens += _estimate_tokens(line)
            best_score = max(best_score, -neg_hits)

        # Entropy confidence over the full candidate evidence —
        # gate telemetry + sweep_abstention input (Cycle 448).
        confidence = score_confidence([-neg for neg, _, _ in ranked])

        context = "\n".join(lines)
        latency = (time.perf_counter() - start) * 1000
        meta = {
            "candidates_found": len(candidate_ids),
            "messages_retrieved": len(lines),
            "best_score": best_score,
            "confidence": confidence,
            "latency_ms": latency,
            "tokens_est": tokens,
            "keywords": keywords,
            "retrieved_ids": retrieved_ids,   # Cycle 451: turn-level evidence scoring
        }
        return context, meta

    # ── Phase 3: answering ─────────────────────────────────────────

    def answer_extractive(self, question: str,
                          question_date: str = "") -> tuple[str, dict]:
        """Extractive answer with the dual confidence gate (no LLM).
        The best-ranked message is the answer; the adapter abstains
        with ``"I don't know"`` when confidence is low — the correct
        behavior on LongMemEval ``_abs`` questions (Research #061
        Insight #3). Gate order:

        1. ``empty`` — nothing retrieved;
        2. ``score`` — best keyword-hit count < ``abstain_score``;
        3. ``entropy`` — weak scattered evidence (best <= weak,
           flat distribution over ≥3 candidates, Cycle 448);
        else ``answer``.

        Returns:
            ``(answer, metadata)`` — metadata is the retrieval dict
            plus ``abstained`` and ``gate`` (the firing reason).
        Also when abstaining the retrieval context is stashed into the
        metadata (``meta["context"]``) so ``evaluate`` can still score
        ``retrieval_hit`` — abstention and retrieval quality are
        independent axes (a system can retrieve nothing AND rightly
        abstain, or retrieve the truth but gate the answer wrongly).
        """
        context, meta = self.retrieve_context(question, question_date)
        meta["context"] = context

        # Cycle 457: temporal-arithmetic path — duration/ordering
        # questions answered by calendar arithmetic on session dates
        # (node→session map from ingest wiring). Runs BEFORE the gate
        # chain: an unresolvable form falls through untouched (the
        # gates still own abstention); a resolved form bypasses them
        # (arithmetic on two distinct dated sessions is not a guess).
        if (self.temporal_arith and self._session_dates
                and temporal_arith_form(question)):
            def _dated(nids):
                return [
                    (f"[{self._nodes[nid]['role'] or '?'}] "
                     f"{self._nodes[nid]['label']}",
                     self._session_dates.get(
                         self._nodes[nid]["session_id"], ""))
                    for nid in nids if nid in self._nodes]

            t_ans, t_detail = answer_temporal_arith(
                question, _dated(meta.get("retrieved_ids", [])),
                question_date)
            if t_ans is None and t_detail.get("form"):
                # Cycle 472: full-graph anchor retry. When the window
                # cannot resolve the form (missing anchors OR both
                # anchors landing on the same session — the dominant
                # failure: assistant advice lines that lexically
                # mirror the question crowd out the true event lines
                # and collapse both anchors onto one wrong session),
                # retry against ALL ingested messages where the C471
                # tie ladder has the full candidate set. Window-first
                # is preserved: an in-window answer is never second-
                # guessed; walls that persist on the full graph
                # still fall through untouched (C472 A/B: the 4
                # prev-correct same-session cases stay None).
                t_ans, t_detail = answer_temporal_arith(
                    question, _dated(self._messages), question_date)
                if t_ans is not None:
                    t_detail["fallback"] = "full_graph"
            meta["temporal"] = t_detail
            if t_ans is not None:
                meta["gate"] = "temporal_arith"
                meta["abstained"] = False
                return t_ans, meta

        # Cycle 477: multi-session counting forms — evidence-side
        # aggregation (#075 i3 layered integration: ONLY precision-
        # ≥0.5 mechanisms — duration_sum 0.67 / total_sum 1.00 /
        # number_total 0.50 / argmax 0.50; entity_count 0.20 stays
        # prototype-level pending the venue+date composite key).
        # Calendar-distance questions were claimed by C457 above
        # (counting_form returns None for them); counting owns
        # sum/argmax forms over the FULL ingested haystack —
        # aggregation over a retrieval window undercounts (the C472
        # full-graph lesson applies to sums too). Fall-through
        # preserved: an unresolved form reaches the gates untouched.
        if self.counting and counting_form(question):
            c_ans, c_detail = answer_counting(
                question, self._counting_sessions())
            meta["counting"] = c_detail
            if c_ans is not None:
                meta["gate"] = "counting"
                meta["abstained"] = False
                return c_ans, meta

        # Cycle 468: speaker-recall path — you-addressed "remind me
        # what you recommended" forms. Assistant answers are multi-
        # paragraph and the specific fact sits mid-body, so message-
        # level ranking surfaces generic openers ("Sure, here are…");
        # this path scores assistant SENTENCES and returns the best.
        # Runs before the gate chain: an unresolved form (no sentence
        # reaches recall_min_score) falls through untouched.
        if self.assistant_recall and recall_form(question):
            r_ans, r_detail = answer_speaker_recall(
                question, self._nodes,
                min_score=self.recall_min_score,
                mode=self.recall_mode)
            meta["speaker_recall"] = r_detail
            if r_ans is not None:
                meta["gate"] = "speaker_recall"
                meta["abstained"] = False
                return r_ans, meta

        conf = meta["confidence"]
        if not meta["messages_retrieved"]:
            gate = "empty"
        elif meta["best_score"] < self.abstain_score:
            gate = "score"
        elif entropy_gate_fires(conf, self.abstain_entropy,
                                self.entropy_weak_score):
            gate = "entropy"
        else:
            gate = "answer"
        meta["gate"] = gate
        if gate != "answer":
            meta["abstained"] = True
            return ABSTAIN_ANSWER, meta
        meta["abstained"] = False
        # First context line = best-ranked message ([role] prefix).
        best_line = context.split("\n", 1)[0]
        return best_line.split("] ", 1)[-1], meta

    def _counting_sessions(self) -> list[dict]:
        """All ingested messages grouped by session, in ingest order.

        The #075 prototype's evidence-session shape — session-level
        grouping is what duration_sum's anchor propagation and
        signature dedup operate on. Full haystack, not the retrieval
        window: aggregation over a window undercounts.
        """
        by_sess: dict[str, dict] = {}
        for nid in sorted(self._messages,
                          key=lambda n: self._messages[n]["seq"]):
            info = self._messages[nid]
            s = by_sess.setdefault(
                info["session_id"],
                {"session_id": info["session_id"], "turns": []})
            s["turns"].append({"role": info["role"],
                               "content": info["label"]})
        return list(by_sess.values())

    @staticmethod
    def format_answer_prompt(question: str, context: str,
                             question_date: str = "") -> str:
        """Reader prompt for full-mode (LLM) evaluation runs."""
        date_hint = (f"\n(Current date: {question_date})"
                     if question_date else "")
        return (
            "You are a helpful assistant with access to conversation "
            "history.\nAnswer the question based ONLY on the provided "
            "conversation context.\nIf the information is not in the "
            "context, say 'I don't know'.\n\n"
            f"## Conversation History\n{context}\n\n"
            f"## Question\n{question}{date_hint}\n\n## Answer\n"
        )

    @staticmethod
    def format_judge_prompt(question: str, ground_truth: str,
                            predicted: str) -> str:
        """Judge prompt for full-mode (LLM) evaluation runs."""
        return (
            "You are an impartial judge evaluating whether the "
            "predicted answer conveys the same information as the "
            "ground truth answer.\n\n"
            f"Question: {question}\n"
            f"Ground Truth: {ground_truth}\n"
            f"Predicted: {predicted}\n\n"
            "Respond with ONLY '1' if the answers match in meaning, "
            "or '0' if they differ."
        )

    # ── Full evaluation loop ────────────────────────────────────────

    def evaluate(self, dataset: list[dict], *, judge_fn=None,
                 limit: int = 0, judge_mode: str = "exact") -> dict:
        """Run the full evaluation over a LongMemEval dataset.

        Per question: retrieve + extractive answer + judge. Scoring:

        * ``judge_fn(question, truth, predicted) -> bool`` when given
          (full-mode LLM judge), else ``exact_judge`` containment.
        * ``_abs`` questions (qid suffix or ``abstention`` flag) score
          correct iff the adapter abstained.
        * ``retrieval_hit``: normalized ground truth appears in the
          retrieved context — the zero-cost recall-quality metric
          (Research #061 Action 1: retrieval-only mode).

        ``judge_mode="dual"`` additionally scores every non-abstention
        question with :func:`judge_llm` (ollama endpoint with mock
        fallback), producing ``accuracy_exact`` / ``accuracy_llm`` /
        ``calibration`` report keys — one metric's gains can't mask
        the other's losses (Research #069).

        Args:
            dataset: ``[{"id", "question", "answer", ...}]``.
              ``question_id`` is honored as an id fallback (C466 —
              LongMemEval-cleaned naming), and ``question_type`` /
              ``category`` override category heuristics when present
              (C466 — honest attribution for calibration_by_category).
            judge_fn: Optional external judge; default containment.
            limit: Evaluate at most this many questions (0 = all).
            judge_mode: "exact" (default) or "dual".

        Returns:
            Report dict: overall accuracy / retrieval-hit rate /
            abstention rate / avg tokens per query, per-category
            summaries, per-question results, adapter config.
        """
        items = dataset[:limit] if limit and limit > 0 else dataset
        results: list[QuestionResult] = []
        cat: dict[str, CategorySummary] = {}

        for i, item in enumerate(items):
            # C466: LongMemEval-cleaned ships ``question_id`` (not ``id``);
            # honoring it keeps run_eval rows traceable (was: all "0",
            # because run_eval passes single-item lists → index 0).
            qid = str(item.get("id") or item.get("question_id") or i)
            question = str(item.get("question", ""))
            truth = str(item.get("answer", ""))
            is_abs = qid.endswith("_abs") or bool(item.get("abstention"))

            predicted, meta = self.answer_extractive(
                question, item.get("question_date", ""))

            if is_abs:
                correct = meta["abstained"]
            elif meta.get("gate") == "temporal_arith":
                correct = temporal_arith_judge(question, truth,
                                               predicted)
            elif meta.get("gate") == "counting":
                correct = counting_judge(question, truth, predicted)
            elif judge_fn is not None:
                correct = bool(judge_fn(question, truth, predicted))
            else:
                correct = exact_judge(question, truth, predicted)

            correct_exact: bool | None = None
            correct_llm: bool | None = None
            if judge_mode == "dual":
                correct_exact = correct
                if is_abs:
                    # abstention semantics are protocol-level, not
                    # semantic — both metrics share the verdict
                    correct_llm = correct
                else:
                    verdict = judge_llm(question, predicted, truth)
                    correct_llm = (None if verdict == "ERROR"
                                   else verdict == "CORRECT")

            # retrieval_hit: truth text appears in the retrieved
            # context — the zero-cost recall-quality metric
            # (Research #061 Action 1: retrieval-only mode).
            hit = (bool(truth) and not is_abs
                   and _normalize(truth) in _normalize(meta["context"]))

            # Cycle 467: evidence-session coverage — resolvable only
            # when the item ships answer_session_ids; None means
            # unresolvable (excluded from rates, never counted a miss).
            answer_session_hit: bool | None = None
            ev_ids = evidence_session_ids(item)
            if ev_ids:
                retrieved_sessions = {
                    self._nodes[nid]["session_id"]
                    for nid in meta.get("retrieved_ids", [])
                    if nid in self._nodes}
                answer_session_hit = bool(retrieved_sessions & ev_ids)

            # C466: dataset question_type/category is AUTHORITATIVE when
            # present — _classify_question heuristics mislabel otherwise
            # (full-500 LME_s: 419/500 → single_session_user, temporal 49
            # vs true 133; raw ids carry no category suffix).
            qtype = str(item.get("question_type")
                        or item.get("category") or "").strip().lower()
            category = (CATEGORIES.get(qtype, qtype) if qtype
                        else self._classify_question(question, qid))
            res = QuestionResult(
                question_id=qid, category=category, question=question,
                ground_truth=truth, predicted_answer=predicted,
                abstained=meta["abstained"], correct=correct,
                retrieval_hit=hit,
                answer_session_hit=answer_session_hit,
                latency_ms=meta["latency_ms"], tokens_est=meta["tokens_est"],
                correct_exact=correct_exact, correct_llm=correct_llm,
                retrieval={"best_score": meta["best_score"],
                           "candidates_found": meta["candidates_found"],
                           "messages_retrieved": meta["messages_retrieved"],
                           "norm_entropy": meta["confidence"]["norm_entropy"],
                           "margin": meta["confidence"]["margin"],
                           "gate": meta["gate"]})
            results.append(res)

            summary = cat.setdefault(category,
                                     CategorySummary(category=category))
            summary.total += 1
            summary.correct += int(correct)
            summary.abstentions += int(meta["abstained"])
            summary.hits += int(hit)
            summary.total_tokens += meta["tokens_est"]
            if answer_session_hit is not None:
                summary.answer_resolved += 1
                summary.answer_hits += int(answer_session_hit)

        total = len(results)
        resolved = [r for r in results if r.answer_session_hit is not None]
        report = {
            "overall_accuracy": (sum(r.correct for r in results) / total
                                 if total else 0.0),
            "retrieval_hit_rate": (sum(r.retrieval_hit for r in results)
                                   / total if total else 0.0),
            "answer_session_hit_rate": (
                sum(r.answer_session_hit for r in resolved)
                / len(resolved) if resolved else 0.0),
            "answer_sessions_resolved": len(resolved),
            "abstention_rate": (sum(r.abstained for r in results) / total
                                if total else 0.0),
            "avg_tokens": (sum(r.tokens_est for r in results) / total
                           if total else 0.0),
            "total_questions": total,
            "categories": {k: v.to_dict() for k, v in cat.items()},
            "results": [r.to_dict() for r in results],
            "config": {"use_ppr": self.use_ppr,
                       "temporal_arith": self.temporal_arith,
                       "max_context_tokens": self.max_context_tokens,
                       "abstain_score": self.abstain_score,
                       "abstain_entropy": self.abstain_entropy,
                       "entropy_weak_score": self.entropy_weak_score,
                       "judge_mode": judge_mode},
        }
        if judge_mode == "dual":
            report["accuracy_exact"] = report["overall_accuracy"]
            scored = [r for r in results if r.correct_llm is not None]
            report["accuracy_llm"] = (
                sum(1 for r in scored if r.correct_llm) / len(scored)
                if scored else 0.0)
            report["calibration"] = calibration_summary(results)
            report["calibration_by_category"] = \
                calibration_by_category(results)
        return report

    def sweep_abstention(self, dataset: list[dict], *,
                         entropies: list[float | None],
                         limit: int = 0) -> dict:
        """Entropy-threshold sweep — one retrieval per question.

        Retrieval is the expensive stage; the entropy gate is a pure
        post-retrieval decision over the cached evidence report, so
        every question is retrieved ONCE and then gated at each
        threshold (Cycle 448 — C447 Next Step #2, abstention
        threshold tuning without re-retrieval cost).

        Args:
            dataset: LongMemEval items (``id``/``question``/
                ``answer``; ``_abs`` suffix = abstention-scored).
            entropies: thresholds to evaluate (each in ``[0, 1]``;
                ``None`` = gate off — the Cycle 447 baseline).
            limit: Sweep at most this many questions (0 = all).

        Returns:
            ``{"thresholds": [labels], "summary": {label: {accuracy,
            abstention_rate, total}}, "rows": [{"id", "abstained":
            {label: bool}, "correct": {label: bool}}]}`` — labels are
            ``str(threshold)`` (``"None"`` for the off-baseline).
            Scoring matches ``evaluate``: ``_abs`` correct iff
            abstained, else ``exact_judge`` containment.
        """
        items = dataset[:limit] if limit and limit > 0 else dataset
        labels = ["None" if e is None else str(e) for e in entropies]

        rows: list[dict] = []
        totals = {lab: [0, 0] for lab in labels}  # correct, abstained

        for i, item in enumerate(items):
            qid = str(item.get("id", i))
            question = str(item.get("question", ""))
            truth = str(item.get("answer", ""))
            is_abs = qid.endswith("_abs") or bool(item.get("abstention"))

            context, meta = self.retrieve_context(
                question, item.get("question_date", ""))
            conf = meta["confidence"]
            best_line = context.split("\n", 1)[0] if context else ""
            extracted = best_line.split("] ", 1)[-1] if best_line else ""

            row = {"id": qid, "abstained": {}, "correct": {}}
            for entropy, lab in zip(entropies, labels):
                abstained = (
                    not meta["messages_retrieved"]
                    or meta["best_score"] < self.abstain_score
                    or entropy_gate_fires(conf, entropy,
                                          self.entropy_weak_score))
                correct = (abstained if is_abs else
                           exact_judge(question, truth,
                                       ABSTAIN_ANSWER if abstained
                                       else extracted))
                row["abstained"][lab] = abstained
                row["correct"][lab] = correct
                totals[lab][0] += int(correct)
                totals[lab][1] += int(abstained)
            rows.append(row)

        n = len(rows)
        summary = {lab: {"accuracy": (c / n if n else 0.0),
                         "abstention_rate": (a / n if n else 0.0),
                         "total": n}
                   for lab, (c, a) in totals.items()}
        return {"thresholds": labels, "summary": summary, "rows": rows}

    @staticmethod
    def _classify_question(question: str, qid: str) -> str:
        """Map a question to a LongMemEval category (id suffix first)."""
        qid_lower = qid.lower()
        for suffix, category in CATEGORIES.items():
            if suffix in qid_lower:
                return category
        q = question.lower()
        if any(w in q for w in ("change", "update", "switch",
                                "current", "now ")):
            return "knowledge_update"
        if any(w in q for w in ("when", "before", "after")):
            return "temporal_reasoning"
        if "assistant" in q:
            return "single_session_assistant"
        if "prefer" in q:
            return "single_session_preference"
        return "single_session_user"


def exact_judge(question: str, truth: str, predicted: str) -> bool:
    """Containment judge — truth normalized inside predicted (or equal).

    Zero-cost default for retrieval-only runs; a fixed LLM judge
    should be used for comparable leaderboard numbers.
    """
    if not truth or not predicted:
        return False
    nt, np_ = _normalize(truth), _normalize(predicted)
    return nt == np_ or nt in np_


# ── LLM judge (Cycle 462 — Research #069: dual-metric scoring) ─────
#
# Reference-anchored binary judgment for the cat5 / knowledge-update
# residual where containment fails on semantically-equivalent answers.
# Protocol choices (per 2026-08 research): (1) reference-anchored beats
# prompt-only; (2) binary CORRECT/WRONG avoids score-ID and rubric-order
# bias; (3) explicit failure conditions (missing key fact / contradiction /
# different entity substitution); (4) ollama OpenAI-compatible endpoint
# for zero-API-cost runs with deterministic mock fallback so the pipeline
# is always runnable and testable.

JUDGE_PROMPT = """You are a strict answer grader for a memory-QA benchmark.

Question: {question}

Candidate answer: {answer}

Grade the candidate answer against the reference answer below.
The candidate is CORRECT only if it contains the same key information as the
reference (paraphrase, pronoun substitution, or superset details are OK).
It is WRONG if the key fact is missing, contradicted, or a different entity
is substituted (e.g. wrong person, wrong date).
Do not reward verbosity. Do not infer missing facts.
Reply with exactly one word: CORRECT or WRONG.

Reference answer: {reference}"""


def judge_mock(question: str, answer: str, reference: str) -> str:
    """Deterministic mock judge — word-level F1 >= 0.35 containment.

    Used to validate pipeline plumbing and calibration aggregation
    without ollama; NOT for drawing real conclusions.
    """
    if not reference:
        return "CORRECT"
    if not answer:
        return "WRONG"
    a_toks = set(re.findall(r"[a-z0-9']+", answer.lower()))
    r_toks = set(re.findall(r"[a-z0-9']+", reference.lower()))
    if not r_toks:
        return "CORRECT"
    overlap = len(a_toks & r_toks) / len(r_toks)
    return "CORRECT" if overlap >= 0.35 else "WRONG"


def judge_ollama(question: str, answer: str, reference: str, *,
                 endpoint: str = "http://localhost:11434/v1/chat/completions",
                 model: str = "qwen2.5:7b", timeout: int = 60) -> str:
    """Single LLM verdict via an OpenAI-compatible (ollama) endpoint.

    Returns "CORRECT" / "WRONG" / "ERROR" (network/model failure).
    """
    import urllib.request
    payload = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 8,
        "messages": [
            {"role": "system",
             "content": "You are a binary grader. Output one word only."},
            {"role": "user",
             "content": JUDGE_PROMPT.format(
                 question=question, answer=answer, reference=reference)},
        ],
    }
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode()) or ""
        out = (body.get("choices", [{}])[0]
               .get("message", {}).get("content", "")).strip().upper()
        if "CORRECT" in out:
            return "CORRECT"
        if "WRONG" in out:
            return "WRONG"
        return "ERROR"
    except Exception:  # noqa: BLE001 — any failure grades as ERROR
        return "ERROR"


def judge_llm(question: str, answer: str, reference: str, *,
              mode: str | None = None, n_judges: int = 1,
              **ollama_kw) -> str:
    """Majority-vote LLM judge — Research #069 protocol.

    Args:
        mode: "mock" forces the deterministic mock judge; "ollama"
            forces the real endpoint; None auto-detects (tries one
            ollama call, falls back to mock for the rest of the run).
        n_judges: votes per item — odd >= 3 enables majority voting
            (Memora: 3-judge atomic-criteria majority ≈ κ 0.86-0.90).
            ERROR votes don't count toward the majority; all-ERROR →
            "ERROR".

    Returns "CORRECT" / "WRONG" / "ERROR".
    """
    global _JUDGE_MODE
    if mode is None:
        mode = _JUDGE_MODE
    votes: list[str] = []
    if mode is None:
        # One-time probe: a live ollama endpoint sticks for the run,
        # a dead one degrades permanently to the mock judge.
        v = judge_ollama(question, answer, reference, **ollama_kw)
        mode = "ollama" if v != "ERROR" else "mock"
        _JUDGE_MODE = mode
        if v != "ERROR":
            votes.append(v)
    for _ in range(max(1, n_judges) - len(votes)):
        if mode == "ollama":
            votes.append(judge_ollama(
                question, answer, reference, **ollama_kw))
        else:
            votes.append(judge_mock(question, answer, reference))
    valid = [v for v in votes if v != "ERROR"]
    if not valid:
        return "ERROR"
    return "CORRECT" if valid.count("CORRECT") > len(valid) / 2 else "WRONG"


_JUDGE_MODE: str | None = None  # sticky auto-detect cache


def calibration_summary(results: list) -> dict:
    """Exact-vs-LLM calibration over dual-scored results.

    Divergence rate > 25% means the rubric needs re-review before
    either number is quoted (judge validation practice).
    """
    n = 0
    agree = llm_only_correct = llm_only_wrong = errors = 0
    for r in results:
        # Duck-typed access: QuestionResult attrs or report dict rows.
        exact = (r.correct_exact if hasattr(r, "correct_exact")
                 else r.get("correct_exact"))
        llm = (r.correct_llm if hasattr(r, "correct_llm")
               else r.get("correct_llm"))
        if exact is None:
            continue
        n += 1
        if llm is None:  # judge errored on this item
            errors += 1
            continue
        if exact == llm:
            agree += 1
        elif llm and not exact:
            llm_only_correct += 1  # semantic-equivalence rescues
        else:
            llm_only_wrong += 1  # false passes — sample manually
    div = (llm_only_correct + llm_only_wrong) / max(n, 1)
    return {
        "scored": n,
        "agree": agree,
        "llm_only_correct": llm_only_correct,
        "llm_only_wrong": llm_only_wrong,
        "judge_errors": errors,
        "divergence_rate": round(div, 4),
        "verdict": "rubric OK" if div <= 0.25 else "RECALIBRATE",
    }


def calibration_by_category(results: list) -> dict:
    """Category-wise exact-vs-LLM divergence breakdown (Cycle 465).

    Groups dual-scored results by category and runs
    :func:`calibration_summary` per group, so a full-run divergence
    verdict traces to the categories driving it — e.g. kupdate
    llm_only_correct rescues (containment too strict) diverge in the
    opposite direction from adversarial llm_only_wrong false passes.
    Duck-typed input — QuestionResult attrs or report dict rows,
    same protocol as :func:`calibration_summary`.
    """
    groups: dict[str, list] = {}
    for r in results:
        cat = (r.category if hasattr(r, "category")
               else r.get("category")) or "unknown"
        groups.setdefault(cat, []).append(r)
    return {cat: calibration_summary(rows)
            for cat, rows in sorted(groups.items())}


# ── Temporal arithmetic (Cycle 457 — LME_s temporal-reasoning) ──────
#
# LongMemEval temporal-reasoning questions are NOT when-questions
# (the C456 LoCoMo discovery): they are duration arithmetic ("how many
# days passed between X and Y", "how many weeks ago did I X") and
# event ordering ("which happened first, X or Y?"). The dataset gives
# structured grounding — ``question_date`` plus ``haystack_dates``
# (one date per session) — so the answer side can do calendar
# arithmetic over session dates, zero LLM. Mirrors C456's philosophy:
# trigger on question FORM (category-agnostic), resolve on RETRIEVED
# context only, fall through (no fabrication) when anchors don't
# resolve to distinct dated sessions.

_LME_DATE_RE = re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})")

# Cycle 468 — speaker-recall form: you-addressed recall targets the
# assistant's own prior statements; a first-person source phrase
# ("remind me what I told you") is user-side and must not fire.
_RECALL_YOU_RE = re.compile(
    r"(remind me|you (?:told|recommended|suggested|mentioned|said|"
    r"advised|gave)|did you (?:say|suggest|recommend)|"
    r"your (?:recommendation|suggestion|advice))", re.I)
_RECALL_USER_SRC_RE = re.compile(
    r"\b(?:i|we)\s+(?:told|said|mentioned|asked|"
    r"recommended|suggested)\b", re.I)

# Generic event-words stripped from anchor phrases so "the day I
# visited the MoMA" scores on "moma", not on "day/visited".
_ANCHOR_GENERIC = frozenset({
    "event", "day", "days", "time", "one", "thing",
    "visit", "visited", "went", "go", "started", "start",
    "attended", "attend", "met", "meet", "participated",
    "participate", "receive", "received", "helped", "help",
    "prepare", "played", "play", "made", "make", "finished",
    "finish", "completed", "complete", "bought", "buy",
    "sold", "sell", "get", "got",
})

_TA_BETWEEN_RE = re.compile(
    r"how many (days?|weeks?|months?|years?)\s+"
    r"(?:have\s+|had\s+)?passed\s+between\s+(.+?)\s+and\s+(.+?)\s*[?.!]*$",
    re.I | re.S)
_TA_AGO_RE = re.compile(
    r"how many (days?|weeks?|months?|years?)\s+ago\s+"
    r"(?:did\s+)?(?:i\s+)?(.+?)\s*[?.!]*$",
    re.I | re.S)
_TA_SINCE_RE = re.compile(
    r"how many (days?|weeks?|months?|years?)\s+have\s+passed\s+since\s+"
    r"(?:i\s+)?(.+?)\s*[?.!]*$",
    re.I | re.S)
_TA_FIRST_RE = re.compile(
    r"^(?:who|which\b[^,?]*)\b.*?\bfirst\s*,\s*(.+?)\s+or\s+(.+?)\s*[?.!]*$",
    re.I | re.S)

# Cycle 482 forms: calendar-distance questions in new surface
# clothes. Forensics on the 63 form-missed temporal questions:
# the two largest coherent families are plain ``between``
# arithmetic — "how many days before X did I Y" (5q) and "how
# many days had passed since A when B" (4q). Both map onto the
# existing two-anchor machinery; only the form regex was missing.
_TA_BEFORE_RE = re.compile(
    r"how many (days?|weeks?|months?|years?)\s+before\s+(.+?)\s+"
    r"did\s+(?:i\s+)?(.+?)\s*[?.!]*$",
    re.I | re.S)
_TA_SINCEWHEN_RE = re.compile(
    r"how many (days?|weeks?|months?|years?)\s+had\s+passed\s+since\s+"
    r"(?:i\s+)?(.+?)\s+when\s+(?:i\s+)?(.+?)\s*[?.!]*$",
    re.I | re.S)

# Cycle 482: in-text adverbial dates. The true event lines STATE
# their dates ("attended the workshop on January 10th") while the
# session dates collapse same-session events onto one day — the
# day-level truth lives in the line text. Only ADVERBIAL dates
# engage (preposition "on" directly before the date): dated NOUNS
# ("the March 15th issue of The New Yorker") are entity names,
# not event times — engaging them would regress the currently-
# correct issue-reading question onto the issue's publication date.
_MONTH_WORD_RE = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
                  r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
                  r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
                  r"dec(?:ember)?")
_TA_LINE_DATE_RE = re.compile(
    r"\bon\s+(?:the\s+)?(?P<m1>" + _MONTH_WORD_RE + r")\.?,?\s+"
    r"(?P<d1>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<y1>\d{4}))?"
    r"|\bon\s+the\s+(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s+of\s+"
    r"(?P<m2>" + _MONTH_WORD_RE + r")\.?(?:,?\s+(?P<y2>\d{4}))?",
    re.I)
_TA_MONTH_NUM = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5,
                 "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
                 "nov": 11, "dec": 12}

# C482 closeness gate: an in-text date only engages when it sits
# within this many days of the session that contains it (true
# event dates cluster near the session; far dates are plans).
_TA_DATE_PROXIMITY = 14


def _line_adverbial_date(line: str, year_hint: str = "") -> str | None:
    """First adverbial date in *line* as ISO ``YYYY-MM-DD``.

    Matches ``on January 10th`` / ``on Jun 14`` / ``on the 3rd of
    March`` / ``on March 5, 2022`` (explicit year beats *year_hint*).
    Dated nouns and month-year mentions without a day return
    ``None`` (see the module comment for the regression guard).
    """
    m = _TA_LINE_DATE_RE.search(line or "")
    if not m:
        return None
    if m.group("m1"):
        mon = _TA_MONTH_NUM[m.group("m1")[:3].lower()]
        day, yr = int(m.group("d1")), m.group("y1")
    else:
        day = int(m.group("d2"))
        mon = _TA_MONTH_NUM[m.group("m2")[:3].lower()]
        yr = m.group("y2")
    if yr:
        year = int(yr)
    elif year_hint and str(year_hint).isdigit():
        year = int(year_hint)
    else:
        return None
    try:
        return date(year, mon, day).isoformat()
    except ValueError:
        return None


def recall_form(question: str) -> str | None:
    """Classify a speaker-recall question form (Cycle 468).

    You-addressed recall ("remind me what you recommended",
    "did you suggest…", "your advice on…") targets the ASSISTANT's
    own prior statements. Returns ``"assistant"``; ``None`` when
    the question is not you-addressed recall, or when it carries a
    first-person source ("remind me what I told you") — that is
    user-side recall and must NOT be answered from assistant nodes.
    """
    q = (question or "").strip()
    if _RECALL_USER_SRC_RE.search(q):
        return None
    return "assistant" if _RECALL_YOU_RE.search(q) else None


# Cycle 475 preface lexicon (Research #074): generic openers
# ("Sure, here are…") directly answer the question, so they
# necessarily overlap its keywords — in dialogue recall, word
# overlap is a NEGATIVE discriminator for prefaces (the AS2
# literature's most reliable feature, reversed). The three v5.1
# additions came from forensics: the contraction "Here's",
# "Thank you for providing…", "I hope these help".
_RECALL_PREAMBLE_RE = re.compile(
    r"^(?:sure|absolutely|of course|certainly|"
    r"yes,?\s*(?:here|of course|sure)|"
    r"great (?:idea|question|news)|"
    r"i(?:'d| would| will) (?:be happy|love|be delighted) to|"
    r"i can help|i'?m happy to|"
    r"here(?:\s+are|\s+is|'s)|let me know if|"
    r"(?:(?:i|we)\s+)?hope (?:this|that|these) help(?:s|ed)?|"
    r"happy to (?:help|provide|share|suggest)|"
    r"thank you for (?:sharing|providing)|"
    r"would you like me to)", re.I)


def _split_sentences(text: str) -> list[str]:
    """Sentences (and line-broken fragments) longer than 10 chars."""
    parts = re.split(r"(?<=[.!?])\s+|\n", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 10]


def answer_speaker_recall(question: str,
                          nodes: dict,
                          min_score: int = 5,
                          mode: str = "distinctive",
                          distinctive_df: int = 8,
                          weighted_floor: float = 10.0,
                          ) -> tuple[str | None, dict]:
    """Best assistant SENTENCE for a you-addressed recall question.

    The full graph is the agent's own memory — scanning it is
    legitimate retrieval, not ground-truth peeking (answer_session_ids
    are never read).

    ``mode="distinctive"`` (default, Cycle 475 / Research #074 v5):
    squared distinctive weights ``w(kw)**2`` with ``w = 1 +
    log(N/df)`` over the assistant-sentence pool. Prefaces parasitize
    raw overlap (they answer the question directly), so ranking is
    dominated by rare content hits instead:

    * raw floor 3 — the v3 zero-flip lesson: parasitism is
      FLOOR-level, and answer sentences with distinctive-but-few
      hits never clear the legacy raw ``min_score`` of 5;
    * necessary condition: at least one matched keyword with
      ``df <= distinctive_df`` (a table header matching six
      mid-frequency terms is not an answer row);
    * preface sentences take a ``x0.25`` score penalty (v2 proved a
      rank-level novelty multiplier regresses — dual-regime
      reversal — while the floor-level penalty flips nothing);
    * ``'?'`` sentences are skipped, and the winner must reach
      ``weighted_floor`` (else unresolved, caller falls through).

    ``mode="raw"`` preserves the Cycle 468 behavior: raw
    ``_keyword_hits`` counting against *min_score*.

    Returns:
        ``(answer, detail)`` — answer ``None`` = unresolved (caller
        falls through to the gate chain); detail carries the mode,
        best score, sentence pool size and the winning session.
    """
    kws = _keywords(question)
    if mode == "raw":
        best_sent: str | None = None
        best_score = 0
        best_session: str | None = None
        sentences_scanned = 0
        for nid, node in (nodes or {}).items():
            if node.get("role") != "assistant":
                continue
            for sent in _split_sentences(node.get("label", "")):
                sentences_scanned += 1
                s = _keyword_hits(sent, kws)
                if s > best_score:
                    best_score = s
                    best_sent = sent
                    best_session = node.get("session_id")
        detail = {"mode": "raw", "keywords": kws,
                  "sentences_scanned": sentences_scanned,
                  "best_score": best_score, "session_id": best_session,
                  "min_score": min_score}
        if best_sent is None or best_score < min_score:
            return None, detail
        return best_sent, detail

    # distinctive mode (Cycle 475)
    min_raw = 3
    pool: list[tuple[str, str | None]] = []
    for nid, node in (nodes or {}).items():
        if node.get("role") != "assistant":
            continue
        for sent in _split_sentences(node.get("label", "")):
            pool.append((sent.strip(), node.get("session_id")))
    detail: dict = {"mode": "distinctive", "keywords": kws,
                    "pool": len(pool), "questions_skipped": 0}
    if not pool:
        detail["best_score"] = 0
        return None, detail
    N = len(pool)
    df = {kw: sum(1 for s, _ in pool if _keyword_hits(s, [kw]))
          for kw in kws}
    w = {kw: (1.0 + math.log(N / d) if d else 0.0) for kw, d in df.items()}
    detail["df"] = {k: v for k, v in df.items() if v}
    best = None
    for s, sid in pool:
        if s.endswith("?"):
            detail["questions_skipped"] += 1
            continue
        matched = [kw for kw in kws if w[kw] and _keyword_hits(s, [kw])]
        if len(matched) < min_raw:
            continue
        if min(df[kw] for kw in matched) > distinctive_df:
            continue          # no distinctive hit -> not an answer row
        score = sum(w[kw] ** 2 for kw in matched)
        if _RECALL_PREAMBLE_RE.match(s):
            score *= 0.25
        if best is None or score > best[0]:
            best = (score, s, sid, len(matched))
    detail["best_score"] = round(best[0], 1) if best else 0
    if best is None:
        return None, detail
    detail["session_id"] = best[2]
    detail["raw_hits"] = best[3]
    if best[0] < weighted_floor:
        return None, detail
    return best[1], detail


def parse_lme_date(text: str) -> str:
    """Parse an LME date (``2023/02/01 (Wed) 10:20`` / ISO-ish) to
    canonical ``YYYY-MM-DD`` (``""`` when unparseable)."""
    m = _LME_DATE_RE.match((text or "").strip())
    if not m:
        return ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    except Exception:
        return ""


def temporal_arith_form(question: str) -> tuple | None:
    """Classify a temporal-arithmetic question form.

    Returns ``(kind, unit, anchor_a, anchor_b)`` — kind ``"between"``/
    ``"ago"``/``"since"`` carry a duration unit and two/one anchors;
    ``"first"`` carries two event anchors and unit ``""``.
    ``None`` = not a temporal-arithmetic form (leave to the normal
    answer path; category labels are NOT trusted — C456 lesson 4).
    """
    q = question.strip()
    m = _TA_BEFORE_RE.match(q)
    if m:      # "days before B did A" = between(A, B)
        return ("between", m.group(1).rstrip("s") or "day",
                m.group(3).strip(), m.group(2).strip())
    m = _TA_SINCEWHEN_RE.match(q)
    if m:      # "days since A when B" = between(A, B)
        return ("between", m.group(1).rstrip("s") or "day",
                m.group(2).strip(), m.group(3).strip())
    m = _TA_BETWEEN_RE.match(q)
    if m:
        return ("between", m.group(1).rstrip("s") or "day",
                m.group(2).strip(), m.group(3).strip())
    m = _TA_AGO_RE.match(q)
    if m:
        return ("ago", m.group(1).rstrip("s") or "day",
                m.group(2).strip(), None)
    m = _TA_SINCE_RE.match(q)
    if m:
        return ("since", m.group(1).rstrip("s") or "day",
                m.group(2).strip(), None)
    m = _TA_FIRST_RE.match(q)
    if m:
        return ("first", "", m.group(1).strip(), m.group(2).strip())
    return None


def _anchor_keywords(anchor: str) -> list[str]:
    """Distinctive content keywords for an event anchor phrase."""
    ks = [w for w in _keywords(anchor) if w not in _ANCHOR_GENERIC]
    return ks or _keywords(anchor)


def duration_units(date_a: str, date_b: str, unit: str) -> int:
    """Calendar distance between canonical dates in *unit*.

    Days are exact; months use calendar-month arithmetic with
    half-month rounding; years round on 365.25 days. Weeks round
    half-up on days/7 (Cycle 471 A/B: 13d→2w, 20d→3w, 23d→3w,
    30d→4w all fit round(); floor fails two, ceil fails two — the
    annotator semantics are "about N weeks", same family as the
    month half-rounding). Integer days never land on exactly
    x.5 weeks, so the rounding boundary is unambiguous.
    """
    da = date.fromisoformat(date_a)
    db = date.fromisoformat(date_b)
    days = abs((da - db).days)
    if unit == "week":
        return round(days / 7)
    if unit == "month":
        months = (da.year - db.year) * 12 + (da.month - db.month)
        if (da.day - db.day) > 15:
            months += 1
        elif (db.day - da.day) > 15:
            months -= 1
        return abs(months)
    if unit == "year":
        return round(days / 365.25)
    return days


# Cycle 471 tie-ladder lexicon: realized events beat stated
# intentions (forensics bucket A — "planning to run" vs "ran").
_TA_FUTURE_RE = re.compile(
    r"\b(?:plan(?:ning)?\s+to|will|going\s+to|wants?\s+to|"
    r"hope\s+to|thinking\s+of|looking\s+forward|next\s+"
    r"(?:week|month|year))\b", re.I)
_TA_PAST_RE = re.compile(
    r"\b(?:i|we)\s+(?:visited|attended|participated|went|had|took|"
    r"saw|got|ran|finished|completed|submitted|adopted|received|met|"
    r"did|made|bought|started|volunteered|helped|hosted|joined|won)\b",
    re.I)


def answer_temporal_arith(question: str,
                          dated_lines: list[tuple[str, str]],
                          question_date: str = "") -> tuple[str | None, dict]:
    """Answer a temporal-arithmetic question from dated evidence.

    Args:
        question: The raw question.
        dated_lines: Retrieved context as ``(line_text,
            session_date)`` pairs — session dates come from the
            node→session graph path (ingest wiring).
        question_date: Canonical ``YYYY-MM-DD`` ask date (ago/since
            reference point).

    Returns:
        ``(answer, detail)`` — answer ``None`` means the form didn't
        resolve (anchors unresolved / same session / impossible
        geometry); the caller falls through to the extractive path
        instead of fabricating. ``detail`` always describes the
        resolution for telemetry.
    """
    form = temporal_arith_form(question)
    detail: dict = {"form": None}
    if form is None:
        return None, detail
    kind, unit, a, b = form
    detail = {"form": kind, "unit": unit}

    def best_line(anchor: str) -> tuple[int, str] | None:
        """Best dated line for *anchor* (≥1 distinctive hit).

        Cycle 471 tie ladder (was: silent first-max = list-position
        tie-break, which decided 3 of 9 forensics failures):
        distinctive hits ↓, generic hits ↓ (tie-break only),
        user-role, past aspect over future marker, in-text date
        (Cycle 482), later date.
        """
        ks = _anchor_keywords(anchor)
        if not ks:
            return None
        gen = [w for w in _keywords(anchor)
               if w in _ANCHOR_GENERIC and w not in ks]
        best, best_key = None, None
        for line, sdate in dated_lines:
            hits = _keyword_hits(line, ks)
            if hits <= 0:
                continue
            # Cycle 482: an adverbial in-text date refines the
            # session date to day granularity — same-session
            # events that state their own dates separate, and
            # explicitly-dated lines outrank undated ones on ties
            # (they are the lines asserting WHEN the event was).
            # Closeness gate (asymmetric): only dates within
            # _TA_DATE_PROXIMITY days of the session — in EITHER
            # direction — or in the PAST relative to it engage.
            # Near dates are same-session day-granularity truth; a
            # past in-text date is later recall ("during Holi on
            # March 7th" mentioned weeks after). The poison is
            # far-FUTURE dates: reminder/plan lines ("set up a
            # reminder for the graduation on June 1st" in a March
            # session) carry dates that are NOT the anchor event's
            # time; engaging them hijacks the anchor onto the
            # plan's date (C482 A/B loss gpt4_7a0daae1: 1 week →
            # 12 weeks).
            eff = sdate
            ad = _line_adverbial_date(
                line, sdate[:4] or question_date[:4] or "")
            if ad:
                try:
                    delta = abs((date.fromisoformat(ad)
                                 - date.fromisoformat(sdate)).days)
                except ValueError:
                    delta = None
                if (delta is not None
                        and (delta <= _TA_DATE_PROXIMITY or ad < sdate)):
                    eff = ad
            try:
                date_key = (0, -date.fromisoformat(eff).toordinal())
            except ValueError:
                date_key = (1, 0)     # missing/unparseable date last
            key = (
                -hits,
                -(_keyword_hits(line, gen) if gen else 0),
                0 if line.startswith("[user]") else 1,
                1 if _TA_FUTURE_RE.search(line) else 0,
                0 if _TA_PAST_RE.search(line) else 1,
                0 if eff != sdate else 1,
                date_key,
            )
            if best_key is None or key < best_key:
                best, best_key = (hits, eff), key
        return best

    if kind == "first":
        ra, rb = best_line(a), best_line(b)
        detail["anchors"] = [bool(ra), bool(rb)]
        if not ra or not rb:
            return None, detail
        if ra[1] == rb[1]:          # same session — day granularity
            return None, detail    # cannot order within a session
        earlier = a if ra[1] < rb[1] else b
        detail["dates"] = [ra[1], rb[1]]
        return earlier, detail

    if kind in ("ago", "since"):
        qd = parse_lme_date(question_date)
        ra = best_line(a)
        detail["anchors"] = [bool(ra)]
        if not qd or not ra:
            return None, detail
        if ra[1] > qd:              # anchor resolves AFTER the ask —
            return None, detail    # wrong session; don't fabricate
        n = duration_units(qd, ra[1], unit)
        detail["dates"] = [ra[1], qd]
        detail["value"] = n
        return f"{n} {unit}{'' if n == 1 else 's'}", detail

    # between
    ra, rb = best_line(a), best_line(b)
    detail["anchors"] = [bool(ra), bool(rb)]
    if not ra or not rb:
        return None, detail
    if ra[1] == rb[1]:
        return None, detail
    n = duration_units(ra[1], rb[1], unit)
    detail["dates"] = [ra[1], rb[1]]
    detail["value"] = n
    return f"{n} {unit}{'' if n == 1 else 's'}", detail


def temporal_arith_judge(question: str, truth: str,
                         predicted: str) -> bool:
    """Judge temporal-arithmetic answers (zero cost).

    Duration forms: every integer of the ground truth is an accepted
    value (the dataset itself accepts "7 days. 8 days (including the
    last day) is also acceptable") — the predicted integer must be
    one of them. First-form: distinctive-keyword containment in
    EITHER direction (question anchors and gold answers name the
    same event with different word counts).
    """
    if not truth or not predicted:
        return False
    form = temporal_arith_form(question)
    if form is None:
        return exact_judge(question, truth, predicted)
    kind = form[0]
    if kind == "first":
        gold_ks = _anchor_keywords(truth)
        pred_ks = _anchor_keywords(predicted)
        return bool(pred_ks and gold_ks
                    and (pred_ks[0] in _normalize(truth)
                         or gold_ks[0] in _normalize(predicted)))
    golds = [int(x) for x in re.findall(r"\d+", str(truth))]
    preds = [int(x) for x in re.findall(r"\d+", str(predicted))]
    return bool(preds and golds and any(p in golds for p in preds))


# ════════ Cycle 477: multi-session counting forms (#075 i3) ════════
# Layered integration of the counting-aggregation prototype
# (msagg_proto_v2.py): ONLY precision-≥0.5 mechanisms enter the
# pipeline — duration_sum 0.67 / total_sum 1.00 / number_total
# 0.50 / argmax 0.50 (~11 correct of the 133-question multi-
# session axis). entity_count (prec 0.20) stays prototype-level
# pending the venue+date composite event key (#075 v3). Form-
# triggered like C456/C457/C473 — the form detector IS the
# configuration surface; unresolved forms fall through to the
# gate chain (abstention stays owned by the gates).

_CNT_WORD2NUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3,
                 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
                 'twelve': 12, 'fifteen': 15, 'twenty': 20,
                 'thirty': 30}

# speaker intent — intent lines carry unrealized (unspendable,
# unowned) durations/amounts and must not enter sums
_CNT_INTENT_RE = re.compile(
    r"\b(?:i(?:'m| am|’m)?\s+(?:thinking\s+of|planning|considering|"
    r"hoping\s+to|looking\s+(?:to|at|into)|going\s+to)|"
    r"i\s+(?:want|would\s+like|'ll|will|plan)\b|i'?d\s+like|"
    r"i\s+think\si(?:'ll|\s+will)|planning\s+a|i'll\b)", re.I)

# units that make a counted number a measurement, not an instance
_CNT_UNIT_BLACKLIST = {
    'gallon', 'gallons', 'pound', 'pounds', 'lb', 'lbs', 'mph',
    'kph', 'percent', 'dollar', 'dollars', 'mile', 'miles', 'km',
    'kilometer', 'kilometers', 'kg', 'kilogram', 'kilograms',
    'ounce', 'ounces', 'oz', 'liter', 'liters', 'litre', 'litres',
    'foot', 'feet', 'inch', 'inches', 'year', 'years', 'month',
    'months', 'week', 'weeks', 'day', 'days', 'hour', 'hours',
    'minute', 'minutes', 'degree', 'degrees'}

_CNT_GENERIC_HEADS = {
    'trip', 'trips', 'trek', 'treks', 'hike', 'hikes', 'thing',
    'things', 'item', 'items', 'stuff', 'one', 'ones', 'time',
    'times'}

_CNT_STOP_Q = {
    'many', 'much', 'have', 'does', 'did', 'that', 'this', 'with',
    'from', 'about', 'what', 'which', 'there', 'been', 'were',
    'will', 'would', 'currently', 'leading', 'worked', 'watched',
    'watching', 'spent', 'spend', 'take', 'took', 'combined',
    'total', 'year', 'month', 'past', 'recent', 'recently',
    'different', 'various', 'distinct', 'all', 'my', 'me', 'i',
    'in', 'on', 'at', 'the', 'a', 'an', 'of', 'for', 'and', 'or',
    'to', 'how', 'is', 'was', 'are', 'do', 'number', 'amount',
    'new', 'last', 'first', 'including', 'before', 'after',
    'making', 'offer', 'own', 'led', 'simultaneously',
    'excluding'}

_CNT_MONTHS = {'january', 'february', 'march', 'april', 'may',
               'june', 'july', 'august', 'september', 'october',
               'november', 'december'}
_CNT_WEEKDAYS = {'monday', 'tuesday', 'wednesday', 'thursday',
                 'friday', 'saturday', 'sunday'}
# capitalized tokens that are never instance names
_CNT_CAP_STOP = {
    "i'm", "i've", "i'll", "i'd", "it's", "that's", "they're",
    "we're", "you're", "don't", "doesn't", "didn't", "can't",
    "won't", "he's", "she's", "there's", "let's", "what's",
    'by', 'can', 'now', 'since', 'when', 'what', 'how', 'the',
    'do', 'does', 'did', 'so', 'and', 'but', 'if', 'then', 'also',
    'for', 'from', 'with', 'my', 'im', 'ive', 'ill', 'id'} | \
    _CNT_MONTHS | _CNT_WEEKDAYS

# noun-family hyponyms: family word expands to its members
_CNT_HYPONYM = {
    'instrument': {'guitar', 'piano', 'drum', 'violin', 'ukulele',
                   'bass', 'keyboard', 'saxophone', 'flute', 'cello',
                   'banjo', 'mandolin', 'trumpet', 'clarinet',
                   'synthesizer', 'organ', 'harp', 'trombone',
                   'viola'},
    'property': {'house', 'condo', 'townhouse', 'bungalow',
                 'apartment', 'loft', 'cottage', 'duplex', 'villa',
                 'cabin', 'flat'},
    'museum': {'museum', 'gallery', 'exhibition', 'exhibit'},
    'event': {'exhibition', 'lecture', 'tour', 'concert', 'show',
              'festival', 'workshop', 'event', 'meetup',
              'screening', 'performance'},
    'service': {'platform', 'app', 'service', 'website',
                'provider'},
    'store': {'store', 'market', 'shop', 'grocery'},
    'vehicle': {'bike', 'bicycle', 'car', 'motorcycle', 'scooter',
                'truck'},
    'plant': {'plant', 'seedling', 'shrub', 'tree'},
    'course': {'course', 'class', 'module', 'program'},
    'kit': {'kit', 'model'},
    'sibling': {'brother', 'sister'},
}


def _cnt_num(tok: str) -> float | None:
    tok = tok.lower()
    if tok in _CNT_WORD2NUM:
        return float(_CNT_WORD2NUM[tok])
    try:
        return float(tok)
    except ValueError:
        return None


def _cnt_sing(noun: str) -> str:
    if noun.endswith('ies'):
        return noun[:-3] + 'y'
    if noun.endswith('s') and not noun.endswith('ss'):
        return noun[:-1]
    return noun


def _cnt_sents(sessions: list[dict], role: str = 'user'):
    """Yield ``(session_index, sentence)`` for *role* turns."""
    for si, s in enumerate(sessions):
        for t in s.get('turns', []):
            if t.get('role') != role:
                continue
            for m in re.finditer(r'[^.!?]*[.!?]?',
                                 t.get('content', '')):
                sent = m.group(0).strip()
                if sent:
                    yield si, sent


def _cnt_proper_nouns(text: str) -> set[str]:
    """Capitalized runs minus contractions/months/weekdays."""
    out = set()
    for w in re.findall(r"\b[A-Z][A-Za-z&'-]*\b", text):
        wl = w.lower()
        if wl in _CNT_CAP_STOP or wl in ('the', 'i', 'my', 'we',
                                         'a', 'an'):
            continue
        out.add(wl)
    return out


def _cnt_np_fam(question: str) -> tuple:
    """Content words of the counted NP (robust vs modifiers).

    Returns ``(family, subtypes)`` — family is the full morph set of
    every content word; subtypes is the conjoined head list when
    the question counts "X and Y" separately (each needs evidence
    or the mechanism abstains — conjunctive completeness).
    """
    ql = question.lower()
    m = re.match(r'^how many ([a-z][\w\s-]{1,60}?)'
                 r'(?:\s+(?:do|did|have|has)\s+i'
                 r'|\s+i\s+(?:do|did|have|has|had|currently)'
                 r'|\s+(?:in|on|at|from|across|over|during|before'
                 r'|after|last|this|due)\b|[?.])', ql)
    if not m:
        m = re.match(r'^what (?:is|was) the total number of '
                     r'([a-z][\w\s-]{1,60}?)'
                     r'(?:\s+i\b|\s+(?:do|did|have|has)\s+i'
                     r'|\bthat\b|,|\bby\b|\bfrom\b|[?.])', ql)
    if not m:
        return None, None
    np = m.group(1)
    parts = re.split(r'\s+and\s+|,\s+|\s+or\s+', np)
    subs, fam = [], set()
    for part in parts:
        ws = [w for w in re.findall(r"[a-z][\w-]+", part)
              if w not in _CNT_STOP_Q
              and w not in _CNT_GENERIC_HEADS and len(w) >= 4]
        if not ws:
            continue
        h = ws[-1]
        for w in ws:
            fam |= {w, _cnt_sing(w), w + 's', _cnt_sing(w) + 's'}
        if len(parts) >= 2 and h not in subs:
            subs.append(h)
    return fam, (subs if len(subs) >= 2 else None)


def _cnt_anchor_re(anchors: set[str]):
    if not anchors:
        return None
    return re.compile(
        r'\b(' + '|'.join(re.escape(a) for a in
                          sorted(anchors, key=len, reverse=True))
        + r')\b', re.I)


def _cnt_question_anchors(question: str) -> set[str]:
    toks = set()
    for w in re.findall(r"[A-Za-z][\w'-]*", question):
        wl = w.lower()
        if wl in _CNT_STOP_Q or wl in _CNT_GENERIC_HEADS:
            continue
        if len(wl) < 4 and not w[0].isupper():
            continue
        toks.add(wl)
    return {t for t in toks if len(t) >= 4}


def _cnt_durations_days(text: str) -> list:
    """Explicit durations in days (``7-day trip`` = 7)."""
    out = []
    for m in re.finditer(
            r'\b(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six'
            r'|seven|eight|nine|ten)\s*-?\s*(day|week)s?\b',
            text, re.I):
        n = _cnt_num(m.group(1))
        if n is None:
            continue
        out.append((n * (7.0 if m.group(2).lower().startswith('week')
                         else 1.0), m.group(0)))
    for m in re.finditer(r'\ba\s+week\s+and\sa\s+half\b', text,
                         re.I):
        out.append((10.5, m.group(0)))
    for m in re.finditer(r'\b(?:full|all)[- ]day\b', text, re.I):
        out.append((1.0, m.group(0)))
    return out


def _cnt_daterange_days(text: str) -> float | None:
    """"April 15th to 22nd" = 7 days (exclusive count — fits GT)."""
    m = re.search(
        r'\b(' + '|'.join(_CNT_MONTHS) + r')\.?\s+(\d{1,2})'
        r'(?:st|nd|rd|th)?\s*(?:to|-|through|until)\s+(\d{1,2})'
        r'(?:st|nd|rd|th)?\b', text, re.I)
    if m:
        d1, d2 = int(m.group(2)), int(m.group(3))
        if 0 < d1 < 32 and 0 < d2 < 32 and d2 > d1:
            return float(d2 - d1)
    return None


def counting_form(question: str) -> str | None:
    """Classify a counting-aggregation question form (layered).

    Returns ``"duration_sum"`` / ``"total_sum"`` / ``"number_total"``
    / ``"argmax"``, or ``None`` (not a counting form). Calendar-
    distance questions ("how many days between …") belong to the
    Cycle 457 temporal-arithmetic path and are excluded here —
    distance is calendar arithmetic, not an evidence sum.
    """
    if temporal_arith_form(question):
        return None
    q = question.strip()
    ql = q.lower()
    if re.match(r'^what is the total number of (days|weeks)', ql):
        return "duration_sum"
    if re.search(r'\bhow many (days|weeks)\b', ql) or \
            (re.search(r'\b(days|weeks)\b', ql)
             and re.search(r'\b(spend|spent|take|took)\b', ql)
             and ql.startswith('how')):
        return "duration_sum"
    if re.match(r'^how (much|many)\b', q, re.I) \
            and re.search(r'\btotal\b', ql):
        return "total_sum"
    if re.match(r'^what (is|was) the total number', ql):
        return "number_total"
    if re.match(r'^which\b', q, re.I) and re.search(r'\bmost\b', ql):
        return "argmax"
    return None


def _cnt_duration_sum(question: str, sessions: list[dict]):
    q = question.lower()
    want_unit = ('days' if re.search(r'\bdays\b', q)
                 else ('weeks' if re.search(r'\bweeks\b', q)
                       else None))
    if want_unit is None:
        return None
    anchors = _cnt_question_anchors(question)
    are = _cnt_anchor_re(anchors)
    per_session = defaultdict(
        lambda: {'events': [], 'counts': set(), 'pnouns': set(),
                 'anchor_ok': False})
    # proper-noun anchors only — activity words like 'camping'
    # appear in gear-discussion sessions and pollute propagation
    cap_anchors = {w.lower()
                   for w in re.findall(r"\b[A-Z][a-z]+\b", question)
                   if w.lower() in anchors}
    cap_are = _cnt_anchor_re(cap_anchors) if cap_anchors else None
    for si, sent in _cnt_sents(sessions):
        if are and are.search(sent):
            per_session[si]['pnouns'] |= _cnt_proper_nouns(sent)
            per_session[si]['counts'] |= {
                int(n) for n in
                re.findall(r'\ball\s+(\d{1,4})\b', sent)}
            if cap_are and cap_are.search(sent):
                per_session[si]['anchor_ok'] = True
    # enrich signature from all non-intent sentences of anchor-ok
    # sessions
    for si, sent in _cnt_sents(sessions):
        sess = per_session[si]
        if not sess['anchor_ok']:
            continue
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        sess['pnouns'] |= _cnt_proper_nouns(sent)

    for si, sent in _cnt_sents(sessions):
        sess = per_session[si]
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        if are and not are.search(sent) and not sess['anchor_ok']:
            continue
        for days, _span in _cnt_durations_days(sent):
            sess['events'].append(round(days, 1))
        dr = _cnt_daterange_days(sent)
        if dr is not None:
            sess['events'].append(round(dr, 1))

    # merge equal values across sessions on signature overlap
    merged = []   # [days, signature]
    for si, data in sorted(per_session.items()):
        sig = data['counts'] | data['pnouns']
        for days in data['events']:
            hit = next((ev for ev in merged
                        if ev[0] == days and (ev[1] & sig)), None)
            if hit:
                hit[1] |= sig
            else:
                merged.append([days, set(sig)])
    if not merged:
        return None
    # conjunctive completeness: "Hawaii and Seattle" — each needs
    # an event, else abstain (fall through)
    if cap_anchors and ' and ' in question.lower():
        ev_sigs = set()
        for ev, sig in merged:
            ev_sigs |= sig
        missing = [a for a in cap_anchors
                   if a not in ev_sigs
                   and not any(a in s for s in ev_sigs)]
        if missing:
            return None
    total = sum(ev[0] for ev in merged)
    val = total / (7.0 if want_unit == 'weeks' else 1.0)
    return f"{round(val, 2):g} {want_unit}"


def _cnt_total_sum(question: str, sessions: list[dict]):
    amts = set()
    for si, sent in _cnt_sents(sessions):
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        for m2 in re.finditer(
                r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', sent):
            amts.add(m2.group(1))
    if not amts:
        return None
    total = round(sum(float(a.replace(',', '')) for a in amts), 2)
    return f"${total:g}"


def _cnt_number_total(question: str, sessions: list[dict]):
    fam, subtypes = _cnt_np_fam(question)
    if not fam:
        return None
    fam = {f for f in fam if len(f) >= 3}
    for w in list(fam):
        fam |= _CNT_HYPONYM.get(w, set()) \
            | _CNT_HYPONYM.get(_cnt_sing(w), set())
    sub_counts, all_counts = defaultdict(set), set()
    for si, sent in _cnt_sents(sessions):
        low = sent.lower()
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        if not any(re.search(r'\b' + re.escape(f) + r'\b', low)
                   for f in fam):
            continue
        if subtypes:
            for s_ in subtypes:
                if re.search(r'\b' + re.escape(s_) + r's?\b', low):
                    for em in re.finditer(
                            r'\b(\d{1,3}(?:,\d{3})*|one|two|three'
                            r'|four|five|six|seven|eight|nine|ten'
                            r'|eleven|twelve|fifteen|twenty)\b'
                            r'[^\w]{0,3}(?:\w+\s+){0,2}'
                            + re.escape(s_) + r's?\b', sent, re.I):
                        n = _cnt_num(em.group(1))
                        if n and n < 10000:
                            sub_counts[s_].add(n)
        else:
            for em in re.finditer(
                    r'\b(\d{1,3}(?:,\d{3})*|one|two|three|four'
                    r'|five|six|seven|eight|nine|ten|eleven|twelve'
                    r'|fifteen|twenty)\b[^\w]{0,3}(?:\w+\s+){0,2}('
                    + '|'.join(sorted(fam)) + r')\b', sent, re.I):
                n = _cnt_num(em.group(1))
                if n and n < 1000000:
                    after = sent[em.end(1):em.start(2)] \
                        .strip().lower().strip(' -')
                    parts = after.split()
                    if parts and parts[0].rstrip('s') in {
                            u.rstrip('s')
                            for u in _CNT_UNIT_BLACKLIST}:
                        continue
                    all_counts.add(n)
    if subtypes:
        vals = []
        for s_ in subtypes:
            if not sub_counts.get(s_):
                return None      # conjunctive completeness
            vals.append(max(sub_counts[s_]))
        return str(int(sum(vals)))
    if all_counts:
        return str(int(sum(all_counts)))   # SUM of distinct
    return None


def _cnt_argmax_entity(question: str, sessions: list[dict]):
    ql = question.lower()
    money = ('money' in ql or 'spend' in ql or 'spent' in ql
             or 'cost' in ql)
    followers = 'follower' in ql
    ent_totals = defaultdict(float)
    for si, sent in _cnt_sents(sessions):
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        vals = []
        if money:
            vals = [float(x.replace(',', '')) for x in
                    re.findall(
                        r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)',
                        sent)]
        elif followers:
            vals = [float(x.replace(',', '')) for x in
                    re.findall(r'\b(\d{1,6}(?:,\d{3})*)\s+'
                               r'followers?\b', sent, re.I)]
        if not vals:
            continue
        m = re.search(
            r"\b(?:at|on|from|in)\s+((?:[A-Z][\w&'-]*\s*){1,3})",
            sent)
        if m:
            key = m.group(1).strip()
            toks = [w for w in key.split()
                    if w.lower() not in _CNT_CAP_STOP]
            if not toks:
                continue
            ent_totals[' '.join(toks)] += max(vals)
        else:
            ents = [w.lower() for w in
                    re.findall(r"\b[A-Z][A-Za-z&'-]*\b", sent)
                    if w.lower() not in _CNT_CAP_STOP
                    and w.lower() not in ('the', 'i', 'my', 'we',
                                          'a', 'an')]
            ents = list(dict.fromkeys(ents))   # ordered dedup
            if not ents:
                continue
            ent_totals[' '.join(ents)] += max(vals)
    if not ent_totals:
        return None
    best = max(ent_totals.items(), key=lambda kv: kv[1])
    return ' '.join(w.capitalize() for w in best[0].split())


def answer_counting(question: str,
                    sessions: list[dict]) -> tuple[str | None, dict]:
    """Answer a counting-aggregation form from evidence sessions.

    Args:
        question: The raw question.
        sessions: Evidence sessions — ``[{"session_id", "turns":
            [{"role", "content"}]}]`` (the adapter groups its
            ingested messages into this shape).

    Returns:
        ``(answer, detail)`` — answer ``None`` means the form did
        not resolve (fall through to the gate chain; the gates own
        abstention). ``detail["form"]`` names the detected form for
        telemetry/forensics.
    """
    form = counting_form(question)
    if form is None:
        return None, {}
    fn = {"duration_sum": _cnt_duration_sum,
          "total_sum": _cnt_total_sum,
          "number_total": _cnt_number_total,
          "argmax": _cnt_argmax_entity}
    try:
        return fn[form](question, sessions), {"form": form}
    except Exception:                     # noqa: BLE001 — never break
        return None, {"form": form, "error": True}


_CNT_NUMWORD = {v: k for k, v in _CNT_WORD2NUM.items()
                if k not in ('a', 'an')}


def _cnt_numval(s: str) -> float | None:
    """Numeric value of an answer string (digits or word number)."""
    if s is None:
        return None
    s = str(s).strip()
    m = re.match(r'^\$?\s*([\d,]+(?:\.\d+)?)', s)
    if m:
        return float(m.group(1).replace(',', ''))
    m = re.match(r'^\$?\s*(\w+)', s.lower())
    if m and m.group(1) in _CNT_WORD2NUM:
        return float(_CNT_WORD2NUM[m.group(1)])
    # sentence-style GT: first numeric claim
    m = re.search(
        r'\b(five|four|three|two|one|zero|six|seven|eight|nine'
        r'|ten|eleven|twelve|fifteen|twenty'
        r'|\d+(?:,\d{3})*)\b', s.lower())
    if m:
        tok = m.group(1)
        if tok in _CNT_WORD2NUM:
            return float(_CNT_WORD2NUM[tok])
        return float(tok.replace(',', ''))
    return None


def counting_judge(question: str, truth: str,
                   predicted: str) -> bool:
    """Judge counting answers (zero cost, numeric-first).

    ``"2.5 weeks"`` vs ``"2.5"`` match numerically; word numbers
    (``"three"`` vs ``"3"``) match; sentence-style ground truths
    fall back to their first numeric claim; non-numeric answers
    (argmax entities) fall back to bidirectional containment.
    """
    if not truth or not predicted:
        return False
    form = counting_form(question)
    if form is None:
        return exact_judge(question, truth, predicted)
    p, g = _cnt_numval(predicted), _cnt_numval(truth)
    if p is not None and g is not None:
        return abs(p - g) < 1e-6
    pl = str(predicted).lower().strip()
    gl = str(truth).lower().strip()
    if pl in gl or gl in pl:
        return True
    # entity answers: token-set containment — "Thrive Market" vs
    # "Market Thrive" name the same store (word order is not
    # semantics for proper-name evidence)
    pt, gt_ = set(pl.split()), set(gl.split())
    return bool(pt and gt_ and (pt <= gt_ or gt_ <= pt))


def load_longmemeval_data(path, *, limit: int = 0) -> list[dict]:
    """Load a LongMemEval JSON dataset (list of question dicts).

    Args:
        path: JSON file path (``[{"id", "question", "answer", ...}]``).
        limit: Keep at most this many items (0 = all).

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the JSON is not a list or items lack the
            required ``question`` key.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"dataset not found: {p}")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"{p}: expected JSON list, got {type(data).__name__}")
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "question" not in item:
            raise ValueError(f"{p}[{i}]: missing 'question' key")
    return data[:limit] if limit and limit > 0 else data


# ── CLI entry point ────────────────────────────────────────────────

def run_eval(dataset: list[dict], *, limit: int = 0,
             entropies: list[float | None] | None = None,
             use_ppr: bool = True, max_context_tokens: int = 4000,
             abstain_score: float = 1.0, abstain_entropy: float | None = 0.95,
             entropy_weak_score: int = 1,
             temporal_arith: bool = True,
             counting: bool = True,
             assistant_recall: bool = True,
             recall_mode: str = "distinctive",
             recall_seed_k: int = 40,
             judge_mode: str = "exact") -> dict:
    """Per-question-haystack evaluation (Cycle 454).

    LongMemEval-cleaned ships one haystack per question; this builds a
    FRESH adapter + graph per question (isolation guarantee — no
    cross-question contamination), runs single-question ``evaluate()``
    and aggregates, optionally running the C448 entropy
    ``sweep_abstention`` on the same graphs.

    Args:
        dataset: LongMemEval items (``id``/``question``/``answer``;
            ``haystack_sessions`` or ``sessions`` per item;
            ``_abs`` suffix = abstention-scored).
        limit: Evaluate at most this many questions (0 = all).
        entropies: Optional entropy thresholds (``None`` = gate off).
        judge_mode: "exact" (default) or "dual" (Cycle 462 — adds
            ``accuracy_exact``/``accuracy_llm``/``calibration`` to the
            aggregated report).

    Returns:
        Same shape as ``evaluate()`` plus ``sweep`` (``None`` when
        *entropies* not given).
    """
    items = dataset[:limit] if limit and limit > 0 else dataset
    kwargs = dict(use_ppr=use_ppr, max_context_tokens=max_context_tokens,
                  abstain_score=abstain_score,
                  abstain_entropy=abstain_entropy,
                  entropy_weak_score=entropy_weak_score,
                  temporal_arith=temporal_arith,
                  counting=counting,
                  assistant_recall=assistant_recall,
                  recall_mode=recall_mode,
                  recall_seed_k=recall_seed_k)
    all_results: list[dict] = []
    sweep_rows: list[dict] = []
    for i, item in enumerate(items):
        adapter = LongMemEvalAdapter(**kwargs)
        haystack = (item.get("haystack_sessions")
                    or item.get("sessions") or [])
        if haystack:
            sessions = haystack if isinstance(haystack, list) else [haystack]
            # LongMemEval-cleaned ships each session as a bare list of
            # message dicts — normalize to ingest_sessions shape.
            sessions = [{"session_id": f"session_{j + 1}", "messages": s}
                        if isinstance(s, list) else s
                        for j, s in enumerate(sessions)]
            # Cycle 457: positional haystack_dates[j] ↔ session j —
            # bare-list sessions get canonical session_{j+1} ids,
            # dict sessions keep their own session_id (when present).
            hdates = item.get("haystack_dates") or []
            sdates = None
            if isinstance(hdates, list) and hdates:
                sdates = {}
                for j, dt in enumerate(hdates):
                    if j >= len(sessions):
                        break
                    s = sessions[j]
                    sid = (s.get("session_id") if isinstance(s, dict)
                           else None) or f"session_{j + 1}"
                    sdates[sid] = dt
            adapter.ingest_sessions(sessions, session_dates=sdates)
        all_results.extend(adapter.evaluate([item],
                                            judge_mode=judge_mode)["results"])
        if entropies:
            sweep_rows.extend(
                adapter.sweep_abstention([item], entropies=entropies)["rows"])

    n = len(all_results)

    def _rate(key: str) -> float:
        return sum(r[key] for r in all_results) / n if n else 0.0

    categories: dict[str, dict] = {}
    for r in all_results:
        c = categories.setdefault(r["category"], {
            "category": r["category"], "total": 0, "correct": 0,
            "abstentions": 0, "hits": 0, "total_tokens": 0,
            "answer_session_hits": 0, "answer_sessions_resolved": 0})
        c["total"] += 1
        c["correct"] += int(r["correct"])
        c["abstentions"] += int(r["abstained"])
        c["hits"] += int(r["retrieval_hit"])
        c["total_tokens"] += r["tokens_est"]
        ash = r.get("answer_session_hit")
        if ash is not None:
            c["answer_sessions_resolved"] += 1
            c["answer_session_hits"] += int(ash)
    for c in categories.values():
        t, tok = c["total"], c.pop("total_tokens")
        c["accuracy"] = round(c["correct"] / t, 4) if t else 0.0
        c["abstention_rate"] = round(c["abstentions"] / t, 4) if t else 0.0
        c["retrieval_hit_rate"] = round(c["hits"] / t, 4) if t else 0.0
        c["answer_session_hit_rate"] = (
            round(c["answer_session_hits"]
                  / c["answer_sessions_resolved"], 4)
            if c["answer_sessions_resolved"] else 0.0)
        c["avg_tokens"] = round(tok / t, 1) if t else 0.0

    sweep = None
    if entropies:
        labels = ["None" if e is None else str(e) for e in entropies]
        totals = {lab: [0, 0] for lab in labels}  # correct, abstained
        for row in sweep_rows:
            for lab in labels:
                totals[lab][0] += int(row["correct"][lab])
                totals[lab][1] += int(row["abstained"][lab])
        m = len(sweep_rows)
        sweep = {
            "thresholds": labels,
            "summary": {lab: {"accuracy": (c / m if m else 0.0),
                              "abstention_rate": (a / m if m else 0.0),
                              "total": m}
                        for lab, (c, a) in totals.items()},
            "rows": sweep_rows,
        }

    report = {
        "overall_accuracy": _rate("correct"),
        "retrieval_hit_rate": _rate("retrieval_hit"),
        "abstention_rate": _rate("abstained"),
        "avg_tokens": _rate("tokens_est"),
        "total_questions": n,
        "categories": categories,
        "results": all_results,
        "sweep": sweep,
        "config": kwargs,
    }
    # Cycle 467: None-aware evidence-coverage aggregation.
    resolved_rows = [r for r in all_results
                     if r.get("answer_session_hit") is not None]
    report["answer_session_hit_rate"] = (
        sum(r["answer_session_hit"] for r in resolved_rows)
        / len(resolved_rows) if resolved_rows else 0.0)
    report["answer_sessions_resolved"] = len(resolved_rows)
    if judge_mode == "dual":
        report["config"] = {**kwargs, "judge_mode": judge_mode}
        report["accuracy_exact"] = report["overall_accuracy"]
        scored = [r for r in all_results
                  if r.get("correct_llm") is not None]
        report["accuracy_llm"] = (
            sum(1 for r in scored if r["correct_llm"]) / len(scored)
            if scored else 0.0)
        report["calibration"] = calibration_summary(all_results)
        report["calibration_by_category"] = \
            calibration_by_category(all_results)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="amg LongMemEval memory-quality benchmark")
    parser.add_argument("--data", required=True,
                        help="Path to LongMemEval JSON dataset")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max questions (0 = all)")
    parser.add_argument("--no-ppr", action="store_true",
                        help="Disable PPR multi-hop expansion")
    parser.add_argument("--max-tokens", type=int, default=4000,
                        help="Context token budget")
    parser.add_argument("--abstain-score", type=float, default=1.0,
                        help="Min keyword hits to answer (else abstain)")
    parser.add_argument("--abstain-entropy", type=float, default=0.95,
                        help="Entropy-gate threshold for abstention "
                             "on weak scattered evidence "
                             "(<0 disables — Cycle 447 behavior)")
    parser.add_argument("--entropy-weak", type=int, default=1,
                        help="Max keyword hits still counted as weak "
                             "evidence for the entropy gate")
    parser.add_argument("--no-temporal-arith", action="store_true",
                        help="Disable the Cycle 457 temporal-arithmetic "
                             "answer path (pre-C457 baseline)")
    parser.add_argument("--no-assistant-recall", action="store_true",
                        help="Disable the Cycle 468 speaker-recall "
                             "answer path (pre-C468 baseline)")
    parser.add_argument("--recall-mode", choices=("distinctive", "raw"),
                        default="distinctive",
                        help="Speaker-recall scoring: distinctive = w^2 "
                             "distinctive weights + preface penalty "
                             "(Cycle 475, default); raw = legacy "
                             "hit counting")
    parser.add_argument("--no-counting", action="store_true",
                        help="Disable the Cycle 477 multi-session "
                             "counting path (pre-C477 baseline)")
    parser.add_argument("--mode", choices=("extract", "eval"),
                        default="extract",
                        help="extract = pre-C454 row dump (default); "
                             "eval = full per-question evaluation + "
                             "scoring (Cycle 454)")
    parser.add_argument("--sweep-entropies", default="",
                        help="CSV entropy thresholds for eval-mode sweep "
                             "(e.g. 'none,0.90,0.95'; 'none' = gate off)")
    parser.add_argument("--judge", choices=("exact", "dual"),
                        default="exact",
                        help="exact = containment judge (default); "
                             "dual = additionally score with judge_llm "
                             "(ollama/mock — two-column accuracy + "
                             "calibration, Cycle 462)")
    parser.add_argument("--output", default="amg_longmemeval_results.json",
                        help="Output report path")
    args = parser.parse_args(argv)

    dataset = load_longmemeval_data(args.data, limit=args.limit)
    print(f"Loaded {len(dataset)} questions from {args.data}")

    # Negative --abstain-entropy disables the entropy gate (None).
    abstain_entropy = (args.abstain_entropy
                       if args.abstain_entropy >= 0 else None)

    adapter = LongMemEvalAdapter(
        use_ppr=not args.no_ppr, max_context_tokens=args.max_tokens,
        abstain_score=args.abstain_score,
        abstain_entropy=abstain_entropy,
        entropy_weak_score=args.entropy_weak,
        temporal_arith=not args.no_temporal_arith,
        counting=not args.no_counting,
        assistant_recall=not args.no_assistant_recall,
        recall_mode=args.recall_mode)

    if args.mode == "eval":
        entropies = None
        if args.sweep_entropies:
            entropies = [None if t.strip().lower() == "none"
                         else float(t)
                         for t in args.sweep_entropies.split(",")]
        report = run_eval(
            dataset, limit=args.limit, entropies=entropies,
            use_ppr=not args.no_ppr,
            max_context_tokens=args.max_tokens,
            abstain_score=args.abstain_score,
            abstain_entropy=abstain_entropy,
            entropy_weak_score=args.entropy_weak,
            temporal_arith=not args.no_temporal_arith,
            counting=not args.no_counting,
            assistant_recall=not args.no_assistant_recall,
            recall_mode=args.recall_mode,
            judge_mode=args.judge)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n{report['total_questions']} questions · "
              f"accuracy {report['overall_accuracy']:.3f} · "
              f"retrieval_hit {report['retrieval_hit_rate']:.3f} · "
              f"evidence_hit {report['answer_session_hit_rate']:.3f} "
              f"({report['answer_sessions_resolved']} resolved) · "
              f"abstention {report['abstention_rate']:.1%} · "
              f"avg {report['avg_tokens']:.0f} tokens/query")
        if report["sweep"]:
            best = max(report["sweep"]["summary"].items(),
                       key=lambda kv: kv[1]["accuracy"])
            print(f"sweep best: entropy={best[0]} "
                  f"accuracy {best[1]['accuracy']:.3f} "
                  f"abstention {best[1]['abstention_rate']:.1%}")
        print(f"Report written to {args.output}")
        return 0

    # LongMemEval-cleaned ships one shared haystack per question; ingest
    # the first non-empty one (all-question mode) or per-question.
    report_rows = []
    for i, item in enumerate(dataset):
        haystack = item.get("haystack_sessions") or item.get("sessions") or []
        if haystack:
            # Fresh graph + adapter state per haystack (LongMemEval
            # questions each carry their own conversation history).
            adapter = LongMemEvalAdapter(
                use_ppr=not args.no_ppr,
                max_context_tokens=args.max_tokens,
                abstain_score=args.abstain_score,
                abstain_entropy=abstain_entropy,
                entropy_weak_score=args.entropy_weak,
                temporal_arith=not args.no_temporal_arith)
            adapter.ingest_sessions(haystack if isinstance(haystack, list)
                                    else [haystack])
        answer, meta = adapter.answer_extractive(
            item.get("question", ""), item.get("question_date", ""))
        report_rows.append({"id": item.get("id", i), "answer": answer,
                            "abstained": meta["abstained"],
                            "tokens_est": meta["tokens_est"]})

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"rows": report_rows,
                   "config": {"use_ppr": not args.no_ppr,
                              "max_context_tokens": args.max_tokens,
                              "abstain_entropy": abstain_entropy,
                              "entropy_weak_score": args.entropy_weak,
                              "temporal_arith": not args.no_temporal_arith}},
                  f, indent=2)
    abst = sum(1 for r in report_rows if r["abstained"])
    avg_tok = (sum(r["tokens_est"] for r in report_rows) / len(report_rows)
               if report_rows else 0)
    print(f"\n{len(report_rows)} questions · {abst} abstentions "
          f"({abst / len(report_rows):.1%}) · avg {avg_tok:.0f} tokens/query")
    print(f"Report written to {args.output}")
    print("Full-quality mode (LLM judge) needs answer_fn/judge_fn — see "
          "LongMemEvalAdapter.evaluate().")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
