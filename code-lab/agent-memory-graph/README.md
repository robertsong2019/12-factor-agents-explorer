# Agent Memory Graph 🧠

A lightweight knowledge graph memory system for AI agents.

**Zero dependencies** — only Python stdlib + sqlite3.

## Why?

Agents wake up fresh each session. Files work, but they're flat. A memory graph lets agents:
- Store **entities** (people, projects, concepts)
- Create **relations** between them
- **Query** by type, relation, or semantic similarity
- **Decay** old memories automatically

## Quick Start

```python
from memory_graph import MemoryGraph

mg = MemoryGraph("agent_memory.db")

# Store entities
mg.add_entity("罗嵩", type="person", properties={"role": "developer", "timezone": "Asia/Shanghai"})
mg.add_entity("Catalyst", type="agent", properties={"emoji": "🧪", "role": "digital familiar"})

# Create relations
mg.relate("罗嵩", "created", "Catalyst")
mg.relate("Catalyst", "serves", "罗嵩")

# Query
friends = mg.query(entity_type="person")
relations = mg.get_relations("罗嵩")

# Context recall — get everything connected to an entity
context = mg.context("Catalyst", depth=2)

# Memory decay — reduce weight of old, unused memories
mg.decay(max_age_days=30, threshold=0.1)
```

## Features

- **SQLite-backed** — zero dependencies, persistent
- **Weighted edges** — memories strengthen with use, decay with time
- **Context retrieval** — BFS traversal for connected subgraphs
- **Auto-decay** — old unused memories fade away
- **Full-text search** — fuzzy match on entity names and properties

## Tutorial

### Step 1: Create an in-memory graph

```python
from memory_graph import MemoryGraph

# :memory: for testing, or a file path for persistence
mg = MemoryGraph(":memory:")
```

### Step 2: Build a knowledge base

```python
# Add people
mg.add_entity("Alice", type="person", properties={"skill": "backend"})
mg.add_entity("Bob", type="person", properties={"skill": "frontend"})

# Add a project
mg.add_entity("ProjectX", type="project", properties={"status": "active"})

# Link them
mg.relate("Alice", "leads", "ProjectX")
mg.relate("Bob", "contributes_to", "ProjectX")
```

### Step 3: Query and traverse

```python
# Find all people
people = mg.query(entity_type="person")
# → [Entity(name='Alice', ...), Entity(name='Bob', ...)]

# Get Alice's relations
alice_edges = mg.get_relations("Alice")
# → [Relation(source='Alice', verb='leads', target='ProjectX', ...)]

# Context: everything within 2 hops of ProjectX
ctx = mg.context("ProjectX", depth=2)
# Returns all entities and relations connected to ProjectX
```

### Step 4: Memory lifecycle

```python
# Accessing an entity boosts its weight
entity = mg.get_entity("Alice")
# access_count++, accessed_at updated

# Old memories fade — run decay periodically
mg.decay(max_age_days=30, threshold=0.1)
# Entities below threshold are removed
```

### Pattern: Using with an AI Agent

```python
class MemoryAwareAgent:
    def __init__(self, db_path="agent_memory.db"):
        self.memory = MemoryGraph(db_path)

    def learn(self, text: str):
        """Extract entities from text and store them."""
        # Your NER logic here
        self.memory.add_entity(text, type="fact")

    def recall_context(self, topic: str, depth=2):
        """Get related context for a topic."""
        return self.memory.context(topic, depth=depth)

    def maintenance(self):
        """Call periodically to prune old memories."""
        self.memory.decay(max_age_days=60, threshold=0.05)
```

## API Reference

### Core CRUD

| Method | Description |
|--------|-------------|
| `add_entity(name, type, properties)` | Create or update an entity |
| `get_entity(name)` | Retrieve entity by name |
| `query(entity_type=None)` | Filter entities by type |
| `relate(source, verb, target)` | Create a directed edge |
| `get_relations(name)` | Get all edges involving name |
| `context(name, depth=2)` | BFS subgraph around entity |
| `decay(max_age_days, threshold)` | Prune low-weight old memories |
| `add_many(entities)` | Batch create entities |
| `link_many(links)` | Batch create relations |
| `delete_many(names)` | Batch delete entities |
| `batch_reweight(updates)` | Batch update weights |

### Graph Algorithms

| Method | Description |
|--------|-------------|
| `pagerank(damping, max_iter, tol)` | PageRank centrality scores |
| `eigenvector_centrality(max_iter, tol)` | Eigenvector centrality |
| `authority_score(max_iter)` | HITS authority scores |
| `betweenness_centrality()` | Betweenness centrality |
| `degree_centrality()` | Degree centrality per node |
| `k_core(k)` | Iterative k-core pruning |
| `core_number()` | Core number per node (Batagelj-Zaversnik) |
| `count_triangles()` | Global triangle count |
| `local_triangle_count(node_id)` | Per-node triangle participation |
| `clustering_coefficient(node_id)` | Local clustering coefficient |
| `community_detection()` | Label propagation community detection |

### Graph Transformations

| Method | Description |
|--------|-------------|
| `reverse_edges()` | Reverse all edge directions |
| `to_undirected()` | Convert to undirected (merge reciprocal) |
| `induce_by_label(labels)` | Subgraph induced by node labels |
| `normalize_weights()` | Normalize all weights to [0, 1] |

### Export Formats

| Method | Description |
|--------|-------------|
| `serialize_graphml()` | GraphML XML (Gephi/yEd/Cytoscape) |
| `serialize_cytoscape()` | Cytoscape.js JSON (web visualization) |
| `serialize_edgelist()` | Edge list format |

### Evolution Tracking

| Method | Description |
|--------|-------------|
| `record_evolution(node, old_label, new_label)` | Track label changes |
| `evolution_history(node)` | Get label/kind change history |
| `rollback_evolution(node, to_version)` | Revert to historical state |

### Data Classes

- **`Entity`**: `name`, `type`, `properties`, `weight`, `created_at`, `accessed_at`, `access_count`
- **`Relation`**: `source`, `verb`, `target`, `weight`, `created_at`, `properties`

> **130+ API methods** total — see source for full coverage.
