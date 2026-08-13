# Agent Memory Graph 🧠

> A graph-native memory engine for AI agents — 53,900+ lines, 565+ API methods, 8,794 tests, zero dependencies.
>
> **291st consecutive day of iteration** 🏆

**Zero dependencies** — pure Python stdlib + sqlite3. `sqlite-vec` optional for vector search.

## Why?

Agents wake up fresh each session. Files work, but they're flat. A memory graph lets agents:
- Store **entities** (people, projects, concepts) as graph nodes
- Create **typed relations** between them as weighted edges
- **Query** by label, kind, tag, semantic similarity, or graph traversal
- **Decay & consolidate** memories automatically using cognitive science models
- **Track evolution** — bi-temporal versioning, snapshots, rollback
- **Analyze structure** — 57+ graph metrics + 40+ entropy/spectral tools
- **Classify graphs** — 25-API classification suite (single-match → ensemble → meta → evaluation → optimization → explainability)
- **Reason over memory** — multi-hop reasoning, PPR, spreading activation (5-member family)
- **Secure memory** — OWASP ASI06 security suite (6 APIs: trust score, quarantine, selective repair, audit, laundering detection, dashboard)
- **Observe operations** — OTel GenAI telemetry with 5 context managers
- **Serve via MCP** — 16-tool MCP server for any MCP client
- **Manage retrieval quality** — 5-API family: audit → explain → rerank → compare → trend (complete lifecycle)
- **Track bi-temporal queries** — 3-mode point-in-time queries (knowledge/truth/certain)
- **Forecast forgetting** — non-destructive Ebbinghaus decay prediction with risk zones
- **Analyze temporal dynamics** — changepoints/stability/velocity trilogy
- **Dual-process writing** — FastAppendQueue: System-1 (hot O(1) append) + System-2 (cold async consolidation)
- **GraphRAG pipeline** — extract_from_text → graphrag_query → graphrag_explain → coverage_report (zero-dependency KG construction + retrieval)
- **Track knowledge freshness** — FAMA-aware graph-level diagnostics with 5 time buckets

---

## Quick Start

```python
from memory_graph import MemoryGraph

mg = MemoryGraph("agent_memory.db")  # or ":memory:" for testing

# Store entities (returns Node objects)
alice = mg.add("Alice", kind="person", data={"skill": "backend"}, tags=["team"])
bob = mg.add("Bob", kind="person", data={"skill": "frontend"}, tags=["team"])
proj = mg.add("ProjectX", kind="project", data={"status": "active"})

# Link by ID or by label
mg.link(alice.id, proj.id, "leads")
mg.link_by_label("Bob", "ProjectX", "contributes_to")

# Search
results = mg.recall("Alice")          # keyword search → ranked Nodes
neighbors = mg.neighbors(alice.id, depth=1)  # 1-hop graph traversal

# Graph analytics
pr = mg.pagerank()                    # → {node_id: score}
density = mg.graph_density()          # → float
h = mg.von_neumann_entropy()          # spectral entropy of graph structure

# Memory lifecycle
mg.decay_all()                        # apply forgetting curve
mg.consolidate_memory(threshold=0.8)  # merge similar memories

# Export
print(mg.to_markdown())               # human-readable summary
```

---

## Feature Domains

