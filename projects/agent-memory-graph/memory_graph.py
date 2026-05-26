"""
Agent Memory Graph — AI Agent 的记忆网络

概念演示：用知识图谱管理 Agent 的长期记忆。
节点 = 概念/实体/事件，边 = 关系。
支持：添加记忆、语义召回、遗忘衰减、摘要压缩。

Usage:
    python memory_graph.py

依赖：仅需 Python 标准库（sqlite3 + json + math）
"""

import sqlite3
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

# ── 数据模型 ──────────────────────────────────────────────

@dataclass
class Node:
    id: str
    label: str           # 简短描述
    kind: str            # fact | event | person | concept | skill
    data: dict = field(default_factory=dict)
    created: float = 0.0
    accessed: float = 0.0
    weight: float = 1.0  # 记忆强度 0~1

@dataclass
class Edge:
    source: str
    target: str
    relation: str        # e.g. "likes", "works_on", "caused"
    weight: float = 1.0

# ── 记忆图谱 ──────────────────────────────────────────────

class MemoryGraph:
    """基于 SQLite 的轻量知识图谱，模拟人类长期记忆。"""

    # 遗忘曲线参数（Ebbinghaus）
    DECAY_RATE = 0.3          # 衰减速率
    ACCESS_BOOST = 0.4        # 每次访问恢复量
    MIN_WEIGHT = 0.05         # 低于此阈值视为"遗忘"

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                label TEXT,
                kind TEXT,
                data TEXT DEFAULT '{}',
                created REAL,
                accessed REAL,
                weight REAL DEFAULT 1.0,
                tags TEXT DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS edges (
                source TEXT,
                target TEXT,
                relation TEXT,
                weight REAL DEFAULT 1.0,
                PRIMARY KEY (source, target, relation)
            );
        """)

    def add(self, label: str, kind: str = "fact", data: dict = None, tags: list[str] = None) -> Node:
        """添加一个记忆节点。"""
        node = Node(
            id=uuid.uuid4().hex[:12],
            label=label, kind=kind,
            data=data or {},
            created=time.time(), accessed=time.time(), weight=1.0
        )
        self.conn.execute(
            "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
            (node.id, node.label, node.kind, json.dumps(node.data),
             node.created, node.accessed, node.weight, json.dumps(tags or []))
        )
        self.conn.commit()
        return node

    def get_node(self, node_id: str) -> Optional[Node]:
        """Retrieve a single node by ID. Returns None if not found."""
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return None
        return Node(row["id"], row["label"], row["kind"],
                    json.loads(row["data"]), row["created"], row["accessed"], row["weight"])

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its edges. Returns True if node existed."""
        row = self.conn.execute("SELECT id FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return False
        self.conn.execute("DELETE FROM edges WHERE source=? OR target=?", (node_id, node_id))
        self.conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        self.conn.commit()
        return True

    def update_node(self, node_id: str, label: str = None, kind: str = None,
                    data: dict = None, weight: float = None) -> Optional[Node]:
        """Update node attributes. Only non-None fields are changed. Returns updated node or None."""
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return None
        new_label = label if label is not None else row["label"]
        new_kind = kind if kind is not None else row["kind"]
        new_data = json.dumps(data) if data is not None else row["data"]
        new_weight = weight if weight is not None else row["weight"]
        self.conn.execute(
            "UPDATE nodes SET label=?, kind=?, data=?, weight=? WHERE id=?",
            (new_label, new_kind, new_data, new_weight, node_id)
        )
        self.conn.commit()
        return self.get_node(node_id)

    def add_many(self, items: list[dict]) -> list[Node]:
        """Batch-add nodes. Each item is a dict with keys: label, kind?, data?, tags?.
        Uses a single transaction for efficiency."""
        now = time.time()
        nodes = []
        for item in items:
            node = Node(
                id=uuid.uuid4().hex[:12],
                label=item["label"],
                kind=item.get("kind", "fact"),
                data=item.get("data", {}),
                created=now, accessed=now, weight=1.0
            )
            tags = item.get("tags", [])
            self.conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                (node.id, node.label, node.kind, json.dumps(node.data),
                 node.created, node.accessed, node.weight, json.dumps(tags))
            )
            nodes.append(node)
        self.conn.commit()
        return nodes

    def link_many(self, pairs: list[dict]) -> int:
        """Batch-link nodes. Each dict: {source, target, relation, weight?}.
        Returns count of edges created."""
        count = 0
        for p in pairs:
            self.conn.execute(
                "INSERT OR REPLACE INTO edges VALUES (?,?,?,?)",
                (p["source"], p["target"], p["relation"], p.get("weight", 1.0))
            )
            count += 1
        self.conn.commit()
        return count

    def delete_many(self, node_ids: list[str]) -> int:
        """Batch-delete nodes with edge cleanup. Returns count of nodes deleted."""
        count = 0
        for nid in node_ids:
            row = self.conn.execute("SELECT id FROM nodes WHERE id=?", (nid,)).fetchone()
            if row:
                self.conn.execute("DELETE FROM edges WHERE source=? OR target=?", (nid, nid))
                self.conn.execute("DELETE FROM nodes WHERE id=?", (nid,))
                count += 1
        self.conn.commit()
        return count

    def tag_nodes(self, tag: str, node_ids: list[str]):
        """Add a tag to multiple nodes."""
        for nid in node_ids:
            row = self.conn.execute("SELECT tags FROM nodes WHERE id=?", (nid,)).fetchone()
            if not row:
                continue
            tags = json.loads(row["tags"])
            if tag not in tags:
                tags.append(tag)
                self.conn.execute("UPDATE nodes SET tags=? WHERE id=?", (json.dumps(tags), nid))
        self.conn.commit()

    def search_by_tag(self, tag: str) -> list[Node]:
        """Return all nodes with a given tag."""
        rows = self.conn.execute("SELECT * FROM nodes").fetchall()
        results = []
        for r in rows:
            tags_list = json.loads(r["tags"])
            if tag in tags_list:
                results.append(Node(
                    r["id"], r["label"], r["kind"],
                    json.loads(r["data"]), r["created"], r["accessed"], r["weight"]
                ))
        return results

    def link(self, source_id: str, target_id: str, relation: str, weight: float = 1.0):
        """连接两个节点。"""
        self.conn.execute(
            "INSERT OR REPLACE INTO edges VALUES (?,?,?,?)",
            (source_id, target_id, relation, weight)
        )
        self.conn.commit()

    def unlink(self, source_id: str, target_id: str, relation: str):
        """Remove an edge between two nodes."""
        self.conn.execute(
            "DELETE FROM edges WHERE source=? AND target=? AND relation=?",
            (source_id, target_id, relation)
        )
        self.conn.commit()

    def recall(self, query: str, limit: int = 5) -> list[Node]:
        """按关键词召回记忆，访问过的记忆强度增加。"""
        now = time.time()
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE label LIKE ? ORDER BY weight DESC LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()

        results = []
        for r in rows:
            # 应用遗忘衰减
            elapsed_days = (now - r["accessed"]) / 86400
            decayed = r["weight"] * math.exp(-self.DECAY_RATE * elapsed_days)
            boosted = min(1.0, decayed + self.ACCESS_BOOST)

            self.conn.execute(
                "UPDATE nodes SET weight=?, accessed=? WHERE id=?",
                (boosted, now, r["id"])
            )
            results.append(Node(
                id=r["id"], label=r["label"], kind=r["kind"],
                data=json.loads(r["data"]),
                created=r["created"], accessed=now, weight=boosted
            ))
        self.conn.commit()
        return results

    def decay_all(self):
        """对所有记忆应用遗忘衰减（模拟时间流逝）。"""
        now = time.time()
        rows = self.conn.execute("SELECT id, accessed, weight FROM nodes").fetchall()
        for r in rows:
            elapsed_days = (now - r["accessed"]) / 86400
            new_w = max(0.0, r["weight"] * math.exp(-self.DECAY_RATE * elapsed_days))
            self.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (new_w, r["id"]))
        # 清除已遗忘的
        self.conn.execute("DELETE FROM nodes WHERE weight < ?", (self.MIN_WEIGHT,))
        self.conn.commit()

    def neighbors(self, node_id: str, depth: int = 1) -> list[Node]:
        """获取关联记忆（BFS 遍历）。"""
        visited = {node_id}
        frontier = [node_id]
        results = []
        for _ in range(depth):
            next_frontier = []
            for nid in frontier:
                rows = self.conn.execute(
                    "SELECT n.* FROM nodes n JOIN edges e ON n.id=e.target WHERE e.source=?",
                    (nid,)
                ).fetchall()
                for r in rows:
                    if r["id"] not in visited:
                        visited.add(r["id"])
                        results.append(Node(
                            r["id"], r["label"], r["kind"],
                            json.loads(r["data"]), r["created"], r["accessed"], r["weight"]
                        ))
                        next_frontier.append(r["id"])
            frontier = next_frontier
        return results

    def stats(self) -> dict:
        """记忆网络统计。"""
        n = self.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        e = self.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        avg_w = self.conn.execute("SELECT AVG(weight) w FROM nodes").fetchone()["w"] or 0
        kinds = self.conn.execute(
            "SELECT kind, COUNT(*) c FROM nodes GROUP BY kind"
        ).fetchall()
        return {
            "nodes": n, "edges": e,
            "avg_weight": round(avg_w, 3),
            "by_kind": {r["kind"]: r["c"] for r in kinds}
        }

    def merge_nodes(self, source_id: str, target_id: str) -> Optional[Node]:
        """Merge source into target. Target keeps its id, absorbs source's data and edges."""
        src = self.conn.execute("SELECT * FROM nodes WHERE id=?", (source_id,)).fetchone()
        tgt = self.conn.execute("SELECT * FROM nodes WHERE id=?", (target_id,)).fetchone()
        if not src or not tgt:
            return None
        # Merge data
        merged_data = {**json.loads(src["data"]), **json.loads(tgt["data"])}
        new_weight = max(src["weight"], tgt["weight"])
        # Rewire edges pointing to source -> point to target
        # First delete edges that would become duplicates
        self.conn.execute("""
            DELETE FROM edges WHERE (source=? OR source=?) AND target IN (
                SELECT e2.target FROM edges e2 WHERE e2.source=? AND e2.target=?
                UNION
                SELECT e2.source FROM edges e2 WHERE e2.target=? AND e2.source=?
            )
        """, (source_id, target_id, source_id, target_id, source_id, target_id))
        self.conn.execute("UPDATE edges SET source=? WHERE source=?", (target_id, source_id))
        self.conn.execute("UPDATE edges SET target=? WHERE target=?", (target_id, source_id))
        # Remove self-loops
        self.conn.execute("DELETE FROM edges WHERE source=? AND target=?", (target_id, target_id))
        # Update target
        self.conn.execute(
            "UPDATE nodes SET data=?, weight=? WHERE id=?",
            (json.dumps(merged_data), new_weight, target_id)
        )
        # Delete source
        self.conn.execute("DELETE FROM nodes WHERE id=?", (source_id,))
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (target_id,)).fetchone()
        return Node(row["id"], row["label"], row["kind"],
                    json.loads(row["data"]), row["created"], row["accessed"], row["weight"])

    def shortest_path(self, start_id: str, end_id: str) -> Optional[list[str]]:
        """BFS shortest path between two nodes. Returns list of node ids or None."""
        if start_id == end_id:
            return [start_id]
        visited = {start_id}
        queue = [(start_id, [start_id])]
        while queue:
            current, path = queue.pop(0)
            neighbors = self.conn.execute(
                "SELECT target FROM edges WHERE source=?", (current,)
            ).fetchall()
            for n in neighbors:
                nid = n["target"]
                if nid in visited:
                    continue
                visited.add(nid)
                new_path = path + [nid]
                if nid == end_id:
                    return new_path
                queue.append((nid, new_path))
        return None

    def export_json(self) -> dict:
        """Export entire graph as a JSON-serializable dict."""
        nodes = []
        for r in self.conn.execute("SELECT * FROM nodes").fetchall():
            nodes.append({
                "id": r["id"], "label": r["label"], "kind": r["kind"],
                "data": json.loads(r["data"]), "created": r["created"],
                "accessed": r["accessed"], "weight": r["weight"],
                "tags": json.loads(r["tags"])
            })
        edges = []
        for r in self.conn.execute("SELECT * FROM edges").fetchall():
            edges.append({
                "source": r["source"], "target": r["target"],
                "relation": r["relation"], "weight": r["weight"]
            })
        return {"version": 1, "nodes": nodes, "edges": edges}

    def import_json(self, data: dict, merge: bool = False):
        """Import graph from export_json() output.
        If merge=True, add to existing graph. Otherwise clear first."""
        if not merge:
            self.conn.execute("DELETE FROM edges")
            self.conn.execute("DELETE FROM nodes")
        for n in data.get("nodes", []):
            self.conn.execute(
                "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                (n["id"], n["label"], n["kind"], json.dumps(n.get("data", {})),
                 n.get("created", time.time()), n.get("accessed", time.time()),
                 n.get("weight", 1.0), json.dumps(n.get("tags", [])))
            )
        for e in data.get("edges", []):
            self.conn.execute(
                "INSERT OR REPLACE INTO edges VALUES (?,?,?,?)",
                (e["source"], e["target"], e["relation"], e.get("weight", 1.0))
            )
        self.conn.commit()

    def find_by_kind(self, kind: str) -> list[Node]:
        """Return all nodes of a given kind."""
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE kind=? ORDER BY weight DESC", (kind,)
        ).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                     json.loads(r["data"]), r["created"], r["accessed"], r["weight"])
                for r in rows]

    def search_by_data(self, key: str, value=None) -> list[Node]:
        """Find nodes whose data dict contains key (and optionally matches value)."""
        results = []
        for r in self.conn.execute("SELECT * FROM nodes").fetchall():
            d = json.loads(r["data"])
            if key in d and (value is None or d[key] == value):
                results.append(Node(
                    r["id"], r["label"], r["kind"],
                    d, r["created"], r["accessed"], r["weight"]
                ))
        return results

    def edges_of(self, node_id: str, direction: str = "both") -> list[Edge]:
        """Get edges connected to a node. direction: 'outgoing', 'incoming', or 'both'."""
        edges = []
        if direction in ("outgoing", "both"):
            for r in self.conn.execute(
                "SELECT * FROM edges WHERE source=?", (node_id,)
            ).fetchall():
                edges.append(Edge(r["source"], r["target"], r["relation"], r["weight"]))
        if direction in ("incoming", "both"):
            for r in self.conn.execute(
                "SELECT * FROM edges WHERE target=?", (node_id,)
            ).fetchall():
                edges.append(Edge(r["source"], r["target"], r["relation"], r["weight"]))
        return edges

    def count_by_kind(self) -> dict[str, int]:
        """Return {kind: count} for all node kinds."""
        rows = self.conn.execute(
            "SELECT kind, COUNT(*) c FROM nodes GROUP BY kind"
        ).fetchall()
        return {r["kind"]: r["c"] for r in rows}

    def top_nodes(self, n: int = 5) -> list[Node]:
        """Return top-n nodes by weight."""
        rows = self.conn.execute(
            "SELECT * FROM nodes ORDER BY weight DESC LIMIT ?", (n,)
        ).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                     json.loads(r["data"]), r["created"], r["accessed"], r["weight"])
                for r in rows]

    def touch(self, node_id: str) -> Optional[Node]:
        """Update a node's accessed timestamp and boost weight. Returns updated node or None."""
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return None
        new_weight = min(1.0, row["weight"] + self.ACCESS_BOOST)
        now = time.time()
        self.conn.execute(
            "UPDATE nodes SET accessed=?, weight=? WHERE id=?",
            (now, new_weight, node_id)
        )
        self.conn.commit()
        return self.get_node(node_id)

    def has_node(self, node_id: str) -> bool:
        """Check if a node exists without fetching it."""
        row = self.conn.execute("SELECT 1 FROM nodes WHERE id=?", (node_id,)).fetchone()
        return row is not None

    def rename_tag(self, old_tag: str, new_tag: str) -> int:
        """Rename a tag across all nodes. Returns count of nodes updated."""
        count = 0
        for r in self.conn.execute("SELECT id, tags FROM nodes").fetchall():
            tags = json.loads(r["tags"])
            if old_tag in tags:
                tags[tags.index(old_tag)] = new_tag
                self.conn.execute("UPDATE nodes SET tags=? WHERE id=?", (json.dumps(tags), r["id"]))
                count += 1
        self.conn.commit()
        return count

    def clear_tags(self, node_id: str) -> bool:
        """Remove all tags from a node. Returns True if node existed."""
        if not self.has_node(node_id):
            return False
        self.conn.execute("UPDATE nodes SET tags='[]' WHERE id=?", (node_id,))
        self.conn.commit()
        return True

    def reweight(self, node_id: str, delta: float) -> Optional[Node]:
        """Adjust a node's weight by delta (can be negative). Clamps to [0, 1]. Returns updated node."""
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return None
        new_w = max(0.0, min(1.0, row["weight"] + delta))
        self.conn.execute("UPDATE nodes SET weight=? WHERE id=?", (new_w, node_id))
        self.conn.commit()
        return self.get_node(node_id)

    def is_linked(self, source_id: str, target_id: str, relation: str = None) -> bool:
        """Check if an edge exists. If relation is None, checks any edge between the two."""
        if relation is not None:
            row = self.conn.execute(
                "SELECT 1 FROM edges WHERE source=? AND target=? AND relation=?",
                (source_id, target_id, relation)
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT 1 FROM edges WHERE source=? AND target=?",
                (source_id, target_id)
            ).fetchone()
        return row is not None

    def all_tags(self) -> list[str]:
        """Return sorted list of unique tags across all nodes."""
        tags_set = set()
        for r in self.conn.execute("SELECT tags FROM nodes").fetchall():
            tags_set.update(json.loads(r["tags"]))
        return sorted(tags_set)

    def subgraph(self, node_id: str, depth: int = 1) -> dict:
        """Extract a subgraph around node_id up to `depth` hops.

        Returns a dict with 'center', 'nodes', 'edges' suitable for JSON serialization
        or passing to import_json(). Useful for pulling relevant context into an agent's
        working memory.
        """
        visited_nodes = set()
        visited_edges = set()
        frontier = {node_id}

        for _ in range(depth + 1):
            next_frontier = set()
            for nid in frontier:
                if nid in visited_nodes:
                    continue
                visited_nodes.add(nid)
                # collect edges
                for r in self.conn.execute(
                    "SELECT source, target, relation, weight FROM edges WHERE source=? OR target=?",
                    (nid, nid)
                ).fetchall():
                    edge_key = (r["source"], r["target"], r["relation"])
                    if edge_key not in visited_edges:
                        visited_edges.add(edge_key)
                        next_frontier.add(r["source"])
                        next_frontier.add(r["target"])
            frontier = next_frontier - visited_nodes

        # Build node/edge lists (reuse export_json format)
        nodes = []
        placeholders = ",".join("?" for _ in visited_nodes)
        for r in self.conn.execute(
            f"SELECT * FROM nodes WHERE id IN ({placeholders})",
            list(visited_nodes)
        ).fetchall():
            nodes.append({
                "id": r["id"], "label": r["label"], "kind": r["kind"],
                "data": json.loads(r["data"]), "created": r["created"],
                "accessed": r["accessed"], "weight": r["weight"],
                "tags": json.loads(r["tags"])
            })
        edges = []
        for sk, tk, rel in visited_edges:
            row = self.conn.execute(
                "SELECT weight FROM edges WHERE source=? AND target=? AND relation=?",
                (sk, tk, rel)
            ).fetchone()
            edges.append({"source": sk, "target": tk, "relation": rel, "weight": row["weight"]})

        return {"center": node_id, "nodes": nodes, "edges": edges}

    def prune(self, min_weight: float = 0.1) -> dict:
        """Remove nodes below min_weight and their orphaned edges.

        Returns dict with 'nodes_removed', 'edges_removed' counts.
        Useful for periodic memory cleanup — keeps the graph lean.
        """
        # Find low-weight nodes
        rows = self.conn.execute(
            "SELECT id FROM nodes WHERE weight < ?", (min_weight,)
        ).fetchall()
        node_ids = [r["id"] for r in rows]
        if not node_ids:
            return {"nodes_removed": 0, "edges_removed": 0}

        # Count edges that will be removed
        placeholders = ",".join("?" for _ in node_ids)
        edge_count = self.conn.execute(
            f"SELECT COUNT(*) c FROM edges WHERE source IN ({placeholders}) OR target IN ({placeholders})",
            node_ids + node_ids
        ).fetchone()["c"]

        # Delete edges then nodes
        self.conn.execute(
            f"DELETE FROM edges WHERE source IN ({placeholders}) OR target IN ({placeholders})",
            node_ids + node_ids
        )
        self.conn.execute(
            f"DELETE FROM nodes WHERE id IN ({placeholders})",
            node_ids
        )
        self.conn.commit()
        return {"nodes_removed": len(node_ids), "edges_removed": edge_count}

    def aggregate(self, kind: str, field: str = "weight", fn: str = "sum") -> float:
        """Aggregate a numeric field across all nodes of a given kind.

        fn can be 'sum', 'avg', 'min', 'max', 'count'.
        Useful for answering questions like 'average weight of all events',
        'total weight of skills', etc.
        """
        valid_fns = {"sum", "avg", "min", "max", "count"}
        if fn not in valid_fns:
            raise ValueError(f"fn must be one of {valid_fns}, got '{fn}'")

        if fn == "count":
            row = self.conn.execute(
                "SELECT COUNT(*) c FROM nodes WHERE kind=?", (kind,)
            ).fetchone()
            return float(row["c"])

        sql_fn = {"sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX"}[fn]
        # Map field to column
        col_map = {"weight": "weight", "created": "created", "accessed": "accessed"}
        col = col_map.get(field, field)
        row = self.conn.execute(
            f"SELECT {sql_fn}({col}) v FROM nodes WHERE kind=?", (kind,)
        ).fetchone()
        val = row["v"]
        return float(val) if val is not None else 0.0

    def unlink_many(self, pairs: list[dict]) -> int:
        """Batch unlink edges. Each dict: {source, target, relation?}.
        If relation is omitted, removes all edges between source and target.
        Returns count of removed edges.
        """
        removed = 0
        for p in pairs:
            rel = p.get("relation")
            if rel is not None:
                cur = self.conn.execute(
                    "DELETE FROM edges WHERE source=? AND target=? AND relation=?",
                    (p["source"], p["target"], rel)
                )
            else:
                cur = self.conn.execute(
                    "DELETE FROM edges WHERE source=? AND target=?",
                    (p["source"], p["target"])
                )
            removed += cur.rowcount
        self.conn.commit()
        return removed

    def graph_diff(self, other: 'MemoryGraph') -> dict:
        """Compare this graph with another. Returns dict with:
        - nodes_only_self: node ids in self but not other
        - nodes_only_other: node ids in other but not self
        - nodes_modified: list of {id, field, self_val, other_val} for changed nodes
        - edges_only_self: edge tuples in self but not other
        - edges_only_other: edge tuples in other but not self
        Useful for graph sync — detect what changed between two versions.
        """
        self_nodes = {r["id"]: r for r in self.conn.execute("SELECT * FROM nodes").fetchall()}
        other_nodes = {r["id"]: r for r in other.conn.execute("SELECT * FROM nodes").fetchall()}

        self_ids = set(self_nodes.keys())
        other_ids = set(other_nodes.keys())

        diff = {
            "nodes_only_self": sorted(self_ids - other_ids),
            "nodes_only_other": sorted(other_ids - self_ids),
            "nodes_modified": [],
            "edges_only_self": [],
            "edges_only_other": [],
        }

        # Check modified nodes (same id, different content)
        for nid in self_ids & other_ids:
            s, o = self_nodes[nid], other_nodes[nid]
            for field in ("label", "kind", "weight"):
                if s[field] != o[field]:
                    diff["nodes_modified"].append({
                        "id": nid, "field": field,
                        "self_val": s[field], "other_val": o[field]
                    })
            # data diff
            sd, od = json.loads(s["data"]), json.loads(o["data"])
            if sd != od:
                diff["nodes_modified"].append({
                    "id": nid, "field": "data",
                    "self_val": sd, "other_val": od
                })

        # Edge diff
        self_edges = set()
        for r in self.conn.execute("SELECT source, target, relation FROM edges").fetchall():
            self_edges.add((r["source"], r["target"], r["relation"]))
        other_edges = set()
        for r in other.conn.execute("SELECT source, target, relation FROM edges").fetchall():
            other_edges.add((r["source"], r["target"], r["relation"]))

        diff["edges_only_self"] = sorted(self_edges - other_edges)
        diff["edges_only_other"] = sorted(other_edges - self_edges)
        return diff

    def compact(self, strategy: str = "merge_similar", similarity_threshold: float = 0.8) -> dict:
        """Compact the graph by merging similar/low-value nodes.

        strategy='merge_similar': merge nodes with identical labels and kind.
        Returns dict with 'merged_pairs' (list of [survivor_id, absorbed_id]) and 'total_merged'.
        """
        if strategy != "merge_similar":
            raise ValueError(f"Unknown strategy: {strategy}")

        # Group by (label, kind)
        groups = defaultdict(list)
        for r in self.conn.execute("SELECT id, label, kind FROM nodes").fetchall():
            groups[(r["label"], r["kind"])].append(r["id"])

        merged_pairs = []
        for (label, kind), ids in groups.items():
            if len(ids) < 2:
                continue
            # Keep the first (survivor), merge rest into it
            survivor = ids[0]
            for absorb_id in ids[1:]:
                self.merge_nodes(absorb_id, survivor)
                merged_pairs.append([survivor, absorb_id])

        return {"merged_pairs": merged_pairs, "total_merged": len(merged_pairs)}

    def search_unified(self, query: str, limit: int = 10) -> list[dict]:
        """Unified search across label, data values, and tags.

        Returns list of dicts: {node, score, matched_fields}.
        Score = field_matches * weight_boost. label match scores highest.
        """
        query_lower = query.lower()
        results = []

        for r in self.conn.execute("SELECT * FROM nodes").fetchall():
            score = 0.0
            matched = []

            # Label match (highest weight)
            if query_lower in r["label"].lower():
                score += 3.0
                matched.append("label")

            # Data value match
            data = json.loads(r["data"])
            for v in data.values():
                if query_lower in str(v).lower():
                    score += 2.0
                    matched.append("data")
                    break

            # Tag match
            tags = json.loads(r["tags"])
            for t in tags:
                if query_lower in t.lower():
                    score += 1.5
                    matched.append("tags")
                    break

            # Kind match (bonus)
            if query_lower == r["kind"].lower():
                score += 1.0
                matched.append("kind")

            if score > 0:
                node = Node(r["id"], r["label"], r["kind"],
                           data, r["created"], r["accessed"], r["weight"])
                results.append({
                    "node": node,
                    "score": score * r["weight"],
                    "matched_fields": matched
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def rename_node(self, node_id: str, new_label: str) -> Optional[Node]:
        """Rename a node's label. Returns updated node or None."""
        if not self.has_node(node_id):
            return None
        self.conn.execute("UPDATE nodes SET label=? WHERE id=?", (new_label, node_id))
        self.conn.commit()
        return self.get_node(node_id)

    def clone_node(self, node_id: str, new_label: str = None) -> Optional[Node]:
        """Clone a node (with same data/kind/tags) but not its edges.
        Returns the new node or None if source doesn't exist."""
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return None
        new_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
            (new_id, new_label or row["label"], row["kind"], row["data"],
             time.time(), time.time(), row["weight"], row["tags"])
        )
        self.conn.commit()
        return self.get_node(new_id)

    def path_exists(self, start_id: str, end_id: str, max_depth: int = 10) -> bool:
        """Check if a path exists between two nodes (BFS with depth limit)."""
        if start_id == end_id:
            return self.has_node(start_id)
        visited = {start_id}
        frontier = [start_id]
        for _ in range(max_depth):
            next_frontier = []
            for nid in frontier:
                for r in self.conn.execute(
                    "SELECT target FROM edges WHERE source=?", (nid,)
                ).fetchall():
                    if r["target"] == end_id:
                        return True
                    if r["target"] not in visited:
                        visited.add(r["target"])
                        next_frontier.append(r["target"])
            frontier = next_frontier
        return False

    def find_roots(self) -> list:
        """Find nodes with no incoming edges (root/source nodes)."""
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE id NOT IN (SELECT target FROM edges)"
        ).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                     json.loads(r["data"]) if r["data"] else {},
                     r["created"], r["accessed"], r["weight"]) for r in rows]

    def find_leaves(self) -> list:
        """Find nodes with no outgoing edges (leaf/sink nodes)."""
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE id NOT IN (SELECT source FROM edges)"
        ).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                     json.loads(r["data"]) if r["data"] else {},
                     r["created"], r["accessed"], r["weight"]) for r in rows]

    def degree(self, node_id: str, direction: str = "both") -> int:
        """Get degree of a node. direction: 'in', 'out', or 'both'."""
        if not self.has_node(node_id):
            return 0
        if direction == "in":
            return self.conn.execute(
                "SELECT COUNT(*) as c FROM edges WHERE target=?", (node_id,)
            ).fetchone()["c"]
        elif direction == "out":
            return self.conn.execute(
                "SELECT COUNT(*) as c FROM edges WHERE source=?", (node_id,)
            ).fetchone()["c"]
        else:
            return self.conn.execute(
                "SELECT COUNT(*) as c FROM edges WHERE source=? OR target=?",
                (node_id, node_id)
            ).fetchone()["c"]

    def degree_centrality(self, node_id: str) -> float:
        """Normalized degree centrality (0.0-1.0). Returns 0.0 for isolated/missing nodes."""
        total_nodes = self.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        if total_nodes <= 1:
            return 0.0
        deg = self.degree(node_id, "both")
        return deg / (total_nodes - 1)

    def shortest_path(self, start_id: str, end_id: str) -> Optional[list]:
        """BFS shortest path returning list of node IDs, or None if no path."""
        if start_id == end_id:
            return [start_id] if self.has_node(start_id) else None
        visited = {start_id: None}
        frontier = [start_id]
        while frontier:
            next_frontier = []
            for nid in frontier:
                for r in self.conn.execute(
                    "SELECT target FROM edges WHERE source=?", (nid,)
                ).fetchall():
                    tid = r["target"]
                    if tid == end_id:
                        path = [end_id]
                        cur = nid
                        while cur is not None:
                            path.append(cur)
                            cur = visited[cur]
                        return list(reversed(path))
                    if tid not in visited:
                        visited[tid] = nid
                        next_frontier.append(tid)
            frontier = next_frontier
        return None

    def betweenness_centrality(self, node_id: str, samples: int = 50) -> float:
        """Approximate betweenness centrality via random sampling of shortest paths."""
        if not self.has_node(node_id):
            return 0.0
        all_ids = [r[0] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        if len(all_ids) < 3:
            return 0.0
        import random
        count = 0
        for _ in range(min(samples, len(all_ids) * (len(all_ids) - 1) // 2)):
            s, t = random.sample(all_ids, 2)
            path = self.shortest_path(s, t)
            if path and node_id in path[1:-1]:  # exclude endpoints
                count += 1
        return count / max(samples, 1)

    def community_detect(self, max_iter: int = 10) -> dict:
        """Label-propagation community detection. Returns {community_label: [node_ids]}."""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not nodes:
            return {}
        import random
        labels = {r["id"]: i for i, r in enumerate(nodes)}
        ids = list(labels.keys())
        for _ in range(max_iter):
            random.shuffle(ids)
            changed = False
            for nid in ids:
                neighbor_labels = {}
                for r in self.conn.execute(
                    "SELECT source FROM edges WHERE target=? UNION SELECT target FROM edges WHERE source=?",
                    (nid, nid)
                ).fetchall():
                    lbl = labels.get(r[0])
                    if lbl is not None:
                        neighbor_labels[lbl] = neighbor_labels.get(lbl, 0) + 1
                if neighbor_labels:
                    best = max(neighbor_labels, key=neighbor_labels.get)
                    if labels[nid] != best:
                        labels[nid] = best
                        changed = True
            if not changed:
                break
        communities = {}
        for nid, lbl in labels.items():
            communities.setdefault(lbl, []).append(nid)
        return communities

    def eigenvector_centrality(self, iterations: int = 20, damping: float = 0.85) -> dict:
        """Iterative eigenvector centrality. Returns {node_id: score}."""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not nodes:
            return {}
        n = len(nodes)
        scores = {r["id"]: 1.0 / n for r in nodes}
        for _ in range(iterations):
            new_scores = {}
            for r in nodes:
                nid = r["id"]
                s = 0.0
                for src in self.conn.execute(
                    "SELECT source FROM edges WHERE target=?", (nid,)
                ).fetchall():
                    out_deg = self.degree(src[0], "out")
                    if out_deg > 0:
                        s += scores.get(src[0], 0) / out_deg
                new_scores[nid] = (1 - damping) / n + damping * s
            # Normalize
            max_s = max(new_scores.values()) or 1.0
            scores = {k: v / max_s for k, v in new_scores.items()}
        return scores

    def pagerank(self, iterations: int = 20, damping: float = 0.85) -> dict:
        """PageRank algorithm. Returns {node_id: score}."""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not nodes:
            return {}
        n = len(nodes)
        scores = {r["id"]: 1.0 / n for r in nodes}
        for _ in range(iterations):
            new_scores = {}
            for r in nodes:
                nid = r["id"]
                s = 0.0
                for src in self.conn.execute(
                    "SELECT source FROM edges WHERE target=?", (nid,)
                ).fetchall():
                    out_deg = self.degree(src[0], "out")
                    if out_deg > 0:
                        s += scores.get(src[0], 0) / out_deg
                new_scores[nid] = (1 - damping) / n + damping * s
            total = sum(new_scores.values()) or 1.0
            scores = {k: v / total for k, v in new_scores.items()}
        return scores

    def k_core(self, k: int) -> list:
        """Find k-core: nodes with degree >= k after iterative pruning."""
        nodes = {r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()}
        changed = True
        while changed:
            changed = False
            to_remove = set()
            for nid in nodes:
                deg = 0
                for r in self.conn.execute(
                    "SELECT source FROM edges WHERE target=? UNION ALL SELECT target FROM edges WHERE source=?",
                    (nid, nid)
                ).fetchall():
                    if r[0] in nodes:
                        deg += 1
                if deg < k:
                    to_remove.add(nid)
            if to_remove:
                nodes -= to_remove
                changed = True
        return list(nodes)

    def triangles(self, node_id: str) -> int:
        """Count triangles involving this node."""
        if not self.has_node(node_id):
            return 0
        neighbors = set()
        for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION ALL SELECT source FROM edges WHERE target=?",
            (node_id, node_id)
        ).fetchall():
            neighbors.add(r[0])
        count = 0
        for n1 in neighbors:
            n1_neighbors = set()
            for r in self.conn.execute(
                "SELECT target FROM edges WHERE source=? UNION ALL SELECT source FROM edges WHERE target=?",
                (n1, n1)
            ).fetchall():
                n1_neighbors.add(r[0])
            if n1_neighbors & neighbors:
                count += len(n1_neighbors & neighbors)
        # Each triangle counted twice (once per neighbor pair)
        return count // 2

    def visualize_ascii(self) -> str:
        """简单的 ASCII 可视化。"""
        lines = ["📊 Memory Network:"]
        nodes = self.conn.execute(
            "SELECT * FROM nodes ORDER BY weight DESC LIMIT 15"
        ).fetchall()
        for n in nodes:
            bar = "█" * int(n["weight"] * 10)
            lines.append(f"  [{n['kind']:7s}] {n['label'][:30]:30s} {bar} {n['weight']:.1f}")
            edges = self.conn.execute(
                "SELECT relation, target FROM edges WHERE source=?", (n["id"],)
            ).fetchall()
            for e in edges:
                tgt = self.conn.execute(
                    "SELECT label FROM nodes WHERE id=?", (e["target"],)
                ).fetchone()
                if tgt:
                    lines.append(f"    ──{e['relation']}──▶ {tgt['label'][:25]}")
        return "\n".join(lines)


# ── 演示 ──────────────────────────────────────────────────

def demo():
    print("🧪 Agent Memory Graph Demo\n")
    mg = MemoryGraph()

    # 添加记忆
    user = mg.add("罗嵩", "person", {"timezone": "Asia/Shanghai"})
    catalyst = mg.add("Catalyst - 数字精灵", "person", {"vibe": "sharp & fast"})
    project = mg.add("OpenClaw Agent", "concept", {"lang": "TypeScript"})
    python_skill = mg.add("Python 快速原型", "skill")
    rust_interest = mg.add("Rust 嵌入式AI", "concept")

    # 建立关系
    mg.link(user.id, catalyst.id, "created")
    mg.link(user.id, project.id, "works_on")
    mg.link(catalyst.id, project.id, "assists_with")
    mg.link(user.id, python_skill.id, "skilled_in")
    mg.link(user.id, rust_interest.id, "interested_in")
    mg.link(rust_interest.id, project.id, "relevant_to")

    # 添加一些事件
    e1 = mg.add("深夜debug session", "event", {"hours": 3})
    mg.link(e1.id, project.id, "about")
    mg.link(user.id, e1.id, "experienced")

    print(mg.visualize_ascii())
    print()

    # 召回
    print("🔍 Recalling 'Python':")
    for r in mg.recall("Python"):
        print(f"  ✓ {r.label} (weight={r.weight:.2f})")
    print()

    # 关联记忆
    print(f"🔗 Neighbors of '{user.label}':")
    for n in mg.neighbors(user.id):
        print(f"  → {n.label} [{n.kind}]")
    print()

    # 统计
    print(f"📈 Stats: {json.dumps(mg.stats(), ensure_ascii=False, indent=2)}")

    # 模拟遗忘
    print("\n⏳ Simulating 7-day decay...")
    # 手动模拟：降低 accessed 时间
    mg.conn.execute("UPDATE nodes SET accessed = accessed - 604800")
    mg.conn.commit()
    mg.decay_all()
    print(mg.visualize_ascii())

    print("\n✅ Done. 这是一个 Agent 记忆管理的概念原型。")


if __name__ == "__main__":
    demo()
