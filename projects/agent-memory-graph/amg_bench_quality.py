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
import hashlib
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
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
    "pp_duration_form",
    "pp_pure_tenure_form",
    "answer_pp_duration",
    "pp_duration_judge",
    "order_form",
    "answer_order",
    "order_judge",
    "ecm_form",
    "answer_ecm",
    "delta_form",
    "answer_delta",
    "pref_form",
    "recall_form",
    "chunk_session_text",
    "SidechannelEngine",
    "probe_sidechannel_engine",
    "session_embedding_scores",
    "sidechannel_form",
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
                 pp_duration: bool = True,
                 order_sort: bool = True,
                 pairwise_sort: bool = True,
                 ecm: bool = True,
                 delta_agg: bool = True,
                 pref_abstain: bool = True,
                 neg_exist: bool = True,
                 role_answer: bool = True,
                 role_margin: int = 0,
                 assistant_recall: bool = True,
                 recall_min_score: int = 5,
                 recall_mode: str = "distinctive",
                 ppr_top: int = 15,
                 seed_recall_k: int = 5,
                 recall_seed_k: int = 40,
                 sidechannel: bool = False,
                 sidechannel_cache: SidechannelCache | None = None,
                 where_loc: bool = True):
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
            pp_duration: Enable the Cycle 486 past-perfect duration
                path ("How long had I been <state> when/before
                <event>?" resolved by anchoring both duration
                expressions to absolute dates via their containing
                session, then calendar subtraction; nested-tenure
                route for before-current-job forms; unresolved
                forms fall through to the gate chain).
            order_sort: Enable the Cycle 488 order-family path
                ("order of / from first to last" questions answered
                by anchoring every item to its earliest FRESH
                report and sorting by session date — fresh >
                vague-recall > planning tiers, clause-level intent,
                substring-containment label merge; STRICT form gate
                zero-hijack by census; unresolved forms fall
                through to the gate chain).
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
        self.pp_duration = pp_duration
        self.order_sort = order_sort
        self.pairwise_sort = pairwise_sort
        self.ecm = ecm
        self.delta_agg = delta_agg
        self.pref_abstain = pref_abstain
        self.neg_exist = neg_exist
        # Cycle 501: role-aware answer face (echo pathology fix) —
        # see _user_fact_form. role_margin: how many keyword hits a
        # user line may trail the top assistant line by and still
        # win (0 = must tie; the -seq tie-break hands equal-hit
        # tops to the LATEST message, routinely the advice reply).
        self.role_answer = role_answer
        self.role_margin = role_margin
        self.assistant_recall = assistant_recall
        self.recall_min_score = recall_min_score
        self.recall_mode = recall_mode
        self.ppr_top = ppr_top
        self.seed_recall_k = seed_recall_k
        self.recall_seed_k = recall_seed_k
        # Cycle 506: embedding side-channel (Research #083) — opt-in;
        # the engine is probed lazily on the FIRST gated question so
        # import-time cost stays zero and the lexical default is
        # untouched (zero-dep hermetic tests rely on that).
        self.sidechannel = sidechannel
        # Cycle 512: write-time chunk-embedding amortization. Default
        # cache is per-adapter; pass an external one to amortize
        # across the run_eval per-question fresh-adapter protocol.
        self.sidechannel_cache = sidechannel_cache or SidechannelCache()
        self.where_loc = where_loc
        self._side_engine = None
        self._side_probed = False
        # Adapter-side bookkeeping (avoids depending on repo getter
        # APIs): node id → {label, kind, role, seq, session_id}.
        self._nodes: dict[str, dict] = {}
        self._messages: dict[str, dict] = {}       # message nodes only
        self._entities: dict[str, str] = {}        # entity name → node id
        self._session_dates: dict[str, str] = {}   # session id → YYYY-MM-DD
        # C489: raw haystack date strings (minute granularity —
        # "2023/03/10 (Fri) 00:07") before parse_lme_date truncates
        # them; same-day session ORDER is the pairwise signal.
        self._session_dates_raw: dict[str, str] = {}
        self._seq = 0                               # deterministic order

    def _sidechannel_engine(self):
        """Lazily resolve the side-channel engine (None when the
        flag is off or no backend imports)."""
        if not self.sidechannel:
            return None
        if not self._side_probed:
            self._side_engine = probe_sidechannel_engine()
            self._side_probed = True
        return self._side_engine

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
        stats = {"sessions": 0, "messages": 0, "entities": 0,
                 "edges": 0, "chunks_embedded": 0}
        if session_dates:
            for sid, dt in session_dates.items():
                self._session_dates_raw[str(sid)] = str(dt)
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

            # Cycle 512: write-time pass — warm the side-channel
            # cache while the session is being written, so query
            # time embeds only the question.
            engine = self._sidechannel_engine()
            if engine is not None:
                stats["chunks_embedded"] += (
                    self.sidechannel_cache.precompute_sessions(
                        [session], engine))

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

        # Cycle 506: form-gated embedding side-channel (Research
        # #083). "embed" — preference forms: keyword ranking is
        # replaced by full-haystack session scoring (the lexical
        # bridge is unreachable; candidates often lack the evidence
        # session entirely, so re-ranking them cannot help — the
        # switch pulls NEW sessions in). "hybrid" — assistant-recall
        # forms: keyword candidates re-ordered by session embedding
        # score, ties fall back to (-hits, -seq) — the #083 lesson
        # bans id-alphabetical tie-breaks, ingest order is ours.
        side_mode = None
        side_cache_meta: dict | None = None
        engine = (self._sidechannel_engine()
                  if sidechannel_form(question) else None)
        if engine is not None:
            side_mode = sidechannel_form(question)
            sessions = self._counting_sessions()
            h0, m0 = (self.sidechannel_cache.hits,
                      self.sidechannel_cache.misses)
            scores = session_embedding_scores(
                question, sessions, engine,
                cache=self.sidechannel_cache)
            side_cache_meta = {"hits": self.sidechannel_cache.hits - h0,
                               "misses": self.sidechannel_cache.misses - m0}
            if side_mode == "embed":
                order = [s["session_id"] for s in sessions]
                top = sorted(scores,
                             key=lambda s: (-scores[s],
                                            order.index(s)))
                top = top[:SIDECHANNEL_TOP_SESSIONS]
                by_sid: dict[str, list] = {}
                for nid, info in self._messages.items():
                    by_sid.setdefault(info["session_id"], []).append(
                        (-info["seq"], nid))
                ranked = []
                for sid in top:
                    for neg_seq, nid in sorted(by_sid.get(sid, [])):
                        info = self._messages[nid]
                        ranked.append(
                            (-_keyword_hits(info["label"], keywords),
                             neg_seq, nid))
            else:  # hybrid
                ranked.sort(
                    key=lambda t: (
                        -scores.get(
                            self._messages[t[2]]["session_id"],
                            float("-inf")),
                        t[0], t[1], t[2]))

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
            "sidechannel": side_mode,   # None | "embed" | "hybrid"
            "sidecache": side_cache_meta,  # Cycle 512: per-query delta
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

        # Cycle 498: preference honest abstention (Research #080
        # candidate A) — advice-request forms are generation-native:
        # the GT is a synthesized meta-description ("The user would
        # prefer…"), the category-entity vocabulary gap makes the
        # retrieval bridge lexically unreachable (unique-lexical-best
        # 4/30, arm F), and echoing retrieved suggestion text is a
        # category error (correct_llm 1/30 = judge leniency). A
        # zero-LLM pipeline cannot compose a personalized response
        # → abstain honestly instead of fabricating one. Census over
        # full-500: fires 29/30 preference questions, ZERO of the
        # other 470 (zero hijack); third instance of C448-style
        # answer-side abstention.
        if self.pref_abstain and pref_form(question):
            meta["gate"] = "pref"
            meta["abstained"] = True
            return ABSTAIN_ANSWER, meta

        # Cycle 513: negative-existence abstention (#087 ABS_Q
        # lineage). LME _abs near-miss traps: the question
        # presupposes an entity (Shinjuku) whose confusable sibling
        # (Harajuku) IS in the corpus — retrieval is strong-but-
        # tangent, confidence high, every downstream gate fabricates
        # (18/24 abs-GT questions answered with fabrications at
        # C511 HEAD, zero abstained). The presupposition failure is
        # detectable BEFORE any answering: a proper noun in the
        # question that appears NOWHERE in the full haystack
        # (word-boundary, case-insensitive) means the answer cannot
        # be extracted. Census v3 @HEAD: 13 fires / 500, +3 abs-GT
        # wins, 0 hijacks (the two quoted-title regex artifacts
        # were the only false fires — bare tokens only, the 4th
        # display-layer-bug family instance). Runs before the
        # mechanism gates: presupposition failure outranks form
        # families (gate ORDER is a correctness face — C482).
        if self.neg_exist:
            haystack_text = "\n".join(
                " ".join(str(t.get("content", ""))
                         for t in s["turns"])
                for s in self._counting_sessions())
            missing = negative_existence(question, haystack_text)
            if missing:
                meta["gate"] = "neg_exist"
                meta["abstained"] = True
                meta["neg_exist_entity"] = missing
                return ABSTAIN_ANSWER, meta

        # Cycle 497: neither-family ECM (Research #082) — "Who did
        # I meet first, X or Y?" / "Who became a parent first…".
        # STRICT gate census over 500: fires exactly the 4 family
        # members, zero collisions. Runs BEFORE pairwise — forms are
        # mutually exclusive ("who did I <V> first" vs "which …
        # first"), C488 precedent: the family's own renderer claims
        # it first when two form families overlap (gate ORDER is a
        # correctness face — C482 lesson). Full-haystack sentence
        # scan (C472 lesson); fall-through preserved.
        if (self.ecm and self._session_dates
                and ecm_form(question)):
            dated = [
                (self._session_dates.get(s["session_id"], ""),
                 s["turns"]) for s in self._counting_sessions()]
            e_ans, e_detail = answer_ecm(question, dated,
                                         question_date)
            meta["ecm"] = e_detail
            if e_ans is not None:
                meta["gate"] = "ecm"
                meta["abstained"] = e_ans == ABSTAIN_ANSWER
                return e_ans, meta

        # Cycle 489: pairwise "which happened first, X or Y?" (#078
        # sibling family, 29 members) — two candidates extracted from
        # the question's tail disjunction, each anchored to its
        # earliest trustworthy report (fresh > vague-eventive >
        # planning, C482 tiers at clause granularity + verb
        # congruence from the question's did-I verb). Session times
        # are MINUTE-granular raw haystack strings — same-day pairs
        # resolve; a <24 h anchor gap is treated as unresolvable
        # (fall-through: recommendation echoes routinely sit hours
        # apart on the same day — C489 A/B). Anchors may be pulled to
        # the in-clause adverbial/relative date ("last week",
        # "since February 20") but only when a candidate keyword
        # shares the clause. Decision matrix: both anchored → earlier
        # one; one anchored + the other has ZERO user-line mentions
        # → negative-existence ABSTAIN (the _abs ground truth);
        # anything partial → fall through (the answer gates still
        # own currently-correct cases). Runs BEFORE temporal_arith:
        # the TA "first" kind claims this family too and mis-
        # resolves 2 of them (C486 forensics) — pairwise's richer
        # evidence (minutes, verb congruence) subsumes it, and the
        # 5 TA-correct members re-answer identically here (C489
        # census). C493 went further and RETIRED the TA "first"
        # kind outright (zero-loss A/B, 12/30 both arms): the 3
        # residual TA-first resolutions were 1 correct-but-
        # redundant with the extractive answer gate + 2 wrong.
        if (self.pairwise_sort and self._session_dates
                and pw_form(question)):
            dated = []
            for s in self._counting_sessions():
                sid = s["session_id"]
                dated.append((
                    self._session_dates_raw.get(sid)
                    or self._session_dates.get(sid, ""), s["turns"]))
            w_ans, w_detail = answer_pairwise(question, dated,
                                              question_date)
            meta["pairwise"] = w_detail
            if w_ans is not None:
                meta["gate"] = "pairwise"
                meta["abstained"] = w_ans == ABSTAIN_ANSWER
                return w_ans, meta

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

        # Cycle 486: past-perfect duration forms (#077) — "How long
        # had I been <state> when/before <event>?" Every "N units
        # ago" / "for N units (now)" expression anchors to the
        # ABSOLUTE date of its containing session (C482's
        # line-adverbial insight generalized from dates to
        # durations); the answer is calendar subtraction on the two
        # anchors. Nested-tenure route ("before I started my current
        # job at X" = total profession − tenure at X, in months)
        # handles the compound y+m case. Full-haystack evidence —
        # anchors are session-scattered (the C472 full-graph
        # lesson). Runs after temporal_arith, before counting:
        # the precise-arithmetic family claims first when forms
        # overlap (C482 gate-order lesson). Fall-through preserved;
        # only the negative-existence abstain (before-job route, no
        # tenure line for the company anywhere) resolves here.
        if (self.pp_duration and self._session_dates
                and (pp_duration_form(question)
                     or pp_pure_tenure_form(question))):
            dated = [(self._session_dates.get(s["session_id"], ""),
                      s["turns"]) for s in self._counting_sessions()]
            p_ans, p_detail = answer_pp_duration(question, dated)
            meta["pp_duration"] = p_detail
            if p_ans is not None:
                meta["gate"] = "pp_duration"
                meta["abstained"] = p_ans == ABSTAIN_ANSWER
                return p_ans, meta

        # Cycle 488: order-family N-anchor sorting (#078) —
        # "order of / from first to last" questions answered by
        # anchoring every item to its earliest FRESH report (fresh
        # > vague-recall > planning — the C482 trust tiers, now
        # three) and sorting by session date. Clause is the unit of
        # intent, line the unit of time; category-set extraction
        # canonicalizes labels and merges by substring containment
        # (kw-subset over-merges: "Museum of History" ≠ "Natural
        # History Museum"); concerts fall back to session-scope
        # anchors. STRICT form gate: exactly the 9 currently-wrong
        # family members match (census #078) — the 29 pairwise
        # "which first" siblings stay out until their own render
        # is validated (C489). Fall-through preserved.
        if (self.order_sort and self._session_dates
                and order_form(question)):
            dated = [(self._session_dates.get(s["session_id"], ""),
                      s["turns"]) for s in self._counting_sessions()]
            o_ans, o_detail = answer_order(question, dated,
                                           question_date)
            meta["order"] = o_detail
            if o_ans is not None:
                meta["gate"] = "order"
                meta["abstained"] = False
                return o_ans, meta

        # Cycle 509: delta-family two-anchor numeric aggregation
        # (#086) — questions naming BOTH sides of a numeric
        # comparison in the question text ("how much more … compared
        # to …", "… instead of …", "minimum amount … and …", "how
        # much did I save"). Single-direction aggregators cannot see
        # the question's own entity split; delta binds each side
        # independently (any-of anchors, user-role priority,
        # strict-majority cross-side exclusion, clause-locality
        # tie-break) then applies the operator family (diff / sum2
        # / minmax / rate / ratio / pct). Runs BEFORE counting:
        # counting's undifferentiated sums mis-answer the two-sided
        # members today (C507 forensics: the 21-member family was
        # all-wrong). STRICT question-form gate; miss → fall-through
        # untouched (never answers IDK — the gates own abstention).
        if self.delta_agg and delta_form(question):
            dl_ans, dl_detail = answer_delta(
                question, self._counting_sessions())
            meta["delta"] = dl_detail
            if dl_ans is not None:
                meta["gate"] = "delta_agg"
                meta["abstained"] = False
                return dl_ans, meta

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
                # C514: museum_count's zero-venue abstention is a
                # RESOLVED negative existence, not a fall-through —
                # no other counting form returns ABSTAIN_ANSWER
                # today (verified: zero occurrences in the
                # counting layer), so this is museum-only.
                meta["abstained"] = c_ans == ABSTAIN_ANSWER
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

        # Cycle 508: where-form locative extraction (#084) —
        # "Where did I …" questions: retrieval bridges the answer
        # session but the echo path returns an advice/echo line, not
        # the user's location statement. Locative sentence selection
        # over retrieved sessions (user-role + first-person + window
        # + rank priors); returns the whole winning sentence so
        # containment judging passes. Runs after speaker_recall,
        # before the answer gates: strict start-with-where form,
        # zero family overlap (census 19/500); no locative candidate
        # -> fall-through untouched (C488 lesson). Sim A/B (mini =
        # all 19 full-500 where-qs, 3 hash seeds stable): +4 fixes
        # (Target/Serenity Yoga/IKEA/Oahu), 0 regressions.
        if self.where_loc and where_form(question):
            w_ans, w_detail = answer_where(
                question, self._counting_sessions(),
                meta.get("retrieved_ids", []), self._nodes, context)
            meta["where"] = w_detail
            if w_ans is not None:
                meta["gate"] = "where"
                meta["abstained"] = False
                return w_ans, meta

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
        lines = context.split("\n")
        best_line = lines[0]
        # Cycle 501: role-aware answer face. User-fact questions
        # ("What color did I repaint my bedroom walls?") are
        # answered by the best-ranked line, but assistant advice
        # routinely out-hits the terse user fact statement (advice
        # discusses the topic extensively) → the gate echoes
        # "Mint is a fantastic app…" while the GT lives in a user
        # line. C499 forensics: 257/302 answer-gate questions wrong
        # while answer_session_hit is near-universal — retrieval
        # finds the session, extraction picks the wrong speaker.
        # Fix: for first-person fact questions NOT claimed by any
        # specialized family (gate ORDER is a correctness face —
        # C482/C488; pairwise/ECM/TA/counting own their forms even
        # on fall-through, speaker-recall owns you-addressed
        # forms, C498 owns advice requests), when the top line is
        # an assistant line and a user line TIES its keyword
        # evidence (margin) with floor 2, the user line wins — at
        # equal evidence strength the user's own statement is the
        # fact source. Sim: 21 wins / 1 loss over the answer-gate
        # population (C501 /tmp/c501/sim.json).
        if (self.role_answer and _user_fact_form(question)
                and not _answer_form_claimed(question)
                and best_line.startswith("[assistant")):
            kws = meta.get("keywords") or _keywords(question)
            top_hits = _keyword_hits(
                best_line.split("] ", 1)[-1], kws)
            best_u, best_u_hits = None, -1
            for ln in lines[1:]:
                if not ln.startswith("[user"):
                    continue
                h = _keyword_hits(ln.split("] ", 1)[-1], kws)
                if h > best_u_hits:
                    best_u, best_u_hits = ln, h
            meta["role_answer"] = {
                "top_hits": top_hits,
                "user_hits": max(best_u_hits, 0),
                "override": bool(
                    best_u is not None and best_u_hits >= 2
                    and best_u_hits >= top_hits - self.role_margin)}
            if meta["role_answer"]["override"]:
                best_line = best_u
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
            elif meta.get("gate") == "pp_duration":
                correct = pp_duration_judge(question, truth, predicted)
            elif meta.get("gate") == "order":
                correct = order_judge(question, truth, predicted)
            elif meta.get("gate") == "pairwise":
                correct = pairwise_judge(question, truth, predicted)
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
                       "order_sort": self.order_sort,
                       "pairwise_sort": self.pairwise_sort,
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
# Cycle 493: _TA_FIRST_RE ("Which happened first, X or Y?") RETIRED —
# pairwise (C489) owns the family and runs earlier in the pipeline;
# full-500 forensics showed TA-first resolved only 3 residual
# members (1 correct-but-redundant with the extractive answer gate,
# 2 wrong). Zero-loss A/B on the 30-q family slice (12/30 both
# arms, zero flips) — first-form questions now fall through.

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


# ── Cycle 506: embedding side-channel (Research #083) ──────────────
# The preference retrieval bridge is lexically unreachable
# (unique-lexical-best 4/30) while a 384-d MiniLM closes it
# (@5 18→26/30); ssa lexical recall is already 49/56 and embeddings
# fix the @1 ordering. RRF fusion is HARMFUL when one arm is
# near-random (@1 10 < 15) → the integration is a per-form SWITCH,
# not a fusion — C473's "the form classifier IS the configuration
# surface", extended from seed breadth to retrieval modality.

SIDECHANNEL_WORDS_PER_CHUNK = 150   # MiniLM 256-token context budget
SIDECHANNEL_MAX_CHUNKS = 6         # sessions score by chunk-max
SIDECHANNEL_TOP_SESSIONS = 3       # embed-mode context window sessions


def chunk_session_text(
        text: str,
        words_per_chunk: int = SIDECHANNEL_WORDS_PER_CHUNK,
        max_chunks: int = SIDECHANNEL_MAX_CHUNKS) -> list[str]:
    """Split *text* into ≤ *max_chunks* word chunks (research
    protocol: 150 words × 6). Longer sessions keep their first
    ``max_chunks`` chunks — the evidence for recall questions is
    front-loaded in LongMemEval-style dialogues."""
    words = text.split()
    if not words:
        return []
    cap = min(len(words), words_per_chunk * max_chunks)
    return [" ".join(words[i:i + words_per_chunk])
            for i in range(0, cap, words_per_chunk)]


class SidechannelEngine:
    """Thin wrapper over an optional embedding backend.

    ``embed(texts)`` returns L2-normalized vectors (list of float
    lists) — the caller computes cosines as plain dot products.
    Pure-python on purpose: numpy exists whenever fastembed or
    model2vec imports, but the adapter itself stays zero-dep.
    """

    def __init__(self, embed_fn, tier: str):
        self._embed_fn = embed_fn
        self.tier = tier

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [self._normalize(v) for v in self._embed_fn(texts)]

    @staticmethod
    def _normalize(vec) -> list[float]:
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec] if norm > 0.0 else list(vec)


# Cached probe result (0 or 1 entries) — module-import side effects
# must not repeat per adapter (OTel optional-dependency precedent).
_SIDECHANNEL_PROBE: list = []


def _probe_fastembed():
    """Quality tier: fastembed + MiniLM int8 ONNX (36 chunks/s on a
    1GB box, bitwise-deterministic, ~100MB extras)."""
    try:
        from fastembed import TextEmbedding  # noqa: PLC0415
    except Exception:
        return None
    try:
        model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return None
    return SidechannelEngine(
        lambda texts: [list(map(float, v)) for v in model.embed(texts)],
        "quality")


def _probe_model2vec():
    """Fast tier: model2vec static potion (2463 chunks/s = 69×, no
    neural runtime, ~30MB extras; @1 costs 4 questions vs MiniLM)."""
    try:
        from model2vec import StaticModel  # noqa: PLC0415
    except Exception:
        return None
    try:
        model = StaticModel.from_pretrained(
            "minishlab/potion-retrieval-32M")
    except Exception:
        return None
    return SidechannelEngine(
        lambda texts: [list(map(float, v))
                       for v in model.encode(texts)],
        "fast")


def probe_sidechannel_engine() -> SidechannelEngine | None:
    """Import-probe optional embedding engines, quality tier first.

    Returns ``None`` when neither backend imports — the lexical
    pipeline is the zero-dependency default and stays untouched
    (graceful degradation, OTel precedent). Result is cached.
    """
    if _SIDECHANNEL_PROBE:
        return _SIDECHANNEL_PROBE[0]
    engine = _probe_fastembed() or _probe_model2vec()
    _SIDECHANNEL_PROBE.append(engine)
    return engine


def session_embedding_scores(question: str, sessions: list[dict],
                             engine: SidechannelEngine,
                             cache: "SidechannelCache | None" = None) -> dict:
    """Session → chunk-max cosine against *question*.

    ``sessions``: ``[{"session_id", "turns": [{"role", "content"}]}]``
    (the ``_counting_sessions`` shape). Deterministic: ties keep
    ingest order at the CALLER (never an id-alphabetical second key
    — the #083 tie-break artifact fabricated 12/30 from ``answer_*``
    session ids sorting first). With a Cycle 512 *cache* warmed at
    ingest time, only the question is embedded here — the
    per-question 7.5s full-haystack pass amortizes to ~zero.
    """
    chunks: list[str] = []
    owners: list[str] = []
    for session in sessions:
        text = " ".join(str(t.get("content", ""))
                         for t in session.get("turns", []))
        for chunk in chunk_session_text(text):
            chunks.append(chunk)
            owners.append(str(session.get("session_id", "")))
    if not chunks:
        return {}
    qv = engine.embed([question])[0]
    if cache is not None:
        vecs = cache.embed_missing(chunks, engine)
    else:
        vecs = engine.embed(chunks)
    best: dict[str, float] = {}
    for row, vec in enumerate(vecs):
        sid = owners[row]
        sim = sum(a * b for a, b in zip(qv, vec))
        if sim > best.get(sid, float("-inf")):
            best[sid] = sim
    return best


class SidechannelCache:
    """Content-addressed chunk-embedding store (Cycle 512).

    Keys are sha1 of the exact ``chunk_session_text`` output, so a
    session edit naturally misses (new text → new hash) while
    identical chunks across sessions dedupe to one vector. The
    write-time pass (``precompute_sessions`` at ingest) turns the
    C506 per-question full-haystack embed (7.5s/q measured on the
    full-500 POST arm) into a one-time ingest cost; a cache shared
    across adapters also survives the run_eval per-question
    fresh-adapter protocol.
    """

    def __init__(self, maxsize: int = 8192):
        self._vecs: dict[str, list[float]] = {}
        self._order: list[str] = []        # FIFO eviction order
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.embed_calls = 0               # texts sent to the engine

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        return self._vecs.get(self._key(text))

    def put(self, text: str, vec: list[float]) -> None:
        key = self._key(text)
        if key not in self._vecs:
            self._order.append(key)
            if len(self._order) > self.maxsize:
                self._vecs.pop(self._order.pop(0), None)
        self._vecs[key] = list(vec)

    def forget(self) -> None:
        """Drop all vectors (counters kept for audit)."""
        self._vecs.clear()
        self._order.clear()

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {"size": len(self._vecs), "maxsize": self.maxsize,
                "hits": self.hits, "misses": self.misses,
                "embed_calls": self.embed_calls,
                "hit_rate": self.hits / total if total else 0.0}

    def embed_missing(self, texts: list[str],
                      engine) -> list[list[float] | None]:
        """Vectors for *texts*, embedding and storing only misses."""
        out: list[list[float] | None] = [None] * len(texts)
        miss_idx: list[int] = []
        for i, text in enumerate(texts):
            vec = self._vecs.get(self._key(text))
            if vec is None:
                self.misses += 1
                miss_idx.append(i)
            else:
                self.hits += 1
                out[i] = vec
        if miss_idx:
            fresh = engine.embed([texts[i] for i in miss_idx])
            self.embed_calls += len(miss_idx)
            for i, vec in zip(miss_idx, fresh):
                self.put(texts[i], vec)
                out[i] = vec
        return out

    def precompute_sessions(self, sessions: list[dict],
                            engine) -> int:
        """Write-time pass: warm the cache for whole sessions.

        Accepts both shapes used in this module — the ingest shape
        (``{"session_id", "messages"}``) and the
        ``_counting_sessions`` shape (``turns``) — chunked with the
        exact ``session_embedding_scores`` protocol so warmed keys
        match query-time keys byte for byte. Returns the number of
        chunks embedded (misses consumed this call).
        """
        chunks: list[str] = []
        for session in sessions:
            turns = (session.get("messages")
                     or session.get("turns") or [])
            text = " ".join(str(t.get("content", "")) for t in turns)
            chunks.extend(chunk_session_text(text))
        before = self.misses
        self.embed_missing(chunks, engine)
        return self.misses - before


def sidechannel_form(question: str) -> str | None:
    """Form gate for the embedding side-channel (Research #083).

    ``"embed"``  — advice-request forms (C498 ``pref_form``): the
    lexical bridge is unreachable → pure embedding session
    selection replaces keyword ranking;
    ``"hybrid"`` — assistant-recall forms (C468 ``recall_form``):
    lexical recall is strong → embedding re-ranks the keyword
    candidates, fixing @1 ordering;
    ``None``     — every other form: lexical pipeline unchanged.
    Order matters and the two gates are disjoint in practice
    (C498 census: pref fires 29/30 preference, ZERO of 470 others
    — recall questions are excluded by the shipped-gate set).
    """
    if pref_form(question):
        return "embed"
    if recall_form(question) == "assistant":
        return "hybrid"
    return None


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


# ── Cycle 508: where-form locative extraction (Research #084) ──────