| Domain | Methods | Highlights |
|--------|---------|------------|
| **CRUD** | 12 | `add`, `update_node`, `link`, `delete_node`, `touch`, `clone_node` |
| **Search** | 33 | `recall`, `search_unified`, `search_bm25`, `search_hybrid`, `search_graphrag`, `grep` |
| **Graph Metrics** | 57+ | `pagerank`, `betweenness_centrality`, `community_detect`, `clustering_coefficient`, `modularity` |
| **Spectral / Entropy** | 40+ | `von_neumann_entropy`, `FINGEREntropy`, `spectral_entropy_profile`, `entropy_fingerprint`, `semantic_divergence`, `divergence_scan`, `entropy_scan`, `entropy_explain` |
| **Graph Classification** | 25 | 3 base methods (degree/spectral/fingerprint) × ensemble (RRF/Bayesian/weighted/k-NN) + rejection + consensus + LOOCV + calibration + optimization + confusion_explain + counterfactual + confidence_interval |
| **Spreading Activation** | 5 | `spreading_activation` (ACT-R base), `activation_trace` (explainable), `competitive_spreading` (multi-seed), `temporal_spreading` (Ebbinghaus decay), `activation_diff` (comparative) |
| **Reasoning** | 3 | `multi_hop_reason` (PPR + BFS evidence), `personalized_pagerank`, `enrich_node` (A-MEM retroactive) |
| **Temporal Hierarchy** | 1 | `SummaryTree` — 5-level (segment→session→day→week→profile) |
| **Security (OWASP ASI06)** | 6 | `trust_score`, `memory_quarantine`, `selective_repair`, `memory_audit_report`, `detect_provenance_laundering`, `security_dashboard` |
| **Code-Aware** | 3 | `explainCode`, `recordCodeDecision`, `impactAnalysis` |
| **Provenance / Lineage** | 4 | `propagate_correction`, `trace_derivation`, `trace_derivation_impact`, `derivation_lineage_report` |
| **Memory Lifecycle** | 24+ | `forgetting_curve`, `fifa_forget`, `consolidate_memory`, `sleep_consolidate`, `strategic_forget` + adaptive forgetting (6 APIs) |
| **Workflow / Patterns** | 14 | `add_workflow`, `retrieve_workflows`, `workflow_success_patterns`, `workflow_compose` |
| **Temporal / Versioning** | 31 | `evolve`, `temporal_snapshot`, `query_as_of`, `temporal_diff`, `supersede`, `immutable_retrieve`, `revert_evolution` |
| **Embedding / Vector** | 19 | `add_embedding`, `search_similar`, `train_kge`, `kge_score` |
| **Entity Resolution** | 8 | `EntityResolver` — alias detection, merge, split, cluster dedup |
| **Diagnostics** | 5+ | `graph_health_score`, `entropy_dashboard`, `get_operation_history`, `streaming_health`, `graph_digest` |
| **Retrieval Quality** | 5 | `retrieval_quality_audit` (diversity/coverage/relevance/redundancy), `retrieval_quality_explain` (per-node diagnostic), `retrieval_quality_rerank` (Greedy Marginal Contribution), `retrieval_quality_compare` (multi-set A/B), `retrieval_quality_trend` (N-snapshot regression + change points) |
| **Attention Management** | 2 | `attention_distribution` (Gini + Shannon + zones + hotspots/blindspots), `attention_rebalance_plan` (refresh/boost/diversify/consolidate/forget + Gini delta) |
| **Temporal Analysis** | 3 | `temporal_changepoints` (burst detection + outliers), `temporal_stability_score` (growth × retention × changepoint density), `temporal_velocity` (creation/supersession rates + trend slope) |
| **Bi-Temporal Queries** | 5 | `edge_record`, `edge_supersede`, `bitemporal_as_of` (3-mode: knowledge/truth/certain), `knowledge_diff`, `supersedence_chain` |
| **Forgetting Forecast** | 1 | `forgetting_forecast` — non-destructive Ebbinghaus decay projection with 4 risk zones |
| **Link Prediction** | 1 | `link_prediction` — Adamic-Adar / Preferential Attachment / Common Neighbors |
| **Serialization** | 24 | `export_json`, `to_markdown`, `serialize_dot`, `serialize_graphml`, `serialize_cytoscape` |
| **Telemetry** | 5 | `enable_telemetry()` auto-instrumentation + 5 OTel context managers |
| **Dual-Process Write** | 8 | `FastAppendQueue`: System-1 buffer append/search + System-2 flush/consolidate, peek, health, E2E integration |
| **GraphRAG** | 4 | `extract_from_text` (rule-based KG construction), `graphrag_query` (subgraph retrieval), `graphrag_explain` (per-query diagnostic), `graphrag_coverage_report` (global health) |
| **Knowledge Freshness** | 1 | `knowledge_freshness_report` — FAMA-aware 5-bucket distribution + weighted score + recommendations |
| **MCP Server** | 16 | remember/recall/relate/ask/lookup/neighbors/forget/stats/timeline/health + entropy/reason/snapshot/code_explain/quarantine/security |

---

## Tutorial

### Step 1: Create a graph

```python
from memory_graph import MemoryGraph

mg = MemoryGraph(":memory:")  # in-memory for testing
# mg = MemoryGraph("memory.db")  # persistent on disk
```

### Step 2: Build a knowledge base

```python
# Add nodes — each returns a Node with auto-generated short ID
alice = mg.add("Alice", kind="person", data={"skill": "python"})
bob = mg.add("Bob", kind="person", data={"skill": "rust"})
proj = mg.add("ProjectX", kind="project", data={"status": "active"})

# Add tags for categorization
mg.add_tag(alice.id, "backend")
mg.add_tag(bob.id, "backend")
mg.add_tag(proj.id, "q1-goal")

# Create edges — typed, weighted, directional
mg.link(alice.id, proj.id, "leads", weight=1.0)
mg.link(bob.id, proj.id, "contributes_to", weight=0.8)
```

