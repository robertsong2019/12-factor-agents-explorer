# Agent Memory Graph 🧠

> A graph-native memory engine for AI agents — 18,000+ lines, 460+ API methods, zero dependencies.

**Zero dependencies** — pure Python stdlib + sqlite3.

## Why?

Agents wake up fresh each session. Files work, but they're flat. A memory graph lets agents:
- Store **entities** (people, projects, concepts) as graph nodes
- Create **typed relations** between them as weighted edges
- **Query** by label, kind, tag, semantic similarity, or graph traversal
- **Decay & consolidate** memories automatically using cognitive science models
- **Track evolution** — bi-temporal versioning, snapshots, rollback
- **Analyze structure** — 57 graph metrics + spectral/information-theoretic tools

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
| **Graph Metrics** | 57 | `pagerank`, `betweenness_centrality`, `community_detect`, `clustering_coefficient`, `modularity` |
| **Spectral / Information Theory** | 22 | `von_neumann_entropy`, `spectral_entropy_profile`, `spectral_entropy_contribution`, `entropy_stability_spectral`, `entropy_anomaly_detect`, `ego_entropy_profile`, `entropy_fingerprint`, `semantic_divergence`, `divergence_scan` |
| **Memory Lifecycle** | 24 | `forgetting_curve`, `fifa_forget`, `consolidate_memory`, `sleep_consolidate`, `strategic_forget` |
| **Workflow / Patterns** | 14 | `add_workflow`, `retrieve_workflows`, `workflow_success_patterns`, `workflow_compose` |
| **Temporal / Versioning** | 31 | `evolve`, `temporal_snapshot`, `query_as_of`, `temporal_diff`, `supersede`, `immutable_retrieve`, `revert_evolution` |
| **Embedding / Vector** | 19 | `add_embedding`, `search_similar`, `train_kge`, `kge_score` |
| **Classification** | 6 | `rrf_classification`, `bayesian_classification`, `knn_classification`, `weighted_average_classification`, `classification_compare` |
| **Diagnostics** | 3 | `graph_health_score`, `entropy_dashboard`, `get_operation_history` |
| **Serialization** | 24 | `export_json`, `to_markdown`, `serialize_dot`, `serialize_graphml`, `serialize_cytoscape` |

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

## Testing

```bash
cd agent-memory-graph
python3 -m pytest test_memory_graph.py -q
```

**2,130+ test cases** covering all API methods.

---

## Design Philosophy

- **Graph-native** — memories aren't flat rows; they're nodes with edges, density, and health metrics
- **Zero dependencies** — pure Python stdlib + sqlite3; no pip install needed
- **Educational** — code readability > micro-optimization
- **Composable** — methods chain naturally for complex queries
- **Cognitive science inspired** — forgetting curves, sleep consolidation, strategic retention

---

*Part of [Code Lab](../) · 280 days of iteration · Cycle 330+*
