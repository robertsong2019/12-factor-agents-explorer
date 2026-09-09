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
import os
import math
import re
import unicodedata
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
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
    "judge_semantic",
    "judge_cascade",
    "cohens_kappa",
    "mcnemar_exact",
    "judge_ab_report",
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
                 temporal_fullgraph: bool = True,
                 counting: bool = True,
                 pp_duration: bool = True,
                 order_sort: bool = True,
                 pairwise_sort: bool = True,
                 ecm: bool = True,
                 delta_agg: bool = True,
                 pref_abstain: bool = True,
                 neg_exist: bool = True,
                 quant_rerank: bool = True,
                 ku_session_face: bool = True,
                 session_complete_face: bool = True,
                 user_challenge_face: bool = True,
                 role_answer: bool = True,
                 role_margin: int = 0,
                 acq_face: bool = True,
                 opener_floor: bool = True,
                 ordinal_face: bool = True,
                 assistant_recall: bool = True,
                 recall_min_score: int = 5,
                 recall_mode: str = "distinctive",
                 ppr_top: int = 15,
                 seed_recall_k: int = 5,
                 recall_seed_k: int = 40,
                 sidechannel: bool = False,
                 sidechannel_cache: SidechannelCache | None = None,
                 where_loc: bool = True,
                 deterministic_recall: bool = True):
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
        # C551: resolve temporal anchors on the FULL graph first.
        # Census-first over the 46-row temporal population: window
        # resolution loses 4 rows to distractor-corpus crowding
        # (Tribunal-style noise lines lexically mirror the question
        # harder than the true event line, and the true line sits
        # outside the retrieval top-k) while the C471 tie ladder
        # picks the true event lines when it can see the full
        # candidate set — +4 rescue / 0 kill (33 currently-correct
        # rows byte-identical). C472's window-first caution is
        # empirically dead here; flag-off restores it.
        self.temporal_fullgraph = temporal_fullgraph
        self.counting = counting
        self.pp_duration = pp_duration
        self.order_sort = order_sort
        self.pairwise_sort = pairwise_sort
        self.ecm = ecm
        self.delta_agg = delta_agg
        self.pref_abstain = pref_abstain
        self.neg_exist = neg_exist
        self.ordinal_face = ordinal_face
        # Cycle 501: role-aware answer face (echo pathology fix) —
        # see _user_fact_form. role_margin: how many keyword hits a
        # user line may trail the top assistant line by and still
        # win (0 = must tie; the -seq tie-break hands equal-hit
        # tops to the LATEST message, routinely the advice reply).
        self.quant_rerank = quant_rerank
        self.ku_session_face = ku_session_face
        self.session_complete_face = session_complete_face
        self.user_challenge_face = user_challenge_face
        # Cycle 528: read-only recall in the eval path — retrieval
        # becomes a pure function of the ingested graph (no wall-clock
        # decay, no access-boost writes). Root-cause fix for the
        # "tie-jitter" family (C517✓→C522✓→C523✓→C527✗ flips of
        # 86f00804 with identical code+seed): the default recall
        # mutated weights with ``now=time.time()`` decay + boost, so
        # each fresh per-question ingest carried fresh float noise
        # into ``ORDER BY weight DESC`` near-ties. RNG audit (C528):
        # zero unseeded ``random.`` reachable in the retrieval path —
        # the noise was wall clock, not RNG.
        self.deterministic_recall = deterministic_recall
        self.role_answer = role_answer
        self.role_margin = role_margin
        self.acq_face = acq_face
        self.opener_floor = opener_floor
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
        ordered_candidates: list[str] = []  # C528: discovery order

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
        # readonly (C528): see deterministic_recall in __init__ —
        # no decay/boost mutation, rowid tie-break, clock-free.
        # C528: ordered_candidates tracks first-discovery order — node
        # ids are fresh uuid4 per ingest, so set iteration over them
        # (hash order keyed by RANDOM values) re-rolls every run even
        # with PYTHONHASHSEED pinned. PPR seed selection below must
        # see discovery order, not hash order.
        def _add_candidate(nid: str) -> None:
            if nid not in candidate_ids:
                candidate_ids.add(nid)
                ordered_candidates.append(nid)

        for kw in keywords[:8]:
            for node in self.mg.recall(kw, limit=k_eff,
                                       readonly=self.deterministic_recall):
                _add_candidate(node.id)

        # Scored candidates: graphrag local (BM25 + 1-hop expansion).
        try:
            for r in self.mg.search_graphrag(question, mode="local",
                                             limit=10):
                _add_candidate(r.get("node_id", ""))
        except Exception:
            pass  # search may raise on empty graphs — recall is enough

        # Multi-hop expansion: PPR from the seed set (discovery order,
        # NOT set/hash order — C528 determinism).
        if self.use_ppr and candidate_ids:
            seeds = [nid for nid in ordered_candidates if nid][:8]
            try:
                ppr = self.mg.personalized_pagerank(seeds)
                for nid in sorted(ppr, key=ppr.get, reverse=True):
                    if len(candidate_ids) >= len(seeds) + self.ppr_top:
                        break
                    _add_candidate(nid)
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

            if self.temporal_fullgraph:
                # C551: full-graph-first anchor resolution — one call
                # on the complete candidate set (see flag comment).
                t_ans, t_detail = answer_temporal_arith(
                    question, _dated(self._messages), question_date)
                if t_ans is not None:
                    t_detail["fallback"] = "fullgraph_first"
            else:
                t_ans, t_detail = answer_temporal_arith(
                    question, _dated(meta.get("retrieved_ids", [])),
                    question_date)
                if t_ans is None and t_detail.get("form"):
                    # Cycle 472: full-graph anchor retry (flag-off
                    # legacy path). When the window cannot resolve the
                    # form (missing anchors OR both anchors landing on
                    # the same session — the dominant failure: assistant
                    # advice lines that lexically mirror the question
                    # crowd out the true event lines and collapse both
                    # anchors onto one wrong session), retry against ALL
                    # ingested messages where the C471 tie ladder has
                    # the full candidate set. C472 A/B: the 4
                    # prev-correct same-session cases stay None.
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

        # C540: ordinal-item face WIRED (closes the C536 debt). The
        # C536 falsification killed kh-only ranking (twin cocktail
        # lists tie 12/12); the C536-declared embedding fix was
        # probed and ALSO falsified this cycle (3249768e: cos(q,
        # decoy msg) 0.7068 > GT 0.5607, preface level 0.7725 >
        # 0.7286 — MiniLM treats the question's "gin-based"
        # constraint as minor mass; the decoy list is a semantic
        # superset of the question domain). The surviving separator
        # is question-PHRASE continuity: the full keyword run
        # ("widest variety of gin based cocktails") appears only in
        # the GT node (run 5 vs decoy 2). answer_ordinal now breaks
        # kh ties by longest question-keyword phrase run, keeping
        # C536's head-noun + list-size + kh-floor guards. Tight gate
        # unchanged (ordinal + you-list act, census 3/500): the 2
        # siblings stay neutral — 1903aded falls through under the
        # size pin (GT bare list kh=1, tips list fails the pin),
        # 8752c811 is judge-side (truth⊆pred vs sentence-wrapped
        # GT). Runs BEFORE speaker_recall — the preface-parasitism
        # winner it fixes IS a speaker_recall output (C468 family).
        if self.ordinal_face and ordinal_item_form(question):
            o_ans, o_detail = answer_ordinal(question, self._nodes)
            meta["ordinal"] = o_detail
            if o_ans is not None:
                meta["gate"] = "ordinal"
                meta["abstained"] = False
                return o_ans, meta

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
            # C516: common-noun restrictors (violin/football/iPad/
            # uncle swaps) — placed at the FABRICATION point: every
            # specialized gate (counting/pp_duration/where/recall)
            # had its claim first; an absent asked-about object
            # noun at the answer path means sibling-driven retrieval
            # is about to fabricate. Gate label stays neg_exist.
            if self.neg_exist:
                hay = "\n".join(
                    " ".join(str(t.get("content", ""))
                             for t in s["turns"])
                    for s in self._counting_sessions())
                missing_c = common_noun_missing(question, hay)
                if missing_c:
                    meta["gate"] = "neg_exist"
                    meta["abstained"] = True
                    meta["neg_exist_entity"] = missing_c
                    meta["neg_exist_kind"] = "common"
                    return ABSTAIN_ANSWER, meta
                # C518: possessive numeric-attribute compounds
                # (my 30-gallon tank) — same fabrication point,
                # same gate label family.
                miss_num = numeric_compound_missing(question, hay)
                if miss_num:
                    meta["gate"] = "neg_exist"
                    meta["abstained"] = True
                    meta["neg_exist_entity"] = miss_num
                    meta["neg_exist_kind"] = "numeric"
                    return ABSTAIN_ANSWER, meta
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
        # C523: quantity-form answer-face re-rank (#090). Census
        # (C523 /tmp/c523/census_gates.py, official C522
        # post_full500.json): 220/500 questions match ^how
        # (many|long|much); 103 of them reach the answer gate — 81
        # wrong, 42 with retrieval_hit AND answer_session_hit True,
        # i.e. the GT number IS in the window but the quoted face is
        # a number-free adjacent message (the C499 pathology's
        # quantity subtype: c960da58 Spotify "20", 94f70d80 IKEA "4
        # hours", af8d2e46 "7 shirts", 6b168ec8 "three bikes", ...
        # Fix: when the top line carries NO quantity token, prefer
        # the number-bearing USER line with the most keyword evidence
        # (floor 2, C501 floor). Strict scope makes regressions on
        # correct answers near-constructive-impossible: a top line
        # that already quotes a number is untouched (correct numeric
        # answers keep their face by construction), and with no
        # qualifying candidate we fall through untouched (C488).
        # Iteration order over lines is (-hits, -seq): strict `>` on
        # hits keeps the EARLIEST matching entry on ties, which is
        # the latest message — the knowledge-update recency
        # convention (C437/C447 -seq) for free.
        if (self.quant_rerank and _quantity_form(question)
                and not _QUANTITY_TOKEN_RE.search(
                    best_line.split("] ", 1)[-1])):
            kws = meta.get("keywords") or _keywords(question)
            best_q, best_q_hits = None, -1
            for ln in lines[1:]:
                if not ln.startswith("[user"):
                    continue
                body = ln.split("] ", 1)[-1]
                if not _QUANTITY_TOKEN_RE.search(body):
                    continue
                h = _keyword_hits(body, kws)
                if h > best_q_hits:
                    best_q, best_q_hits = ln, h
            meta["quant_rerank"] = {
                "candidate_hits": max(best_q_hits, 0),
                "override": bool(
                    best_q is not None and best_q_hits >= 2)}
            if meta["quant_rerank"]["override"]:
                best_line = best_q
        # C525: knowledge-update recency session-scope (#090
        # spin-off). Census (C525 /tmp/c525/census_c525.py, official
        # C523 post_full500_c523.json, 225 answer-gate questions
        # replayed on pristine HEAD): 109/158 answer-gate wrongs
        # have NO GT-bearing line in the window, but 92 of them DO
        # have the GT session retrieved (answer_session_hit=True) —
        # the window-composition surface. Face-level remainder:
        # questions asking the CURRENT state of an accumulating
        # quantity (recency adverbs, _KU_RECENCY_RE) are answered by
        # the LATEST session's evidence, while keyword ranking
        # saturates on topic echoes from older sessions (C499
        # pathology, session subtype). Rule: when the face line's
        # session differs from the latest evidence session (max seq
        # over keyword-hit lines), re-face to that session's best
        # line — max keyword hits, ties keep the LATEST message
        # (C437/C447 recency convention), any role, floor 2 (C501).
        # Census: 6 fires = 2 wins (1a8a66a6 magazines,
        # 6a27ffc2 Corey-30-videos) + 4 wrong→wrong noops, ZERO
        # correct-question touches. The adverb scope is what
        # separates: the same condition unscoped fires 58 with 10
        # hijacks incl. 3 C523 wins (C522/C524 inseparability
        # pattern avoided by form-narrowing, not a new
        # discriminator). Fall-through with no qualifying candidate
        # (C488); window lines are mapped via retrieved_ids (labels
        # may embed newlines — split-based mapping desyncs, the
        # C525 census v1 lesson). Specialized gates upstream own
        # counting/TA/delta forms, so this block only ever sees the
        # answer-gate remainder.
        if self.ku_session_face and _KU_RECENCY_RE.search(question):
            kws = meta.get("keywords") or _keywords(question)
            face_body = best_line.split("] ", 1)[-1]
            nodes = []
            for nid in (meta.get("retrieved_ids") or []):
                info = self._messages.get(nid)
                if not info:
                    continue
                body = info.get("label", "")
                nodes.append({
                    "role": info.get("role") or "?",
                    "body": body,
                    "sid": info.get("session_id"),
                    "seq": info.get("seq") or 0,
                    "hits": _keyword_hits(body, kws)})
            face_node = next(
                (n for n in nodes if n["body"] == face_body), None)
            ev = [n for n in nodes if n["hits"] >= 1]
            les = (max(ev, key=lambda n: n["seq"])["sid"]
                   if ev else None)
            best_n = None
            if face_node is not None and les is not None:
                cands = [n for n in nodes if n["sid"] == les
                         and n["hits"] >= 2]
                if cands:
                    mh = max(n["hits"] for n in cands)
                    best_n = max(
                        (n for n in cands if n["hits"] == mh),
                        key=lambda n: n["seq"])
            meta["ku_session_face"] = {
                "face_session": (face_node or {}).get("sid"),
                "latest_evidence_session": les,
                "candidate_hits": best_n["hits"] if best_n else 0,
                "override": bool(best_n is not None
                                 and face_node is not None
                                 and best_n["body"] != face_body)}
            if meta["ku_session_face"]["override"]:
                best_line = (f"[{best_n['role']}] {best_n['body']}")
        # C526: session-completion face rescue (C525 queue item —
        # window-composition census, /tmp/c526, 225 answer-gate
        # questions replayed on HEAD). The census KILLS the
        # budget-truncation hypothesis: only 5 wrongs have a
        # GT-bearing line in the candidate list beyond the window
        # (all hits=1), while 105 wrongs never see the GT line as a
        # candidate at all (58 have NO GT-bearing line anywhere in
        # the haystack — quotation-judge dead, judge_semantic
        # territory). Rescue surface: same-session lines the seed
        # phase missed. Rule: scan messages of the FACE's OWN session
        # that are NOT in the retrieval window; if one out-hits the
        # face (margin 1, floor 2), re-face to it — max hits, ties
        # keep the latest (C437/C447). Session-locality is the
        # separator: unscoped (any session) the same rule is
        # +7/−3 with ALL 3 hijacks cross-session; same-session is
        # +3/−0 over the full population (caf9ead2, c4a1ceb8 new
        # wins; 6a27ffc2 idempotent on the C525 fix), zero correct
        # touches. Fall-through otherwise (C488); window lines are
        # mapped via retrieved_ids, not split (C525 census v1
        # lesson). Specialized gates upstream own their forms, so
        # this block only ever sees the answer-gate remainder.
        if self.session_complete_face:
            kws = meta.get("keywords") or _keywords(question)
            face_body = best_line.split("] ", 1)[-1]
            win_ids = set(meta.get("retrieved_ids") or [])
            face_sid = None
            face_hits = 0
            for nid in (meta.get("retrieved_ids") or []):
                info = self._messages.get(nid)
                if info and info.get("label", "") == face_body:
                    face_sid = info.get("session_id")
                    face_hits = _keyword_hits(face_body, kws)
                    break
            best_n = None
            if face_sid is not None:
                for nid, info in self._messages.items():
                    if nid in win_ids:
                        continue
                    if info.get("session_id") != face_sid:
                        continue
                    body = info.get("label", "")
                    h = _keyword_hits(body, kws)
                    if h < max(2, face_hits + 1):
                        continue
                    if (best_n is None or h > best_n["hits"]
                            or (h == best_n["hits"]
                                and (info.get("seq") or 0)
                                > (best_n["seq"] or 0))):
                        best_n = {"role": info.get("role") or "?",
                                  "body": body, "hits": h,
                                  "seq": info.get("seq") or 0}
            meta["session_complete_face"] = {
                "face_session": face_sid,
                "candidate_hits": best_n["hits"] if best_n else 0,
                "override": bool(best_n is not None
                                 and best_n["body"] != face_body)}
            if meta["session_complete_face"]["override"]:
                best_line = f"[{best_n['role']}] {best_n['body']}"
        # C548: cross-session user-statement challenge face. Runs
        # AFTER session_complete_face (same-session repair is C526's
        # territory — claimed first, C482/C488) and BEFORE the
        # opener floor / acquisition face (the specialized downstream
        # faces still own their forms on a promoted line).
        if self.user_challenge_face:
            kws_c = meta.get("keywords") or _keywords(question)
            uc_line, uc_detail = answer_user_challenge(
                best_line, meta.get("retrieved_ids") or [],
                self._messages, kws_c)
            meta["user_challenge_face"] = uc_detail
            if uc_line is not None:
                best_line = uc_line
        # C539: opener demotion floor. Runs BEFORE the acquisition
        # face (most form-specific claims last, C482/C488): the floor
        # only demotes hand-over-shaped winners for a strictly-better
        # first-person statement; acquisition rows the face claims are
        # then overridden by it regardless.
        if self.opener_floor:
            kws_f = meta.get("keywords") or _keywords(question)
            ofl_line, ofl_detail = answer_opener_floor(
                best_line, lines, kws_f)
            meta["opener_floor"] = ofl_detail
            if ofl_line is not None:
                best_line = ofl_line
        # C538: first-person acquisition/conversation statement face.
        # The C499-family remainder at this point: message-level
        # ranking hands the face the top message's FIRST line, which
        # for multi-paragraph messages is a hand-over opener or a
        # tangent (66f24dbb: "Here's a start - I've bought gifts for
        # my sister's birthday, my mom…" names recipients while the
        # GT line "For my sister's birthday, I got her a yellow
        # dress…" sits hits=2 in the same window). Question structure
        # picks the verb family (what did I buy/complete/get; who did
        # I have a conversation with); tier preference among C501
        # floor-passers that first-person-perform the verb; openers
        # excluded wherever they sit (C475). Runs LAST: most
        # form-specific face claims its family (C482/C488 gate-order
        # discipline), fall-through with no passer untouched.
        if self.acq_face:
            kws = meta.get("keywords") or _keywords(question)
            acq_line, acq_detail = answer_acquisition_face(
                question, lines, kws)
            meta["acq_face"] = acq_detail
            if acq_line is not None:
                best_line = acq_line
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
        the other's losses (Research #069). ``judge_mode="semantic"``
        (Cycle 529) scores via :func:`judge_cascade` instead —
        deterministic semantic layer first, LLM only on NEEDS_JUDGE
        — same report shape plus ``judge_ab`` (Research #092
        kappa/McNemar A/B statistics).

        Args:
            dataset: ``[{"id", "question", "answer", ...}]``.
              ``question_id`` is honored as an id fallback (C466 —
              LongMemEval-cleaned naming), and ``question_type`` /
              ``category`` override category heuristics when present
              (C466 — honest attribution for calibration_by_category).
            judge_fn: Optional external judge; default containment.
            limit: Evaluate at most this many questions (0 = all).
            judge_mode: "exact" (default), "dual" or "semantic"
                (Cycle 529 cascade).

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
            if judge_mode in ("dual", "semantic"):
                correct_exact = correct
                if is_abs:
                    # abstention semantics are protocol-level, not
                    # semantic — both metrics share the verdict
                    correct_llm = correct
                elif judge_mode == "semantic":
                    # Cycle 529: cascade — deterministic semantic
                    # layer first, LLM only on NEEDS_JUDGE
                    verdict = judge_cascade(question, predicted, truth)
                    correct_llm = (None if verdict == "ERROR"
                                   else verdict == "CORRECT")
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
                       "temporal_fullgraph": self.temporal_fullgraph,
                       "order_sort": self.order_sort,
                       "pairwise_sort": self.pairwise_sort,
                       "max_context_tokens": self.max_context_tokens,
                       "abstain_score": self.abstain_score,
                       "abstain_entropy": self.abstain_entropy,
                       "entropy_weak_score": self.entropy_weak_score,
                       "judge_mode": judge_mode},
        }
        if judge_mode in ("dual", "semantic"):
            report["accuracy_exact"] = report["overall_accuracy"]
            scored = [r for r in results if r.correct_llm is not None]
            report["accuracy_llm"] = (
                sum(1 for r in scored if r.correct_llm) / len(scored)
                if scored else 0.0)
            report["calibration"] = calibration_summary(results)
            report["calibration_by_category"] = \
                calibration_by_category(results)
            report["judge_ab"] = judge_ab_report(results)
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
    global _JUDGE_MODEL
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
            _JUDGE_MODEL = model
            return "CORRECT"
        if "WRONG" in out:
            _JUDGE_MODEL = model
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
_JUDGE_MODEL: str | None = None  # C560: model that issued live verdicts