### Step 3: Query and traverse

```python
# Keyword search (fuzzy match on labels + data)
results = mg.recall("python")
# → [Node(label='Alice', ...)]

# Unified search (combines BM25 + graph + tag routing)
hits = mg.search_unified("backend developer", limit=5)

# Graph traversal — N-hop neighbors
teammates = mg.neighbors(alice.id, depth=2)

# Shortest path
path = mg.shortest_path(alice.id, bob.id)

# Filter by kind or tag
people = mg.find_by_kind("person")
backend = mg.search_by_tag("backend")
```

### Step 4: Graph analytics

```python
# Centrality — who's most influential?
pr = mg.pagerank(damping=0.85)
ev = mg.eigenvector_centrality()
bc = mg.betweenness_centrality()

# Structure
print(f"Density: {mg.graph_density():.3f}")
print(f"Clustering: {mg.clustering_coefficient(alice.id):.3f}")
print(f"Diameter: {mg.graph_diameter()}")

# Communities
communities = mg.community_detect()
print(f"Detected {len(communities)} communities")

# Spectral analysis
vn = mg.von_neumann_entropy()       # graph structural entropy
profile = mg.spectral_entropy_profile()  # full spectral breakdown
```

### Step 5: Memory lifecycle

```python
# Memories decay over time (Ebbinghaus-style forgetting curve)
mg.decay_all()

# Strategic forgetting — remove low-value nodes
mg.strategic_forget(strategy="relevance", max_remove=10)

# Consolidation — merge duplicate/similar memories
mg.consolidate_memory(threshold=0.85)

# Sleep consolidation — deep offline processing
mg.sleep_consolidate()

# Check memory health
report = mg.memory_health_score()
```

### Pattern: Using with an AI Agent

```python
class MemoryAwareAgent:
    def __init__(self, db_path="agent_memory.db"):
        self.memory = MemoryGraph(db_path)

    def learn(self, subject, obj, relation="related_to", **data):
        """Store a fact as a graph edge."""
        s = self.memory.add(subject, kind="entity", data=data)
        o = self.memory.add(obj, kind="entity")
        self.memory.link(s.id, o.id, relation)

    def recall_context(self, topic, depth=2):
        """Get subgraph around a topic for prompt injection."""
        hits = self.memory.recall(topic)
        if not hits:
            return ""
        neighbors = self.memory.neighbors(hits[0].id, depth=depth)
        return self.memory.to_markdown()

    def maintenance(self):
        """Periodic cleanup — call between sessions."""
        self.memory.decay_all()
        self.memory.consolidate_memory(threshold=0.85)
        self.memory.strategic_forget(max_remove=50)
```

---

## API Reference

### Core CRUD

| Method | Signature | Description |
|--------|-----------|-------------|
| `add` | `(label, kind='fact', data=None, tags=None) → Node` | Create a node |
| `get_node` | `(node_id) → Node \| None` | Get by ID |
| `update_node` | `(node_id, label=None, kind=None, data=None, ...)` | Update fields |
| `delete_node` | `(node_id) → bool` | Remove node + edges |
| `link` | `(source_id, target_id, relation, weight=1.0)` | Create edge |
| `link_by_label` | `(source_label, target_label, relation, weight=1.0)` | Edge by label |
| `unlink` | `(source_id, target_id, relation=None)` | Remove edge |
| `touch` | `(node_id)` | Boost access metrics |
| `clone_node` | `(node_id, new_label)` | Duplicate a node |
| `rename_node` | `(node_id, new_label)` | Rename |
| `has_node` | `(node_id) → bool` | Existence check |

### Search

| Method | Description |
|--------|-------------|
| `recall(query, limit=5)` | Keyword search → ranked Nodes |
| `search_unified(query, limit=10)` | BM25 + graph + tag fusion |
| `search_bm25(query, limit=10)` | BM25 ranking |
| `search_hybrid(query, limit=10)` | Keyword + vector |
| `search_graphrag(query, limit=10)` | Graph RAG retrieval |
| `find_by_kind(kind)` | Filter by node kind |
| `search_by_label(pattern)` | Regex label match |
| `search_by_tag(tag)` | Tag-based filter |
| `grep(pattern, limit=100)` | Raw regex across all data |

### Graph Algorithms

| Method | Description |
|--------|-------------|
| `pagerank(damping=0.85)` | PageRank centrality |
| `eigenvector_centrality()` | Eigenvector centrality |
| `betweenness_centrality()` | Betweenness centrality |
| `closeness_centrality()` | Closeness centrality |
| `community_detect()` | Label propagation |
| `shortest_path(source, target)` | BFS shortest path |
| `clustering_coefficient(node_id)` | Local clustering |
| `k_core(k)` | K-core decomposition |
| `maximal_cliques()` | All maximal cliques |
| `graph_density()` | Edge / max-possible ratio |
| `graph_diameter()` | Longest shortest path |

