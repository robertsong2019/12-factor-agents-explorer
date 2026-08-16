"""locomo_bench_quality.py — LoCoMo memory-quality adapter for amg-bench.

Cycle 451 (Research #067, 2026-08-16): adapts the LoCoMo benchmark
(snap-research/locomo, ACL 2024) on top of the LongMemEval quality
adapter (Cycles 447/448). Ten ultra-long conversations (up to 35
sessions / ~300 turns / ~9K tokens each), 1986 questions across five
categories::

    1 = single_hop (282)   2 = multi_hop (321)   3 = temporal (96)
    4 = open_domain (841)  5 = adversarial (446)

Design decisions carried from the research note:

* **Evidence is turn-level** — LoCoMo's ``evidence`` dia_ids
  (``"D<session>:<turn>"``) enable session- AND turn-level recall,
  which LongMemEval cannot offer. Reported as ``session_hit`` /
  ``turn_hit`` per question.
* **Adversarial (cat 5) is abstention-scored** — 22.5% of questions
  ask about events that never happened; competitors exclude them.
  amg answers the FULL set: cat 5 counts correct iff the adapter
  abstained (the C448 dual confidence gate). Retrieval metrics are
  meaningless for cat 5 and excluded from evidence-recall aggregates.
* **One graph per sample** — samples are independent conversations;
  cross-sample retrieval would be noise.

Zero-LLM protocol: extractive answers + ``exact_judge`` containment
(or an injected ``judge_fn``), tokens-per-query — directly comparable
to the C447/C448 LongMemEval reports.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from amg_bench_quality import (
    ABSTAIN_ANSWER,
    LongMemEvalAdapter,
    _normalize,
    exact_judge,
)

__all__ = [
    "CATEGORY_NAMES",
    "LoCoMoAdapter",
    "load_locomo",
    "run_locomo",
    "main",
]

CATEGORY_NAMES = {
    1: "single_hop",
    2: "multi_hop",
    3: "temporal",
    4: "open_domain",
    5: "adversarial",
}

_DIA_RE = re.compile(r"^D(\d+):(\d+)$")


def _dia_session(dia_id: str) -> str:
    """``"D3:12"`` → ``"S3"`` (ingest session id)."""
    m = _DIA_RE.match(dia_id)
    return f"S{m.group(1)}" if m else ""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class LoCoMoAdapter(LongMemEvalAdapter):
    """Per-sample LoCoMo adapter (one independent conversation graph).

    Reuses the full C447/C448 pipeline — ``ingest_sessions`` /
    ``retrieve_context`` / ``answer_extractive`` dual confidence gate —
    and adds LoCoMo specifics: dia_id → node indexing for turn-level
    evidence scoring and category-aware evaluation (cat 5 =
    abstention-scored adversarial questions).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dia_nodes: dict[str, str] = {}   # "D<n>:<t>" → node id

    # ── Ingestion ──────────────────────────────────────────────────

    def ingest_sample(self, sample: dict) -> dict:
        """Ingest one LoCoMo sample (``conversation`` + implied qa).

        Converts ``session_N`` lists (``speaker``/``dia_id``/``text``)
        into the adapter session format, ingests via the C447 pipeline,
        then indexes every dia_id to its message node id (insertion
        order is deterministic — ``self._messages`` is append-ordered).

        Returns:
            The ``ingest_sessions`` stats dict.
        """
        conv = sample.get("conversation", {})
        sessions: list[dict] = []
        flat_dias: list[str] = []

        n = 1
        while f"session_{n}" in conv:
            messages = []
            for msg in conv[f"session_{n}"]:
                messages.append({
                    "role": str(msg.get("speaker", "")),
                    "content": str(msg.get("text", "")),
                })
                flat_dias.append(str(msg.get("dia_id", "")))
            sessions.append({
                "session_id": f"S{n}",
                "timestamp": str(conv.get(f"session_{n}_date_time", "")),
                "messages": messages,
            })
            n += 1

        before = len(self._messages)
        stats = self.ingest_sessions(sessions)
        # Dicts preserve insertion order (Py3.7+): the tail of
        # ``_messages`` maps 1:1 onto the flattened input order.
        new_ids = list(self._messages)[before:]
        if len(new_ids) != len(flat_dias):
            raise RuntimeError(
                f"dia indexing mismatch: {len(new_ids)} new message "
                f"nodes vs {len(flat_dias)} input messages")
        for dia_id, nid in zip(flat_dias, new_ids):
            if dia_id:
                self._dia_nodes[dia_id] = nid
        return stats

    # ── Evidence helpers ───────────────────────────────────────────

    def evidence_node_ids(self, evidence: list[str]) -> set[str]:
        """Ground-truth message node ids for the evidence dia_ids."""
        return {self._dia_nodes[d] for d in evidence
                if d in self._dia_nodes}

    def evidence_sessions(self, evidence: list[str]) -> set[str]:
        """Ground-truth session ids (``"S<n>"``) from dia_ids."""
        return {_dia_session(d) for d in evidence
                if _DIA_RE.match(d)}

    def retrieved_sessions(self, retrieved_ids: list[str]) -> set[str]:
        """Session ids of the retrieved message nodes."""
        return {self._messages[nid]["session_id"]
                for nid in retrieved_ids if nid in self._messages}

    # ── Evaluation ─────────────────────────────────────────────────

    def evaluate_sample(self, qa: list[dict], *, judge_fn=None,
                        limit: int = 0) -> dict:
        """Evaluate one sample's question list.

        Scoring per category:

        * ``adversarial`` (5): correct iff the adapter abstained.
        * others: ``judge_fn(question, truth, predicted)`` when given,
          else ``exact_judge`` containment (zero-cost protocol).

        Evidence recall (non-adversarial only — retrieval metrics are
        meaningless for questions about events that never happened):

        * ``session_hit`` — any retrieved message belongs to an
          evidence session (session-level recall, the research-note
          baseline metric, R@k with k = messages packed in budget);
        * ``turn_hit`` — any retrieved message IS an evidence turn
          (dia_id-level precision, LoCoMo's unique strength);
        * ``context_hit`` — normalized truth appears in the full
          retrieved context (zero-cost answerability: the top-1
          extractive line is often the partner's reply, but the
          answer turn sits in the surrounding context window).

        Returns:
            ``{"sample_id", "overall_accuracy",
            "overall_accuracy_no_adversarial", "abstention_rate",
            "session_hit_rate", "turn_hit_rate", "context_hit_rate",
            "avg_tokens", "total_questions", "categories",
            "questions"}``.
        """
        items = qa[:limit] if limit and limit > 0 else qa
        rows: list[dict] = []
        cats: dict[str, dict] = {}

        for i, item in enumerate(items):
            qid = str(item.get("qid", i))
            question = str(item.get("question", ""))
            truth = str(item.get("answer", ""))
            evidence = [str(e) for e in item.get("evidence", [])]
            category = CATEGORY_NAMES.get(int(item.get("category", 0)),
                                          "unknown")
            is_adv = category == "adversarial"

            predicted, meta = self.answer_extractive(question)
            abstained = bool(meta["abstained"])

            if is_adv:
                correct = abstained
            elif judge_fn is not None:
                correct = bool(judge_fn(question, truth, predicted))
            else:
                correct = exact_judge(question, truth, predicted)

            retrieved = meta.get("retrieved_ids", [])
            ev_nodes = self.evidence_node_ids(evidence)
            ev_sessions = self.evidence_sessions(evidence)
            session_hit = (bool(ev_sessions) and not is_adv
                           and bool(self.retrieved_sessions(retrieved)
                                    & ev_sessions))
            turn_hit = (bool(ev_nodes) and not is_adv
                        and bool(ev_nodes & set(retrieved)))
            context_hit = (
                bool(truth) and not is_adv and not abstained
                and _normalize(truth) in _normalize(
                    meta.get("context", "")))

            row = {
                "qid": qid,
                "category": category,
                "question": question,
                "ground_truth": truth,
                "predicted": predicted,
                "abstained": abstained,
                "correct": correct,
                "session_hit": session_hit,
                "turn_hit": turn_hit,
                "context_hit": context_hit,
                "tokens_est": meta["tokens_est"],
                "gate": meta["gate"],
                "evidence": evidence,
            }
            rows.append(row)

            c = cats.setdefault(category, {
                "category": category, "total": 0, "correct": 0,
                "abstentions": 0, "session_hits": 0, "turn_hits": 0,
                "context_hits": 0, "total_tokens": 0})
            c["total"] += 1
            c["correct"] += int(correct)
            c["abstentions"] += int(abstained)
            c["session_hits"] += int(session_hit)
            c["turn_hits"] += int(turn_hit)
            c["context_hits"] += int(context_hit)
            c["total_tokens"] += meta["tokens_est"]

        total = len(rows)
        non_adv = [r for r in rows if r["category"] != "adversarial"]

        def _rate(num: int, den: int) -> float:
            return num / den if den else 0.0

        return {
            "total_questions": total,
            "overall_accuracy": _rate(sum(r["correct"] for r in rows),
                                      total),
            "overall_accuracy_no_adversarial": _rate(
                sum(r["correct"] for r in non_adv), len(non_adv)),
            "abstention_rate": _rate(
                sum(r["abstained"] for r in rows), total),
            "session_hit_rate": _rate(
                sum(r["session_hit"] for r in non_adv), len(non_adv)),
            "turn_hit_rate": _rate(
                sum(r["turn_hit"] for r in non_adv), len(non_adv)),
            "context_hit_rate": _rate(
                sum(r["context_hit"] for r in non_adv), len(non_adv)),
            "avg_tokens": _rate(sum(r["tokens_est"] for r in rows), total),
            "categories": cats,
            "questions": rows,
        }


