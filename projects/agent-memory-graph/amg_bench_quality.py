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


def _keywords(question: str) -> list[str]:
    """Content keywords from a question (lowercased, stopwords removed).

    Possessives are stripped BEFORE the stopword filter so "user's"
    normalizes to the stopped word "user" (not a phantom keyword).
    """
    words = [w.removesuffix("'s")
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
    Cycle 447 smoke run).
    """
    tokens = re.findall(r"[a-z']+", label.lower())
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
                 ppr_top: int = 15,
                 seed_recall_k: int = 5):
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
            ppr_top: Extra candidates taken from the PPR tail.
            seed_recall_k: Per-keyword recall limit for seed building.
        """
        self.mg = mg if mg is not None else MemoryGraph(db_path=":memory:")
        self.use_ppr = use_ppr
        self.max_context_tokens = max_context_tokens
        self.abstain_score = abstain_score
        self.abstain_entropy = abstain_entropy
        self.entropy_weak_score = entropy_weak_score
        self.temporal_arith = temporal_arith
        self.ppr_top = ppr_top
        self.seed_recall_k = seed_recall_k
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

        # Seed: direct keyword recall (substring match, zero-cost).
        for kw in keywords[:8]:
            for node in self.mg.recall(kw, limit=self.seed_recall_k):
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
            dated_lines = [
                (f"[{self._nodes[nid]['role'] or '?'}] "
                 f"{self._nodes[nid]['label']}",
                 self._session_dates.get(
                     self._nodes[nid]["session_id"], ""))
                for nid in meta.get("retrieved_ids", [])
                if nid in self._nodes]
            t_ans, t_detail = answer_temporal_arith(
                question, dated_lines, question_date)
            meta["temporal"] = t_detail
            if t_ans is not None:
                meta["gate"] = "temporal_arith"
                meta["abstained"] = False
                return t_ans, meta

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
            qid = str(item.get("id", i))
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

            category = self._classify_question(question, qid)
            res = QuestionResult(
                question_id=qid, category=category, question=question,
                ground_truth=truth, predicted_answer=predicted,
                abstained=meta["abstained"], correct=correct,
                retrieval_hit=hit,
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

        total = len(results)
        report = {
            "overall_accuracy": (sum(r.correct for r in results) / total
                                 if total else 0.0),
            "retrieval_hit_rate": (sum(r.retrieval_hit for r in results)
                                   / total if total else 0.0),
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

    Days/weeks are exact; months use calendar-month arithmetic with
    half-month rounding; years round on 365.25 days.
    """
    da = date.fromisoformat(date_a)
    db = date.fromisoformat(date_b)
    days = abs((da - db).days)
    if unit == "week":
        return days // 7
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
        """Best-scoring dated line for *anchor* (≥1 keyword hit)."""
        ks = _anchor_keywords(anchor)
        if not ks:
            return None
        best, best_hits = None, 0
        for line, sdate in dated_lines:
            hits = _keyword_hits(line, ks)
            if hits > best_hits:
                best, best_hits = (hits, sdate), hits
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
                  temporal_arith=temporal_arith)
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
            "abstentions": 0, "hits": 0, "total_tokens": 0})
        c["total"] += 1
        c["correct"] += int(r["correct"])
        c["abstentions"] += int(r["abstained"])
        c["hits"] += int(r["retrieval_hit"])
        c["total_tokens"] += r["tokens_est"]
    for c in categories.values():
        t, tok = c["total"], c.pop("total_tokens")
        c["accuracy"] = round(c["correct"] / t, 4) if t else 0.0
        c["abstention_rate"] = round(c["abstentions"] / t, 4) if t else 0.0
        c["retrieval_hit_rate"] = round(c["hits"] / t, 4) if t else 0.0
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
        temporal_arith=not args.no_temporal_arith)

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
            judge_mode=args.judge)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n{report['total_questions']} questions · "
              f"accuracy {report['overall_accuracy']:.3f} · "
              f"retrieval_hit {report['retrieval_hit_rate']:.3f} · "
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