### Spectral & Information Theory

| Method | Description |
|--------|-------------|
| `von_neumann_entropy()` | Graph structural entropy (Laplacian eigenvalues) |
| `spectral_entropy_profile()` | Full spectral breakdown (gap, radius, complexity) |
| `spectral_entropy_contribution()` | Leave-one-out VNE per node — spectral importance |
| `entropy_stability_spectral()` | Monte Carlo VNE stability under perturbation |
| `entropy_anomaly_detect()` | Spectral anomaly detection (node-level scores) |
| `ego_entropy_profile(node_id, radius)` | Ego-local Shannon entropy — O(n·k²) |
| `entropy_fingerprint()` | Compact 12-index entropy feature vector |
| `fingerprint_distance(other)` | L2 distance between two graph fingerprints |
| `graph_type_indicator()` | Topology classification (7 types) |
| `node_entropy_importance()` | Unified per-node importance (contribution + ego + anomaly) |
| `spectral_radius()` | Largest eigenvalue of adjacency matrix |
| `fiedler_vector()` | Algebraic connectivity (2nd smallest Laplacian eigenvector) |
| `semantic_divergence(other_graph)` | JSD/KL/CE between two graphs |
| `divergence_scan(other_graph)` | Multi-resolution divergence analysis |
| `graph_entropy()` | Shannon degree-distribution entropy |
| `entropy_dashboard()` | Unified one-call entropy overview (all indices) |

### Memory Lifecycle

| Method | Description |
|--------|-------------|
| `forgetting_curve(...)` | Ebbinghaus decay model |
| `decay_all()` | Apply time-based decay |
| `fifa_forget(...)` | FIFO + Frequency-Aware forgetting |
| `consolidate_memory(threshold)` | Merge similar nodes |
| `strategic_forget(...)` | Value-aware pruning |
| `sleep_consolidate()` | Deep offline processing |
| `retention_score(node_id)` | Individual memory strength |
| `memory_health_score()` | Global memory quality metric |

### Temporal & Versioning

| Method | Description |
|--------|-------------|
| `evolve(...)` | Record a graph transformation |
| `evolution_history(node_id)` | Change log |
| `revert_evolution(...)` | Rollback to prior state |
| `temporal_snapshot(timestamp)` | Point-in-time graph view |
| `query_as_of(timestamp, query)` | Bi-temporal snapshot + query (Engram pattern) |
| `temporal_diff(t1, t2)` | Diff between two temporal snapshots |
| `supersede(node_id, replacement_id)` | Mark node as superseded |
| `immutable_retrieve(node_id)` | Append-only retrieval |
| `snapshot()` | Full graph snapshot |
| `restore(snapshot_data)` | Restore from snapshot |

### Classification

Multi-method graph classification — compare reference graphs using different fusion strategies.

| Method | Description |
|--------|-------------|
| `rrf_classification(candidate, references)` | Reciprocal Rank Fusion — rank-based aggregation |
| `bayesian_classification(candidate, references)` | Confidence-weighted adaptive ensemble |
| `knn_classification(candidate, references, k)` | k-nearest reference with distance-weighted voting |
| `weighted_average_classification(...)` | Explicit weight control over modalities |
| `classification_compare(candidate, references)` | Multi-method consensus report |

### Diagnostics

| Method | Description |
|--------|-------------|
| `graph_health_score()` | Composite 0–100 health metric (redundancy, staleness, connectivity) |
| `entropy_dashboard()` | Unified entropy overview in one call |
| `get_operation_history(node_id)` | MemOps-compatible audit trail |

### Serialization

| Method | Description |
|--------|-------------|
| `export_json()` | Full graph as JSON |
| `to_markdown()` | Human-readable summary |
| `serialize_dot()` | Graphviz DOT format |
| `serialize_graphml()` | GraphML XML |
| `serialize_cytoscape()` | Cytoscape.js JSON |
| `to_adjacency_list()` | Adjacency list |
| `to_adjacency_matrix()` | Adjacency matrix |

---

## Information Theory Toolkit (Cycles 306–316)

The graph's spectral toolkit evolved through three phases:

### Phase 1: Foundation (Cycles 306–309)