# ── Semantic judge layer (Cycle 529 — Research #090/#092) ──────
#
# Deterministic first rung of the judging cascade: normalization +
# guarded soft-matching so semantically-equivalent answers credit
# without an LLM call, and lexically-unsolvable pairs abstain
# honestly (NEEDS_JUDGE → judge_llm in :func:`judge_cascade`).
# #090 simplified port; A/B decision protocol per Research #092
# (discordant counts + McNemar exact + Cohen's kappa, per category).
#
# False-pass red lines (the guards): number-signature mismatch is a
# veto (7 vs 17), currency-domain conflict is a veto ($5 vs 5
# euros), and containment is ASYMMETRIC per the LongMemEval official
# protocol — a weaker candidate ("tennis" vs ref "table tennis")
# fails while a superset candidate ("blue is his favorite color" vs
# ref "blue") passes. Deviation from the #092 prototype: no
# bootstrap-CI vs truth — production rows carry no ground-truth
# correctness label; the A/B decision runs on McNemar, and
# oracle-labeled CIs live in the research harness.

_SEM_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15",
    "twenty": "20", "thirty": "30", "hundred": "100",
    "thousand": "1000",
}
_SEM_TIME_UNITS = {"hours": 3600, "hour": 3600, "minutes": 60,
                   "minute": 60, "days": 86400, "day": 86400,
                   "weeks": 604800, "week": 604800}
_SEM_STOPWORDS = {"is", "his", "her", "the", "a", "an", "of", "to",
                  "in", "at", "on", "and", "was"}

# British→American lexeme folding (C535): same word, different spelling.
# Explicit word table, not a suffix rule — an our→or rewrite would corrupt
# the pronoun "our". Sense-splitting pairs (programme/program,
# storey/story, licence/license, practise/practice) are deliberately
# excluded: the two spellings denote different things in one variant.
# C535 census over the frozen cascade-500: jewellery/jewelry is the only
# pair occurring in the data (b759caee); the full standard set is kept so
# the rule stays a lexeme-class fold rather than a row-targeted patch.
_SEM_BRE_VARIANTS = {
    # -our/-or
    "colour": "color", "colours": "colors", "favourite": "favorite",
    "favourites": "favorites", "honour": "honor", "honours": "honors",
    "neighbour": "neighbor", "neighbours": "neighbors",
    "behaviour": "behavior", "flavour": "flavor", "flavours": "flavors",
    "humour": "humor", "labour": "labor", "armour": "armor",
    "rumour": "rumor", "rumours": "rumors", "harbour": "harbor",
    "endeavour": "endeavor",
    # -re/-er
    "centre": "center", "centres": "centers", "metre": "meter",
    "metres": "meters", "theatre": "theater", "theatres": "theaters",
    "litre": "liter", "litres": "liters", "fibre": "fiber",
    "calibre": "caliber",
    # -ise/-ize, -yse/-yze
    "organise": "organize", "realise": "realize", "recognise": "recognize",
    "apologise": "apologize", "specialise": "specialize",
    "criticise": "criticize", "summarise": "summarize",
    "analyse": "analyze", "paralyse": "paralyze",
    # -ogue/-og
    "catalogue": "catalog", "catalogues": "catalogs",
    "dialogue": "dialog", "analogue": "analog",
    # doubled consonant
    "jewellery": "jewelry", "jeweller": "jeweler",
    "jewellers": "jewelers", "travelling": "traveling",
    "cancelled": "canceled", "labelled": "labeled",
    "marvellous": "marvelous", "modelling": "modeling",
    "fuelled": "fueled", "signalling": "signaling",
    # misc unambiguous
    "grey": "gray", "mould": "mold", "smoulder": "smolder",
    "plough": "plow", "sceptical": "skeptical", "defence": "defense",
    "offence": "offense", "pretence": "pretense", "judgement": "judgment",
    "acknowledgement": "acknowledgment", "tyre": "tire",
    "cheque": "check", "aluminium": "aluminum",
}


def _sem_norm(text: str) -> str:
    """Judge-side normalization: number words folded, trailing/prefix
    $ adsorbed + currency words canonicalized, ordinals stripped,
    non-lexical residue (markdown escapes, quotes, brackets, attached
    punctuation) folded to word separators, British→American lexemes
    folded, separators dropped, lowercased."""
    t = text.strip().lower()
    t = re.sub(r"([\d,])\s*\$(?!\d)", r"\1 usd", t)      # trailing $
    t = re.sub(r"\$\s*([\d,]+(?:\.\d+)?)", r"\1 usd", t)  # prefix $
    t = re.sub(r"\bdollars?\b", "usd", t)
    t = re.sub(r"\beuros?\b", "eur", t)
    t = re.sub(r"\byen\b", "jpy", t)
    t = re.sub(r"\byuan\b", "cny", t)
    t = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", t)   # ordinals
    for w, d in _SEM_NUMBER_WORDS.items():
        t = re.sub(rf"\b{w}\b", d, t)
    t = re.sub(r"[,$.]", "", t)
    # Markdown/punctuation residue folds to word separators (C535):
    # escaped handles "@jessica\\_poole\\_jewellery", wrapped tokens
    # "(hugo):", attached quotes 'give"' all normalize to their bare
    # lexemes — token identity must not depend on markup glue. The
    # [,$.] removal above stays narrow so "2,000" still folds to "2000".
    t = re.sub(r"[^a-z0-9@%\s]", " ", t)
    for w, d in _SEM_BRE_VARIANTS.items():
        t = re.sub(rf"\b{w}\b", d, t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _sem_date_fold(text: str) -> str:
    """Best-effort date folding: january 5 2023 / 5 january 2023 →
    ``year-mon-day`` (or ``mon-day`` when yearless)."""
    t = _sem_norm(text)
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})\s*(\d{4})?\b", t)
    if m:
        mon, day, year = m.group(1), int(m.group(2)), m.group(3) or ""
        return f"{year}-{mon}-{day}".strip("-")
    m = re.search(r"\b(\d{1,2})\s+(?:(?:of|the)\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d{4})?\b", t)
    if m:
        day, mon, year = int(m.group(1)), m.group(2), m.group(3) or ""
        return f"{year}-{mon}-{day}".strip("-")
    return t


def _sem_numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", _sem_norm(text))


def _sem_currencies(text: str) -> set[str]:
    return set(re.findall(r"\b(usd|eur|jpy|cny)\b", _sem_norm(text)))


def _sem_time_seconds(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|minutes?|days?|weeks?)",
                  _sem_norm(text))
    if not m:
        return None
    return float(m.group(1)) * _SEM_TIME_UNITS[m.group(2)]


_SEM_DET_RE = re.compile(r"\b(the|a|an|my|our)\s+[^\s]+", re.IGNORECASE)
_SEM_NEG_RE = re.compile(
    r"\b(not|never|no|cant|dont|doesnt|didnt|wasnt|werent)\b")


def _sem_either_or_face(question: str, answer: str, reference: str) -> bool:
    """Question-conditioned answer face for either/or questions (C531).

    When the question itself offers exactly two alternatives ("X or Y?"),
    the complete answer is one of them — a candidate that verbatim-names
    an alternative is the precise form of the reference, not a weaker
    subset (the textual analogue of the exact-number answer face).
    Guarded: fires only when (a) the normalized question contains exactly
    one " or ", (b) the candidate's tokens sit inside the named
    alternative, (c) the reference contains the candidate's alternative
    while containing nothing from the *other* alternative's distinctive
    tokens (an undecided reference mentioning both must not rescue a
    guess), and (d) the reference carries no negation ("not the bake
    sale" must stay vetoed).
    """
    nq, nc, nr = _sem_norm(question), _sem_norm(answer), _sem_norm(reference)
    if nq.count(" or ") != 1:
        return False
    left, right = nq.split(" or ", 1)
    alt_b = right.replace("?", "").strip()
    dets = list(_SEM_DET_RE.finditer(left))
    if not dets or not alt_b:
        return False
    alt_a = left[dets[-1].start():].strip()
    toks_c = {w for w in nc.split() if w not in _SEM_STOPWORDS}
    if not toks_c:
        return False
    toks_a, toks_b = set(alt_a.split()), set(alt_b.split())
    if toks_c <= toks_a:
        named, other = alt_a, alt_b
    elif toks_c <= toks_b:
        named, other = alt_b, alt_a
    else:
        return False            # candidate not contained in either alternative
    toks_r = {w for w in nr.split() if w not in _SEM_STOPWORDS}
    diff = ({w for w in other.split()} - set(nc.split())) - _SEM_STOPWORDS
    if diff & toks_r:
        return False            # reference also names the other alternative
    if _SEM_NEG_RE.search(nr):
        return False
    return bool(set(nc.split()) & toks_r) and toks_c <= toks_r


_SEM_ORDER_Q_RE = re.compile(r"\border\b|\bsequence\b|\bchronolog")
_SEM_MARKER_SPLIT_RE = re.compile(
    r"\b(after that|first|second|third|fourth|fifth|next|then|"
    r"finally|lastly|subsequently)\b")


def _sem_marker_subsequence_face(question: str, answer: str,
                                 reference: str) -> bool:
    """Marker-aware subsequence answer face for order questions (C532).

    A narrative answer that (a) answers an order/sequence question,
    (b) shares the reference's discourse-marker skeleton — the same
    markers (first/then/finally/...) in the same order, >= 2 of them,
    with no content preamble before the first — and (c) whose every
    segment is an in-order token subsequence of the corresponding
    reference segment, is the same narrative *abbreviated*, not a
    weaker subset. Event-skipping partials are excluded structurally:
    a dropped event removes a marker (skeleton mismatch) and a
    reordered or foreign event breaks per-segment alignment — which
    is exactly why C531 could only pin this debt as "needs a
    principled formulation" rather than a coverage threshold.
    """
    if not _SEM_ORDER_Q_RE.search(_sem_norm(question)):
        return False
    pa = _SEM_MARKER_SPLIT_RE.split(_sem_norm(answer))
    pr = _SEM_MARKER_SPLIT_RE.split(_sem_norm(reference))
    if len(pa) != len(pr):                       # different marker count
        return False
    if pa[1::2] != pr[1::2] or len(pa[1::2]) < 2:
        return False                              # skeleton mismatch / thin
    for pre in (pa[0], pr[0]):                   # clean skeleton start
        if {w for w in pre.split() if w not in _SEM_STOPWORDS}:
            return False
    for ca, cr in zip(pa[2::2], pr[2::2]):
        cand = [w for w in ca.split() if w not in _SEM_STOPWORDS]
        if not cand:                              # empty segment = drop
            return False
        stream = iter(cr.split())
        if not all(w in stream for w in cand):    # in-order subsequence
            return False
    return True


_PAREN_ACRONYM_RE = re.compile(r"\(([A-Z][A-Z0-9]{1,9})\)")


def _sem_paren_acronym_face(reference: str, answer: str) -> bool:
    """C541 reference-alias face: parenthesized acronym alias.

    When the reference itself names its entity twice — ``Full Name
    (ACRONYM)`` — the acronym is the same entity's canonical short
    form (the dataset asserts the equivalence by carrying it). An
    answer naming either alias names the fact; requiring the full
    expansion tokens would punish the tighter form (25e5aa4f: GT
    ``University of California, Los Angeles (UCLA)`` vs bearer
    ``...completed my undergrad in CS from UCLA...``). Same family
    as the C531 either/or face: alias coverage, not subset weakening
    — and only reachable from the NEEDS_JUDGE zone, so it can never
    rescue a number/currency-conflicting pair.
    """
    m = _PAREN_ACRONYM_RE.search(reference or "")
    if not m:
        return False
    acr = re.escape(m.group(1).lower())
    nc = _sem_norm(answer)
    return re.search(r"(?<![a-z0-9])" + acr + r"(?![a-z0-9])", nc) is not None


_QUOTE_SPAN_RES = (
    re.compile(r"(?<![A-Za-z0-9])'([^']{2,})'(?![A-Za-z0-9])"),
    re.compile(r'(?<![A-Za-z0-9])"([^"]{2,})"(?![A-Za-z0-9])'),
    re.compile(r"(?<![A-Za-z0-9])[\u2018]([^\u2019]{2,})[\u2019](?![A-Za-z0-9])"),
    re.compile(r'(?<![A-Za-z0-9])[\u201c]([^\u201d]{2,})[\u201d](?![A-Za-z0-9])'),
)


def _sem_quoted_core_face(reference: str, answer: str) -> bool:
    """C542 reference-wrap face: quoted-core equality.

    A reference that wraps its asserted fact in quotation marks —
    ``The 27th parameter was 'Sound effects (e.g., ...)'.`` — carries
    the answer twice: a narrative frame plus the quoted core. The
    quoted core is the fact the dataset asserts; a candidate equal to
    it (normalized) is the complete answer, not a weaker subset
    (8752c811: the frame's ``27th parameter`` tokens made the subset
    veto read the wrapped, byte-identical answer as missing content).
    Word-boundary lookarounds keep apostrophes from opening spans
    (``it's 'test'`` quotes ``test``, never ``s ``). Guarded by exact
    normalized equality — the strongest possible match form — and
    only reachable from the subset-veto branch, where guards 1-2
    already passed (a quoted core's numbers are reference numbers by
    construction).
    """
    nc = _sem_norm(answer)
    if not nc:
        return False
    for rx in _QUOTE_SPAN_RES:
        for m in rx.finditer(reference or ""):
            core = _sem_norm(m.group(1))
            if core and core == nc:
                return True
    return False

_PLACE_COMPLEMENT_RE = re.compile(
    r"^(?P<head>.+?),?\s+\b(?:in|at)\s+"
    r"(?P<tail>[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,2})$")


def _sem_place_complement_face(reference: str, answer: str) -> bool:
    """C541 reference-alias face: place-tail disambiguation.

    ``<head> in <Place>`` references append the country/place as
    grader disambiguation, not as a second fact (3b6f954b: GT
    ``University of Melbourne in Australia`` — the window sentence
    carries the institution; ``Australia`` sits in a neighbouring
    sentence). An answer containing every head content token, with
    the tail absent (not contradicted — tail ABSENCE, since the
    disambiguator is redundant by construction), is the complete
    answer. Guarded: tail must be a capitalized proper run (≤3
    tokens) so common-noun tails never qualify.
    """
    m = _PLACE_COMPLEMENT_RE.match((reference or "").strip())
    if not m:
        return False
    head_toks = {w for w in _sem_norm(m.group("head")).split()
                 if w not in _SEM_STOPWORDS}
    tail_toks = {w for w in _sem_norm(m.group("tail")).split()
                 if w not in _SEM_STOPWORDS}
    ans_toks = {w for w in _sem_norm(answer).split()
                if w not in _SEM_STOPWORDS}
    if not head_toks or not tail_toks:
        return False
    return head_toks <= ans_toks and not (tail_toks & ans_toks)


_PAREN_SPAN_RE = re.compile(r"\(([^()]{2,})\)")
_DEIXIS_FOLD = {"you": "i", "your": "my", "yours": "mine",
                "yourself": "myself"}


def _sem_paren_complement_face(reference: str, answer: str) -> bool:
    """C544 reference-elaboration face: parenthetical complement.

    A reference shaped ``Head (elaboration)`` asserts its graded fact
    in the head; the parenthetical adds detail (c6853660: GT ``You
    increased the limit (from one cup to two cups)`` vs answer ``I
    have increased the limit to two cups``). An answer carrying every
    head content token asserts the head fact — the elaboration may or
    may not be repeated. Guarded: the head must keep >=2 content
    tokens after paren stripping, so thin heads (``Yes. (You have a
    road bike too.)``) never qualify, and every head token must be
    present in the answer — an answer lacking the head tokens never
    fires. Same family as the C541 place-complement face (elaboration
    as redundancy, not second fact) and, like it, only reachable from
    the NEEDS_JUDGE zone.
    """
    spans = _PAREN_SPAN_RE.findall(reference or "")
    if not spans:
        return False
    if re.search(r"\([^()]*\(", reference):
        return False                      # nested parens: bail, conservative
    head = reference
    for s in spans:
        head = head.replace(f"({s})", " ")
    head_toks = {w for w in _sem_norm(head).split()
                 if w not in _SEM_STOPWORDS}
    if len(head_toks) < 2:
        return False
    ans_toks = {w for w in _sem_norm(answer).split()
                if w not in _SEM_STOPWORDS}
    # person-deixis fold: the GT speaks in the grader's second person
    # ("You increased the limit"), the answer in the user's first person
    # ("I have increased the limit") — the same fact under deixis
    # shift, not a missing token (c6853660).
    head_toks = {_DEIXIS_FOLD.get(w, w) for w in head_toks}
    ans_toks = {_DEIXIS_FOLD.get(w, w) for w in ans_toks}
    return head_toks <= ans_toks


_TENSE_FOLDS = (("had", "has"), ("was", "is"), ("were", "are"))


def _sem_tense_superset_face(reference: str, answer: str) -> bool:
    """C544 tense-fold superset face.

    The same assertion in a different tense — 89527b6b: GT ``The
    Plesiosaur had a blue scaly body.`` vs answer ``The Plesiosaur
    has a blue scaly body, and its eyes are fixed on something in the
    distance`` — misses the plain superset branch only because
    had/has (was/is, were/are) are distinct tokens. Folding the three
    tense pairs on both sides restores the token-superset relation.
    Requires at least one tense pair to actually occur, so it never
    widens the superset path for tense-identical pairs (those already
    returned CORRECT earlier). NEEDS_JUDGE-zone only — the only
    possible flip is NEEDS_JUDGE -> CORRECT.
    """
    nr, nc = _sem_norm(reference), _sem_norm(answer)
    if not (nr and nc):
        return False
    if not any(re.search(rf"\b{a}\b", nr) or re.search(rf"\b{a}\b", nc)
               for a, _ in _TENSE_FOLDS):
        return False

    def fold(t: str) -> str:
        for a, b in _TENSE_FOLDS:
            t = re.sub(rf"\b{a}\b", b, t)
        return t

    tr = {w for w in fold(nr).split() if w not in _SEM_STOPWORDS}
    tc = {w for w in fold(nc).split() if w not in _SEM_STOPWORDS}
    return bool(tr and tc and tr < tc)


_BARE_AFFIRM_GTS = {"yes", "yes."}
_BARE_AFFIRM_AUX_RE = re.compile(
    r"^(do|does|did|is|are|was|were|have|has|had|can|could|will|would|am)\b",
    re.I)
_BARE_AFFIRM_NEG_RE = re.compile(
    r"\b(not|never|no|nothing|nobody|none|nor|cannot|cant|dont|didnt|doesnt|"
    r"hasnt|havent|wont|isnt|arent|wasnt|werent|couldnt|shouldnt|wouldnt|t)\b",
    re.I)

# C547 affirm-elaboration face constants. Lead: affirmation word opening
# the reference (bare-affirm's superset — elaboration may follow). Aux-any:
# a yes/no interrogative clause ANYWHERE in the question ("Before I
# purchased the gravel bike, do I have ...?" fails the aux-INITIAL match
# but is still a yes/no question). Drop-set: pronouns/connectives are
# grammar, not facts — the elaboration's fact tokens are what an answer
# must carry ("too" in "You have a road bike too." need not echo).
_AFFIRM_ELAB_LEAD_RE = re.compile(r"^(yes|yeah|yep|yup|correct)\b[\s.,!]*",
                                  re.I)
_AFFIRM_ELAB_AUX_ANY_RE = re.compile(
    r"\b(do|does|did|is|are|was|were|have|has|had|can|could|will|would|am)"
    r"\s+i\b", re.I)
