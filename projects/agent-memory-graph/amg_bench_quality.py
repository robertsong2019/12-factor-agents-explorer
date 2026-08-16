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
from pathlib import Path

from memory_graph import MemoryGraph

__all__ = [
    "QuestionResult",
    "CategorySummary",
    "LongMemEvalAdapter",
    "score_confidence",
    "entropy_gate_fires",
    "exact_judge",
    "load_longmemeval_data",
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
            ppr_top: Extra candidates taken from the PPR tail.
            seed_recall_k: Per-keyword recall limit for seed building.
        """
        self.mg = mg if mg is not None else MemoryGraph(db_path=":memory:")
        self.use_ppr = use_ppr
        self.max_context_tokens = max_context_tokens
        self.abstain_score = abstain_score
        self.abstain_entropy = abstain_entropy
        self.entropy_weak_score = entropy_weak_score
        self.ppr_top = ppr_top
        self.seed_recall_k = seed_recall_k
        # Adapter-side bookkeeping (avoids depending on repo getter
        # APIs): node id → {label, kind, role, seq, session_id}.
        self._nodes: dict[str, dict] = {}
        self._messages: dict[str, dict] = {}       # message nodes only
        self._entities: dict[str, str] = {}        # entity name → node id
        self._seq = 0                               # deterministic order

    # ── Phase 1: ingestion ─────────────────────────────────────────

    def ingest_sessions(self, sessions: list[dict]) -> dict:
        """Ingest conversation sessions into the memory graph.

        Each session: ``{"session_id", "timestamp"?, "messages":
        [{"role", "content", "timestamp"?}, ...]}``. Creates a session
        node, message nodes (``contains`` + ``follows`` edges) and
        entity nodes for capitalized non-stopwords
        (``mentioned_in`` edges, deduplicated across sessions).

        Returns:
            Stats dict ``{sessions, messages, entities, edges}``.
        """
        stats = {"sessions": 0, "messages": 0, "entities": 0, "edges": 0}

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
                 limit: int = 0) -> dict:
        """Run the full evaluation over a LongMemEval dataset.

        Per question: retrieve + extractive answer + judge. Scoring:

        * ``judge_fn(question, truth, predicted) -> bool`` when given
          (full-mode LLM judge), else ``exact_judge`` containment.
        * ``_abs`` questions (qid suffix or ``abstention`` flag) score
          correct iff the adapter abstained.
        * ``retrieval_hit``: normalized ground truth appears in the
          retrieved context — the zero-cost recall-quality metric
          (Research #061 Action 1: retrieval-only mode).

        Args:
            dataset: ``[{"id", "question", "answer", ...}]``.
            judge_fn: Optional external judge; default containment.
            limit: Evaluate at most this many questions (0 = all).

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
            elif judge_fn is not None:
                correct = bool(judge_fn(question, truth, predicted))
            else:
                correct = exact_judge(question, truth, predicted)

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
        return {
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
                       "max_context_tokens": self.max_context_tokens,
                       "abstain_score": self.abstain_score,
                       "abstain_entropy": self.abstain_entropy,
                       "entropy_weak_score": self.entropy_weak_score},
        }

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
        entropy_weak_score=args.entropy_weak)

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
                entropy_weak_score=args.entropy_weak)
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
                              "entropy_weak_score": args.entropy_weak}},
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