| Cycle | Method | Core Idea |
|-------|--------|----------|
| 306 | `entropy_contribution()` | Leave-one-out degree entropy — which nodes matter most? |
| 307 | `entropy_stability()` | Monte Carlo perturbation — how resilient is the structure? |
| 308 | `spectral_divergence()` | Laplacian eigenvalue JSD/KL/CE — graph shape comparison |
| 309 | `spectral_divergence_scan()` | Multi-resolution — at which frequency do two graphs differ? |

### Phase 2: Spectral & Ego-Local (Cycles 310–314)

| Cycle | Method | Core Idea |
|-------|--------|----------|
| 310 | `spectral_entropy_contribution()` | Leave-one-out **von Neumann** entropy per node |
| 311 | `entropy_stability_spectral()` | Monte Carlo VNE stability (remove/rewire modes) |
| 312 | `entropy_anomaly_detect()` | Spectral anomaly scores — find structural outliers |
| 313 | `ego_entropy_profile()` | O(n·k²) ego-local entropy — VNEstruct-inspired |
| 314 | `entropy_fingerprint()` + `fingerprint_distance()` | 12-index compact feature vector for fast similarity |

### Phase 3: Classification & Topology (Cycles 315–316)

| Cycle | Method | Core Idea |
|-------|--------|----------|
| 315 | `graph_type_indicator()` | Heuristic topology: complete / star / path / cycle / tree / random / scale-free |
| 316 | `node_entropy_importance()` | Unified ranking: fuses contribution + ego + anomaly |

### Phase 4: Graph Classification (Cycles 326–330)

| Cycle | Method | Core Idea |
|-------|--------|----------|
| 326 | `rrf_classification()` | Reciprocal Rank Fusion — rank-based multi-modal aggregation |
| 327 | `bayesian_classification()` | Confidence-weighted adaptive ensemble |
| 328 | `classification_compare()` | Multi-method consensus report |
| 329 | `knn_classification()` | k-nearest reference with distance-weighted voting |
| 330 | `weighted_average_classification()` | Explicit weight control over all 3 modalities |

---

## Advanced API Families

### Spreading Activation Family (5 APIs)

Cognitive-model-inspired retrieval based on Anderson's ACT-R. Fire-once BFS, threshold-gated, decay per hop.

```python
# Base: spreading activation from seed nodes
results = mg.spreading_activation(seed_ids=[alice.id], threshold=0.1, decay=0.5, max_hops=3)

# Explainable: wave-by-wave firing log + path reconstruction
trace = mg.activation_trace(seed_ids=[alice.id], threshold=0.1)
# trace.wave_log, trace.propagation_tree, trace.bottlenecks, trace.dead_ends

# Competitive: multi-seed lateral inhibition (Anderson & Reder 1999)
comp = mg.competitive_spreading(seed_sets={'team_a': [alice.id], 'team_b': [bob.id]})
# comp.territory_map, comp.contested_nodes, comp.influence_balance

# Temporal: Ebbinghaus time-decay spreading
temp = mg.temporal_spreading(seed_ids=[alice.id], decay_mode='multiply')
# temp.fresh_nodes, temp.stale_nodes, temp.temporal_decay_impact

# Comparative: delta analysis between any two activation runs
diff = mg.activation_diff(results, trace, activation_key='fired_nodes')
# diff.node_deltas, diff.rank_changes, diff.spearman_rho, diff.jaccard_overlap, diff.biggest_mover
```

### Graph Classification Suite (25 APIs)

Identify graph topology without training data — powered by entropy fingerprints.

```python
# Single-method classification
result = mg.graph_classification(candidate, references)
result = mg.spectral_classification(candidate, references)
result = mg.fingerprint_classification(candidate, references)

# Ensemble fusion
result = mg.rrf_classification(candidate, references)           # parameter-free
result = mg.bayesian_classification(candidate, references)      # adaptive
result = mg.weighted_average_classification(candidate, refs, weights={...})
result = mg.knn_classification(candidate, references, k=3)       # voting

# Meta-classification
report = mg.classification_compare(candidate, references)       # multi-method
result = mg.max_confidence_classification(candidate, references) # conviction

# Statistical validation
loocv = mg.classification_loocv(references)                      # leave-one-out CV
cal = mg.classification_calibrate(references, method='degree')   # temperature scaling
opt = mg.optimize_reference_set(references)                     # ENN + CCCD
bench = mg.classification_benchmark(references, queries)         # standardized eval
conf = mg.classification_confusion_explain(query, references)    # per-modality
cf = mg.classification_counterfactual(query, references)         # flip analysis
ci = mg.classification_confidence_interval(query, references)    # bootstrap CI

# Rejection + noise robustness
result = mg.classify_with_rejection(candidate, references, threshold=0.3)
result = mg.classification_noise_adaptive(candidate, references) # auto-method
result = mg.classification_consensus(candidate, references)      # majority vote
report = mg.classification_report(references, queries, labels)   # full report
```