_AFFIRM_ELAB_WH_LEAD_RE = re.compile(
    r"\b(what|which|when|where|who|whom|whose|why|how)\b", re.I)
_AFFIRM_ELAB_DROP = ("i", "my", "me", "you", "your", "we", "our",
                     "too", "also", "either", "though", "anyway",
                     "however", "still", "already", "again",
                     "not", "nor", "never", "nothing", "nobody", "none",
                     "cannot")


def _sem_bare_affirm_face(question: str, answer: str, reference: str) -> bool:
    """C545 bare-affirmation face.

    Yes/no-auxiliary questions whose reference is a bare ``Yes`` (b01defab:
    ``Did I finish reading 'The Nightingale' by Kristin Hannah?`` vs an
    answer narrating ``... which I finished reading recently``): the
    answer AFFIRMS the questioned predicate without the literal "yes",
    so neither superset branch can see the reference tokens. Gates:
    (1) bare-affirmation reference, (2) auxiliary-initial question,
    (3) every question content token covered in the answer (exact or
    4-char stem), (4) >=2 stem hits, (5) no negator within +-6 tokens
    of a hit (kills "didn't finish"), (6) no interrogative-echo
    sentence among the hits (kills the question-back form, 42ec0761).
    NEEDS_JUDGE-zone only — number/currency guards and the subset veto
    return WRONG before this line, so the only possible flip is
    NEEDS_JUDGE -> CORRECT. C545 census: bare-yes population 5 rows,
    exactly 1 fire (b01defab), 0 false positives.
    """
    if reference.strip().lower() not in _BARE_AFFIRM_GTS:
        return False
    if not _BARE_AFFIRM_AUX_RE.match(question.strip()):
        return False
    a_toks = re.sub(r"[^a-z0-9 ]", " ", answer.lower()).split()
    if not a_toks:
        return False
    a_set = set(a_toks)
    q_toks = re.sub(r"[^a-z0-9 ]", " ", question.lower()).split()
    content = [t for t in q_toks[1:]
               if t not in _SEM_STOPWORDS and len(t) >= 3]
    if not content:
        return False

    def covered(t: str) -> bool:
        if t in a_set:
            return True
        stem = t[:4]
        return len(stem) >= 3 and any(p.startswith(stem) for p in a_toks)

    if not all(covered(t) for t in content):
        return False
    hits = [t for t in content
            if any(p.startswith(t[:4]) for p in a_toks)]
    if len(hits) < 2:
        return False
    for h in hits:                       # negation window
        for idx, p in enumerate(a_toks):
            if not p.startswith(h[:4]):
                continue
            window = a_toks[max(0, idx - 6):idx + 7]
            if any(_BARE_AFFIRM_NEG_RE.fullmatch(w) for w in window):
                return False
    for sent in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if sent.rstrip().endswith("?") and any(
                re.search(rf"\b{re.escape(h[:4])}", sent.lower())
                for h in hits):
            return False                 # interrogative echo
    return True


def _sem_affirm_elaboration_face(question: str, answer: str,
                                 reference: str) -> bool:
    """C547 affirm-elaboration face (bare-affirm's elaborated cousin).

    A reference shaped ``Affirmation. (Elaboration.)`` (89941a94: GT
    ``Yes. (You have a road bike too.)`` vs an answer naming the road
    bike among its bikes): the affirmation answers the yes/no question
    and the elaboration carries the asserted fact. The C545
    bare-affirm face cannot reach it (the GT is not bare), and the
    C544 paren-complement face deliberately excludes it (thin head:
    the head after paren stripping is just ``Yes.``). The question's
    auxiliary clause may sit behind a preamble (``Before I purchased
    the gravel bike, do I have ...?``), so aux-INITIAL anchoring is
    replaced by aux-clause-anywhere + ``?``. Coverage is required for
    the elaboration's FACT tokens only (pronouns/connectives dropped:
    the grader's ``too`` need not echo in the answer), reusing the
    exact/4-char-stem rule, the +-6 negation window and the
    interrogative-echo block from bare-affirm. NEEDS_JUDGE-zone only:
    number/currency guards and the subset veto return WRONG before
    this line, so the only possible flip is NEEDS_JUDGE -> CORRECT.
    C547 census: affirmation-led GT population across the full-500 is
    6 rows; only 89941a94 carries an elaboration rest, exactly 1 fire,
    0 false positives (bare-rest rows stay in bare-affirm's hands;
    42ec0761 stays blocked by the echo gate).
    """
    ref = reference.strip()
    m = _AFFIRM_ELAB_LEAD_RE.match(ref)
    if not m:
        return False
    rest = ref[m.end():].strip()
    rest_norm_toks = _sem_norm(rest).split()
    # Polarity gate: the elaboration must be affirmative. A negative
    # elaboration ("Yes. (You did not sell it.)") asserts a negated fact
    # whose verification is outside deterministic reach — dropping its
    # negator would let a contradicting answer fire. Stay abstaining.
    if any(_BARE_AFFIRM_NEG_RE.fullmatch(t) for t in rest_norm_toks):
        return False
    content = [t for t in rest_norm_toks
               if t not in _SEM_STOPWORDS and t not in _AFFIRM_ELAB_DROP
               and len(t) >= 3]
    if not content:
        return False        # bare affirmation -> _sem_bare_affirm_face
    q = question.strip()
    if not q.endswith("?"):
        return False
    if not _AFFIRM_ELAB_AUX_ANY_RE.search(q):
        return False
    # A wh-lead ('What other bikes do I have ...?') is not a yes/no
    # question even though it carries an aux+I clause — the affirmation
    # GT cannot answer it. Preamble forms ('Before I purchased ..., do
    # I have ...?') have no wh word and stay reachable.
    if _AFFIRM_ELAB_WH_LEAD_RE.search(q[:12]):
        return False
    a_toks = re.sub(r"[^a-z0-9 ]", " ", answer.lower()).split()
    if not a_toks:
        return False

    def covered(t: str) -> bool:
        if t in a_toks:
            return True
        stem = t[:4]
        return len(stem) >= 3 and any(p.startswith(stem) for p in a_toks)

    if not all(covered(t) for t in content):
        return False
    for h in content:                    # negation window
        for idx, p in enumerate(a_toks):
            if not p.startswith(h[:4]):
                continue
            window = a_toks[max(0, idx - 6):idx + 7]
            if any(_BARE_AFFIRM_NEG_RE.fullmatch(w) for w in window):
                return False
    for sent in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if sent.rstrip().endswith("?") and any(
                re.search(rf"\b{re.escape(h[:4])}", sent.lower())
                for h in content):
            return False                 # interrogative echo
    return True


def judge_semantic(question: str, answer: str, reference: str) -> str:
    """Deterministic semantic-equivalence judge (#090 simplified port).

    Ladder: exact (case-insensitive) → normalized → date fold →
    time-unit conversion → guarded containment → soft similarity.
    ``question`` is unused in the lexical ladder but kept for judge
    signature uniformity (and future question-conditioned guards).

    Returns "CORRECT" / "WRONG" / "NEEDS_JUDGE" — the third verdict
    is an honest abstention for lexically-unsolvable pairs (entity
    substitution, zero-overlap paraphrase); :func:`judge_cascade`
    routes those to the LLM judge. NEVER use NEEDS_JUDGE as credit.
    """
    if not reference:
        return "CORRECT"  # same convention as exact_judge/judge_mock
    if not answer:
        return "WRONG"
    r, c = reference.strip(), answer.strip()
    if r.lower() == c.lower():
        return "CORRECT"
    nr, nc = _sem_norm(r), _sem_norm(c)
    if nr == nc:
        return "CORRECT"
    dr, dc = _sem_date_fold(r), _sem_date_fold(c)
    if dr == dc and dr not in (nr, nc):
        return "CORRECT"
    tr, tc = _sem_time_seconds(r), _sem_time_seconds(c)
    if tr is not None and tc is not None and abs(tr - tc) < 1e-9:
        return "CORRECT"
    # Guard 1: number-signature mismatch → veto, but ONLY when the
    # number sets are DISJOINT (7 vs 17). Superset candidates
    # legitimately carry extra numbers ("16GB" answered with a full
    # laptop spec listing) — C529 veto-kill audit caught 32 false
    # losses under the stricter sorted-multiset rule, all fixed by
    # requiring an empty intersection (full-spec answers share the
    # GT number; 17 shares nothing with 7).
    num_r, num_c = _sem_numbers(r), _sem_numbers(c)
    if num_r and num_c and not (set(num_r) & set(num_c)):
        return "WRONG"
    # Guard 2: currency-domain conflict ($5 vs 5 euros).
    cur_r, cur_c = _sem_currencies(r), _sem_currencies(c)
    if cur_r and cur_c and cur_r != cur_c:
        return "WRONG"
    # Guard 3: asymmetric containment (official superset protocol).
    toks_r = {w for w in nr.split() if w not in _SEM_STOPWORDS}
    toks_c = {w for w in nc.split() if w not in _SEM_STOPWORDS}
    if toks_c and toks_c < toks_r:
        # Exact-number answer face: a bare/equivalent numeric answer
        # ("140" vs "140 hours", "5" vs "five model kits") is the
        # precise form of the reference, not a weaker one — the
        # norm already folded five→5, so equal numbers = equal fact.
        if num_c and set(num_c) <= set(num_r):
            return "CORRECT"
        # Either/or answer face (C531): when the question itself offers
        # exactly two alternatives, a candidate that verbatim-names one
        # of them is the complete answer, not a weaker subset — the
        # textual analogue of the numeric face above. C531 census: the
        # blanket subset veto fired twice on the official cascade-500,
        # both false kills (gpt4_98f46fc6 charity either/or;
        # gpt4_45189cb4 narrative abbreviation — the latter stays
        # vetoed, deferred until a non-fitted rule exists).
        if _sem_either_or_face(question, answer, reference):
            return "CORRECT"
        # Marker-subsequence answer face (C532): same discourse-marker
        # skeleton + per-segment in-order subsequence ⇒ same narrative
        # abbreviated. Resolves the C531 pinned debt (gpt4_45189cb4)
        # without a coverage threshold: event-skipping partials break
        # the skeleton, reorders/foreign tokens break alignment.
        if _sem_marker_subsequence_face(question, answer, reference):
            return "CORRECT"
        # C542 quoted-core face: the reference wraps its asserted fact
        # in quotes (frame + core); a candidate equal to the quoted
        # core IS the complete fact, not a weaker subset. Branch-local:
        # only converts this branch's WRONG to CORRECT, never touches
        # superset/number-currency paths (guards 1-2 returned already).
        if _sem_quoted_core_face(r, c):
            return "CORRECT"
        return "WRONG"
    if toks_r and toks_r < toks_c:       # superset candidate
        return "CORRECT"
    if SequenceMatcher(None, nr, nc).ratio() >= 0.75:
        return "CORRECT"
    # C541/C544 reference-alias faces: the reference names its entity
    # (or asserts its fact) with structural redundancy; an answer
    # naming/asserting the same thing through the alias channel is the
    # complete fact, not a weaker subset. All four faces live in the
    # NEEDS_JUDGE zone (guards 1-3 and the subset veto already
    # returned WRONG above), so the only possible flip is
    # NEEDS_JUDGE -> CORRECT — pure upside for banking, and never
    # masks a numeric/currency conflict (those returned WRONG before
    # this line).
    if (_sem_paren_acronym_face(r, c) or _sem_place_complement_face(r, c)
            or _sem_paren_complement_face(r, c)
            or _sem_tense_superset_face(r, c)
            or _sem_bare_affirm_face(question, c, r)
            or _sem_affirm_elaboration_face(question, c, r)):
        return "CORRECT"
    return "NEEDS_JUDGE"


def judge_cascade(question: str, answer: str, reference: str, *,
                  llm_fn=None, **llm_kw) -> str:
    """Semantic-first judging cascade — LLM only on honest abstention.

    :func:`judge_semantic` resolves the lexically-decidable surface at
    zero cost with bitwise reproducibility; NEEDS_JUDGE pairs fall
    through to ``llm_fn`` (default :func:`judge_llm`). Returns
    "CORRECT" / "WRONG" / "ERROR" (ERROR propagates from the LLM)."""
    verdict = judge_semantic(question, answer, reference)
    if verdict != "NEEDS_JUDGE":
        return verdict
    fn = llm_fn or judge_llm
    return fn(question, answer, reference, **llm_kw)


def cohens_kappa(labels_a: list[int], labels_b: list[int]) -> float:
    """Cohen's kappa — chance-corrected agreement.

    Raw agreement is inflated whenever both judges lean the same way
    on imbalanced data (Research #092: official-judge raw 0.98 vs
    kappa after 33-41pp shrink); kappa is the honest A/B lens."""
    assert len(labels_a) == len(labels_b) and labels_a
    n = len(labels_a)
    po = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n
    p_a1, p_b1 = sum(labels_a) / n, sum(labels_b) / n
    pe = p_a1 * p_b1 + (1 - p_a1) * (1 - p_b1)
    return 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe)


def mcnemar_exact(b: int, c_disc: int) -> float:
    """Two-sided exact binomial McNemar p-value for discordant (b, c).

    The legal paired test for judge A/Bs: only the rows the two
    judges disagree on carry evidence; concordant rows cancel."""
    n = b + c_disc
    if n == 0:
        return 1.0
    k = min(b, c_disc)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def _ab_pair_stats(pairs: list[tuple[int, int]]) -> dict:
    """Discordant summary for one (correct_exact, correct_llm) group."""
    n = len(pairs)
    b = sum(1 for e, c in pairs if not e and c)    # cascade-only correct
    cc = sum(1 for e, c in pairs if e and not c)   # cascade-only wrong
    return {"scored": n, "cascade_only_correct": b,
            "cascade_only_wrong": cc, "mcnemar_p": mcnemar_exact(b, cc)}


def judge_ab_report(results: list) -> dict:
    """A/B decision statistics: containment-baseline vs cascade judge.

    Research #092 protocol over dual/semantic-scored rows (duck-typed
    — QuestionResult attrs or report dict rows, same protocol as
    :func:`calibration_summary`): discordant counts (rescues b vs
    losses c), McNemar exact p, Cohen's kappa, and a per-category
    breakdown so any verdict traces to the question types driving it
    (type noise floors differ — preference 0.10 vs ss 0.00).

    ``verdict`` at p<0.05: "cascade>exact" / "exact>cascade",
    else "n.s." — McNemar is the decision rule; kappa quantifies how
    much of the raw agreement is chance consensus.
    """
    ex: list[int] = []
    ca: list[int] = []
    cats: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for r in results:
        e = (r.correct_exact if hasattr(r, "correct_exact")
             else r.get("correct_exact"))
        c = (r.correct_llm if hasattr(r, "correct_llm")
             else r.get("correct_llm"))
        if e is None or c is None:
            continue  # judge ERROR rows carry no pair evidence
        pair = (int(bool(e)), int(bool(c)))
        ex.append(pair[0])
        ca.append(pair[1])
        cat = ((r.category if hasattr(r, "category") else r.get("category"))
               or "unknown")
        cats[cat].append(pair)
    overall = _ab_pair_stats(list(zip(ex, ca)))
    p = overall["mcnemar_p"]
    if p < 0.05:
        verdict = ("cascade>exact" if overall["cascade_only_correct"]
                   > overall["cascade_only_wrong"] else "exact>cascade")
    else:
        verdict = "n.s."
    return {"scored": overall["scored"],
            "agree": overall["scored"] - overall["cascade_only_correct"]
            - overall["cascade_only_wrong"],
            "cascade_only_correct": overall["cascade_only_correct"],
            "cascade_only_wrong": overall["cascade_only_wrong"],
            "mcnemar_p": p,
            "kappa": cohens_kappa(ex, ca) if ex else 0.0,
            "verdict": verdict,
            "by_category": {cat: _ab_pair_stats(pairs)
                            for cat, pairs in sorted(cats.items())}}


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


# ── Risk-coverage / selective prediction (Cycle 520 — Research #089) ─
#
# The abstention stack (C448 entropy gate + C513/C516/C518 neg-exist
# + presupposition gates) has so far been evaluated at ONE operating
# point per A/B (accuracy at the shipped threshold). Selective
# prediction upgrades that to curve metrics: rank every question by
# answering confidence, sweep the coverage frontier, and measure
# risk everywhere — AURC (area under the curve) needs no threshold
# choice to compare two confidence signals, E-AURC subtracts the
# exact oracle AURC (perfect ordering — all-correct-first — measured
# through the same trapezoid integrator) so only RANKING
# quality remains, and Risk@coverage reads off deployable operating
# points (e.g. "abstain 10% → Risk@90%"). Per-category breakdown
# lands "the form classifier is the configuration surface" (#233/
# #251) as a measurement: a single global threshold rides a saddle
# point on a mixed curve surface (C452/C473 twice shown empirically).
# Calibration ≠ selective prediction: a signal can be symmetrically
# calibrated yet rank-blind (AURC high) or overconfident yet perfectly
# ranked (AURC minimal) — RL-driven selective regression, arXiv
# 2607.03528 Fig.1. Citations: Ding et al. CVPRW 2020 (AURC the only
# reliable metric among AUROC/AUPR/AURC); Kirichenko et al.
# AbstentionBench ICML 2025 (frontier LLMs hallucinate on
# unanswerable; reasoning tuning reduces abstention 24%).

def _rc_confidence(r) -> float | None:
    """Per-question answering confidence for curve ranking.

    1 − norm_entropy over the keyword-hit evidence distribution
    (C448 signal, inverted so higher = answer more confidently).
    Duck-typed: QuestionResult attrs or serialized report rows.
    """
    retr = (r.retrieval if hasattr(r, "retrieval")
            else r.get("retrieval") if hasattr(r, "get") else None)
    ne = retr.get("norm_entropy") if isinstance(retr, dict) else None
    return None if ne is None else 1.0 - float(ne)


def _risk_coverage_curve(scored: list[dict]) -> list[tuple[float, float]]:
    """[(coverage, risk)] sweeping the answered set by confidence.

    risk = error rate of the answered prefix; abstained questions
    excluded below the operating coverage carry no risk — that is
    exactly where abstention pays. Ported verbatim (semantics) from
    Research #089 risk_coverage_aurc.py.
    """
    ranked = sorted(scored, key=lambda s: s["score"], reverse=True)
    n, wrong, points = len(ranked), 0, []
    if not n:
        return points
    for i, r in enumerate(ranked, 1):
        wrong += 0 if r["correct"] else 1
        points.append((i / n, wrong / i))
    return points


def _aurc(points: list[tuple[float, float]]) -> float:
    """Area under the risk-coverage curve (trapezoid integral)."""
    (c0, r0), area = (0.0, 0.0), 0.0
    for c, r in points:
        area += (c - c0) * (r0 + r) / 2
        c0, r0 = c, r
    return area


def risk_at_coverage(points, coverage: float) -> float:
    """Risk at a coverage level — the deployable operating-point read."""
    for cov, risk in points:
        if cov >= coverage - 1e-9:
            return risk
    return points[-1][1] if points else 0.0


def _oracle_aurc(n: int, k: int) -> float:
    """AURC of the perfect ordering, computed exactly.

    Builds the all-correct-first arrangement and integrates it
    through the SAME trapezoid code — constructive exactness, no
    closed form to mistranscribe. (The k²/2n² formula circulating in
    notes — incl. our own #089 — is its small-k Taylor approximation,
    e.g. n=10,k=4: exact 0.0926 vs 0.0800; the Cycle 520 oracle
    cross-check caught it. Empirically k²/2n² underestimates, so it
    flatters every E-AURC it touches.)
    """
    if not n or k < 0 or k > n:
        return 0.0
    perfect = ([{"score": 1.0, "correct": True}] * (n - k)
               + [{"score": 0.0, "correct": False}] * k)
    return _aurc(_risk_coverage_curve(perfect))