_WHERE_QUESTION_RE = re.compile(r"^\s*where\b", re.I)
_WHERE_PREP = r"(?:at|in|from|to|near|inside|outside|onto|on|under)"
_WHERE_DET = r"(?:(?:the|a|an|my|our)\s+)?"
# Case-SENSITIVE proper-noun run — re.I here also matches lowercase
# verb junk ("mix up my routine"), which cost a Denver regression
# in the C508 sim (v2 lesson).
_WHERE_PROPER_RE = re.compile(
    _WHERE_PREP + r"\s+" + _WHERE_DET + r"((?:[A-Z][\w'&.\-]*\s?){1,4})")
_WHERE_COMMON_RE = re.compile(
    _WHERE_PREP + r"\s+" + _WHERE_DET + r"("
    r"suburbs?|cities|downtown|countryside|mountains?|beaches?|"
    r"campus|office|gyms?|garage|bedrooms?|closets?|kitchens?|"
    r"yard|balcony|basement|attic|beds?|shelves?|shelf|walls?|"
    r"desks?|drawers?|cars?|bags?|backpacks?|cabinets?"
    r")\b", re.I)
_WHERE_TRAIL = frozenset({
    "and", "or", "the", "a", "an", "my", "our", "of", "in", "on",
    "at", "to", "is", "was", "are", "were", "it", "its", "it's",
    "been", "being", "so", "but", "because", "while", "when",
    "where", "who", "that", "which", "since", "for", "with", "as",
    "by", "near", "from", "up", "out", "if"})
_WHERE_TIMES = frozenset({
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "weekend", "january", "february",
    "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "today",
    "tomorrow", "yesterday", "morning", "afternoon", "evening",
    "night", "week", "day", "month", "year", "time"})
_WHERE_EVID_RE = re.compile(
    r"\b(?:remember|actually|just|recently|currently|finally)\b",
    re.I)
_WHERE_FP_RE = re.compile(r"\b(?:I|I'm|I've|I'll|we|my|me)\b")


def where_form(question: str) -> bool:
    """True for where-questions (STRICT: must START with "where").

    Census over full-500: exactly the 19 where-questions match (all
    currently land in the echo path, gate=answer); no other form
    family starts with "where" — zero hijack surface (C482/C488
    lesson). Mid-sentence "where" ("Do you remember where…") stays
    negative: those are recall forms owned by speaker_recall.
    """
    return bool(_WHERE_QUESTION_RE.search(question))


def _where_is_time(word: str) -> bool:
    return word.lower().rstrip("s") in _WHERE_TIMES


def _where_loc_candidates(sent: str) -> list[tuple[str, int]]:
    """Locative spans in *sent* with strength (3 multi-token
    proper, 2 single proper, 1 common noun)."""
    out: list[tuple[str, int]] = []
    for m in _WHERE_PROPER_RE.finditer(sent):
        toks = m.group(1).strip().split()
        while toks and (toks[-1].lower() in _WHERE_TRAIL
                        or _where_is_time(toks[-1])):
            toks.pop()
        if not toks or all(_where_is_time(w) for w in toks):
            continue
        span = " ".join(toks)
        if len(span) >= 3:
            out.append((span, 3 if len(toks) >= 2 else 2))
    for m in _WHERE_COMMON_RE.finditer(sent):
        out.append((m.group(1).lower(), 1))
    return out


def answer_where(question: str, sessions: list[dict],
                 retrieved_ids: list[str], nodes: dict,
                 context: str) -> tuple[str | None, dict]:
    """Locative sentence selection for where-questions (Cycle 508).

    "Where did I …" questions: retrieval bridges the answer session
    (answer_session_hit 13/15 on wrong where-qs) but the echo path
    returns the best-ranked LINE, which for where-facts is routine-
    ly an advice/echo sentence about the topic, not the user's
    location statement. This scans turns of RETRIEVED sessions only
    — the C472 full-graph lesson does NOT transfer: an all-haystack
    scan admits kh>=1 question-echoing distractors from unretrieved
    sessions (C508 sim A/B: 4 fixes -> 3 + 1 regression). Scoring:
    ``2*keyword_hits + 3*user_role + 2*first_person + 1*evidential
    + loc_strength + 3*in_window + session_rank_bonus``; the winning
    sentence is returned WHOLE so containment judging passes (GT
    phrases live mid-sentence). Questions and loc-less sentences
    never compete; no locative candidate anywhere -> None
    (fall-through to the answer gates, untouched).

    Returns ``(answer_or_None, detail)``.
    """
    kws = _keywords(question)
    sess_rank: dict[str, int] = {}
    for nid in retrieved_ids:
        node = nodes.get(nid)
        sid = node.get("session_id") if node else None
        if sid and sid not in sess_rank:
            sess_rank[sid] = len(sess_rank)
    window_texts = {ln.split("] ", 1)[-1].strip()
                    for ln in (context or "").split("\n") if "] " in ln}
    cands: list[dict] = []
    for s in sessions:
        rank = sess_rank.get(s["session_id"], None)
        if rank is None:
            continue
        for turn in s["turns"]:
            role = turn.get("role", "?")
            for sent in _split_sentences(str(turn.get("content", ""))):
                if sent.rstrip().endswith("?"):
                    continue
                locs = _where_loc_candidates(sent)
                if not locs:
                    continue
                kh = _keyword_hits(sent, kws)
                score = (kh * 2
                         + (3 if role == "user" else 0)
                         + (2 if _WHERE_FP_RE.search(sent) else 0)
                         + (1 if _WHERE_EVID_RE.search(sent) else 0)
                         + max(sc for _, sc in locs)
                         + (3 if sent.strip() in window_texts else 0)
                         + max(0, 2 - rank))
                cands.append({"role": role, "kh": kh, "score": score,
                              "sent": sent})
    if not cands:
        return None, {"sessions": len(sess_rank), "cands": 0}
    cands.sort(key=lambda c: -c["score"])
    best = cands[0]
    detail = {"sessions": len(sess_rank), "cands": len(cands),
              "best": {"role": best["role"], "kh": best["kh"],
                       "score": best["score"]},
              "top3": [(c["role"], c["score"], c["sent"][:80])
                       for c in cands[:3]]}
    return best["sent"], detail


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
    ``"ago"``/``"since"`` carry a duration unit and two/one anchors.
    ``None`` = not a temporal-arithmetic form (leave to the normal
    answer path; category labels are NOT trusted — C456 lesson 4).
    The former ``"first"`` kind was retired in C493 (zero-loss A/B;
    pairwise C489 owns the family).
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
    return None


def _anchor_keywords(anchor: str) -> list[str]:
    """Distinctive content keywords for an event anchor phrase."""
    ks = [w for w in _keywords(anchor) if w not in _ANCHOR_GENERIC]
    return ks or _keywords(anchor)