### OWASP ASI06 Security Suite (6 APIs)

First agent memory library with infrastructure for all 5 OWASP ASI06 defense layers.

```python
# Trust scoring (L3) — composite from source + age + verification + anomaly
score = mg.trust_score(node_id)

# Quarantine (L1+L2) — shadow memory for low-trust writes
mg.memory_quarantine(entry, reason="unverified source")

# Selective repair (L5) — surgical removal via dependency edges
mg.selective_repair([poisoned_node_id])

# Audit report (L5) — forensic timeline
report = mg.memory_audit_report(start_time, end_time)

# Laundering detection (L2) — compression pipeline toxicity check
mg.detect_provenance_laundering(transform, known_patterns)

# Dashboard — one-call OWASP ASI06 overview
dash = mg.security_dashboard()
```

### Streaming & Incremental Entropy

Real-time entropy tracking without full eigendecomposition.

```python
from memory_graph import StreamingGraph, FINGEREntropy

# StreamingGraph: real-time FINGER tracking on every add/link/delete
sg = StreamingGraph()
sg.add(1, "Alice", kind="person")
sg.add(2, "Bob", kind="person")
sg.link(1, 2, "knows")
# sg.current_Q  — quadratic proxy (O(1) health signal)
# sg.anomaly_log — unusual structural changes

report = sg.streaming_report()
```

### Retrieval Quality Family (4 APIs)

Complete lifecycle: **diagnose → explain → correct → compare**.

```python
# 1. Audit: evaluate retrieval result quality
audit = mg.retrieval_quality_audit(
    query="machine learning",
    results=mg.recall("machine learning", limit=20)
)
# audit.diversity_score, audit.coverage_score, audit.relevance_score,
# audit.redundancy_score, audit.qa_score (composite)

# 2. Explain: per-node diagnostic (why each node is good/bad)
explain = mg.retrieval_quality_explain(
    query="machine learning",
    results=mg.recall("machine learning", limit=20)
)
# explain.nodes[0].freshness, .interference, .diversity_gain, .marginal_coverage
# explain.nodes[0].suggestion  (human-readable)

# 3. Rerank: fix quality issues via Greedy Marginal Contribution
reranked = mg.retrieval_quality_rerank(
    query="machine learning",
    results=mg.recall("machine learning", limit=20),
    weights={"coverage": 0.3, "diversity": 0.3, "freshness": 0.2, "redundancy": 0.2}
)
# reranked.reranked_nodes, reranked.audit_before, reranked.audit_after, reranked.improvement_deltas

# 4. Compare: A/B test multiple retrieval strategies
comparison = mg.retrieval_quality_compare(
    query="machine learning",
    result_sets={
        "keyword": mg.recall("machine learning", limit=10),
        "hybrid": mg.search_hybrid("machine learning", limit=10),
        "graphrag": mg.search_graphrag("machine learning", limit=10)
    }
)
# comparison.pairwise_jaccard, comparison.unique_nodes, comparison.winners, comparison.agreement
```

### Bi-Temporal Query APIs (5 APIs)

Three-mode point-in-time queries — what the agent knew, what was true, what was certain.

```python
import time

# Record a fact with both valid_time and transaction_time
mg.edge_record(alice.id, "works_at", "Acme Corp",
               valid_time=time.time() - 86400,  # started yesterday
               source="hr_system")

# Later, Alice moves to Google — supersede (non-destructive)
mg.edge_supersede(alice.id, "works_at", "Acme Corp",
                  new_value="Google Corp",
                  supersede_time=time.time())

# Query at a specific time — 3 modes
knowledge = mg.bitemporal_as_of(timestamp=time.time() - 3600, mode="knowledge")
# → "Acme Corp" (what the agent believed 1h ago)

truth = mg.bitemporal_as_of(timestamp=time.time(), mode="truth")
# → "Google Corp" (what's objectively true now)

certain = mg.bitemporal_as_of(timestamp=time.time(), mode="certain")
# → intersection of knowledge and truth

# Trace the full supersession chain
chain = mg.supersedence_chain(alice.id, "works_at")
# chain = [Acme Corp → Google Corp]

# Diff between two time points
diff = mg.knowledge_diff(t1=time.time() - 86400, t2=time.time())
# diff.added, diff.removed, diff.superseded
```

### Forgetting Forecast

Non-destructive Ebbinghaus decay projection — predict which memories will fade.