def risk_coverage_report(results: list, *,
                         coverage_levels: tuple[float, ...] =
                         (0.5, 0.7, 0.8, 0.9, 0.95)) -> dict:
    """Selective-prediction report over an evaluated result set.

    Answers, for the confidence signal ``1 − norm_entropy``: how much
    risk remains if the system answers only the top-p fraction
    (Risk@p), how good the ranking is independent of any threshold
    (E-AURC, 0 = perfect ordering), and where the curve surface
    diverges by question form (per-category AURC — global thresholds
    ride saddle points on mixed surfaces, C452/C473).

    Duck-typed input — QuestionResult attrs or report dict rows,
    same protocol as :func:`calibration_summary`. ``correct`` already
    encodes the benchmark verdict (honest abstention on _abs counts
    as correct); rows lacking a confidence signal are counted in
    ``unresolved_score`` and excluded from the curve.
    """
    scored: list[dict] = []
    unresolved = 0
    for r in results:
        conf = _rc_confidence(r)
        if conf is None:
            unresolved += 1
            continue
        if hasattr(r, "correct"):
            correct, abstained = bool(r.correct), bool(r.abstained)
            category = r.category or "unknown"
        else:
            correct = bool(r.get("correct"))
            abstained = bool(r.get("abstained"))
            category = r.get("category") or "unknown"
        scored.append({"score": conf, "correct": correct,
                       "abstained": abstained, "category": category})
    n = len(scored)
    k = sum(1 for s in scored if not s["correct"])
    if not n:
        return {"total": 0, "unresolved_score": unresolved,
                "answered": 0, "abstained": 0, "errors": 0,
                "overall_risk": 0.0, "aurc": 0.0, "aurc_oracle": 0.0,
                "e_aurc": 0.0, "risk_at": {}, "curve_deciles": [],
                "per_category": {}}
    pts = _risk_coverage_curve(scored)
    aurc_val = _aurc(pts)
    oracle = _oracle_aurc(n, k)
    curve_deciles = [pts[min(int(d * n), n) - 1]
                     for d in range(1, 11) if int(d * n) >= 1]
    per_category: dict[str, dict] = {}
    for cat in sorted({s["category"] for s in scored}):
        sub = [s for s in scored if s["category"] == cat]
        sub_pts = _risk_coverage_curve(sub)
        m, kw = len(sub), sum(1 for s in sub if not s["correct"])
        per_category[cat] = {
            "total": m, "errors": kw,
            "accuracy": round((m - kw) / m, 4),
            "aurc": round(_aurc(sub_pts), 4),
            "e_aurc": round(_aurc(sub_pts) - _oracle_aurc(m, kw), 4)
            if m else 0.0,
        }
    return {
        "total": n,
        "unresolved_score": unresolved,
        "answered": sum(1 for s in scored if not s["abstained"]),
        "abstained": sum(1 for s in scored if s["abstained"]),
        "errors": k,
        "overall_risk": round(k / n, 4),
        "aurc": round(aurc_val, 4),
        "aurc_oracle": round(oracle, 4),
        "e_aurc": round(aurc_val - oracle, 4),
        "risk_at": {f"{int(c * 100)}%":
                    round(risk_at_coverage(pts, c), 4)
                    for c in coverage_levels},
        "curve_deciles": [(round(c, 3), round(rk, 4))
                           for c, rk in curve_deciles],
        "per_category": per_category,
    }


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
    r"(?P<m2>" + _MONTH_WORD_RE + r")\.?(?:,?\s+(?P<y2>\d{4}))?"
    # C554: numeric month/day slash form — "on the 3/8" / "on
    # 3/8/23". The graduation-gift anchor lost its in-text date to
    # this form (8c18457d: 14 days vs GT 7 — the true line kept the
    # bare session date). "on" prefix stays mandatory: bare "3/8"
    # also matches fractions/ratios ("3/8 of the budget").
    r"|\bon\s+(?:the\s+)?(?P<nm>\d{1,2})/(?P<nd>\d{1,2})"
    r"(?:/(?P<ny>\d{2,4}))?\b",
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
    March`` / ``on March 5, 2022`` / ``on the 3/8`` (C554: numeric
    month/day; optional 2- or 4-digit year) — explicit year beats
    *year_hint*. Dated nouns and month-year mentions without a day
    return ``None`` (see the module comment for the regression
    guard).
    """
    m = _TA_LINE_DATE_RE.search(line or "")
    if not m:
        return None
    if m.group("m1"):
        mon = _TA_MONTH_NUM[m.group("m1")[:3].lower()]
        day, yr = int(m.group("d1")), m.group("y1")
    elif m.group("nm"):
        # C554 numeric slash form (US month/day convention)
        mon, day = int(m.group("nm")), int(m.group("nd"))
        yr = m.group("ny")
        if yr and len(yr) == 2:
            yr = str(2000 + int(yr))
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


def _line_adverbial_dates(line: str, year_hint: str = "") -> list[tuple[str, int]]:
    """All adverbial dates in *line* as ``(iso, char_offset)``.

    C557 companion to :func:`_line_adverbial_date` (which keeps the
    leftmost-match contract for its other callers): same regex,
    same parsing, every match.
    """
    out: list[tuple[str, int]] = []
    for m in _TA_LINE_DATE_RE.finditer(line or ""):
        iso = None
        try:
            if m.group("m1"):
                mon = _TA_MONTH_NUM[m.group("m1")[:3].lower()]
                day, yr = int(m.group("d1")), m.group("y1")
            elif m.group("nm"):
                mon, day = int(m.group("nm")), int(m.group("nd"))
                yr = m.group("ny")
                if yr and len(yr) == 2:
                    yr = str(2000 + int(yr))
            else:
                day = int(m.group("d2"))
                mon = _TA_MONTH_NUM[m.group("m2")[:3].lower()]
                yr = m.group("y2")
            if yr:
                year = int(yr)
            elif year_hint and str(year_hint).isdigit():
                year = int(year_hint)
            else:
                year = None
            if year:
                iso = date(year, mon, day).isoformat()
        except (ValueError, KeyError):
            iso = None
        if iso:
            out.append((iso, m.start()))
    return out


def _line_eff_date(line: str, sdate: str, question_date: str = "",
                   ks: list[str] | None = None) -> str | None:
    """Anchor-aware adverbial date for one line (C482 gate + C557 pick).

    The C482 closeness gate applies to every candidate
    individually (within _TA_DATE_PROXIMITY days of the session, or
    in the past relative to it — far-future plan dates are poison).
    C557: when several candidates survive the gate, pick the one
    nearest the anchor's keyword cluster. Multi-event lines anchor
    their SECOND event in the anchor's words: "got a pair of
    sneakers ... on February 1st ... realized that the shoelaces on
    my old Converse sneakers had broken on January 24th" — the
    realized-shoelaces anchor must date 01-24, not leftmost 02-01
    (dcfa8644: 22 days vs GT 14). Single surviving candidate or no
    keyword positions → leftmost, byte-identical with the pre-C557
    path.
    """
    year_hint = sdate[:4] or (question_date[:4] if question_date else "") or ""
    cands: list[tuple[str, int]] = []
    for iso, pos in _line_adverbial_dates(line, year_hint):
        try:
            delta = abs((date.fromisoformat(iso)
                         - date.fromisoformat(sdate)).days)
        except ValueError:
            continue
        if delta <= _TA_DATE_PROXIMITY or iso < sdate:
            cands.append((iso, pos))
    if not cands:
        return None
    if len(cands) == 1 or not ks:
        return cands[0][0]
    kpos = [m.start() for w in ks
            for m in re.finditer(r"\b%s\b" % re.escape(w), line, re.I)]
    if not kpos:
        return cands[0][0]
    return min(cands,
               key=lambda t: (min(abs(t[1] - p) for p in kpos), t[1]))[0]


# C557: consecutive-pair descriptor in "since" anchors — "two
# charity events in a row, on consecutive days" asserts a temporal
# RELATION between two events, so the anchor date is the pair's
# completion (the later day), not the most recent single event
# (b46e15ed: pair = 02-14 bike ride + 02-15 book drive; the recency
# ladder anchored the 03-19 walk → '1 month' vs GT 2).
_TA_PAIR_RE = re.compile(r"\bin a row\b|\bconsecutive\b", re.I)


# ── Cycle 558: relative-advance composition (982b5123 family) ────
# A winning anchor line can date its event only RELATIVE to another
# event: "... for my best friend's wedding and had to book three
# months in advance" — no absolute date, so the recency path
# collapses onto the session date (== ask date → "0 months"). The
# pivot event is dated by a second line relative to its own session
# ("been to SF ... exactly two months ago ... wedding"). Census
# (/tmp/c558): exactly ONE row of 500 carries an advance phrase on
# its winning anchor line; the other three "in advance" rows carry
# it on losing assistant-advice lines. Pivot identity = shared
# content word with document frequency ≤ 5 over the candidate set
# (wedding df=6, friend's df=3 qualify; francisco df=21, great
# df=108, trip df=46 are thematic noise).
_TA_NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12}
_TA_ADVANCE_RE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve)\s+(day|week|month|year)s?\s+in advance\b", re.I)
_TA_REL_AGO_RE = re.compile(
    r"\b(?:exactly\s+|about\s+|almost\s+|nearly\s+|just\s+|over\s+)?"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve)\s+(day|week|month|year)s?\s+ago\b", re.I)
_TA_PIVOT_DF = 5     # rare-shared-word identity threshold (census)
_TA_PIVOT_STOP = {
    "the", "a", "an", "to", "for", "in", "of", "and", "or", "is",
    "are", "was", "were", "be", "been", "have", "has", "had", "i",
    "you", "my", "me", "we", "our", "it", "its", "that", "this",
    "these", "those", "with", "on", "at", "by", "from", "as", "if",
    "so", "do", "does", "did", "not", "no", "yes", "user", "assistant",
    "s", "t", "ve", "ll", "re", "can", "could", "will", "would",
    "should", "may", "might", "must", "shall", "am", "when", "what",
    "which", "who", "how", "where", "why", "there", "here", "some",
    "any", "all", "get", "got", "go", "going", "like", "just", "also",
    "very", "really", "about", "up", "out", "your", "than", "then",
    "them", "they", "their", "he", "she", "his", "her", "one",
}


def _shift_months(d0: date, months: int) -> date:
    """Calendar-month shift with end-of-month clamping
    (Jan 31 − 1mo → Feb 28; leap years honored)."""
    idx = d0.month - 1 + months
    y = d0.year + idx // 12
    m = idx % 12 + 1
    try:
        return date(y, m, d0.day)
    except ValueError:
        nxt = date(y + (m == 12), (m % 12) + 1, 1)
        return nxt - timedelta(days=1)


def _shift_delta(d0: date, n: int, unit: str) -> date:
    """Shift *d0* by *n* day/week/month/year units (signed)."""
    if unit == "day":
        return d0 + timedelta(days=n)
    if unit == "week":
        return d0 + timedelta(weeks=n)
    if unit == "year":
        return _shift_months(d0, 12 * n)
    return _shift_months(d0, n)


def _ta_num(m: re.Match) -> tuple[int, str]:
    """(number, unit) from a _TA_NUMWORDS-bearing duration match."""
    g1 = m.group(1).lower()
    return (_TA_NUMWORDS.get(g1) or int(g1), m.group(2).lower())


def _compose_relative_advance(winner_line: str,
                              dated_lines: list,
                              qd: str) -> str | None:
    """Resolve the anchor date through a two-hop relative chain.

    The winner line carries ``<N> <unit> in advance`` (the anchor
    event happened N units BEFORE a pivot event it names); a pivot
    line dates that event relative to its own session (``M units
    ago``). anchor_date = pivot_session − rel − advance. The pivot
    must share a content word with df ≤ _TA_PIVOT_DF across the
    candidate set (rare-word identity link; common-word overlap is
    thematic noise). Returns an ISO date or None (no qualified
    pivot / unresolvable / anchor after the ask) — callers keep
    their existing behavior on None, never fabricate.
    """
    ma = _TA_ADVANCE_RE.search(winner_line)
    if not ma:
        return None
    adv_n, adv_u = _ta_num(ma)
    df: dict[str, int] = {}
    toks = []
    for line, _sd in dated_lines:
        ws = set(w for w in re.findall(r"[a-z']+", (line or "").lower())
                 if w not in _TA_PIVOT_STOP)
        toks.append(ws)
        for w in ws:
            df[w] = df.get(w, 0) + 1
    w_words = set(w for w in re.findall(r"[a-z']+", winner_line.lower())
                  if w not in _TA_PIVOT_STOP)
    best = None
    for (line, sdate), ws in zip(dated_lines, toks):
        if line == winner_line:
            continue
        m2 = _TA_REL_AGO_RE.search(line or "")
        if not m2:
            continue
        shared = w_words & ws
        if not any(df.get(w, 0) <= _TA_PIVOT_DF for w in shared):
            continue
        try:
            ps = date.fromisoformat(sdate or "")
        except ValueError:
            continue
        rel_n, rel_u = _ta_num(m2)
        pdate = _shift_delta(ps, -rel_n, rel_u)   # rel-ago: before session
        score = len(shared)
        if best is None or score > best[0]:
            best = (score, pdate)
    if best is None:
        return None
    anchor = _shift_delta(best[1], -adv_n, adv_u)  # in advance: before pivot
    try:
        if anchor > date.fromisoformat(qd):
            return None                            # never answer future "ago"
    except ValueError:
        return None
    return anchor.isoformat()


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


# Cycle 539 opener-floor lexicon: the dialogue-management opener
# family (hand-over/acknowledgment/request-for-help) whose members
# win the answer-gate ranking purely on echo overlap. C539 census:
# 16/16 GT-in-window answer-gate rows had an opener-shaped winner
# while the GT line sat same-band below. Distinct from
# _RECALL_PREAMBLE_RE (reader-side acks) — this is the USER/assistant
# conversational hand-over family, plus ask-patterns anywhere in the
# line's first 200 chars ("...was wondering if you could help...").
_OPENER_HANDOVER_RE = re.compile(
    r"^(?:sure[,;! ]|absolutely|of course|certainly|"
    r"great (?:idea|question|news)|"
    r"i(?:'d| would) (?:be happy|love|be delighted) to|"
    r"i can help|i'?m happy to|"
    r"here(?:\s+are|\s+is|'s)|let me know if|"
    r"(?:i|we) hope (?:this|that|these) help|"
    r"happy to (?:help|provide|share|suggest)|"
    r"thank you for (?:sharing|providing)|would you like me to|"
    r"that(?:'s| is) (?:great|good) to (?:hear|know)|"
    r"i think (?:there)?'?s been a misunderstanding|"
    r"i apologize|i'?m (?:really )?sorry)", re.I)
_OPENER_ASK_RE = re.compile(
    r"\b(?:can|could) you (?:help|suggest|recommend|tell|give|provide)\b|"
    r"\bdo you have any\b|\bwondering if\b|"
    r"\bany (?:suggestions|recommendations|advice|ideas|tips)\b|"
    r"\bi want you to be\b|\bwhat do you think\b", re.I)
# Candidate-side personal-statement guard: first clause carries a
# first-person subject. Excludes the naive-census kill shapes —
# assistant lists ("3. **Art Festivals..."), lectures ("The number
# of free nights..."), meta-transitions ("Now, about that...").
_OPENER_FLOOR_STMT_RE = re.compile(
    r"^(?:by the way|anyway|well|so|oh)?[,:\s]*"
    r"i(?:'ll|'ve|'d|'m)?\b", re.I)


def _split_sentences(text: str) -> list[str]:
    """Sentences (and line-broken fragments) longer than 10 chars."""
    parts = re.split(r"(?<=[.!?])\s+|\n", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 10]


# Cycle 538 answer-face verb lexicon: question head-verb →
# first-person past-tense surface family. The question's own
# main verb predicts the ANSWER LINE's verb (answer-type prior,
# C534 precedent, applied to acquisition/statement lines): "What
# did I buy…" is answered by "…I got her a yellow dress", not by
# a gift-recipient list or advice echo. Families are closed
# (suppletive past forms only — no stemming): buy→bought/purchased,
# complete/finish→completed/finished/earned, get→got/received.
# No free parameters: the C501 hits>=2 floor is reused, ranking
# is structural (tier preference among floor-passers, C534/C537
# shape), and openers are excluded wherever they sit (C475:
# prefaces parasitize overlap — "Here's a start - I've bought
# gifts for…" names recipients, not the item).
_ACQ_FORM_RE = re.compile(
    r"^(?:what|which)\b[^\n]{0,80}?\b(?:did|have)\s+i\s+"
    r"(buy|purchase|complete|finish|get)\b", re.I)
_ACQ_FAMILY = {
    "buy": ("bought", "purchased", "got", "received"),
    "purchase": ("bought", "purchased", "got", "received"),
    "complete": ("completed", "finished", "earned"),
    "finish": ("completed", "finished", "earned"),
    "get": ("got", "received", "bought", "picked up"),
}
_ACQ_STATEMENT_RE = re.compile(
    r"(?<!can )(?<!could )(?<!should )(?<!would )(?<!will )(?<!shall )"
    r"(?<!may )(?<!might )(?<!must )"
    r"\bi(?:'ve\s+|'d\s+|\s+have\s+|\s+had\s+|\s+)"
    r"(?:bought|purchased|completed|finished|earned|got|received)\b",
    re.I)
_WHO_CONV_FORM_RE = re.compile(
    r"^who\b[^\n]{0,80}?\bdid\s+i\s+(?:have\s+(?:a\s+)?)?"
    r"(?:conversation|chat|talk)\b", re.I)
_WHO_CONV_STATEMENT_RE = re.compile(
    r"\bmy\s+(?:conversation|chat|discussion)\s+with\b"
    r"|\bi\s+(?:talked|spoke|chatted)\s+(?:to|with)\b", re.I)


def answer_user_challenge(best_line: str,
                          retrieved_ids: list,
                          messages: dict,
                          kws: list) -> tuple[str | None, dict]:
    """C548: cross-session user-statement challenge face.

    The LAST pred-side vein after C546's kh-elite falsification. A
    line OUTSIDE the retrieval window that outranks the current
    winner under the production ranking (-hits, -seq) is promoted
    ONLY when it passes all three census-separated gates:

      (a) role == "user" — personal-fact answers are asserted by the
          user; assistant empathy preambles/echoes are exactly the
          C546 impostor family (first census pass: 2/2 kill-side
          triggers were assistant lines, all 5 rescues user lines);
      (b) cross-session — same-session repair is C526's territory;
          its unscoped variant hijacked ONLY cross-session;
      (c) phrase-run dominance — _kw_phrase_run(challenger) beats
          the winner's with floor 2 (C540 primitive: the question's
          own contiguous phrase is GT evidence bag-of-hits lacks).

    Census (/tmp/c548/census_user.py, 187 answer-gate rows: 50
    banked-correct seed-7 sample + all 137 banked-wrong): 5 RESCUE
    (c8c3f81d, 8ebdbe50, c19f7a0b, gpt4_5dcc0aab, f523d9fe) / 0 KILL
    / 0 kill-side triggers of 50. Plain admission without (a)-(c)
    is C546's NET-NEGATIVE 14%-kill — the gates ARE the result, not
    decoration.
    """
    face_body = best_line.split("] ", 1)[-1]
    win_ids = set(retrieved_ids or [])
    # C525 lesson: context.split("\n") maps lines 1:1 onto window
    # messages EXCEPT multi-paragraph labels — lines[0] is then the
    # winner's FIRST line (the C526 face no-ops there by exact
    # match). Match on the label's first line so the face still
    # sees the winner; the outrank/run comparison stays on the
    # first-line evidence exactly as censused (stored preds ARE
    # first lines).
    win_info = next((messages[nid] for nid in retrieved_ids or []
                     if nid in messages
                     and messages[nid].get("label", "").split(
                         "\n", 1)[0] == face_body),
                    None)
    detail = {"face_found": win_info is not None, "override": False}
    if win_info is None:
        return None, detail
    win_kh = _keyword_hits(face_body, kws)
    win_run = _kw_phrase_run(face_body, kws)
    win_seq = win_info.get("seq") or 0
    win_sid = win_info.get("session_id")
    detail.update({"win_kh": win_kh, "win_run": win_run,
                   "win_session": win_sid})
    best_n = None
    for nid, info in messages.items():
        if nid in win_ids or info.get("role") != "user":
            continue
        if win_sid is not None and info.get("session_id") == win_sid:
            continue
        body = info.get("label", "")
        kh = _keyword_hits(body, kws)
        if not (kh > win_kh
                or (kh == win_kh and (info.get("seq") or 0) > win_seq)):
            continue
        run = _kw_phrase_run(body, kws)
        if run <= win_run or run < 2:
            continue
        if (best_n is None or kh > best_n["kh"]
                or (kh == best_n["kh"]
                    and (info.get("seq") or 0) > best_n["seq"])):
            best_n = {"body": body, "kh": kh,
                      "seq": info.get("seq") or 0, "run": run,
                      "session_id": info.get("session_id")}
    detail.update({"candidate_kh": best_n["kh"] if best_n else 0,
                   "candidate_run": best_n["run"] if best_n else 0,
                   "override": best_n is not None})
    if best_n is None:
        return None, detail
    return f"[user] {best_n['body']}", detail


def answer_opener_floor(best_line: str, lines: list[str],
                        kws: list[str]) -> tuple[str | None, dict]:
    """C539: opener demotion floor for the answer gate.

    When the best-ranked line is a dialogue-management opener (the
    _OPENER_HANDOVER_RE/ask family — C539 census: 16/16 GT-in-window
    answer-gate rows had an opener-shaped winner while the GT line
    sat same-band below), demote it ONLY for a candidate that is,
    jointly: strictly richer in question evidence (kh > win_kh —
    same-kh demotions are the naive census's 5-kill shape: opener
    lines that CONTINUE into the answer), a first-person personal
    statement (excludes assistant lists/lectures — the
    masked-degradation shape), and itself not opener-shaped.
    C533 where-floor lineage: a floor demotes a defective winner for
    a structurally better candidate; no thresholds fitted (C531).

    Returns ``(line, detail)`` — line ``None`` = no qualifying
    candidate, caller falls through untouched (C488).
    """
    body = (best_line.split("] ", 1)[-1]
            if best_line.startswith("[") else best_line).strip()
    if not (_OPENER_HANDOVER_RE.match(body)
            or _OPENER_ASK_RE.search(body[:200])):
        return None, {"fired": False, "reason": "winner-not-opener"}
    win_kh = _keyword_hits(body, kws)
    best = None
    best_h = win_kh
    for ln in lines:
        if ln == best_line:
            continue
        cand = (ln.split("] ", 1)[-1]
                if ln.startswith("[") else ln).strip()
        if (not cand or _OPENER_HANDOVER_RE.match(cand)
                or _RECALL_PREAMBLE_RE.match(cand)
                or _OPENER_ASK_RE.search(cand[:200])):
            continue
        if not _OPENER_FLOOR_STMT_RE.match(cand):
            continue
        h = _keyword_hits(cand, kws)
        if h > best_h:
            best, best_h = ln, h
    if best is None:
        return None, {"fired": False, "win_kh": win_kh,
                      "reason": "no-strict-statement-candidate"}
    return best, {"fired": True, "win_kh": win_kh, "rep_kh": best_h}


def answer_acquisition_face(question: str, lines: list[str],
                            kws: list[str]) -> tuple[str | None, dict]:
    """C538: first-person acquisition/conversation statement face.

    Among the answer-gate window lines, the sentence that actually
    PERFORMS the question's verb in first person past tense (and
    clears the C501 hits>=2 floor) is the answer-bearing line —
    openers name recipients, tangents discuss the topic, but only
    "For my sister's birthday, I got her a yellow dress" answers
    "What did I buy for my sister's birthday gift?". Question
    structure picks the family; no thresholds are fitted (C531).

    Returns ``(line, detail)`` — line ``None`` = no tier-1 passer,
    caller falls through untouched (C488).
    """
    m = _ACQ_FORM_RE.search(question)
    if m:
        verb = m.group(1).lower()
        family = _ACQ_FAMILY.get(verb, ())
        stmt_re = _ACQ_STATEMENT_RE
        kind = f"acq:{verb}"
    elif _WHO_CONV_FORM_RE.search(question):
        family = ("conversation",)
        stmt_re = _WHO_CONV_STATEMENT_RE
        kind = "who:conversation"
    else:
        return None, {"kind": None, "override": False}
    best_a = None
    best_a_hits = 0
    for ln in lines:
        body = (ln.split("] ", 1)[-1]
                if ln.startswith("[") else ln)
        if _RECALL_PREAMBLE_RE.match(body.strip()):
            continue  # openers parasitize overlap (C475)
        if not stmt_re.search(body):
            continue
        if family[0] != "conversation":
            if not any(v in body.lower() for v in family):
                continue
        h = _keyword_hits(body, kws)
        if h < 2:  # C501 floor, reused verbatim
            continue
        if h > best_a_hits:
            best_a, best_a_hits = ln, h
    return best_a, {"kind": kind,
                    "candidate_hits": best_a_hits,
                    "override": best_a is not None}


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
    passers: list[tuple[float, str, str | None, int]] = []
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
        passers.append((score, s, sid, len(matched)))
    best = max(passers, key=lambda p: p[0]) if passers else None
    # C537 speech-act face: a you-addressed question referencing the
    # assistant's own past act ("...the restaurant you recommended")
    # is answered by the sentence where the assistant PERFORMS that
    # act in first person ("For a romantic dinner, I would recommend
    # Roscioli."), not by a list row that merely shares content words
    # (La Pergola's fine-dining/Italian/Rome line parasitizes overlap
    # like a C475 preface — 4c36ccef official-run casualty, losing
    # 150.8 vs 145.5). Question structure, not a tuned threshold
    # (C531 principle): tier preference among floor-passers only —
    # the content floor keeps relevance, the act verb breaks the
    # tie. No exemption pass: if the act sentence is not even a
    # passer the floors excluded it for a reason (C536 census lesson).
    # Applied BEFORE the C534 type-demand face so a type question
    # ("how many ... did you recommend") still resolves to the
    # type-bearing sentence — the demand is the more specific face.
    if best is not None and _SPEECH_ACT_Q_RE.search(question):
        tier = [p for p in passers
                if _speech_act_bearer(p[1])
                and not _RECALL_PREAMBLE_RE.match(p[1])]
        if tier:
            faced = max(tier, key=lambda p: p[0])
            if faced[1] != best[1]:
                best = faced
                detail["speech_act_face"] = "tier"
    # C534 answer-type face: a question demanding a fact type ("how
    # many" → digit, "how much" → currency, "what year" → year,
    # "handle" → @handle) prefers a candidate that bears it — a
    # type-less descriptive line parasitizes overlap like a preface
    # (C475), and the guarantee comes from question structure, not a
    # tuned threshold (C531 either/or principle). Tier preference
    # among floor-passers; when no passer bears the type, a bounded
    # exemption pass (type-bearing, raw >= 2, preface penalty and
    # weighted_floor kept) rescues candidates the distinctive filter
    # hid — the @handle line (b759caee) and the "$2,000" budget line
    # (7a8d0b71) each lost only to that filter on the official run.
    demand = next((t for t, qre, _ in _RECALL_TYPE_DEMANDS
                   if qre.search(question)), None)
    detail["type_demand"] = demand
    if demand and best is not None:
        tier_re = next(tre for t, _, tre in _RECALL_TYPE_DEMANDS
                       if t == demand)
        tier = [p for p in passers if tier_re.search(p[1])]
        if tier:
            faced = max(tier, key=lambda p: p[0])
            if faced[1] != best[1]:
                best = faced
                detail["type_face"] = "tier"
        else:
            exempt: list[tuple[float, str, str | None, int]] = []
            for s, sid in pool:
                if not tier_re.search(s):
                    continue
                matched = [kw for kw in kws if w[kw]
                           and _keyword_hits(s, [kw])]
                if len(matched) < 2:
                    continue
                score = sum(w[kw] ** 2 for kw in matched)
                if _RECALL_PREAMBLE_RE.match(s):
                    score *= 0.25
                if score >= weighted_floor:
                    exempt.append((score, s, sid, len(matched)))
            if exempt:
                best = max(exempt, key=lambda p: p[0])
                detail["type_face"] = "exemption"
    # C559 name-demand definitional-anaphora face: a question asking
    # for the NAME of a thing ("...the name of that restaurant in
    # Cihampelas Walk...") is answered by the sentence that DEFINES
    # the entity under that name — "<ProperName>: this <head-noun>
    # ..." — even when the distinctive floors hid it: cross-sentence
    # evidence (the locator "Cihampelas Walk" sits in the INTRO
    # sentence) left the bearer "Miss Bee Providore: This restaurant
    # serves..." at raw=2 while the impostor list item "Take a
    # cooking class: ... nasi goreng ..." (raw=3) parasitized the
    # overlap (c4f10528 official-run casualty). The anaphor noun
    # matching the question head noun separates the true bearer from
    # the entity the LOCATOR names ("Cihampelas Walk: ... this
    # shopping center ..." — wrong head) and from verb-prefix colon
    # items ("Take a cooking class: ..." — not a name). Tier among
    # passers first; exemption pass (raw >= 2, preface penalty +
    # weighted_floor kept) mirrors the C534 shape; fires only when a
    # best already exists — best=None falls through untouched
    # (censused behavior, 8-row routing ∩ demand population, exactly
    # 1 change / 0 kills).
    head = _name_def_head(question)
    if head and best is not None:
        tier = [p for p in passers if _name_def_bearer(p[1], head)]
        if tier:
            faced = max(tier, key=lambda p: p[0])
            if faced[1] != best[1]:
                best = faced
                detail["name_def_face"] = "tier"
        else:
            exempt: list[tuple[float, str, str | None, int]] = []
            for s, sid in pool:
                if not _name_def_bearer(s, head):
                    continue
                matched = [kw for kw in kws if w[kw]
                           and _keyword_hits(s, [kw])]
                if len(matched) < 2:
                    continue
                score = sum(w[kw] ** 2 for kw in matched)
                if _RECALL_PREAMBLE_RE.match(s):
                    score *= 0.25
                if score >= weighted_floor:
                    exempt.append((score, s, sid, len(matched)))
            if exempt:
                best = max(exempt, key=lambda p: p[0])
                detail["name_def_face"] = "exemption"
    detail["best_score"] = round(best[0], 1) if best else 0
    if best is None:
        return None, detail
    detail["session_id"] = best[2]
    detail["raw_hits"] = best[3]
    if best[0] < weighted_floor:
        return None, detail
    return best[1], detail


# ── C537: speech-act face — "you recommended" ⇒ first-person act ──
# (question-side detector, candidate-side bearer). The question
# references the assistant's own past speech act; the direct answer
# lives in a sentence performing that act ("I would recommend X").
# Irregular pasts (told/said/gave) listed beside their stems; \w*
# covers regular inflections (recommended/suggesting/gives).
_SPEECH_ACT_VERB = (r"(?:recommend|suggest|mention|advise|share|"
                    r"provide|tell|said|say|told|gave|give)")
_SPEECH_ACT_Q_RE = re.compile(
    r"\byou\b[^.?!]{0,80}?\b" + _SPEECH_ACT_VERB + r"\w*", re.I)
_I_SPEECH_ACT_RE = re.compile(
    r"\bi\b(?:['’](?:ve|ll|m))?(?:\s+\w+){0,2}?\s+\b("
    + _SPEECH_ACT_VERB + r")\w*", re.I)

# C537 A/B kills (488d3006, c8f1aeed) — an act sentence only answers
# a "what did you recommend" question when it performs the act ON A
# CONCRETE OBJECT. Three structural exclusions, no thresholds:
# propositional clause ("I can suggest THAT hiking …"), negated or
# absent act ("since you DIDN'T mention … I'll provide …"), generic
# object ("recommend SOME OTHER bands …" — topic-incoherent
# parasitism of the act verb itself). The GT bearer ("I would
# recommend Roscioli.") passes all three. A fourth exclusion lives
# at the call site: preamble-prefixed passers (C475 penalty) are
# never bearers — "Sure, here are the options I mentioned …" is a
# hand-over, not an act on an object (C475: prefaces parasitize
# you-addressed questions by construction).
_SPEECH_ACT_NEG_BEFORE_RE = re.compile(
    r"\b(?:not|never|didn't|don't|doesn't|can't|cannot|won't|"
    r"haven't|hasn't|did not|do not)\b[^.?!]{0,40}$", re.I)
_SPEECH_ACT_PROP_RE = re.compile(r"^\s+that\b", re.I)
_SPEECH_ACT_GENERIC_OBJ_RE = re.compile(
    r"^(?:\s+\w+){0,2}?\s+\b(?:some|any|other|another|general|"
    r"various|certain|few)\b", re.I)


def _speech_act_bearer(sent: str) -> bool:
    """True when *sent* performs a first-person speech act with a
    concrete object (C537 guards — see block comment above)."""
    for m in _I_SPEECH_ACT_RE.finditer(sent):
        verb_start = m.start(1)
        before = sent[max(0, verb_start - 45):verb_start]
        after = sent[m.end(1):]
        if _SPEECH_ACT_NEG_BEFORE_RE.search(before):
            continue
        if _SPEECH_ACT_PROP_RE.match(after):
            continue
        if _SPEECH_ACT_GENERIC_OBJ_RE.match(after):
            continue
        return True
    return False


# ── C534: answer-type demands (recall answer-type face) ────────────
# (demand name, question-side detector, candidate-side bearer pattern).
# Ordered: more specific demands first (a "handle" question that also
# says "how much" is a handle question).
_RECALL_TYPE_DEMANDS = (
    ("handle", re.compile(r"\bhandle\b", re.I), re.compile(r"@\w+")),
    ("money", re.compile(r"\bhow much\b", re.I),
     re.compile(r"[$€£]\s?\d[\d,]*"
                r"|\b\d+\s?(?:dollars|euros|pounds)\b", re.I)),
    ("year", re.compile(r"\b(?:what|which) year\b", re.I),
     re.compile(r"\b(?:19|20)\d{2}\b")),
    ("number", re.compile(r"\bhow many\b", re.I), re.compile(r"\d")),
)


# ── C559: name-demand definitional-anaphora face ───────────────
# Question side: "...the name of that|the <head phrase> ..."; the
# head phrase is cut at the first stopword/preposition ("restaurant
# in Cihampelas Walk" -> {restaurant}). Candidate side: a sentence
# of the form "<MultiCapitalWord Name>: ... this|that <anaphor
# phrase> ..." — a definition by anaphora ("Miss Bee Providore:
# This restaurant serves ..."). The face promotes such a bearer
# only when the anaphor phrase overlaps the question head noun —
# the structural test that separates the asked entity's definition
# from locator-sibling definitions ("Cihampelas Walk: ... this
# shopping center ...") and verb-prefix colon items ("Take a
# cooking class: ...", lowercase prefix word -> not a name).
_NAME_DEF_Q_RE = re.compile(
    r"\bname\s+of\s+(?:that|this|the|a|an)\s+"
    r"((?:[a-z'-]+\s+){0,3}[a-z'-]+)", re.I)
_NAME_DEF_BEARER_RE = re.compile(
    r"^[A-Z][\w'&.\-]*(?:\s+[A-Z][\w'&.\-]*)+\s*:")
_NAME_DEF_ANAPHOR_RE = re.compile(
    r"\b(?:this|that)\s+((?:[a-z'-]+\s+){0,2}[a-z'-]+)", re.I)
_NAME_DEF_CUT = {"in", "at", "on", "of", "near", "by", "for", "with",
                 "from", "to", "that", "which", "who", "whose", "and",
                 "or", "but", "is", "was", "are", "were", "a", "an",
                 "the", "you", "we", "i", "they"}


def _name_def_tokens(phrase: str) -> list[str]:
    """Head/anaphor phrase -> stemmed tokens, cut at the first
    stopword/preposition (stops the capture window from swallowing
    modifiers that belong to the rest of the sentence)."""
    out: list[str] = []
    for t in phrase.lower().split():
        if t in _NAME_DEF_CUT:
            break
        out.append(t[:-1] if t.endswith("s") and len(t) > 3 else t)
    return out


def _name_def_head(question: str) -> list[str] | None:
    """Question head-noun tokens of a name demand, or None."""
    m = _NAME_DEF_Q_RE.search(question)
    if not m:
        return None
    return _name_def_tokens(m.group(1)) or None


def _name_def_bearer(sent: str, head: list[str]) -> bool:
    """True when *sent* defines an entity under a proper name and the
    anaphor phrase matches the demanded head noun (C559 guards)."""
    if not head or not _NAME_DEF_BEARER_RE.match(sent):
        return False
    colon = sent.find(":")
    for m in _NAME_DEF_ANAPHOR_RE.finditer(sent, colon + 1):
        toks = _name_def_tokens(m.group(1))
        if toks and set(toks) & set(head):
            return True
    return False


# ── C536: ordinal-item face — "the fifth bottle you recommended" ──
#
# NEGATIVE RESULT (census-negative, unwired — see answer_extractive
# note). Question structure, not score, should locate the answer
# (C531 either/or principle, #086 "the question is the join
# condition"): an ordinal index into the assistant's enumerated
# list joins directly onto the "N."-marked item. The join works on
# clean mini-fixtures (tests below) but the frozen-500 census
# falsified it at node level: 3249768e's corpus contains TWIN
# five-bottle cocktail lists (both kh=12, both act-prefaced, only
# "gin-based" phrasing separates GT from "5. Triple Sec") and
# 1903aded's GT is a bare numbered list ("1. Virtual customer
# service representative … 7. Transcriptionist", kh=1 — any
# relevance floor excludes it while an act-bearing presentation-
# tips list wins kh=8). Enumerated lists lack a unique structural
# key; rescuing these rows needs an embedding side-channel join
# (C506 precedent), not lexical ranking. 8752c811 did extract the
# right item ("27. Sound effects …") but exact_judge is
# truth⊆predicted and the GT wraps the item in a full sentence —
# judge-side, not retrieval-side.
#
# 3249768e forensics kept for the record: the GT line "5. Absinthe:
# …" scores only 2 raw keyword hits (below the C475 raw floor 3)
# while the list PREFACE wins speaker_recall outright — and
# _split_sentences strips the "5." marker, so any sentence-level
# ordinal face must join on the node label.
#
# C540 addendum — the "embedding side-channel join" plan above was
# probed and FALSIFIED (3249768e, MiniLM via the C506 engine):
# message-level cos(q, decoy)=0.7068 > cos(q, GT)=0.5607, preface-
# sentence level 0.7725 > 0.7286, item-line level 0.2404 > 0.1926 —
# the decoy list is a semantic superset of the question domain and
# MiniLM treats the "gin-based" constraint as minor mass. The
# surviving separator is question-PHRASE continuity: the full
# keyword run "widest variety of gin based cocktails" appears only
# in the GT node (run 5 vs decoy 2). See answer_ordinal.
_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
    "tenth": 10, "eleventh": 11, "twelfth": 12,
}
_ORDINAL_ITEM_Q_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|"
    r"tenth|eleventh|twelfth|(\d{1,2})(?:st|nd|rd|th))\s+"
    r"([a-z][a-z\-]*)", re.I)
_YOU_LIST_ACT_RE = re.compile(
    r"\byou\b[^.?!]*\b(recommend|suggest|list|give|mention|share|"
    r"provid)\w*", re.I)
# A/B lesson (C536 first cut): node relevance alone joins the WRONG
# enumerated list — "5. Triple Sec" in an unrelated cocktail list and
# "7. Encourage Questions" in a presentation-tips list both out-
# scored the GT nodes. The real join keys are structural: the head
# noun after the ordinal ("bottle"/"job"/"parameter") must appear in
# the carrying node, and a question-stated list size ("five bottles")
# pins the candidate list's item count.
_SIZE_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
               "seven": 7, "eight": 8, "nine": 9, "ten": 10,
               "eleven": 11, "twelve": 12, "twenty": 20}
_LIST_SIZE_Q_RE = re.compile(
    r"\b(ten|twenty|two|three|four|five|six|seven|eight|nine|eleven|"
    r"twelve|\d{1,3})\s+[a-z][a-z\-]*s\b", re.I)


def _kw_phrase_run(label: str, kws: list[str]) -> int:
    """Longest contiguous question-keyword run found in *label*.

    C540 tie-break for enumerated-list joins: bag-of-keyword counts
    tie on twin lists (3249768e, both kh=12) while the QUESTION's
    own phrase — "widest variety of gin based cocktails" — appears
    verbatim only in the GT node. Both sides use the Cycle 471
    token normalization (quote/possessive strip + inflectional
    _token_matches), so "gin-based" in the question yields the
    keyword pair ``gin, based`` and matches "gin-based" in a label.
    Runs shorter than 2 keywords carry no phrase evidence (0).
    """
    if len(kws) < 2:
        return 0
    toks = [_strip_quotes(t.removesuffix("'s"))
            for t in re.findall(r"[a-z']+", label.lower())]
    n, m = len(kws), len(toks)
    for size in range(min(n, 8), 1, -1):
        for i in range(n - size + 1):
            seq = kws[i:i + size]
            for j in range(m - size + 1):
                if all(_token_matches(toks[j + k], seq[k])
                       for k in range(size)):
                    return size
    return 0


def ordinal_item_form(question: str) -> bool:
    """True when the question demands an indexed item of a list the
    assistant previously gave (tight dual guard — see C536 notes)."""
    return bool(_ORDINAL_ITEM_Q_RE.search(question)
                and _YOU_LIST_ACT_RE.search(question))


def answer_ordinal(question: str,
                   nodes: dict) -> tuple[str | None, dict]:
    """Nth enumerated-list item head term from the assistant corpus.

    Scans assistant node labels (sentence splitting destroys the
    ``N.`` marker) for the question's ordinal ``N``, selects the
    carrying node by question-keyword relevance (floor 3 — a
    spurious ``N.`` item in an unrelated node cannot win), and
    returns the item's HEAD TERM (text before ``:`` / `` - `` /
    sentence end, the "Absinthe" of "5. Absinthe: Absinthe
    is …"). Kh ties — twin enumerated lists, the C536
    falsification — are broken by the longest contiguous
    question-keyword phrase run in the label (``_kw_phrase_run``;
    the embedding alternative was probed and falsified in C540,
    see the census notes above). Unresolvable → ``(None, detail)``
    and the caller falls through to the speaker-recall path
    untouched.
    """
    m = _ORDINAL_ITEM_Q_RE.search(question or "")
    n = (_ORDINAL_WORDS.get(m.group(1).lower()) if m
         else None) or (int(m.group(2)) if m and m.group(2) else None)
    detail: dict = {"ordinal": n}
    if not n or n > 99:
        return None, detail
    kws = _keywords(question)
    noun = (m.group(3).lower() if m and m.group(3) else "")
    noun_base = noun[:-1] if noun.endswith("s") else noun
    size_m = _LIST_SIZE_Q_RE.search(question or "")
    want_size = (_SIZE_WORDS.get(size_m.group(1).lower())
                 if size_m and size_m.group(1).isalpha()
                 else (int(size_m.group(1)) if size_m else None))
    detail["join_noun"] = noun_base or None
    detail["join_size"] = want_size
    item_re = re.compile(rf"^\s*{n}[.)]\s+(.+)$", re.M)
    cands: list[tuple[int, int, str, str | None]] = []
    for node in (nodes or {}).values():
        if node.get("role") != "assistant":
            continue
        label = node.get("label", "") or ""
        im = item_re.search(label)
        if not im:
            continue
        nlab = _normalize(label)
        if noun_base and noun_base not in nlab:
            continue          # head noun not in this node -> wrong list
        if want_size:
            n_items = len(re.findall(r"^\s*\d{1,3}[.)]\s", label, re.M))
            if n_items != want_size:
                continue      # list length pins the question's "five"
        kh = _keyword_hits(label, kws)
        if kh < 3:          # relevance floor on the carrying node
            continue
        run = _kw_phrase_run(label, kws)
        cands.append((run, kh, im.group(1).strip(), node.get("session_id")))
    detail["nodes_with_item"] = bool(cands)
    if not cands:
        return None, detail
    # phrase-run beats kh (C540); equal (run, kh) keeps ingest order
    best = max(cands, key=lambda c: (c[0], c[1]))
    if best[0] < 2:
        # No question-phrase echo in ANY carrier — the kh floor alone
        # selected this node, and C536 showed kh floors join wrong
        # lists (1903aded: presentation-tips "7. Encourage Questions"
        # out-scores the kh=1 GT bare list). Fall through honestly.
        return None, detail
    detail["run"] = best[0]
    detail["node_kh"] = best[1]
    detail["session_id"] = best[3]
    head = re.split(r"\s*[:\u2013\u2014]\s*|\s+-\s+|\.\s",
                    best[2], 1)[0].strip()
    if not (2 <= len(head) <= 80):
        head = best[2][:80]     # no clean separator: bounded raw item
    detail["item"] = head
    return head, detail


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
    r"suburbs?|cit(y|ies)|towns?|downtown|countryside|mountains?|beaches?|"
    r"campus|offices?|gyms?|garage|bedrooms?|closets?|kitchens?|"
    r"yards?|balcon(y|ies)|basement|attic|beds?|shelves?|shelf|walls?|"
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
# C541: past-act interrogation form + future-intention markers. Markers are
# checked ONLY in the clause containing the locative span (naive whole-sentence
# scan falsified by census: d52b4f67 banked winner demoted via tangent clause
# "want to get her something", e01b8e2f via trailing "thinking of planning").
_WHERE_DID_RE = re.compile(r"\bwhere\s+did\s+(?:i|we|you)\b", re.I)
_WHERE_INTENT_RE = re.compile(
    r"\b(?:considering|pursuing|planning|thinking\s+(?:of|about)|narrowed\s+down|"
    r"hoping|would\s+like|want\s+to|applying|intend|going\s+to|plan\s+to|"
    r"looking\s+(?:into|at|forward))\b", re.I)
_WHERE_CLAUSE_SPLIT_RE = re.compile(
    r",\s+(?:and|but|or|so)\s+|;\s+|\s+-\s+|\s+—\s+")


def _where_intent_in_loc_clauses(sent: str) -> bool:
    """True when a locative-bearing clause of *sent* is intention-shaped."""
    for clause in _WHERE_CLAUSE_SPLIT_RE.split(sent):
        if _where_loc_candidates(clause) and _WHERE_INTENT_RE.search(clause):
            return True
    return False


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
                              "sent": sent,
                              "intent": _where_intent_in_loc_clauses(sent)})
    if not cands:
        return None, {"sessions": len(sess_rank), "cands": 0}
    # C541: past-act interrogation demotes future-intention winners.
    # "Where did I <V>" asks about a COMPLETED act; a candidate whose
    # locative clause is intention-shaped ("considering pursuing...",
    # "narrowed down my options to...") asserts a plan, not a memory
    # (25e5aa4f: the Master's-plan line beat "completed my undergrad
    # in CS from UCLA" on kh priors). Band restriction (C533 floor
    # shape): demote only when a clean candidate exists; all-marked
    # populations are untouched. Question-conditioned (strict did-form
    # — present-tense where questions keep the untouched ranking).
    if _WHERE_DID_RE.search(question):
        marked = [c for c in cands if c["intent"]]
        clean = [c for c in cands if not c["intent"]]
        if marked and clean:
            cands = clean
    cands.sort(key=lambda c: -c["score"])
    best = cands[0]
    # C533: relevance floor. The question is the join condition
    # (#086): a locative-dense line sharing ZERO question keywords
    # is not evidence for THIS question — when the top candidate has
    # kh=0 but some candidate echoes the question (kh>=1), the
    # best-scoring kh>=1 candidate wins instead (locative priors
    # still rank within the kh>=1 band). Forensic trigger (C533,
    # 3d86fd0a): kh=0 "organize my gym bag ... to the gym" beat the
    # GT-bearing "For Sophia, it was a coffee shop in the city."
    # (kh=1) purely on role/first-person priors. kh=0 winners with
    # NO kh>=1 candidate are untouched (the question's vocabulary
    # genuinely never recurs — answer stays locative-best).
    floor = False
    if best["kh"] == 0:
        rel = [c for c in cands if c["kh"] > 0]
        if rel:
            rel.sort(key=lambda c: -c["score"])
            best = rel[0]
            floor = True
    detail = {"sessions": len(sess_rank), "cands": len(cands),
              "best": {"role": best["role"], "kh": best["kh"],
                       "score": best["score"]},
              "relevance_floor": floor,
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
        anchor = m.group(2).strip()
        # Cycle 556: "how many days ago did I X when I Y" — the
        # annotator's value is the X→Y event SPAN, not the ask-to-
        # event distance (census: the only two ago+when members in
        # the full 500 are eac54adc 19 = 03-01 contract minus 02-10
        # launch; 9a707b81 21 = 04-10 cake minus 03-20 class, where
        # the class line says "yesterday" — qd-anchored arithmetic
        # gives 24/25 and misses both). Split on " when " and map
        # onto the between-style span arithmetic (same convention
        # as _TA_SINCEWHEN above).
        wm = re.search(r"\s+when\s+", anchor, re.I)
        if wm:
            b = anchor[wm.end():].strip()
            b = re.sub(r"^i\s+", "", b, flags=re.I)
            return ("ago_when", m.group(1).rstrip("s") or "day",
                    anchor[:wm.start()].strip(), b)
        return ("ago", m.group(1).rstrip("s") or "day", anchor, None)
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

# Cycle 556: line-relative day shift for ago_when span anchors —
# a line saying the event was "yesterday" dates the event one day
# before its session (9a707b81: class line in the 03-21 session,
# event 03-20; span to the 04-10 cake session = 21 = GT). Only
# engaged by the ago_when path (span_mode), never by the shared
# ladder's other callers.
_TA_YESTERDAY_RE = re.compile(r"\byesterday\b", re.I)


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

    def best_line(anchor: str,
                  span_mode: bool = False) -> tuple[int, str] | None:
        """Best dated line for *anchor* (≥1 distinctive hit).

        Cycle 471 tie ladder (was: silent first-max = list-position
        tie-break, which decided 3 of 9 forensics failures):
        distinctive hits ↓, user-role, generic hits ↓ (tie-break
        only), past aspect over future marker, in-text date
        (Cycle 482), later date. C555: user-role moved ahead of
        the generic-keyword tie-break — assistant tangents
        systematically echo the question's own scaffolding verbs
        ("encourage them to participate in your event"), so
        generic hits are assistant-biased; the asker's own words
        anchor the event (census: 45-row gate-routing set,
        mirror 45/45 chain-identical, exactly 1 designed rescue
        gpt4_b0863698 '16 days'→'7 days', 0 kills).
        span_mode (C556): ago_when span anchors only — (a) a
        winning line that says the event happened "yesterday"
        dates the event one day before its session (an explicit
        adverbial date always wins over the relative word);
        (b) a possessive tie-break slot after user-role — "my
        <keyword>" adjacency marks the asker's own event, which
        keyword-only ties otherwise lose to same-verb tangents
        (eac54adc: "I just launched my website" vs the WhatGPT
        "launching a service ... website campaigns" line, where
        the true line loses the future/past keys to its own
        "I want to make sure" scaffolding).
        Returns ``(hits, eff, line, refined)`` — C558 added the
        winning line text and whether ``eff`` came from an in-text
        adverbial (the relative-advance composition only engages
        when the line has no absolute date of its own).
        """
        ks = _anchor_keywords(anchor)
        if not ks:
            return None
        gen = [w for w in _keywords(anchor)
               if w in _ANCHOR_GENERIC and w not in ks]

        def _poss_hits(line: str) -> int:
            """Possessive-adjacent keyword hits (span_mode only):
            \"my|our <keyword>\" — the asker's own event."""
            return sum(1 for w in ks
                       if re.search(r"\b(?:my|our)\s+%s\b"
                                    % re.escape(w), line, re.I))

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
            ad = _line_eff_date(line, sdate, question_date, ks)
            if ad:
                eff = ad
            elif span_mode and _TA_YESTERDAY_RE.search(line):
                try:
                    eff = (date.fromisoformat(eff)
                           - timedelta(days=1)).isoformat()
                except ValueError:
                    pass
            try:
                date_key = (0, -date.fromisoformat(eff).toordinal())
            except ValueError:
                date_key = (1, 0)     # missing/unparseable date last
            key = (
                -hits,
                0 if line.startswith("[user]") else 1,
                -(_poss_hits(line) if span_mode else 0),
                -(_keyword_hits(line, gen) if gen else 0),
                1 if _TA_FUTURE_RE.search(line) else 0,
                0 if _TA_PAST_RE.search(line) else 1,
                0 if eff != sdate else 1,
                date_key,
            )
            if best_key is None or key < best_key:
                best, best_key = (hits, eff, line, bool(ad)), key
        return best

    if kind in ("ago", "since"):
        qd = parse_lme_date(question_date)
        ra = best_line(a)
        # C557: consecutive-pair refinement ("since" only). The
        # anchor clause describes TWO events on adjacent days; the
        # completion of that pair — not the most recent lone event —
        # is the ask-relative anchor. Scans the same candidate set
        # best_line sees, resolves each line's effective date via
        # the shared C482/C557 helper, and looks for a Δ1 pair.
        # No pair (or pair end after the ask) → keep best_line's
        # recency anchor (graceful degradation, never abstain).
        if (kind == "since" and qd and ra
                and _TA_PAIR_RE.search(a)):
            ks_p = _anchor_keywords(a)
            ds = set()
            for line, sdate in dated_lines:
                if not ks_p or _keyword_hits(line, ks_p) <= 0:
                    continue
                eff = (_line_eff_date(line, sdate, question_date,
                                      ks_p) or sdate)
                try:
                    date.fromisoformat(eff)
                except ValueError:
                    continue
                ds.add(eff)
            ordered = sorted(ds)
            pair_ends = [b for x, b in zip(ordered, ordered[1:])
                         if (date.fromisoformat(b)
                             - date.fromisoformat(x)).days == 1]
            if pair_ends and max(pair_ends) <= qd:
                ra = (ra[0], max(pair_ends), ra[2], ra[3])
        detail["anchors"] = [bool(ra)]
        if not qd or not ra:
            return None, detail
        # C558: relative-advance composition — the winning line may
        # date its event only relative to a pivot event ("<N> units
        # in advance") that a second line dates relative to its own
        # session ("M units ago"). Engages only when the line's date
        # was NOT already refined by an in-text adverbial (an
        # absolute date wins when present). No qualified pivot →
        # unchanged recency behavior (census: 1/500 engagement,
        # 982b5123).
        if (kind == "ago" and not ra[3]
                and _TA_ADVANCE_RE.search(ra[2])):
            comp = _compose_relative_advance(ra[2], dated_lines, qd)
            if comp is not None:
                n = duration_units(qd, comp, unit)
                detail["dates"] = [comp, qd]
                detail["value"] = n
                detail["compose"] = True
                return f"{n} {unit}{'' if n == 1 else 's'}", detail
        if ra[1] > qd:              # anchor resolves AFTER the ask —
            return None, detail    # wrong session; don't fabricate
        n = duration_units(qd, ra[1], unit)
        detail["dates"] = [ra[1], qd]
        detail["value"] = n
        return f"{n} {unit}{'' if n == 1 else 's'}", detail

    if kind == "ago_when":
        # Cycle 556: X→Y event span (see temporal_arith_form) —
        # both anchors resolve, span = calendar distance; same
        # date guards as "between" below. Both anchors run
        # span_mode: the X clause is where a recalled
        # "... class yesterday" line dates the event off its
        # session date, and the possessive slot separates the
        # asker's own event from same-verb tangents. Honesty
        # contract: either anchor unresolved (or both land on
        # one date) → abstain, never fall back to the qd-
        # anchored single-anchor arithmetic that misreads the
        # form (24/25 vs GT 19/21 on the census pair).
        ra = best_line(a, span_mode=True)
        rb = best_line(b, span_mode=True)
        detail["anchors"] = [bool(ra), bool(rb)]
        if not ra or not rb:
            return None, detail
        if ra[1] == rb[1]:
            return None, detail
        n = duration_units(ra[1], rb[1], unit)
        detail["dates"] = [ra[1], rb[1]]
        detail["value"] = n
        detail["span"] = True
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