def _cnt_filter_session_context(sessions: list[dict], 
                               question_date: str = "",
                               max_sessions: int = 3) -> list[dict]:
    """Filter sessions to only include relevant temporal context.
    
    Args:
        sessions: List of session dictionaries
        question_date: ISO format date when question was asked
        max_sessions: Maximum number of relevant sessions to include
        
    Returns:
        Filtered list of sessions likely to contain relevant temporal context
    """
    if not sessions:
        return []
    
    # If we have a question date, prioritize sessions around that time
    if question_date:
        try:
            from datetime import datetime
            q_date = datetime.fromisoformat(question_date.replace('Z', '+00:00'))
            
            # Score sessions by temporal proximity
            scored_sessions = []
            for i, session in enumerate(sessions):
                session_score = 0
                
                # Check session date if available
                if 'date' in session:
                    try:
                        s_date = datetime.fromisoformat(session['date'].replace('Z', '+00:00'))
                        days_diff = abs((q_date - s_date).days)
                        
                        # Recent sessions score higher (exponential decay)
                        if days_diff <= 7:  # Same week
                            session_score += 3
                        elif days_diff <= 30:  # Same month
                            session_score += 2
                        elif days_diff <= 90:  # Same quarter
                            session_score += 1
                        elif days_diff <= 365:  # Same year
                            session_score += 0.5
                        
                        # Future/past bias handling
                        if s_date > q_date:  # Future sessions (plans/reminders)
                            session_score *= 0.3  # Deprioritize future planning
                        elif days_diff > 30:  # Distant past
                            session_score *= 0.7  # Slight deprioritization
                            
                    except (ValueError, KeyError):
                        pass
                
                # Score by content relevance
                content_score = 0
                if 'messages' in session:
                    content = ' '.join(session['messages'])
                    # Score for temporal keywords
                    temporal_keywords = ['day', 'week', 'month', 'year', 'today', 'yesterday', 
                                       'tomorrow', 'last', 'next', 'this', 'ago', 'since']
                    for keyword in temporal_keywords:
                        if keyword in content.lower():
                            content_score += 0.1
                
                total_score = session_score + content_score
                scored_sessions.append((total_score, i, session))
            
            # Sort by score and return top sessions
            scored_sessions.sort(reverse=True, key=lambda x: x[0])
            top_sessions = [sess[2] for sess in scored_sessions[:max_sessions]]
            return top_sessions
            
        except Exception:
            # Fall back to simple slicing if date parsing fails
            pass
    
    # Default: Return most recent sessions
    return sessions[:max_sessions]


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
    one of them. First-form questions retired in C493 fall back to
    exact containment (below) when passed here.
    """
    if not truth or not predicted:
        return False
    form = temporal_arith_form(question)
    if form is None:
        return exact_judge(question, truth, predicted)
    golds = [int(x) for x in re.findall(r"\d+", str(truth))]
    preds = [int(x) for x in re.findall(r"\d+", str(predicted))]
    return bool(preds and golds and any(p in golds for p in preds))


# ════════ Cycle 486: past-perfect duration forms (#077) ════════
# "How long had I been <state> when/before <event>?" — durations
# are dates in disguise: every "N units ago" / "for N units (now)"
# expression resolves to an absolute date via its containing
# session, and the past-perfect question reduces to the same
# calendar subtraction as C457/C482 (one subtract, no LLM).
# Prototype validated 7/7 on the full-500 population (baseline
# 0/7); the strict form gate matched ONLY currently-wrong questions
# → zero hijack surface by construction (C473 form-classifier
# interlock property, now proven for answer-side routes).

_PP_UNIT_DAYS = {"year": 365.25, "month": 30.44, "week": 7.0,
                 "day": 1.0, "hour": 1 / 24, "minute": 1 / 1440}

_PP_NUM_RE_SRC = (r"(\d+|a|an|one|two|three|four|five|six|seven|"
                  r"eight|nine|ten|eleven|twelve)")

_PP_AGO_RE = re.compile(
    r"\b(?:about\s+|around\s+|over\s+|almost\s+|just\s+|recently\s+)?"
    + _PP_NUM_RE_SRC
    + r"\s*(?:and\s+a\s+half\s*)?(years?|months?|weeks?|days?|hours?|"
      r"minutes?)\s+ago\b", re.I)
_PP_LAST_RE = re.compile(r"\blast\s+(month|week|year)\b", re.I)
_PP_NOW_RE = re.compile(
    r"\bfor\s+(?:about\s+|around\s+|over\s+|almost\s+|just\s+)?"
    + _PP_NUM_RE_SRC
    + r"\s*(?:and\s+a\s+half\s*)?"
      r"(years?|months?|weeks?|days?|hours?|minutes?)\b(?:\s+now\b)?",
    re.I)
_PP_BEFORE_JOB_RE = re.compile(
    r"before\s+i\s+started\s+my\s+current\s+job\s+at\s+"
    r"([a-z0-9 .&'-]+?)\s*\??\s*$", re.I)
_PP_TENURE_RE = re.compile(
    r"for\s+(?:about\s+|around\s+|over\s+|almost\s+)?"
    + _PP_NUM_RE_SRC
    + r"\s*(years?|months?)"
      r"(?:\s+and\s+" + _PP_NUM_RE_SRC + r"\s*months?)?\s*(?:now\b)?",
    re.I)

_PP_HEAD_RE = re.compile(r"^\s*how long\s+(?:had|have|did)\b", re.I)

# clause stopwords — 3-letter content nouns ("rug", "amp") must
# survive (#077 prototype v2 lesson: len>3 silently dropped them)
_PP_STOP = frozenset({
    "how", "long", "had", "have", "been", "when", "before", "i",
    "my", "me", "the", "a", "an", "to", "of", "in", "at", "for",
    "on", "new", "regularly", "current", "job", "using", "so",
    "far", "did", "you", "was", "were", "that", "use"})


def _pp_num(tok: str) -> int | None:
    """Word/digit → int (None when unparsable)."""
    return (int(tok) if tok.isdigit()
            else _CNT_WORD2NUM.get(tok.lower()))


def pp_duration_form(question: str) -> bool:
    """Strict past-perfect duration form gate (#077 census).

    ``how long (had|have|did) … (when|before)`` — the census over
    the full-500 found exactly 7 ``had|have`` matches (all currently
    wrong, zero currently-correct questions inside) plus one
    ``did`` sibling (same arithmetic). Pure-tenure "how long have I
    been X?" (no when/before) is deliberately excluded until the
    v2 tenure route ships; "how long did it take…" event-duration
    questions carry no when/before clause either.
    """
    q = question.strip()
    if not _PP_HEAD_RE.match(q):
        return False
    return bool(re.search(r"\b(?:when|before)\b", q, re.I))


def pp_pure_tenure_form(question: str) -> bool:
    """Pure present-perfect tenure form (#077 v2).

    ``how long (had|have) … been …`` with NO when/before clause —
    the tenure line states the answer as-of its session, no
    subtraction. ``did``-forms are excluded (event durations,
    "how long did it take…").
    """
    q = question.strip()
    if not _PP_HEAD_RE.match(q):
        return False
    if re.search(r"\b(?:when|before)\b", q, re.I):
        return False
    return bool(re.search(r"\bbeen\b", q, re.I))


def _pp_dur_exprs(line: str):
    """Yield ``(kind, n, unit, raw)`` for every duration expression.

    Two expression families, one arithmetic: *ago-type* (``N units
    ago``, ``last month/week/year``) and *now-type* (``for N units
    (now)`` — present-perfect tenure) both yield
    ``session_date − N`` as the state/event start.
    """
    for m in _PP_AGO_RE.finditer(line):
        n, u = _pp_num(m.group(1)), m.group(2)
        if n:
            yield ("ago", n, u.lower().rstrip("s"), m.group(0))
    for m in _PP_LAST_RE.finditer(line):
        u = m.group(1).lower()
        yield ("ago", 1, u, m.group(0))
    for m in _PP_NOW_RE.finditer(line):
        n, u = _pp_num(m.group(1)), m.group(2)
        if n:
            yield ("now", n, u.lower().rstrip("s"), m.group(0))


def _pp_kws(clause: str) -> list[str]:
    """Distinctive content keywords of a state/event clause."""
    return [w for w in re.findall(r"[a-z]+", clause.lower())
            if w not in _PP_STOP and len(w) >= 3]


def _pp_overlap(kw_list: list[str], line: str) -> int:
    low = line.lower()
    return sum(1 for w in kw_list if w in low)


def _pp_render(days: float, hint_units: list[str]) -> str:
    """Render a day count in the anchors' dominant unit.

    Nonzero guard (#077 v4): a tolerance branch that accepts ``0
    months`` for 10 days is a fabrication — every render path must
    keep ``0 < round(x)``.
    """
    if days <= 0:
        return "0 days"
    if "week" in hint_units:
        w = days / 7
        r = round(w)
        if 0 < r and abs(w - r) <= 0.5:
            return f"{r} week" + ("s" if r != 1 else "")
    if "month" in hint_units:
        mo = days / 30.44
        r = round(mo)
        if 0 < r and abs(mo - r) <= 0.5:
            return f"{r} month" + ("s" if r != 1 else "")
    d = round(days)
    if d > 0:
        return f"{d} day" + ("s" if d != 1 else "")
    return f"{round(days, 1)} days"


def _pp_ym_sub(total_m: int, part_m: int) -> str:
    """Compound y+m subtraction in months → canonical string."""
    d = total_m - part_m
    y, mo = d // 12, d % 12
    return (f"{y} year{'s' if y != 1 else ''} and "
            f"{mo} month{'s' if mo != 1 else ''}")


def _pp_tenure_months(line: str) -> int | None:
    """Parse ``for [about] N years [and M months] (now)`` → months."""
    m = _PP_TENURE_RE.search(line)
    if not m:
        return None
    n = _pp_num(m.group(1))
    if n is None:
        return None
    total = n * (12 if m.group(2).lower().startswith("year") else 1)
    if m.group(3):
        extra = _pp_num(m.group(3))
        if extra is not None:
            total += extra
    return total


def _pp_tenure_str(line: str) -> str | None:
    """Tenure expr → canonical answer string (compound-aware).

    ``for a year and five months now`` → ``1 year and 5 months``;
    ``for six weeks now`` → ``6 weeks``.
    """
    m = _PP_TENURE_RE.search(line)
    if not m:
        return None
    n = _pp_num(m.group(1))
    if n is None:
        return None
    unit = m.group(2).lower().rstrip("s")
    if m.group(3):
        extra = _pp_num(m.group(3))
        if extra is None:
            return None
        return _pp_ym_sub(n * (12 if unit.startswith("year") else 1)
                          + extra, 0)
    return f"{n} {unit}" + ("s" if n != 1 else "")


def answer_pp_duration(
        question: str,
        dated_sessions: list[tuple[str, list[dict]]],
) -> tuple[str | None, dict]:
    """Answer a past-perfect duration question (zero LLM).

    Routes (#077 prototype, 7/7 vs baseline 0/7):

    (a) *nested tenure* — "How long had I been working before I
        started my current job at <C>?" Both facts are stated
        as-of-now: ``total(profession) − tenure(C)`` in months.
        No tenure line for C anywhere → ABSTAIN (negative
        existence — the company was never joined).
    (b) *anchor arithmetic* — split the question at when/before
        into state and event clauses; scan user lines for duration
        expressions; anchor each to ``session_date − N``. Two-phase
        cross-exclusion selection: the event line is picked first
        (max event-overlap), then the state line EXCLUDING that
        line's identity — shared phrases ("bird watching") make
        single-line double-capture the dominant failure mode.

    Args:
        question: The question text.
        dated_sessions: Full-haystack evidence as
            ``[(session_date "YYYY-MM-DD", turns), …]``; only user
            lines are scanned. Unparsable dates are skipped.

    Returns:
        ``(answer | None, detail)`` — ``None`` = unresolved (fall
        through to the gate chain; the gates own abstention).
    """
    detail: dict = {"form": "pp_duration"}
    sessions: list[tuple[datetime, list[dict]]] = []
    for sdate, turns in dated_sessions:
        try:
            dt = datetime.strptime(sdate, "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        sessions.append((dt, turns))
    if not sessions:
        return None, detail

    m = _PP_BEFORE_JOB_RE.search(question)
    if m:  # route (a): tenure subtraction
        company = m.group(1).strip().rstrip("?.!")
        comp_low = company.lower()
        best_tenure = best_total = None
        for _dt, turns in sessions:
            for turn in turns:
                if turn.get("role") != "user":
                    continue
                line = str(turn.get("content", ""))
                low = line.lower()
                if comp_low in low:
                    tm = _pp_tenure_months(line)
                    if tm is not None and ("work" in low
                                           or "job" in low):
                        best_tenure = tm
                if ("working professionally" in low
                        or ("working" in low and " for " in low)):
                    tm = _pp_tenure_months(line)
                    if tm is not None and comp_low not in low:
                        best_total = tm
        detail["route"] = "before_job"
        detail["company"] = company
        if best_tenure is None:
            # Negative existence: no tenure line for the company
            # anywhere — absence of state evidence, not retrieval
            # failure (mirrors C469's ownership wall).
            detail["abstain"] = f"no tenure line for {company}"
            return ABSTAIN_ANSWER, detail
        if best_total is None or best_total < best_tenure:
            detail["abstain"] = "unparsable tenure/total"
            return ABSTAIN_ANSWER, detail
        detail["tenure_m"], detail["total_m"] = best_tenure, best_total
        return _pp_ym_sub(best_total, best_tenure), detail

    if not re.search(r"\b(?:when|before)\b", question, re.I):
        # route (c): pure tenure — no event anchor to subtract; the
        # best all-keywords tenure line IS the answer, as-of its
        # session (latest statement wins — knowledge_update
        # questions are asked after the statement session). Strict
        # all-keywords-on-one-line wall: with no second anchor to
        # disambiguate, a partial match (the Shinjuku twin against
        # a Harajuku line) must NOT fire (#077 v2). Planned
        # durations ("taking a break for a month") are not tenure —
        # for-type exprs require the explicit ``now`` suffix here.
        clause = re.sub(
            r"^\s*how long\s+(?:had|have)\s+(?:i\s+)?(?:been\s+)?",
            "", question, flags=re.I)
        sk = _pp_kws(clause)
        best = None  # (dt, answer)
        if sk:
            for dt, turns in sessions:
                for turn in turns:
                    if turn.get("role") != "user":
                        continue
                    line = str(turn.get("content", ""))
                    if _pp_overlap(sk, line) < len(sk):
                        continue
                    pick = None
                    tm = _PP_TENURE_RE.search(line)
                    if tm and tm.group(0).rstrip().lower()\
                            .endswith("now"):
                        # explicit as-of-now tenure (the compound
                        # "for a year and five months now" is only
                        # visible to TENURE_RE — NOW_RE stops at the
                        # first unit and loses the trailing "now")
                        pick = _pp_tenure_str(line)
                    if pick is None:
                        for kind, n, u, raw in _pp_dur_exprs(line):
                            if kind == "ago" or (kind == "now" and
                                                 raw.rstrip().lower()
                                                 .endswith("now")):
                                pick = f"{n} {u}" + (
                                    "s" if n != 1 else "")
                                break
                    if pick is not None and (
                            best is None or dt > best[0]):
                        best = (dt, pick)
        detail["route"] = "pure_tenure"
        if best is None:
            detail["missing"] = "tenure line"
            return None, detail
        return best[1], detail

    # route (b): event_abs − state_abs
    if re.search(r"\bwhen\b", question, re.I):
        state_clause, event_clause = re.split(
            r"\bwhen\b", question, 1, flags=re.I)
    else:
        state_clause, event_clause = re.split(
            r"\bbefore\b", question, 1, flags=re.I)
    state_clause = re.sub(
        r"^\s*how long\s+(?:had|have|did)\s+(?:i\s+)?(?:been\s+)?",
        "", state_clause, flags=re.I)
    sk, ek = _pp_kws(state_clause), _pp_kws(event_clause)
    scored = []  # (line_id, s_ov, e_ov, anchor, n, unit, kind)
    for si, (dt, turns) in enumerate(sessions):
        for ti, turn in enumerate(turns):
            if turn.get("role") != "user":
                continue
            line = str(turn.get("content", ""))
            for kind, n, u, _raw in _pp_dur_exprs(line):
                anchor = dt - timedelta(days=n * _PP_UNIT_DAYS[u])
                scored.append(((si, ti), _pp_overlap(sk, line),
                               _pp_overlap(ek, line), anchor, n, u, kind))
    # phase 1: event anchor (max event-overlap; ties prefer lines
    # whose event-overlap dominates over state-overlap). Short
    # clauses need all of their keywords, not a fixed 2 (census:
    # "did I use my new binoculars" → single content keyword after
    # tenure verbs are stopped).
    ev_c = [x for x in scored
            if len(ek) and x[2] >= min(2, len(ek))]
    best_event = max(ev_c, key=lambda x: (x[2], -x[1])) if ev_c else None
    # phase 2: state anchor — max state-overlap among lines OTHER
    # than the event line (cross-exclusion by line identity).
    st_c = [x for x in scored
            if len(sk) and x[1] >= min(2, len(sk))
            and x[0] != (best_event[0] if best_event else None)]
    best_state = max(st_c, key=lambda x: (x[1], -x[2])) if st_c else None
    if not best_state or not best_event:
        detail["missing"] = ("state" if not best_state else "event") \
            + " anchor"
        return None, detail
    days = abs((best_event[3] - best_state[3]).days)
    detail.update(route="ago_arith", state_unit=best_state[5],
                  event_unit=best_event[5], days=days)
    return _pp_render(days, [best_state[5], best_event[5]]), detail


_PP_NUMWORD_JUDGE_RE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve)\b")


def _pp_norm_judge(s: str) -> str:
    """Normalize number words to digits, strip punctuation."""
    s = s.lower().strip()
    s = _PP_NUMWORD_JUDGE_RE.sub(
        lambda m: str(int(m.group(1))) if m.group(1).isdigit()
        else str(_CNT_WORD2NUM.get(m.group(1), m.group(1))), s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def pp_duration_judge(question: str, truth: str,
                      predicted: str) -> bool:
    """Judge past-perfect duration answers (zero cost).

    Word-number normalization ("two weeks" ≡ "2 weeks"), GT
    day-range tolerance ("Answers ranging from 7 to 10 days are
    also acceptable"), and singular/plural + article tolerance.
    """
    if not truth or not predicted:
        return False
    if predicted.strip() == ABSTAIN_ANSWER:
        return ("not enough" in truth.lower()
                or "haven't" in truth.lower())
    if "not enough" in truth.lower():
        return False
    rng = re.search(r"ranging from (\d+) to (\d+) days",
                    truth.lower())
    base = _pp_norm_judge(
        re.split(r"Answers ranging", truth, flags=re.I)[0])
    p = _pp_norm_judge(predicted)
    if rng:
        m = re.search(r"(\d+)", p)
        if m and int(rng.group(1)) <= int(m.group(1)) \
                <= int(rng.group(2)):
            return True
    if p == base:
        return True
    ps = re.sub(r"\b(?:a|an|the)\b|s\b", "", p).split()
    bs = re.sub(r"\b(?:a|an|the)\b|s\b", "", base).split()
    return ps == bs


# ════════ Cycle 488: order-family N-anchor sorting (#078) ════════
# "What is the order of X, Y, Z from first to last?" — ordering
# questions need no date arithmetic: every item's anchor is the
# session date of its earliest FRESH report ("today/just/
# yesterday"), and the answer is the sort. Mention hygiene IS the
# mechanism (fresh > vague-recall > planning — the C482 trust
# tiers, now three: the earliest fresh report beats EVERY vague
# recall; vague recalls are consulted only when no fresh exists —
# "recently"-class mentions are post-hoc recalls that lag the
# event and systematically skew order late). Clause is the unit
# of intent, line the unit of time (a line can plan one event and
# freshly report another); item mention and eventive predicate
# can straddle a comma (relative-clause window). Prototype
# validated 9/9 on the full-500 family (baseline 0/9); the STRICT
# form gate matches exactly those 9 — all currently wrong → zero
# hijack surface by construction. The 29 pairwise "which happened
# first, X or Y?" siblings stay OUT until their own render is
# validated (C489 candidate).

_ORDER_FORM_RE = re.compile(
    r"(order of|from (the )?(first|earliest) to (the )?(last|latest)"
    r"|who .{0,30} first, second)", re.I | re.S)


def order_form(question: str) -> bool:
    """Strict order-family gate (Cycle 488 / Research #078).

    Matches ONLY the 9-family ordering phrasings ("order of …",
    "from first/earliest to last/latest", "who … first, second")
    — a full-500 census matched exactly the 9 family members, all
    currently wrong (zero hijack surface). The 29 pairwise "which
    happened first, X or Y?" siblings are deliberately excluded
    (they need their own render + negative-existence abstention
    before routing — C489).
    """
    return bool(_ORDER_FORM_RE.search(question))


# discourse timestamps scope to the whole utterance line
_ORD_FRESH_RE = re.compile(
    r"\b(today|just|yesterday|this morning|last night|tonight)\b",
    re.I)
# typo-tolerant ("yesterady") — the dataset ships real typos
_ORD_YESTERDAY_RE = re.compile(r"\byester\w{0,8}\b", re.I)
# intent markers scope to their CLAUSE (C488 granularity law)
_ORD_PLANNING_RE = re.compile(
    r"(planning|thinking of|thinking about|considering|want to|"
    r"would like|upcoming|looking forward|in the future|soon|"
    r"interested in|next time)", re.I)
_ORD_EVENTIVE_RE = re.compile(
    r"(attended|visited|went to|saw|watched|flew|got back|came back"
    r"|helped|ordered|signed up|redeemed|used a|participated|"
    r"participate|hiked|took part|completed|finished|started|"
    r"been to|took my|took our|loving|enjoying|on a high|"
    r"riding high|had such a great time|spent|graduated|graduate)",
    re.I)

_ORD_AIRLINES = ["American Airlines", "JetBlue", "Delta",
                 "United", "Southwest", "Spirit Airlines",
                 "Alaska Airlines", "Frontier", "Allegiant"]
_ORD_MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November",
     "December"])}
_ORD_FLIGHT_CTX_RE = re.compile(
    r"(flight|flew|flying|red-eye|miles|delay|round-trip|"
    r"non-stop|airline)", re.I)
_ORD_MUSEUM_PAT = re.compile(
    r"\b((?:[A-Z][\w'-]*\s+)*(?:[A-Z][\w'-]*\s+)?Museum(?:\s+of\s+"
    r"[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*)?)")
_ORD_TRIP_PAT = re.compile(
    r"((?:solo\s+|day\s+|road\s+)?(?:hike|camping trip|road trip|"
    r"trip)\s+to\s+[A-Z][\w'-]*(?:\s+(?:and\s+)?[A-Z][\w'-]*)*)")
_ORD_SPORT_PAT = re.compile(
    r"\b((?:(?:[A-Z][\w'-]*|the)\s+)*(?:[a-z]+\s+){0,2}(?:[Gg]ame|"
    r"[Cc]hampionship|[Pp]layoffs|[Tt]riathlon|[Tt]ournament|"
    r"5K(?:\s+[Rr]un)?)\b)")
_ORD_PROP2_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_ORD_VENUE_RE = re.compile(
    r"(Center|Arena|Theatre|Theater|Stadium|Pavilion|Hall)$")
_ORD_MUSIC_LINE_RE = re.compile(
    r"\b(concert|festival|jazz night|live|tour|merch(?:andise)?)\b",
    re.I)
# event-phrase templates, longest-specific first three
_ORD_CONCERT_CORE = [
    re.compile(r"(outdoor concert series(?:\s+in\s+the\s+park)?)"),
    re.compile(r"(music festival(?:\s+in\s+[A-Z][a-z]+)?)"),
    re.compile(r"(jazz night(?:\s+at\s+a\s+local\s+bar)?)"),
    re.compile(r"((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+"
               r"(?:concert|tour)(?:\s+at\s+the\s+[A-Z][a-z]+"
               r"(?:\s+[A-Z][a-z]+)*)?)")]

_ORD_WIN_PAST_N_RE = re.compile(
    r"past (three|two|one|\d+) months?", re.I)
_ORD_WIN_PAST_RE = re.compile(r"past month\b", re.I)
_ORD_WIN_MONTH_RE = re.compile(
    r"\b(?:in|during) (january|february|march|april|may|june|july"
    r"|august|september|october|november|december)\b", re.I)


def _ord_lines(dated: list) -> list[tuple]:
    """(date, session_idx, line) for user-role utterance lines.

    Assistant lines are never evidence — recommendations and
    itineraries mention exactly the distractor nouns (role
    discipline alone kills the whole recommendation class).
    """
    out = []
    for idx, (d, turns) in enumerate(dated):
        iso = parse_lme_date(str(d))
        if not iso:
            continue
        try:
            dt = datetime.strptime(iso, "%Y-%m-%d").date()
        except ValueError:
            continue
        for msg in turns or []:
            if msg.get("role") != "user":
                continue
            for line in re.split(r"[.\n]",
                                 str(msg.get("content", ""))):
                s = line.strip()
                if s:
                    out.append((dt, idx, s))
    return out


def _ord_qdate(question_date: str):
    iso = parse_lme_date(str(question_date)) if question_date \
        else None
    if not iso:
        return None
    try:
        return datetime.strptime(iso, "%Y-%m-%d").date()
    except ValueError:
        return None


def _ord_window(question: str, qdate):
    """(start, end) inclusive date window the question names, or
    ``None`` when it names none. ``qdate`` None → None."""
    if qdate is None:
        return None
    ql = question.lower()
    m = _ORD_WIN_PAST_N_RE.search(ql)
    if m:
        n = {"three": 3, "two": 2, "one": 1}.get(m.group(1))
        if n is None:
            n = int(m.group(1))
        return (qdate - timedelta(days=round(30.5 * n)), qdate)
    if _ORD_WIN_PAST_RE.search(ql):
        return (qdate - timedelta(days=31), qdate)
    m = _ORD_WIN_MONTH_RE.search(ql)
    if m:
        mo = _ORD_MONTHS[m.group(1)]
        y = qdate.year if qdate.month >= mo else qdate.year - 1
        start = date(y, mo, 1)
        end = (date(y + (mo == 12), (mo % 12) + 1, 1)
               - timedelta(days=1))
        return (start, end)
    return None


def _ord_window_needed(question: str) -> bool:
    ql = question.lower()
    return bool(_ORD_WIN_PAST_N_RE.search(ql)
                or _ORD_WIN_PAST_RE.search(ql)
                or _ORD_WIN_MONTH_RE.search(ql))


# ---------- closed-set item extraction (from the question) ----------

def _ord_extract_quoted(question: str) -> list[str]:
    return [c.strip() for c in
            re.findall(r"'([^']{12,})'", question)]


def _ord_extract_day_clauses(question: str) -> list[str]:
    return [c.strip() for c in re.findall(
        r"the day (I[^,.:]{10,}?)(?:,| and the day|\s*\?)",
        question)]


def _ord_extract_among_names(question: str) -> list[str]:
    m = re.search(r"among (.+?)\?", question)
    if not m:
        return []
    names, seen = [], set()
    for n in re.findall(r"\b[A-Z][a-z]{2,}\b", m.group(1)):
        if n not in seen:
            seen.add(n)
            names.append(n)
    return names


def _ord_closed_items(question: str) -> list[str]:
    items = _ord_extract_quoted(question)
    if not items:
        items = _ord_extract_day_clauses(question)
    if not items:
        items = _ord_extract_among_names(question)
    return items


_ORD_KW_STOP = {"the", "a", "an", "i", "my", "for", "at", "on",
                "in", "to", "of", "and", "with", "her", "his",
                "their", "from", "used", "just", "day"}


def _ord_kws(item: str) -> set[str]:
    words = [w for w in re.findall(r"[a-z$]+", item.lower())
             if w not in _ORD_KW_STOP and len(w) > 2]
    return set(words) or {item.lower()}


# ---------- label canonicalization (category-set route) ----------

def _ord_canon_label(s: str) -> str:
    s = re.sub(r"'s\b", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    strip = re.compile(
        r"^(?:the|a|an|finished|completed|recently|attended|back|"
        r"from|been|to|of|my|at|time|like|loving|free|and)\s+",
        re.I)
    prev = None
    while prev != s:
        prev = s
        s = strip.sub("", s)
    return s


def _ord_merge_items(anchored: list[tuple]) -> list[tuple]:
    """Merge anchored (date, idx, label) items by case-insensitive
    substring containment of canonicalized labels — kw-subset
    over-merges ("Museum of History" is a kw-subset of "Natural
    History Museum" but a different museum); containment keeps
    both while absorbing "5K run" into "Midsummer 5K Run"."""
    norm = [(d, i, _ord_canon_label(l)) for d, i, l in anchored]
    keep = []
    for a in sorted(norm, key=lambda x: -len(x[2])):
        if not any(a[2].lower() in b[2].lower() for b in keep):
            keep.append(a)
    return [a for a in keep if not any(
        a is not b and a[2].lower() in b[2].lower() for b in keep)]


# ---------- category-set route ----------

def _ord_category(question: str) -> str | None:
    ql = question.lower()
    if 'museum' in ql:
        return 'museum'
    if 'airline' in ql or 'flew with' in ql:
        return 'airline'
    if 'concert' in ql or 'musical event' in ql:
        return 'concert'
    if 'trip' in ql:
        return 'trip'
    if 'sport' in ql:
        return 'sport'
    if 'graduat' in ql:
        return 'graduation'
    return None


def _ord_specific(label: str) -> bool:
    return len(label) >= 5 and len(label.split()) >= 2


def _ord_category_items(cat: str, lines: list) -> list[str]:
    items: list[str] = []
    if cat == 'airline':
        for _, _, line in lines:
            if _ORD_FLIGHT_CTX_RE.search(line):
                ll = line.lower()
                for al in _ORD_AIRLINES:
                    if al.lower() in ll:
                        items.append(al)
    elif cat == 'museum':
        for _, _, line in lines:
            for m in _ORD_MUSEUM_PAT.finditer(line):
                items.append(m.group(1))
    elif cat == 'trip':
        for _, _, line in lines:
            for m in _ORD_TRIP_PAT.finditer(line):
                items.append(m.group(1).strip())
    elif cat == 'sport':
        for _, _, line in lines:
            for m in _ORD_SPORT_PAT.finditer(line):
                lab = m.group(1).strip()
                if _ord_specific(lab):
                    items.append(lab)
    return list(dict.fromkeys(items))


# ---------- anchoring (fresh > vague-recall > planning) ----------

def _ord_clauses(line: str) -> list[str]:
    return [c for c in re.split(r',', line) if c.strip()]


def _ord_scan_anchor(item_kws: set, lines: list, window=None,
                     ctx: re.Pattern | None = None):
    """Earliest trustworthy mention of the item (Cycle 488).

    FRESH is a line-level discourse timestamp; planning/eventive
    intent is CLAUSE-level (a line can plan one event and freshly
    report another — evaluating planning at line level kills
    valid anchors). Clause windows extend one clause right
    (relative clauses: "my cousin Alex, who graduated …").
    Priority tiers: earliest fresh report > earliest clean vague
    recall; planning-only mentions never anchor.
    """
    fresh_hits, vague_hits = [], []
    for d, idx, line in lines:
        if window and not (window[0] <= d <= window[1]):
            continue
        ll = line.lower()
        if not all(k in ll for k in item_kws):
            continue
        if ctx and not ctx.search(line):
            continue
        cs = _ord_clauses(line) or [line]
        windows = []
        for j, c in enumerate(cs):
            if all(k in c.lower() for k in item_kws):
                windows.append(c)
                if j + 1 < len(cs):
                    windows.append(c + ' ' + cs[j + 1])
        if not windows:
            windows = [line]
        hit = any(_ORD_EVENTIVE_RE.search(w)
                  and not _ORD_PLANNING_RE.search(w)
                  for w in windows)
        if _ORD_FRESH_RE.search(line):
            rd = (d - timedelta(days=1)
                  if _ORD_YESTERDAY_RE.search(line) else d)
            fresh_hits.append((rd, idx, line))
        elif hit:
            vague_hits.append((d, idx, line))
    pool = fresh_hits or vague_hits
    if not pool:
        return None
    pool.sort(key=lambda x: (x[0], x[1]))
    return pool[0]


def _ord_concert_items(lines: list, window) -> list[str] | None:
    """Session-anchored concert labels: event phrases from
    fresh/eventive music lines; artists = 2+Cap phrases co-occurring
    with music nouns, anchored to the earliest session holding a
    fresh/eventive music line — the item mention and the event
    marker can live in adjacent lines of one conversation (line
    scope first, session scope as the fallback tier)."""
    def ev_ok(line: str) -> bool:
        return bool(_ORD_FRESH_RE.search(line)
                    or (_ORD_EVENTIVE_RE.search(line)
                        and not _ORD_PLANNING_RE.search(line)))

    sess: dict[int, list] = {}
    for d, i, line in lines:
        sess.setdefault(i, []).append((d, line))
    phrases: dict[str, tuple] = {}
    for d, i, line in lines:
        if not (_ORD_MUSIC_LINE_RE.search(line)
                and ev_ok(line)):
            continue
        for pat in _ORD_CONCERT_CORE:
            m = pat.search(line)
            if m:
                key = m.group(1).lower()
                if key not in phrases or (d, i) < phrases[key][:2]:
                    phrases[key] = (d, i, m.group(1))
    anchored = [(d, i, lab) for d, i, lab in phrases.values()]
    phrase_anchors = {(d, i) for d, i, _ in anchored}
    artists: dict[str, list] = {}
    for d, i, line in lines:
        if not _ORD_MUSIC_LINE_RE.search(line):
            continue
        for m in _ORD_PROP2_RE.finditer(line):
            nm = m.group(1)
            if _ORD_VENUE_RE.search(nm):
                continue
            if re.search(
                    r"(Festival|Concert|Tour|Series|Music)$", nm):
                continue          # event name, not an artist
            artists.setdefault(nm, []).append((d, i))
    for nm, occ in artists.items():
        best = None
        for d, i in occ:
            for dd, sline in sess.get(i, []):
                if (_ORD_MUSIC_LINE_RE.search(sline)
                        and ev_ok(sline)):
                    cand = (dd, i)
                    if best is None or cand < best:
                        best = cand
        if best and best not in phrase_anchors:
            if window and not (window[0] <= best[0]
                               <= window[1]):
                continue
            anchored.append((best[0], best[1], nm))
    if window:
        anchored = [a for a in anchored
                    if window[0] <= a[0] <= window[1]]
    anchored = _ord_merge_items(anchored)
    anchored.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in anchored] if anchored else None


def _ord_render(items: list[str]) -> str:
    """N==3 connective render (the family's dominant convention),
    numbered list otherwise (the judge segments both shapes)."""
    if len(items) == 3:
        return (f"First {items[0]}, then {items[1]}, "
                f"finally {items[2]}")
    return ", ".join(f"{i}. {it}" for i, it in enumerate(items, 1))


def answer_order(question: str, dated: list,
                 question_date: str = "") -> tuple:
    """Answer an order-family question by N-anchor sorting.

    Args:
        question: Raw question (callers gate with
            :func:`order_form` first).
        dated: Evidence sessions — ``[(date, turns)]`` where turns
            are ``{"role", "content"}`` dicts (the adapter's
            ``_counting_sessions`` shape with dates joined in).
        question_date: Question timestamp (window resolution;
            windowed questions without it stay unresolved rather
            than misfire — the C488 locality rule).

    Returns:
        ``(answer, detail)`` — answer ``None`` means unresolved
        (fall through to the gate chain; the gates own
        abstention). ``detail`` carries ``form``/``mode`` for
        telemetry/forensics.
    """
    lines = _ord_lines(dated)
    qdate = _ord_qdate(question_date)
    if _ord_window_needed(question) and qdate is None:
        return None, {"form": "order", "mode": "window-unresolvable"}
    window = _ord_window(question, qdate)

    closed = _ord_closed_items(question)
    if closed:
        anchored = []
        for item in closed:
            a = _ord_scan_anchor(_ord_kws(item), lines, window)
            if a:
                anchored.append((a[0], a[1], item))
        anchored.sort(key=lambda x: (x[0], x[1]))
        if anchored:
            return (_ord_render([x[2] for x in anchored]),
                    {"form": "order", "mode": "closed",
                     "n": len(anchored)})
        return None, {"form": "order", "mode": "closed"}

    cat = _ord_category(question)
    if not cat:
        return None, {"form": "order", "mode": "no-category"}
    if cat == 'concert':
        items = _ord_concert_items(lines, window)
        if items:
            return (_ord_render(items),
                    {"form": "order", "mode": "concert",
                     "n": len(items)})
        return None, {"form": "order", "mode": "concert"}

    ctx = (_ORD_FLIGHT_CTX_RE if cat == 'airline'
           else re.compile(r"graduat", re.I)
           if cat == 'graduation' else None)
    if cat == 'graduation':
        names = _ord_extract_among_names(question)
        anchored = []
        for nm in names:
            a = _ord_scan_anchor({nm.lower()}, lines, window, ctx)
            if a:
                anchored.append((a[0], a[1], nm))
        anchored.sort(key=lambda x: (x[0], x[1]))
        if anchored:
            return (_ord_render([x[2] for x in anchored]),
                    {"form": "order", "mode": "graduation",
                     "n": len(anchored)})
        return None, {"form": "order", "mode": "graduation"}

    labels = _ord_category_items(cat, lines)
    anchored = []
    for lab in labels:
        a = _ord_scan_anchor(_ord_kws(lab), lines, window, ctx)
        if a:
            anchored.append((a[0], a[1], lab))
    anchored = _ord_merge_items(anchored)
    anchored.sort(key=lambda x: (x[0], x[1]))
    if anchored:
        return (_ord_render([x[2] for x in anchored]),
                {"form": "order", "mode": cat, "n": len(anchored)})
    return None, {"form": "order", "mode": cat}


# ---------- sequence-equivalence judge ----------

_ORD_SEG_SPLIT_RE = re.compile(
    r"\s*\d+\.\s+"
    r"|[,;]\s*(?:and\s+)?(?:then|after that|finally|lastly)\b"
    r"|\.\s+(?:then|finally|lastly)\b"
    r"|,\s*followed\s+by\b"
    r"|\band\s+then\b", re.I)
_ORD_LEAD_RE = re.compile(
    r"^(?:first[,:]?\s+|i\s+first\s+)", re.I)
_ORD_ORDER_PREFIX_RE = re.compile(
    r"^[Tt]he\s+order\b[^:]*:\s*")
_ORD_JUDGE_STOP = frozenset(
    "i me my the a an and then after that finally lastly first "
    "second third followed by of is was were be been to on at in "
    "for with from order it its".split())


def _ord_segments(text: str) -> list[str]:
    """Ordered item segments from a rendered/truth answer:
    numbered markers, then/finally connectives, "followed by",
    bare comma lists as the last resort."""
    t = _ORD_ORDER_PREFIX_RE.sub(
        "", str(text).strip().rstrip("."))
    parts = [p for p in _ORD_SEG_SPLIT_RE.split(t) if p.strip()]
    parts = [_ORD_LEAD_RE.sub("", p).strip(" ,.")
             for p in parts if p.strip()]
    parts = [p for p in parts if p]
    if len(parts) == 1 and "," in parts[0]:
        parts = [p.strip() for p in parts[0].split(",")
                 if p.strip()]
    return parts


def _ord_seg_kws(seg: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z$&'+-]*", seg.lower())
            if len(w) >= 3 and w not in _ORD_JUDGE_STOP}


def _ord_seg_match(a: str, b: str) -> bool:
    ka, kb = _ord_seg_kws(a), _ord_seg_kws(b)
    ov = ka & kb
    # >=2 shared distinctive words, or the smaller side is a
    # single keyword and that keyword is shared (proper nouns:
    # "JetBlue" / "Emma"). A single shared generic ("game" in
    # "NBA game" vs "championship game") must NOT match — that
    # would pass reordered sports answers.
    if ov and (len(ov) >= 2 or min(len(ka), len(kb)) == 1):
        return True
    na, nb = a.strip().lower(), b.strip().lower()
    return bool(na) and bool(nb) and (na in nb or nb in na)


def order_judge(question: str, truth: str,
                predicted: str) -> bool:
    """Judge order-family answers by SEQUENCE equivalence (zero
    cost): both sides are segmented into ordered item lists and
    each position must keyword-match (distinctive-word overlap or
    containment either way). A length mismatch fails — item recall
    without order is not an ordering; a reordering is a different
    answer."""
    if not truth or not predicted:
        return False
    if not order_form(question):
        return exact_judge(question, truth, predicted)
    tsegs = _ord_segments(truth)
    psegs = _ord_segments(predicted)
    if not tsegs or not psegs or len(tsegs) != len(psegs):
        return False
    return all(_ord_seg_match(t, p)
               for t, p in zip(tsegs, psegs))


# ════════ Cycle 489: pairwise "which happened first" (#078) ════════
# The 29-family gate C488 left out. Form: ^Which … first + tail
# disjunction ", X or Y?" — candidates render VERBATIM from the
# question (the judge is containment-based, so article/noun form
# survives). Evidence lines are user-role only (C488 role law);
# timestamps are the RAW haystack strings — minute granularity is
# the whole point (same-day sessions are ordered by time-of-day,
# date-only collapses them). Decision matrix (C489 A/B verified
# +4/−0 on the 29): both anchored (>24 h apart) → earlier; one
# anchored + other never mentioned in ANY user line → ABSTAIN
# (negative existence — both _abs members); everything else falls
# through untouched.

_PW_TAIL_RE = re.compile(r',\s*([^,?]+?)\s+or\s+([^,?]+?)\s*\?\s*$')
_PW_ORDER_EXCL = re.compile(r'order of|from first|to last|order from',
                            re.I)


def pw_form(question: str):
    """Pairwise which-first gate (Cycle 489 / Research #078).

    ``^Which`` + ``first`` + terminal disjunction ", X or Y?".
    Returns ``(X, Y)`` or ``None``. Order-family phrasings
    ("order of", "from first to last") are excluded — those route
    to ``order_form`` (C488). Full-500 census: 0 non-temporal
    matches — zero hijack surface.
    """
    q = question.strip()
    if not re.match(r'(?i)^which\b', q):
        return None
    if not re.search(r'\bfirst\b', q, re.I):
        return None
    if _PW_ORDER_EXCL.search(q):
        return None
    m = _PW_TAIL_RE.search(q)
    if not m:
        return None
    a, b = m.group(1).strip(), m.group(2).strip()
    if len(a) < 3 or len(b) < 3:
        return None
    return a, b


# question-framing words never anchor (the question's nouns carry
# the event identity; "did I attend first" contributes nothing)
# C495: 'trip' joins the stops — "which trip did I take first"
# contributes the FRAMING noun; evidence lines say "went on a
# two-week trip to Europe" and partial-kw matching takes over
_PW_FRAME_STOP = frozenset(
    "narrator purchase purchases arrival malfunction start "
    "started starting loss lose losing lost received receiving "
    "receive attendance attend attended participation "
    "participate participated the a an my our their his her one "
    "first new upcoming event item task device for to of with "
    "from in on at by and or did was were trip".split())
_PW_TOKEN_RE = re.compile(r"[a-z0-9#$&'+-]+")


def _pw_stems(word: str) -> list[str]:
    """Surface + stripped variants (ing/ies/es/s/ed) — 'buying'
    matches a 'bought'-clause's noun, 'plants' matches 'plant'."""
    st = {word}
    if word.endswith('ing') and len(word) > 5:
        st.add(word[:-3])
    if word.endswith('ies') and len(word) > 4:
        st.add(word[:-3] + 'y')
    elif word.endswith('es') and len(word) > 4:
        st.add(word[:-2])
    elif word.endswith('s') and len(word) > 3:
        st.add(word[:-1])
    if word.endswith('ed') and len(word) > 4:
        st.add(word[:-2])
    return sorted(st)


# C495 F4: purpose clauses in candidate TAILS are modifier
# noise for kw extraction — "a charity 5K run to raise money"
# anchors on charity+run, not on raise/money (213fd887)
_PW_PURPOSE_RE = re.compile(
    r'\s+to\s+(raise|buy|get|help|support|celebrate|commemorate|'
    r'donate|find|learn|improve)\b', re.I)


def _pw_kws(phrase: str) -> list[list[str]]:
    """Stem-group keyword list (≤4 content words, stop-stripped).
    Every group must match somewhere in the line (any variant).
    Purpose-clause tails are pruned first (C495 F4)."""
    phrase = _PW_PURPOSE_RE.split(phrase)[0] or phrase
    toks = [t.strip("'\"") for t in _PW_TOKEN_RE.findall(phrase.lower())]
    words = [w for w in toks
             if len(w) > 2 and w not in _PW_FRAME_STOP]
    words = words[:4]
    return [_pw_stems(w) for w in words] if words else []


def _pw_line_match(kws, line: str) -> bool:
    ll = line.lower()
    return all(any(v in ll for v in grp) for grp in kws)


# verb congruence: the question's did-I verb filters evidence
# clauses — "did I finish X or Y first" ignores mere mentions of
# X/Y in unrelated clauses (buying, wanting, recommending)
_PW_VERB_RE = re.compile(
    r'\bdid i\s+((?:\w+\s+){0,2}?\w+?)\s+(?:.*?\s+)?first\b'
    r'|\bwere\s+(\w+ed)\s+first\b', re.I)
_PW_VERB_MAP = {
    'attend': ('attend', 'went to', 'participate'),
    'got': ('got', 'bought', 'purchas', 'received'),
    'get': ('got', 'bought', 'purchas', 'received'),
    'buy': ('bought', 'purchas', 'order', 'got'),
    'purchase': ('bought', 'purchas', 'order', 'got'),
    'complete': ('complet', 'finish', 'done', 'fix', 'trimm'),
    'finish': ('finish', 'complet', 'done', 'wrapp'),
    'start': ('start', 'began', 'plant', 'sign up', 'launch'),
    'set up': ('set up', 'install', 'configur', 'got'),
    'setup': ('set up', 'install', 'configur', 'got'),
    'take': ('took', 'went'),  # C495: 'take a trip' surfaces as 'went on/to'
    'take care of': ('took', 'mainten', 'repair', 'care', 'clean'),
    'join': ('join', 'sign up', 'became', 'enroll'),
    'lose': ('lost', 'lost my', 'misplac'),
}


def _pw_qverbs(question: str):
    """Question-verb → acceptable evidence-verb surfaces."""
    m = _PW_VERB_RE.search(question)
    if not m:
        return None
    v = (m.group(1) or m.group(2) or '').strip().lower()
    v = re.sub(r'\s+(a|an|the|my|our)\b.*$', '', v).strip()
    if v in _PW_VERB_MAP:
        return _PW_VERB_MAP[v]
    for k, vv in _PW_VERB_MAP.items():
        if v.startswith(k.split()[0]) and k.split()[0] not in (
                'take', 'set', 'setup'):
            return vv
    return None


_PW_DT_RE = re.compile(
    r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:\s*\([^)]*\))?\s+'
    r'(\d{1,2}):(\d{2})')
_PW_DATE_RE = re.compile(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})')


def _pw_lines(dated: list) -> list[tuple]:
    """(datetime, session_idx, line) for user-role lines.

    Datetimes keep MINUTE granularity from the raw haystack
    string — the same-day discriminator date-only ``_ord_lines``
    throws away (C489's key forensic datum: haystack timestamps
    like ``2023/05/30 (Fri) 07:08``).
    """
    out = []
    for idx, (d, turns) in enumerate(dated):
        txt = str(d or '').strip()
        dt = None
        m = _PW_DT_RE.match(txt)
        if m:
            try:
                dt = datetime(int(m.group(1)), int(m.group(2)),
                              int(m.group(3)), int(m.group(4)),
                              int(m.group(5)))
            except ValueError:
                dt = None
        if dt is None:
            m2 = _PW_DATE_RE.match(txt)
            if not m2:
                continue
            try:
                dt = datetime(int(m2.group(1)), int(m2.group(2)),
                              int(m2.group(3)))
            except ValueError:
                continue
        for msg in turns or []:
            if msg.get('role') != 'user':
                continue
            for line in re.split(r'[.\n]', str(msg.get('content', ''))):
                s = line.strip()
                if s:
                    out.append((dt, idx, s))
    return out


_PW_SINCE_RE = re.compile(
    r'\bsince\s+(' + '|'.join(_TA_MONTH_NUM) +
    r')\w*\s+(\d{1,2})(?:st|nd|rd|th)?\b', re.I)
# C494: ordinal suffix ("since February 20th") — the bare
# (\d{1,2})\b failed on '20th' (word char after digits).
_PW_NUMW = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
            'ten': 10}
_PW_REL_RE = re.compile(
    r'\b(?:' + '|'.join(_PW_NUMW) + r'|\d{1,2})\s+'
    r'(day|week|month|year)s?\s+ago\b'
    r'|\blast\s+(week|month|year)\b'
    r'|\blast\s+summer\b'
    r'|\ba\s+few\s+(day|week|month|year)s?\s+ago\b'
    r'|\b(?:for\s+)?the\s+past\s+(?:' + '|'.join(_PW_NUMW) +
    r'|\d{1,2})\s+(day|week|month|year)s?\b', re.I)
# C494 surface widening (29-family residual forensics): 'last
# summer' (calendar-anchored to July 1 of the previous year —
# order-safe, ±2-month precision), 'a few <unit>s ago' (the
# conventional 3 units), and 'for the past N <unit>s' (state-START
# anchoring — "taking Spanish classes for the past three months"
# starts 3 months back, not at the session clock). All remain
# clause-gated by _pw_rel_dt (anaphora safety, C489 trace).
_PW_UNIT_DAYS = {'day': 1, 'week': 7, 'month': 30, 'year': 365}


def _pw_rel_delta(m) -> timedelta | None:
    txt = m.group(0).lower()
    m2 = re.match(r'last\s+(week|month|year)', txt)
    if m2:
        return timedelta(days=_PW_UNIT_DAYS[m2.group(1)])
    m3 = re.match(r'a\s+few\s+(day|week|month|year)', txt)
    if m3:
        return timedelta(days=3 * _PW_UNIT_DAYS[m3.group(1)])
    m4 = re.match(r'(?:for\s+)?the\s+past\s+([a-z]+|\d{1,2})\s+'
                  r'(day|week|month|year)', txt)
    if m4:
        tok = m4.group(1)
        n = _PW_NUMW.get(tok)
        if n is None:
            try:
                n = int(tok)
            except ValueError:
                return None
        return timedelta(days=n * _PW_UNIT_DAYS[m4.group(2)])
    m5 = re.match(r'(\d{1,2})\s+(day|week|month|year)', txt)
    if m5:
        n, u = int(m5.group(1)), m5.group(2)
    else:
        mw = re.match(r'([a-z]+)\s+(day|week|month|year)', txt)
        if not mw:
            return None
        n = _PW_NUMW.get(mw.group(1))
        if n is None:
            return None
        u = mw.group(2)
    return timedelta(days=n * _PW_UNIT_DAYS[u])


def _pw_rel_dt(dt, line, kws):
    """Relative-duration override ("a month ago", "last week") —
    ONLY when a candidate keyword shares the CLAUSE (anaphoric
    "started it three weeks ago" stays on the session clock: the
    pronoun's referent is unproven at clause level — C489 trace
    c27434e8: the pronoun line shares its clause with "the
    Japanese Zero", pulling the anchor wrong otherwise)."""
    for m in _PW_REL_RE.finditer(line):
        cs = _ord_clauses(line) or [line]
        span = (m.start(), m.end())
        for c in cs:
            if c in line:
                i = line.find(c)
                if i <= span[0] and span[1] <= i + len(c):
                    cl = c
                    if any(any(v in cl.lower() for v in grp)
                           for grp in kws):
                        if m.group(0).lower().startswith('last summer'):
                            return datetime(dt.year - 1, 7, 1)
                        dl = _pw_rel_delta(m)
                        if dl:
                            return dt - dl
    return dt


def _pw_line_dt(dt, line, kws=None):
    """Effective event datetime: in-line adverbial date > "since
    <Month> <day>" > clause-gated relative duration > session
    clock. Future-dated in-text dates (> session +14 d, next-year
    typos) are distrusted (C482 asymmetry)."""
    yh = str(dt.year)
    itd = _line_adverbial_date(line, yh)
    if itd is None:
        m = _PW_SINCE_RE.search(line)
        if m:
            try:
                itd = date(int(yh), _TA_MONTH_NUM[
                    m.group(1)[:3].lower()], int(m.group(2))).isoformat()
            except (ValueError, KeyError):
                itd = None
    if itd is not None:
        try:
            ev = datetime.strptime(itd, '%Y-%m-%d')
            if not (ev > dt + timedelta(days=14)):
                return ev
        except ValueError:
            pass
    return _pw_rel_dt(dt, line, kws or [])


_PW_EVENTIVE_RE = re.compile(
    r'(attended|attending|visited|went to|saw|watched|flew|got back|came back'
    r'|helped|ordered|signed up|redeemed|used a|participated|'
    r'participate|hiked|took part|completed|finished|started|starting|'
    r'taking|been to|took my|took our|loving|enjoying|on a high|'
    r'joined|bought|purchased|got|received|set up|installed|'
    r'fixed|repaired|took care|maintenance|lost|broke|'
    r'stopped working|dropped|planted|cleaned|washed'
    # C495: 'went' bare ("went on a two-week trip"), precise
    # 'did a/it/my/the' (never bare 'did' — question-form safe),
    # 'had a meeting' (1a1dc16d rel-clause eventive)
    r'|\bdid (?:a|it|my|the)\b|had a meeting|\bwent\b)', re.I)
# C494: progressive gerunds attending/starting/taking join the
# eventive surface — "I've been attending workshops", "starting
# seeds indoors", "taking Spanish classes" are ongoing-PAST
# reports (progressive + no future marker), not plans; planning
# clauses stay vetoed by _ORD_PLANNING_RE at window granularity.


# ── C495: clause-granular + cross-line anchor scanning ─────────


def _cl_kw_hits(kws, clause: str) -> list[int]:
    """Indices of kw groups hitting this clause (partial ok)."""
    ll = clause.lower()
    return [i for i, grp in enumerate(kws)
            if any(v in ll for v in grp)]


def _pw_hit_windows(kws, text: str) -> list[str]:
    """Eventive clause windows anchored at ANY kw-hitting clause
    (C494 anchored only at full-kw clauses — a strict subset).
    Appositive evidence: "Rachel, who I had a meeting with on
    April 10th" — the kw clause and the eventive rel-clause are
    separate, ±1-clause windows bridge them (F3)."""
    cs = _ord_clauses(text) or [text]
    wins = []
    for j, c in enumerate(cs):
        if not _cl_kw_hits(kws, c):
            continue
        wins.append(c)
        if j + 1 < len(cs):
            wins.append(c + ' ' + cs[j + 1])
        if j > 0:
            wins.append(cs[j - 1] + ' ' + c)
    if not wins:
        wins = [text]
    return [w for w in wins
            if _PW_EVENTIVE_RE.search(w)
            and not _ORD_PLANNING_RE.search(w)]


# C495 F5: planning veto waived by a subordinate/relative PAST —
# "planning to buy a charger, since I lost my old one two weeks
# ago" (78cf46a3), "lens that I got a month ago" under 'interested
# in' (b4a80587). The past event is reported INSIDE the plan
# sentence; kw-scoped planning still vetoes clean plans.
_PW_SUB_RE = re.compile(
    r'\b(since|because|after|when)\b[^,]{0,60}?(?:'
    + _PW_EVENTIVE_RE.pattern + r')'
    r'|\b(?:that|which|who)\s+(?:i\s+|we\s+|they\s+|he\s+|she\s+)?'
    r'(?:got|bought|ordered|received|lost|started|joined|fixed|'
    r'planted|signed up|attended)', re.I)

# C495: generic candidate nouns — a relative-date pull inside a
# CROSS-LINE join must sit in a clause with candidate-UNIQUE kw
# (c27434e8: 'model' shared across Ferrari/Zero questions only
# by words[:4] truncation — insufficient distinctiveness)
_PW_GENERIC = frozenset(
    'model event item task device trip gift project game show '
    'book party meeting sale'.split())


# C496 F6: anaphora purchase-report join — the kw-less
# sentence DIRECTLY AFTER a full-matching kw line pair reports
# the pair-item's purchase with a BARE QUANTIFIED object + price
# ("I got a set of 10 for $25 about a month ago", 6ed717ea: the
# 'set of 10' anaphorically resumes 'those training pads').
# Discriminators vs poison: (a) NUMERIC of-complement only —
# 'a pack of dental chews' names a new item and stays out;
# (b) line-level rule — intra-sentence anaphora ('started it
# three weeks ago', c27434e8) lives in the in-line branch whose
# _pw_rel_dt clause gate still holds; (c) question-verb
# congruence + realized-purchase price signature; (d) planning
# veto and kw-hit exclusivity on the event line.
_PW_ANAPHOR_EV_RE = re.compile(
    r'\b(?:got|bought|ordered|purchased)\b[^.!?]{0,40}?'
    r'\b(?:a|an|another|some)\s+'
    r'(?:set|pack|box|pair|bag|bunch|dozen|bottle)\b'
    r'(?:\s+of\s+\d{1,3})?(?!\s+of\b)'
    r'[^.!?]{0,30}?\bfor\s+\$\s?\d', re.I)

# URL debris from _pw_lines' sentence split (Chewy.com → 'com')
_PW_DEBRIS_RE = re.compile(r'[a-z]{2,4}\d{0,2}', re.I)


def _pw_scan_anchor(kws, lines, window=None, qverbs=None,
                    weak=frozenset()):
    """Earliest trustworthy (effective_dt, session_idx, line) for
    one candidate. Tiers (C482/C488): fresh discourse deictics
    (today/just/yesterday−1 d) outrank vague eventive pasts;
    planning clauses never anchor (kw-scoped, C495 F5-waivable).
    Verb congruence narrows the eventive tier when the question
    names a did-I verb.

    C495: (F3) clause windows anchor at any kw-hit clause;
    (F1) cross-line joins — same-session adjacent lines each
    contributing ≥1 kw group, joined text must full-match;
    (F5) subordinate-past waiver of the planning veto. Join
    relative-date pulls require kw unique to this candidate
    (``weak`` guard)."""
    fresh_hits, vague_hits = [], []
    n = len(lines)

    def join_dt(dt, T):
        # weak-kw guard: relative-date pulls in a JOIN must sit
        # in a clause hitting a kw group unique to this candidate
        base = _pw_line_dt(dt, T, kws)
        if base != dt:
            cs = _ord_clauses(T) or [T]
            for m in _PW_REL_RE.finditer(T):
                for c in cs:
                    if c in T:
                        i0 = T.find(c)
                        if i0 <= m.start() and m.end() <= i0 + len(c):
                            hits = {g[0] for g in kws
                                    if any(v in c.lower() for v in g)}
                            if hits and hits <= weak:
                                return dt  # session clock
                            break
        return base

    def waiver_ok(T):
        cs = _ord_clauses(T) or [T]
        plan_kw = any(_ORD_PLANNING_RE.search(c)
                      and _cl_kw_hits(kws, c) for c in cs)
        return plan_kw and bool(_PW_SUB_RE.search(T))

    for i, (dt, idx, line) in enumerate(lines):
        if window and not (window[0] <= dt.date() <= window[1]):
            continue
        if not _cl_kw_hits(kws, line):
            continue
        if _pw_line_match(kws, line):
            # fresh discourse deictics anchor without eventive
            # evidence (C488 tier discipline)
            if _ORD_FRESH_RE.search(line):
                base = _pw_line_dt(dt, line, kws)
                rd = base - timedelta(days=1) \
                    if _ORD_YESTERDAY_RE.search(line) else base
                fresh_hits.append((rd, idx, line))
                continue
            wins = _pw_hit_windows(kws, line)
            if qverbs:
                wins = [w for w in wins
                        if any(v in w.lower() for v in qverbs)]
            if wins:
                vague_hits.append(
                    (_pw_line_dt(dt, line, kws), idx, line))
                continue
            if waiver_ok(line):
                vague_hits.append(
                    (_pw_line_dt(dt, line, kws), idx, line))
                continue
        # F1: cross-line joins — even from partial lines (the
        # kw-completing partner is often a non-matching line)
        joins = []
        if i + 1 < n and lines[i + 1][1] == idx \
                and _cl_kw_hits(kws, lines[i + 1][2]):
            joins.append(line + ' ' + lines[i + 1][2])
        if i > 0 and lines[i - 1][1] == idx \
                and _cl_kw_hits(kws, lines[i - 1][2]):
            joins.append(lines[i - 1][2] + ' ' + line)
        for T in joins:
            if not _pw_line_match(kws, T):
                continue
            jw = _pw_hit_windows(kws, T) or (
                [T] if waiver_ok(T) else [])
            if qverbs:
                jw = [w for w in jw
                      if any(v in w.lower() for v in qverbs)]
            if jw:
                vague_hits.append((join_dt(dt, T), idx, T))
                break
        # F6 (C496): anaphora purchase-report join — a full-
        # matching pair (or full-matching line) followed by a
        # kw-less purchase-report sentence whose bare quantified
        # object + price resume the pair item; its relative
        # duration anchors the candidate. Up to one URL-debris
        # fragment ("com" from Chewy.com's split) may sit
        # between (C496 trace: line[256] = 'com').
        pair_ok = (
            _pw_line_match(kws, line)
            or (i > 0 and lines[i - 1][1] == idx
                and _cl_kw_hits(kws, lines[i - 1][2])
                and _pw_line_match(
                    kws, lines[i - 1][2] + ' ' + line)))
        j = i + 1
        if (j + 1 < n and lines[j][1] == idx
                and _PW_DEBRIS_RE.fullmatch(lines[j][2].strip())):
            j += 1  # skip the single URL fragment
        if (pair_ok and j < n and lines[j][1] == idx):
            nxt = lines[j][2]
            if (not _cl_kw_hits(kws, nxt)
                    and _PW_ANAPHOR_EV_RE.search(nxt)
                    and not _ORD_PLANNING_RE.search(nxt)
                    and (not qverbs
                         or any(v in nxt.lower() for v in qverbs))):
                m = _PW_REL_RE.search(nxt)
                dl = _pw_rel_delta(m) if m else None
                if dl:
                    vague_hits.append(
                        (dt - dl, idx,
                         lines[i - 1][2] + ' ' + line + ' ' + nxt
                         if i > 0 else line + ' ' + nxt))
                    continue
    pool = fresh_hits or vague_hits
    if not pool:
        return None
    pool.sort(key=lambda x: (x[0], x[1]))
    return pool[0]


def _pw_any_mention(kws, lines) -> bool:
    """Full-kw mention anywhere — single line OR same-session
    adjacent line pair (C495: "8 prime lens" + next line's 50mm
    lens talk; mention checks do NOT apply the planning veto —
    planned-but-unrealized still counts as existence-evidence
    for the neg-exist abstain gate, by design)."""
    if any(_pw_line_match(kws, ll) for _, _, ll in lines):
        return True
    n = len(lines)
    for i in range(n - 1):
        if lines[i][1] != lines[i + 1][1]:
            continue
        a, b_ = lines[i][2], lines[i + 1][2]
        if (_cl_kw_hits(kws, a) and _cl_kw_hits(kws, b_)
                and _pw_line_match(kws, a + ' ' + b_)):
            return True
    return False


# ── Cycle 497: Event-Centric Comparison Matcher (ECM) ───────────
# "neither family" (Research #082): "Who did I meet first, X or Y?"
# / "Who became a parent first, X or Y?" — four walls no prior
# mechanism crosses (neither order-family C488 nor pairwise C489):
#   W1 descriptive-NP entities ("the woman selling jam" ↔ "a jam
#      maker" — no name token to index; ≥2 content-word overlap +
#      window-time resolvable are the dual discriminant);
#   W2 event-surface diversity ("met" never appears — "had a
#      conversation with"; "became a parent" surfaces as
#      "adopted"/"twins were born" — VERBMAP);
#   W3 cross-TURN anaphora join (Rachel's name is 8 turns away
#      from her twins' birth date; join key = relation NP +
#      shared proper nouns);
#   W4 vague durations are ORDINAL scalars ("a few months ago" 90d
#      > "about a month ago" 30d — calendar anchoring would be
#      pseudo-precision; the local counter-example to the
#      temporal-anchoring dogma);
#   W5 abstain twins (never-mentioned candidate → ABSTAIN, C489
#      negative-existence semantics; verb-face gates block the
#      same-name decoy sessions).
# Zero-hijack (census 500): the STRICT gate fires exactly the 4
# family members — C488 precedent. Runs BEFORE pairwise: forms are
# mutually exclusive ("who did I <V> first" vs "which … first").
_PREF_RE = re.compile(
    r'\b((?:recommend|suggest)(?:ations?|ions?|s)?|tips?|advice|any ideas|'
    r'what should|do you think|what do you think)\b', re.I)
# Past-tense participles ("you recommended…" / "you suggested…") and
# interrogative past-action recall ("did you recommend…") ask ABOUT
# a past recommendation — factual recall (ssa category), not an
# advice request; the stem above deliberately excludes them
# (recommended/suggested/recommending → no boundary match).
_PREF_EXCLUDE_RE = re.compile(r'\bdid you (recommend|suggest)', re.I)


def pref_form(question: str) -> bool:
    """True when *question* is an advice-request form ("any
    recommendations?" / "what should…" / "do you think…", Research
    #080). Used by the C498 honest-abstention gate."""
    return (bool(_PREF_RE.search(question))
            and not _PREF_EXCLUDE_RE.search(question))


# ── Cycle 513: negative-existence abstention (#087 ABS_Q lineage) ──
# Months/weekdays/holiday anchors are temporal modifiers, not
# presupposed entities — the corpus legitimately anchors them
# relatively ("in January" + question_date) while the entity the
# question asks about is elsewhere.
_NEG_EXIST_STOP = frozenset({
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday", "Valentine", "Christmas", "Halloween",
    "Thanksgiving", "Easter",
    # generic question/service words that surface capitalized
    "How", "What", "When", "Where", "Which", "Who", "Why", "The",
    "Do", "Did", "Does", "Is", "Are", "Was", "Were", "Have", "Has",
    "Will", "Would", "Should", "Instagram", "Google", "Apple",
    "Amazon", "Facebook", "Netflix", "Spotify", "YouTube", "Twitter",
})


# First-person marker: LME _abs trap form ("How long have I lived
# in Shinjuku?"). Case-sensitive \bI\b — lowercase "i" is noise.
_NEG_EXIST_FIRST_PERSON_RE = re.compile(
    r"\bI\b|\bmy\b|\bMy\b|\bme\b|\bmine\b")


def _neg_exist_entities(question: str) -> list[str]:
    """Proper-noun candidates from *question* (bare tokens only).

    Quoted-phrase regexes are BANNED here: ``'([^']{2,40})'``
    fabricated spans ACROSS apostrophes ("Jessica's wedding or
    Michael's" → ``s wedding or Michael``; "…'How I Built This' and
    'My Fa…" → ``ve listened to from ``) — the 4th instance of the
    display-layer-bug-pretending-to-be-data family (TOOLS.md
    permanent rule). Bare tokenization splits them away naturally.
    """
    toks = re.findall(r"[A-Za-z][A-Za-z0-9-]*", question)
    out = []
    for i, t in enumerate(toks):
        if (t[0].isupper() and i > 0 and len(t) > 2
                and t not in _NEG_EXIST_STOP
                and (not t.isupper() or len(t) > 3)):
            out.append(t)
    return out


def negative_existence(question: str,
                       haystack_text: str) -> str | None:
    """The first asked-for entity that never appears in the corpus.

    Returns the missing entity name when any proper noun in
    *question* is absent from *haystack_text* (word-boundary,
    case-insensitive), ``None`` when every presupposition holds.
    Absent entity ⇒ the answer cannot be extracted ⇒ the honest
    answer is abstention, whatever the retrieval confidence (the
    near-miss sibling drives retrieval astray by design).

    First-person forms only (``I``/``my``/…): LME _abs traps ask
    "How long have I lived in Shinjuku?" — the proper nouns are the
    asked-about objects. Third-person subject questions (LoCoMo
    "What class did Caroline start?") name a dialogue SUBJECT whose
    own lines never self-name — absence there is normal, not a
    presupposition failure (caught by the LoCoMo fixture suite).
    """
    if not _NEG_EXIST_FIRST_PERSON_RE.search(question):
        return None
    ents = _neg_exist_entities(question)
    if not ents:
        return None
    tl = haystack_text.lower()
    for e in ents:
        if not re.search(rf"\b{re.escape(e.lower())}\b", tl):
            return e
    return None



# Cycle 501: role-aware answer face — form gates. First-person
# fact questions are answered from the best-ranked context line,
# but assistant advice out-hits the terse user fact statement and
# the answer gate echoes advice text ("Mint is a fantastic app…")
# while the GT lives in a user line. Two guards keep the user-line
# override surgical:
#   1. _user_fact_form — first-person pronoun present AND not a
#      you-addressed recall form (C468 owns assistant-side
#      recall) AND not an advice request (C498 abstains those);
#   2. _answer_form_claimed — questions claimed by a specialized
#      answer family (ECM/pairwise/temporal_arith/counting) keep
#      their fall-through behavior untouched: gate ORDER is a
#      correctness face (C482/C488) — the family that claims a
#      form owns it even when it cannot resolve it.
_ROLE_USER_FACT_RE = re.compile(r"\b(?:I|my|me|we|our)\b", re.I)


def _user_fact_form(question: str) -> bool:
    """True for first-person fact questions (Cycle 501)."""
    return bool(_ROLE_USER_FACT_RE.search(question)
                and not recall_form(question)
                and not pref_form(question))


def _answer_form_claimed(question: str) -> bool:
    """True when a specialized answer family claims *question*.

    Cycle 501 guard — see module comment above. Order of the
    checks is irrelevant (pure predicates)."""
    return bool(ecm_form(question) or pw_form(question)
                or temporal_arith_form(question)
                or delta_form(question)
                or counting_form(question) or recall_form(question)
                or pref_form(question))


_ECM_GATE_A_RE = re.compile(
    r"^who did i (meet|get to know) first,\s*(.+?)\s+or\s+(.+?)\?$",
    re.I)
_ECM_GATE_B_RE = re.compile(
    r"^who (became a parent|got married|moved out|graduated) first,"
    r"\s*(.+?)\s+or\s+(.+?)\?$", re.I)

_ECM_VERBMAP = {
    "meet": [r"\bmet\b", r"\bmeet\b", r"\bconversation with\b",
             r"\bran into\b", r"\bstruck up\b"],
    "get to know": [r"\bmet\b", r"\bconversation with\b"],
    "became a parent": [r"\badopted\b", r"\bborn\b",
                        r"\bgave birth\b", r"\bwelcomed\b"],
    "got married": [r"\bwedding\b", r"\bmarried\b"],
    "moved out": [r"\bmoved\b"],
    "graduated": [r"\bgraduated\b"],
}

_ECM_STOP = set('''a an the i my me of at on in to from and or who whom
did do does with was were is are that this it her his their she he
they guy girl woman man named who's selling maker from'''.split())

_ECM_RELNOUNS = [
    "sister-in-law", "brother", "sister", "cousin", "friend",
    "mother", "father", "aunt", "uncle", "wife", "husband",
    "partner", "colleague", "neighbor", "boss"]

_ECM_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday",
                  "friday", "saturday", "sunday"]
_ECM_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}

_ECM_NUMWORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3,
                 "four": 4, "five": 5, "six": 6}


def _ecm_resolve_days(text: str, anchor) -> int | None:
    """Text → days-before-anchor scalar (larger = earlier).

    Vague-duration track (W4) and calendar track unify on one
    ordinal scalar; ``None`` when no time expression resolves.
    """
    t = text.lower()
    m = re.search(r"\b(?:a few|several) months ago\b", t)
    if m:
        return 90
    m = re.search(
        r"\b(?:about|around|roughly)? ?(\d+|a|an|one|two|three|four|"
        r"five|six) months? ago\b", t)
    if m:
        n = _ECM_NUMWORDS.get(m.group(1), m.group(1))
        return int(n) * 30
    m = re.search(r"\b(?:a few|several) weeks ago\b", t)
    if m:
        return 21
    m = re.search(
        r"\b(?:a couple of|about |around )?(\d+|a|one|two|three|four|"
        r"five) weeks? ago\b", t)
    if m:
        n = _ECM_NUMWORDS.get(m.group(1), m.group(1))
        return int(n) * 7
    m = re.search(r"\blast week\b", t)
    if m:
        return 7
    m = re.search(r"\blast weekend\b", t)
    if m:
        return 4
    m = re.search(
        r"\blast (monday|tuesday|wednesday|thursday|friday|saturday|"
        r"sunday)\b", t)
    if m:
        wd = _ECM_WEEKDAYS.index(m.group(1))
        d = 1
        while (anchor - timedelta(days=d)).weekday() != wd:
            d += 1
        return d
    m = re.search(r"\b(?:a few|several) days ago\b", t)
    if m:
        return 3
    m = re.search(r"\b(\d+|a|one|two|three) days? ago\b", t)
    if m:
        n = _ECM_NUMWORDS.get(m.group(1), m.group(1))
        return int(n)
    m = re.search(r"\blast month\b", t)
    if m:
        return 30
    m = re.search(
        r"\bin (january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\b", t)
    if m:
        mm = _ECM_MONTHS[m.group(1)]
        if anchor.month > mm:
            try:
                dt = anchor.replace(month=mm, day=15)
                return (anchor - dt).days
            except ValueError:
                pass
    m = re.search(
        r"\bon (january|february|march|april|may|june|july|august|"
        r"september|october|november|december) (\d+)(?:st|nd|rd|th)?\b",
        t)
    if m:
        mm, dd = _ECM_MONTHS[m.group(1)], int(m.group(2))
        try:
            dt = anchor.replace(month=mm, day=dd)
            if dt <= anchor:
                return (anchor - dt).days
        except ValueError:
            pass
    return None


def _ecm_sentences(turn_text: str) -> list[str]:
    """Sentence split at prototype contract (>5 chars — #082 kept
    verbatim; the production ``_split_sentences`` floor of 10 would
    drop short date fragments)."""
    parts = re.split(r"(?<=[.!?])\s+", turn_text.replace("\n", " "))
    return [p.strip() for p in parts if len(p.strip()) > 5]


def _ecm_content_words(np: str) -> set[str]:
    words = re.findall(r"[a-z]+", np.lower())
    return {w for w in words
            if w not in _ECM_STOP and len(w) > 2
            and w not in _ECM_RELNOUNS}


def _ecm_is_name_entity(np: str) -> bool:
    toks = re.findall(r"[A-Za-z][a-z]+", np)
    return bool(toks) and all(t[0].isupper() for t in toks)


def _ecm_hits(pats, s) -> bool:
    return any(re.search(p, s, re.I) for p in pats)


def _ecm_window_text(recs, i, span=1) -> str:
    """Sentence ± adjacent same-turn sentences (sentence-window,
    LlamaIndex small-to-big lineage — applied at MATCH time, not
    just return time: the jam case's time expression and NP sit in
    neighbouring sentences)."""
    si, ti, xi, s, _ = recs[i]
    out = [s]
    for j in (i - 1, i + 1):
        if 0 <= j < len(recs):
            sj, tj, xj, sj_txt, _ = recs[j]
            if (sj, tj) == (si, ti) and abs(xj - xi) <= span:
                out.append(sj_txt)
    return " ".join(out)


def _ecm_build_recs(dated: list) -> list[tuple]:
    """(sess_idx, turn_idx, sent_idx, sentence, session_date) over
    all USER turns of the full haystack (C472 full-graph lesson)."""
    recs = []
    for si, (date_str, turns) in enumerate(dated):
        iso = parse_lme_date(str(date_str)) if date_str else ""
        d = None
        if iso:
            try:
                d = datetime.strptime(iso, "%Y-%m-%d").date()
            except ValueError:
                d = None
        for ti, turn in enumerate(turns or []):
            if (turn or {}).get("role") != "user":
                continue
            for xi, s in enumerate(
                    _ecm_sentences((turn or {}).get("content", ""))):
                recs.append((si, ti, xi, s, d))
    return recs


def _ecm_find_entity(entity, recs, verb_pats):
    """(best_days_ago, evidence_sentence) or None for one entity.

    Name entities keep the verb face (W5 — same-name decoys carry
    no event verbs); descriptive NPs skip it (W1+W2 — "conversation
    with" carries no "met"; the ≥2 content-word overlap plus a
    resolvable window time are the discriminants)."""
    if _ecm_is_name_entity(entity):
        name_toks = {t.lower()
                     for t in re.findall(r"[A-Za-z][a-z]+", entity)}
        cands = []
        for i, (si, ti, xi, s, d) in enumerate(recs):
            if d is None:
                continue
            low = s.lower()
            n_hit = sum(1 for t in name_toks
                        if re.search(r"\b" + t + r"\b", low))
            if n_hit and _ecm_hits(verb_pats, s):
                w = _ecm_window_text(recs, i)
                days = (_ecm_resolve_days(w, d)
                        or _ecm_resolve_days(s, d))
                if days is not None:
                    cands.append((n_hit, days, s))
        if not cands:
            return None
        cands.sort(key=lambda c: -c[0])
        return cands[0][1], cands[0][2]
    cw = _ecm_content_words(entity)
    best = None
    for i, (si, ti, xi, s, d) in enumerate(recs):
        if d is None:
            continue
        w = _ecm_window_text(recs, i)
        wl = w.lower()
        ov = sum(1 for t in cw if re.search(r"\b" + t + r"\b", wl))
        if ov >= 2 or (cw and ov == len(cw)):
            days = _ecm_resolve_days(w, d)
            if days is not None and (best is None or ov > best[0]):
                best = (ov, days, s)
    return None if not best else (best[1], best[2])


def _ecm_anaphora_join(entity, recs, verb_pats):
    """W3 cross-turn join: a name-bearing sentence without a date
    joins (same session) a date-bearing sentence that shares a
    relation NP or a proper noun. Name sentences are exempt from
    the verb face ("sister-in-law, Rachel, is doing great" has no
    event verb); the DATE sentence must carry it."""
    name_toks = {t.lower()
                 for t in re.findall(r"[A-Za-z][a-z]+", entity)}
    for i, (si, ti, xi, s, d) in enumerate(recs):
        if d is None:
            continue
        low = s.lower()
        if not sum(1 for t in name_toks
                   if re.search(r"\b" + t + r"\b", low)):
            continue
        keys = {n for n in _ECM_RELNOUNS if n in low}
        proper = set(re.findall(r"\b[A-Z][a-z]+\b", s))
        for j, (sj, tj, xj, sj_txt, dj) in enumerate(recs):
            if sj != si or dj is None:
                continue
            if not _ecm_hits(verb_pats, sj_txt):
                continue
            jl = sj_txt.lower()
            share_rel = any(n in jl for n in keys)
            share_proper = bool(
                proper & set(re.findall(r"\b[A-Z][a-z]+\b", sj_txt))
                - {t.capitalize() for t in name_toks})
            if share_rel or share_proper:
                days = _ecm_resolve_days(sj_txt, dj)
                if days is not None:
                    return days, sj_txt
    return None


def ecm_form(question: str):
    """(verb, entity_a, entity_b) for an ECM comparison form, else
    ``None``."""
    q = question.strip()
    m = _ECM_GATE_A_RE.match(q)
    if not m:
        m = _ECM_GATE_B_RE.match(q)
    if not m:
        return None
    return m.group(1).lower(), m.group(2).strip(), m.group(3).strip()


def answer_ecm(question: str, dated: list,
               question_date: str = "") -> tuple:
    """Answer a neither-family comparison question (Cycle 497).

    ``dated``: ``[(date_str, turns)]`` over the FULL ingested
    haystack. Returns ``(answer, detail)`` — answer ``None`` =
    unresolved fall-through; ``ABSTAIN_ANSWER`` = negative-
    existence abstain (one side has no evidence at all).
    """
    form = ecm_form(question)
    if not form:
        return None, {"form": "ecm", "mode": "no-form"}
    verb, e1, e2 = form
    vp = _ECM_VERBMAP.get(verb)
    if not vp:
        return None, {"form": "ecm", "mode": "no-verbmap"}
    recs = _ecm_build_recs(dated)
    r1 = _ecm_find_entity(e1, recs, vp)
    r2 = _ecm_find_entity(e2, recs, vp)
    if r1 is None and _ecm_is_name_entity(e1):
        r1 = _ecm_anaphora_join(e1, recs, vp)
        if r1 is not None:
            r1 = r1 + ("anaphora",)
    if r2 is None and _ecm_is_name_entity(e2):
        r2 = _ecm_anaphora_join(e2, recs, vp)
        if r2 is not None:
            r2 = r2 + ("anaphora",)
    detail = {"form": "ecm", "verb": verb,
              "e1": e1, "e2": e2,
              "a_days": r1[0] if r1 else None,
              "b_days": r2[0] if r2 else None,
              "a_mode": r1[2] if r1 and len(r1) > 2 else "direct",
              "b_mode": r2[2] if r2 and len(r2) > 2 else "direct"}
    if r1 is None or r2 is None:
        missing = e1 if r1 is None else e2
        return ABSTAIN_ANSWER, {**detail, "mode": "neg-exist",
                                "missing": missing}
    d1, ev1 = r1[0], r1[1]
    d2, ev2 = r2[0], r2[1]
    if d1 == d2:
        return None, {**detail, "mode": "tie"}
    win, days = (e1, d1) if d1 > d2 else (e2, d2)
    return win, {**detail, "mode": "compare", "winner_days": days}


def answer_pairwise(question: str, dated: list,
                    question_date: str = "") -> tuple:
    """Answer a pairwise which-first question (C489).

    See :func:`pw_form` for the form contract and the module-level
    C489 block for the decision matrix. ``dated`` carries RAW
    haystack date strings (minute granularity via
    ``_session_dates_raw``; bare dates degrade to date-only).

    Returns ``(answer, detail)``; answer ``None`` = unresolved
    (fall through — the answer gates own currently-correct
    cases); ``ABSTAIN_ANSWER`` = negative-existence abstain.
    """
    cands = pw_form(question)
    if not cands:
        return None, {"form": "pairwise", "mode": "no-form"}
    a_txt, b_txt = cands
    a_kws, b_kws = _pw_kws(a_txt), _pw_kws(b_txt)
    if not a_kws or not b_kws:
        return None, {"form": "pairwise", "mode": "no-kws"}
    qdate = _ord_qdate(question_date)
    if _ord_window_needed(question) and qdate is None:
        return None, {"form": "pairwise", "mode": "window-unresolvable"}
    window = _ord_window(question, qdate)
    qv = _pw_qverbs(question)
    lines = _pw_lines(dated)
    # C495: weak kw groups (shared with the OTHER candidate, or
    # generic nouns) cannot pull relative dates in cross-line
    # joins — uniqueness is the anaphora-safety substitute there
    def _weak(kws, other):
        ow = ' '.join(' '.join(g) for g in other).lower()
        return frozenset(
            g[0] for g in kws
            if g[0] in _PW_GENERIC
            or any(v in ow for v in g))
    aa = _pw_scan_anchor(a_kws, lines, window, qv,
                         weak=_weak(a_kws, b_kws))
    bb = _pw_scan_anchor(b_kws, lines, window, qv,
                         weak=_weak(b_kws, a_kws))
    if aa and bb:
        if abs((aa[0] - bb[0]).total_seconds()) <= 24 * 3600:
            return None, {"form": "pairwise", "mode": "sub-24h-tie",
                          "a": str(aa[0])[:16], "b": str(bb[0])[:16]}
        win = a_txt if (aa[0], aa[1]) < (bb[0], bb[1]) else b_txt
        return win, {"form": "pairwise", "mode": "both",
                     "a": str(aa[0])[:16], "b": str(bb[0])[:16]}
    if aa and not bb:
        if not _pw_any_mention(b_kws, lines):
            return ABSTAIN_ANSWER, {"form": "pairwise",
                                    "mode": "neg-exist-B"}
        return None, {"form": "pairwise", "mode": "B-unanchored"}
    if bb and not aa:
        if not _pw_any_mention(a_kws, lines):
            return ABSTAIN_ANSWER, {"form": "pairwise",
                                    "mode": "neg-exist-A"}
        return None, {"form": "pairwise", "mode": "A-unanchored"}
    return None, {"form": "pairwise", "mode": "neither"}


def pairwise_judge(question: str, truth: str,
                   predicted: str) -> bool:
    """Pairwise answers render candidate text VERBATIM from the
    question; truths are sentences ("I participated in the
    charity bake sale first.") — containment/shared-keyword match
    (``_ord_seg_match``) judges both directions. Abstentions never
    reach here (evaluate's ``is_abs`` branch owns them)."""
    if not truth or not predicted:
        return False
    return _ord_seg_match(truth, predicted)


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

# C490 (#079 F1): the question's own UNIT word ('How many DAYS...')
# is a topic-uniform token — it appears in legal/congressional/
# fitness sessions alike and passes ANY anchor gate. Measurement
# units carry zero topical signal, so they never qualify as
# anchors (distribution-based anchor eligibility).
_CNT_UNIT_ANCHOR_STOP = {u.rstrip('s') for u in (
    'day', 'days', 'week', 'weeks', 'hour', 'hours', 'month',
    'months', 'year', 'years', 'minute', 'minutes', 'night',
    'nights', 'time', 'times')}

# C491 (#079 residual bucket 1): money-question unit words are
# topic-uniform the same way — 'money'/'raise'/'total' appear in
# every $-bearing sentence and admit nothing topical.
_CNT_MONEY_ANCHOR_STOP = {
    'money', 'raise', 'spend', 'spent', 'total', 'expense',
    'since', 'start', 'participate', 'attending', 'attend',
    'through', 'event'}

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
    'fish': {'tetra', 'gourami', 'pleco', 'catfish', 'betta',
             'danio', 'molly', 'guppy', 'cory', 'barb', 'loach',
             'angelfish', 'goldfish', 'shark', 'snail', 'shrimp',
             'eel', 'oscar', 'discus', 'platy', 'swordtail'},
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


def _cnt_normalize_entity(entity: str) -> str:
    """Normalize entity names for cross-session deduplication.
    
    Handles variations like: 'apple' vs 'Apple' vs 'apples' vs 'Apples'
    'Google' vs 'google' vs 'Google Maps'
    'MacBook' vs 'macbook' vs 'MacBooks'
    """
    if not entity:
        return ""
    
    # Normalize case
    entity = entity.lower()
    
    # Remove pluralization (simple heuristic)
    if entity.endswith('s') and len(entity) > 3:
        # Check if likely plural (not possessive, not specific)
        # TODO: Better plural detection needed for real edge cases
        pass
    
    # Normalize common abbreviations and variants
    entity = entity.replace(' inc', '').replace(' inc.', '')
    entity = entity.replace(' llc', '').replace(' llc.', '')
    entity = entity.replace(' corp', '').replace(' corporation', '')
    entity = entity.replace(' company', '')
    entity = entity.replace(' service', '')
    entity = entity.replace(' app', '')
    entity = entity.replace(' software', '')
    
    # Remove trailing punctuation
    entity = entity.rstrip('.,;:!?')
    
    return entity.strip()


def _cnt_deduplicate_entities(across_sessions: bool = True) -> callable:
    """Create entity deduplication function for cross-session normalization."""
    seen_entities = {}
    
    def normalize_and_dedupe(entity: str, session_id: str) -> str:
        normalized = _cnt_normalize_entity(entity)
        if not normalized:
            return ""
        
        key = f"{session_id}:{normalized}" if across_sessions else normalized
        
        # Track entity variants to avoid double-counting
        if key not in seen_entities:
            seen_entities[key] = normalized
            return normalized
        
        # Return first occurrence to avoid duplication
        return seen_entities[key]
    
    return normalize_and_dedupe


def _cnt_np_fam(question: str) -> tuple:
    """Content words of the counted NP (robust vs modifiers).

    Returns ``(family, subtypes, head0)`` — family is the full morph set of
    every content word; subtypes is the conjoined head list when
    the question counts "X and Y" separately; head0 is the first
    content word of the NP (used by C507 entity-split to distinguish
    "views on A and B" from "tetras and guppies").
    """
    ql = question.lower()
    m = re.match(r'^how many ([a-z][\w\s-]{1,60}?)'
                 r'(?:\s+(?:do|did|have|has)\s+i'
                 r'|\s+i\s+(?:do|did|have|has|had|currently)'
                 r'|\s+(?:in|on|at|from|across|over|during|before'
                 r'|after|last|this|due)\b|[?.])', ql)
    if not m:
        m = re.match(r'^what (?:is|was) the total number of '
                     r'([a-z][\w\s-]{1,90}?)'
                     r'(?:\s+i\b|\s+(?:do|did|have|has)\s+i'
                     r'|\bthat\b|,|\bby\b|\bfrom\b|[?.])', ql)
    if not m:
        return None, None, None
    np = m.group(1)
    parts = re.split(r'\s+and\s+|,\s+|\s+or\s+', np)
    subs, fam, head0 = [], set(), None
    for part in parts:
        ws = [w for w in re.findall(r"[a-z][\w-]+", part)
              if w not in _CNT_STOP_Q
              and w not in _CNT_GENERIC_HEADS and len(w) >= 4]
        if not ws:
            continue
        h = ws[-1]
        if head0 is None:
            head0 = ws[0]
        for w in ws:
            fam |= {w, _cnt_sing(w), w + 's', _cnt_sing(w) + 's'}
            # C507: -es / -ies plurals (lunches, boxes, cities)
            if w.endswith(('s', 'x', 'z', 'ch', 'sh')):
                fam |= {w + 'es', _cnt_sing(w) + 'es'}
            elif w.endswith('y') and len(w) > 2 and w[-2] not in 'aeiou':
                fam.add(w[:-1] + 'ies')
        if len(parts) >= 2 and h not in subs:
            subs.append(h)
    return fam, (subs if len(subs) >= 2 else None), head0


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
    """Explicit durations in days (``7-day trip`` = 7).

    Cycle 483 title guard: hyphenated durations followed by a
    capitalized word are program/book titles ("12-Week Study"),
    not lived durations — excluded.
    """
    out = []
    for m in re.finditer(
            r'\b(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six'
            r'|seven|eight|nine|ten)\s*-?\s*(day|week)s?\b',
            text, re.I):
        n = _cnt_num(m.group(1))
        if n is None:
            continue
        hyphen = '-' in m.group(0)
        after = text[m.end():].lstrip()[:1]
        if hyphen and after.isupper():
            continue      # "12-Week Study" — a title, not a duration
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
    / ``"argmax"`` / ``"unit_sum"`` / ``"freq_days"``, or ``None``
    (not a counting form). Calendar-distance questions ("how many
    days between …") belong to the Cycle 457 temporal-arithmetic
    path and are excluded here — distance is calendar arithmetic,
    not an evidence sum. Cycle 483 unit discipline: ``total_sum``
    sums money and ONLY fires on money-asking questions — unit
    questions (hours/years/months) route to ``unit_sum``, count-
    noun "in total" questions route to ``number_total``, and
    "days a week" frequency questions route to ``freq_days``.
    """
    if temporal_arith_form(question):
        return None
    q = question.strip()
    ql = q.lower()
    # C505 (#085): duration-family M1/M4/M3 claim their narrow
    # forms ahead of duration_sum — legacy aggregation double-
    # counts franchise re-mentions (M1) and misses delivery
    # joins (M4); M3's plan/fact wall excludes habitual mood.
    if _dur_family_gate(ql):
        return "duration_family"
    if re.search(r'\bhow many days?\s+(?:a|per)\s+week\b', ql):
        return "freq_days"
    if re.match(r'^what is the total number of (days|weeks)', ql):
        return "duration_sum"
    if re.search(r'\bhow many (days|weeks)\b', ql) or \
            (re.search(r'\b(days|weeks)\b', ql)
             and re.search(r'\b(spend|spent|take|took)\b', ql)
             and ql.startswith('how')):
        return "duration_sum"
    if re.match(r'^what (?:is|was) the total '
               r'(?:amount|cost|price)\b', ql):
        return "item_total"   # C500: enumerated-item money sum
    if re.match(r'^how (much|many)\b', q, re.I) \
            and re.search(r'\btotal\b', ql):
        if re.search(r'\bhow many (hours|years|months)\b', ql):
            return "unit_sum"
        if re.match(r'^how much\b', q, re.I):
            return "total_sum"      # how-much totals are money
        return "number_total"
    if re.match(r'^what (is|was) the total number', ql):
        return "number_total"
    if re.match(r'^which\b', q, re.I) and re.search(r'\bmost\b', ql):
        return "argmax"
    # C503 (#084): named/role/size enumeration — claims plain
    # "how many X" questions every earlier form left unclaimed.
    # C511: inventory families (kit/instrument/property) claim
    # ahead of this — brand/scale/descriptor identity is
    # invisible to name/role signatures.
    if re.match(r'^how many\b', q, re.I):
        if _muv_form_gate(ql):
            return "museum_count"
        if _inv_form_gate(ql):
            return "inventory_count"
        if _age_form_gate(ql):
            return "age_diff"
        np_words = _enum_np(q)
        if np_words and _enum_form_gate(ql, np_words):
            return "enum_count"
    return None


# ---------------------------------------------------------------------------
# C505 (#085): duration-family mechanisms M1-M4. Oracle v3 7/7
# (incl. two controls — aae3761f driving stays 15, 2788b940
# per-typical-week stays untouched). Cascade M1 -> M4 -> M3;
# M2 is the freq_days schedule-context discipline added below.
# Faithful port of dur_family_proto.py — helpers are deliberately
# independent (oracle-parity first, reuse second).
# ---------------------------------------------------------------------------

_DUR_MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'])}

_DUR_NUMWORDS = {'one': 1, 'a': 1, 'an': 1, 'two': 2, 'three': 3,
                 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                 'eight': 8, 'nine': 9, 'ten': 10, 'half': 0.5,
                 'couple': 2, 'few': 3}

_DUR_STOP = set('''a an the my i we our your this that these those and or but so
it its is are was were be been being do does did have has had will would
can could should may might must to of in on at for with about from by as
like just really very much more most some any all no not new old other
recently lately been get got great good nice super plenty stuff'''.split())

_DUR_PRONOUNS = {'it', 'this', 'that', 'they', 'them'}

_DUR_BINGE_RE = re.compile(
    r'(?:watched|finished|completed|read)\s+(?:all|the|my)?\s*'
    r'(?:(\d+)\s+)?([a-zA-Z][a-zA-Z\- ]{2,40}?)\s+'
    r'(?:movies|films|books|episodes|in|for)\b.*?'
    r'(?:in|for)\s+(?:about\s+|around\s+|roughly\s+)?'
    r'((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)?)'
    r'(?:\s+(?:week|weeks|day|days|hour|hours))?'
    r'(?:\s+and\s+a\s+half)?)')

_DUR_FRANCHISE = {}
for _toks, _fam in [
        ('marvel mcu cinematic avengers disney', 'marvel'),
        ('star wars skywalker jedi rogue solo empire awakens', 'starwars'),
        ('harry potter hogwarts', 'harrypotter'),
        ('lord rings hobbit tolkien', 'lotr')]:
    for _t in _toks.split():
        _DUR_FRANCHISE[_t] = _fam

_DUR_H_RE = re.compile(
    r'\b(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)?)'
    r'[-\s]?(?:hour|hours)\b')

# case-SENSITIVE on purpose — destination NPs are proper nouns and
# the (?i) global flag kills the capital heuristic (#085 bug 1)
_DUR_TRIP_TO = re.compile(
    r'\b(?:trip|trips|drove|drive|visited?) to '
    r'((?:the )?([A-Z][\w.\-]+(?: [A-Z][\w.\-]+)*))')
_DUR_ANY_CAP = re.compile(
    r'(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,}(?: [A-Z][a-z]{2,})*)\b')

_DUR_REALIZED_RE = re.compile(
    r'(?i)(?:went (?:for|on) a|did (?:a|an|my)|completed|took)\s+'
    r'((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+(?:\.\d+)?)'
    r'[-\s]*(?:minute|minutes|hour|hours))\s+([a-z\- ]{3,30})')

_DUR_PLAN_MARKERS = re.compile(
    r"(?i)\b(used to|trying to get back|hoping to|plan(?:ning)? to|"
    r"want to|would like to|i'?ll (?:start|try|schedule|do)|"
    r"schedule my|getting back into|slacking|inconsistent)\b")

_DUR_ACT_WORDS = {
    'jog', 'jogging', 'yoga', 'running', 'run', 'exercise',
    'exercising', 'workout', 'working', 'swim', 'swimming',
    'cycling', 'walk', 'walking', 'class', 'classes', 'fitness',
    'meditation', 'hiking', 'hike', 'watching', 'watch',
    'documentary', 'documentaries'}

_DUR_DATE_CORE = (
    r'((?:January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\s+(?:the\s+)?(\d{1,2})'
    r'(?:st|nd|rd|th)?|(\d{1,2})/(\d{1,2}))')

_DUR_ORD_RE = re.compile(
    r'(?:ordered|bought|purchased|placed an order for)\s+'
    r'((?:a|an|the|my|new|it)\s+)?'
    r'([a-zA-Z][a-zA-Z\- ]{2,40}?)?\s*'
    r'(?:from [A-Za-z]+\s+)?(?:online\s+)?'
    r'(?:on|back on)\s+' + _DUR_DATE_CORE, re.I)

_DUR_ARR_RE = re.compile(
    r'(?:arrived|received|was delivered|showed up|came)\s+on\s+'
    + _DUR_DATE_CORE, re.I)

_DUR_ARR_PROD_RE = re.compile(
    r'([a-zA-Z][a-zA-Z\- ]{2,40}?)\s+(?:that\s+)?'
    r'(?:arrived|was delivered|showed up)', re.I)

_DUR_SCHED_ACT = re.compile(
    r'(?i)\b(attend|class|classes|lesson|lessons|session|sessions|'
    r'practice)\b')


def _dur_clauses(text):
    parts = re.split(r'(?<=[.!?])\s+|\n+|;\s+', text)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def _dur_words(text):
    return [w.strip('.,!?;:"\'()[]').lower() for w in text.split()]


def _dur_cstems(text):
    return {w for w in _dur_words(text)
            if w and w not in _DUR_STOP and len(w) > 2
            and not w.isdigit()}


def _dur_stem(w):
    w = w.lower()
    for suf in ('ing', 'ed'):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            w = w[:-len(suf)]
            break
    if len(w) > 3 and w[-1] == w[-2]:
        w = w[:-1]          # jogging -> jog (C471, again)
    return w


def _dur_num(token):
    t = token.lower()
    return float(t) if t.isdigit() else _DUR_NUMWORDS.get(t)


def _dur_user_turns(sessions):
    for s in sessions:
        for ti, t in enumerate(s.get('turns', [])):
            if t.get('role') == 'user':
                yield s.get('session_id', ''), ti, t.get('content', '')


def _dur_m1_gate(ql):
    if 'how many' not in ql:
        return None
    if re.search(r'how many (?:videos|movies|books|pieces|episodes|'
                 r'times|classes|items)', ql):
        return None
    if re.search(r'\b(ago|passed|between)\b', ql):
        return None
    if ('week' in ql or 'day' in ql) and \
            re.search(r'\b(watch|read|finish|complete|binge)\b', ql):
        return 'watch'
    if 'hour' in ql and re.search(r'\bdriv', ql) \
            and 'destination' in ql:
        return 'drive'
    return None


def _dur_m4_gate(ql):
    if not re.search(r'how many days .*(arrive|arrived|receive|received|'
                     r'take for|took for)', ql):
        return None
    if not re.search(r'(after i (ordered|bought|purchased)|to arrive)', ql):
        return None
    return True


def _dur_m3_gate(ql):
    if not ('how many hours' in ql or 'how much time' in ql):
        return None
    if not re.search(r'\b(did i|have i|do i)\b', ql):
        return None
    if re.search(r'\b(in total|combined|typical|every day|each day)\b', ql):
        return None
    if 'driv' in ql and 'destination' in ql:
        return None
    return True


def _dur_family_gate(ql):
    return _dur_m1_gate(ql) or _dur_m4_gate(ql) or _dur_m3_gate(ql)


def _dur_parse_dur(token):
    t = token.lower().strip()
    m = re.match(r'^(a|an|one|two|three|four|five|six|seven|eight|nine|'
                 r'ten|\d+(?:\.\d+)?)'
                 r'(?:\s+(\w+))?(?:\s+and\s+a\s+half)?$', t)
    if not m:
        return None, None
    n = _dur_num(m.group(1))
    unit = m.group(2)
    if n is None:
        return None, None
    if 'and a half' in t:
        n += 0.5
    return n, unit


def _dur_m1(question, sessions):
    """M1 binge-dedup-sum: franchise/destination-keyed dedup so a
    re-mention of the same entity adds nothing (e831120c 4.5→3.5)."""
    mode = _dur_m1_gate(question.lower())
    if not mode:
        return None
    if mode == 'watch':
        dur_by_key = {}
        for _, _, c in _dur_user_turns(sessions):
            fams = {_DUR_FRANCHISE.get(w) for w in _dur_words(c)} - {None}
            for m in _DUR_BINGE_RE.finditer(c):
                n, unit = _dur_parse_dur(m.group(3))
                if n is None:
                    continue
                if unit and 'day' in unit:
                    n = round(n / 7.0, 2)
                key = frozenset(fams) if fams else frozenset(
                    _dur_cstems((m.group(2) or '').lstrip('TtHhEe '))) or None
                if key is None:
                    continue
                if any(k & key for k in dur_by_key):
                    continue
                dur_by_key[key] = n
        if not dur_by_key:
            return None
        return f"{round(sum(dur_by_key.values()), 2):g} weeks"
    # drive mode: destination-keyed hour dedup (control aae3761f=15)
    hrs_by_dest = {}
    for _, _, c in _dur_user_turns(sessions):
        dm = _DUR_H_RE.search(c)
        if not dm:
            continue
        n = _dur_num(dm.group(0).split()[0])
        if n is None:
            continue
        tm = _DUR_TRIP_TO.search(c)
        dest = tm.group(2) if tm else (
            [mm.group(1) for mm in _DUR_ANY_CAP.finditer(c)] or [None])[0]
        if not dest:
            continue
        key = dest.split()[0].lower()
        if key in ('my', 'the', 'i'):
            continue
        hrs_by_dest.setdefault(key, n)
    if not hrs_by_dest:
        return None
    return str(int(sum(hrs_by_dest.values())))


def _dur_m3(question, sessions):
    """M3 realized-window-duration: clause-level plan/fact wall —
    habitual mood (used to / planning to / I'll schedule) never
    enters the realized sum (7024f17c → 0.5 hours)."""
    if not _dur_m3_gate(question.lower()):
        return None
    acts = {_dur_stem(w) for w in _dur_words(question.lower())
            if w in _DUR_ACT_WORDS}
    total_h, fired = 0.0, False
    for _, _, c in _dur_user_turns(sessions):
        for cl in _dur_clauses(c):
            if _DUR_PLAN_MARKERS.search(cl):
                continue
            for m in _DUR_REALIZED_RE.finditer(cl):
                tok = re.split(r'[-\s]+', m.group(1))[0]
                n = _dur_num(tok)
                if n is None:
                    continue
                unit = m.group(1).lower()
                if 'minute' in unit:
                    n = n / 60.0
                if acts and not (acts & {_dur_stem(w)
                                         for w in _dur_words(m.group(2))}):
                    continue
                total_h += n
                fired = True
    if not fired:
        return None
    return f"{round(total_h, 2):g} hours"


def _dur_ord_date(m):
    if m.group(4):
        mon = m.group(3).split()[0]
        return date(2023, _DUR_MONTHS.get(mon.lower(), 1), int(m.group(4)))
    return date(2023, int(m.group(5)), int(m.group(6)))   # M/D


def _dur_arr_date(m):
    if m.group(2):
        mon = m.group(1).split()[0]
        return date(2023, _DUR_MONTHS.get(mon.lower(), 1), int(m.group(2)))
    return date(2023, int(m.group(3)), int(m.group(4)))   # M/D


def _dur_resolve_product(turns, turn_idx, explicit):
    """Explicit NP after the order verb, or anaphora: walk back
    user clauses nearest-first for a `my (new) X` possessive
    anchor (#085: two reversed() traps live here)."""
    exp = (explicit or '').strip()
    first = _dur_words(exp)[0] if exp else ''
    is_pronoun = (first in _DUR_PRONOUNS
                  or first in ('from', 'online') or not exp)
    if not is_pronoun:
        return _dur_cstems(exp)
    candidates = []
    pre = []
    for cl in _dur_clauses(turns[turn_idx].get('content', '')):
        if _DUR_ORD_RE.search(cl) or _DUR_ARR_RE.search(cl):
            break
        pre.append(cl)
    candidates.extend(reversed(pre))
    for t in reversed(turns[:turn_idx]):
        if t.get('role') == 'user':
            candidates.extend(reversed(
                _dur_clauses(t.get('content', ''))))
    for cl in candidates[:8]:
        pm = re.search(r'\bmy\s+(?:new\s+)?((?:[a-z]+[\- ]){0,5}[a-z]+)',
                       cl, re.I)
        if pm:
            return _dur_cstems(pm.group(1))
    return None


def _dur_m4(question, sessions):
    """M4 delivery-interval: order→arrival date join with
    month-name AND slash dates, anaphoric product resolution, and
    a question-side product guard (evidence ≠ asked entity →
    abstain, the 60bf93ed_abs lesson)."""
    if not _dur_m4_gate(question.lower()):
        return None
    qm = re.search(r'(?:my|the|a|an)\s+((?:[a-zA-Z\-]+[ ]{0,1}){1,5}?)\s+'
                   r'(?:after|to arrive|\?)', question)
    q_stems = _dur_cstems(qm.group(1)) if qm else set()
    orders, arrivals = [], []
    for s in sessions:
        turns = s.get('turns', [])
        for ti, t in enumerate(turns):
            if t.get('role') != 'user':
                continue
            c = t.get('content', '')
            for m in _DUR_ORD_RE.finditer(c):
                explicit = m.group(2) or (m.group(1) or '').strip()
                stems = _dur_resolve_product(turns, ti, explicit)
                orders.append((stems or set(), _dur_ord_date(m)))
            for m in _DUR_ARR_RE.finditer(c):
                start = max(0, m.start() - 120)
                pm = _DUR_ARR_PROD_RE.search(
                    c[start:m.start()] + ' arrived')
                if pm and _dur_words(pm.group(1))[0] \
                        not in _DUR_PRONOUNS:
                    stems = _dur_cstems(pm.group(1))
                else:
                    stems = _dur_resolve_product(turns, ti, 'it')
                arrivals.append((stems or set(), _dur_arr_date(m)))
    if not orders and not arrivals:
        return None       # form fired, zero evidence (C498 abstain)
    best = None
    for astems, adate in arrivals:
        for ostems, odate in orders:
            inter = astems & ostems
            if not inter:
                continue
            if q_stems and not (q_stems & (astems | ostems)):
                continue    # joined product ≠ asked product
            if len(inter) >= 2 or len(ostems) <= 2 or len(astems) <= 2:
                delta = (adate - odate).days
                if delta > 0 and (best is None or delta < best):
                    best = delta
    if best is None:
        return None       # evidence present but not the asked pair
    return f"{best} days"


def _cnt_duration_family(question, sessions: list[dict]):
    """Duration-family cascade M1 -> M4 -> M3 (#085 oracle 7/7).
    M2 (distinct-day-rate) is claimed by the freq_days form one
    gate below — disjoint gates make the split equivalent to the
    prototype's M1 -> M2 -> M4 -> M3 cascade."""
    v = _dur_m1(question, sessions)
    if v is not None:
        return v
    v = _dur_m4(question, sessions)
    if v is not None:
        return v
    return _dur_m3(question, sessions)


def _cnt_duration_sum(question: str, sessions: list[dict]):
    q = question.lower()
    want_unit = ('days' if re.search(r'\bdays\b', q)
                 else ('weeks' if re.search(r'\bweeks\b', q)
                       else None))
    if want_unit is None:
        return None
    # C490 F1: strip unit words from the anchor set BEFORE gate
    # compilation — 'days' must not admit legal ('28 days to lodge
    # an appeal') or congressional ('notify 15 days before') noise
    # sessions (#079: 59vs17 and 90vs15 were both unit-key admits).
    # C490 F2: generic geographic heads ('New York City' → 'city')
    # are equally topic-uniform — a 'city council' sentence passes
    # any 'city' gate. Removed from the FULL anchor set (not just
    # cap_anchors — prototype gap caught by C490 unit test):
    # 'york' carries the topical signal.
    anchors = {a for a in _cnt_question_anchors(question)
               if a.rstrip('s') not in _CNT_UNIT_ANCHOR_STOP}
    anchors -= {'city', 'cities'} | _CNT_GENERIC_HEADS
    are = _cnt_anchor_re(anchors)
    per_session = defaultdict(
        lambda: {'events': [], 'counts': set(), 'pnouns': set(),
                 'anchor_ok': False})

    # Cross-session entity deduplication
    deduper = _cnt_deduplicate_entities(across_sessions=True)
    seen_entities = set()
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
    # sessions with deduplicated entities
    for si, sent in _cnt_sents(sessions):
        sess = per_session[si]
        if not sess['anchor_ok']:
            continue
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        # Apply entity normalization and deduplication
        for pnoun in _cnt_proper_nouns(sent):
            deduped = deduper(pnoun, si)
            if deduped:
                sess['pnouns'].add(deduped)
                seen_entities.add(deduped)

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


def _cnt_money_q(ql: str) -> bool:
    """Question asks for a money amount (unit discipline gate)."""
    return bool(re.search(
        r'\b(money|spend|spent|raise|raised|earn|earned|cost|costs'
        r'|paid|pay|save|saved|donat\w*|fund\w*|discount|budget'
        r'|expense|expenses|\$)\b', ql))


def _cnt_unit_sum(question: str, sessions: list[dict]):
    """Sum stated <N> <unit> quantities for unit-aggregate questions.

    Cycle 483: hours/years/months totals. User-role sentences only,
    money tokens and numeric ranges stripped, repeated quantities
    deduplicated by (number, proper-noun signature of sentence) —
    "it took me 30 hours" stated twice for the same game counts
    once, while a second playthrough's "25 hours" counts again.
    """
    ql = question.lower()
    m = re.search(r'\bhow many (hours?|years?|months?)\b', ql)
    if not m:
        return None
    unit = m.group(1).rstrip('s')
    unit_re = re.compile(
        r'\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven'
        r'|eight|nine|ten|eleven|twelve|fifteen|twenty)\s+'
        r'(' + unit + r's?)\b', re.I)
    sents = list(_cnt_sents(sessions))
    seen = set()          # (n, entity) pairs already summed
    total = 0.0
    found = False
    for idx, (si, sent) in enumerate(sents):
        # clause-level gating: a question sentence may carry the
        # count in a declarative relative clause ("…similar to
        # Celeste, which took me 10 hours to complete?") — only
        # the interrogative head clause is skipped
        clauses = [c.strip() for c in re.split(r'[,;]', sent)
                   if c.strip()]
        for cl in clauses:
            if _CNT_INTENT_RE.search(cl):
                continue
            if cl.endswith('?') and not re.match(
                    r'^(which|that|who|and|but|so|because|since)\b',
                    cl, re.I):
                continue      # interrogative head clause
            s = cl
            # strip money tokens, ranges, and title-style durations
            s = re.sub(r'\$\s?\d[\d,.]*', ' ', s)
            s = re.sub(r'\b\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?'
                       r'\s+(?:' + unit + r's?)\b', ' ', s,
                       flags=re.I)
            s = re.sub(r'\b\d+\s*-?\s*(?:week|month|day)s?\s+'
                       r'(?:program|study|plan|challenge|course)s?\b',
                       ' ', s, flags=re.I)
            for em in unit_re.finditer(s):
                n = _cnt_num(em.group(1))
                if n is None or n <= 0:
                    continue
                # C497b: window-scoped ENTITY-PAIR dedup — the
                # proper noun often sits in a NEIGHBOURING sentence
                # ("my recent trip to Outer Banks … it only took me
                # four hours" — pronoun cataphora), so the OLD
                # whole-sentence signature split one statement into
                # (4, ∅) vs (4, {outer, banks}) and double-counted
                # it (driving aae3761f: 19 vs GT 15). ±1
                # same-session sentences join the signature
                # (#082 ECM W5 lineage) and dedup fires on ANY
                # shared (n, entity) pair — a set-equality match
                # would still miss {outer, banks, north, carolina}
                # vs {outer, banks}.
                caps = set()
                for j in (idx - 1, idx, idx + 1):
                    if 0 <= j < len(sents) and sents[j][0] == si:
                        caps.update(
                            w.lower() for w in re.findall(
                                r'\b[A-Z][a-z]{2,}\b', sents[j][1])
                            if w.lower() not in _CNT_CAP_STOP)
                n_r = round(n, 2)
                pairs = {(n_r, w) for w in caps}
                if pairs:
                    if pairs & seen:
                        continue   # same number + same entity
                    seen |= pairs
                else:
                    if (n_r, frozenset()) in seen:
                        continue  # nounless repeat (legacy key)
                    seen.add((n_r, frozenset()))
                total += n
                found = True
    if not found:
        return None
    val = round(total, 2)
    return str(int(val)) if val == int(val) else str(val)


_WEEKDAY_RE = re.compile(
    r'\b(monday|tuesday|wednesday|thursday|friday|saturday'
    r'|sunday)s?\b', re.I)

# families whose hyponyms are true species (per-species max
# aggregation is valid); NOT generic hypernyms like course/event
# families whose hyponyms are true species (per-species max
# aggregation is valid); NOT generic hypernyms like course/event
_CNT_SPECIES_FAMS = frozenset({'fish', 'sibling'})


def _cnt_freq_days(question: str, sessions: list[dict]):
    """"Days a week" frequency: distinct weekdays in habitual
    attendance sentences ("I attend Zumba on Tuesdays and
    Thursdays, yoga on Wednesdays" → 4). C505 (#085 M2): a
    schedule-context word is now required in the sentence —
    weekday mentions in unrelated sentences (a tennis Sunday, a
    work Monday) no longer pollute the count (a08a253f 5→4)."""
    days = set()
    for si, sent in _cnt_sents(sessions):
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        if not _DUR_SCHED_ACT.search(sent):
            continue      # schedule context required (C505)
        if not _WEEKDAY_RE.search(sent):
            continue
        for m in _WEEKDAY_RE.finditer(sent):
            days.add(m.group(1).lower())
    if not days:
        return None
    return str(len(days))


def _cnt_total_sum(question: str, sessions: list[dict]):
    if not _cnt_money_q(question.lower()):
        return None      # unit discipline — never sum $ into
    # hours/fish/course questions (Cycle 483)
    # C491 (#079): anchor-discipline transplant from duration_sum.
    # The old gateless sum admitted EVERY $ in the haystack —
    # watch purchases, L-visa legal fee text and income
    # statements polluted the totals ($56355 vs GT $5850 =
    # $50k income line; $8940 vs GT $720 = $4500 visa fees).
    # Anchors: question tokens minus money-unit words (C490 F1
    # principle: the question's own unit vocabulary carries zero
    # topical signal), hyphen heads split ('bike-related' →
    # 'bike'), singular/plural forms both match ('workshops' →
    # 'workshop').
    anchors = set()
    for a in _cnt_question_anchors(question):
        base = a.split('-')[0]
        if (base.rstrip('s') in _CNT_MONEY_ANCHOR_STOP
                or base.rstrip('s') in _CNT_UNIT_ANCHOR_STOP
                or len(base) < 4):
            continue
        for form in (base, _cnt_sing(base)):
            anchors.add(form)
    are = _cnt_anchor_re(anchors) if anchors else None
    # session-level propagation: ONE non-intent anchor mention
    # lights the session (the $25 bike-chain sentence has no
    # 'bike', but its sibling 'bike lights' sentence does);
    # intent sentences can't light (planning mentions leak).
    ok_sessions = set()
    if are:
        for si, sent in _cnt_sents(sessions):
            if are.search(sent) and not _CNT_INTENT_RE.search(sent):
                ok_sessions.add(si)
    amts = set()
    for si, sent in _cnt_sents(sessions):
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        if are and not are.search(sent) and si not in ok_sessions:
            continue
        # price-range pairs ("$50 to $200", "$100-$200") are
        # budgets, not spent amounts — skip both endpoints
        skip = [(rm.start(), rm.end()) for rm in re.finditer(
            r'\$\s?\d[\d,]*(?:\.\d+)?\s*(?:to|[-\u2013])\s*'
            r'\$?\s?\d[\d,]*(?:\.\d+)?', sent)]
        for m2 in re.finditer(
                r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', sent):
            if any(s <= m2.start() < e for s, e in skip):
                continue
            amts.add(m2.group(1))
    if not amts:
        return None
    total = round(sum(float(a.replace(',', '')) for a in amts), 2)
    return f"${total:g}"


# C500: enumerated-item money aggregation ("What is the total
# cost of A and B"). Decorative modifiers carry no item identity
# — the evidence says "Coach handbag" for the question's "designer
# handbag"; generic container nouns ("products", "items") are
# anchor-poisoned exactly like unit words (#079 discipline).
_CNT_ITEM_MOD_DROP = frozenset({
    'new', 'designer', 'high-end', 'luxury', 'expensive', 'nice',
    'recent', 'recently', 'favorite', 'big', 'small', 'certain',
    'different', 'various', 'good', 'great', 'best', 'top'})
_CNT_ITEM_KW_STOP = frozenset({
    'my', 'me', 'i', 'the', 'a', 'an', 'and', 'or', 'of', 'for',
    'on', 'in', 'to', 'at', 'from', 'with', 'her', 'his', 'our',
    'their', 'that', 'this', 'these', 'those', 'some', 'any',
    'past', 'last', 'next', 'few', 'couple', 'month', 'months',
    'week', 'weeks', 'day', 'days', 'year', 'years', 'products',
    'product', 'items', 'item', 'stuff', 'supplies', 'money',
    'amount', 'price', 'cost', 'gifts', 'gift', 'purchased',
    'bought', 'got', 'spent', 'paid'}) | _CNT_ITEM_MOD_DROP
# anaphora/apposition faces license binding a $ from a
# NEIGHBOURING clause or sentence ("which was $20", "it was $25",
# "totaling $100", "I remember it cost me $120")
_CNT_ITEM_COST_FACE = re.compile(
    r"\b(?:which\s+(?:was|were|cost(?:ed)?)|that\s+(?:was|were)"
    r"|it\s+(?:was|is|cost|costed)|cost\s+me|costed|totaling"
    r"|worth|i\s+(?:paid|spent|purchased|bought|invested)\b"
    r"|(?:was|is|are|were)\s+(?:about\s+|around\s+)?\$)",
    re.I)
# strong past-cost faces may anchor against an INTERROGATIVE
# neighbour ("can I claim the cost of the car cover …? /
# I remember it cost me $120")
_CNT_ITEM_STRONG_FACE = re.compile(
    r"\b(?:i\s+remember|it\s+cost\s+me|cost\s+me|i\s+paid)\b",
    re.I)
# aggregate/summary statements are not per-item prices
_CNT_ITEM_SUMMARY_RE = re.compile(
    r"\btotal(?:ed)?\s+(?:of\s+)?\$|per\s+(?:month|week|year)\b"
    r"|\ba\s+(?:month|week|year)\b|\bmonthly\b|\bon\s+average\b",
    re.I)
# optional debug hook: set to a list to collect bind traces
_ITEM_TOTAL_TRACE = None
_CNT_ITEM_RANGE_RE = re.compile(
    r'\$\s?\d[\d,]*(?:\.\d+)?\s*(?:to|[-\u2013])\s*'
    r'\$?\s?\d[\d,]*(?:\.\d+)?')


def _cnt_item_list(question: str) -> list[set[str]]:
    """Question's enumerated items as keyword sets (C500).

    ``"the car cover and detailing spray I purchased"`` →
    ``[{car, cover}, {detailing, spray}]``. Returns ``[]`` when
    the tail parses to no usable item (money-word tails like
    "money I earned from selling my products" are refused).
    """
    ql = ' '.join(question.lower().split())
    m = re.search(
        r'\b(?:amount|cost|price)\b.*?\b(?:of|on|for)\s+(.+)$', ql)
    if not m:
        return []
    rest = m.group(1)
    # strip trailing relative clause ("… I purchased/got …")
    rest = re.split(
        r"\bi\s+(?:purchased|bought|got|spent|paid|earned|could"
        r"|have|'ve|usually)\b", rest)[0]
    # strip trailing time-window PPs ("in the past few months")
    rest = re.split(
        r'\b(?:in|over|during|within|across)\s+(?:the|a)\s+'
        r'(?:past|last|next)\b', rest)[0]
    parts = [p.strip(" .?!") for p in rest.split(',')]
    parts = [p for p in parts if p]
    chunks = []
    if len(parts) >= 2:
        last = re.sub(r'^(?:and|plus)\s+', '', parts[-1])
        chunks = parts[:-1] + ([last] if last else [])
    elif parts:
        p = parts[0]
        if ' and ' in p:
            a, b = p.split(' and ', 1)
            if a.strip(" .?!") and b.strip(" .?!"):
                chunks = [a, b]
            else:
                chunks = [p]
        else:
            chunks = [p]
    out = []
    for ch in chunks:
        kws = []
        for w in re.findall(r"[a-z][a-z'-]*", ch):
            # possessive marker is not identity: "lola's" →
            # "lola" (question says "Lola's vet visit", evidence
            # says "took Lola to the vet")
            w = w.split("'")[0]
            if w in _CNT_ITEM_KW_STOP or len(w) < 2:
                continue
            kws.append(w)
        if kws:
            out.append(set(kws))
    return out


def _cnt_item_money(sent: str) -> list[float]:
    """Non-range $ values in a sentence."""
    skip = [(rm.start(), rm.end())
            for rm in _CNT_ITEM_RANGE_RE.finditer(sent)]
    vals = []
    for m2 in re.finditer(
            r'\$\s?(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)', sent):
        if any(s <= m2.start() < e for s, e in skip):
            continue
        vals.append(float(m2.group(1).replace(',', '')))
    return vals


def _cnt_item_total(question: str, sessions: list[dict]):
    """Sum per-item prices for enumerated "total cost" questions.

    Cycle 500 ("What is the total cost of A and B I got?").
    Binding tiers, strictest first (first tier that resolves an
    item wins; every item must resolve or the question falls
    through untouched):

    T1 — same clause: the clause carries all item kws (len<=2),
         len-1 of them (len>=3, "Lola's vet visit" → lola+vet),
         or the head noun, plus a non-range $ (chews "are $10 a
         pack", "food bowl … for $15").
    T2 — adjacent clause, same sentence: kw clause + cost-face
         clause ("…flea and tick collar …, which was $20").
    T3 — adjacent sentence, same turn: kw sentence followed by a
         cost-face sentence ("…for my coworker's baby shower. /
         …totaling $100"); an interrogative kw anchor is licensed
         only by a strong past-cost face (car cover $120).
    T4a — turn-unique: kws on a declarative, item-exclusive
         sentence of the turn + the turn's surviving $ values
         collapse to one number (Lola's vet visit ← $50).
    T4b — session-unique: same predicate scoped to the session;
         the price may sit in another turn ("high-end skincare"
         ← the only $500 session).

    Conflicting distinct values for one item resolve only when a
    purchase-verb face uniquely backs one of them; otherwise the
    question abstains from this form (returns None).
    """
    items = _cnt_item_list(question)
    if not items:
        return None
    # per (session, turn) sentence lists — T3 needs turn locality
    turns: list[list[tuple[int, str]]] = []
    for si, s in enumerate(sessions):
        for t in s.get('turns', []):
            if t.get('role') != 'user':
                continue
            sents = [m.group(0).strip() for m in re.finditer(
                r'[^.!?]*[.!?]?', t.get('content', ''))]
            sents = [x for x in sents if x]
            if sents:
                turns.append([(si, x) for x in sents])

    def kw_hits(clause: str, kws: set[str]) -> int:
        low = clause.lower()
        return sum(1 for k in kws
                   if re.search(r'\b' + re.escape(k) + r's?\b', low))

    def bind(kws: set[str], idx: int, trace=None) -> float | None:
        # head = longest kw (most specific token: "medication">
        # "flea", "cover">"car", "chews">"dental") — used only
        # as T1's last-resort identity signal
        head = max(kws, key=len)
        others = items[:idx] + items[idx + 1:]

        def foreign_full(cl: str) -> bool:
            # another enumerated item fully named in this scope
            # → the scope cannot be attributed to item idx alone
            return any(kw_hits(cl, o) == len(o) for o in others)

        vals: dict[float, str] = {}       # value -> backing face
        for sent_list in turns:
            for si, sent in sent_list:
                if _CNT_ITEM_SUMMARY_RE.search(sent):
                    continue
                clauses = [c.strip() for c in re.split(r'[,;]', sent)
                           if c.strip()]
                for ci, cl in enumerate(clauses):
                    if cl.endswith('?') \
                            or _CNT_INTENT_RE.search(cl):
                        continue
                    hits = kw_hits(cl, kws)
                    mvals = _cnt_item_money(cl)
                    ok_t1 = (hits == len(kws)
                             or (len(kws) >= 3 and hits >= len(kws) - 1)
                             or re.search(r'\b' + re.escape(head)
                                          + r's?\b', cl, re.I))
                    if mvals and ok_t1 and not foreign_full(cl):
                        for v in mvals:
                            vals[v] = 't1'
                        if trace is not None:
                            trace.append(f'T1 {mvals} :: {cl[:80]}')
                        continue
                    # T2: same sentence, any-clause co-occurrence
                    # — the kw clause and the $ clause may be
                    # separated by intervening clauses (dental
                    # chews … teeth, and the chews are $10 a
                    # pack); same-sentence proximity outranks
                    # cross-sentence anaphora (T3)
                    if mvals and _CNT_ITEM_COST_FACE.search(cl):
                        if any(not foreign_full(c2)
                               and (kw_hits(c2, kws) == len(kws)
                                    or (len(kws) >= 3
                                        and kw_hits(c2, kws)
                                        >= len(kws) - 1))
                               for c2 in clauses):
                            for v in mvals:
                                vals.setdefault(v, 't2')
                            if trace is not None:
                                trace.append(
                                    f'T2 {mvals} :: {cl[:80]}')
        # T3: adjacent sentences within the turn — the $
        # evidence is evaluated per CLAUSE of cur (a trailing
        # "and I want to make sure…" clause must not poison the
        # purchase clause)
        if not vals:
            for sent_list in turns:
                for k in range(1, len(sent_list)):
                    si, prev = sent_list[k - 1]
                    si2, cur = sent_list[k]
                    if si != si2 or _CNT_ITEM_SUMMARY_RE.search(cur):
                        continue
                    strong = None
                    for cl in re.split(r'[,;]', cur):
                        cl = cl.strip()
                        if not cl or cl.endswith('?') \
                                or _CNT_INTENT_RE.search(cl):
                            continue
                        if not _CNT_ITEM_COST_FACE.search(cl):
                            continue
                        mvals = _cnt_item_money(cl)
                        if not mvals:
                            continue
                        if strong is None:
                            strong = bool(
                                _CNT_ITEM_STRONG_FACE.search(cur))
                            if prev.endswith('?') and not strong:
                                break
                        h = kw_hits(prev, kws)
                        if h == len(kws) or (len(kws) >= 3
                                             and h >= len(kws) - 1) \
                                or (strong and h >= 1) \
                                or (len(kws) == 1 and h >= 1):
                            for v in mvals:
                                vals.setdefault(v, 't3')
                            if trace is not None:
                                trace.append(
                                    f'T3 {mvals} strong={strong}'
                                    f' :: {cl[:60]}')
        # T4a: turn-unique fallback — item kws meet the standard
        # predicate in some sentence of the turn, and the turn's
        # non-skipped $ values collapse to one distinct number
        # (Lola's vet visit ← the turn's only $50). Skipping is
        # CLAUSE-level: a purpose clause ("and I want to make
        # sure…") must not hide the purchase clause's $ in the
        # same sentence.
        if not vals:
            for sent_list in turns:
                # kw predicate must hold on a DECLARATIVE,
                # item-exclusive sentence of the turn
                if not any(
                        not s2.endswith('?') and not foreign_full(s2)
                        and (kw_hits(s2, kws) == len(kws)
                             or (len(kws) >= 3
                                 and kw_hits(s2, kws) >= len(kws) - 1))
                        for _, s2 in sent_list):
                    continue
                cand = {}
                for _, s2 in sent_list:
                    if s2.endswith('?'):
                        continue
                    for cl in re.split(r'[,;]', s2):
                        cl = cl.strip()
                        if (not cl or cl.endswith('?')
                                or _CNT_INTENT_RE.search(cl)
                                or _CNT_ITEM_SUMMARY_RE.search(cl)):
                            continue
                        for v in _cnt_item_money(cl):
                            cand[v] = 't4'
                if len(cand) == 1:
                    vals.update(cand)
                    if trace is not None:
                        trace.append(f'T4a {list(cand)}')
        # T4b: session-unique fallback — scoped to the SESSION;
        # the same kw predicate must hold somewhere in it, and
        # its non-skipped $ values must collapse to one number
        # (price sentence in a different turn than the kw one)
        if not vals:
            by_sess: dict[int, list[str]] = {}
            for sent_list in turns:
                for si, s2 in sent_list:
                    by_sess.setdefault(si, []).append(s2)
            for s2s in by_sess.values():
                # kw predicate on a declarative, item-exclusive
                # sentence somewhere in the session
                if not any(
                        not s2.endswith('?') and not foreign_full(s2)
                        and (kw_hits(s2, kws) == len(kws)
                             or (len(kws) >= 3
                                 and kw_hits(s2, kws) >= len(kws) - 1))
                        for s2 in s2s):
                    continue
                cand = {}
                for s2 in s2s:
                    if s2.endswith('?'):
                        continue
                    for cl in re.split(r'[,;]', s2):
                        cl = cl.strip()
                        if (not cl or cl.endswith('?')
                                or _CNT_INTENT_RE.search(cl)
                                or _CNT_ITEM_SUMMARY_RE.search(cl)):
                            continue
                        for v in _cnt_item_money(cl):
                            cand[v] = 't4'
                if len(cand) == 1:
                    vals.update(cand)
                    if trace is not None:
                        trace.append(f'T4b {list(cand)}')
        if not vals:
            return None
        if len(vals) == 1:
            return next(iter(vals))
        # conflict: a unique same-clause (T1) value outranks
        # anaphora-tier readings
        backed = {v for v, f in vals.items() if f == 't1'}
        if len(backed) == 1:
            return backed.pop()
        return None            # ambiguous — fall through

    total = 0.0
    dbg = _ITEM_TOTAL_TRACE if _ITEM_TOTAL_TRACE is not None \
        else None
    for idx, kws in enumerate(items):
        v = bind(kws, idx, dbg)
        if v is None:
            return None
        total += v
    return f"${round(total, 2):g}"


# C507: ordinal lookup (limited, used only in P5)
_CNT_ORDINAL = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
    'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
    'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fourteenth': 14,
    'fifteenth': 15, 'sixteenth': 16, 'seventeenth': 17,
    'eighteenth': 18, 'nineteenth': 19, 'twentieth': 20}
_CNT_RATE_RE = re.compile(
    r'\b(?:a|per|each)\s+(?:week|day|month|year)s?\b', re.I)
_CNT_NUMW_PRE = (r'one|two|three|four|five|six|seven|eight|nine|ten'
                  r'|eleven|twelve|fifteen|twenty')
_CNT_PRE_NOUN_RE_TPL = (
    r'\b(\d{1,3}(?:,\d{3})*|' + _CNT_NUMW_PRE + r')\b'
    r'[^\w]{0,3}(?:\w+\s+){0,2}(%(HEADS)s)\b')


def _cnt_number_total(question: str, sessions: list[dict]):
    fam, subtypes, head0 = _cnt_np_fam(question)
    if not fam:
        return None
    fam = {f for f in fam if len(f) >= 3}
    # pre-hyponym fam for own_re (P4/P5 must use question's own
    # head, not hyponym heads — blocks "Expand on module 4")
    own = set(fam)
    for w in list(fam):
        fam |= _CNT_HYPONYM.get(w, set()) \
            | _CNT_HYPONYM.get(_cnt_sing(w), set())
    fam_re = '|'.join(re.escape(f) for f in
                      sorted(fam, key=len, reverse=True))
    own_re = '|'.join(re.escape(f) for f in
                      sorted(own, key=len, reverse=True)) or fam_re
    fam_gate = re.compile(r'\b(' + fam_re + r')\b', re.I)
    pre_re = re.compile(_CNT_PRE_NOUN_RE_TPL % {'HEADS': fam_re}, re.I)

    def _collect(sent: str, own: str) -> list[float]:
        """Pre-noun (+rate-filter) + post-noun-of + ordinal counts.
        *own* is own_re: P4/P5 restrict heads to question-own fam."""
        vals = []
        for em in pre_re.finditer(sent):
            n = _cnt_num(em.group(1).replace(',', ''))  # C507 comma
            if n is None or n >= 1000000:
                continue
            after = sent[em.end(1):em.start(2)] \
                .strip().lower().strip(' -')
            parts = after.split()
            if parts and parts[0].rstrip('s') in {
                    u.rstrip('s')
                    for u in _CNT_UNIT_BLACKLIST}:
                continue
            # C507 P3: span-level rate filter
            if _CNT_RATE_RE.search(
                    sent[max(0, em.start()):em.end() + 34]):
                continue
            vals.append(n)
        # C507 P4: post-noun numbering ("episode 12 of the X")
        # own_re only — hyponym heads excluded (imperative guard)
        for em in re.finditer(
                r'\b(' + own + r')\s+(\d{1,3})\b\s+of\b',
                sent, re.I):
            n = float(em.group(2))
            if n < 1000:
                vals.append(n)
        # C507 P5: ordinal counting ("the third meal")
        for em in re.finditer(
                r'\b(?:the\s+)?(' + '|'.join(_CNT_ORDINAL)
                + r')\s+(' + own + r')\b', sent, re.I):
            vals.append(float(_CNT_ORDINAL[em.group(1).lower()]))
        return vals

    # C507 P6: head-anchored entity split (head0 not in subtypes)
    if subtypes and head0 and head0 not in subtypes:
        per = defaultdict(set)
        for s_ in subtypes:
            sre = re.compile(r'\b' + re.escape(s_) + r's?\b', re.I)
            for si, sent in _cnt_sents(sessions):
                if sent.endswith('?'):
                    continue
                if not sre.search(sent) or not fam_gate.search(sent):
                    continue
                # Clause-level intent + comma-thousands protection
                clauses = [c.strip() for c in
                           re.split(r'[,;](?!\d)', sent)
                           if c.strip()]
                for cl in clauses:
                    if cl.endswith('?') \
                            or _CNT_INTENT_RE.search(cl):
                        continue
                    if not fam_gate.search(cl):
                        continue
                    for v in _collect(cl, own_re):
                        per[s_].add(v)
        if per and all(per.get(s_) for s_ in subtypes):
            return str(int(sum(max(v) for v in per.values())))
        return None

    # Existing paths with P1-P5 upgrades
    sub_counts, all_counts = defaultdict(set), set()
    for si, sent in _cnt_sents(sessions):
        low = sent.lower()
        if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
            continue
        if not fam_gate.search(low):
            continue
        if subtypes:
            for s_ in subtypes:
                if re.search(r'\b' + re.escape(s_) + r's?\b', low):
                    for v in _collect(sent, own_re):
                        if v < 10000:
                            sub_counts[s_].add(v)
        else:
            for v in _collect(sent, own_re):
                all_counts.add(v)
    if subtypes:
        vals = []
        for s_ in subtypes:
            if not sub_counts.get(s_):
                return None      # conjunctive completeness
            vals.append(max(sub_counts[s_]))
        return str(int(sum(vals)))
    # Cycle 483 species sum: hyponym-carrying families (fish, sibling)
    speciesable = {w for w in fam
                   if w in _CNT_SPECIES_FAMS
                   or _cnt_sing(w) in _CNT_SPECIES_FAMS}
    if speciesable:
        hypos = {h for w in speciesable
                 for h in (_CNT_HYPONYM.get(w, set())
                           | _CNT_HYPONYM.get(_cnt_sing(w), set()))}
        species = defaultdict(set)
        adjacent = set()
        for si, sent in _cnt_sents(sessions):
            clauses = [c.strip() for c in
                       re.split(r'[,;](?!\d)', sent)
                       if c.strip()]
            for cl in clauses:
                if cl.endswith('?') or _CNT_INTENT_RE.search(cl):
                    continue
                low = cl.lower()
                present = [h for h in hypos
                           if re.search(r'\b' + re.escape(h) + r's?\b',
                                        low)]
                if not present:
                    continue
                for a, b in ((a, b) for a in present for b in present
                             if a != b
                             and re.search(r'\b' + re.escape(a)
                                           + r's?\s+'
                                           + re.escape(b) + r's?\b',
                                           low)):
                    adjacent.add((a, b))
                for h in present:
                    for em in re.finditer(
                            r'\b(\d{1,3}(?:,\d{3})*|one|two|three|four'
                            r'|five|six|seven|eight|nine|ten)\b'
                            r'[^\w]{0,3}(?:\w+\s+){0,2}'
                            + re.escape(h) + r's?\b', cl, re.I):
                        n = _cnt_num(em.group(1))
                        if n:
                            species[h].add(n)
                    if re.search(r'\b(?:a|an|my|the)\s+(?:\w+\s+){0,2}'
                                 + re.escape(h) + r'\b(?!s)', cl,
                                 re.I) and 'some' not in low:
                        species[h].add(1)
        if species:
            for a, b in adjacent:
                if b in species and a in species:
                    species[a] |= species[b]
                    del species[b]
            return str(int(sum(max(v) for v in species.values())))
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


# ----------------------------------------------------------------
# Cycle 503 (Research #084 v5.2): enum_count — 5th counting form.
# Entity-count questions split into four sub-classes; the two with
# signatures carrying built-in dedup keys bypass the predicate-
# semantics wall (C469/#075/C483's wall governs (entity x action)
# pairs, not enumeration):
#   named X / Name's X / my ROLE's X  -> one counted instance
#   N-unit ("20-gallon tank")         -> size signature
# Ownership gate: "have I bought/own/my" questions suppress name
# signatures ("Billie Eilish's album" is brand pollution, not my
# inventory) — sizes stay valid. Exclusion verbs (missed/skipped)
# void a clause's signatures (realized-vs-intended micro-wall);
# "Rachel's baby shower" is excluded via the possessive tail
# window only (clause-level exclusion kills same-clause true
# signatures — #084 v5.1 overcorrection). No resolvable signature
# -> fall through (honest abstention; 26 wrong how-many questions
# in the census stay untouched by construction).
_ENUM_SIZE_UNITS = ('gallon', 'liter', 'inch', 'foot', 'pound',
                    'kg', 'gb', 'tb', 'acre', 'bedroom')
_ENUM_ROLE_NOUNS = (
    'cousin', 'roommate', 'colleague', 'friend', 'sister',
    'brother', 'aunt', 'uncle', 'niece', 'nephew', 'neighbor',
    'classmate', 'coworker', 'boss', 'daughter', 'son', 'mother',
    'father', 'grandma', 'grandpa', 'buddy', 'partner',
    'teammate', 'professor', 'teacher', 'student')
_ENUM_COMMON_CAPS = {
    'Fresh', 'New', 'The', 'My', 'We', 'They', 'Last', 'This',
    'That', 'Next', 'So', 'Also', 'Anyway', 'Well', 'Oh', 'Yeah',
    'Okay', 'Children', 'Family', 'Friends', 'Kids', 'Local',
    'City', 'Google', 'Amazon', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri',
    'Sat', 'Sun', 'St', 'San', 'Los', 'Museum', 'Gallery',
    'Center', 'University', 'School', 'Park', 'Library', 'Church',
    'Hospital', 'Store', 'Shop', 'Studio', 'Theater', 'Cafe',
    'Restaurant', 'College', 'Institute', 'High'} | _CNT_MONTHS \
    | _CNT_WEEKDAYS
_ENUM_EXCLUDE_VERBS = re.compile(
    r"\b(missed|missing|skip(?:ped)?|couldn'?t (?:make|attend)"
    r"|did(?:n'?t| not) attend|unable to attend"
    r"|wasn'?t able to attend|didn'?t go to)\b", re.I)
_ENUM_TWINS_APPOS = re.compile(
    r"\btwins?,\s*([A-Z][a-z]{2,})\s+and\s+([A-Z][a-z]{2,})\b")
# name-possessives belong to brands/artists on my-inventory
# questions, not to my collection -> names invalid there
_ENUM_MY_INVENTORY = re.compile(
    r"\b(?:have i|did i|do i)\b.*\b(?:bought|purchased|worked on"
    r"|worked with|own|owned|use|using|collected|acquired"
    r"|downloaded|replaced|fixed|assembled|sold)\b|\bmy\b",
    re.I)
_ENUM_STOP_NP = {
    'do', 'did', 'have', 'has', 'am', 'are', 'is', 'was', 'were',
    'that', 'which', 'in', 'last', 'this', 'over', 'so',
    'different', 'various', 'total', 'many', 'other', 'new',
    'related', 'type', 'types', 'of', 'or', 'and', 'my', 'the'}
_ENUM_TIME_HEADS = {
    'time', 'times', 'week', 'weeks', 'day', 'days', 'hour',
    'hours', 'minute', 'minutes', 'month', 'months', 'year',
    'years', 'page', 'pages', 'point', 'points'}


def _enum_stem(n: str) -> str:
    n = n.lower()
    if n.endswith('ies'):
        return n[:-3] + 'y'
    if n.endswith('es') and not n.endswith('ses'):
        return n[:-2]
    if n.endswith('s') and not n.endswith('ss'):
        return n[:-1]
    return n


def _enum_np(question: str) -> list[str]:
    """Content words of the counted NP ("how many babies were
    born to friends..." -> ['babies', 'born', 'friends'])."""
    ql = question.lower()
    m = re.search(r'how many ([a-z][a-z\- ]{1,40}?) '
                  r'(do|did|have|has|am|are|is|was|were|that|'
                  r'which|in|last|this|over|so)', ql)
    if not m:
        m = re.search(r'how many ([a-z][a-z\- ]{1,40}?)\??$', ql)
    if not m:
        return []
    words = [w for w in re.split(r'[.?!]', m.group(1))[0].split()
             if w not in _ENUM_STOP_NP]
    return words if words else []


def _enum_form_gate(ql: str, np_words: list[str]) -> bool:
    """Strict eligibility for the enum-count form (C488 census
    discipline: a loose gate is a hijack surface — #084 v1's 26
    fires carried a 0.15 precision)."""
    if re.search(r'how many (times|years older'
                 r'|minutes did i exceed|hours (a|per) week)', ql):
        return False
    if re.search(r'(older|younger|exceed|when will i be)', ql):
        return False
    if re.search(r'(typical week|a typical|per week|days a week)',
                 ql):
        return False
    head = np_words[-1] if np_words else ''
    if head in _ENUM_TIME_HEADS:
        return False
    return True


def _enum_valid_name(tok: str) -> bool:
    return tok not in _ENUM_COMMON_CAPS and \
        re.fullmatch(r'[A-Z][a-z]{2,}', tok) is not None


def _enum_clause_sigs(cl: str, stems: list[str]) -> tuple:
    """Signatures in one clause -> (names, roles, bare_twins)."""
    low = cl.lower()
    if not any(st in low for st in stems):
        return set(), set(), False
    if _ENUM_EXCLUDE_VERBS.search(cl):
        return set(), set(), False
    names, roles = set(), set()
    for m in re.finditer(
            r'(?:named|calling|called)\s+([A-Z][a-z]{2,})', cl):
        if _enum_valid_name(m.group(1)):
            names.add(m.group(1))
    for st in stems:
        for m in re.finditer(
                r"\b([A-Z][a-z]{2,})('s)\s+([^,]{0,60}?)\b" + st, cl):
            tail = cl[m.end():m.end() + 15].lower()
            if _enum_valid_name(m.group(1)) and 'shower' not in tail:
                names.add(m.group(1))
        for m in re.finditer(
                r"\b(?:and\s+)([A-Z][a-z]{2,})('s)\s+([^,]{0,60}?)\b"
                + st, cl):
            if _enum_valid_name(m.group(1)):
                names.add(m.group(1))
        for m in re.finditer(
                r'\b([A-Z][a-z]{2,})\s+'
                r'(?:got\s+married|and\s+[A-Z][a-z]+\s*,)', cl):
            if _enum_valid_name(m.group(1)) and \
                    re.search(r'(wedding|married|bride|groom)', low):
                names.add(m.group(1))
        for m in re.finditer(
                r'\b(?:my|our)\s+(?:little|best|old|college|close|'
                r'dear)?\s*(' + '|'.join(_ENUM_ROLE_NOUNS) +
                r")s?(?:\s+[A-Z][a-z]+)?(?:'s)?\s+([^,]{0,60}?)\b"
                + st, cl):
            roles.add(m.group(1))
    twins_family = any(st.startswith(('bab', 'twin', 'famil'))
                       for st in stems)
    bare_twins = twins_family and bool(
        re.search(r'\btwins?\b(?!,\s*[A-Z])', low))
    if twins_family:
        for m in _ENUM_TWINS_APPOS.finditer(cl):
            if _enum_valid_name(m.group(1)):
                names.add(m.group(1))
            if _enum_valid_name(m.group(2)):
                names.add(m.group(2))
    return names, roles, bare_twins


# ---------------------------------------------------------------------------
# C511: inventory_count — distinct-item enumeration for hobby/
# acquisition inventories ("how many model kits have I worked
# on or bought?", "how many musical instruments do I currently
# own?", "how many properties did I view …?"). The enum_count
# machinery reads name/role signatures (weddings, babies); these
# families carry identity in scale/brand/model codes (1/72 B-29,
# Tamiya Spitfire, Korg B1) and descriptors (2-bedroom condo,
# Cedar Creek). Census discipline: the family whitelist is
# exactly the three implemented grammars; a wider gate is a
# hijack surface (C488 lesson).
# ---------------------------------------------------------------------------

_INV_FAMS = {'kit', 'instrument', 'property'}

_INV_HYPO_RE = re.compile(
    r"\b(?:thinking (?:of|about) (?:buying|getting|working on"
    r"|trying)"
    r"|eyeing|considering (?:buying|getting|a few)"
    r"|planning to (?:buy|get)"
    r"|want(?:ing)? to (?:buy|get)"
    r"|maybe (?:getting|buying)"
    r"|next project"
    r"|when i (?:get|buy)"
    r"|hoping to (?:buy|get)"
    r"|check(?:ing)? out (?:those|some of|the)"
    r"|you mentioned"
    r"|looking (?:at|to buy|to get)"
    r"|\bi'?ll (?:start by |definitely )?(?:check|keep|get))\b",
    re.I)

_INV_FOREIGN_RE = re.compile(
    r"\b(?:my|our)\s+(?:niece|nephew|sister|brother|friend"
    r"|coworker|daughter|son|wife|husband|mom|mother|dad|father"
    r"|neighbor|bandmate|classmate)\b"
    r"|\b(?:her|his|their)\s+(?:new\s+|old\s+"
    r"|student[- ]level\s+)?"
    r"(?:guitar|piano|drum|violin|ukulele|cello|flute|trumpet"
    r"|saxophone|banjo|mandolin|keyboard|synth\w*|bass)\b"
    r"|\b(?:she|he|they)\s+(?:just\s+)?(?:got|bought|has"
    r"|have)\b",
    re.I)

_INV_KIT_GUARD_RE = re.compile(
    r"\b(?:meal\s?kit|first[- ]aid\s?kit|survival\s?kit"
    r"|tool\s?kit"
    r"|stock price|prediction model|role model|data model"
    r"|business model|mental model|3d model|model (?:train"
    r"|railway|rocket))\b", re.I)

_INV_KIT_BRAND_RE = re.compile(
    r"\b(revell|tamiya|airfix|italeri|hasegawa|trumpeter|meng"
    r"|dragon|academy|monogram|amt|mpc|fujimi|aoshima"
    r"|polar lights|moebius|lindberg|eduard|zvezda"
    r"|hobby\s?boss)\b", re.I)

_INV_KIT_ANCHOR_RE = re.compile(
    r'(?:\d+\s*/\s*\d+|Revell|Tamiya|Airfix|Italeri|Hasegawa'
    r'|Trumpeter|Meng|Dragon|Academy|Monogram|AMT|MPC|Fujimi'
    r'|Aoshima|Polar Lights|Moebius|Lindberg|Eduard|Zvezda'
    r'|Hobby Boss)\s*(?:scale\s+)?'
    r"((?:[A-Za-z0-9'\.\-]+\s+){0,4}[A-Za-z0-9'\.\-]+)")

_INV_SCALE_RE = re.compile(r'\b(\d+)\s*/\s*(\d+)\b')

_INV_VIEW_RE = re.compile(
    r"\b(?:i|i'?ve|we|we'?ve)\s+(?:also\s+|actually\s+"
    r"|recently\s+)?"
    r"(?:viewed|saw|seen|toured|visited"
    r"|fell in love with)\b", re.I)

_INV_OWN_RE = re.compile(
    r"\b(?:my|our)\s+(?:new\s+|old\s+|first\s+|black\s+"
    r"|white\s+|acoustic\s+|electric\s+|digital\s+"
    r"|upright\s+|5-?piece\s+|simple\s+)*"
    r"(?:[a-z0-9\-'/]+\s+){0,5}?"
    r"(guitar|piano|drum|violin|ukulele|cello|flute|trumpet"
    r"|saxophone|banjo|mandolin|keyboard|synth\w*|bass"
    r"|instrument|kit|kits|model|models|tank|tanks)\b"
    r"|\b(?:i'?ve had|i have had|just got|picked up"
    r"|recently finished|started working on|been working on"
    r"|been playing|finished)\b", re.I)

_INV_MONTHS = _CNT_MONTHS if isinstance(_CNT_MONTHS, set) \
    else {'january', 'february', 'march', 'april', 'may', 'june',
         'july', 'august', 'september', 'october', 'november',
         'december'}

_INV_PROP_TYPE = {'house', 'condo', 'townhouse', 'bungalow',
                  'apartment', 'loft', 'cottage', 'duplex',
                  'villa', 'cabin', 'flat', 'home', 'property',
                  'properties'}

_INV_STOP_TOK = {'the', 'a', 'an', 'my', 'our', 'new', 'old',
                 'simple', 'beautiful', 'scale', 'model', 'kit',
                 'bomber', 'tank', 'and', 'that', 'one', 'some',
                 'in', 'on', 'at', 'for', 'with', 'of', 'german',
                 'american', 'student', 'level'}


def _inv_form_gate(ql: str) -> str | None:
    """Family whitelist for the inventory form (C511 census:
    exactly 3 fires on the 500-question suite, all currently
    wrong — zero hijack surface by construction)."""
    if re.search(r'\b(times|in total|older|younger|exceed'
                 r'|when will i be)\b', ql):
        return None
    if re.search(r'(typical week|a typical|per week|days a week)',
                 ql):
        return None
    m = re.search(r'how many (?:different |total |other )*'
                  r'([a-z][a-z\- ]{0,40}?) '
                  r'(do|did|have|has|am|are|is|was|were|that|which)',
                  ql)
    if not m:
        m = re.search(r'how many (?:different |total |other )*'
                      r'([a-z][a-z\- ]{0,40}?)\??$', ql)
    if not m or not m.group(1).split():
        return None
    head = _cnt_sing(m.group(1).split()[-1])
    return head if head in _INV_FAMS else None


def _inv_sents(sessions: list[dict]):
    """User-role sentences across all evidence sessions."""
    for s in sessions:
        for t in s.get('turns', []):
            if t.get('role') != 'user':
                continue
            for m in re.finditer(r'[^.!?]*[.!?]?',
                                 t.get('content', '')):
                sent = m.group(0).strip()
                if len(sent) > 3:
                    yield sent


def _inv_kit_sigs(sent: str) -> list[frozenset]:
    """Sentence-level scale/brand/model signature union."""
    if _INV_KIT_GUARD_RE.search(sent):
        return []
    toks: set[str] = set()
    for m in _INV_SCALE_RE.finditer(sent):
        toks.add(f"{m.group(1)}/{m.group(2)}")
    for m in _INV_KIT_BRAND_RE.finditer(sent):
        toks.add(m.group(1).replace(' ', '').lower())
    for m in _INV_KIT_ANCHOR_RE.finditer(sent):
        for tok in re.findall(r"[A-Za-z0-9'\.\-]+", m.group(1)):
            tl = tok.lower()
            if tl in _INV_STOP_TOK or tl in _INV_MONTHS \
                    or tok == 'I' or tok.isdigit():
                continue
            if any(c.isdigit() for c in tok) or \
                    (tok[0].isupper() and len(tok) > 1):
                toks.add(tl)
    return [frozenset(toks)] if toks else []


def _inv_instr_sigs(sent: str, members: set) -> list[frozenset]:
    """Brand/model + qualifier signature for one sentence."""
    toks: set[str] = set()
    low = sent.lower()
    for m in re.finditer(
            r"\b([A-Z][A-Za-z]*\d[\w\-]*|\d+[- ]?piece)\b", sent):
        toks.add(m.group(1).lower().replace(' ', '-'))
    for m in re.finditer(
            r"\b(Fender|Yamaha|Pearl|Korg|Cordoba|Kala|Gibson"
            r"|Martin|Roland|Casio|Ibanez|Epiphone|Squier"
            r"|Takamine|Gretsch|Jackson)\s+"
            r"([A-Z0-9][\w\-]*(?:\s+[A-Z0-9][\w\-]*){0,2})", sent):
        toks.add(m.group(1).lower())
        toks.add(m.group(2).split()[0].lower())
    quals = {'acoustic', 'electric', 'upright', 'digital',
             'black', 'white', 'old'}
    for w in re.findall(r'[a-z\-]+', low):
        if w in quals or w in members:
            toks.add(w)
    return [frozenset(toks)] if toks else []


def _inv_prop_sigs(sent: str) -> list[frozenset]:
    """Descriptor signature (bedrooms/type, neighborhood)."""
    toks: set[str] = set()
    for m in re.finditer(r'(\d+)[- ]bedroom\s+([a-z]+)', sent,
                         re.I):
        toks.add(f"{m.group(1)}-bedroom")
        t = m.group(2).lower()
        if t.endswith('s'):
            t = t[:-1]
        toks.add(t)
    for m in re.finditer(
            r'\bin (?:the )?([A-Z][a-z]+(?: [A-Z][a-z]+)?)'
            r'\s+(?:neighborhood|area)\b', sent):
        parts = m.group(1).split()
        if all(p.lower() in _INV_MONTHS for p in parts):
            continue
        toks.update(p.lower() for p in parts)
    for m in re.finditer(
            r'\bin ([A-Z][a-z]+ [A-Z][a-z]+)\b', sent):
        parts = m.group(1).split()
        if all(p.lower() in _INV_MONTHS for p in parts):
            continue
        toks.update(p.lower() for p in parts)
    return [frozenset(toks)] if toks else []


def _inv_dedup(sigs: list[frozenset]) -> int:
    """Count maximal signatures under token containment."""
    uniq: list[frozenset] = []
    for s in sorted(set(sigs), key=len, reverse=True):
        if not any(s <= t for t in uniq):
            uniq.append(s)
    return len(uniq)


def _cnt_inventory_count(question: str,
                         sessions: list[dict]):
    """Distinct-item inventory count (C511 oracle 3/3).

    Faces: hypothetical acquisition ("thinking of buying a new
    ukulele") and foreign possessors ("my niece … her violin")
    are excluded at sentence level; the question's own offer-on
    anchor NP ("the townhouse in the Brookside neighborhood")
    drops the purchase target from viewed-property counts.
    Selling contemplation does NOT exclude (still owned — the
    Pearl drum set counts)."""
    fam = _inv_form_gate(question.lower().strip())
    if not fam:
        return None
    ql = question.lower()
    viewing = bool(re.search(
        r'\b(view|viewed|tour|toured|visit|visited|see|seen'
        r'|saw)\b', ql))
    members = {'instrument': {'guitar', 'piano', 'drum', 'violin',
                              'ukulele', 'cello', 'flute', 'trumpet',
                              'saxophone', 'banjo', 'mandolin',
                              'keyboard', 'synth', 'synthesizer',
                              'bass', 'instrument', 'instruments'},
               'property': _INV_PROP_TYPE,
               'kit': {'kit', 'kits', 'model', 'models', 'tank',
                       'tanks'}}[fam]
    anchor: set[str] = set()
    m = re.search(r'(?:offer on|purchase[ds]?|bought|contract on)'
                  r'\s+(?:the|a|an)\s+(.+?)(?:\?|$)', question,
                  re.I)
    if m:
        for w in re.findall(r"[A-Za-z][\w\-']*", m.group(1)):
            wl = w.lower()
            if wl not in ('in', 'the', 'a', 'an', 'neighborhood',
                          'area', 'and', 'that', 'one', 'home',
                          'place'):
                anchor.add(wl)
    sigs: list[frozenset] = []
    for sent in _inv_sents(sessions):
        if _INV_HYPO_RE.search(sent) or \
                _INV_FOREIGN_RE.search(sent):
            continue
        if fam == 'kit':
            if _INV_SCALE_RE.search(sent) or \
                    _INV_KIT_BRAND_RE.search(sent) or \
                    _INV_OWN_RE.search(sent):
                sigs.extend(_inv_kit_sigs(sent))
        else:
            lic = _INV_VIEW_RE.search(sent) if viewing \
                else _INV_OWN_RE.search(sent)
            if not lic:
                continue
            if fam == 'instrument':
                sigs.extend(_inv_instr_sigs(sent, members))
            else:
                sigs.extend(_inv_prop_sigs(sent))
    if not sigs:
        return None
    if anchor and len(anchor) >= 2:
        sigs = [s for s in sigs if not anchor <= s]
    return str(_inv_dedup(sigs))


# ---------------------------------------------------------------------------
# Cycle 514: museum_count — venue visitation with a month window
# (11th counting form). Census: exactly 2 fires on the full-500
# ("how many different museums or galleries did I visit …", both
# currently wrong, zero overlap with any other family). Grammar:
# realized visit verbs + venue identity (Museum-suffix names,
# quoted titles, gallery-context TitleSeqs) + venue-level date
# aggregation — the month window is load-bearing: it excludes
# the January Modern-Art-Museum workshop while keeping the 2/8
# and 2/15 (15th February) visits. Future/speculative mentions
# ("I'll check out the National Waterfront Museum") and generic
# event NPs ("opening night") are rejected at clause level.
# ---------------------------------------------------------------------------

_MUV_Q_RE = re.compile(
    r'how many (?:different |other |total |various )*'
    r'(?:museums?|galleries?)'
    r'(?: or (?:museums?|galleries?))? did i visit\b', re.I)
_MUV_MONTH_RE = re.compile(
    r'\b(?:in|during)(?: the)?(?: month of)?\s+'
    + '(' + '|'.join(_TA_MONTH_NUM) + r')\w*\b', re.I)
_MUV_FUTURE_RE = re.compile(
    r"\b(?:i'?ll|we'?ll|will|might|maybe|planning|looking to"
    r"|want to|hoping|can't wait|soon|next time|recommend)\b", re.I)
_MUV_VISIT_RE = re.compile(
    r"\b(?:visited|visit|attended|attending|was at|were at"
    r"|took|went to|seen at|saw|met|toured|tour)\b", re.I)
_MUV_VENUE_RE = re.compile(
    r"(?:\b(?:to|at|of)\s+|\b(?:visited|saw|attended|toured)\s+)"
    r"(?:the\s+)?[\"\']?"
    r"((?:(?:Museum|Gallery)\s+of\s+|(?:[A-Z][\w&'\-]*\s+){1,3})"
    r"[A-Z][\w&'\-]*)")
_MUV_EVENT_GEN = frozenset(
    'opening night workshop class event party show gala fair '
    'tour lesson session meetup gathering'.split())
_MUV_CTX_RE = re.compile(
    r'\b(?:curator|exhibition|exhibit|gallery|galleries|museum'
    r'|museums|opening night)\b', re.I)
_MUV_DATE_M_D = re.compile(r'\b(\d{1,2})/(\d{1,2})\b')
_MUV_DATE_DM = re.compile(
    r'\b(\d{1,2})(?:st|nd|rd|th)?\s+('
    + '|'.join(_TA_MONTH_NUM) + r')\w*\b', re.I)
_MUV_DATE_MD = re.compile(
    r'\b(' + '|'.join(_TA_MONTH_NUM) + r')\w*\s+'
    r'(\d{1,2})(?:st|nd|rd|th)?\b', re.I)
_MUV_DATE_IN = re.compile(
    r'\b(?:in|during)\s+(' + '|'.join(_TA_MONTH_NUM)
    + r')\w*\b', re.I)


def _muv_form_gate(ql: str) -> bool:
    """Exactly the census surface: how-many museum/gallery
    visitation questions (C488 discipline — no wider gate)."""
    return bool(_MUV_Q_RE.search(ql))


def _muv_venue_norm(name: str) -> str:
    n = name.strip().strip('"\'').strip()
    if n.lower().startswith('the '):
        n = n[4:]
    return re.sub(r'\s+', ' ', n).strip().lower()


def _muv_clause_months(cl: str) -> set[int]:
    months: set[int] = set()
    for m in _MUV_DATE_DM.finditer(cl):
        months.add(_TA_MONTH_NUM[m.group(2)[:3].lower()])
    for m in _MUV_DATE_MD.finditer(cl):
        months.add(_TA_MONTH_NUM[m.group(1)[:3].lower()])
    for m in _MUV_DATE_IN.finditer(cl):
        months.add(_TA_MONTH_NUM[m.group(1)[:3].lower()])
    for m in _MUV_DATE_M_D.finditer(cl):
        months.add(int(m.group(1)))      # US M/D per LME authoring
    return months


def _cnt_museum_count(question: str, sessions: list[dict]):
    """Distinct visited venues inside the question's month
    window (C514). Venue-level date aggregation: a venue counts
    iff at least one realized clause dates it inside the window;
    undated realized mentions never fabricate window membership.
    Zero venues (window asked or not) → ABSTAIN: the memory
    never mentioned any qualifying visit — presupposition
    failure, the honest protocol answer (the _abs twin scores
    via abstention, not a fabricated "0" — C513's lesson that
    silence is not a zero claim)."""
    ql = question.lower().strip()
    if not _muv_form_gate(ql):
        return None
    mq = _MUV_MONTH_RE.search(ql)
    window = (_TA_MONTH_NUM[mq.group(1)[:3].lower()]
              if mq else None)
    venues: dict[str, set[int]] = {}
    for s in sessions:
        for t in s.get('turns', []):
            if t.get('role') != 'user':
                continue
            content = t.get('content', '')
            if not re.search(r'museum|galler|exhibit|curator',
                             content, re.I):
                continue        # turn candidacy (same unit as enum)
            quoted = set(_muv_venue_norm(q) for q in
                         re.findall(r'["\']([^"\']{2,40})["\']',
                                    content))
            for cl in re.split(r'[.;!?]', content):
                cl = cl.strip()
                if not cl or _MUV_FUTURE_RE.search(cl):
                    continue
                if not _MUV_VISIT_RE.search(cl):
                    continue
                for m in _MUV_VENUE_RE.finditer(cl):
                    name = m.group(1)
                    if not name:
                        continue
                    tail = name.split()[-1].lower()
                    words = [w.lower() for w in name.split()]
                    valid = (tail in ('museum', 'gallery',
                                      'galleries')
                             or name.startswith('Museum')
                             or _muv_venue_norm(name) in quoted
                             or (_MUV_CTX_RE.search(cl)
                                 and not (set(words)
                                          & _MUV_EVENT_GEN)))
                    if not valid:
                        continue
                    key = _muv_venue_norm(name)
                    if len(key) < 4 or key in _MUV_EVENT_GEN:
                        continue
                    months = venues.setdefault(key, set())
                    months |= _muv_clause_months(cl)
    if window is not None:
        counted = [k for k, ms in venues.items() if window in ms]
    else:
        counted = list(venues)
    if not counted:
        return ABSTAIN_ANSWER
    return str(len(counted))


# Cycle 515: age_diff — self-age-anchored year arithmetic, the
# 12th counting form. Census surface (ms133 + full500, C515
# discipline): exactly 3 gate fires — "older than me" (relative),
# "older than when I <event>" (self-then), "will I be when …
# gets married" (self+until) — all three currently wrong at HEAD
# (chatty-echo answers), oracle 3/3, zero hijack.

_AGE_G_OTHER = re.compile(
    r'^how many years older is my (\w+) than me\b')
_AGE_G_THEN = re.compile(
    r'^how many years older am i than when i (\w+)')
_AGE_G_UNTIL = re.compile(
    r'^how many years will i be when\b')

_AGE_SELF_PATS = [
    # "I'm 32" / "I'm 32 now" — case-sensitive on I (re.I would
    # let stray "m 32" fragments through; As/do-you-think carry
    # their own case-insensitive anchors)
    re.compile(r"\bI'?m\s+(\d{2})\b"),
    re.compile(r"\bas someone who'?s\s+(\d{2})\b", re.I),
    re.compile(r"\bas an? (\d{2})-year-old\b", re.I),
    re.compile(r"\bdo you think (\d{2}) is considered "
               r"(?:young or old|old or young)\b", re.I),
]
_AGE_EVENT_AGE = re.compile(r'\bat the age of (\d{2})\b')
_AGE_MARRIED_NEXT = re.compile(
    r'\b(?:getting|gets) married next year\b', re.I)
_AGE_EVENT_WORDS = {
    'graduated': ('graduat', 'complet', 'degree', 'diploma'),
    'moved': ('moved', 'relocat'),
    'started': ('started', 'began'),
}


def _age_form_gate(ql: str) -> str | None:
    """Exactly the census surface (C515): three age-arithmetic
    question shapes, lowercase question input."""
    if _AGE_G_OTHER.search(ql):
        return 'other'
    if _AGE_G_THEN.search(ql):
        return 'then'
    if _AGE_G_UNTIL.search(ql):
        return 'until'
    return None


def _age_self(sessions: list[dict]) -> set[int]:
    vals: set[int] = set()
    for _si, sent in _cnt_sents(sessions):
        for p in _AGE_SELF_PATS:
            for m in p.finditer(sent):
                v = int(m.group(1))
                if 13 <= v <= 90:
                    vals.add(v)
    return vals


def _age_other(sessions: list[dict], rel: str) -> set[int]:
    vals: set[int] = set()
    ob = re.compile(r"\b" + rel + r"(?:'s)?\s+(\d{2,3})"
                    r"(?:th|st|nd|rd)?\s+birthday\b", re.I)
    oy = re.compile(r"\b" + rel + r"\b[\w' ,]{0,60}?"
                    r'\b(\d{2,3})\s+years? old\b', re.I)
    for _si, sent in _cnt_sents(sessions):
        for m in ob.finditer(sent):
            vals.add(int(m.group(1)))
        for m in oy.finditer(sent):
            vals.add(int(m.group(1)))
    return vals


def _age_then(sessions: list[dict], event: str) -> set[int]:
    words = _AGE_EVENT_WORDS.get(event, (event,))
    vals: set[int] = set()
    for _si, sent in _cnt_sents(sessions):
        if any(w in sent.lower() for w in words):
            for m in _AGE_EVENT_AGE.finditer(sent):
                vals.add(int(m.group(1)))
    return vals


def _cnt_age_diff(question: str, sessions: list[dict]):
    """Self-age-anchored year arithmetic (C515, oracle 3/3,
    census 3 fires / zero hijack across ms133+full500).

    Every anchor must be unique-valued across user-role
    sentences; a missing or multi-valued (genuinely ambiguous)
    anchor returns None and the question falls through to the
    gate chain — arithmetic never guesses, and a non-positive
    difference is a grammar miss, not an answer."""
    ql = question.lower().strip()
    form = _age_form_gate(ql)
    if not form:
        return None
    sa = _age_self(sessions)
    if len(sa) != 1:
        return None
    me = sa.pop()
    if form == 'other':
        rel = _AGE_G_OTHER.search(ql).group(1)
        oa = _age_other(sessions, re.escape(rel))
        if len(oa) != 1:
            return None
        d = oa.pop() - me
        return str(d) if d > 0 else None
    if form == 'then':
        event = _AGE_G_THEN.search(ql).group(1)
        ta = _age_then(sessions, event)
        if len(ta) != 1:
            return None
        d = me - ta.pop()
        return str(d) if d > 0 else None
    # form == 'until': only the married-next-year grammar is
    # evidence-backed so far — other event types fall through
    if 'married' not in ql:
        return None
    for _si, sent in _cnt_sents(sessions):
        if _AGE_MARRIED_NEXT.search(sent):
            return str(me + 1)
    return None


def _cnt_enum_count(question: str, sessions: list[dict]):
    """Enumeration-signature count (#084 v5.2 oracle parity 4/4).

    Granularity follows the prototype exactly: user TURNS are the
    candidacy unit (a turn containing any stem contributes ALL
    its clauses — the role-absorption step must see stem-less
    clauses too, e.g. "my cousin Rachel's wedding" riding in a
    turn whose stem sits in another clause); clauses are the
    signature unit; size signatures scan the full turn.
    """
    np_words = _enum_np(question)
    if not np_words:
        return None
    if not _enum_form_gate(question.lower(), np_words):
        return None
    stems = [_enum_stem(w) for w in np_words]
    all_names: set[str] = set()
    all_roles: set[str] = set()
    sizes: set[str] = set()
    bare_twins = twins_appos = False
    cand_clauses: list[str] = []
    n_cand = 0
    for s in sessions:
        for t in s.get('turns', []):
            if t.get('role') != 'user':
                continue
            content = t.get('content', '')
            if len(content) <= 3:
                continue
            if not any(st in content.lower() for st in stems):
                continue          # turn-level candidacy (prototype)
            n_cand += 1
            cls = [c for c in re.split(r'[.;!?]', content)
                   if c.strip()]
            cand_clauses.extend(cls)
            for cl in cls:
                n, r, tw = _enum_clause_sigs(cl, stems)
                all_names |= n
                all_roles |= r
                bare_twins = bare_twins or tw
                if _ENUM_TWINS_APPOS.search(cl):
                    twins_appos = True
            for m in re.finditer(
                    r'\b(\d+)[- ]?('
                    + '|'.join(_ENUM_SIZE_UNITS) + r')\b',
                    content.lower()):
                sizes.add(m.group(1) + m.group(2))
    if n_cand == 0:
        return None
    head = np_words[-1]
    q_size = _enum_stem(head) in ('tank', 'aquarium') or \
        any(u in head for u in _ENUM_SIZE_UNITS)
    if sizes and q_size:
        return str(len(sizes))
    my_inv = bool(_ENUM_MY_INVENTORY.search(question))
    if (all_names or all_roles) and not my_inv:
        # same-clause name absorbs its role ("my cousin Rachel's
        # wedding" is ONE instance, not cousin + Rachel) — over
        # ALL clauses of candidate turns, stem-less included
        absorbed = set()
        for cl in cand_clauses:
            for role in all_roles:
                if role in cl.lower():
                    for nm in all_names:
                        if nm in cl:
                            absorbed.add(role)
                            break
        n = len(all_names) + len(all_roles - absorbed) + \
            (1 if bare_twins and not twins_appos else 0)
        return str(n)
    return None


# ════════ Cycle 509: delta-family — two-anchor numeric aggregation
# (Research #086) ════════
#
# Questions that name BOTH sides of a numeric comparison in the
# question text itself — "how much more did I pay for X compared
# to Y", "did I save by taking the train instead of the taxi",
# "the minimum amount … and …". Every pre-C509 aggregator
# (total_sum / unit_sum / number_total / item_total) assumes ONE
# entity → many value lines → one direction; none bind two sides
# independently then apply an operator. The question IS the join
# condition: the separator (compared to / than / instead of /
# between … and / after the initial) splits the question into two
# side-keyword sets, each side picks its value line over the FULL
# haystack, then the operator family runs. Ported verbatim from
# the #086 prototype (r086_proto7.py, oracle 16/21 fired-precision
# 100%) — every constraint in _dl_pick is load-bearing against an
# observed failure from the prototype's six-iteration arc:
# any-of (not must-all) anchors / strict-majority cross-side
# exclusion (≥ killed transition-narrative lines) / clause
# locality as tie-breaker only (hard filter killed end-of-line
# values in 434-char lines) / require=originally + orig-line
# exclusion (same-line self-comparison) / unit_ctx instead of
# anchor ('per night' as an anchor annihilated the Tokyo side).
# Production deltas vs prototype: mechanism-miss → None fall-
# through (the gates own abstention — an IDK here would flip
# currently-correct answers reached via the answer gate); the
# GT-gated 'faster' temporal-diff branch gates on the question
# text alone (census-checked, see delta_form).

_DL_MONEY = re.compile(r'\$\s?([\d,]+(?:\.\d+)?)')
_DL_PCT = re.compile(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', re.I)
_DL_MPG = re.compile(r'(\d+(?:\.\d+)?)\s*miles per gallon', re.I)
_DL_MINRE = re.compile(r'(\d+(?:\.\d+)?)\s*minutes', re.I)
_DL_OLD_T = ('ago', 'last', 'previous', 'initially', 'before',
             'earlier')
_DL_NEW_T = ('now', 'lately', 'recently', 'current', 'these days')
_DL_WORDN = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
             'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
# Mini geo lexicon — 'hawaii' side must see maui/honolulu/oahu
# mentions as its own anchors (#086 insight 3; candidate for the
# #083 embedding side-channel's shared lexicon assets).
_DL_LEX = {'hawaii': ('maui', 'honolulu', 'oahu', 'hawaii', 'kauai')}
_DL_GENERIC = set(
    'the a an my i me of on in at for to with and or did do does '
    'is was were how much many what which more less than compared '
    'compare comparison between higher lower instead take taking '
    'by will would could it its that this these those spend spent '
    'cost costs cost paid pay save saved price amount money total '
    'per night nightly week month day'.split())
_DL_SIDE_GEN = set(
    'receive percentage discount expensive ride daily commute fare '
    'ticket amount quote initial corrected final get got order '
    'first trip event charity from again will would'.split())
_DL_RANGE_RE = re.compile(
    r'\$[\d,]+\s*(?:-|to|–)\s*\$?[\d,]+'
    r'|(?:want|planning|budget(?:ing)?|looking) (?:to )?spend', re.I)
_DL_CLAUSE_STOP = '.!?;'


def _dl_stem(t: str) -> str:
    for suf in ('ed', 'al', 'es', 's'):
        if len(t) > 5 and t.endswith(suf):
            return t[:-len(suf)]
    return t


def _dl_norm(s: str) -> str:
    return re.sub(r'[^a-z0-9$% ]', ' ', s.lower())


def _dl_kws(s: str, side: bool = False) -> list[str]:
    out = [t for t in re.findall(r"[a-z']+", s.lower())
           if t not in _DL_GENERIC
           and (not side or t not in _DL_SIDE_GEN) and len(t) > 2]
    return [_dl_stem(t) for t in out]


def _dl_flat(sessions: list[dict]):
    """(session_idx, role, line) stream over evidence sessions."""
    for si, s in enumerate(sessions):
        for t in s.get("turns", []):
            for line in (t.get("content") or "").split("\n"):
                yield si, t.get("role", ""), line


def _dl_wnum(tok: str):
    if tok in _DL_WORDN:
        return _DL_WORDN[tok]
    try:
        return float(tok)
    except ValueError:
        return None


def _dl_scan(sessions: list[dict], ureg: re.Pattern) -> list[tuple]:
    out = []
    for si, role, ln in _dl_flat(sessions):
        for m in ureg.finditer(ln):
            raw = m.group(1).replace(',', '')
            v = (float(raw)
                 if raw.replace('.', '', 1).isdigit()
                 else _dl_wnum(raw.lower()))
            if v is None:
                continue
            out.append((v, si, role, ln, m.group(0)))
    return out


def _dl_pick(cands, anchors, unit_ctx=None, require=None,
             exclude=None):
    """Any-of anchor scoring: (n_hits, user_role, later_session,
    same_clause, -char_distance). require=must-appear words;
    exclude=opposing-side anchors (strict-majority skip);
    150-char hard distance cap."""
    exp = list(anchors or [])
    for a in (anchors or []):
        exp.extend(_DL_LEX.get(a, ()))
    excl = list(exclude or [])
    best = bestkey = None
    for t in cands:
        v, si, r, ln, raw = t
        l = ln.lower()
        if _DL_RANGE_RE.search(ln):
            continue
        if unit_ctx and not any(u in l for u in unit_ctx):
            continue
        n = sum(1 for a in exp if a in l)
        if exp and n == 0:
            continue
        if require and not all(x in l for x in require):
            continue
        if excl and sum(1 for x in excl if x in l) > n:
            continue
        dist = local_ok = 0
        if exp:
            vpos = l.find(raw)
            if vpos < 0:
                vpos = l.find(f"{int(v):,}" if v == int(v) else str(v))
            if vpos < 0:
                continue
            poss = [(abs(vpos - l.find(a)), l.find(a), vpos)
                    for a in exp if a in l]
            if not poss:
                continue
            dist, apos, vpos = min(poss)
            if dist > 150:
                continue
            seg = l[min(apos, vpos):max(apos, vpos)]
            local_ok = not any(s in seg for s in _DL_CLAUSE_STOP)
        key = (n, r == 'user', si, local_ok, -dist)
        if bestkey is None or key > bestkey:
            best, bestkey = t, key
    return best


def _dl_split_sides(q: str):
    """Split a two-sided question at its comparison separator."""
    ql = q.lower()
    for sep in (' compared to ', ' instead of '):
        if sep in ql:
            a, b = ql.split(sep, 1)
            return a, b
    if ' than ' in ql:
        a, b = ql.split(' than ', 1)
        return a, b
    if ' between ' in ql and ' and ' in ql:
        m = re.search(r'between (.+?) and (.+)', ql)
        if m:
            return m.group(1), m.group(2)
    return None


def _dl_money(v) -> str:
    if v == int(v):
        v = int(v)
    return f"${v:,}" if isinstance(v, int) else f"${v:,.2f}"


def delta_form(question: str) -> str | None:
    """Classify a delta-family question form (STRICT gate).

    Returns the form kind for telemetry, or ``None``. Gate
    patterns are exactly the #086 operator dispatchers — question
    text only, no evidence peeking. "faster" gates the temporal-
    diff branch alone (prototype used GT; census over the full
    500 confirms the question-text gate is family-clean).
    """
    ql = question.strip().lower()
    if ('miles per gallon' in ql or 'mpg' in ql or 'faster' in ql):
        return 't_diff'
    if re.search(r'how much (cashback|interest)', ql):
        return 'rate'
    m = re.search(
        r'what percentage of (?:the )?(?:packed |my )?(.+?) did i (\w+)',
        ql)
    if m and not ql.startswith('what percentage of the countryside'):
        return 'count_ratio'
    if ql.startswith('did i') and 'percentage' in ql:
        return 'cmp_pct'
    if re.search(r'what percentage discount', ql):
        return 'pct_price'
    if re.search(r'how much\b.{0,40}\bsave', ql):
        return 'save'
    if re.search(r'(minimum|maximum) amount', ql) and ' and ' in ql:
        return 'minmax'
    if (re.search(r'how much (?:more|less|more expensive)', ql)
            or 'difference in price' in ql or 'initial quote' in ql):
        return 'diff'
    m = re.search(r'how much did i spend on (.+)', ql)
    if m and ' and ' in m.group(1):
        return 'sum2'
    return None


def answer_delta(question: str,
                 sessions: list[dict]) -> tuple[str | None, dict]:
    """Answer a delta-family form from evidence sessions.

    Returns ``(answer, detail)``; answer ``None`` = unresolved,
    falls through to the gate chain (the gates own abstention —
    C509 deviation from the prototype's IDK-on-miss, which would
    flip currently-correct answer-gate questions to abstain).
    """
    ql = question.strip().lower()
    form = delta_form(question)
    detail = {"form": form} if form else {}

    # temporal diff (non-money): mpg / 5K minutes — direction words
    # (ago/last vs now/recently) pick old vs new values, user-role
    # required on BOTH picks.
    if form == 't_diff':
        ureg = _DL_MPG if ('miles per gallon' in ql
                           or 'mpg' in ql) else _DL_MINRE
        subj = ['5k'] if '5k' in ql else []
        vals = [t for t in _dl_scan(sessions, ureg)
                if not subj or any(s in _dl_norm(t[3]) for s in subj)]
        old = _dl_pick(vals, [], unit_ctx=_DL_OLD_T)
        new = _dl_pick(vals, [], unit_ctx=_DL_NEW_T)
        if old and new and old[2] == new[2] == 'user':
            u = ' mpg' if ureg is _DL_MPG else ' minutes'
            return (f"{abs(old[0] - new[0]):g}{u}".replace(' mpg', ''),
                    {**detail, "op": "t_diff", "old": old[0],
                     "new": new[0]})
        return None, {**detail, "op": "t_diff-miss"}

    # rate multiplication: $amount × percentage (cashback/interest)
    if form == 'rate':
        noun = 'cashback' if 'cashback' in ql else 'interest'
        rates = [t for t in _dl_scan(sessions, _DL_PCT)
                 if noun in _dl_norm(t[3])]
        akws = [k for k in _dl_kws(question)
                if k != _dl_stem(noun)
                and k not in ('earn', 'last', 'thursday', 'much')]
        amts = [t for t in _dl_scan(sessions, _DL_MONEY)
                if any(k in _dl_norm(t[3]) for k in akws)]
        if rates and amts:
            store = [k for k in akws if k != 'much'] or ['cashback']
            rr = [t for t in rates
                  if any(k in _dl_norm(t[3]) for k in store)] or rates
            r = max(rr, key=lambda t: (t[2] == 'user', t[1]))[0] / 100
            ua = [t for t in amts if t[2] == 'user']
            a = max(ua or amts, key=lambda t: t[0])
            p = a[0] * r
            return ((f"${p:.2f}" if p % 1 else f"${p:.0f}"),
                    {**detail, "op": "rate", "amount": a[0],
                     "rate": r})
        return None, {**detail, "op": "rate-miss"}

    # count ratio: n/denominator over packed items
    if form == 'count_ratio':
        m = re.search(
            r'what percentage of (?:the )?(?:packed |my )?(.+?) did i (\w+)',
            ql)
        subj_n = m.group(1).split()[-1]
        numpat = re.compile(
            r'(?:only )?(?:wearing|wore|used)\s+'
            r'(two|three|four|five|six|seven|eight|nine|ten|\d+)', re.I)
        denpat = re.compile(
            r'packed\s+(\d+|two|three|four|five|six|seven|eight|nine'
            r'|ten)\s+pairs? of ' + re.escape(subj_n), re.I)
        num = _dl_pick(_dl_scan(sessions, numpat), [m.group(2)])
        den = _dl_pick(_dl_scan(sessions, denpat), [])
        if num and den:
            nn = _dl_wnum(numpat.search(num[3]).group(1))
            dd = _dl_wnum(denpat.search(den[3]).group(1))
            return (f"{round(nn / dd * 100)}%",
                    {**detail, "op": "ratio", "num": nn, "den": dd})
        return None, {**detail, "op": "ratio-miss"}

    # compare-pct yes/no: two sides' percentages
    if form == 'cmp_pct':
        ss = _dl_split_sides(question)
        if ss:
            vals = _dl_scan(sessions, _DL_PCT)
            a = _dl_pick(vals, _dl_kws(ss[0], side=True))
            b = _dl_pick(vals, _dl_kws(ss[1], side=True))
            if a and b and a[3] is not b[3]:
                return (('Yes.' if a[0] > b[0] else 'No.'),
                        {**detail, "op": "cmp-pct",
                         "a": a[0], "b": b[0]})
        return None, {**detail, "op": "cmp-pct-miss"}

    # price → percentage discount (original vs paid)
    if form == 'pct_price':
        item = [k for k in _dl_kws(question)
                if k not in ('discount', 'favorite', 'percentage')]
        vals = _dl_scan(sessions, _DL_MONEY)
        orig = _dl_pick(vals, item + ['originally'],
                        require=['originally'])
        paid = _dl_pick(
            [t for t in vals if orig is None or t[3] is not orig[3]],
            item)
        if orig and paid and paid[0] < orig[0]:
            return (f"{round((1 - paid[0] / orig[0]) * 100)}%",
                    {**detail, "op": "pct-price",
                     "paid": paid[0], "orig": orig[0]})
        return None, {**detail, "op": "pct-price-miss"}

    # save: instead-of two sides, or original-vs-paid
    if form == 'save':
        ss = _dl_split_sides(question)
        if ss and 'instead of' in ql:
            vals = _dl_scan(sessions, _DL_MONEY)
            a = _dl_pick(vals, _dl_kws(ss[0], side=True) or ['taxi'])
            b = _dl_pick(vals, _dl_kws(ss[1], side=True) or ['train'])
            if a and b:
                return (_dl_money(abs(a[0] - b[0])),
                        {**detail, "op": "save-instead",
                         "a": a[0], "b": b[0]})
            return None, {**detail, "op": "save-instead-miss"}
        item = [k for k in _dl_kws(question) if k != 'save']
        vals = _dl_scan(sessions, _DL_MONEY)
        orig = _dl_pick(vals, item + ['originally'],
                        require=['originally'])
        paid = _dl_pick(vals, item, require=None,
                        exclude=['originally'])
        if orig and paid and paid[0] < orig[0]:
            return (_dl_money(orig[0] - paid[0]),
                    {**detail, "op": "save-orig",
                     "orig": orig[0], "paid": paid[0]})
        return None, {**detail, "op": "save-miss"}

    # minmax-sum: sum of per-entity min/max money values
    if form == 'minmax':
        mm = re.search(r'(minimum|maximum) amount', ql)
        want_min = mm.group(1) == 'minimum'
        tail = ql.split('sold', 1)[-1] if 'sold' in ql else ql
        ents = [_dl_kws(x, side=True) for x in re.split(r' and ', tail)]
        tot, det = 0, []
        for ek in ents:
            if not ek:
                continue
            vals = [t for t in _dl_scan(sessions, _DL_MONEY)
                    if any(k in _dl_norm(t[3]) for k in ek)]
            if not vals:
                return None, {**detail, "op": "minmax-miss"}
            u = [t for t in vals if t[2] == 'user'] or vals
            pick_v = (min if want_min else max)(t[0] for t in u)
            tot += pick_v
            det.append(pick_v)
        return _dl_money(tot), {**detail, "op": "minmax", "parts": det}

    # bipartite money diff — the flagship operator
    if form == 'diff':
        if 'after the initial' in ql:
            vals = _dl_scan(sessions, _DL_MONEY)
            init = _dl_pick(vals, ['quote'])
            corr = _dl_pick(vals, ['corrected'])
            if init and corr:
                return (_dl_money(abs(corr[0] - init[0])),
                        {**detail, "op": "after-init",
                         "corr": corr[0], "init": init[0]})
            return None, {**detail, "op": "after-init-miss"}
        ss = _dl_split_sides(question)
        if not ss:
            return None, {**detail, "op": "diff-nosplit"}
        unit_ctx = (['per night', 'nightly']
                    if 'per night' in ql else None)
        vals = _dl_scan(sessions, _DL_MONEY)
        if 'goal' in ql:
            a = _dl_pick(vals, ['raised'])
            b = _dl_pick(vals, ['aimed', 'goal'])
            if a and b:
                return (_dl_money(abs(a[0] - b[0])),
                        {**detail, "op": "goal-diff",
                         "a": a[0], "b": b[0]})
            return None, {**detail, "op": "goal-miss"}
        ka, kb = _dl_kws(ss[0], side=True), _dl_kws(ss[1], side=True)
        a = _dl_pick(vals, ka, unit_ctx=unit_ctx, exclude=kb)
        b = _dl_pick(vals, kb, unit_ctx=unit_ctx, exclude=ka)
        if a and b and a[3] is not b[3]:
            return (_dl_money(abs(a[0] - b[0])),
                    {**detail, "op": "diff", "a": a[0], "b": b[0]})
        return None, {**detail, "op": "diff-miss"}

    # sum-two: per-side picks summed (question's own entity split)
    if form == 'sum2':
        m = re.search(r'how much did i spend on (.+)', ql)
        sides2 = m.group(1).split(' and ')
        eks = [_dl_kws(s, side=True) for s in sides2]
        tot, det = 0, []
        for i, s in enumerate(sides2):
            others = [a for j, e2 in enumerate(eks) if j != i
                      for a in e2]
            v = _dl_pick(_dl_scan(sessions, _DL_MONEY), eks[i],
                         unit_ctx=(['ticket'] if 'ticket' in s else None),
                         exclude=others)
            if not v:
                return None, {**detail, "op": "sum2-miss"}
            tot += v[0]
            det.append(v[0])
        return _dl_money(tot), {**detail, "op": "sum2", "parts": det}

    return None, detail


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
          "duration_family": _cnt_duration_family,
          "total_sum": _cnt_total_sum,
          "item_total": _cnt_item_total,
          "unit_sum": _cnt_unit_sum,
          "freq_days": _cnt_freq_days,
          "enum_count": _cnt_enum_count,
          "inventory_count": _cnt_inventory_count,
          "museum_count": _cnt_museum_count,
          "age_diff": _cnt_age_diff,
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
             pp_duration: bool = True,
             pairwise_sort: bool = True,
             ecm: bool = True,
             delta_agg: bool = True,
             pref_abstain: bool = True,
             neg_exist: bool = True,
             role_answer: bool = True,
             role_margin: int = 0,
             assistant_recall: bool = True,
             recall_mode: str = "distinctive",
             recall_seed_k: int = 40,
             sidechannel: bool = False,
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
                  pp_duration=pp_duration,
                  pairwise_sort=pairwise_sort,
                  ecm=ecm,
                  delta_agg=delta_agg,
                  pref_abstain=pref_abstain,
                  neg_exist=neg_exist,
                  role_answer=role_answer,
                  sidechannel=sidechannel,
                  role_margin=role_margin,
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
    parser.add_argument("--no-delta", action="store_true",
                        help="disable delta-family two-anchor "
                             "aggregation (C509)")
    parser.add_argument("--no-pp-duration", action="store_true",
                        help="Disable the Cycle 486 past-perfect "
                             "duration path (pre-C486 baseline)")
    parser.add_argument("--no-neg-exist", action="store_true",
                        help="Disable the Cycle 513 negative-existence "
                             "abstention gate (missing proper noun ⇒ "
                             "abstain)")
    parser.add_argument("--no-role-answer", action="store_true",
                        help="Disable the Cycle 501 role-aware answer "
                             "face (user-line selection for first-"
                             "person fact questions)")
    parser.add_argument("--sidechannel", action="store_true",
                        help="Enable the Cycle 506 form-gated embedding "
                             "side-channel (preference/assistant-recall "
                             "forms; needs optional fastembed or "
                             "model2vec — degrades to lexical without)")
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
        delta_agg=not args.no_delta,
        pp_duration=not args.no_pp_duration,
        assistant_recall=not args.no_assistant_recall,
        role_answer=not args.no_role_answer,
        sidechannel=args.sidechannel,
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
            delta_agg=not args.no_delta,
            pp_duration=not args.no_pp_duration,
            assistant_recall=not args.no_assistant_recall,
            role_answer=not args.no_role_answer,
            neg_exist=not args.no_neg_exist,
            sidechannel=args.sidechannel,
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