```python
# Forecast: which nodes are at risk of being forgotten?
forecast = mg.forgetting_forecast(
    node_ids=None,  # None = all nodes
    horizon_hours=168  # 1 week ahead
)
# forecast.risk_zones: {critical: [...], high: [...], medium: [...], low: [...]}
# forecast.population_summary: {median_ttt_hours, earliest_crossing, at_risk_count}
# Non-destructive: does NOT modify weights (unlike forgetting_curve())
```

### Temporal Analysis Trilogy

```python
# 1. Changepoints: when did the graph structure shift?
cp = mg.temporal_changepoints(bucket_size="day")
# cp.changepoints, cp.bursts, cp.outliers

# 2. Stability: how stable is the knowledge graph?
stability = mg.temporal_stability_score()
# stability.score (0-1), stability.tier (stable/healthy/moderate/fragile/unstable)

# 3. Velocity: how fast is knowledge changing?
vel = mg.temporal_velocity(bucket_size="day", window_days=7)
# vel.creation_rate, vel.supersession_rate, vel.trend (accelerating/decelerating/steady)
```

### Retrieval Quality Trend (Cycle 416)

Temporal trend analysis across N audit snapshots — completes the retrieval quality lifecycle:
audit → explain → rerank → compare → **trend**.

```python
# Collect daily quality snapshots
snapshots = [mg.retrieval_quality_audit(results) for results in daily_results]

trend = mg.retrieval_quality_trend(snapshots)
# trend.directions: {diversity: 'improving', coverage: 'degrading', ...}
# trend.slopes: {diversity: +0.03, coverage: -0.01, ...}
# trend.change_points: dimensions where sudden shifts occurred
# trend.volatility: coefficient of variation per dimension
```

### Knowledge Durability (Cycles 417-419)

Estimate how long memories last and which are going stale:

```python
# Per-node half-life: time for weight to halve
hl = mg.memory_half_life('concept:react')
# hl.half_life_hours, hl.category ('durable'|'stable'|'fragile'|'ephemeral')

# Population-level batch analysis
batch = mg.batch_half_life()
# batch.mean, batch.median, batch.category_distribution
# batch.top5_durable, batch.bottom5_fragile

# Population staleness report
report = mg.staleness_report()
# report.distribution: {fresh: 45, aging: 30, stale: 15, critical: 5}
# report.most_stale: [(node_id, age_days), ...]
# report.recommendations: ['Consider consolidating 15 stale nodes...']
```

### Experience Compression Spectrum: L2→L3 Rules (Cycles 420-424)

The highest compression level — extract declarative rules from procedural skills.
Full lifecycle: **extract_rules → rule_conflict_detect → rule_apply → rule_explain**.

```python
# L1→L2 already existed: compress_to_skill()
mg.compress_to_skill(['event:bug_fix_1', 'event:bug_fix_2'], name='fix-null-pointer')

# L2→L3: Extract rules from skills
rules = mg.extract_rules(['skill:fix-null-pointer', 'skill:fix-race-condition'],
                         min_confidence=0.7)
# Each rule: {action, constraint, polarity: 'positive'|'negative', confidence}
# Negative constraints ("never assume non-null") are separated from
# positive rules ("always check before dereference")

# Check for contradictions in your rule set
conflicts = mg.rule_conflict_detect()
# conflicts.contradictions: rules that directly oppose each other
# conflicts.overlaps: redundant rules that may need merging

# Apply rules at runtime — match against new situations
matches = mg.rule_apply('event:new_bug_report', top_k=5)
# matches: [{rule_id, score, polarity: 'positive'|'negative'}, ...]

# Explain WHY a rule matched (or didn't)
explanation = mg.rule_explain('event:new_bug_report', 'rule:always-check-null')
# explanation.keyword_overlap: which keywords matched
# explanation.jaccard_contribution: per-keyword Jaccard scores
# explanation.suggestions: human-readable next steps
```

### Compression Spectrum Report

```python
report = mg.compression_spectrum_report()
# L0 (raw traces): 1,250 nodes (62%)
# L1 (episodes):   450 nodes (22%)
# L2 (skills):      85 nodes (4%)
# L3 (rules):       12 nodes (0.6%)
# Weighted compression ratio: 8.3x
# Dominant level: L0 (raw traces dominate — consider L0→L1 compression)
# Recommendations: actionable next steps for each compression transition
```

### Dual-Process Write Path: FastAppendQueue (Cycles 425-427)

Inspired by Engram's System-1/System-2 split (83.6% vs 73.2% accuracy). Hot path is O(1) append; cold path flushes with full graph integration.