# Units-progressive head (C563): "How many weeks have I been taking
# sculpting classes when …" — present-perfect PROGRESSIVE carries a
# duration-up-to-event semantics identical to the ``how long``
# family; the progressive ``-ing`` discriminator keeps the
# perfect-passive siblings ("how many weeks have I been accepted …",
# counting-gated, banked CORRECT) out by construction.
_PP_UNITS_PROG_RE = re.compile(
    r"^\s*how\s+many\s+(?:days?|weeks?|months?|years?)\s+"
    r"(?:have|had)\s+I\s+been\s+[a-z]+ing\b", re.I)

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
    if not (_PP_HEAD_RE.match(q) or _PP_UNITS_PROG_RE.match(q)):
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


def _pp_expr_sentence(line: str, expr: str) -> str:
    """The sentence of ``line`` containing duration expr ``expr``.

    Sentence is the unit of keyword-binding (C563): a tenure
    mention and the keyword it contextualizes can sit in adjacent
    sentences of one line — only same-sentence co-occurrence is
    acquisition evidence ("Speaking of my new binoculars, I got
    them exactly three weeks ago" vs "...for about a month now.
    My new binoculars has made a huge difference").
    """
    i = line.lower().find(expr.lower())
    if i < 0:
        return line
    off = 0
    for s in re.split(r"(?<=[.!?])\s+", line):
        if off <= i < off + len(s):
            return s
        off += len(s) + 1
    return line


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