# ---------------------------------------------------------------------------
# Data loading & full run
# ---------------------------------------------------------------------------

def load_locomo(path, *, limit_samples: int = 0) -> list[dict]:
    """Load and validate a LoCoMo JSON dataset.

    Args:
        path: JSON file with a list of samples (``conversation`` with
            ``session_N`` lists + ``qa`` with LoCoMo category ints).
        limit_samples: Keep at most this many samples (0 = all).

    Raises:
        FileNotFoundError: Missing file.
        ValueError: Not a list, or samples missing ``conversation`` /
            ``qa`` / ``session_1``.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"dataset not found: {p}")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{p}: expected JSON list, "
                         f"got {type(data).__name__}")
    for i, sample in enumerate(data):
        if (not isinstance(sample, dict)
                or "conversation" not in sample or "qa" not in sample
                or "session_1" not in sample.get("conversation", {})):
            raise ValueError(
                f"{p}[{i}]: sample must have 'conversation' (with "
                "'session_1') and 'qa'")
    return data[:limit_samples] if limit_samples and limit_samples > 0 \
        else data


def run_locomo(path, *, limit_samples: int = 0,
               max_questions_per_sample: int = 0,
               judge_fn=None, **adapter_kwargs) -> dict:
    """Full LoCoMo run: per-sample graphs, cross-sample aggregation.

    Each sample gets a FRESH adapter + graph (samples are independent
    conversations — cross-sample retrieval would be noise). Category
    counters merge across samples; adversarial questions are scored by
    abstention and excluded from evidence-recall aggregates (see
    ``LoCoMoAdapter.evaluate_sample``).

    Args:
        path: Dataset path (see ``load_locomo``).
        limit_samples: Evaluate at most this many samples (0 = all).
        max_questions_per_sample: Cap per sample (0 = all).
        judge_fn: Optional ``(question, truth, predicted) -> bool``.
        **adapter_kwargs: Forwarded to ``LoCoMoAdapter`` (``use_ppr``,
            ``abstain_entropy``, ``max_context_tokens``, ...).

    Returns:
        Report: ``{"overall_accuracy", "overall_accuracy_no_adversarial",
        "abstention_rate", "session_hit_rate", "turn_hit_rate",
        "context_hit_rate", "avg_tokens", "total_questions",
        "categories", "samples", "config"}``.
    """
    samples = load_locomo(path, limit_samples=limit_samples)
    t0 = time.perf_counter()

    merged: dict[str, dict] = {}
    totals = {"total": 0, "correct": 0, "correct_na": 0, "na": 0,
              "abstained": 0, "session_hits": 0, "turn_hits": 0,
              "context_hits": 0, "tokens": 0}
    sample_reports = []

    for sample in samples:
        adapter = LoCoMoAdapter(**adapter_kwargs)
        stats = adapter.ingest_sample(sample)
        report = adapter.evaluate_sample(
            sample["qa"], judge_fn=judge_fn,
            limit=max_questions_per_sample)
        report["ingest_stats"] = stats
        sample_reports.append(report)

        for name, c in report["categories"].items():
            m = merged.setdefault(name, {
                "category": name, "total": 0, "correct": 0,
                "abstentions": 0, "session_hits": 0, "turn_hits": 0,
                "context_hits": 0, "total_tokens": 0})
            for key in ("total", "correct", "abstentions",
                        "session_hits", "turn_hits", "context_hits",
                        "total_tokens"):
                m[key] += c[key]

        na = [r for r in report["questions"]
              if r["category"] != "adversarial"]
        totals["total"] += report["total_questions"]
        totals["correct"] += sum(r["correct"] for r in report["questions"])
        totals["correct_na"] += sum(r["correct"] for r in na)
        totals["na"] += len(na)
        totals["abstained"] += sum(r["abstained"] for r in report["questions"])
        totals["session_hits"] += sum(r["session_hit"] for r in na)
        totals["turn_hits"] += sum(r["turn_hit"] for r in na)
        totals["context_hits"] += sum(r["context_hit"] for r in na)
        totals["tokens"] += sum(r["tokens_est"] for r in report["questions"])

    n = totals["total"]

    def _rate(num: int, den: int) -> float:
        return num / den if den else 0.0

    return {
        "total_questions": n,
        "overall_accuracy": _rate(totals["correct"], n),
        "overall_accuracy_no_adversarial": _rate(
            totals["correct_na"], totals["na"]),
        "abstention_rate": _rate(totals["abstained"], n),
        "session_hit_rate": _rate(totals["session_hits"], totals["na"]),
        "turn_hit_rate": _rate(totals["turn_hits"], totals["na"]),
        "context_hit_rate": _rate(totals["context_hits"], totals["na"]),
        "avg_tokens": _rate(totals["tokens"], n),
        "categories": merged,
        "samples": [{k: v for k, v in r.items() if k != "questions"}
                    for r in sample_reports],
        "config": {**adapter_kwargs,
                   "limit_samples": limit_samples,
                   "max_questions_per_sample": max_questions_per_sample,
                   "wall_seconds": round(time.perf_counter() - t0, 2)},
    }


# ── CLI entry point ────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="amg LoCoMo memory-quality benchmark (zero-LLM)")
    parser.add_argument("--data", required=True,
                        help="Path to locomo10.json")
    parser.add_argument("--samples", type=int, default=0,
                        help="Max samples (0 = all)")
    parser.add_argument("--max-questions", type=int, default=0,
                        help="Max questions per sample (0 = all)")
    parser.add_argument("--no-ppr", action="store_true",
                        help="Disable PPR multi-hop expansion")
    parser.add_argument("--max-tokens", type=int, default=4000,
                        help="Context token budget")
    parser.add_argument("--abstain-score", type=float, default=1.0,
                        help="Min keyword hits to answer (else abstain)")
    parser.add_argument("--abstain-entropy", type=float, default=0.95,
                        help="Entropy-gate threshold (<0 disables)")
    parser.add_argument("--entropy-weak", type=int, default=1,
                        help="Max keyword hits counted as weak evidence")
    parser.add_argument("--output", default="amg_locomo_results.json",
                        help="Output report path")
    args = parser.parse_args(argv)

    abstain_entropy = (args.abstain_entropy
                       if args.abstain_entropy >= 0 else None)
    report = run_locomo(
        args.data, limit_samples=args.samples,
        max_questions_per_sample=args.max_questions,
        use_ppr=not args.no_ppr,
        max_context_tokens=args.max_tokens,
        abstain_score=args.abstain_score,
        abstain_entropy=abstain_entropy,
        entropy_weak_score=args.entropy_weak)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    n = report["total_questions"]
    print(f"{n} questions · accuracy "
          f"{report['overall_accuracy']:.3f} (all) / "
          f"{report['overall_accuracy_no_adversarial']:.3f} "
          f"(no-adversarial) · abstain {report['abstention_rate']:.1%}")
    print(f"evidence recall: session {report['session_hit_rate']:.3f} · "
          f"turn {report['turn_hit_rate']:.3f} · "
          f"context-answerable {report['context_hit_rate']:.3f} · "
          f"avg {report['avg_tokens']:.0f} tokens/query")
    for name in CATEGORY_NAMES.values():
        c = report["categories"].get(name)
        if c and c["total"]:
            acc = c["correct"] / c["total"]
            extra = (f"abstain {c['abstentions'] / c['total']:.1%}"
                     if name == "adversarial" else
                     f"sess {c['session_hits'] / c['total']:.3f} "
                     f"turn {c['turn_hits'] / c['total']:.3f} "
                     f"ctx {c['context_hits'] / c['total']:.3f}")
            print(f"  {name:<12} n={c['total']:<4} acc={acc:.3f}  {extra}")
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