```python
from memory_graph import FastAppendQueue

faq = FastAppendQueue(mg, auto_flush_threshold=100)

# System-1: hot path — O(1) append, no graph ops
faq.append("User asked about React hooks", kind="interaction")
faq.append("Resolved null pointer in auth flow", kind="event")

# System-1: keyword search on buffer (no graph traversal)
hits = faq.search("React")

# Peek without removal
recent = faq.peek(5)

# System-2: cold path — flush to graph with dedup + link-by-kind/tags
faq.flush()  # nodes enter the full graph

# Combined flush + consolidation
faq.flush_and_consolidate(strategy="nrem")

# Diagnostics
print(faq.status())         # pending count, capacity, flush history
print(faq.is_healthy())     # issue detection
print(faq.peak_buffer_size())
```

### Knowledge Freshness Report (Cycle 426)

Graph-level freshness analysis based on FAMA research (stale memory penalized 15-43 points).

```python
report = mg.knowledge_freshness_report()
# report.buckets: {fresh: 45, recent: 30, aging: 15, stale: 8, decayed: 2}
# report.weighted_score: 72.3 (0-100)
# report.per_kind: {"person": 85.2, "project": 60.1, ...}
# report.stalest_nodes: [(node_id, age_days), ...]
# report.freshest_nodes: [(node_id, age_days), ...]
# report.recommendations: ["15 nodes in stale bucket — consider consolidation", ...]
```

### GraphRAG Pipeline (Cycles 428-431)

Zero-dependency KG construction + retrieval — complete extract → query → explain → diagnose lifecycle.

```python
# 1. Extract: build a knowledge graph from raw text
result = mg.extract_from_text(
    "Alice works_at Acme Corp. She created the auth module. "
    "Bob is_a developer. The auth module is part_of the backend."
)
# result.nodes_created, result.edges_created
# result.entities: ['Alice', 'Acme Corp', 'auth module', 'Bob', 'backend']
# result.relations: [('Alice', 'works_at', 'Acme Corp'), ...]
# 7 relation patterns: is_a, works_at, created, located_in, has, part_of, built

# 2. Query: natural-language subgraph retrieval
answer = mg.graphrag_query("Who created the auth module?", max_hops=2, top_k=5)
# answer.answer_nodes: ranked nodes by keyword_score × centrality × hop_penalty
# answer.context: formatted string for LLM prompt injection

# 3. Explain: per-query diagnostic
explanation = mg.graphrag_explain("Who created the auth module?", mg.graphrag_query(...))
# explanation.keyword_breakdown: matched/unmatched keywords with match types
# explanation.node_scores: per-node score decomposition
# explanation.traversal_paths: seed → answer node paths
# explanation.suggestions: human-readable improvement tips

# 4. Coverage Report: global KG retrieval health
coverage = mg.graphrag_coverage_report()
# coverage.label_coverage, coverage.tag_coverage, coverage.avg_tags_per_node
# coverage.orphan_rate, coverage.degree_stats
# coverage.matchability_tiers: {high: 40, medium: 25, low: 35}
# coverage.sparse_nodes: nodes nearly invisible to retrieval
# coverage.health_score: composite weighted score (0-100)
# coverage.suggestions: context-aware improvement actions
```

### MCP Server (16 Tools)

Built-in MCP server for any MCP client (Claude Desktop, mcporter, OpenClaw).

```python
from mcp_server import create_mcp_server

mcp = create_mcp_server(mg)
# Tools: remember, recall, relate, ask, lookup, neighbors, forget, stats,
#        timeline, health, entropy, reason, snapshot, code_explain,
#        quarantine, security
```

### OTel Telemetry

OpenTelemetry GenAI-compatible observability — first agent memory library with native OTel.

```python
from telemetry import enable_telemetry

# Auto-instruments 8 CRUD methods with gen_ai.memory.* spans
enable_telemetry(mg, exporter_endpoint="http://localhost:4317")
```

---

## Testing

```bash
cd agent-memory-graph
python3 -m pytest -q  # all 2,728 tests
python3 -m pytest test_memory_graph.py -q  # core only
python3 -m pytest -k "classification" -q  # classification suite
python3 -m pytest -k "activation" -q  # spreading activation family
```

**8,794 test cases** across 40+ test files. **291st consecutive day** 🏆.

---

## Design Philosophy

- **Graph-native** — memories aren't flat rows; they're nodes with edges, density, and health metrics
- **Zero dependencies** — pure Python stdlib + sqlite3; no pip install needed
- **Educational** — code readability > micro-optimization
- **Composable** — methods chain naturally for complex queries
- **Cognitive science inspired** — forgetting curves, sleep consolidation, strategic retention

---

*Part of [Code Lab](../) · 291 days of iteration · Cycle 431+*