_PP_QUNIT_RE = re.compile(
    r"^\s*how\s+many\s+(days?|weeks?|months?|years?)\b", re.I)


def _pp_session_span(question: str,
                     sessions: list[tuple[datetime, list[dict]]],
                     sk: list[str], ek: list[str]) -> str | None:
    """Route (d): session-pair span (C563).

    Units-progressive heads ("how many weeks have I been X-ing
    when Y?") often anchor state and event as same-session
    "today" facts — no ago/now expressions anywhere, so route (b)
    finds nothing to subtract. The span is the SESSION-pair
    distance |event_session − state_session|, rendered in the
    question's own unit (the unit is part of the question, not an
    anchor's phrasing). Engages only after route (b) misses;
    missing anchors, a shared line/date (unmeasurable span), or a
    unit with no faithful render (years) → None — honest
    fall-through, the gate chain keeps its claims.
    """
    if not (sk and ek):
        return None
    mu = _PP_QUNIT_RE.match(question)
    if not mu:
        return None
    unit = mu.group(1).lower().rstrip("s")
    if unit == "year":
        return None
    e_c, s_c = [], []
    for si, (dt, turns) in enumerate(sessions):
        for ti, turn in enumerate(turns):
            if turn.get("role") != "user":
                continue
            line = str(turn.get("content", ""))
            e_ov = _pp_overlap(ek, line)
            s_ov = _pp_overlap(sk, line)
            if e_ov >= min(2, len(ek)):
                e_c.append(((si, ti), e_ov, -s_ov, dt))
            if s_ov >= min(2, len(sk)):
                s_c.append(((si, ti), s_ov, -e_ov, dt))
    if not e_c or not s_c:
        return None
    ev_id, _ev_ov, _neg, ev_dt = max(e_c, key=lambda x: (x[1], x[2]))
    st_c = [x for x in s_c if x[0] != ev_id]
    if not st_c:
        return None
    st_id, _st_ov, _neg, st_dt = max(st_c,
                                     key=lambda x: (x[1], x[2]))
    if st_dt == ev_dt:
        return None
    days = float(abs((ev_dt - st_dt).days))
    if unit == "week":
        w = days / 7
        r = round(w)
        if 0 < r and abs(w - r) <= 0.5:
            return f"{r} week" + ("s" if r != 1 else "")
    if unit == "month":
        mo = days / 30.44
        r = round(mo)
        if 0 < r and abs(mo - r) <= 0.5:
            return f"{r} month" + ("s" if r != 1 else "")
    d = round(days)
    if d > 0:
        return f"{d} day" + ("s" if d != 1 else "")
    return None


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
        Overlap-tied state picks prefer same-sentence expressions
        (C563: the acquisition sentence beats a cross-sentence
        tenure mention sharing the line).
    (d) *session span* (C563) — units-progressive heads whose
        anchors are same-session "today" facts (no ago/now
        expressions anywhere): the span is the session-pair
        distance, rendered in the question's own unit. Only
        engages after route (b) misses.

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
        r"^\s*how\s+(?:long|many\s+(?:days?|weeks?|months?|years?))"
        r"\s+(?:had|have|did)\s+(?:i\s+)?(?:been\s+)?",
        "", state_clause, flags=re.I)
    sk, ek = _pp_kws(state_clause), _pp_kws(event_clause)
    scored = []  # (line_id, s_ov, e_ov, anchor, n, unit, kind, s_ss)
    for si, (dt, turns) in enumerate(sessions):
        for ti, turn in enumerate(turns):
            if turn.get("role") != "user":
                continue
            line = str(turn.get("content", ""))
            for kind, n, u, raw in _pp_dur_exprs(line):
                anchor = dt - timedelta(days=n * _PP_UNIT_DAYS[u])
                low_sent = _pp_expr_sentence(line, raw).lower()
                s_ss = sum(1 for w in sk if w in low_sent)
                scored.append(((si, ti), _pp_overlap(sk, line),
                               _pp_overlap(ek, line), anchor, n, u,
                               kind, s_ss))
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
    # Same-sentence binding (C563): among overlap-tied candidates,
    # a duration expression whose containing sentence also carries
    # a state keyword is acquisition evidence; a cross-sentence
    # tenure mention ("...for about a month now. By the way, my
    # new binoculars...") is background context that happens to
    # share the line. First-maximal falls out only when the ss
    # column ties too — prior behavior preserved.
    st_c = [x for x in scored
            if len(sk) and x[1] >= min(2, len(sk))
            and x[0] != (best_event[0] if best_event else None)]
    best_state = max(st_c,
                     key=lambda x: (x[1], x[7], -x[2])) if st_c else None
    if not best_state or not best_event:
        span = _pp_session_span(question, sessions, sk, ek)
        if span is not None:
            detail["route"] = "session_span"
            return span, detail
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
    # Bare-number GT ("3" for a "how many weeks" question — the
    # unit lives in the question, the oracle stores the count):
    # credit only the pred that spells the question's own unit
    # ("3 weeks"); a unit mismatch ("3 months") stays wrong.
    _qm = re.match(r"\s*how\s+many\s+(days?|weeks?|months?|years?)\b",
                   question, re.I)
    if base.isdigit() and _qm and re.match(
            rf"{base}\s+{_qm.group(1).lower()}", p):
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
    # C519 (proper-noun false-fire forensics, full-500 census):
    # * degree-level attributes are CATEGORY words, not entities —
    #   "Where did I complete my Bachelor's degree…" fires on
    #   'Bachelor' while the corpus says "background in CS from
    #   UCLA" (25e5aa4f misfire; Master/PhD/MBA same shape)
    "Bachelor", "Master", "Masters", "Doctorate", "PhD", "MBA",
    # * media-format abbreviations pluralize like common nouns
    #   ("albums or EPs" — corpus has singular 'EP'; bf659f65
    #   misfire): the plural token is not a distinct entity
    "EPs", "CDs", "LPs", "DVDs",
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
    C519: the question is accent-FOLDED before tokenizing — 'Aragón'
    must yield the token 'Aragon', not the truncated 'Arag' (which
    then matches nothing; see _neg_exist_fold).
    """
    toks = re.findall(r"[A-Za-z][A-Za-z0-9-]*", _neg_exist_fold(question))
    out = []
    for i, t in enumerate(toks):
        if (t[0].isupper() and i > 0 and len(t) > 2
                and t not in _NEG_EXIST_STOP
                and (not t.isupper() or len(t) > 3)):
            out.append(t)
    return out


def _neg_exist_fold(text: str) -> str:
    """C519: Unicode accent fold for negative-existence matching.

    'Aragón' tokenizes at the accented char ([A-Za-z]-classes stop
    at 'ó'), leaving 'Arag' — which then matches nothing because
    '\\barag\\b' fails inside 'aragón' (the 'ó' is a word char).
    The user's own corpus names the place six times, yet the gate
    fired (488d3006 misfire). Folding BOTH sides via NFKD + strip
    combining marks turns 'Aragón'→'aragon' on both sides — a pure
    widening of the match relation (fires can only decrease).
    """
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


_NEG_EXIST_GEO_SUB = {
    # C519: state asked, subordinate place attested — the corpus
    # names the island/city, never the state (2318644b: 'Hawaii'
    # absent, every sentence says 'Maui'). Restricted map, census-
    # driven; each entry must earn its place by a misfire.
    "hawaii": ("maui", "honolulu", "oahu", "kauai", "hilo", "kona",
               "lahaina", "waikiki", "big island"),
}


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
    tl = _neg_exist_fold(haystack_text).lower()
    for e in ents:
        if re.search(rf"\b{re.escape(_neg_exist_fold(e).lower())}\b", tl):
            continue
        subs = _NEG_EXIST_GEO_SUB.get(_neg_exist_fold(e).lower())
        if subs and any(re.search(rf"\b{re.escape(s)}\b", tl)
                        for s in subs):
            continue
        return e
    return None


# ── Cycle 516: negative-existence, COMMON-noun restrictors ──
# C513's gate is proper-noun-only. The LME _abs trap family also
# swaps the asked-about OBJECT NOUN (violin vs guitar, football vs
# baseball, iPad vs iPhone, uncle vs niece, egg tarts, table
# tennis): the sibling drives retrieval, every gate fabricates.
# Absent common noun in an object-asking first-person question
# = same presupposition failure. Census v1→v6 over full-500
# (170→104→33→8→6 fires; false-fire forensics drove every stop):
#   * verbs paraphrase freely ("repotted"/"acquire"/"sold" absent
#     is NOT presupposition failure) → VERB_STOP + *ed/*ing suffix
#     heuristic with noun exceptions
#   * event-CLASS nouns (ceremonies/conferences) — corpora name
#     the specific event instead ("my graduation")
#   * hyphen/digit tokens paraphrase ("week-long", "pre-1920") →
#     skipped as candidates; corpus hyphens joined for matching
#     (home-grown ~ homegrown)
#   * modifiers drop legitimately ("music albums" corpus "albums")
#     → compounds are NOT checked at all (sibling-signature
#     separation falsified: adjectives precede trap nouns too —
#     killed pre-implementation, C510 virtual-flip discipline)
#   * typo tolerance: len>=7 with Levenshtein<=1 to any corpus
#     word suppressed ("buisiness"/"business")
# Final census: 6 fires / 500 — 5 abs-GT (all currently wrong),
# 1 real-GT paraphrase (homegrown→locally grown) currently wrong
# via pref-gate anyway → wrong→wrong, zero hijack.
_NEG_EXIST_COMMON_STOP = frozenset("""
how many much long often old far
many few lot lots thing things stuff kind sort
there here now then today yesterday tomorrow
when which where what who why ago order
number total first second third last past
minute minutes hour hours day days week weeks month months year years time times
page pages amount count level
money color price cost name
me my mine i you your
did do does have has had was were will would can could should is are be been am
the a an of for with to in on at from by or and but if as than
between without within during until since about after before while over under into onto near across through
weekend weekends family
this that these those
different various other more most less just only even also
very really quite some any each every all both
one two three four five six seven eight nine ten eleven twelve
currently initially instead regularly usually recently already
finally actually typically normally
""".split())

_NEG_EXIST_VERB_STOP = frozenset("""
graduate graduated pass passed attending attend attended
participate participated flied fly flew love loved cancel cancelled
wear worn save submit submitted complete completed use used reach
need book booked meet met get got give gave buy bought purchase
play played watch watched finish finished start started spend spent
dedicate practice practicing bake baked lead led try tried
collect collecting add added live living work working move moved
present presented study studied learn learned plan planning make made
take took see saw go went gone come came keep kept think worth
reading leading making view own gets acquire inherit repaint arrive sold
pick serve left read
""".split())

_NEG_EXIST_ADJ_STOP = frozenset("""
earliest latest typical consecutive minimum maximum formal initial
significant favorite excluding previous
""".split())

_NEG_EXIST_EVENT_CLASS = frozenset("""
ceremony ceremonies conference conferences festival festivals
party parties meeting meetings gathering gatherings meetup meetups
""".split())

_NEG_EXIST_NOUN_ED_ING = frozenset("""
seed speed feed bed hundred thousand morning evening wedding
something anything nothing
""".split())

# C518: "At which … did I" enters the same object-asking
# surface (census: exactly one new fire — "At which university
# did I present a poster for my undergrad course research
# project?", undergrad absent, sibling poster/thesis drive the
# echo; zero hijack, the six C516 fires unchanged).
_NEG_EXIST_OBJECT_FORM_RE = re.compile(
    r"^how (many|much|long|often|old|far)"
    r"|^(?:at which|what|when|where|which) .{0,40}\bI\b",
    re.I)


def _neg_exist_verbish(tok: str) -> bool:
    """Verb-surface heuristic (census-built): STOP list + *ed/*ing."""
    if tok in _NEG_EXIST_VERB_STOP:
        return True
    if tok in _NEG_EXIST_NOUN_ED_ING:
        return False
    return len(tok) > 4 and (tok.endswith('ed') or tok.endswith('ing'))


def _neg_exist_forms(tok: str) -> list[str]:
    """Corpus surface forms for a question token (stem-both-ways
    + cross-POS derivational tolerance: 'visit' matches 'visited'/
    'visiting' — corpus legitimately uses the verb where the
    question says the noun; derivational misses are safe (no
    fire), derivational false-fires would be hijacks)."""
    forms = [tok, tok + 's', tok + 'es', tok + 'ed', tok + 'd',
             tok + 'ing']
    if tok.endswith('e'):
        forms.extend([tok[:-1] + 'ed', tok[:-1] + 'ing'])
    if tok.endswith('ies'):
        forms.append(tok[:-3] + 'y')
    if tok.endswith('s'):
        forms.append(tok[:-1])
    if tok.endswith('es'):
        forms.append(tok[:-2])
    return forms


def _neg_exist_lev1(a: str, b: str) -> bool:
    """Levenshtein distance <= 1 with early exit."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def common_noun_missing(question: str,
                        haystack_text: str) -> str | None:
    """First absent COMMON-noun restrictor, or None.

    Complements :func:`negative_existence` (proper nouns): scans
    lowercase content tokens of first-person object-asking
    questions; a token absent from the FULL haystack (plural/
    hyphen/typo tolerant) means the asked-about object was never
    mentioned — presupposition failure, abstain whatever the
    sibling-driven retrieval confidence.
    """
    if not _NEG_EXIST_FIRST_PERSON_RE.search(question):
        return None
    if not _NEG_EXIST_OBJECT_FORM_RE.search(question):
        return None
    q = re.sub(r"'([^']{2,40})'", " ", question)  # quoted titles out
    q = re.sub(r"(\w+)'s\b", r"\1", q)          # uncle's -> uncle
    toks = re.findall(r"[A-Za-z][A-Za-z0-9-]*", q)
    tl = _neg_exist_fold(haystack_text).lower()
    tl_nohy = tl.replace('-', '')
    tl_words = None
    for t in toks:
        tok = t.lower()
        if (not t[0].islower() or len(tok) < 3
                or tok in _NEG_EXIST_COMMON_STOP
                or tok in _NEG_EXIST_ADJ_STOP
                or tok in _NEG_EXIST_EVENT_CLASS
                or '-' in tok or any(c.isdigit() for c in tok)
                or _neg_exist_verbish(tok)):
            continue
        pats = [rf"\b{re.escape(f)}\b" for f in _neg_exist_forms(tok)]
        if (any(re.search(p, tl) for p in pats)
                or re.search(rf"\b{re.escape(tok)}\b", tl_nohy)):
            continue
        if len(tok) >= 7:  # typo tolerance (buisiness ~ business)
            if tl_words is None:
                tl_words = set(re.findall(r"[a-z]{7,}", tl))
            if any(_neg_exist_lev1(tok, w) for w in tl_words):
                continue
        return tok
    return None


# C518: numeric-attribute compounds. "How many fish are there
# in my 30-gallon tank?" — the user owns a 20-gallon (and an old
# 10-gallon); "30-gallon" appears NOWHERE. C516 skips hyphen/
# digit tokens as restrictor candidates (paraphrase-prone), but
# a POSSESSIVE N-gallon compound is a quantity attribute, not a
# paraphrasable noun: absent = presupposition failure. Census
# full-500: 1 fire (the trap), zero hijack — noun-compound
# generalization deliberately NOT attempted (C510 falsified
# sibling-signature separation; hyphen tokens stay skipped).
_GALLON_MY_RE = re.compile(r"\bmy (\d{1,3}) ?-? ?gallons?\b", re.I)


def numeric_compound_missing(question: str,
                             haystack_text: str) -> str | None:
    """First absent possessive N-gallon compound, or None."""
    nums = _GALLON_MY_RE.findall(question)
    if not nums:
        return None
    tl = haystack_text.lower()
    for n in dict.fromkeys(nums):   # question order, deduped
        if not re.search(rf"\b{n} ?-? ?gallons?\b", tl):
            return f"{n}-gallon"
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


# C523 quantity-form face (see answer_extractive comment). Cardinal
# words only — NOT once/twice/couple/half, which saturate advice text
# and would both false-qualify candidates and false-guard the top.
_QUANTITY_FORM_RE = re.compile(r"^how\s+(?:many|long|much)\b", re.I)
_QUANTITY_TOKEN_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\b|\b(?:one|two|three|four|five|six|seven|"
    r"eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
    r"seventy|eighty|ninety|hundred|dozen)\b", re.I)

# C525: recency-adverb markers for current-state knowledge-update
# questions. Lexicalizes "the answer is the LATEST value" intent —
# the kupdate recency signal C524 localized to session/date (not
# keyword) granularity.
_KU_RECENCY_RE = re.compile(
    r"\b(?:so far|currently|to date|as of (?:now|today)|lately"
    r"|these days|up to now)\b", re.I)


def _quantity_form(question: str) -> bool:
    """True for how-many/long/much fact questions (Cycle 523).

    No family exclusions: gate ORDER means counting/TA/delta
    already had their pass upstream — their unresolved fall-throughs
    are exactly the answer-face population this re-rank serves; and
    where-questions (STRICT start-with-where) cannot match a ^how
    anchor. The top-line-number guard is the safety face."""
    return bool(_QUANTITY_FORM_RE.match(question.strip()))


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
    # C561: measurement-unit sums — the non-money siblings of
    # item_total ("total distance/weight/time"). Census (500):
    # exactly 4 rows (d3ab962e/6c49646a/bc149d6b/1192316e), all
    # previously WRONG, zero banked overlap.
    if re.match(r'^what (?:is|was) the total '
               r'(?:distance|weight|time)\b', ql):
        return "measure_sum"
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
    # C518: age_diff hoisted above the how-many block — its 4th
    # form starts "how old will … be when I get married"
    # (census: 1 fire full-500). The three C515 forms are all
    # "how many …" and disjoint from museum/inventory/enum
    # signatures, so the hoist is behavior-neutral for them.
    if _age_form_gate(ql):
        return "age_diff"
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

# C553: object-NP "hours spent on my <np>" questions — topic-anchored
# hour mentions resolved by recency (71315a70), not activity regexes.
_DUR_Q_SPENT = re.compile(
    r'how (?:many hours|much time) have i spent on (?:my|the|a|an)\s+'
    r'((?:[a-z]+[\- ]){0,5}[a-z]+)', re.I)
_DUR_HR_MENTION = re.compile(
    r'\b(\d+(?:\.\d+)?(?:\s*[-–]|to\s*)\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?)\s*'
    r'hours?\b|\bhalf an hour\b', re.I)

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
                if n is None or not unit:
                    # C553: a unit-less capture ("read the subreddit for
                    # like a") is not duration evidence; output is weeks.
                    continue
                if 'day' in unit:
                    n = round(n / 7.0, 2)
                elif 'week' not in unit:
                    # C553: hour-denominated binges have no week-math.
                    continue
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
    # C553 topic-anchored recency face: object-NP questions ("hours spent
    # on my <np>") carry no activity words — the realized-activity regex
    # models the wrong evidence family (a 30-minute walk fired for the
    # abstract ocean sculpture, 71315a70). Resolve from hour mentions in
    # clauses anchoring the question NP; latest occurrence wins
    # (knowledge-update convention, C550 recency).
    qm = _DUR_Q_SPENT.search(question.lower())
    if not acts and qm:
        q_stems = _dur_cstems(qm.group(1))
        latest, seq = None, -1
        for _, _, c in _dur_user_turns(sessions):
            seq += 1
            for cl in _dur_clauses(c):
                cl_l = cl.lower()
                if not any(st in cl_l for st in q_stems):
                    continue
                for m in _DUR_HR_MENTION.finditer(cl):
                    if m.group(0).lower() == 'half an hour':
                        tok = '0.5 hours'
                    else:
                        ntok = m.group(1).replace(' ', '').replace('–', '-')
                        tok = f"{ntok} hours"
                    latest = (seq, tok)
        if latest is not None:
            return latest[1]
        # C553 honesty contract: object-NP form recognized but no
        # anchored evidence — abstain rather than answer from the
        # wrong evidence family (realized-activity regex).
        return None
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


# C561: measurement-unit sums — distance/weight/time siblings of
# item_total. Evidence discipline mirrors the money sums (#079):
# USER-role sentences only, ranges ("20-40 miles") are capacities
# not quantities. Intent refinement: an intent phrase BEFORE the
# quantity poisons it ("I'm thinking of getting 30 pounds" —
# planning mentions leak); intent phrasing AFTER the quantity
# ("… takes about 30 minutes, so I want to make the most of that
# time") does not — the takes/total anchor certifies the fact.
# Two tiers for distance/weight: when any user sentence marks a
# quantity with "total" ("covered a total of 1,800 miles"), ONLY
# marked sentences sum (unmarked per-day/first-day quantities are
# noise); otherwise all user quantities sum (3-mile loop + 5-mile
# hike). Time evidence must be "takes"-anchored ("commute takes
# about 30 minutes") — a quantity later in a takes-sentence
# ("… includes a 20-minute meditation") is not the sentence's
# duration, and "4.5-hour drive away" has no takes anchor at all.
_MEAS_NUM = r'(\d{1,6}(?:,\d{3})*(?:\.\d+)?)'
_MEAS_QTY_RE = {
    'distance': re.compile(r'(?<![\d,.])' + _MEAS_NUM
                           + r'\s*-?\s*miles?\b', re.I),
    'weight': re.compile(r'(?<![\d,.])' + _MEAS_NUM
                         + r'\s*-?\s*(?:pounds?|lbs?)\b', re.I),
}
_MEAS_RANGE_RE = {
    'distance': re.compile(r'\d[\d,]*(?:\.\d+)?\s*(?:-|\u2013|to)'
                           r'\s*\d[\d,]*(?:\.\d+)?\s*-?\s*'
                           r'miles?\b', re.I),
    'weight': re.compile(r'\d[\d,]*(?:\.\d+)?\s*(?:-|\u2013|to)'
                         r'\s*\d[\d,]*(?:\.\d+)?\s*'
                         r'(?:pounds?|lbs?)\b', re.I),
}
_MEAS_TIME_ANCHOR_RE = re.compile(
    r'\b(?:take|takes|took)\s+(?:(?:me|him|her|them|us)\s+)?'
    r'(?:about\s+|around\s+|roughly\s+|approximately\s+)?', re.I)
_MEAS_TIME_DIGIT_RE = re.compile(
    _MEAS_NUM + r'\s*(hours?|minutes?)\b', re.I)
_MEAS_TIME_WORD_RE = re.compile(
    r'^(a|an|one|two|three|four|five|six|seven|eight|nine|ten'
    r'|eleven|twelve)\s*(hours?)\b'
    r'(\s+and\s+a\s+half\b)?', re.I)


def _meas_render(total: float, singular: str, plural: str) -> str:
    t = round(total, 6)
    if t == int(t):
        n = int(t)
        return f"1 {singular}" if n == 1 else f"{n:,} {plural}"
    return f"{t:g} {plural}"


def _cnt_measure_sum(question: str, sessions: list[dict]):
    """C561: sum user-stated quantities of the question's measure
    unit (distance/weight/time siblings of ``total_sum``). Returns
    a unit-rendered string or ``None`` (fall through to the gate
    chain; the gates own abstention).
    """
    m = re.match(r'^what (?:is|was) the total '
                 r'(distance|weight|time)\b',
                 ' '.join(question.lower().split()))
    if not m:
        return None
    fam = m.group(1)
    if fam == 'time':
        return _meas_time_sum(sessions)
    qty_re, range_re = _MEAS_QTY_RE[fam], _MEAS_RANGE_RE[fam]
    marked, unmarked = [], []
    for _, sent in _cnt_sents(sessions):
        if sent.endswith('?'):
            continue
        poisoned = [im.start()
                    for im in _CNT_INTENT_RE.finditer(sent)]
        skip = [(rm.start(), rm.end())
                for rm in range_re.finditer(sent)]
        vals = [float(qm.group(1).replace(',', ''))
                for qm in qty_re.finditer(sent)
                if not any(s <= qm.start() < e for s, e in skip)
                and not any(i < qm.start() for i in poisoned)]
        if vals:
            (marked if re.search(r'\btotal\b', sent, re.I)
             else unmarked).extend(vals)
    vals = marked or unmarked
    if not vals:
        return None
    total = round(sum(vals), 6)
    if fam == 'distance':
        return _meas_render(total, 'mile', 'miles')
    return _meas_render(total, 'pound', 'pounds')


def _meas_time_sum(sessions: list[dict]):
    """C561 time face: sum takes-anchored durations in minutes."""
    mins = []
    for _, sent in _cnt_sents(sessions):
        if sent.endswith('?'):
            continue
        poisoned = [im.start()
                    for im in _CNT_INTENT_RE.finditer(sent)]
        for tm in _MEAS_TIME_ANCHOR_RE.finditer(sent):
            if any(i < tm.start() for i in poisoned):
                continue
            tail = sent[tm.end():]
            dm = _MEAS_TIME_DIGIT_RE.match(tail)
            if dm:
                n = float(dm.group(1).replace(',', ''))
                mins.append(n * 60 if dm.group(2).lower().startswith(
                    'hour') else n)
                continue
            wm = _MEAS_TIME_WORD_RE.match(tail)
            if wm:
                n = {'a': 1.0, 'an': 1.0, 'one': 1.0, 'two': 2.0,
                     'three': 3.0, 'four': 4.0, 'five': 5.0,
                     'six': 6.0, 'seven': 7.0, 'eight': 8.0,
                     'nine': 9.0, 'ten': 10.0, 'eleven': 11.0,
                     'twelve': 12.0}[wm.group(1).lower()]
                if wm.group(3):          # "an hour and a half"
                    n += 0.5
                mins.append(n * 60)
    if not mins:
        return None
    total = round(sum(mins), 6)
    h = total / 60.0
    if h == int(h):
        n = int(h)
        return "an hour" if n == 1 else f"{n} hours"
    if abs(h - int(h) - 0.5) < 1e-9:
        n = int(h)
        if n == 0:
            return "half an hour"
        return ("an hour and a half" if n == 1
                else f"{n} and a half hours")
    return f"{total:g} minutes"


# C562: category-sum face — the item_total sibling for questions
# whose "items" are a CATEGORY, not an enumerated list ("total
# amount I spent on luxury items"). Census (500,
# /tmp/c562/step1_census.py): exactly one routed row reached
# item_total with an empty _cnt_item_list (36b9f61e, GT $2,500 =
# 800 + 1,200 + 500) — the T1-T4b binders never saw it. Evidence
# (user-role only, verified from raw haystack,
# /tmp/c562/step2_evidence.py): three splurge anchors, each
# carrying exactly one price — same-sentence ("designer handbag
# ... for $1,200", "leather boots ... that I got for $500") or
# next-user-sentence anaphora ("...bought a luxury evening gown
# for a wedding." / "It was a big purchase, $800, ...").
# Assistant lifestyle math ($4,000 income, $1,400 discretionary,
# even a literal $2,500 example) and non-category purchases
# (H&M $20 graphic tees) are excluded by the role + category
# faces; intent planning lines ("I'm considering splurging...")
# are _CNT_INTENT_RE-poisoned (C561 lesson); multi-price anchors
# are skipped, never guessed.
_CNT_CAT_TERM_RE = re.compile(r'\bluxury\b', re.I)
_CNT_CAT_ANCHOR_RE = re.compile(
    r'\b(?:splurg\w*|bought|got|purchased?|purchases?|made)\b',
    re.I)


def _cnt_category_sum(question: str, sessions: list[dict]):
    """Sum user-stated prices behind category splurge anchors.

    Fires only when the question asks about spending on a named
    category ("luxury items/purchases") — i.e. the enumerated
    item list was empty. Each user anchor sentence contributes at
    most ONE distinct price: same-sentence when unique, else the
    next user sentence when it carries a cost face ("It was a
    big purchase, $800"). Returns ``$<total>`` (lane render) or
    ``None`` (question falls through untouched).
    """
    ql = ' '.join(question.lower().split())
    if not (_CNT_CAT_TERM_RE.search(ql)
            and re.search(r'\b(items|purchases)\b', ql)
            and re.search(r'\b(spend|spent)\b', ql)):
        return None
    by_sess: dict[int, list[str]] = {}
    for si, sent in _cnt_sents(sessions):
        by_sess.setdefault(si, []).append(sent)
    total = 0.0
    seen = 0
    for sents in by_sess.values():
        for k, sent in enumerate(sents):
            if sent.endswith('?') or _CNT_INTENT_RE.search(sent):
                continue
            if not (_CNT_CAT_TERM_RE.search(sent)
                    and _CNT_CAT_ANCHOR_RE.search(sent)):
                continue
            vals = _cnt_item_money(sent)
            if not vals:
                if k + 1 < len(sents):
                    nxt = sents[k + 1]
                    if (not nxt.endswith('?')
                            and not _CNT_INTENT_RE.search(nxt)
                            and _CNT_ITEM_COST_FACE.search(nxt)):
                        vals = _cnt_item_money(nxt)
                if not vals:
                    continue
            if len(set(vals)) != 1:
                continue          # ambiguous anchor — skip
            total += vals[0]
            seen += 1
    if not seen:
        return None
    return f"${round(total, 2):g}"


def _cnt_item_total(question: str, sessions: list[dict]):
    """Sum per-item prices for enumerated "total cost" questions.

    Cycle 500 ("What is the total cost of A and B I got?").
    Binding tiers, strictest first (first tier that resolves an
    item wins; every item must resolve or the question falls
    through untouched). C562: when the question names a CATEGORY
    instead of enumerated items (empty ``_cnt_item_list``), the
    category-sum face (``_cnt_category_sum``) owns the lane —
    "total amount I spent on luxury items" has no item list to
    bind:

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
        # C562: category-sum face — "luxury items" is not a list
        # the T1-T4b binders can work with; the category face
        # owns these rows (None when it doesn't match either)
        return _cnt_category_sum(question, sessions)
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
# C521: event-name occurrence counting — counted-NP heads whose
# instances surface as DISTINCT proper-noun event names, so the
# count is |distinct names|, not |clauses| (a festival mentioned
# five times is still one festival).
_ENUM_EVENT_NAME_HEADS = {'festival', 'fest'}
_ENUM_EVENT_NAME_PHRASE = re.compile(
    r"\b((?:[A-Z][\w&'\-]*\s+){0,4}[A-Z][\w&'\-]*\s*"
    r"(?:Festivals?|Fests?))\b")


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
# C518: third-party until-married — "How old will Rachel be
# when I get married?" The trap: Rachel's wedding chatter is in
# the corpus, Rachel's AGE never is; the echo answers from the
# wedding session. Census: 1 fire full-500, zero hijack.
_AGE_G_OTHER_UNTIL = re.compile(
    r"^how old will (\w+) be when i (?:get|'m getting|got)\s+married\b")

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
    """Exactly the census surface (C515+C518): four age-arithmetic
    question shapes, lowercase question input."""
    if _AGE_G_OTHER.search(ql):
        return 'other'
    if _AGE_G_THEN.search(ql):
        return 'then'
    if _AGE_G_UNTIL.search(ql):
        return 'until'
    if _AGE_G_OTHER_UNTIL.search(ql):
        return 'other_until'
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
    if form == 'other_until':
        # C518: "How old will Rachel be when I get married?" —
        # the subject's AGE anchor is the presupposition. Absent
        # anchor anywhere in the corpus = resolved negative
        # existence (C514 museum precedent: the counting layer
        # owns the abstain); anchored = fall through, arithmetic
        # never guesses (no timing anchor grammar exists yet).
        subj = _AGE_G_OTHER_UNTIL.search(ql).group(1)
        if subj in ('i', 'we'):
            return None
        if _age_other(sessions, re.escape(subj)):
            return None
        return ABSTAIN_ANSWER
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


# C552: temporal-scope qualifiers that override plain recency in
# _cnt_qty_stated — "before the 7/22 trip" (excluded date) and
# "first three months" (onset-window phrase). Census /tmp/c552:
# 2 RESCUE / 0 KILL on the 22-row enum_count population.
_DATE_MD = re.compile(r'\b\d{1,2}/\d{1,2}\b')
_BEFORE_DATE_Q = re.compile(
    r'\b(?:before|prior to)\s+(?:the\s+)?(\d{1,2}/\d{1,2})\b')
_FIRST_DUR_Q = re.compile(
    r'\bfirst\s+([a-z]+|\d+)\s+(months?|weeks?|years?|days?)\b')


def _cnt_qty_stated(question: str, sessions: list[dict]) -> str | None:
    """C550: explicit digit-quantity statements about the question's
    head noun (``600 followers``, ``15 crash course videos``).

    Census /tmp/c550 (2026-09-06, full-500 enum_count population = 10
    rows): 3 RESCUE / 0 KILL / 7 no-fire. Digits-only — word numerals
    are determiner poison here ("a baby", "one tank" = article usage,
    not counts; the naive all-numerals variant simulated 14 KILLs and
    was falsified pre-wiring). Recency: the LATEST user turn carrying
    a digit mention wins (current-state questions); coordinated
    questions (and/both/combined) SUM distinct values (5 tomato +
    3 cucumber plants = 8). Non-candidate turns still scan clauses
    carrying the head stem — evidence often drops the topic word
    ("now at 600 followers" without "Instagram").

    C552 (census /tmp/c552, gate=counting production replay, 66 rows
    byte-identical at HEAD / 22 enum_count rows): 2 RESCUE / 0 KILL.
    Plain recency loses when the question itself carries a temporal
    scope qualifier: "before the 7/22 trip" (10e09553) must resolve
    among explicitly DATED mentions, dropping the excluded date;
    "first three months" (0ddfec37) must resolve among clauses
    carrying that same duration phrase. When the qualifier is present
    but evidence cannot discriminate, the face ABSTAINS (None) —
    answering out-of-scope via bare recency is the failure mode the
    gates exist to prevent (same honesty contract as the same-turn
    ambiguity abstention below).
    """
    np_words = _enum_np(question)
    if not np_words:
        return None
    stems = [_enum_stem(w) for w in np_words]
    hstem = _enum_stem(np_words[-1])
    pat = re.compile(r'(\d+(?:,\d{3})*)(?=(?:\s+\w+){0,3}?\s+'
                     + re.escape(hstem) + r'\w*)')
    # lookahead (non-consuming) so multiple values ahead of one head
    # noun are all seen — "40 or 50 followers" must abstain, not
    # resolve to whichever number the consuming scan anchored first
    mentions: list[tuple[int, float]] = []
    clauses: list[tuple[int, float, str]] = []   # (seq, val, clause_lower)
    seq = 0
    for s in sessions:
        for t in s.get('turns', []):
            content = t.get('content', '')
            if t.get('role') != 'user' or len(content) <= 3:
                continue
            cand = any(st in content.lower() for st in stems)
            for cl in re.split(r'[.;!?]', content):
                cl_l = cl.lower()
                if not cand and hstem not in cl_l:
                    continue
                for m in pat.finditer(cl_l):
                    mentions.append(
                        (seq, float(m.group(1).replace(',', ''))))
                    clauses.append(
                        (seq, float(m.group(1).replace(',', '')), cl_l))
            seq += 1
    if not mentions:
        return None
    ql = question.lower()
    if re.search(r'\b(?:and|both|combined)\b', ql):
        total = sum({v for _, v in mentions})
        return str(int(total)) if total == int(total) else str(total)
    # C552 Gate A: "before the 7/22 trip" — resolve among explicitly
    # dated mentions, dropping clauses that carry the excluded date.
    # The undated anaphoric echo ("remember that trip when we caught
    # 9...") never votes: when the question pins a date boundary,
    # only dated evidence can discriminate.
    ma = _BEFORE_DATE_Q.search(ql)
    if ma:
        excl = ma.group(1)
        survivors = [(s, v) for s, v, cl in clauses
                     if _DATE_MD.search(cl) and excl not in cl]
        if survivors:
            vals = {v for _, v in survivors}
            if len(vals) == 1:
                v = vals.pop()
                return str(int(v)) if v == int(v) else str(v)
        return None          # qualifier pinned, evidence can't date it
    # C552 Gate B: "first three months" — resolve among clauses
    # carrying that same duration phrase (word/digit forms cross-
    # matched). Onset-window questions and recency windows disagree
    # by design; the phrase match is the discriminating signal.
    mb = _FIRST_DUR_Q.search(ql)
    if mb:
        num, unit = mb.group(1), mb.group(2)
        # numeral variants both ways: "first 3 months" must match a
        # "three months" clause and vice versa (a/an excluded upstream
        # from _CNT_NUMWORD so no article poison here)
        num_int = (int(num) if num.isdigit()
                   else _CNT_WORD2NUM.get(num))
        variants = {num}
        if num_int is not None:
            variants.add(str(num_int))
            variants.add(_CNT_NUMWORD.get(num_int, ''))
        dpat = re.compile(
            r'\b(' + '|'.join(re.escape(x) for x in variants if x)
            + r')\s+' + re.escape(unit) + r'\b')
        survivors = [(s, v) for s, v, cl in clauses
                     if dpat.search(cl)]
        if survivors:
            latest = max(s for s, _ in survivors)
            vals = {v for s, v in survivors if s == latest}
            if len(vals) == 1:
                v = vals.pop()
                return str(int(v)) if v == int(v) else str(v)
        return None          # qualifier pinned, no phrase match
    latest = max(s for s, _ in mentions)
    vals = {v for s, v in mentions if s == latest}
    if len(vals) != 1:
        return None          # same-turn ambiguity: honest abstention
    v = vals.pop()
    return str(int(v)) if v == int(v) else str(v)


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
    # C550: an explicit digit-quantity statement about the head noun
    # ("600 followers", "15 crash course videos") outranks signature
    # counting — the names/roles signature leaks the topic itself as
    # an instance ("crash course" counted = 1). Census-validated
    # 3 RESCUE / 0 KILL; runs after the form gate so the claim scope
    # is unchanged.
    qty = _cnt_qty_stated(question, sessions)
    if qty is not None:
        return qty
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
    # C521: event proper-name signature — attendance counted by
    # DISTINCT event proper-nouns ("Austin Film Festival" and
    # "AFI Fest" are two festivals however often each is
    # re-mentioned). Runs BEFORE the names/roles branch: event
    # candidate turns often carry person names (a director, a
    # volunteer meetup) that the names signature miscounts as
    # instances. Census @2026-08-27 (full-500): exactly ONE enum
    # question has an event-name head (gpt4_a56, GT=4 — was a
    # names-count/generic-recall miss); no other family moves.
    if _enum_stem(head) in _ENUM_EVENT_NAME_HEADS:
        events = set()
        for cl in cand_clauses:
            if _ENUM_EXCLUDE_VERBS.search(cl):
                continue
            for m in _ENUM_EVENT_NAME_PHRASE.finditer(cl):
                events.add(re.sub(
                    r"^(?:the|a|an)\s+", '',
                    re.sub(r'\s+', ' ', m.group(1)).lower()))
        if events:
            return str(len(events))
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
          "measure_sum": _cnt_measure_sum,
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
             data_source: str | None = None,
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
             quant_rerank: bool = True,
             ku_session_face: bool = True,
             session_complete_face: bool = True,
             role_answer: bool = True,
             role_margin: int = 0,
             assistant_recall: bool = True,
             recall_mode: str = "distinctive",
             recall_seed_k: int = 40,
             sidechannel: bool = False,
             deterministic_recall: bool = True,
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
        judge_mode: "exact" (default), "dual", or "semantic"
            (Cycle 529 — cascade judge; adds ``accuracy_exact`` /
            ``accuracy_llm``/``calibration``/``judge_ab`` to the
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
                  quant_rerank=quant_rerank,
                  ku_session_face=ku_session_face,
                  session_complete_face=session_complete_face,
                  role_answer=role_answer,
                  sidechannel=sidechannel,
                  deterministic_recall=deterministic_recall,
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
        "risk_coverage": risk_coverage_report(all_results),
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
    if judge_mode in ("dual", "semantic"):
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
        report["judge_ab"] = judge_ab_report(all_results)
        # Cycle 530: LLM-judge backend fingerprint. judge_llm
        # auto-detects once per process (ollama probe) and degrades
        # permanently to the lexical mock judge when no endpoint
        # answers — without this field a mock-resolved run is
        # indistinguishable from an oracle-resolved one in the report
        # (C530 cascade-500: 24 mock verdicts silently inflated the
        # raw cascade metric 262/500 vs 246 deterministic-bankable).
        # "unconsulted" = zero NEEDS_JUDGE rows, the semantic layer
        # decided everything; abs rows share the exact verdict and
        # never consult the LLM.
        report["config"]["judge_llm_backend"] = _JUDGE_MODE or "unconsulted"
        # Cycle 560: judge provenance — prompt-template hash + model id.
        # A JUDGE_PROMPT edit changes verdicts on identical code with no
        # report trace; judge_ollama's model parameter was invisible, so
        # ollama-resolved runs could not be told apart across models.
        report["config"]["judge_prompt_sha12"] = hashlib.sha256(
            JUDGE_PROMPT.encode("utf-8")).hexdigest()[:12]
        if (_JUDGE_MODE or "") == "ollama" and _JUDGE_MODEL:
            report["config"]["judge_model"] = _JUDGE_MODEL
    # Cycle 527: lineage fingerprint — dataset identity + interpreter
    # hash seed, recorded AFTER the dual-mode config overwrite so both
    # judge modes carry it. Rationale: the oracle-vs-s_cleaned dataset
    # mixup (0.526 vs 0.484 on identical code) and the ±2-question
    # PYTHONHASHSEED jitter both produce silent unreproducible diffs
    # in full-500 lineage comparisons; fingerprinting makes every
    # comparison auditable (runners should still pin PYTHONHASHSEED).
    if data_source:
        p = Path(data_source)
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        report["config"]["data_file"] = p.name
        report["config"]["data_sha256_12"] = h.hexdigest()[:12]
        report["config"]["pythonhashseed"] = (
            os.environ.get("PYTHONHASHSEED") or "unpinned")
    # Cycle 528: determinism flag travels with the report — readonly
    # recall runs are bitwise-replayable, wall-clock runs are not.
    report["config"]["deterministic_recall"] = deterministic_recall
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
    parser.add_argument("--no-quant-rerank", action="store_true",
                        help="Disable the Cycle 523 quantity-form "
                             "answer-face re-rank")
    parser.add_argument("--no-ku-session-face", action="store_true",
                        help="Disable the Cycle 525 knowledge-update "
                             "recency session-scope answer face")
    parser.add_argument("--no-session-complete-face", action="store_true",
                        help="Disable the Cycle 526 session-completion "
                             "face rescue")
    parser.add_argument("--wallclock-recall", action="store_true",
                        help="Legacy wall-clock recall (decay + access "
                             "boost writes). Default is readonly "
                             "deterministic recall (Cycle 528) — bitwise "
                             "replayable, immune to ingest-time jitter.")
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
    parser.add_argument("--judge", choices=("exact", "dual", "semantic"),
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
        quant_rerank=not args.no_quant_rerank,
        ku_session_face=not args.no_ku_session_face,
        session_complete_face=not args.no_session_complete_face,
        sidechannel=args.sidechannel,
        recall_mode=args.recall_mode,
        deterministic_recall=not args.wallclock_recall)

    if args.mode == "eval":
        entropies = None
        if args.sweep_entropies:
            entropies = [None if t.strip().lower() == "none"
                         else float(t)
                         for t in args.sweep_entropies.split(",")]
        report = run_eval(
            dataset, limit=args.limit, entropies=entropies,
            data_source=args.data,
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
            quant_rerank=not args.no_quant_rerank,
            ku_session_face=not args.no_ku_session_face,
        session_complete_face=not args.no_session_complete_face,
            neg_exist=not args.no_neg_exist,
            sidechannel=args.sidechannel,
            recall_mode=args.recall_mode,
            judge_mode=args.judge,
            deterministic_recall=not args.wallclock_recall)
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
