"""run_amg.py — GraphRAG-Bench (ICLR 2026) adapter for agent-memory-graph.

Closes Research #064 Gap #4: the full benchmark runner that turns the
prototype (catalyst-research code/2026-08-14/run_amg_grb.py) into a
reusable, testable module.

Pipeline (zero LLM / zero API cost — retrieval-only staged entry):

    corpus + questions (local JSON, GraphRAG-Bench HF layout)
        → index_corpus()        [extract_from_text, rule mode]
        → answer_question()     [graphrag_query + fact_answer edge objects]
        → official prediction schema JSON
        → optional export_graphml()  [indexing_eval input]

Official prediction schema (all frameworks, Evaluation/*.eval consumers):

    {"id", "question", "source", "context", "evidence",
     "question_type", "generated_answer", "ground_truth"}

Rows are kept STRICTLY to these 8 keys — retrieval_eval/generation_eval
parse them; diagnostic info lives in the summary dict instead.

Dataset download (one-time, offline thereafter):

    huggingface-cli download GraphRAG-Bench/GraphRAG-Bench \
        --repo-type dataset --include "Novel/*" --local-dir <data_dir>

<data_dir>/novel.json        → [{"corpus_name", "context"}, ...]
<data_dir>/novel_questions.json → [{"id", "source", "question", "answer",
                                     "question_type", "evidence", ...}, ...]

CLI:

    python run_amg.py --data-dir data/ --out results/amg.json \
        --sample 100 --graphml results/amg.graphml
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from memory_graph import MemoryGraph

__all__ = [
    "load_bench_data",
    "index_corpus",
    "answer_question",
    "run_bench",
    "main",
]

OFFICIAL_SCHEMA_KEYS = [
    "id", "question", "source", "context", "evidence",
    "question_type", "generated_answer", "ground_truth",
]


# ---------------------------------------------------------------------------
# Stage 1: data loading
# ---------------------------------------------------------------------------

def load_bench_data(data_dir, *, corpus_file: str = "novel.json",
                    questions_file: str = "novel_questions.json",
                    sample: int | None = None,
                    seed: int = 42):
    """Load GraphRAG-Bench corpus + questions from a local data directory.

    Args:
        data_dir: Directory containing the two JSON files (path-like).
        corpus_file: Corpus file name (``[{"corpus_name", "context"}]``).
        questions_file: Questions file name
            (``[{"id", "source", "question", "answer", ...}]``).
        sample: If given, deterministically subsample questions to this
            size (``random.Random(seed).sample`` on id-sorted list —
            deterministic across runs, per the Cycle 437 lesson).
        seed: Seed for deterministic sampling.

    Returns:
        ``(corpus, questions)`` lists of dicts.

    Raises:
        FileNotFoundError: If *data_dir* or either JSON file is missing.
        ValueError: If a JSON file is not a list, or corpus/question
            items are missing required keys.
    """
    d = Path(data_dir)
    if not d.is_dir():
        raise FileNotFoundError(f"data_dir not found: {d}")

    corpus_path = d / corpus_file
    questions_path = d / questions_file
    for p in (corpus_path, questions_path):
        if not p.is_file():
            raise FileNotFoundError(f"missing bench file: {p}")

    with open(corpus_path, encoding="utf-8") as f:
        corpus = json.load(f)
    with open(questions_path, encoding="utf-8") as f:
        questions = json.load(f)

    if not isinstance(corpus, list):
        raise ValueError(f"{corpus_path}: expected JSON list, got {type(corpus).__name__}")
    if not isinstance(questions, list):
        raise ValueError(
            f"{questions_path}: expected JSON list, got {type(questions).__name__}")

    for i, doc in enumerate(corpus):
        if "corpus_name" not in doc or "context" not in doc:
            raise ValueError(f"{corpus_path}[{i}]: missing corpus_name/context")
    for i, q in enumerate(questions):
        for key in ("id", "question", "source"):
            if key not in q:
                raise ValueError(f"{questions_path}[{i}]: missing key '{key}'")

    if sample is not None and 0 < sample < len(questions):
        ordered = sorted(questions, key=lambda q: str(q.get("id", "")))
        questions = random.Random(seed).sample(ordered, sample)

    return corpus, questions


# ---------------------------------------------------------------------------
# Stage 2: indexing
# ---------------------------------------------------------------------------

def index_corpus(mg: MemoryGraph, corpus: list[dict]):
    """Index GraphRAG-Bench corpus documents into the KG (rule mode).

    Each document is indexed via :meth:`MemoryGraph.extract_from_text`
    with ``tags=[corpus_name]`` so retrieval can trace nodes back to
    their source document.

    Args:
        mg: Target MemoryGraph instance.
        corpus: List of ``{"corpus_name", "context"}`` dicts.

    Returns:
        Aggregate index stats dict:
        ``{docs, nodes_created, edges_created, sentences, relations,
        corpus_names}``.
    """
    stats = {
        "docs": 0,
        "nodes_created": 0,
        "edges_created": 0,
        "sentences": 0,
        "relations": 0,
        "corpus_names": [],
    }
    for doc in corpus:
        name = doc.get("corpus_name") or f"doc-{stats['docs']}"
        r = mg.extract_from_text(doc.get("context", ""), tags=[name])
        stats["docs"] += 1
        stats["nodes_created"] += r.get("nodes_created", 0)
        stats["edges_created"] += r.get("edges_created", 0)
        stats["sentences"] += r.get("sentences", 0)
        stats["relations"] += len(r.get("relations", []))
        stats["corpus_names"].append(name)
    return stats


# ---------------------------------------------------------------------------
# Stage 3: retrieval + extractive answer
# ---------------------------------------------------------------------------

def answer_question(mg: MemoryGraph, q: dict, *, max_hops: int = 2,
                    top_k: int = 5) -> dict:
    """Answer one bench question, emitting the official prediction row.

    Extractive answer strategy (no LLM, per Research #064 insight #2):

    1. **fact_answer first** — if the question matches a fact cue
       (``"Where is X located?"`` → ``X -located_in→ Y``), return the
       edge OBJECT label(s). Ranking's top-1 node would be the seed
       subject (useless as an answer).
    2. Fall back to the top-ranked answer node label.
    3. Empty string when retrieval yields nothing.

    Args:
        mg: Indexed MemoryGraph.
        q: Question dict (``id``/``question``/``source`` required;
           ``answer``/``question_type``/``evidence`` passed through).
        max_hops: Traversal depth for graphrag_query.
        top_k: Answer-node budget.

    Returns:
        Dict with exactly the 8 official schema keys.
    """
    r = mg.graphrag_query(q.get("question", ""), max_hops=max_hops,
                          top_k=top_k, include_context=True)

    # Fact-answer edge objects beat ranked nodes for fact questions.
    fa = r.get("fact_answer") or {}
    if fa.get("matched") and fa.get("answers"):
        answer = ", ".join(fa["answers"])
    elif r.get("answer_nodes"):
        answer = str(r["answer_nodes"][0].get("label", ""))
    else:
        answer = ""

    return {
        "id": q.get("id"),
        "question": q.get("question"),
        "source": q.get("source"),
        "context": r.get("context", ""),
        "evidence": q.get("evidence", ""),
        "question_type": q.get("question_type", ""),
        "generated_answer": answer,
        "ground_truth": q.get("answer"),
    }


# ---------------------------------------------------------------------------
# Stage 4: full pipeline
# ---------------------------------------------------------------------------

def run_bench(data_dir, out_path=None, *, sample: int | None = None,
              graphml_path=None, max_hops: int = 2, top_k: int = 5,
              seed: int = 42, corpus_file: str = "novel.json",
              questions_file: str = "novel_questions.json",
              quiet: bool = False):
    """Run the full GraphRAG-Bench retrieval-only pipeline.

    Loads bench data, indexes a fresh MemoryGraph, answers every
    question, optionally exports GraphML for indexing_eval, and writes
    the official-schema predictions JSON.

    Args:
        data_dir: Local dataset directory (see :func:`load_bench_data`).
        out_path: Predictions JSON output path (path-like). ``None`` =
            skip file write.
        sample: Optional deterministic question subsample size.
        graphml_path: Optional :meth:`MemoryGraph.export_graphml` target
            for the ``indexing_eval --framework graphml`` module.
        max_hops / top_k: Retrieval parameters.
        seed: Sampling seed.
        corpus_file / questions_file: Bench file names.
        quiet: Suppress progress prints.

    Returns:
        Summary dict:
        ``{questions, predictions, extractive_hits, hit_rate,
        per_question_type, index, out_path, graphml_path}``.
    """
    corpus, questions = load_bench_data(
        data_dir, corpus_file=corpus_file, questions_file=questions_file,
        sample=sample, seed=seed)

    mg = MemoryGraph()
    index_stats = index_corpus(mg, corpus)
    if not quiet:
        print(f"[index] docs={index_stats['docs']} "
              f"nodes={index_stats['nodes_created']} "
              f"edges={index_stats['edges_created']}")

    predictions = [
        answer_question(mg, q, max_hops=max_hops, top_k=top_k)
        for q in questions
    ]

    # Extractive scoring: substring hit of ground_truth in the answer
    # (case-insensitive) — the retrieval-only proxy metric from the
    # Research #064 prototype. LLM-judged ACC comes from generation_eval.
    hits = 0
    per_type: dict[str, dict] = {}
    for row in predictions:
        gt = str(row.get("ground_truth") or "").lower().strip()
        ans = str(row.get("generated_answer") or "").lower()
        row_hit = bool(gt) and gt in ans
        hits += row_hit
        bucket = per_type.setdefault(
            row.get("question_type") or "unknown", {"n": 0, "hits": 0})
        bucket["n"] += 1
        bucket["hits"] += row_hit

    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False)
        if not quiet:
            print(f"[out] predictions → {out}")

    graphml_out = None
    if graphml_path is not None:
        graphml_out = mg.export_graphml(graphml_path)
        if not quiet:
            print(f"[out] graphml → {graphml_path} "
                  f"({graphml_out.get('nodes', '?')} nodes, "
                  f"{graphml_out.get('edges', '?')} edges)")

    n = len(predictions)
    if not quiet:
        print(f"[done] questions={n} extractive_hits={hits} "
              f"hit_rate={hits / n:.2%}" if n else "[done] no questions")

    return {
        "questions": n,
        "predictions": predictions,
        "extractive_hits": hits,
        "hit_rate": (hits / n) if n else 0.0,
        "per_question_type": per_type,
        "index": index_stats,
        "out_path": str(out_path) if out_path is not None else None,
        "graphml_path": str(graphml_path) if graphml_path is not None else None,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        prog="run_amg",
        description="agent-memory-graph → GraphRAG-Bench (ICLR 2026) adapter")
    parser.add_argument("--data-dir", required=True,
                        help="local dir with novel.json + novel_questions.json")
    parser.add_argument("--out", default=None,
                        help="predictions JSON output path")
    parser.add_argument("--sample", type=int, default=None,
                        help="deterministic question subsample size")
    parser.add_argument("--graphml", default=None,
                        help="export KG GraphML for indexing_eval")
    parser.add_argument("--max-hops", type=int, default=2)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    summary = run_bench(
        args.data_dir, args.out, sample=args.sample,
        graphml_path=args.graphml, max_hops=args.max_hops,
        top_k=args.top_k, seed=args.seed)
    print(f"[summary] {summary['questions']} questions, "
          f"hit_rate={summary['hit_rate']:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
