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
from datetime import datetime
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
        self._lamport_clock = 0
        self._typed_subscribers: dict[str, list[tuple[str, callable]]] = {}
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
            CREATE TABLE IF NOT EXISTS evolution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                old_label TEXT,
                new_label TEXT,
                old_kind TEXT,
                new_kind TEXT,
                timestamp REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_evo_node ON evolution_log(node_id);
            CREATE TABLE IF NOT EXISTS edge_props (
                source TEXT,
                target TEXT,
                relation TEXT,
                properties TEXT DEFAULT '{}',
                PRIMARY KEY (source, target, relation)
            );
        """)
        # Schema migration: add provenance + quarantine columns (backward compatible)
        existing_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(nodes)").fetchall()}
        migrations = [
            ("source", "TEXT DEFAULT NULL"),
            ("trust_level", "REAL DEFAULT 1.0"),
            ("parents", "TEXT DEFAULT '[]'"),
            ("quarantined", "INTEGER DEFAULT 0"),
            ("quarantine_reason", "TEXT DEFAULT NULL"),
            ("valid_from", "REAL DEFAULT NULL"),
            ("valid_to", "REAL DEFAULT NULL"),
            ("txn_time", "REAL DEFAULT NULL"),
            ("q_value", "REAL DEFAULT 0.0"),
        ]
        for col, typedef in migrations:
            if col not in existing_cols:
                self.conn.execute(f"ALTER TABLE nodes ADD COLUMN {col} {typedef}")
        # FTS5 full-text index for BM25 search
        try:
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts
                USING fts5(node_id UNINDEXED, label, kind, data, tags,
                           tokenize='unicode61')
            """)
            self._fts_enabled = True
        except sqlite3.OperationalError:
            self._fts_enabled = False
        # Vector clock event log
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS clock_log (
                lamport INTEGER PRIMARY KEY,
                op TEXT NOT NULL,
                node_id TEXT,
                details TEXT DEFAULT '{}',
                wall_time REAL
            )
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
            "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            (node.id, node.label, node.kind, json.dumps(node.data),
             node.created, node.accessed, node.weight, json.dumps(tags or []))
        )
        self._fts_sync_node(node.id)
        self.conn.commit()
        self._tick("add", node.id, {"label": label, "kind": kind})
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
        self._fts_delete_node(node_id)
        self.conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        self.conn.commit()
        self._tick("delete", node_id, {"node_id": node_id})
        return True

    def update_node(self, node_id: str, label: str = None, kind: str = None,
                    data: dict = None, weight: float = None) -> Optional[Node]:
        """Update node attributes. Only non-None fields are changed. Returns updated node or None."""
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return None
        old_label = row["label"]
        new_label = label if label is not None else row["label"]
        new_kind = kind if kind is not None else row["kind"]
        new_data = json.dumps(data) if data is not None else row["data"]
        new_weight = weight if weight is not None else row["weight"]
        self.conn.execute(
            "UPDATE nodes SET label=?, kind=?, data=?, weight=? WHERE id=?",
            (new_label, new_kind, new_data, new_weight, node_id)
        )
        self._fts_sync_node(node_id)
        self.conn.commit()
        self._tick("update", node_id,
                   {"old_label": old_label, "new_label": new_label,
                    "old_kind": row["kind"], "new_kind": new_kind})
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
                "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
                (node.id, node.label, node.kind, json.dumps(node.data),
                 node.created, node.accessed, node.weight, json.dumps(tags))
            )
            self._fts_sync_node(node.id)
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

    def delete_many(self, node_ids: list[str], *, force: bool = False) -> int:
        """Batch-delete nodes with edge cleanup. Returns count of nodes deleted.

        Args:
            node_ids: List of node IDs to delete. Must be non-empty.
            force: If True, bypass the no-scope-delete guard.
                   (no-scope-mass-delete protection per memorywire spec)
        """
        if not node_ids and not force:
            raise ValueError(
                "delete_many requires non-empty node_ids "
                "(no-scope-mass-delete protection). Pass force=True to override."
            )
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
                self._fts_sync_node(nid)
        self.conn.commit()

    def search_by_tag(self, tag: str) -> list[Node]:  # noqa: F811
        """Return all nodes with a given tag (excludes quarantined)."""
        rows = self.conn.execute("SELECT * FROM nodes WHERE quarantined = 0").fetchall()
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
        self._tick("link", source_id,
                   {"source": source_id, "target": target_id, "relation": relation})

    def link_by_label(self, source_label: str, target_label: str, relation: str,
                      weight: float = 1.0) -> bool:
        """Connect two nodes by their labels.

        Resolves labels to node IDs and calls link().
        If either label is not found, does nothing and returns False.

        Args:
            source_label: Label of the source node
            target_label: Label of the target node
            relation: Edge relation type
            weight: Edge weight (default 1.0)

        Returns:
            True if linked, False if either node not found
        """
        src = self.conn.execute(
            "SELECT id FROM nodes WHERE label=? ORDER BY created DESC LIMIT 1",
            (source_label,)
        ).fetchone()
        tgt = self.conn.execute(
            "SELECT id FROM nodes WHERE label=? ORDER BY created DESC LIMIT 1",
            (target_label,)
        ).fetchone()
        if not src or not tgt:
            return False
        self.link(src["id"], tgt["id"], relation, weight)
        return True

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
            "SELECT * FROM nodes WHERE label LIKE ? AND quarantined = 0 ORDER BY weight DESC LIMIT ?",
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
        self._fts_delete_node(source_id)
        self.conn.execute("DELETE FROM nodes WHERE id=?", (source_id,))
        self._fts_sync_node(target_id)
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
                "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
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

    def search_by_label(self, pattern: str, limit: int = 50) -> list[Node]:
        """Find nodes whose label matches a regex pattern.

        Args:
            pattern: Python regex pattern (or simple substring if invalid regex).
            limit: max results.
        """
        import re
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            rows = self.conn.execute("SELECT * FROM nodes").fetchall()
            results = []
            for r in rows:
                if compiled.search(r["label"]):
                    results.append(Node(
                        r["id"], r["label"], r["kind"],
                        json.loads(r["data"]), r["created"], r["accessed"], r["weight"]
                    ))
                    if len(results) >= limit:
                        break
            return results
        except re.error:
            # Fallback to LIKE substring search
            rows = self.conn.execute(
                "SELECT * FROM nodes WHERE label LIKE ? LIMIT ?",
                (f"%{pattern}%", limit)
            ).fetchall()
            return [Node(r["id"], r["label"], r["kind"],
                         json.loads(r["data"]), r["created"], r["accessed"], r["weight"])
                    for r in rows]

    def search_labels(self, prefix: str, limit: int = 20) -> list[Node]:
        """Fast prefix search on node labels using SQLite LIKE.

        Args:
            prefix: label prefix to search for.
            limit: max results.
        """
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE label LIKE ? ORDER BY weight DESC LIMIT ?",
            (f"{prefix}%", limit)
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
                self._fts_sync_node(r["id"])
                count += 1
        self.conn.commit()
        return count

    def clear_tags(self, node_id: str) -> bool:
        """Remove all tags from a node. Returns True if node existed."""
        if not self.has_node(node_id):
            return False
        self.conn.execute("UPDATE nodes SET tags='[]' WHERE id=?", (node_id,))
        self._fts_sync_node(node_id)
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

    def prune_by_relevance(self, query: str, keep_k: int = 50, min_weight: float = 0.0) -> dict:
        """保留与 query 最相关的 keep_k 个节点，其余剪枝。

        使用 BM25 搜索找到最相关的节点，然后删除不在 top-k 中的节点。
        这是 "智能遗忘" — 忘掉无关的，记住相关的。

        Args:
            query: 相关性查询（如 "Python web development"）
            keep_k: 保留的节点数量
            min_weight: 额外保留 weight >= min_weight 的节点（0=不保留）

        Returns:
            {nodes_removed, edges_removed, kept_by_relevance, kept_by_weight}
        """
        # BM25 搜索找到相关节点
        try:
            results = self.search_bm25(query, limit=keep_k)
            relevant_ids = {r["node_id"] for r in results}
        except Exception:
            relevant_ids = set()

        # 额外保留高 weight 节点
        weight_ids = set()
        if min_weight > 0:
            rows = self.conn.execute(
                "SELECT id FROM nodes WHERE weight >= ?", (min_weight,)
            ).fetchall()
            weight_ids = {r["id"] for r in rows}

        keep_ids = relevant_ids | weight_ids
        all_ids = {r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()}
        remove_ids = all_ids - keep_ids

        if not remove_ids:
            return {"nodes_removed": 0, "edges_removed": 0,
                    "kept_by_relevance": len(relevant_ids),
                    "kept_by_weight": len(weight_ids - relevant_ids)}

        placeholders = ",".join("?" for _ in remove_ids)
        edge_count = self.conn.execute(
            f"SELECT COUNT(*) c FROM edges WHERE source IN ({placeholders}) OR target IN ({placeholders})",
            list(remove_ids) + list(remove_ids)
        ).fetchone()["c"]

        self.conn.execute(
            f"DELETE FROM edges WHERE source IN ({placeholders}) OR target IN ({placeholders})",
            list(remove_ids) + list(remove_ids)
        )
        self.conn.execute(
            f"DELETE FROM nodes WHERE id IN ({placeholders})",
            list(remove_ids)
        )
        # 同步 FTS
        for nid in remove_ids:
            self._fts_delete_node(nid)
        # 同步向量
        for nid in remove_ids:
            self.remove_embedding(nid)
        self.conn.commit()

        return {"nodes_removed": len(remove_ids), "edges_removed": edge_count,
                "kept_by_relevance": len(relevant_ids),
                "kept_by_weight": len(weight_ids - relevant_ids)}

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
        self._fts_sync_node(node_id)
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
            "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            (new_id, new_label or row["label"], row["kind"], row["data"],
             time.time(), time.time(), row["weight"], row["tags"])
        )
        self._fts_sync_node(new_id)
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

    def timeline(self, kind: str = None, since: float = None, until: float = None, limit: int = 50) -> list[Node]:
        """Return nodes sorted by creation time (newest first). Optional filters: kind, time range."""
        sql = "SELECT * FROM nodes WHERE 1=1"
        params = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        if since is not None:
            sql += " AND created>=?"
            params.append(since)
        if until is not None:
            sql += " AND created<=?"
            params.append(until)
        sql += " ORDER BY created DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                    json.loads(r["data"]), r["created"], r["accessed"], r["weight"]) for r in rows]

    def recommend(self, node_id: str, limit: int = 5) -> list[dict]:
        """Recommend related nodes via Jaccard similarity of shared neighbors."""
        # Get neighbors of target node
        my_neighbors = set()
        for row in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
            (node_id, node_id)
        ):
            my_neighbors.add(row[0])
        my_neighbors.discard(node_id)
        if not my_neighbors:
            return []
        # Score all other nodes by Jaccard similarity of their neighbor sets
        candidates = []
        all_ids = [r[0] for r in self.conn.execute("SELECT id FROM nodes WHERE id != ?", (node_id,))]
        for nid in all_ids:
            their_neighbors = set()
            for row in self.conn.execute(
                "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
                (nid, nid)
            ):
                their_neighbors.add(row[0])
            their_neighbors.discard(nid)
            if not their_neighbors:
                continue
            intersection = my_neighbors & their_neighbors
            union = my_neighbors | their_neighbors
            if intersection:
                jaccard = len(intersection) / len(union)
                candidates.append({"node_id": nid, "score": round(jaccard, 4)})
        candidates.sort(key=lambda x: x["score"], reverse=True)
        # Enrich with node info
        results = []
        for c in candidates[:limit]:
            node = self.get_node(c["node_id"])
            if node:
                results.append({"node": node, "score": c["score"]})
        return results

    def importance_rank(self, limit: int = 20, decay_hours: float = 168.0) -> list[dict]:
        """Rank nodes by composite importance: weight + degree + recency.

        Score = normalized_weight * 0.4 + normalized_degree * 0.3 + recency_score * 0.3
        recency_score = 1.0 if accessed within decay_hours, decays linearly to 0.
        """
        now = time.time()
        cutoff = now - decay_hours * 3600

        rows = self.conn.execute("""
            SELECT n.id, n.label, n.kind, n.weight, n.accessed,
                   (SELECT COUNT(*) FROM edges WHERE source=n.id OR target=n.id) AS deg
            FROM nodes n
            ORDER BY n.weight DESC
        """).fetchall()

        if not rows:
            return []

        max_weight = max(r["weight"] for r in rows) or 1.0
        max_deg = max(r["deg"] for r in rows) or 1

        results = []
        for r in rows:
            w_norm = r["weight"] / max_weight
            d_norm = r["deg"] / max_deg
            # Recency: 1.0 if accessed after cutoff, linear decay before
            if r["accessed"] >= cutoff:
                recency = 1.0
            else:
                elapsed = cutoff - r["accessed"]
                recency = max(0.0, 1.0 - elapsed / (decay_hours * 3600))

            score = w_norm * 0.4 + d_norm * 0.3 + recency * 0.3
            results.append({
                "node_id": r["id"],
                "label": r["label"],
                "kind": r["kind"],
                "importance": round(score, 4),
                "components": {
                    "weight": round(w_norm, 3),
                    "degree": round(d_norm, 3),
                    "recency": round(recency, 3),
                },
            })

        results.sort(key=lambda x: x["importance"], reverse=True)
        return results[:limit]

    def patch(self, diff: dict, source: 'MemoryGraph' = None) -> dict:
        """Apply a graph_diff result to sync this graph.

        Args:
            diff: output of graph_diff()
            source: the other graph (needed to fetch new nodes/edges)
        Returns dict with applied counts.
        """
        applied = {"nodes_added": 0, "nodes_removed": 0, "edges_added": 0, "edges_removed": 0, "fields_updated": 0}

        # Add nodes that only exist in other
        if source:
            for nid in diff.get("nodes_only_other", []):
                row = source.conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()
                if row:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
                        (row["id"], row["label"], row["kind"], row["data"], row["created"], row["accessed"], row["weight"], row["tags"])
                    )
                    applied["nodes_added"] += 1

            # Add edges that only exist in other
            for (src, tgt, rel) in diff.get("edges_only_other", []):
                self.conn.execute(
                    "INSERT OR IGNORE INTO edges (source,target,relation,weight) VALUES (?,?,?,1.0)",
                    (src, tgt, rel)
                )
                applied["edges_added"] += 1

        # Remove nodes that only exist in self
        for nid in diff.get("nodes_only_self", []):
            self.conn.execute("DELETE FROM edges WHERE source=? OR target=?", (nid, nid))
            self.conn.execute("DELETE FROM nodes WHERE id=?", (nid,))
            applied["nodes_removed"] += 1

        # Remove edges that only exist in self
        for (src, tgt, rel) in diff.get("edges_only_self", []):
            self.conn.execute("DELETE FROM edges WHERE source=? AND target=? AND relation=?", (src, tgt, rel))
            applied["edges_removed"] += 1

        # Apply field updates from modified nodes
        if source:
            for mod in diff.get("nodes_modified", []):
                nid = mod["id"]
                field = mod["field"]
                val = mod["other_val"]
                if field == "data":
                    self.conn.execute("UPDATE nodes SET data=? WHERE id=?", (json.dumps(val), nid))
                else:
                    self.conn.execute(f"UPDATE nodes SET {field}=? WHERE id=?", (val, nid))
                applied["fields_updated"] += 1

        self.conn.commit()
        return applied

    def stats_summary(self) -> dict:
        """One-call graph statistics dashboard."""
        node_count = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edge_count = self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        kind_dist = dict(self.conn.execute(
            "SELECT kind, COUNT(*) FROM nodes GROUP BY kind"
        ).fetchall())
        rel_dist = dict(self.conn.execute(
            "SELECT relation, COUNT(*) FROM edges GROUP BY relation"
        ).fetchall())
        avg_weight = self.conn.execute("SELECT AVG(weight) FROM nodes").fetchone()[0] or 0.0
        isolated = self.conn.execute("""
            SELECT COUNT(*) FROM nodes n
            WHERE NOT EXISTS (SELECT 1 FROM edges e WHERE e.source=n.id OR e.target=n.id)
        """).fetchone()[0]
        density = (2 * edge_count / (node_count * (node_count - 1))) if node_count > 1 else 0.0
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "kind_distribution": kind_dist,
            "relation_distribution": rel_dist,
            "avg_weight": round(avg_weight, 3),
            "isolated_nodes": isolated,
            "density": round(density, 4),
        }

    def anonymize(self) -> 'MemoryGraph':
        """Create a privacy-safe copy: strip labels and data, keep structure/kind/weights."""
        anon = MemoryGraph()
        id_map = {}
        for r in self.conn.execute("SELECT * FROM nodes").fetchall():
            new_id = str(uuid.uuid4())[:8]
            id_map[r["id"]] = new_id
            anon.conn.execute(
                "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
                (new_id, "***", r["kind"], "{}", r["created"], r["accessed"], r["weight"], "[]")
            )
        for r in self.conn.execute("SELECT * FROM edges").fetchall():
            anon.conn.execute(
                "INSERT INTO edges (source,target,relation,weight) VALUES (?,?,?,?)",
                (id_map.get(r["source"], r["source"]), id_map.get(r["target"], r["target"]), r["relation"], r["weight"])
            )
        anon.conn.commit()
        return anon

    def merge_graph(self, other: 'MemoryGraph', strategy: str = "union") -> dict:
        """Merge another graph into this one.

        Args:
            other: Source MemoryGraph to merge from.
            strategy: 'union' (add missing, skip existing) or 'update' (overwrite data/weight).

        Returns dict with counts: {nodes_added, nodes_updated, edges_added, edges_skipped}.
        """
        result = {"nodes_added": 0, "nodes_updated": 0, "edges_added": 0, "edges_skipped": 0}
        other_data = other.export_json()
        id_map = {}  # other_id → self_id (for edge remapping)

        for node in other_data["nodes"]:
            if not self.has_node(node["id"]):
                self.add(node["label"], node["kind"], node.get("data", {}), node.get("tags", []))
                # Reassign ID to match source
                self.conn.execute(
                    "UPDATE nodes SET id=?, weight=?, accessed=?, created=? WHERE rowid=last_insert_rowid()",
                    (node["id"], node.get("weight", 1.0), node.get("accessed", time.time()), node.get("created", time.time()))
                )
                self.conn.commit()
                id_map[node["id"]] = node["id"]
                result["nodes_added"] += 1
            elif strategy == "update":
                self.update_node(node["id"], label=node.get("label"), kind=node.get("kind"), data=node.get("data", {}))
                self.reweight(node["id"], node.get("weight", 1.0) - (self.get_node(node["id"]).weight or 0))
                id_map[node["id"]] = node["id"]
                result["nodes_updated"] += 1
            else:
                id_map[node["id"]] = node["id"]
                result["edges_skipped"] += 0  # node exists, not an edge skip

        for edge in other_data["edges"]:
            if edge["source"] in id_map and edge["target"] in id_map:
                if not self.is_linked(edge["source"], edge["target"], edge.get("relation")):
                    self.link(edge["source"], edge["target"], edge["relation"], edge.get("weight", 1.0))
                    result["edges_added"] += 1
        return result

    def diff_summary(self, other: 'MemoryGraph') -> dict:
        """High-level summary of differences between this graph and another.

        Returns dict with counts and sample labels for: only_in_self, only_in_other, common, label_diffs.
        """
        self_ids = {r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()}
        other_ids = {r["id"] for r in other.conn.execute("SELECT id FROM nodes").fetchall()}

        only_self = self_ids - other_ids
        only_other = other_ids - self_ids
        common = self_ids & other_ids

        # Check label differences in common nodes
        label_diffs = []
        for nid in common:
            s = self.get_node(nid)
            o = other.get_node(nid)
            if s and o and s.label != o.label:
                label_diffs.append({"id": nid, "self_label": s.label, "other_label": o.label})

        def _sample(ids, graph, limit=5):
            return [graph.get_node(nid).label for nid in list(ids)[:limit] if graph.get_node(nid)]

        return {
            "total_self": len(self_ids),
            "total_other": len(other_ids),
            "only_in_self": len(only_self),
            "only_in_other": len(only_other),
            "common": len(common),
            "sample_only_self": _sample(only_self, self),
            "sample_only_other": _sample(only_other, other),
            "label_diffs": label_diffs
        }

    def group_by(self, kind: str = None, tag: str = None) -> dict[str, list[Node]]:
        """Group nodes by kind or tag. Returns {group_key: [Node, ...]}.

        If kind is given, groups all nodes by their kind field.
        If tag is given, groups all nodes by each tag they have.
        """
        groups = defaultdict(list)
        if kind is not None:
            rows = self.conn.execute("SELECT id FROM nodes WHERE kind=?", (kind,)).fetchall()
            for r in rows:
                node = self.get_node(r["id"])
                if node:
                    groups[node.kind].append(node)
        elif tag is not None:
            rows = self.conn.execute("SELECT id, tags FROM nodes WHERE tags IS NOT NULL").fetchall()
            for r in rows:
                node_tags = json.loads(r["tags"]) if r["tags"] else []
                if tag in node_tags:
                    node = self.get_node(r["id"])
                    if node:
                        groups[tag].append(node)
        else:
            # Group all by kind
            rows = self.conn.execute("SELECT id, kind FROM nodes").fetchall()
            for r in rows:
                node = self.get_node(r["id"])
                if node:
                    groups[r["kind"]].append(node)
        return dict(groups)

    def link_strength(self, node_id: str) -> list[dict]:
        """Return all edges connected to node_id sorted by weight descending.

        Returns list of {source, target, relation, weight, partner_id, partner_label}.
        """
        if not self.has_node(node_id):
            return []
        results = []
        for e in self.edges_of(node_id, "both"):
            partner_id = e.target if e.source == node_id else e.source
            partner = self.get_node(partner_id)
            results.append({
                "source": e.source, "target": e.target,
                "relation": e.relation, "weight": e.weight,
                "partner_id": partner_id,
                "partner_label": partner.label if partner else "?"
            })
        results.sort(key=lambda x: x["weight"], reverse=True)
        return results

    def bfs_order(self, start_id: str, max_depth: int = 10) -> list[str]:
        """Return node ids in BFS traversal order from start_id."""
        if not self.has_node(start_id):
            return []
        visited = set()
        queue = [(start_id, 0)]
        order = []
        while queue:
            nid, depth = queue.pop(0)
            if nid in visited or depth > max_depth:
                continue
            visited.add(nid)
            order.append(nid)
            neighbors = []
            for r in self.conn.execute("SELECT target FROM edges WHERE source=?", (nid,)).fetchall():
                neighbors.append(r["target"])
            for r in self.conn.execute("SELECT source FROM edges WHERE target=?", (nid,)).fetchall():
                neighbors.append(r["source"])
            for nb in neighbors:
                if nb not in visited:
                    queue.append((nb, depth + 1))
        return order

    def dfs_order(self, start_id: str, max_depth: int = 10) -> list[str]:
        """Return node ids in DFS traversal order from start_id."""
        if not self.has_node(start_id):
            return []
        visited = set()
        order = []
        def _dfs(nid, depth):
            if nid in visited or depth > max_depth:
                return
            visited.add(nid)
            order.append(nid)
            for r in self.conn.execute("SELECT target FROM edges WHERE source=?", (nid,)).fetchall():
                _dfs(r["target"], depth + 1)
            for r in self.conn.execute("SELECT source FROM edges WHERE target=?", (nid,)).fetchall():
                _dfs(r["source"], depth + 1)
        _dfs(start_id, 0)
        return order

    def ancestor_graph(self, node_id: str, max_depth: int = 10) -> list[str]:
        """Return all ancestor node ids (following incoming edges) up to max_depth."""
        if not self.has_node(node_id):
            return []
        visited = set()
        queue = [(node_id, 0)]
        result = []
        while queue:
            nid, depth = queue.pop(0)
            if nid in visited or depth > max_depth:
                continue
            visited.add(nid)
            if nid != node_id:
                result.append(nid)
            for r in self.conn.execute("SELECT source FROM edges WHERE target=?", (nid,)).fetchall():
                if r["source"] not in visited:
                    queue.append((r["source"], depth + 1))
        return result

    def descendant_graph(self, node_id: str, max_depth: int = 10) -> list[str]:
        """Return all descendant node ids (following outgoing edges) up to max_depth."""
        if not self.has_node(node_id):
            return []
        visited = set()
        queue = [(node_id, 0)]
        result = []
        while queue:
            nid, depth = queue.pop(0)
            if nid in visited or depth > max_depth:
                continue
            visited.add(nid)
            if nid != node_id:
                result.append(nid)
            for r in self.conn.execute("SELECT target FROM edges WHERE source=?", (nid,)).fetchall():
                if r["target"] not in visited:
                    queue.append((r["target"], depth + 1))
        return result

    def random_node(self) -> Optional[Node]:
        """Return a random node from the graph, or None if empty."""
        row = self.conn.execute("SELECT id FROM nodes ORDER BY RANDOM() LIMIT 1").fetchone()
        return self.get_node(row["id"]) if row else None

    def unlink_all(self, node_id: str) -> int:
        """Remove all edges connected to node_id. Returns count of removed edges."""
        if not self.has_node(node_id):
            return 0
        count = self.conn.execute("SELECT COUNT(*) as c FROM edges WHERE source=? OR target=?",
                                   (node_id, node_id)).fetchone()["c"]
        self.conn.execute("DELETE FROM edges WHERE source=? OR target=?", (node_id, node_id))
        self.conn.commit()
        return count

    def edge_count(self, relation: str = None) -> int:
        """Total edge count, optionally filtered by relation."""
        if relation:
            return self.conn.execute("SELECT COUNT(*) as c FROM edges WHERE relation=?",
                                      (relation,)).fetchone()["c"]
        return self.conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]

    def edge_weight_stats(self, relation: str = None) -> dict:
        """Statistics about edge weights (min/max/mean/sum/count).

        Args:
            relation: optional filter by relation type.
        """
        if relation:
            rows = self.conn.execute(
                "SELECT weight FROM edges WHERE relation=?", (relation,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT weight FROM edges").fetchall()
        if not rows:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0}
        weights = [r["weight"] for r in rows]
        return {
            "count": len(weights),
            "min": min(weights),
            "max": max(weights),
            "mean": round(sum(weights) / len(weights), 4),
            "sum": round(sum(weights), 4),
        }

    def weight_distribution(self, bins: int = 10) -> list[dict]:
        """Histogram of node weight distribution.

        Args:
            bins: number of histogram bins.
        """
        rows = self.conn.execute("SELECT weight FROM nodes").fetchall()
        if not rows:
            return []
        weights = [r["weight"] for r in rows]
        w_min, w_max = min(weights), max(weights)
        if w_max == w_min:
            return [{"range": f"{w_min:.2f}", "count": len(weights)}]
        step = (w_max - w_min) / bins
        distribution = []
        for i in range(bins):
            lo = w_min + i * step
            hi = lo + step if i < bins - 1 else w_max
            count = sum(1 for w in weights if lo <= w < hi or (i == bins - 1 and w == hi))
            distribution.append({
                "range": f"{lo:.2f}-{hi:.2f}",
                "count": count,
            })
        return distribution

    def find_components(self) -> list[list[str]]:
        """Find all connected components (undirected). Returns list of node-id lists."""
        visited = set()
        components = []
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        for r in rows:
            nid = r["id"]
            if nid in visited:
                continue
            # BFS
            comp = []
            queue = [nid]
            while queue:
                cur = queue.pop(0)
                if cur in visited:
                    continue
                visited.add(cur)
                comp.append(cur)
                for e in self.conn.execute("SELECT target FROM edges WHERE source=?", (cur,)).fetchall():
                    if e["target"] not in visited:
                        queue.append(e["target"])
                for e in self.conn.execute("SELECT source FROM edges WHERE target=?", (cur,)).fetchall():
                    if e["source"] not in visited:
                        queue.append(e["source"])
            components.append(comp)
        return components

    def distance_matrix(self, node_ids: list[str] = None) -> dict[tuple[str, str], int]:
        """Compute shortest-path lengths between all pairs (BFS). Returns {(src, tgt): dist}.

        If node_ids given, only compute for those nodes.
        """
        ids = node_ids
        if ids is None:
            ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        dist = {}
        for src in ids:
            if not self.has_node(src):
                continue
            # BFS from src
            visited = {src}
            queue = [(src, 0)]
            while queue:
                cur, d = queue.pop(0)
                if cur in ids and (src, cur) not in dist:
                    dist[(src, cur)] = d
                for e in self.conn.execute("SELECT target FROM edges WHERE source=?", (cur,)).fetchall():
                    if e["target"] not in visited:
                        visited.add(e["target"])
                        queue.append((e["target"], d + 1))
                for e in self.conn.execute("SELECT source FROM edges WHERE target=?", (cur,)).fetchall():
                    if e["source"] not in visited:
                        visited.add(e["source"])
                        queue.append((e["source"], d + 1))
        return dist

    def cluster(self, kind: str, threshold: float = 0.4) -> list[dict]:
        """Cluster nodes of a given kind by label similarity.

        Uses normalized Levenshtein distance to group labels that are similar.
        Returns list of {representative: str, labels: list[str], node_ids: list[str], size: int}.
        Nodes with no similar neighbor form singleton clusters.
        """
        rows = self.conn.execute("SELECT id, label FROM nodes WHERE kind=?", (kind,)).fetchall()
        if not rows:
            return []

        # Simple Levenshtein distance
        def _levenshtein(a: str, b: str) -> int:
            if len(a) < len(b):
                return _levenshtein(b, a)
            if not b:
                return len(a)
            prev = list(range(len(b) + 1))
            for i, ca in enumerate(a):
                curr = [i + 1]
                for j, cb in enumerate(b):
                    curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
                prev = curr
            return prev[-1]

        # Normalize: max(len(a), len(b)) to get 0-1 similarity
        nodes = [(r["id"], r["label"]) for r in rows]
        parent = list(range(len(nodes)))  # Union-Find

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Compare all pairs — O(N^2) but fine for typical memory graphs
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                li, lj = nodes[i][1], nodes[j][1]
                max_len = max(len(li), len(lj), 1)
                dist = _levenshtein(li.lower(), lj.lower())
                similarity = 1.0 - dist / max_len
                if similarity >= (1.0 - threshold):
                    union(i, j)

        # Build clusters
        groups = defaultdict(list)
        for idx, (nid, label) in enumerate(nodes):
            groups[find(idx)].append((nid, label))

        result = []
        for members in groups.values():
            labels = [m[1] for m in members]
            # Use longest label as representative
            rep = max(labels, key=len)
            result.append({
                "representative": rep,
                "labels": sorted(labels),
                "node_ids": [m[0] for m in members],
                "size": len(members),
            })
        result.sort(key=lambda c: c["size"], reverse=True)
        return result

    def induced_subgraph(self, node_ids: list[str]) -> 'MemoryGraph':
        """Extract induced subgraph containing only specified node_ids and edges between them.

        Returns a new MemoryGraph instance with copied nodes and internal edges.
        Nodes not found in the current graph are skipped.
        """
        sub = MemoryGraph()
        id_set = set(node_ids)
        for nid in node_ids:
            node = self.get_node(nid)
            if not node:
                continue
            # Get tags from DB
            tags_row = self.conn.execute("SELECT tags FROM nodes WHERE id=?", (nid,)).fetchone()
            tags = json.loads(tags_row["tags"]) if tags_row and tags_row["tags"] else []
            sub.add(node.label, node.kind, node.data, tags)
            # Remap to original id
            found = sub.conn.execute("SELECT id FROM nodes WHERE label=? ORDER BY created DESC LIMIT 1", (node.label,)).fetchone()
            if found:
                sub.conn.execute("UPDATE nodes SET id=?, weight=? WHERE id=?", (nid, node.weight, found["id"]))
                sub.conn.commit()
        # Add edges between nodes in the set
        for nid in node_ids:
            if not self.has_node(nid):
                continue
            for e in self.edges_of(nid, "outgoing"):
                if e.target in id_set:
                    if sub.has_node(nid) and sub.has_node(e.target):
                        sub.link(nid, e.target, e.relation, e.weight)
        return sub

    def evolve(self, node_id: str, new_label: str = None, new_kind: str = None) -> Optional[Node]:
        """Evolve a node's label/kind and log the change to evolution_history.
        Returns the updated node, or None if not found or nothing to change."""
        node = self.get_node(node_id)
        if node is None:
            return None
        old_label, old_kind = node.label, node.kind
        nl = new_label if new_label is not None else old_label
        nk = new_kind if new_kind is not None else old_kind
        if nl == old_label and nk == old_kind:
            return node  # nothing to change
        self.conn.execute(
            "INSERT INTO evolution_log (node_id, old_label, new_label, old_kind, new_kind, timestamp) VALUES (?,?,?,?,?,?)",
            (node_id, old_label, nl, old_kind, nk, time.time())
        )
        self.conn.execute(
            "UPDATE nodes SET label=?, kind=? WHERE id=?",
            (nl, nk, node_id)
        )
        self.conn.commit()
        node.label, node.kind = nl, nk
        return node

    def evolution_history(self, node_id: str) -> list[dict]:
        """Return the evolution audit trail for a node, oldest first."""
        rows = self.conn.execute(
            "SELECT old_label, new_label, old_kind, new_kind, timestamp FROM evolution_log WHERE node_id=? ORDER BY id ASC",
            (node_id,)
        ).fetchall()
        return [
            {"old_label": r[0], "new_label": r[1], "old_kind": r[2], "new_kind": r[3], "timestamp": r[4]}
            for r in rows
        ]

    def revert_evolution(self, node_id: str, step_index: int) -> Optional[Node]:
        """Revert a node to a specific evolution step (0-based index into evolution_history).
        Removes all evolution_log entries after step_index and restores label/kind.
        Returns the reverted node, or None if not found / invalid step."""
        node = self.get_node(node_id)
        if node is None:
            return None
        history = self.evolution_history(node_id)
        if not history or step_index < 0 or step_index >= len(history):
            return None
        # The label/kind at step_index is the NEW state of that step.
        # We revert TO that step's new_label/new_kind.
        target = history[step_index]
        # Delete log entries after step_index
        rows = self.conn.execute(
            "SELECT id FROM evolution_log WHERE node_id=? ORDER BY id ASC",
            (node_id,)
        ).fetchall()
        ids_to_delete = [r[0] for r in rows[step_index + 1:]]
        if ids_to_delete:
            placeholders = ",".join("?" * len(ids_to_delete))
            self.conn.execute(
                f"DELETE FROM evolution_log WHERE id IN ({placeholders})",
                ids_to_delete
            )
        self.conn.execute(
            "UPDATE nodes SET label=?, kind=? WHERE id=?",
            (target["new_label"], target["new_kind"], node_id)
        )
        self.conn.commit()
        node.label = target["new_label"]
        node.kind = target["new_kind"]
        return node

    def batch_evolve(self, mapping: list[dict]) -> list[Optional[Node]]:
        """Evolve multiple nodes in one call. Each dict: {node_id, new_label?, new_kind?}.
        Returns list of updated nodes (None for failures). Single transaction."""
        results = []
        for item in mapping:
            nid = item.get("node_id")
            if nid is None:
                results.append(None)
                continue
            results.append(self.evolve(nid, item.get("new_label"), item.get("new_kind")))
        return results

    def is_dag(self) -> bool:
        """Check if the graph is a Directed Acyclic Graph (no cycles)."""
        visited = set()
        rec_stack = set()

        def _dfs(node_id):
            visited.add(node_id)
            rec_stack.add(node_id)
            rows = self.conn.execute(
                "SELECT target FROM edges WHERE source = ?", (node_id,)
            ).fetchall()
            for (target,) in rows:
                if target not in visited:
                    if _dfs(target):
                        return True
                elif target in rec_stack:
                    return True
            rec_stack.discard(node_id)
            return False

        all_nodes = [r[0] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        for nid in all_nodes:
            if nid not in visited:
                if _dfs(nid):
                    return False
        return True

    def topological_sort(self) -> list:
        """Return nodes in topological order (Kahn's algorithm). Returns [] if graph has cycles."""
        nodes = [r[0] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        in_degree = {nid: 0 for nid in nodes}
        adj = {nid: [] for nid in nodes}
        for src, tgt in self.conn.execute("SELECT source, target FROM edges").fetchall():
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        queue = [nid for nid in nodes if in_degree[nid] == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        return result if len(result) == len(nodes) else []

    def find_paths(self, from_id: int, to_id: int, max_depth: int = 10) -> list:
        """Find all simple paths between two nodes (DFS, max_depth limit)."""
        if not self.has_node(from_id) or not self.has_node(to_id):
            return []
        results = []

        def _dfs(current, target, path, visited):
            if len(path) - 1 > max_depth:
                return
            if current == target:
                results.append(list(path))
                return
            neighbors = self.conn.execute(
                "SELECT target FROM edges WHERE source = ?", (current,)
            ).fetchall()
            for (nxt,) in neighbors:
                if nxt not in visited:
                    visited.add(nxt)
                    path.append(nxt)
                    _dfs(nxt, target, path, visited)
                    path.pop()
                    visited.discard(nxt)

        _dfs(from_id, to_id, [from_id], {from_id})
        return results

    def jaccard_similarity(self, node_id1: int, node_id2: int) -> float:
        """Jaccard similarity of neighbor sets between two nodes."""
        n1 = set(r[0] for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
            (node_id1, node_id1)).fetchall())
        n2 = set(r[0] for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
            (node_id2, node_id2)).fetchall())
        if not n1 and not n2:
            return 0.0
        return len(n1 & n2) / len(n1 | n2)

    def neighborhood_overlap(self, node_id1: int, node_id2: int) -> float:
        """Overlap coefficient of neighbor sets (how much of the smaller set is shared)."""
        n1 = set(r[0] for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
            (node_id1, node_id1)).fetchall())
        n2 = set(r[0] for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
            (node_id2, node_id2)).fetchall())
        min_size = min(len(n1), len(n2))
        if min_size == 0:
            return 0.0
        return len(n1 & n2) / min_size

    def adamic_adar(self, node_id1: int, node_id2: int) -> float:
        """Adamic/Adar index — sum of 1/log(degree) over shared neighbors. Link prediction."""
        n1 = set(r[0] for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
            (node_id1, node_id1)).fetchall())
        n2 = set(r[0] for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
            (node_id2, node_id2)).fetchall())
        common = n1 & n2
        score = 0.0
        for c in common:
            deg = self.conn.execute(
                "SELECT COUNT(*) FROM edges WHERE source=? OR target=?", (c, c)
            ).fetchone()[0]
            if deg > 1:
                score += 1.0 / (1.0 + deg)  # avoid log(0), use deg+1
        return score

    # ── Edge Management ──────────────────────────────────

    def get_edge(self, source_id: str, target_id: str, relation: str) -> Optional[Edge]:
        """Get a specific edge by source, target, and relation. Returns None if not found."""
        row = self.conn.execute(
            "SELECT * FROM edges WHERE source=? AND target=? AND relation=?",
            (source_id, target_id, relation)
        ).fetchone()
        if not row:
            return None
        return Edge(row["source"], row["target"], row["relation"], row["weight"])

    def update_edge(self, source_id: str, target_id: str, relation: str,
                    weight: float = None, new_relation: str = None) -> Optional[Edge]:
        """Update an edge's weight and/or rename its relation. Returns updated Edge or None."""
        existing = self.get_edge(source_id, target_id, relation)
        if not existing:
            return None
        if new_relation and new_relation != relation:
            # Rename relation: insert new, delete old
            self.conn.execute(
                "INSERT INTO edges (source, target, relation, weight) VALUES (?, ?, ?, ?)",
                (source_id, target_id, new_relation, weight if weight is not None else existing.weight)
            )
            self.conn.execute(
                "DELETE FROM edges WHERE source=? AND target=? AND relation=?",
                (source_id, target_id, relation)
            )
        elif weight is not None:
            self.conn.execute(
                "UPDATE edges SET weight=? WHERE source=? AND target=? AND relation=?",
                (weight, source_id, target_id, relation)
            )
        self.conn.commit()
        return self.get_edge(source_id, target_id, new_relation or relation)

    def edge_properties(self, source_id: str, target_id: str, relation: str) -> Optional[dict]:
        """Get edge properties (metadata dict stored in data column). Returns None if edge not found."""
        row = self.conn.execute(
            "SELECT properties FROM edge_props WHERE source=? AND target=? AND relation=?",
            (source_id, target_id, relation)
        ).fetchone()
        if not row:
            return None
        return json.loads(row["properties"])

    def set_edge_properties(self, source_id: str, target_id: str, relation: str,
                            properties: dict) -> bool:
        """Set edge properties (upsert). Returns False if edge doesn't exist."""
        if not self.get_edge(source_id, target_id, relation):
            return False
        self.conn.execute(
            "INSERT OR REPLACE INTO edge_props (source, target, relation, properties) VALUES (?, ?, ?, ?)",
            (source_id, target_id, relation, json.dumps(properties))
        )
        self.conn.commit()
        return True

    def graph_hash(self) -> str:
        """Return a deterministic structural fingerprint (MD5) of the graph.
        Based on sorted node/edge data, not IDs."""
        import hashlib
        parts = []
        for r in self.conn.execute("SELECT label, kind, weight FROM nodes ORDER BY label").fetchall():
            parts.append(f"n:{r['label']}|{r['kind']}|{r['weight']:.4f}")
        for r in self.conn.execute(
            "SELECT source, target, relation, weight FROM edges ORDER BY source, target, relation"
        ).fetchall():
            parts.append(f"e:{r['source']}|{r['target']}|{r['relation']}|{r['weight']:.4f}")
        return hashlib.md5("\n".join(parts).encode()).hexdigest()

    def snapshot(self) -> dict:
        """Capture complete graph state as a dict (nodes + edges + evolution log)."""
        return {
            "nodes": [dict(r) for r in self.conn.execute("SELECT * FROM nodes").fetchall()],
            "edges": [dict(r) for r in self.conn.execute("SELECT * FROM edges").fetchall()],
            "evolution": [dict(r) for r in self.conn.execute("SELECT * FROM evolution_log").fetchall()],
            "edge_props": [dict(r) for r in self.conn.execute("SELECT * FROM edge_props").fetchall()],
        }

    def restore(self, snap: dict) -> None:
        """Restore graph to a previously captured snapshot state."""
        self.conn.executescript("DELETE FROM edge_props; DELETE FROM evolution_log; DELETE FROM edges; DELETE FROM nodes;")
        for n in snap.get("nodes", []):
            self.conn.execute(
                "INSERT INTO nodes (id, label, kind, data, created, accessed, weight, tags) VALUES (?,?,?,?,?,?,?,?)",
                (n["id"], n["label"], n["kind"], n["data"], n["created"], n["accessed"], n["weight"], n.get("tags", "[]"))
            )
        for e in snap.get("edges", []):
            self.conn.execute(
                "INSERT INTO edges (source, target, relation, weight) VALUES (?,?,?,?)",
                (e["source"], e["target"], e["relation"], e["weight"])
            )
        for ev in snap.get("evolution", []):
            self.conn.execute(
                "INSERT INTO evolution_log (id, node_id, old_label, new_label, old_kind, new_kind, timestamp) VALUES (?,?,?,?,?,?,?)",
                (ev["id"], ev["node_id"], ev["old_label"], ev["new_label"], ev["old_kind"], ev["new_kind"], ev["timestamp"])
            )
        for ep in snap.get("edge_props", []):
            self.conn.execute(
                "INSERT INTO edge_props (source, target, relation, properties) VALUES (?,?,?,?)",
                (ep["source"], ep["target"], ep["relation"], ep["properties"])
            )
        self.conn.commit()

    def dedup_nodes(self, similarity_threshold: float = 0.8) -> list[dict]:
        """Find and merge nodes with similar labels (Levenshtein-based).
        Returns list of merged groups: [{kept_id, merged_ids, label}]."""
        def _levenshtein(a, b):
            if len(a) < len(b):
                return _levenshtein(b, a)
            if not b:
                return len(a)
            prev = list(range(len(b) + 1))
            for i, ca in enumerate(a):
                curr = [i + 1]
                for j, cb in enumerate(b):
                    curr.append(min(prev[j + 1] + 1, curr[j] + 1,
                                    prev[j] + (0 if ca == cb else 1)))
                prev = curr
            return prev[-1]

        nodes = self.conn.execute("SELECT id, label FROM nodes").fetchall()
        merged_groups = []
        already_merged = set()

        for i, n1 in enumerate(nodes):
            if n1["id"] in already_merged:
                continue
            group = []
            for n2 in nodes[i + 1:]:
                if n2["id"] in already_merged:
                    continue
                max_len = max(len(n1["label"]), len(n2["label"]), 1)
                dist = _levenshtein(n1["label"], n2["label"])
                sim = 1.0 - dist / max_len
                if sim >= similarity_threshold and n1["id"] != n2["id"]:
                    group.append(n2)
            if group:
                for dup in group:
                    self.merge_nodes(dup["id"], n1["id"])
                    already_merged.add(dup["id"])
                merged_groups.append({
                    "kept_id": n1["id"],
                    "merged_ids": [d["id"] for d in group],
                    "label": n1["label"]
                })
        self.conn.commit()
        return merged_groups

    def merge_evolution(self, node_id: str) -> Optional[dict]:
        """Collapse all evolution steps for a node into a single summary entry.
        The summary records the original state → final state as one transition.
        Returns the summary dict, or None if node doesn't exist or has no history."""
        node = self.get_node(node_id)
        if node is None:
            return None
        history = self.evolution_history(node_id)
        if not history:
            return None
        first = history[0]
        last = history[-1]
        summary = {
            "node_id": node_id,
            "old_label": first["old_label"],
            "new_label": last["new_label"],
            "old_kind": first["old_kind"],
            "new_kind": last["new_kind"],
            "steps_collapsed": len(history),
            "timestamp": last["timestamp"],
        }
        # Delete all existing entries and insert single summary
        self.conn.execute("DELETE FROM evolution_log WHERE node_id=?", (node_id,))
        self.conn.execute(
            "INSERT INTO evolution_log (node_id, old_label, new_label, old_kind, new_kind, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (node_id, summary["old_label"], summary["new_label"],
             summary["old_kind"], summary["new_kind"], summary["timestamp"])
        )
        self.conn.commit()
        return summary

    def evolution_summary(self) -> dict:
        """Global evolution statistics across all nodes.
        Returns: {total_nodes, evolved_nodes, total_steps, most_evolved, avg_steps}."""
        total_nodes = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        evolved = self.conn.execute(
            "SELECT node_id, COUNT(*) as steps FROM evolution_log GROUP BY node_id ORDER BY steps DESC"
        ).fetchall()
        evolved_nodes = len(evolved)
        total_steps = sum(r["steps"] for r in evolved)
        most_evolved = [{"node_id": r["node_id"], "steps": r["steps"]} for r in evolved[:5]]
        avg_steps = round(total_steps / evolved_nodes, 2) if evolved_nodes > 0 else 0.0
        return {
            "total_nodes": total_nodes,
            "evolved_nodes": evolved_nodes,
            "total_steps": total_steps,
            "most_evolved": most_evolved,
            "avg_steps": avg_steps,
        }

    def bfs_shortest_path(self, start_id: str, end_id: str, weight_key: str = None) -> Optional[list]:
        """BFS最短路径。若 weight_key 给出则返回边权重的总和。"""
        if not self.has_node(start_id) or not self.has_node(end_id):
            return None
        if start_id == end_id:
            return [start_id]
        visited = {start_id}
        queue = [(start_id, [start_id])]
        while queue:
            current, path = queue.pop(0)
            for nb in self.neighbors(current):
                nid = str(nb.id)
                if nid in visited:
                    continue
                visited.add(nid)
                new_path = path + [nid]
                if nid == end_id:
                    return new_path
                queue.append((nid, new_path))
        return None

    def centrality_degree(self, node_id: str) -> Optional[float]:
        """度中心性 = degree / (n-1)，考虑双向边。"""
        if not self.has_node(node_id):
            return None
        n = self.stats()["nodes"]
        if n <= 1:
            return 0.0
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM edges WHERE source=? OR target=?", (node_id, node_id)
        ).fetchone()
        return row["c"] / (n - 1) if row else 0.0

    def reachability_count(self, node_id: str, max_depth: int = 10) -> int:
        """从 node_id 可达的不同节点数（BFS，不含自身）。"""
        if not self.has_node(node_id):
            return 0
        visited = {node_id}
        queue = [node_id]
        depth = 0
        while queue and depth < max_depth:
            depth += 1
            next_q = []
            for cur in queue:
                for nb in self.neighbors(cur):
                    nid = str(nb.id)
                    if nid not in visited:
                        visited.add(nid)
                        next_q.append(nid)
            queue = next_q
        return len(visited) - 1

    def graph_density(self) -> float:
        """图密度 = 实际边数 / 最大可能边数。有向图最大 n*(n-1)。"""
        stats = self.stats()
        n = stats["nodes"]
        if n <= 1:
            return 0.0
        e = stats["edges"]
        return e / (n * (n - 1))

    def reciprocity(self) -> float:
        """互惠率 = 双向边对数 / 总边数。"""
        stats = self.stats()
        e = stats["edges"]
        if e == 0:
            return 0.0
        rows = self.conn.execute("SELECT source, target, relation FROM edges").fetchall()
        pairs = set()
        reciprocal = 0
        for r in rows:
            key = (str(r["source"]), str(r["target"]), r["relation"])
            rev = (str(r["target"]), str(r["source"]), r["relation"])
            if rev in pairs:
                reciprocal += 1
            pairs.add(key)
        return reciprocal * 2 / e if reciprocal > 0 else 0.0

    def assortativity_degree(self) -> float:
        """度-度相关性: 正值=相似度节点互连(同配), 负值=异配。"""
        rows = self.conn.execute("SELECT source, target FROM edges").fetchall()
        if not rows:
            return 0.0
        deg = {}
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            deg[s] = deg.get(s, 0) + 1
            deg[t] = deg.get(t, 0) + 1
        # Also count edges from reverse direction (in-degree)
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            # total degree already counted both directions above
        m = len(rows)
        sum_jk = sum(deg.get(str(r["source"]), 0) * deg.get(str(r["target"]), 0) for r in rows)
        sum_j_plus_k = sum((deg.get(str(r["source"]), 0) + deg.get(str(r["target"]), 0)) ** 2 for r in rows)
        sigma_sq = sum_j_plus_k / (2 * m) - (sum_jk / m) ** 2 if m > 0 else 0
        if sigma_sq == 0:
            return 0.0
        r_val = (sum_jk / m - sum_j_plus_k / (4 * m * m)) / (sigma_sq / (2 * m)) if m > 0 else 0.0
        return max(-1.0, min(1.0, r_val))

    def clustering_coefficient(self, node_id: str) -> Optional[float]:
        """局部聚类系数: 邻居间实际边数 / 最大可能边数。"""
        if not self.has_node(node_id):
            return None
        nbs = set()
        for n in self.neighbors(node_id):
            nbs.add(str(n.id))
        for r in self.conn.execute("SELECT source FROM edges WHERE target=?", (node_id,)).fetchall():
            nbs.add(str(r["source"]))
        k = len(nbs)
        if k < 2:
            return 0.0
        nb_set = set(nbs)
        links = 0
        rows = self.conn.execute("SELECT source, target FROM edges").fetchall()
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            if s in nb_set and t in nb_set and s != t:
                links += 1
        return links / (k * (k - 1))

    def rich_club_coefficient(self, degree_k: int) -> float:
        """富人俱乐部系数: 度>=k的节点间实际边数/最大可能。"""
        rows = self.conn.execute(
            "SELECT source FROM edges UNION ALL SELECT target FROM edges"
        ).fetchall()
        deg = {}
        for r in rows:
            nid = str(r[0]) if not isinstance(r, dict) else str(r[list(r.keys())[0]])
            deg[nid] = deg.get(nid, 0) + 1
        rich = [nid for nid, d in deg.items() if d >= degree_k]
        nr = len(rich)
        if nr < 2:
            return 0.0
        rich_set = set(rich)
        links = 0
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        for r in edges:
            s, t = str(r["source"]), str(r["target"])
            if s in rich_set and t in rich_set:
                links += 1
        return links / (nr * (nr - 1))

    def global_clustering_coefficient(self) -> float:
        """全局聚类系数(传递性): 闭合三元组数 / 三元组总数。"""
        rows = self.conn.execute("SELECT source, target FROM edges").fetchall()
        if len(rows) < 2:
            return 0.0
        # Build adjacency (directed)
        adj = {}
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            adj.setdefault(s, set()).add(t)
        all_nodes = set(adj.keys())
        for targets in adj.values():
            all_nodes.update(targets)
        # Count triplets (a->b->c) and triangles (a->b->c and a->c)
        triplets = 0
        triangles = 0
        for a in adj:
            for b in adj.get(a, set()):
                for c in adj.get(b, set()):
                    if c != a:
                        triplets += 1
                        if c in adj.get(a, set()):
                            triangles += 1
        return triangles / triplets if triplets > 0 else 0.0

    def _modularity_simple(self, communities: dict[str, int]) -> float:
        """模块度 Q: 衡量社区划分质量。communities = {node_id: community_id}。"""
        rows = self.conn.execute("SELECT source, target FROM edges").fetchall()
        if not rows:
            return 0.0
        m = len(rows)
        # Degree of each node
        deg = {}
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            deg[s] = deg.get(s, 0) + 1
            deg[t] = deg.get(t, 0) + 1
        q = 0.0
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            c_s = communities.get(s, 0)
            c_t = communities.get(t, 0)
            if c_s == c_t:
                q += 1 - (deg.get(s, 0) * deg.get(t, 0)) / (2 * m)
        return q / (2 * m)

    # ── 生命周期 & 工具方法 ──────────────────────────────

    def clear(self) -> None:
        """删除所有节点和边，重置图为空状态。"""
        self.conn.execute("DELETE FROM edges")
        self.conn.execute("DELETE FROM edge_props")
        self.conn.execute("DELETE FROM evolution_log")
        self.conn.execute("DELETE FROM nodes")
        if getattr(self, '_fts_enabled', False):
            self.conn.execute("DELETE FROM nodes_fts")
        self.conn.commit()

    def is_empty(self) -> bool:
        """图是否为空（无节点）。"""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()
        return row["c"] == 0

    def count_edges(self) -> int:
        """返回图中边的总数。"""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()
        return row["c"]

    def batch_reweight(self, items: list[dict]) -> int:
        """批量调整权重。items = [{"id": ..., "delta": 0.1}, ...]。返回成功更新数。"""
        count = 0
        for item in items:
            nid = str(item["id"])
            delta = float(item["delta"])
            node = self.conn.execute(
                "SELECT id, weight FROM nodes WHERE id=?", (nid,)
            ).fetchone()
            if node is None:
                continue
            new_weight = max(0.0, node["weight"] + delta)
            self.conn.execute(
                "UPDATE nodes SET weight=? WHERE id=?",
                (new_weight, nid),
            )
            count += 1
        self.conn.commit()
        return count

    def to_adjacency_list(self) -> dict[str, list[dict]]:
        """导出邻接表表示。返回 {node_id: [{"target": ..., "relation": ..., "weight": ...}]}。"""
        adj: dict[str, list[dict]] = {}
        rows = self.conn.execute(
            "SELECT source, target, relation, weight FROM edges"
        ).fetchall()
        for r in rows:
            adj.setdefault(str(r["source"]), []).append({
                "target": str(r["target"]),
                "relation": r["relation"],
                "weight": r["weight"],
            })
        return adj

    def to_adjacency_matrix(self, weight_key: str = None) -> dict[str, dict]:
        """Export adjacency matrix as nested dict: {source: {target: value}}.

        Args:
            weight_key: if None, uses 1 for connected (binary).
                        'weight' uses edge weight.
                        Other values try edge properties JSON.
        """
        node_rows = self.conn.execute("SELECT id FROM nodes ORDER BY id").fetchall()
        node_ids = [str(r["id"]) for r in node_rows]
        matrix = {nid: {} for nid in node_ids}
        if weight_key is None or weight_key == "weight":
            edge_rows = self.conn.execute(
                "SELECT source, target, weight FROM edges"
            ).fetchall()
            for e in edge_rows:
                s, t = str(e["source"]), str(e["target"])
                matrix[s][t] = e["weight"] if weight_key == "weight" else 1
        else:
            # Try edge_properties method if available
            edge_rows = self.conn.execute(
                "SELECT source, target, relation, weight FROM edges"
            ).fetchall()
            for e in edge_rows:
                s, t = str(e["source"]), str(e["target"])
                props = self.edge_properties(s, t, e["relation"])
                matrix[s][t] = (props or {}).get(weight_key, 0)
        return matrix

    def node_distance(self, source_id: str, target_id: str) -> Optional[int]:
        """Shortest unweighted hop distance between two nodes. Returns None if unreachable.

        Alias for shortest_path length, but returns just the integer distance
        for quick connectivity checks.
        """
        path = self.shortest_path(source_id, target_id)
        if path is None:
            return None
        return len(path) - 1

    def serialize_dot(self) -> str:
        """导出为 Graphviz DOT 格式字符串，用于可视化工具集成。"""
        lines = ["digraph memory {"]
        lines.append('  node [shape=box];')
        nodes = self.conn.execute("SELECT id, label, kind, weight FROM nodes").fetchall()
        for n in nodes:
            safe_label = n["label"].replace('"', '\\"')
            lines.append(
                f'  "{n["id"]}" [label="{safe_label}", kind="{n["kind"]}", weight="{n["weight"]:.2f}"];'
            )
        edges = self.conn.execute(
            "SELECT source, target, relation, weight FROM edges"
        ).fetchall()
        for e in edges:
            safe_rel = e["relation"].replace('"', '\\"')
            lines.append(
                f'  "{e["source"]}" -> "{e["target"]}" [label="{safe_rel}", weight="{e["weight"]:.2f}"];'
            )
        lines.append("}")
        return "\n".join(lines)

    # ── Import formats (round-trip from serialize_*) ──────────────────────

    def _insert_node_raw(self, nid: str, label: str, kind: str = "", weight: float = 1.0, tags: list = None):
        """直接用指定 ID 插入节点（内部方法，用于 import）。"""
        now = time.time()
        self.conn.execute(
            "INSERT OR IGNORE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            (nid, label, kind, "{}", now, now, weight, json.dumps(tags or []))
        )
        self.conn.commit()

    def import_adjacency_list(self, adj: dict, *, merge: bool = False) -> dict:
        """从邻接表导入，兼容 to_adjacency_list() 的输出格式。

        Args:
            adj: {source_id: [{"target": ..., "relation": ..., "weight": ...}, ...]}
            merge: True=合入现有图, False=清空后导入

        Returns:
            {"nodes": N, "edges": M} 导入统计
        """
        if not merge:
            self.clear()
        node_count = edge_count = 0
        for src, edges in adj.items():
            if not self.has_node(src):
                self._insert_node_raw(src, src)
                node_count += 1
            for e in edges:
                tgt = e.get("target", e.get("target_id", ""))
                if not tgt:
                    continue
                rel = e.get("relation", "")
                w = e.get("weight", 1.0)
                if not self.has_node(tgt):
                    self._insert_node_raw(tgt, tgt)
                    node_count += 1
                self.link(src, tgt, rel, weight=w)
                edge_count += 1
        return {"nodes": node_count, "edges": edge_count}

    def import_edgelist(self, lines: list[str], *, merge: bool = False) -> dict:
        """从边列表导入。每行格式 'source_id target_id [weight]'。

        Args:
            lines: 边列表字符串列表
            merge: True=合入现有图(跳过已有节点), False=清空后导入

        Returns:
            {"nodes": N, "edges": M} 导入统计
        """
        if not merge:
            self.clear()
        node_count = edge_count = 0
        for raw in lines:
            parts = raw.strip().split()
            if len(parts) < 2:
                continue
            src, tgt = parts[0], parts[1]
            weight = float(parts[2]) if len(parts) >= 3 else 1.0
            if not self.has_node(src):
                self._insert_node_raw(src, src)
                node_count += 1
            if not self.has_node(tgt):
                self._insert_node_raw(tgt, tgt)
                node_count += 1
            self.link(src, tgt, "", weight=weight)
            edge_count += 1
        return {"nodes": node_count, "edges": edge_count}

    def import_cytoscape(self, data: dict, *, merge: bool = False) -> dict:
        """从 Cytoscape.js JSON 导入，兼容 serialize_cytoscape() 的输出格式。

        Args:
            data: Cytoscape.js JSON dict
            merge: True=合入现有图, False=清空后导入

        Returns:
            {"nodes": N, "edges": M} 导入统计
        """
        if not merge:
            self.clear()
        elements = data.get("elements", data)
        node_count = edge_count = 0

        # Import nodes first
        for n in elements.get("nodes", []):
            d = n.get("data", n)
            nid = str(d["id"])
            label = d.get("label", nid)
            kind = d.get("kind", "")
            weight = d.get("weight", 1.0)
            tags = d.get("tags", [])
            if merge and self.has_node(nid):
                continue
            self._insert_node_raw(nid, label, kind, weight, tags if isinstance(tags, list) else [tags] if tags else None)
            node_count += 1

        # Import edges
        for e in elements.get("edges", []):
            d = e.get("data", e)
            src = str(d["source"])
            tgt = str(d["target"])
            relation = d.get("relation", "")
            weight = d.get("weight", 1.0)
            self.link(src, tgt, relation, weight=weight)
            edge_count += 1

        return {"nodes": node_count, "edges": edge_count}

    def import_graphml(self, xml_string: str, *, merge: bool = False) -> dict:
        """从 GraphML XML 导入。

        Args:
            xml_string: GraphML XML 字符串
            merge: True=合入现有图, False=清空后导入

        Returns:
            {"nodes": N, "edges": M} 导入统计
        """
        import xml.etree.ElementTree as ET
        if not merge:
            self.clear()
        ns = "{http://graphml.graphdrawing.org/xmlns}"
        root = ET.fromstring(xml_string)

        # Build key mapping (key id -> attr name / type)
        key_map = {}
        for key in root.findall(f"{ns}key"):
            key_map[key.get("id")] = {
                "name": key.get("attr.name", key.get("id")),
                "for": key.get("for", "node"),
            }

        node_count = edge_count = 0
        graph = root.find(f"{ns}graph")
        if graph is None:
            return {"nodes": 0, "edges": 0}

        # Parse data values from <data key="..."> elements
        def parse_data(parent_el, target_type):
            vals = {}
            for d in parent_el.findall(f"{ns}data"):
                key_id = d.get("key")
                if key_id in key_map and key_map[key_id]["for"] == target_type:
                    vals[key_map[key_id]["name"]] = d.text or ""
            return vals

        # Import nodes
        for node_el in graph.findall(f"{ns}node"):
            nid = node_el.get("id")
            if merge and self.has_node(nid):
                continue
            attrs = parse_data(node_el, "node")
            label = attrs.get("label", nid)
            kind = attrs.get("kind", "")
            weight = float(attrs.get("weight", 1.0))
            self._insert_node_raw(nid, label, kind, weight)
            node_count += 1

        # Import edges
        for edge_el in graph.findall(f"{ns}edge"):
            src = edge_el.get("source")
            tgt = edge_el.get("target")
            attrs = parse_data(edge_el, "edge")
            relation = attrs.get("relation", "")
            weight = float(attrs.get("weight", 1.0))
            self.link(src, tgt, relation=relation, weight=weight)
            edge_count += 1

        return {"nodes": node_count, "edges": edge_count}

    def find_orphans(self) -> list[Node]:
        """返回所有没有边的孤立节点。"""
        rows = self.conn.execute(
            """SELECT n.* FROM nodes n
               WHERE NOT EXISTS (SELECT 1 FROM edges e WHERE e.source = n.id OR e.target = n.id)
               ORDER BY n.weight DESC"""
        ).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                    json.loads(r["data"]) if r["data"] else {},
                    r["created"], r["accessed"], r["weight"])
                for r in rows]

    # ── Graph theory algorithms ──────────────────────────────────────────

    def is_bipartite(self) -> bool:
        """检查图是否为二分图（BFS 染色法，将边视为无向）。"""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        color = {}  # node_id -> 0/1
        # Build undirected adjacency
        adj = {str(r["id"]): [] for r in nodes}
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            s, t = str(e["source"]), str(e["target"])
            adj.setdefault(s, []).append(t)
            adj.setdefault(t, []).append(s)
        for start in adj:
            if start in color:
                continue
            color[start] = 0
            queue = [start]
            while queue:
                u = queue.pop(0)
                for v in adj.get(u, []):
                    if v not in color:
                        color[v] = 1 - color[u]
                        queue.append(v)
                    elif color[v] == color[u]:
                        return False
        return True

    def find_bridges(self) -> list[tuple]:
        """寻找桥边（删除后使图不连通的边），基于 Tarjan 桥算法。

        将边视为无向。返回 [(source, target, relation), ...]。
        """
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        node_ids = [str(r["id"]) for r in nodes]
        # Build undirected adjacency with edge info
        adj = {nid: [] for nid in node_ids}
        edge_map = {}  # (u,v sorted) -> (source, target, relation)
        for e in self.conn.execute("SELECT source, target, relation FROM edges").fetchall():
            s, t, rel = str(e["source"]), str(e["target"]), e["relation"]
            adj.setdefault(s, []).append(t)
            adj.setdefault(t, []).append(s)
            key = tuple(sorted([s, t]))
            edge_map[key] = (s, t, rel)

        disc = {}
        low = {}
        timer = [0]
        bridges = []

        def dfs(u, parent):
            disc[u] = low[u] = timer[0]
            timer[0] += 1
            for v in adj.get(u, []):
                if v not in disc:
                    dfs(v, u)
                    low[u] = min(low[u], low[v])
                    if low[v] > disc[u]:
                        key = tuple(sorted([u, v]))
                        if key in edge_map:
                            bridges.append(edge_map[key])
                elif v != parent:
                    low[u] = min(low[u], disc[v])

        for nid in node_ids:
            if nid not in disc:
                dfs(nid, None)
        return bridges

    def articulation_points(self) -> list[str]:
        """寻找割点（删除后使图不连通的节点），基于 Tarjan 割点算法。

        将边视为无向。返回节点 ID 列表。
        """
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        node_ids = [str(r["id"]) for r in nodes]
        adj = {nid: set() for nid in node_ids}
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            s, t = str(e["source"]), str(e["target"])
            adj.setdefault(s, set()).add(t)
            adj.setdefault(t, set()).add(s)

        disc = {}
        low = {}
        timer = [0]
        ap = set()

        def dfs(u, parent):
            children = 0
            disc[u] = low[u] = timer[0]
            timer[0] += 1
            for v in adj.get(u, []):
                if v not in disc:
                    children += 1
                    dfs(v, u)
                    low[u] = min(low[u], low[v])
                    if parent is None and children > 1:
                        ap.add(u)
                    elif parent is not None and low[v] >= disc[u]:
                        ap.add(u)
                elif v != parent:
                    low[u] = min(low[u], disc[v])

        for nid in node_ids:
            if nid not in disc:
                dfs(nid, None)
        return sorted(ap)

    def neighbors_filtered(self, node_id: str, relation: str = None, min_weight: float = 0, direction: str = "out") -> list[Node]:
        """获取邻居节点，支持关系/权重/方向过滤。

        Args:
            node_id: 起始节点
            relation: 仅包含此关系的边（None=所有）
            min_weight: 最小权重阈值
            direction: 'out'(出边), 'in'(入边), 'both'(双向)

        Returns:
            邻居 Node 列表
        """
        if direction == "out":
            sql = """SELECT DISTINCT n.* FROM nodes n
                      JOIN edges e ON n.id=e.target WHERE e.source=?"""
            params = [node_id]
        elif direction == "in":
            sql = """SELECT DISTINCT n.* FROM nodes n
                      JOIN edges e ON n.id=e.source WHERE e.target=?"""
            params = [node_id]
        else:
            sql = """SELECT DISTINCT n.* FROM nodes n
                      JOIN edges e ON (n.id=e.target AND e.source=?)
                         OR (n.id=e.source AND e.target=?)"""
            params = [node_id, node_id]

        if relation is not None:
            sql += " AND e.relation=?"
            params.append(relation)
        if min_weight > 0:
            sql += " AND e.weight >= ?"
            params.append(min_weight)

        rows = self.conn.execute(sql, params).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                    json.loads(r["data"]) if r["data"] else {},
                    r["created"], r["accessed"], r["weight"])
                for r in rows]

    def edge_betweenness(self) -> dict:
        """计算边介数中心性（基于最短路径经过次数）。

        将图视为无向。返回 {(source, target): betweenness_score}。
        """
        nodes = [str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        edges = self.conn.execute("SELECT DISTINCT source, target FROM edges").fetchall()
        edge_set = set()
        adj = {n: set() for n in nodes}
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            key = tuple(sorted([s, t]))
            edge_set.add(key)
            adj.setdefault(s, set()).add(t)
            adj.setdefault(t, set()).add(s)

        betweenness = {e: 0.0 for e in edge_set}

        for source in nodes:
            # BFS: find shortest paths
            dist = {source: 0}
            sigma = {source: 1}  # number of shortest paths
            pred = {n: [] for n in nodes}
            queue = [source]
            for u in queue:
                for v in adj.get(u, []):
                    if v not in dist:
                        dist[v] = dist[u] + 1
                        sigma[v] = sigma[u]
                        pred[v] = [u]
                        queue.append(v)
                    elif dist[v] == dist[u] + 1:
                        sigma[v] += sigma[u]
                        pred[v].append(u)

            # Accumulation (Brandes' algorithm edge part)
            delta = {n: 0.0 for n in nodes}
            for w in reversed(queue):
                for v in pred[w]:
                    c = sigma[v] / sigma[w] * (1 + delta[w])
                    key = tuple(sorted([v, w]))
                    if key in betweenness:
                        betweenness[key] += c
                    delta[v] += c

        # Undirected: divide by 2
        for k in betweenness:
            betweenness[k] /= 2.0
        return betweenness

    def find_roots(self) -> list[Node]:
        """返回无入边的节点（有向图的根），包括孤立节点。"""
        rows = self.conn.execute(
            """SELECT n.* FROM nodes n
               WHERE NOT EXISTS (SELECT 1 FROM edges e_in WHERE e_in.target = n.id)
               ORDER BY n.weight DESC"""
        ).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                    json.loads(r["data"]) if r["data"] else {},
                    r["created"], r["accessed"], r["weight"])
                for r in rows]

    def find_leaves(self) -> list[Node]:
        """返回无出边的节点（有向图的叶），包括孤立节点。"""
        rows = self.conn.execute(
            """SELECT n.* FROM nodes n
               WHERE NOT EXISTS (SELECT 1 FROM edges e_out WHERE e_out.source = n.id)
               ORDER BY n.weight DESC"""
        ).fetchall()
        return [Node(r["id"], r["label"], r["kind"],
                    json.loads(r["data"]) if r["data"] else {},
                    r["created"], r["accessed"], r["weight"])
                for r in rows]

    def has_cycle(self) -> bool:
        """检测图中是否存在环（基于 DFS 三色标记法）。"""
        nodes = [str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        adj: dict[str, list[str]] = {}
        for r in self.conn.execute("SELECT source, target FROM edges").fetchall():
            adj.setdefault(str(r["source"]), []).append(str(r["target"]))
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in nodes}

        def _visit(start):
            stack = [(start, iter(adj.get(start, [])))]
            color[start] = GRAY
            while stack:
                node, it = stack[-1]
                found = False
                for nb in it:
                    if color.get(nb, WHITE) == GRAY:
                        return True
                    if color.get(nb, WHITE) == WHITE:
                        color[nb] = GRAY
                        stack.append((nb, iter(adj.get(nb, []))))
                        found = True
                        break
                if not found:
                    color[node] = BLACK
                    stack.pop()
            return False

        for nid in nodes:
            if color[nid] == WHITE:
                if _visit(nid):
                    return True
        return False

    # ── 进阶图分析 ────────────────────────────────────────

    def degree_histogram(self) -> dict[int, int]:
        """度分布直方图。返回 {degree: count}。"""
        rows = self.conn.execute(
            """SELECT id, (
                SELECT COUNT(*) FROM edges e WHERE e.source = n.id OR e.target = n.id
               ) AS deg FROM nodes n"""
        ).fetchall()
        hist: dict[int, int] = {}
        for r in rows:
            d = r["deg"]
            hist[d] = hist.get(d, 0) + 1
        return hist

    def degree_sequence(self, order: str = "desc") -> list[int]:
        """返回所有节点的度数序列（排序后）。"""
        rows = self.conn.execute(
            """SELECT (
                SELECT COUNT(*) FROM edges e WHERE e.source = n.id OR e.target = n.id
               ) AS deg FROM nodes n"""
        ).fetchall()
        degs = [r["deg"] for r in rows]
        return sorted(degs, reverse=(order == "desc"))

    def largest_component_size(self) -> int:
        """最大连通分量大小（基于 Union-Find）。"""
        nodes = [str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        if not nodes:
            return 0
        parent = {nid: nid for nid in nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        for e in edges:
            union(str(e["source"]), str(e["target"]))

        comp_size: dict[str, int] = {}
        for nid in nodes:
            root = find(nid)
            comp_size[root] = comp_size.get(root, 0) + 1
        return max(comp_size.values()) if comp_size else 0

    def community_detection_greedy(self) -> dict[str, int]:
        """贪心社区检测（基于边密度）。返回 {node_id: community_id}。

        简单方法：按度数降序分配，高优先级节点吸引邻居。
        """
        nodes = [str(r["id"]) for r in
                 self.conn.execute("SELECT id FROM nodes ORDER BY weight DESC").fetchall()]
        if not nodes:
            return {}
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        adj: dict[str, set[str]] = {nid: set() for nid in nodes}
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in adj:
                adj[s].add(t)
            if t in adj:
                adj[t].add(s)

        community = {}
        next_cid = 0
        for nid in nodes:
            if nid in community:
                continue
            # Check if any neighbor already has a community
            neighbor_comms = {community[nb] for nb in adj[nid] if nb in community}
            if neighbor_comms:
                # Join the most connected community (first one for simplicity)
                community[nid] = min(neighbor_comms)
            else:
                community[nid] = next_cid
                next_cid += 1
        return community

    def detect_communities_leiden(self, resolution: float = 1.0,
                                  max_iterations: int = 10, seed: int = 42) -> dict[str, int]:
        """Leiden community detection algorithm (full 3-phase implementation).

        Three phases: Fast Local Move → Refinement → Aggregation.
        Guarantees well-connected communities (unlike Louvain).

        The Aggregation phase contracts communities into super-nodes and
        re-runs, producing a hierarchy that improves quality at each level.

        Args:
            resolution: γ parameter. <1 → larger communities, >1 → smaller communities.
            max_iterations: max outer iterations (move + refine + aggregate cycles).
            seed: random seed for reproducibility.

        Returns:
            {node_id: community_id} mapping.
        """
        import random as _rng
        _rng.seed(seed)

        raw_nodes = [str(r["id"]) for r in
                     self.conn.execute("SELECT id FROM nodes").fetchall()]
        if not raw_nodes:
            return {}

        raw_edges = self.conn.execute(
            "SELECT source, target, weight FROM edges").fetchall()

        # Build initial adjacency
        orig_adj: dict[str, dict[str, float]] = {n: {} for n in raw_nodes}
        for e in raw_edges:
            s, t, w = str(e["source"]), str(e["target"]), float(e["weight"] or 1.0)
            orig_adj[s][t] = orig_adj[s].get(t, 0.0) + w
            orig_adj[t][s] = orig_adj[t].get(s, 0.0) + w

        # Track original members of each super-node
        super_members: dict[str, set[str]] = {n: {n} for n in raw_nodes}
        cur_nodes = list(raw_nodes)
        cur_adj = orig_adj

        for _level in range(max_iterations):
            if len(cur_nodes) <= 1:
                break

            m2 = sum(sum(d.values()) for d in cur_adj.values())
            if m2 == 0:
                break

            degree = {n: sum(cur_adj[n].values()) for n in cur_nodes}

            # Initialize: each node in its own community
            community = {n: i for i, n in enumerate(cur_nodes)}
            comm_degree: dict[int, float] = {}
            for n in cur_nodes:
                comm_degree[community[n]] = comm_degree.get(community[n], 0.0) + degree[n]

            # === Phase 1: Fast Local Move ===
            queue = list(cur_nodes)
            _rng.shuffle(queue)
            in_queue = set(queue)
            moved_any = False

            while queue:
                node = queue.pop(0)
                in_queue.discard(node)
                cur = community[node]
                k_i = degree[node]

                # Compute edge weights to each neighboring community
                # (including current, for proper ΔQ)
                neighbor_comms: dict[int, float] = {}
                for nb in cur_adj[node]:
                    c = community[nb]
                    neighbor_comms[c] = neighbor_comms.get(c, 0.0) + cur_adj[node][nb]

                k_i_in_cur = neighbor_comms.get(cur, 0.0)
                sigma_cur = comm_degree.get(cur, 0.0) - k_i  # exclude self

                best_comm, best_delta = cur, 0.0
                for c, k_i_in_c in neighbor_comms.items():
                    if c == cur:
                        continue
                    sigma_c = comm_degree.get(c, 0.0)
                    # ΔQ = (k_i_in_c - k_i_in_cur) - γ * k_i * (Σ_c - (Σ_cur - k_i)) / m2
                    delta = ((k_i_in_c - k_i_in_cur)
                             - resolution * k_i * (sigma_c - sigma_cur) / m2)
                    if delta > best_delta:
                        best_delta = delta
                        best_comm = c

                if best_comm != cur:
                    comm_degree[cur] -= k_i
                    if comm_degree[cur] <= 0:
                        del comm_degree[cur]
                    comm_degree[best_comm] = comm_degree.get(best_comm, 0.0) + k_i
                    community[node] = best_comm
                    moved_any = True
                    for nb in cur_adj[node]:
                        if nb not in in_queue and community[nb] != best_comm:
                            queue.append(nb)
                            in_queue.add(nb)

            # Check convergence
            unique_comms = set(community.values())
            if not moved_any or len(unique_comms) == len(cur_nodes):
                break

            # === Phase 2: Refinement (connectivity guarantee) ===
            comm_members: dict[int, list[str]] = {}
            for n in cur_nodes:
                comm_members.setdefault(community[n], []).append(n)

            for cid, members in comm_members.items():
                if len(members) <= 1:
                    continue
                member_set = set(members)
                sub_adj: dict[str, set[str]] = {n: set() for n in members}
                for n in members:
                    for nb in cur_adj[n]:
                        if nb in member_set:
                            sub_adj[n].add(nb)

                # BFS connectivity check
                visited = set()
                queue_bfs = [members[0]]
                visited.add(members[0])
                while queue_bfs:
                    bfs_node = queue_bfs.pop(0)
                    for nb in sub_adj[bfs_node]:
                        if nb not in visited:
                            visited.add(nb)
                            queue_bfs.append(nb)

                if len(visited) < len(members):
                    max_comm = max(community.values()) + 1
                    for n in members:
                        if n not in visited:
                            comm_degree[community[n]] -= degree[n]
                            comm_degree[max_comm] = comm_degree.get(max_comm, 0.0) + degree[n]
                            community[n] = max_comm

            # === Phase 3: Aggregation ===
            unique_comms = set(community.values())
            comm_to_new: dict[int, str] = {cid: f"L{_level}_{cid}" for cid in unique_comms}

            # Build aggregated graph (with self-loops for internal edges)
            new_adj: dict[str, dict[str, float]] = {comm_to_new[c]: {} for c in unique_comms}
            for n in cur_nodes:
                src_new = comm_to_new[community[n]]
                for nb, w in cur_adj[n].items():
                    tgt_new = comm_to_new[community[nb]]
                    new_adj[src_new][tgt_new] = new_adj[src_new].get(tgt_new, 0.0) + w

            new_super: dict[str, set[str]] = {comm_to_new[c]: set() for c in unique_comms}
            for n in cur_nodes:
                new_super[comm_to_new[community[n]]].update(super_members[n])

            super_members = new_super
            cur_nodes = list(new_adj.keys())
            cur_adj = new_adj

        # Map back to original node IDs
        result: dict[str, int] = {}
        for final_id, (super_node, orig_ids) in enumerate(super_members.items()):
            for orig_id in orig_ids:
                result[orig_id] = final_id

        return result

    def modularity(self, communities: dict[str, int] = None) -> float:
        """Compute modularity Q for a community partition.

        Args:
            communities: {node_id: community_id}. If None, uses label propagation.

        Returns:
            Modularity value (-0.5 to 1.0, higher is better).
        """
        if communities is None:
            comm_map = self.community_detect()
            communities = {}
            for label, members in comm_map.items():
                for nid in members:
                    communities[nid] = label

        edges = self.conn.execute(
            "SELECT source, target, weight FROM edges").fetchall()
        nodes = [str(r["id"]) for r in
                 self.conn.execute("SELECT id FROM nodes").fetchall()]

        if not nodes or not edges:
            return 0.0

        m = sum(float(e["weight"] or 1.0) for e in edges)
        if m == 0:
            return 0.0

        degree = {n: 0.0 for n in nodes}
        adj: dict[str, dict[str, float]] = {n: {} for n in nodes}
        for e in edges:
            s, t, w = str(e["source"]), str(e["target"]), float(e["weight"] or 1.0)
            adj[s][t] = adj[s].get(t, 0.0) + w
            adj[t][s] = adj[t].get(s, 0.0) + w
            degree[s] += w
            degree[t] += w

        Q = 0.0
        for i, ni in enumerate(nodes):
            for nj in nodes[i+1:]:
                if communities.get(ni) == communities.get(nj):
                    A_ij = adj[ni].get(nj, 0.0)
                    Q += A_ij - degree[ni] * degree[nj] / (2 * m)
        return Q / (2 * m)

    def community_partition(self, algorithm: str = "leiden", resolution: float = 1.0,
                             seed: int = 42) -> dict[str, int]:
        """Detect communities and return {node_id: community_id} mapping.

        Args:
            algorithm: "leiden", "greedy", or "lp" (label propagation).
            resolution: Leiden resolution parameter (only for leiden).
            seed: Random seed (only for leiden).

        Returns:
            {node_id: community_id} dict.
        """
        if algorithm == "leiden":
            return self.detect_communities_leiden(resolution=resolution, seed=seed)
        elif algorithm == "greedy":
            return self.community_detection_greedy()
        else:
            # Label propagation returns {label: [nodes]}, invert to {node: label}
            lp_result = self.community_detect()
            return {nid: label for label, nids in lp_result.items() for nid in nids}

    def community_quality_report(self, algorithm: str = "leiden",
                                 resolution: float = 1.0) -> dict:
        """Generate a comprehensive community detection quality report.

        Compares algorithms and reports modularity, community count, size distribution.

        Args:
            algorithm: Primary algorithm for the report.
            resolution: Leiden resolution parameter.

        Returns dict with: algorithm, num_communities, modularity, sizes, coverage, connectivity.
        """
        nodes = [str(r["id"]) for r in
                 self.conn.execute("SELECT id FROM nodes").fetchall()]
        if not nodes:
            return {"algorithm": algorithm, "num_communities": 0, "modularity": 0.0,
                    "sizes": [], "coverage": 0.0, "connectivity": True}

        if algorithm == "leiden":
            partition = self.detect_communities_leiden(resolution=resolution)
        elif algorithm == "greedy":
            partition = self.community_detection_greedy()
        else:
            lp = self.community_detect()
            partition = {nid: label for label, nids in lp.items() for nid in nids}

        num_comms = len(set(partition.values()))
        q = self.modularity(communities=partition)
        sizes = {}
        for cid in partition.values():
            sizes[cid] = sizes.get(cid, 0) + 1
        size_values = sorted(sizes.values(), reverse=True)

        # Coverage: fraction of nodes assigned
        coverage = len(partition) / len(nodes) if nodes else 0.0

        # Check connectivity of each community
        all_connected = True
        for cid, members_ids in sizes.items():
            if members_ids <= 1:
                continue
            member_list = [n for n in nodes if partition.get(n) == cid]
            member_set = set(member_list)
            visited = set()
            queue = [member_list[0]]
            visited.add(member_list[0])
            while queue:
                cur = queue.pop(0)
                for r in self.conn.execute(
                    "SELECT source FROM edges WHERE target=? UNION SELECT target FROM edges WHERE source=?",
                    (cur, cur)).fetchall():
                    nb = str(r[0])
                    if nb in member_set and nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
            if len(visited) < len(member_list):
                all_connected = False
                break

        return {
            "algorithm": algorithm,
            "num_communities": num_comms,
            "modularity": round(q, 4),
            "sizes": size_values,
            "min_size": min(size_values) if size_values else 0,
            "max_size": max(size_values) if size_values else 0,
            "coverage": round(coverage, 4),
            "connectivity": all_connected,
        }

    def community_hierarchy(self, resolutions: list[float] = None,
                            seed: int = 42) -> list[dict]:
        """Detect communities at multiple resolution levels for hierarchical analysis.

        Runs Leiden at different γ values to build a multi-granularity view.
        Lower γ → fewer/larger communities; higher γ → more/smaller communities.

        Args:
            resolutions: list of γ values. Default: [0.3, 0.5, 1.0, 1.5, 2.0].
            seed: random seed for reproducibility.

        Returns list of dicts (one per resolution) with:
            resolution, communities {node: cid}, num_communities, modularity, sizes.
        """
        if resolutions is None:
            resolutions = [0.3, 0.5, 1.0, 1.5, 2.0]

        results = []
        for gamma in resolutions:
            partition = self.detect_communities_leiden(
                resolution=gamma, seed=seed)
            num_c = len(set(partition.values()))
            q = self.modularity(partition)
            sizes = {}
            for cid in partition.values():
                sizes[cid] = sizes.get(cid, 0) + 1
            results.append({
                "resolution": gamma,
                "communities": partition,
                "num_communities": num_c,
                "modularity": round(q, 4),
                "sizes": sorted(sizes.values(), reverse=True),
            })
        return results

    def incremental_modularity(self, node_id: str, target_community: int,
                                communities: dict[str, int] = None,
                                resolution: float = 1.0) -> float:
        """Compute the modularity gain ΔQ for moving a node to a different community.

        Useful for evaluating community assignments without executing the move.

        Args:
            node_id: node to evaluate.
            target_community: community ID to move to.
            communities: {node_id: community_id} mapping. If None, auto-detects via Leiden.
            resolution: γ parameter.

        Returns:
            ΔQ value. Positive = beneficial move, negative = harmful.
        """
        if communities is None:
            communities = self.detect_communities_leiden(resolution=resolution)

        if node_id not in communities:
            return 0.0

        current = communities[node_id]
        if current == target_community:
            return 0.0

        edges = self.conn.execute(
            "SELECT source, target, weight FROM edges").fetchall()

        adj: dict[str, dict[str, float]] = defaultdict(dict)
        degree: dict[str, float] = defaultdict(float)
        total_weight = 0.0
        for e in edges:
            s, t, w = str(e["source"]), str(e["target"]), float(e["weight"] or 1.0)
            adj[s][t] = adj[s].get(t, 0.0) + w
            adj[t][s] = adj[t].get(s, 0.0) + w
            degree[s] += w
            degree[t] += w
            total_weight += w

        m2 = total_weight * 2.0 if total_weight > 0 else 1.0

        k_i = degree.get(node_id, 0.0)
        k_i_in_target = sum(w for nb, w in adj.get(node_id, {}).items()
                            if communities.get(nb) == target_community)
        k_i_in_current = sum(w for nb, w in adj.get(node_id, {}).items()
                             if communities.get(nb) == current)

        sigma_target = sum(degree[n] for n, c in communities.items() if c == target_community)
        sigma_current = sum(degree[n] for n, c in communities.items() if c == current)

        return ((k_i_in_target - k_i_in_current)
                - resolution * k_i * (sigma_target - sigma_current + k_i) / m2)

    def community_merge(self, comm_a: int, comm_b: int,
                        communities: dict[str, int] = None) -> dict[str, int]:
        """Merge two communities into one.

        Reassigns all nodes in comm_b to comm_a.

        Args:
            comm_a: community ID to merge into.
            comm_b: community ID to merge from.
            communities: partition dict. If None, auto-detects via Leiden.

        Returns:
            Updated {node_id: community_id} mapping.
        """
        if communities is None:
            communities = self.detect_communities_leiden()

        if comm_a == comm_b:
            return communities

        result = dict(communities)
        for nid, cid in result.items():
            if cid == comm_b:
                result[nid] = comm_a
        return result

    def community_split(self, comm_id: int,
                        communities: dict[str, int] = None,
                        resolution: float = 2.0,
                        seed: int = 42) -> dict[str, int]:
        """Split a community into sub-communities using higher-resolution Leiden.

        Extracts the subgraph induced by the community, then runs Leiden at
        higher resolution to find internal structure.

        Args:
            comm_id: community ID to split.
            communities: partition dict. If None, auto-detects via Leiden.
            resolution: γ for sub-graph detection (higher = more communities).
            seed: random seed.

        Returns:
            Updated {node_id: community_id} with new IDs for split communities.
        """
        if communities is None:
            communities = self.detect_communities_leiden()

        members = [nid for nid, cid in communities.items() if cid == comm_id]
        if len(members) <= 1:
            return communities

        # Get max community ID for generating new ones
        max_cid = max(communities.values())

        # Build member set for fast lookup
        member_set = set(members)

        # Get edges within the community
        edges = self.conn.execute(
            "SELECT source, target, weight FROM edges").fetchall()
        sub_edges = []
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in member_set and t in member_set:
                sub_edges.append(e)

        if len(sub_edges) < 2:
            return communities  # Can't split with < 2 internal edges

        # Build temporary subgraph adjacency
        sub_adj: dict[str, dict[str, float]] = {n: {} for n in members}
        total_w = 0.0
        for e in sub_edges:
            s, t, w = str(e["source"]), str(e["target"]), float(e["weight"] or 1.0)
            sub_adj[s][t] = sub_adj[s].get(t, 0.0) + w
            sub_adj[t][s] = sub_adj[t].get(s, 0.0) + w
            total_w += w

        if total_w == 0:
            return communities

        # Simple split: find connected components first
        # If already disconnected, split along component boundaries
        visited: set[str] = set()
        components: list[set[str]] = []
        for node in members:
            if node not in visited:
                component: set[str] = set()
                queue = [node]
                while queue:
                    cur = queue.pop(0)
                    if cur in visited:
                        continue
                    visited.add(cur)
                    component.add(cur)
                    for nb in sub_adj[cur]:
                        if nb not in visited:
                            queue.append(nb)
                components.append(component)

        if len(components) <= 1:
            # Subgraph is connected — try modularity-based split
            # Use simple degree-based splitting: high-degree nodes as seeds
            import random as _rng
            _rng.seed(seed)
            degree = {n: sum(sub_adj[n].values()) for n in members}
            # Sort by degree descending, pick top 2 as seeds
            sorted_nodes = sorted(members, key=lambda n: degree[n], reverse=True)
            if len(sorted_nodes) < 2:
                return communities
            seed_a, seed_b = sorted_nodes[0], sorted_nodes[1]
            # Assign each node to nearest seed by edge weight
            assign_a, assign_b = {seed_a}, {seed_b}
            for n in members:
                if n in (seed_a, seed_b):
                    continue
                w_a = sub_adj[n].get(seed_a, 0.0)
                w_b = sub_adj[n].get(seed_b, 0.0)
                if w_a >= w_b:
                    assign_a.add(n)
                else:
                    assign_b.add(n)
            components = [assign_a, assign_b]

        # Assign new community IDs
        result = dict(communities)
        for i, comp in enumerate(components):
            new_cid = max_cid + 1 + i
            for nid in comp:
                result[nid] = new_cid

        return result

    def community_cohesion_score(self, communities: dict[str, int] = None) -> dict[int, float]:
        """Compute a cohesion score for each community.

        Cohesion = internal_edge_density × avg_internal_weight × size_factor.
        Higher = more tightly-knit community.

        Args:
            communities: {node_id: community_id}. If None, auto-detects.

        Returns:
            {community_id: score 0..1}.
        """
        if communities is None:
            communities = self.detect_communities_leiden()

        if not communities:
            return {}

        edges = self.conn.execute(
            "SELECT source, target, weight FROM edges").fetchall()

        # Group nodes by community
        comm_nodes: dict[int, set[str]] = {}
        for nid, cid in communities.items():
            comm_nodes.setdefault(cid, set()).add(nid)

        # Count internal edges and weights per community
        internal_edges: dict[int, float] = defaultdict(float)
        internal_weight: dict[int, float] = defaultdict(float)
        for e in edges:
            s, t, w = str(e["source"]), str(e["target"]), float(e["weight"] or 1.0)
            if communities.get(s) == communities.get(t) and s != t:
                cid = communities[s]
                internal_edges[cid] += 1
                internal_weight[cid] += w

        scores: dict[int, float] = {}
        for cid, members in comm_nodes.items():
            n = len(members)
            if n <= 1:
                scores[cid] = 0.0
                continue
            max_edges = n * (n - 1) / 2
            density = internal_edges.get(cid, 0.0) / max_edges if max_edges > 0 else 0.0
            avg_w = (internal_weight.get(cid, 0.0) / internal_edges.get(cid, 1.0))
            # Normalize avg_w to 0..1 (assume weights typically 0..2)
            avg_w_norm = min(avg_w / 2.0, 1.0)
            # Size factor: log-scaled, rewards larger cohesive groups
            import math
            size_factor = math.log(n + 1) / math.log(21) if n <= 20 else 1.0
            scores[cid] = round(density * avg_w_norm * size_factor, 4)

        return scores

    @staticmethod
    def _compute_modularity(adj: dict, degree: dict, comm: dict,
                            m2: float, resolution: float) -> float:
        """Compute modularity Q for a given community assignment."""
        q = 0.0
        for cid in set(comm.values()):
            nodes_in = [n for n, c in comm.items() if c == cid]
            in_w = sum(adj.get(n, {}).get(n2, 0.0)
                       for i, n in enumerate(nodes_in)
                       for n2 in nodes_in[i + 1:]) * 2.0
            tot_deg = sum(degree.get(n, 0.0) for n in nodes_in)
            q += (in_w / m2) - resolution * (tot_deg / m2) ** 2
        return q

    def lazy_community_detect(self, seed_nodes: list[str], hops: int = 1,
                             resolution: float = 1.0) -> dict:
        """LazyGraphRAG-style community detection around seed nodes only.

        Instead of running full Leiden on the entire graph, this extracts a
        subgraph around the seed nodes (BFS to *hops* levels), then runs
        community detection only on that subgraph.  Dramatically cheaper for
        large graphs where only a local region is relevant (ICLR 2026
        LazyGraphRAG: ~1000× cost reduction vs full GraphRAG).

        Args:
            seed_nodes: node IDs to start BFS expansion from.
            hops: BFS depth (1 = direct neighbours, 2 = neighbours-of-neighbours).
            resolution: Leiden γ parameter controlling community granularity.

        Returns:
            dict with keys:
              - communities: {node_id: community_id}
              - num_communities: int
              - modularity: float (on the subgraph)
              - subgraph_size: int (number of nodes examined)
              - seed_coverage: float (fraction of seeds that found communities)
        """
        import math

        # --- 1. BFS expansion from seeds (only seeds that exist) ---
        visited: set[str] = set()
        existing_ids = {row[0] for row in self.conn.execute(
            "SELECT id FROM nodes").fetchall()}
        frontier = set(n for n in seed_nodes if n in existing_ids)
        for _ in range(hops + 1):
            next_frontier = set()
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                # Get neighbours from DB
                rows = self.conn.execute(
                    "SELECT target FROM edges WHERE source = ?"
                    " UNION "
                    "SELECT source FROM edges WHERE target = ?",
                    (nid, nid)).fetchall()
                for r in rows:
                    nb = str(r[0]) if not isinstance(r[0], str) else r[0]
                    if nb not in visited:
                        next_frontier.add(nb)
            frontier = next_frontier
            if not frontier:
                break

        if not visited:
            return {"communities": {}, "num_communities": 0, "modularity": 0.0,
                    "subgraph_size": 0, "seed_coverage": 0.0}

        # --- 2. Build adjacency for subgraph ---
        visited_list = list(visited)
        visited_set = set(visited)
        placeholders = ",".join("?" * len(visited_list))
        rows = self.conn.execute(
            f"SELECT source, target, weight FROM edges WHERE source IN ({placeholders}) "
            f"AND target IN ({placeholders})",
            visited_list + visited_list).fetchall()

        adj: dict[str, dict[str, float]] = defaultdict(dict)
        degree: dict[str, float] = defaultdict(float)
        total_w = 0.0
        for r in rows:
            s, t, w = str(r["source"]), str(r["target"]), float(r["weight"] or 1.0)
            adj[s][t] = adj[s].get(t, 0.0) + w
            adj[t][s] = adj[t].get(s, 0.0) + w
            degree[s] += w
            degree[t] += w
            total_w += w

        m2 = total_w * 2.0 if total_w > 0 else 1.0

        # --- 3. Label initialisation (each node its own community) ---
        comm = {n: i for i, n in enumerate(visited_list)}

        # --- 4. Fast local move (Leiden-inspired) ---
        # Randomize node order each iteration to avoid cascading on
        # symmetric graphs (rings, cliques).  Standard Louvain/Leiden
        # practice — without this, fixed order causes label waves on
        # rings that never converge to a good partition.
        import random as _rnd
        _rng = _rnd.Random(42)

        improved = True
        iterations = 0
        max_iterations = 15
        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            _order = visited_list[:]
            _rng.shuffle(_order)
            for nid in _order:
                k_i = degree.get(nid, 0.0)
                if k_i == 0:
                    continue

                # Count links to each community
                comm_links: dict[int, float] = defaultdict(float)
                for nb, w in adj.get(nid, {}).items():
                    if nb in comm:
                        comm_links[comm[nb]] += w

                best_comm = comm[nid]
                best_gain = 0.0

                # Community degree
                comm_degree: dict[int, float] = defaultdict(float)
                for n2, c2 in comm.items():
                    comm_degree[c2] += degree.get(n2, 0.0)

                for cid, link_w in comm_links.items():
                    if cid == comm[nid]:
                        continue
                    # ΔQ = 2*(link_w - γ*k_i*σ_c/(2m))
                    gain = 2.0 * (link_w - resolution * k_i * comm_degree[cid] / m2)
                    if gain > best_gain:
                        best_gain = gain
                        best_comm = cid

                if best_comm != comm[nid]:
                    comm[nid] = best_comm
                    improved = True

        # --- 5. Compute modularity on subgraph ---
        q = self._compute_modularity(adj, degree, comm, m2, resolution)

        # Fallback: if the partition is worse than a single community,
        # merge everything into one (connected graphs always yield Q ≥ 0).
        if q < 0 and len(visited_list) > 1:
            single_comm = {n: 0 for n in visited_list}
            q_single = self._compute_modularity(
                adj, degree, single_comm, m2, resolution)
            if q_single >= q:
                comm = single_comm
                q = q_single

        # Remap community IDs to 0..k-1
        unique = sorted(set(comm.values()))
        remap = {old: new for new, old in enumerate(unique)}
        comm = {n: remap[c] for n, c in comm.items()}

        seeds_found = sum(1 for s in seed_nodes if s in comm)

        return {
            "communities": comm,
            "num_communities": len(unique),
            "modularity": round(q, 4),
            "subgraph_size": len(visited_list),
            "seed_coverage": round(seeds_found / len(seed_nodes), 4) if seed_nodes else 0.0,
        }

    def community_summary(self, communities: dict = None, algorithm: str = "lp") -> list[dict]:
        """Summarize detected communities with key metrics.

        Args:
            communities: pre-computed {label: [node_ids]} dict. If None, auto-detects.
            algorithm: "lp" for label propagation, "greedy" for greedy modularity.

        Returns list of dicts with: id, size, top_members, density, top_tags, avg_weight.
        """
        if communities is None:
            if algorithm == "leiden":
                comm_map = self.detect_communities_leiden()
                communities = {}
                for nid, cid in comm_map.items():
                    communities.setdefault(cid, []).append(nid)
            elif algorithm == "greedy":
                comm_map = self.community_detection_greedy()
                communities = {}
                for nid, cid in comm_map.items():
                    communities.setdefault(cid, []).append(nid)
            else:
                communities = self.community_detect()
        if not communities:
            return []
        results = []
        for cid, node_ids in communities.items():
            if not node_ids:
                continue
            placeholders = ",".join("?" * len(node_ids))
            rows = self.conn.execute(
                f"SELECT id, label, kind, weight, tags FROM nodes WHERE id IN ({placeholders})",
                node_ids
            ).fetchall()
            # Internal edges
            edge_count = self.conn.execute(
                f"SELECT COUNT(*) as c FROM edges WHERE source IN ({placeholders}) AND target IN ({placeholders})",
                node_ids + node_ids
            ).fetchone()["c"]
            # Density: actual / max possible
            n = len(node_ids)
            max_edges = n * (n - 1)
            density = edge_count / max_edges if max_edges > 0 else 0.0
            # Top members by weight
            sorted_rows = sorted(rows, key=lambda r: r["weight"], reverse=True)
            top_members = [
                {"id": r["id"], "label": r["label"], "weight": r["weight"]}
                for r in sorted_rows[:5]
            ]
            # Tag aggregation
            tag_freq = {}
            for r in rows:
                for tag in json.loads(r["tags"]):
                    tag_freq[tag] = tag_freq.get(tag, 0) + 1
            top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:5]
            # Kind distribution
            kind_counts = {}
            for r in rows:
                kind_counts[r["kind"]] = kind_counts.get(r["kind"], 0) + 1
            avg_weight = sum(r["weight"] for r in rows) / len(rows)
            results.append({
                "id": cid,
                "size": n,
                "top_members": top_members,
                "internal_edges": edge_count,
                "density": round(density, 4),
                "top_tags": top_tags,
                "kinds": kind_counts,
                "avg_weight": round(avg_weight, 4),
            })
        results.sort(key=lambda x: x["size"], reverse=True)
        return results

    def community_fit_scores(self, communities: dict[str, int] = None) -> dict[str, float]:
        """Score how well each node fits its assigned community.

        For each node, computes the ratio of internal edges (to same-community
        neighbours) vs total edges.  A score near 1.0 means the node is deeply
        embedded in its community; near 0.0 means it's a bridge or outlier.

        Args:
            communities: {node_id: community_id}. If None, auto-detects via Leiden.

        Returns:
            {node_id: fit_score} where fit_score ∈ [0.0, 1.0].
        """
        if communities is None:
            communities = self.detect_communities_leiden()
        if not communities:
            return {}

        edges = self.conn.execute(
            "SELECT source, target FROM edges").fetchall()
        internal: dict[str, int] = defaultdict(int)
        external: dict[str, int] = defaultdict(int)

        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            cs = communities.get(s)
            ct = communities.get(t)
            if cs is not None and ct is not None:
                if cs == ct:
                    internal[s] += 1
                    internal[t] += 1
                else:
                    external[s] += 1
                    external[t] += 1
            elif s in communities:
                external[s] += 1
            elif t in communities:
                external[t] += 1

        scores = {}
        for nid in communities:
            total = internal[nid] + external[nid]
            scores[nid] = round(internal[nid] / total, 4) if total > 0 else 0.0
        return scores

    def bridge_nodes(self, communities: dict[str, int] = None,
                     min_cross_edges: int = 2) -> list[dict]:
        """Find nodes that bridge multiple communities.

        Bridge nodes have edges to members of different communities.  These are
        structurally important for information flow and cross-cutting themes in
        Agent memory graphs.

        Args:
            communities: {node_id: community_id}. If None, auto-detects via Leiden.
            min_cross_edges: minimum inter-community edges to qualify as a bridge.

        Returns:
            list of dicts sorted by cross-community edge count:
              [{node_id, label, community, cross_edges, cross_communities}]
        """
        if communities is None:
            communities = self.detect_communities_leiden()
        if not communities:
            return []

        edges = self.conn.execute(
            "SELECT source, target FROM edges").fetchall()

        cross_count: dict[str, int] = defaultdict(int)
        cross_comms: dict[str, set] = defaultdict(set)

        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            cs = communities.get(s)
            ct = communities.get(t)
            if cs is not None and ct is not None and cs != ct:
                cross_count[s] += 1
                cross_count[t] += 1
                cross_comms[s].add(ct)
                cross_comms[t].add(cs)

        # Filter and enrich
        bridges = []
        for nid, cnt in cross_count.items():
            if cnt >= min_cross_edges:
                row = self.conn.execute(
                    "SELECT label FROM nodes WHERE id = ?", (nid,)).fetchone()
                bridges.append({
                    "node_id": nid,
                    "label": row["label"] if row else "",
                    "community": communities[nid],
                    "cross_edges": cnt,
                    "cross_communities": sorted(cross_comms[nid]),
                })

        bridges.sort(key=lambda x: x["cross_edges"], reverse=True)
        return bridges

    def community_outliers(self, communities: dict[str, int] = None,
                           threshold: float = 0.2) -> list[dict]:
        """Find nodes with low community fit scores (potential misassignments).

        These nodes might be better suited in a different community or might
        represent cross-cutting concepts that don't belong to any single group.

        Args:
            communities: {node_id: community_id}. If None, auto-detects via Leiden.
            threshold: fit score below this → outlier (default 0.2).

        Returns:
            list of dicts: [{node_id, label, community, fit_score, degree}]
        """
        scores = self.community_fit_scores(communities)
        if not scores:
            return []

        edges = self.conn.execute(
            "SELECT source FROM edges").fetchall()
        degree = defaultdict(int)
        for e in edges:
            degree[str(e["source"])] += 1

        outliers = []
        for nid, score in scores.items():
            if score < threshold and degree[nid] > 0:
                row = self.conn.execute(
                    "SELECT label FROM nodes WHERE id = ?", (nid,)).fetchone()
                comm = communities.get(nid) if communities else None
                outliers.append({
                    "node_id": nid,
                    "label": row["label"] if row else "",
                    "community": comm,
                    "fit_score": score,
                    "degree": degree[nid],
                })

        outliers.sort(key=lambda x: x["fit_score"])
        return outliers

    def node_roles(self, hub_threshold: float = 0.7, authority_threshold: float = 0.7) -> dict[str, str]:
        """Classify each node's structural role: hub, authority, bridge, isolated, or member.

        - hub: high out-degree (sources many edges)
        - authority: high in-degree (target of many edges)
        - bridge: high betweenness relative to others
        - isolated: degree 0
        - member: everything else

        Returns {node_id: role}.
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return {}
        node_ids = [r["id"] for r in rows]
        # Compute in/out degrees
        out_deg = {}
        in_deg = {}
        for r in self.conn.execute("SELECT source, target FROM edges").fetchall():
            out_deg[r["source"]] = out_deg.get(r["source"], 0) + 1
            in_deg[r["target"]] = in_deg.get(r["target"], 0) + 1
        if not out_deg:
            return {nid: "isolated" for nid in node_ids}
        max_out = max(out_deg.values()) if out_deg else 1
        max_in = max(in_deg.values()) if in_deg else 1
        # Compute approximate betweenness for bridge detection
        bc = self.betweenness_centrality_approx(samples=min(20, len(node_ids)))
        max_bc = max(bc.values()) if bc and max(bc.values()) > 0 else 1
        roles = {}
        for nid in node_ids:
            od = out_deg.get(nid, 0)
            idg = in_deg.get(nid, 0)
            bc_score = bc.get(nid, 0)
            if od == 0 and idg == 0:
                roles[nid] = "isolated"
            elif od / max_out >= hub_threshold:
                roles[nid] = "hub"
            elif idg / max_in >= authority_threshold:
                roles[nid] = "authority"
            elif max_bc > 0 and bc_score / max_bc >= 0.6:
                roles[nid] = "bridge"
            else:
                roles[nid] = "member"
        return roles

    def role_summary(self) -> dict[str, int]:
        """Count nodes by role. Returns {role: count}."""
        roles = self.node_roles()
        summary = {}
        for role in roles.values():
            summary[role] = summary.get(role, 0) + 1
        return summary

    def betweenness_centrality_approx(self, samples: int = 20) -> dict[str, float]:
        """近似介数中心性（基于采样 Brandes 算法）。

        对大图提供 O(samples * V) 近似而非 O(V^3) 精确计算。
        """
        nodes = [str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        if not nodes:
            return {}
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        adj: dict[str, list[str]] = {nid: [] for nid in nodes}
        node_set = set(nodes)
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in node_set:
                adj[s].append(t)
            if t in node_set:
                adj[t].append(s)

        bc = {nid: 0.0 for nid in nodes}
        import random
        sample = nodes if len(nodes) <= samples else random.sample(nodes, samples)

        for src in sample:
            # BFS with dependency accumulation (Brandes)
            stack = []
            pred = {nid: [] for nid in nodes}
            sigma = {nid: 0 for nid in nodes}
            sigma[src] = 1
            dist = {nid: -1 for nid in nodes}
            dist[src] = 0
            queue = [src]
            while queue:
                v = queue.pop(0)
                stack.append(v)
                for w in adj[v]:
                    if dist[w] < 0:
                        queue.append(w)
                        dist[w] = dist[v] + 1
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)
            delta = {nid: 0.0 for nid in nodes}
            while stack:
                w = stack.pop()
                for v in pred[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != src:
                    bc[w] += delta[w]

        # Normalize
        n = len(nodes)
        scale = 2 / ((n - 1) * (n - 2)) if n > 2 else 1
        return {nid: round(bc[nid] * scale, 4) for nid in nodes}

    # ── 图变换 ──────────────────────────────────────────

    def reverse_edges(self) -> int:
        """反转所有边的方向。返回受影响的边数。"""
        count = self.conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
        if count == 0:
            return 0
        self.conn.execute("UPDATE edges SET source = target, target = source")
        self.conn.commit()
        return count

    def to_undirected(self) -> int:
        """将有向多重边合并为无向（对称边去重）。

        对于每对 (A→B, B→A) 只保留一条。返回移除的边数。
        """
        edges = self.conn.execute(
            "SELECT source, target, relation, weight FROM edges"
        ).fetchall()
        seen = set()
        to_remove = []
        for e in edges:
            s, t, rel = str(e["source"]), str(e["target"]), e["relation"]
            key = (min(s, t), max(s, t), rel)
            if key in seen:
                to_remove.append((s, t, rel))
            else:
                seen.add(key)
        for s, t, rel in to_remove:
            self.conn.execute(
                "DELETE FROM edges WHERE source=? AND target=? AND relation=?",
                (s, t, rel),
            )
        self.conn.commit()
        return len(to_remove)

    def induce_by_tags(self, tags: list[str], match_all: bool = False) -> dict:
        """按标签筛选节点，返回由这些节点组成的子图。

        match_all=True 时要求所有标签都存在，False 时任一匹配即可。
        """
        nodes = self.conn.execute("SELECT * FROM nodes").fetchall()
        tag_set = set(tags)
        filtered_ids = set()
        for n in nodes:
            node_tags = set(json.loads(n["tags"])) if n["tags"] else set()
            if match_all:
                if tag_set.issubset(node_tags):
                    filtered_ids.add(str(n["id"]))
            else:
                if node_tags & tag_set:
                    filtered_ids.add(str(n["id"]))

        edges = self.conn.execute(
            "SELECT * FROM edges WHERE source IN (%s) AND target IN (%s)"
            % (",".join("?" * len(filtered_ids)), ",".join("?" * len(filtered_ids))),
            list(filtered_ids) + list(filtered_ids),
        ).fetchall()

        return {
            "nodes": [
                {"id": str(r["id"]), "label": r["label"], "kind": r["kind"],
                 "weight": r["weight"], "tags": json.loads(r["tags"]) if r["tags"] else []}
                for r in nodes if str(r["id"]) in filtered_ids
            ],
            "edges": [
                {"source": str(r["source"]), "target": str(r["target"]),
                 "relation": r["relation"], "weight": r["weight"]}
                for r in edges
            ],
        }

    def weight_normalize(self, target_min: float = 0.0, target_max: float = 1.0) -> int:
        """将所有节点权重线性归一化到 [target_min, target_max]。返回更新的节点数。"""
        rows = self.conn.execute("SELECT id, weight FROM nodes").fetchall()
        if not rows:
            return 0
        weights = [r["weight"] for r in rows]
        w_min, w_max = min(weights), max(weights)
        if w_max == w_min:
            # All same weight → set to target_max
            for r in rows:
                self.conn.execute(
                    "UPDATE nodes SET weight=? WHERE id=?",
                    (target_max, str(r["id"])),
                )
        else:
            scale = (target_max - target_min) / (w_max - w_min)
            for r in rows:
                normalized = target_min + (r["weight"] - w_min) * scale
                self.conn.execute(
                    "UPDATE nodes SET weight=? WHERE id=?",
                    (round(normalized, 4), str(r["id"])),
                )
        self.conn.commit()
        return len(rows)

    def pagerank(self, damping: float = 0.85, max_iter: int = 100, tol: float = 1e-6) -> dict[str, float]:
        """PageRank 迭代求解。返回 {node_id: score}。"""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not nodes:
            return {}
        node_ids = [str(r["id"]) for r in nodes]
        n = len(node_ids)
        rank = {nid: 1.0 / n for nid in node_ids}
        # 构建入边索引
        inbound = {nid: [] for nid in node_ids}
        outbound_count = {nid: 0 for nid in node_ids}
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in outbound_count and t in inbound:
                inbound[t].append(s)
                outbound_count[s] += 1
        for _ in range(max_iter):
            new_rank = {}
            dangling_sum = sum(rank[nid] for nid in node_ids if outbound_count[nid] == 0)
            for nid in node_ids:
                contrib = 0.0
                for src in inbound[nid]:
                    if outbound_count[src] > 0:
                        contrib += rank[src] / outbound_count[src]
                # Dangling node redistribution
                contrib += dangling_sum / n
                new_rank[nid] = (1 - damping) / n + damping * contrib
            diff = sum(abs(new_rank[nid] - rank[nid]) for nid in node_ids)
            rank = new_rank
            if diff < tol:
                break
        return rank

    def eigenvector_centrality(self, max_iter: int = 100, tol: float = 1e-6) -> dict[str, float]:
        """幂迭代法求近似特征向量中心性。返回 {node_id: centrality}。"""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not nodes:
            return {}
        node_ids = [str(r["id"]) for r in nodes]
        id_set = set(node_ids)
        # 构建邻接表
        adj = {nid: [] for nid in node_ids}
        edges = self.conn.execute("SELECT source, target, weight FROM edges").fetchall()
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            w = e["weight"] if e["weight"] else 1.0
            if s in id_set and t in id_set:
                adj[s].append((t, w))
        v = {nid: 1.0 for nid in node_ids}
        for _ in range(max_iter):
            new_v = {nid: 0.0 for nid in node_ids}
            for src in node_ids:
                for tgt, w in adj[src]:
                    new_v[tgt] += v[src] * w
            norm = sum(val * val for val in new_v.values()) ** 0.5
            if norm == 0:
                break
            new_v = {nid: val / norm for nid, val in new_v.items()}
            diff = sum(abs(new_v[nid] - v[nid]) for nid in node_ids)
            v = new_v
            if diff < tol:
                break
        return v

    def authority_score(self, max_iter: int = 50) -> dict[str, float]:
        """HITS 算法：返回 {node_id: (hub_score, authority_score)} 的 authority 部分。"""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not nodes:
            return {}
        node_ids = [str(r["id"]) for r in nodes]
        id_set = set(node_ids)
        inbound = {nid: [] for nid in node_ids}
        outbound = {nid: [] for nid in node_ids}
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in id_set and t in id_set:
                inbound[t].append(s)
                outbound[s].append(t)
        hub = {nid: 1.0 for nid in node_ids}
        auth = {nid: 1.0 for nid in node_ids}
        for _ in range(max_iter):
            # Authority update
            new_auth = {nid: sum(hub[s] for s in inbound[nid]) for nid in node_ids}
            a_norm = max(new_auth.values()) or 1
            new_auth = {nid: v / a_norm for nid, v in new_auth.items()}
            # Hub update
            new_hub = {nid: sum(new_auth[t] for t in outbound[nid]) for nid in node_ids}
            h_norm = max(new_hub.values()) or 1
            new_hub = {nid: v / h_norm for nid, v in new_hub.items()}
            if (sum(abs(new_auth[nid] - auth[nid]) for nid in node_ids) +
                sum(abs(new_hub[nid] - hub[nid]) for nid in node_ids)) < 1e-6:
                break
            auth, hub = new_auth, new_hub
        return auth

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

    def serialize_graphml(self) -> str:
        """导出为 GraphML XML 格式，兼容 Gephi/yEd/Cytoscape 桌面版。"""
        import html
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
            '  <key id="kind" for="node" attr.name="kind" attr.type="string"/>',
            '  <key id="weight" for="node" attr.name="weight" attr.type="double"/>',
            '  <key id="relation" for="edge" attr.name="relation" attr.type="string"/>',
            '  <key id="eweight" for="edge" attr.name="weight" attr.type="double"/>',
            '  <graph id="G" edgedefault="directed">',
        ]
        nodes = self.conn.execute("SELECT * FROM nodes").fetchall()
        for n in nodes:
            lines.append(
                f'    <node id="{n["id"]}">'
                f'<data key="label">{html.escape(n["label"])}</data>'
                f'<data key="kind">{html.escape(n["kind"])}</data>'
                f'<data key="weight">{n["weight"]}</data>'
                '</node>'
            )
        edges = self.conn.execute("SELECT * FROM edges").fetchall()
        for i, e in enumerate(edges):
            lines.append(
                f'    <edge id="e{i}" source="{e["source"]}" target="{e["target"]}">'
                f'<data key="relation">{html.escape(e["relation"])}</data>'
                f'<data key="eweight">{e["weight"]}</data>'
                '</edge>'
            )
        lines.append('  </graph>')
        lines.append('</graphml>')
        return '\n'.join(lines)

    def serialize_cytoscape(self) -> dict:
        """导出为 Cytoscape.js JSON 格式，兼容 cytoscape.js 前端可视化。"""
        nodes = self.conn.execute("SELECT * FROM nodes").fetchall()
        edges = self.conn.execute("SELECT * FROM edges").fetchall()
        return {
            "elements": {
                "nodes": [
                    {
                        "data": {
                            "id": str(n["id"]),
                            "label": n["label"],
                            "kind": n["kind"],
                            "weight": n["weight"],
                            "tags": json.loads(n["tags"]) if n["tags"] else [],
                        }
                    }
                    for n in nodes
                ],
                "edges": [
                    {
                        "data": {
                            "id": f"e{i}",
                            "source": str(e["source"]),
                            "target": str(e["target"]),
                            "relation": e["relation"],
                            "weight": e["weight"],
                        }
                    }
                    for i, e in enumerate(edges)
                ],
            }
        }

    def serialize_edgelist(self) -> list[str]:
        """导出为边列表格式 ['source_id target_id weight', ...]。"""
        edges = self.conn.execute("SELECT source, target, weight FROM edges").fetchall()
        return [f"{e['source']} {e['target']} {e['weight']}" for e in edges]

    def k_core(self, k: int) -> list[str]:
        """k-core 分解：返回度数 ≥ k 的节点 ID 列表（迭代删除度数不足的节点）。"""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        node_ids = {str(r["id"]) for r in nodes}
        if not node_ids:
            return []
        # Build undirected degree map (treat directed as undirected)
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        adj = {nid: set() for nid in node_ids}
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in node_ids and t in node_ids:
                adj[s].add(t)
                adj[t].add(s)
        # Iteratively prune nodes with degree < k
        changed = True
        while changed:
            changed = False
            to_remove = set()
            for nid in node_ids:
                if len(adj[nid]) < k:
                    to_remove.add(nid)
            if to_remove:
                changed = True
                for nid in to_remove:
                    node_ids.discard(nid)
                    for neighbor in adj[nid]:
                        if neighbor in adj:
                            adj[neighbor].discard(nid)
        return sorted(node_ids)

    def core_number(self) -> dict[str, int]:
        """每个节点的 core number（最大 k-core 包含该节点的 k 值）。"""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        node_ids = {str(r["id"]) for r in nodes}
        if not node_ids:
            return {}
        # Build undirected adjacency
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        adj = {nid: set() for nid in node_ids}
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in node_ids and t in node_ids:
                adj[s].add(t)
                adj[t].add(s)
        # Batagelj-Zaversnik algorithm
        degree = {nid: len(adj[nid]) for nid in node_ids}
        # Sort nodes by degree
        sorted_nodes = sorted(node_ids, key=lambda n: degree[n])
        core = {}
        for nid in sorted_nodes:
            core[nid] = degree[nid]
            for neighbor in adj[nid]:
                if degree[neighbor] > degree[nid]:
                    degree[neighbor] -= 1
        return core

    def count_triangles(self) -> int:
        """统计图中三角形数量（有向边视为无向）。"""
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        node_ids = {str(r["id"]) for r in nodes}
        edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        adj = {nid: set() for nid in node_ids}
        for e in edges:
            s, t = str(e["source"]), str(e["target"])
            if s in node_ids and t in node_ids:
                adj[s].add(t)
                adj[t].add(s)
        count = 0
        id_list = sorted(node_ids)
        id_index = {nid: i for i, nid in enumerate(id_list)}
        for i, u in enumerate(id_list):
            for v in adj[u]:
                if id_index.get(v, -1) > i:
                    for w in adj[v]:
                        if id_index.get(w, -1) > id_index[v]:
                            if w in adj[u]:
                                count += 1
        return count

    def local_triangle_count(self, node_id: str) -> int:
        """单节点参与的三角形数量。"""
        if node_id not in {str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()}:
            return 0
        # Build adjacency for neighborhood
        all_edges = self.conn.execute("SELECT source, target FROM edges").fetchall()
        adj = {}
        for e in all_edges:
            s, t = str(e["source"]), str(e["target"])
            adj.setdefault(s, set()).add(t)
            adj.setdefault(t, set()).add(s)
        neighbors = adj.get(node_id, set())
        count = 0
        neighbor_list = list(neighbors)
        for i, v in enumerate(neighbor_list):
            for w in neighbor_list[i+1:]:
                if w in adj.get(v, set()):
                    count += 1
        return count

    def add_tag(self, node_id: str, tag: str) -> bool:
        """Add a single tag to a node. Returns True if added, False if node not found."""
        row = self.conn.execute("SELECT tags FROM nodes WHERE id=?", (node_id,)).fetchone()
        if row is None:
            return False
        tags = json.loads(row["tags"])
        if tag not in tags:
            tags.append(tag)
            self.conn.execute("UPDATE nodes SET tags=? WHERE id=?", (json.dumps(tags), node_id))
            self.conn.commit()
        return True

    def remove_tag(self, node_id: str, tag: str) -> bool:
        """Remove a single tag from a node. Returns True if removed, False if node/tag not found."""
        row = self.conn.execute("SELECT tags FROM nodes WHERE id=?", (node_id,)).fetchone()
        if row is None:
            return False
        tags = json.loads(row["tags"])
        if tag not in tags:
            return False
        tags.remove(tag)
        self.conn.execute("UPDATE nodes SET tags=? WHERE id=?", (json.dumps(tags), node_id))
        self.conn.commit()
        return True

    def has_tag(self, node_id: str, tag: str) -> bool:
        """Check if a node has a specific tag."""
        row = self.conn.execute("SELECT tags FROM nodes WHERE id=?", (node_id,)).fetchone()
        if row is None:
            return False
        return tag in json.loads(row["tags"])

    def tag_cloud(self, limit: int = 0) -> list[dict]:
        """Return tag frequency as sorted list of {tag, count} dicts.

        Args:
            limit: if >0, return only top-N most frequent tags.
        """
        freq = {}
        for r in self.conn.execute("SELECT tags FROM nodes").fetchall():
            for tag in json.loads(r["tags"]):
                freq[tag] = freq.get(tag, 0) + 1
        result = [{"tag": t, "count": c} for t, c in sorted(freq.items(), key=lambda x: -x[1])]
        return result[:limit] if limit > 0 else result

    def tag_stats(self) -> dict:
        """Comprehensive tag statistics."""
        all_tags = self.all_tags()
        cloud = self.tag_cloud()
        total_nodes = self.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        tagged_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE tags != '[]'"
        ).fetchone()["c"]
        total_tag_instances = sum(item["count"] for item in cloud)
        avg_tags = total_tag_instances / total_nodes if total_nodes else 0
        return {
            "unique_tags": len(all_tags),
            "total_tag_instances": total_tag_instances,
            "tagged_nodes": tagged_count,
            "untagged_nodes": total_nodes - tagged_count,
            "avg_tags_per_node": round(avg_tags, 2),
            "most_used": cloud[0] if cloud else None,
            "least_used": cloud[-1] if cloud else None,
        }

    def _bfs_distances(self, node_id: str) -> dict[str, int]:
        """Bidirectional BFS: shortest distances from node_id to all reachable nodes.

        Treats edges as undirected (source↔target), which is the standard for
        graph-analysis metrics (diameter, eccentricity, closeness).
        """
        distances = {node_id: 0}
        queue = [node_id]
        while queue:
            cur = queue.pop(0)
            # Both outgoing (source→target) and incoming (target→source) edges
            rows = self.conn.execute(
                "SELECT target AS nb FROM edges WHERE source=? "
                "UNION "
                "SELECT source AS nb FROM edges WHERE target=?",
                (cur, cur)
            ).fetchall()
            for r in rows:
                nid = str(r["nb"])
                if nid not in distances:
                    distances[nid] = distances[cur] + 1
                    queue.append(nid)
        return distances

    def closeness_centrality(self, node_id: str) -> Optional[float]:
        """接近中心性 (Wasserman-Faust normalization).

        C(v) = reachable² / ((n-1) * sum(distances))

        值越高表示该节点越"中心"。对不可达节点自动惩罚。
        """
        if not self.has_node(node_id):
            return None
        n = self.stats()["nodes"]
        if n <= 1:
            return 0.0
        distances = self._bfs_distances(node_id)
        reachable = len(distances) - 1
        if reachable == 0:
            return 0.0
        total_dist = sum(distances.values())
        return (reachable * reachable) / ((n - 1) * total_dist)

    def graph_diameter(self) -> Optional[int]:
        """图直径 = 所有连通分量中最长最短路径。

        空图返回 None，孤立节点图返回 0。
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return None
        diameter = 0
        for row in rows:
            nid = str(row["id"])
            distances = self._bfs_distances(nid)
            if distances:
                local_max = max(distances.values())
                if local_max > diameter:
                    diameter = local_max
        return diameter

    def eccentricity(self, node_id: str) -> Optional[int]:
        """离心率 = 从 node_id 到最远可达节点的距离（双向边）。"""
        if not self.has_node(node_id):
            return None
        distances = self._bfs_distances(node_id)
        return max(distances.values()) if distances else 0

    def graph_radius(self) -> Optional[int]:
        """图半径 = 所有节点离心率的最小值。"""
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return None
        eccentricities = []
        for row in rows:
            ecc = self.eccentricity(str(row["id"]))
            if ecc is not None:
                eccentricities.append(ecc)
        return min(eccentricities) if eccentricities else None

    # ── 连通性分析 ──────────────────────────────────────

    def connected_components(self) -> list[list[str]]:
        """返回所有连通分量（双向边语义）。

        每个分量为节点 ID 列表，按大小降序排列。
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return []
        visited: set[str] = set()
        components: list[list[str]] = []
        for row in rows:
            nid = str(row["id"])
            if nid in visited:
                continue
            dists = self._bfs_distances(nid)
            comp = list(dists.keys())
            visited.update(comp)
            components.append(comp)
        components.sort(key=len, reverse=True)
        return components

    def is_connected(self) -> bool:
        """图是否连通（单一连通分量）。空图返回 True，单节点返回 True。"""
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return True
        first = str(rows[0]["id"])
        dists = self._bfs_distances(first)
        return len(dists) == len(rows)

    def average_path_length(self) -> Optional[float]:
        """所有可达节点对的平均最短路径长度（双向边语义）。

        仅计算同一连通分量内的节点对，不对不可达对做无穷惩罚。
        空图返回 None，单节点返回 0.0。
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return None
        total_dist = 0
        pair_count = 0
        visited_pairs: set[frozenset] = set()
        for row in rows:
            nid = str(row["id"])
            dists = self._bfs_distances(nid)
            for target, dist in dists.items():
                if target == nid:
                    continue
                pair = frozenset({nid, target})
                if pair in visited_pairs:
                    continue
                visited_pairs.add(pair)
                total_dist += dist
                pair_count += 1
        return round(total_dist / pair_count, 4) if pair_count > 0 else 0.0

    def effective_diameter(self, percentile: float = 0.9) -> Optional[float]:
        """有效直径 — 第 percentile 分位的最短路径长度。

        比最大直径更鲁棒：忽略少数极端长路径。
        例如 percentile=0.9 表示 90% 的可达节点对在此距离以内。

        空图返回 None，无可达对返回 0.0。
        """
        if not 0 < percentile <= 1:
            raise ValueError("percentile must be in (0, 1]")
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return None
        all_dists: list[int] = []
        visited_pairs: set[frozenset] = set()
        for row in rows:
            nid = str(row["id"])
            dists = self._bfs_distances(nid)
            for target, dist in dists.items():
                if target == nid:
                    continue
                pair = frozenset({nid, target})
                if pair in visited_pairs:
                    continue
                visited_pairs.add(pair)
                all_dists.append(dist)
        if not all_dists:
            return 0.0
        all_dists.sort()
        idx = int(len(all_dists) * percentile)
        if idx >= len(all_dists):
            idx = len(all_dists) - 1
        return float(all_dists[idx])

    def harmonic_centrality(self, node_id: str) -> Optional[float]:
        """调和中心性 = Σ(1/distance) 对所有可达节点。

        对不可达节点距离视为无穷大（贡献为 0），
        因此在断开图中比 closeness 更有意义。
        归一化到 [0, 1] 区间：H(v) = Σ(1/d) / (n-1)。
        """
        if not self.has_node(node_id):
            return None
        n = self.stats()["nodes"]
        if n <= 1:
            return 0.0
        distances = self._bfs_distances(node_id)
        score = sum(1.0 / d for _, d in distances.items() if d > 0)
        return round(score / (n - 1), 6)

    def clustering_coefficient(self, node_id: str) -> Optional[float]:
        """局部聚类系数 = 邻居之间实际边数 / 可能边数。

        衡量节点的邻居彼此连接的程度（"朋友的朋友也是朋友"）。
        值域 [0, 1]。度为 0 或 1 时返回 0.0。
        双向边语义。
        """
        if not self.has_node(node_id):
            return None
        # Get neighbors (bidirectional)
        rows = self.conn.execute(
            "SELECT target AS nb FROM edges WHERE source=? "
            "UNION "
            "SELECT source AS nb FROM edges WHERE target=?",
            (node_id, node_id)
        ).fetchall()
        neighbors = [str(r["nb"]) for r in rows]
        k = len(neighbors)
        if k < 2:
            return 0.0
        # Count edges between neighbors
        neighbor_set = set(neighbors)
        edge_count = 0
        for nb in neighbors:
            nb_rows = self.conn.execute(
                "SELECT target AS nb2 FROM edges WHERE source=? "
                "UNION "
                "SELECT source AS nb2 FROM edges WHERE target=?",
                (nb, nb)
            ).fetchall()
            for r in nb_rows:
                if str(r["nb2"]) in neighbor_set and str(r["nb2"]) != nb:
                    edge_count += 1
        # Each edge counted twice (once from each endpoint)
        actual_edges = edge_count / 2
        possible_edges = k * (k - 1) / 2
        return round(actual_edges / possible_edges, 6)

    def effective_eccentricity(self, node_id: str, percentile: float = 0.9) -> Optional[float]:
        """有效离心率 — 从 node_id 出发，第 percentile 分位的可达距离。

        结合 eccentricity（最大距离）和 effective_diameter（分位数）的思想：
        eccentricity 取绝对最大值，容易受单个离群节点影响；
        effective_eccentricity 取分位数，更鲁棒地描述节点的"可达范围"。

        例如 percentile=0.9 表示 90% 的可达节点在此距离以内。

        Returns:
            float: 分位数距离；节点不存在返回 None；无可达节点返回 0.0。
        """
        if not self.has_node(node_id):
            return None
        if not 0 < percentile <= 1:
            raise ValueError("percentile must be in (0, 1]")
        distances = self._bfs_distances(node_id)
        # Exclude self (distance 0)
        reach_dists = sorted(d for d in distances.values() if d > 0)
        if not reach_dists:
            return 0.0
        idx = int(len(reach_dists) * percentile)
        if idx >= len(reach_dists):
            idx = len(reach_dists) - 1
        return float(reach_dists[idx])

    def global_efficiency(self) -> Optional[float]:
        """全局效率 — 所有节点对效率的平均值。

        效率(v,u) = 1 / distance(v,u)，不可达时效率为 0。
        全局效率 = Σ 1/d(v,u) / (n*(n-1))，归一化到 [0, 1]。

        衡量图中信息流动的整体效率。比 average_path_length 更好地
        处理断开图：断开的节点对贡献 0 而非被忽略或视为无穷。

        References:
            Latora & Marchiori (2001) "Efficient behavior of small-world networks"

        Returns:
            float: 全局效率 [0, 1]；空图返回 None。
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return None
        n = len(rows)
        node_ids = [str(r["id"]) for r in rows]
        total_efficiency = 0.0
        for nid in node_ids:
            dists = self._bfs_distances(nid)
            for target, d in dists.items():
                if target != nid and d > 0:
                    total_efficiency += 1.0 / d
        # Normalize by n*(n-1) (ordered pairs, not unordered)
        denom = n * (n - 1)
        return round(total_efficiency / denom, 6) if denom > 0 else 0.0

    def s_metric(self) -> Optional[float]:
        """S-metric — 所有边的端点度数乘积之和。

        S = Σ_{(u,v) ∈ E} deg(u) × deg(v)

        衡量图中 hub-hub 连接的程度。高 S 值意味着高度数节点
        倾向于相互连接（如互联网拓扑）。低 S 值意味着 hub 连接
        的是低度数节点（如星形图）。

        可用于评估图的 "scale-free" 程度和 hub 结构质量。

        References:
            Li et al. (2005) "Towards a Theory of Scale-Free Graphs:
            Definition, Properties, and Implications"

        Returns:
            float: S-metric 值；空图返回 None。
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return None
        # Pre-compute degrees
        degrees = {}
        for row in rows:
            nid = str(row["id"])
            degrees[nid] = self.degree(nid)
        # Sum over edges (each edge counted once)
        edge_rows = self.conn.execute("SELECT source, target FROM edges").fetchall()
        s = 0
        for er in edge_rows:
            src = str(er["source"])
            tgt = str(er["target"])
            s += degrees.get(src, 0) * degrees.get(tgt, 0)
        return float(s)

    def local_efficiency(self, node_id: str) -> Optional[float]:
        """局部效率 — 节点邻居子图的全局效率。

        对于节点 v，取出其所有直接邻居，计算这些邻居构成的
        子图（不含 v 本身）的全局效率。衡量 v 的邻居在 v 被移除后
        仍能相互通信的程度。

        范围 [0, 1]。高值 = 鲁棒的局部结构（即使 v 消失，
        邻居们仍高度互联）。与 clustering_coefficient 互补：
        后者基于三角形计数，前者基于距离效率。

        References:
            Latora & Marchiori (2001) — "Efficient Behavior of
            Small-World Networks"

        Args:
            node_id: 目标节点 ID

        Returns:
            float: 局部效率值；节点不存在或邻居不足 2 个返回 None。
        """
        node = self.get_node(node_id)
        if node is None:
            return None
        # Get direct neighbors (undirected)
        rows = self.conn.execute(
            "SELECT target AS nb FROM edges WHERE source=? "
            "UNION "
            "SELECT source AS nb FROM edges WHERE target=?",
            (node_id, node_id)
        ).fetchall()
        neighbors = [str(r["nb"]) for r in rows]
        if len(neighbors) < 2:
            return None
        # Standard definition: efficiency among neighbors using paths
        # that do NOT pass through node_id (induced neighborhood subgraph).
        # We temporarily remove node_id, compute BFS distances among
        # neighbors, then restore.
        n_nb = len(neighbors)
        total = 0.0
        # Get edges to temporarily remove
        removed_edges = self.conn.execute(
            "SELECT rowid, source, target, relation, weight FROM edges "
            "WHERE source=? OR target=?",
            (node_id, node_id)
        ).fetchall()
        self.conn.execute("DELETE FROM edges WHERE source=? OR target=?",
                          (node_id, node_id))
        try:
            for nb in neighbors:
                dists = self._bfs_distances(nb)
                for other in neighbors:
                    if other == nb:
                        continue
                    d = dists.get(other)
                    if d and d > 0:
                        total += 1.0 / d
        finally:
            for e in removed_edges:
                self.conn.execute(
                    "INSERT INTO edges (source, target, relation, weight) VALUES (?,?,?,?)",
                    (e["source"], e["target"], e["relation"], e["weight"]))
        return total / (n_nb * (n_nb - 1))

    def wiener_index(self) -> Optional[int]:
        """Wiener 指数 — 所有节点对最短路径长度之和。

        W = Σ_{u<v} d(u,v)

        经典图论不变量 (Wiener 1947)，是 average_path_length 的
        未归一化版本。值越大图越 "分散"。对不可达的节点对，
        按惯例不计入（与 global_efficiency 的处理方式不同）。

        References:
            Wiener, H. (1947) "Structural Determination of
            Paraffin Boiling Points"

        Returns:
            int: Wiener 指数值；空图或单节点返回 None。
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if len(rows) < 2:
            return None
        node_ids = [str(r["id"]) for r in rows]
        total = 0
        for i, nid in enumerate(node_ids):
            dists = self._bfs_distances(nid)
            for other in node_ids[i + 1:]:
                d = dists.get(other)
                if d and d > 0:
                    total += d
        return total

    def onion_structure(self, n_layers: int = 3) -> Optional[list[dict]]:
        """洋葱结构 — k-core 分层剖面。

        逐步移除度数 < k 的节点，记录每一层的节点集合和统计信息。
        比 core_number() 更直观地展示图的 "深度结构"。

        每层返回：
        - k: 核心度阈值
        - nodes: 属于该层但在 k+1 层被移除的节点 ID
        - count: 节点数量
        - edges: 这些节点之间（在原图中）的边数

        Args:
            n_layers: 最大层数（默认 3）

        Returns:
            list[dict]: 各层剖面；空图返回 None。
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        if not rows:
            return None
        all_ids = {str(r["id"]) for r in rows}
        result = []
        prev_core = set(all_ids)
        for k in range(1, n_layers + 1):
            if not prev_core:
                break
            # Iteratively remove nodes with degree < k among prev_core
            changed = True
            current = set(prev_core)
            while changed:
                changed = False
                to_remove = set()
                ids_list = list(current)
                for nid in current:
                    cnt = self.conn.execute(
                        "SELECT COUNT(*) FROM edges WHERE source=? AND target IN ({}) "
                        "UNION ALL "
                        "SELECT COUNT(*) FROM edges WHERE target=? AND source IN ({})".format(
                            ",".join("?" * len(ids_list)), ",".join("?" * len(ids_list))
                        ),
                        (nid, *ids_list, nid, *ids_list)
                    ).fetchall()
                    deg = sum(r[0] for r in cnt)
                    if deg < k:
                        to_remove.add(nid)
                if to_remove:
                    current -= to_remove
                    changed = True
            # Nodes peeled at this level = in prev_core but not in current
            peeled = prev_core - current
            if k == n_layers:
                # Last layer: all remaining nodes (including those surviving k)
                peeled = prev_core
            prev_core = current
            # Count edges among peeled nodes
            if peeled:
                p_list = list(peeled)
                placeholders = ",".join("?" * len(p_list))
                edge_count = self.conn.execute(
                    "SELECT COUNT(*) FROM edges WHERE source IN ({}) AND target IN ({})".format(
                        placeholders, placeholders
                    ),
                    (*p_list, *p_list)
                ).fetchone()[0]
            else:
                edge_count = 0
            result.append({
                "k": k,
                "nodes": sorted(peeled),
                "count": len(peeled),
                "edges": edge_count
            })
            if not current:
                break
        return result

    # ── 向量搜索 (sqlite-vec 可选集成) ────────────────────

    def _ensure_vec_table(self, dims: int):
        """确保 vec_nodes 虚拟表存在，返回是否首次创建。"""
        try:
            import sqlite_vec
            if not getattr(self, '_vec_loaded', False):
                self.conn.enable_load_extension(True)
                sqlite_vec.load(self.conn)
                self.conn.enable_load_extension(False)
                self._vec_loaded = True
        except ImportError:
            raise ImportError("sqlite-vec is required for vector operations. Install: pip install sqlite-vec")
        row = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_nodes'").fetchone()
        if not row:
            self.conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_nodes USING vec0(embedding float[{dims}])")
            self._vec_dims = dims
            return True
        return False

    def _node_to_rowid(self, node_id: str) -> int:
        """将 node_id 字符串映射为稳定的整数 rowid。"""
        row = self.conn.execute("SELECT rowid FROM node_rowids WHERE node_id = ?", (node_id,)).fetchone()
        if row:
            return row["rowid"]
        self.conn.execute("INSERT OR IGNORE INTO node_rowids(node_id) VALUES (?)", (node_id,))
        return self.conn.execute("SELECT rowid FROM node_rowids WHERE node_id = ?", (node_id,)).fetchone()["rowid"]

    def _ensure_rowid_table(self):
        """确保 node_rowids 映射表存在。"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS node_rowids (
                node_id TEXT PRIMARY KEY
            )
        """)

    def add_embedding(self, node_id: str, embedding: list[float]) -> None:
        """为节点添加向量嵌入。需要可选依赖 sqlite-vec。

        Args:
            node_id: 目标节点 ID
            embedding: 浮点向量 (任意维度, 首次调用决定维度)

        Raises:
            ImportError: 如果 sqlite-vec 未安装
            ValueError: 如果节点不存在或维度不匹配
        """
        if not self.has_node(node_id):
            raise ValueError(f"Node not found: {node_id}")
        try:
            import sqlite_vec
        except ImportError:
            raise ImportError("sqlite-vec is required. Install: pip install sqlite-vec")

        self._ensure_rowid_table()
        dims = len(embedding)
        self._ensure_vec_table(dims)

        rowid = self._node_to_rowid(node_id)
        vec = sqlite_vec.serialize_float32(embedding)
        self.conn.execute("DELETE FROM vec_nodes WHERE rowid = ?", (rowid,))
        self.conn.execute("INSERT INTO vec_nodes(rowid, embedding) VALUES (?, ?)", (rowid, vec))
        self.conn.commit()

    def search_similar(self, embedding: list[float], limit: int = 10) -> list[dict]:
        """向量相似度搜索 (KNN)。需要可选依赖 sqlite-vec。

        Args:
            embedding: 查询向量
            limit: 返回数量上限

        Returns:
            list of {node_id, label, kind, distance, score} 按距离升序

        Raises:
            ImportError: 如果 sqlite-vec 未安装
            ValueError: 如果尚未添加任何嵌入
        """
        try:
            import sqlite_vec
        except ImportError:
            raise ImportError("sqlite-vec is required. Install: pip install sqlite-vec")

        if not hasattr(self, '_vec_dims'):
            row = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_nodes'").fetchone()
            if not row:
                raise ValueError("No embeddings found. Call add_embedding() first.")

        self._ensure_rowid_table()
        vec = sqlite_vec.serialize_float32(embedding)
        rows = self.conn.execute(
            """
            SELECT v.rowid, v.distance, n.id, n.label, n.kind, n.weight
            FROM vec_nodes AS v
            JOIN node_rowids AS r ON v.rowid = r.rowid
            JOIN nodes AS n ON r.node_id = n.id
            WHERE v.embedding MATCH ? AND v.k = ?
            ORDER BY v.distance
            """,
            (vec, limit)
        ).fetchall()
        results = []
        for row in rows:
            dist = row["distance"]
            # 距离转相似度分数 (1/(1+distance), 范围 0~1)
            score = 1.0 / (1.0 + dist)
            results.append({
                "node_id": row["id"],
                "label": row["label"],
                "kind": row["kind"],
                "distance": round(dist, 6),
                "score": round(score, 6),
                "weight": row["weight"],
            })
        return results

    # ── FTS5 BM25 full-text search ──────────────────────────────────────

    def _fts_sync_node(self, node_id: str):
        """Insert/update FTS index for a single node."""
        if not getattr(self, '_fts_enabled', False):
            return
        row = self.conn.execute(
            "SELECT id, label, kind, data, tags FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        if not row:
            self.conn.execute("DELETE FROM nodes_fts WHERE node_id=?", (node_id,))
            return
        self.conn.execute("DELETE FROM nodes_fts WHERE node_id=?", (node_id,))
        self.conn.execute(
            "INSERT INTO nodes_fts(node_id, label, kind, data, tags) VALUES (?,?,?,?,?)",
            (row["id"], row["label"], row["kind"], row["data"], row["tags"])
        )

    def _fts_delete_node(self, node_id: str):
        """Remove a node from FTS index."""
        if not getattr(self, '_fts_enabled', False):
            return
        self.conn.execute("DELETE FROM nodes_fts WHERE node_id=?", (node_id,))

    def _fts_rebuild(self):
        """Rebuild the FTS index from scratch (all nodes)."""
        if not getattr(self, '_fts_enabled', False):
            return
        self.conn.execute("DELETE FROM nodes_fts")
        rows = self.conn.execute("SELECT id, label, kind, data, tags FROM nodes").fetchall()
        for r in rows:
            self.conn.execute(
                "INSERT INTO nodes_fts(node_id, label, kind, data, tags) VALUES (?,?,?,?,?)",
                (r["id"], r["label"], r["kind"], r["data"], r["tags"])
            )

    def search_bm25(self, query: str, limit: int = 10) -> list[dict]:
        """BM25 full-text search via SQLite FTS5.

        Ranks nodes by BM25 relevance across label, kind, data, and tags.
        Falls back to search_unified() if FTS5 is unavailable.

        Args:
            query: FTS5 query string (supports prefix, AND, OR, NOT, "phrase")
            limit: Max results

        Returns:
            list of {node_id, label, kind, score, matched_fields} sorted by BM25 score desc
        """
        if not getattr(self, '_fts_enabled', False):
            # Fallback to unified search
            results = self.search_unified(query, limit=limit)
            return [
                {"node_id": r["node"].id, "label": r["node"].label,
                 "kind": r["node"].kind, "score": r["score"],
                 "matched_fields": r["matched_fields"]}
                for r in results
            ]
        try:
            # Fetch by raw BM25, then re-sort by weight-boosted score
            rows = self.conn.execute(
                """
                SELECT n.id, n.label, n.kind, n.weight,
                       bm25(nodes_fts) as score
                FROM nodes_fts JOIN nodes n ON nodes_fts.node_id = n.id
                WHERE nodes_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query, limit * 3)
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        results = []
        for r in rows:
            bm25_score = -r["score"]  # bm25() returns negative (lower = better)
            results.append({
                "node_id": r["id"],
                "label": r["label"],
                "kind": r["kind"],
                "score": round(bm25_score * r["weight"], 6),
                "matched_fields": ["bm25"],
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    @staticmethod
    def _classify_query(query: str, known_labels: list[str] = None) -> dict:
        """QDAP-v2: 6-class query classifier with continuous weight interpolation.

        Classes: trivial / exact / semantic / relational / temporal / exploratory
        + needs_retrieval gate (trivial queries skip retrieval entirely).
        Weights interpolated from specificity ∈ [0,1] instead of discrete buckets.

        Returns:
            {type, weights: [bm25_w, vector_w, graph_w], k, needs_retrieval, specificity}
        """
        q = query.lower().strip()
        known_labels = known_labels or []
        words = q.split()
        word_count = len(words)

        # ── Feature extraction ──
        has_identifier = any(
            label.lower() in q
            for label in known_labels
            if len(label) >= 3
        )
        # Avoid false positive: common English words ≥4 chars aren't identifiers
        common_words = {"what", "when", "where", "which", "that", "this", "with",
                         "from", "have", "been", "will", "would", "could", "should",
                         "about", "there", "their", "these", "those", "every",
                         "machine", "learning", "deep", "data", "model", "system",
                         "applications", "science", "research", "project", "update",
                         "question", "between", "through", "during", "before",
                         "after", "because", "however", "though", "while"}
        if not has_identifier and word_count <= 2:
            has_identifier = any(
                token.isidentifier() and len(token) >= 4 and token not in common_words
                for token in words
            )

        relation_kw = sum(
            1 for kw in ("relation", "connect", "link", "path", "between",
                         "neighbor", "edge", "关联", "连接", "路径", "邻居")
            if kw in q
        )
        temporal_kw = sum(
            1 for kw in ("when", "time", "before", "after", "recent", "latest",
                         "history", "last", "first", "earliest",
                         "时间", "之前", "之后", "最近", "历史", "上次")
            if kw in q
        )
        exploratory_kw = sum(
            1 for kw in ("how", "why", "what if", "explore", "brainstorm",
                         "compare", "analyze", "design",
                         "如何", "为什么", "探索", "比较", "分析")
            if kw in q
        )

        # ── needs_retrieval gate ──
        # Trivial queries (greetings, single stop-words) skip retrieval
        stop_words = {"hi", "hello", "hey", "ok", "yes", "no", "thanks",
                      "你好", "嗯", "好的", "谢谢"}
        if word_count <= 1 and (q in stop_words or q == ""):
            return {"type": "trivial", "weights": [0.0, 0.0, 0.0], "k": 0,
                    "needs_retrieval": False, "specificity": 0.0}

        # ── Class priority: relational > temporal > exact > exploratory > semantic ──
        if relation_kw > 0:
            q_type = "relational"
            specificity = 0.85
        elif temporal_kw > 0:
            q_type = "temporal"
            specificity = 0.70
        elif has_identifier and word_count <= 3:
            q_type = "exact"
            specificity = 0.90
        elif exploratory_kw > 0:
            q_type = "exploratory"
            specificity = 0.30
        else:
            q_type = "semantic"
            specificity = 0.50

        # ── Continuous weight interpolation (class-aware) ──
        # Base weights per class, modulated by specificity
        base = {
            "relational":   [0.20, 0.25, 0.55],   # graph-dominant
            "exact":        [0.55, 0.20, 0.25],   # bm25-dominant
            "temporal":     [0.45, 0.30, 0.25],   # bm25-leaning (time-sorted)
            "semantic":     [0.25, 0.50, 0.25],   # vector-dominant
            "exploratory":  [0.15, 0.45, 0.40],   # vector + graph diverse
        }[q_type]

        # Specificity modulation: high specificity → sharpen dominant weight
        # low specificity → flatten toward uniform
        s = specificity
        dominant_idx = max(range(3), key=lambda i: base[i])
        weights = []
        for i in range(3):
            if i == dominant_idx:
                weights.append(base[i] + 0.10 * (s - 0.5))
            else:
                weights.append(base[i] - 0.05 * (s - 0.5))
        # Normalize
        total = sum(weights)
        weights = [round(w / total, 3) for w in weights]

        # k scales with exploratory-ness (more open = more results)
        k = 15 if s >= 0.7 else (25 if s <= 0.35 else 20)

        return {"type": q_type, "weights": weights, "k": k,
                "needs_retrieval": True, "specificity": round(specificity, 3)}

    @staticmethod
    def _score_skewness(route_scores: list[dict[str, float]]) -> list[float]:
        """SkewRoute: post-retrieval score distribution analysis.

        Analyzes score skewness per route — top-heavy distributions (high skew)
        indicate confident retrieval; flat distributions indicate uncertainty.
        Returns per-route confidence weights ∈ [0,1].

        Zero training, plug-and-play complement to _entropy_refine.
        """
        import math
        n_routes = len(route_scores)
        if n_routes == 0:
            return []

        confidences = []
        for scores in route_scores:
            vals = sorted(scores.values(), reverse=True)
            if len(vals) < 2:
                # Single or no result: neutral confidence
                confidences.append(0.5 if vals else 0.0)
                continue

            # Skewness via standardized 3rd moment
            n = len(vals)
            mean = sum(vals) / n
            if mean == 0:
                confidences.append(0.5)
                continue
            variance = sum((v - mean) ** 2 for v in vals) / n
            if variance == 0:
                # All scores equal → no signal → neutral
                confidences.append(0.5)
                continue
            std = math.sqrt(variance)
            skew = sum((v - mean) ** 3 for v in vals) / (n * std ** 3)

            # Positive skew = top-heavy dropoff = high confidence (good retrieval)
            # Negative/flat skew = uniform scores = low confidence
            # Map skew ∈ [-2, 2] → confidence ∈ [0.1, 0.9] via sigmoid
            confidence = 1.0 / (1.0 + math.exp(-skew))
            confidences.append(confidence)

        # Normalize to sum=1
        total = sum(confidences)
        if total > 0:
            return [c / total for c in confidences]
        return [1.0 / n_routes] * n_routes

    @staticmethod
    def _entropy_refine(rankings: list[list[str]], initial_weights: list[float],
                        max_iter: int = 3) -> list[float]:
        """Entropy-based 权重修正 (Perez et al. ICML VecDB 2025)。

        分析每路检索结果的分数分布熵,低熵=高置信→增加权重。
        Blend: 70% QDAP + 30% Entropy。
        """
        import math
        weights = list(initial_weights)
        n_routes = len(rankings)
        if n_routes < 2:
            return weights

        for _ in range(max_iter):
            # 计算每路的 Shannon 熵 (用排名位置作为概率代理)
            entropies = []
            for ranking in rankings:
                n = len(ranking)
                if n == 0:
                    entropies.append(1.0)  # 空列表=最大不确定
                    continue
                if n == 1:
                    entropies.append(0.0)  # 单结果=零熵=完全确信
                    continue
                probs = [1.0 / (i + 1) for i in range(n)]
                total = sum(probs)
                probs = [p / total for p in probs]
                h = -sum(p * math.log2(p) for p in probs if p > 0)
                h_norm = h / math.log2(n)
                entropies.append(h_norm)

            # 低熵 → 高置信 → 增加权重
            confidences = [1.0 - h for h in entropies]
            total_conf = sum(confidences)
            if total_conf > 0:
                entropy_weights = [c / total_conf for c in confidences]
            else:
                entropy_weights = [1.0 / n_routes] * n_routes

            # Blend
            new_weights = [0.7 * w + 0.3 * ew for w, ew in zip(weights, entropy_weights)]
            if max(abs(n - o) for n, o in zip(new_weights, weights)) < 0.01:
                break
            weights = new_weights

        return weights

    def search_hybrid(self, query: str, embedding: list[float] = None,
                      limit: int = 10, fusion: str = "adaptive",
                      kge_weight: float = 0.0) -> list[dict]:
        """混合搜索: 文本 + 向量(可选) + 图邻居 RRF 融合。

        三路融合策略:
        1. 文本搜索 (search_unified 已有): label/data/tags/kind
        2. 向量搜索 (可选): embedding KNN
        3. 图邻居加权: 邻居节点 bonus

        支持三种融合模式:
        - "rrf": 经典 Reciprocal Rank Fusion, k=60 (向后兼容)
        - "adaptive": QDAP-Lite 查询分类 + 共识奖励 + 小 k 值 (默认)
        - "wrrf": Weighted RRF, 用归一化分数置信度加权

        Args:
            query: 文本查询
            embedding: 可选查询向量
            limit: 返回数量上限
            fusion: 融合模式 ("adaptive" | "rrf" | "wrrf")

        Returns:
            list of {node_id, label, kind, score, sources} 按融合分数降序
        """
        # 收集已知标签用于查询分类
        known_labels = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT label FROM nodes LIMIT 200"
        ).fetchall()]

        # QDAP-Lite 查询分类
        profile = self._classify_query(query, known_labels)

        # Trivial queries skip retrieval entirely
        if not profile.get("needs_retrieval", True):
            return []

        w_bm25, w_vec, w_graph = profile["weights"]
        K = profile["k"] if fusion == "adaptive" else 60

        rrf_scores: dict[str, float] = defaultdict(float)
        sources_map: dict[str, set] = defaultdict(set)
        route_rankings: list[list[str]] = []  # 用于 entropy 修正
        route_scores: list[dict[str, float]] = []  # 用于 WRRF

        # 路1: BM25 文本搜索 (fallback 到 search_unified)
        text_results = self.search_bm25(query, limit=limit * 3)
        if not text_results:
            text_results = [
                {"node_id": r["node"].id, "label": r["node"].label,
                 "kind": r["node"].kind, "score": r["score"],
                 "matched_fields": r["matched_fields"]}
                for r in self.search_unified(query, limit=limit * 3)
            ]
        text_ranking = [item["node_id"] for item in text_results]
        route_rankings.append(text_ranking)
        text_raw_scores = {item["node_id"]: item.get("score", 0.0) for item in text_results}
        route_scores.append(text_raw_scores)
        for rank, item in enumerate(text_results):
            nid = item["node_id"]
            rrf_scores[nid] += w_bm25 / (K + rank + 1)
            sources_map[nid].add("bm25" if "bm25" in item.get("matched_fields", []) else "text")

        # 路2: 向量搜索 (可选)
        vec_ranking = []
        if embedding is not None:
            try:
                vec_results = self.search_similar(embedding, limit=limit * 3)
                vec_ranking = [item["node_id"] for item in vec_results]
                vec_raw_scores = {item["node_id"]: item.get("score", item.get("distance", 0.0))
                                  for item in vec_results}
                route_rankings.append(vec_ranking)
                route_scores.append(vec_raw_scores)
                for rank, item in enumerate(vec_results):
                    nid = item["node_id"]
                    rrf_scores[nid] += w_vec / (K + rank + 1)
                    sources_map[nid].add("vector")
            except (ImportError, ValueError):
                route_rankings.append([])
                route_scores.append({})
        else:
            route_rankings.append([])
            route_scores.append({})

        # 路3: 图邻居加权 (以文本搜索 top 结果为种子, edge-weight-sorted)
        graph_ranking = []
        graph_raw_scores = {}
        if text_results:
            seed_id = text_results[0]["node_id"]
            if self.has_node(seed_id):
                # Weighted bonus: sort neighbors by edge weight (stronger = higher rank)
                neighbor_rows = self.conn.execute(
                    "SELECT n.id, e.weight as ew FROM nodes n"
                    " JOIN edges e ON n.id=e.target WHERE e.source=?"
                    " ORDER BY e.weight DESC",
                    (seed_id,)
                ).fetchall()
                graph_ranking = [r["id"] for r in neighbor_rows]
                max_ew = max((float(r["ew"] or 1.0) for r in neighbor_rows), default=1.0)
                graph_raw_scores = {
                    r["id"]: float(r["ew"] or 1.0) / max_ew for r in neighbor_rows
                }
                route_rankings.append(graph_ranking)
                route_scores.append(graph_raw_scores)
                # Weighted bonus: stronger edges contribute proportionally more
                # Edge weight 1.0 → 2x base RRF; 0.5 → 1.5x; 0.0 → 1x (backward compat)
                for rank, nid in enumerate(graph_ranking):
                    ew_bonus = 1.0 + graph_raw_scores.get(nid, 0.0)
                    rrf_scores[nid] += w_graph * ew_bonus / (K + rank + 1)
                    sources_map[nid].add("graph")
            else:
                route_rankings.append([])
                route_scores.append({})
        else:
            route_rankings.append([])
            route_scores.append({})

        # 路4: KGE (Knowledge Graph Embedding) 路由
        kge_ranking = []
        kge_raw_scores = {}
        if kge_weight > 0 and getattr(self, '_kge_trained', False):
            # 用文本搜索 top 结果作为 KGE 查询种子
            seed_id = text_results[0]["node_id"] if text_results else None
            if seed_id and self.has_node(seed_id):
                kge_results = self._kge_neighbors(seed_id, limit=limit * 3)
                kge_ranking = [r["node_id"] for r in kge_results]
                max_dist = max((r["kge_distance"] for r in kge_results), default=1.0)
                # Convert distance to similarity-like score (closer = higher)
                kge_raw_scores = {
                    r["node_id"]: 1.0 - (r["kge_distance"] / max_dist if max_dist > 0 else 0)
                    for r in kge_results
                }
                for rank, nid in enumerate(kge_ranking):
                    rrf_scores[nid] += kge_weight / (K + rank + 1)
                    sources_map[nid].add("kge")

        # Adaptive: entropy + skewness 权重修正
        if fusion == "adaptive" and len(route_rankings) >= 2:
            entropy_w = self._entropy_refine(route_rankings, [w_bm25, w_vec, w_graph])
            skew_w = self._score_skewness(route_scores)
            # Blend: 60% QDAP base + 20% entropy + 20% skewness
            refined = [
                0.6 * w + 0.2 * e + 0.2 * s
                for w, e, s in zip([w_bm25, w_vec, w_graph], entropy_w, skew_w)
            ]
            # 重新计算 rrf_scores 用修正后的权重 (仅在权重变化显著时)
            if max(abs(r - o) for r, o in zip(refined, [w_bm25, w_vec, w_graph])) > 0.05:
                rrf_scores = defaultdict(float)
                for rank, nid in enumerate(text_ranking):
                    rrf_scores[nid] += refined[0] / (K + rank + 1)
                if embedding is not None and vec_ranking:
                    for rank, nid in enumerate(vec_ranking):
                        rrf_scores[nid] += refined[1] / (K + rank + 1)
                if graph_ranking:
                    for rank, nid in enumerate(graph_ranking):
                        ew_bonus = 1.0 + graph_raw_scores.get(nid, 0.0)
                        rrf_scores[nid] += refined[2] * ew_bonus / (K + rank + 1)

        # WRRF: 置信度加权 (用归一化原始分数)
        if fusion == "wrrf":
            rrf_scores = defaultdict(float)
            for route_idx, raw_scores in enumerate(route_scores):
                if not raw_scores:
                    continue
                max_s = max(raw_scores.values()) if raw_scores else 1.0
                if max_s <= 0:
                    continue
                for rank, nid in enumerate(route_rankings[route_idx]):
                    conf = raw_scores.get(nid, 0.0) / max_s
                    rrf_scores[nid] += conf / (K + rank + 1)

        # 共识奖励 (Exp4Fuse 启发): 多路同时检索到的节点加分
        if fusion in ("adaptive", "wrrf"):
            for nid in list(rrf_scores.keys()):
                n_sources = len(sources_map[nid])
                if n_sources > 1:
                    rrf_scores[nid] *= (1.0 + 0.15 * (n_sources - 1))

        # 排序并构建结果
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        results = []
        for nid, score in ranked:
            node = self.get_node(nid)
            if node:
                results.append({
                    "node_id": nid,
                    "label": node.label,
                    "kind": node.kind,
                    "score": round(score, 6),
                    "sources": sorted(sources_map[nid]),
                    "query_type": profile["type"] if fusion == "adaptive" else None,
                })
        return results

    def remove_embedding(self, node_id: str) -> bool:
        """删除节点的向量嵌入。返回是否实际删除了。"""
        self._ensure_rowid_table()
        row = self.conn.execute("SELECT rowid FROM node_rowids WHERE node_id = ?", (node_id,)).fetchone()
        if not row:
            return False
        cur = self.conn.execute("DELETE FROM vec_nodes WHERE rowid = ?", (row["rowid"],))
        self.conn.execute("DELETE FROM node_rowids WHERE node_id = ?", (node_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def embedding_count(self) -> int:
        """返回已存储嵌入的数量。"""
        try:
            row = self.conn.execute("SELECT COUNT(*) as c FROM vec_nodes").fetchone()
            return row["c"] if row else 0
        except sqlite3.OperationalError:
            return 0

    def add_embeddings_batch(self, items: list[tuple[str, list[float]]]) -> int:
        """批量添加嵌入。items = [(node_id, embedding), ...]

        Returns:
            成功添加的数量
        """
        try:
            import sqlite_vec
        except ImportError:
            raise ImportError("sqlite-vec is required. Install: pip install sqlite-vec")

        if not items:
            return 0

        self._ensure_rowid_table()
        dims = len(items[0][1])
        self._ensure_vec_table(dims)

        count = 0
        for node_id, embedding in items:
            if not self.has_node(node_id):
                continue
            rowid = self._node_to_rowid(node_id)
            vec = sqlite_vec.serialize_float32(embedding)
            self.conn.execute("DELETE FROM vec_nodes WHERE rowid = ?", (rowid,))
            self.conn.execute("INSERT INTO vec_nodes(rowid, embedding) VALUES (?, ?)", (rowid, vec))
            count += 1
        self.conn.commit()
        return count

    def search_similar_to_node(self, node_id: str, limit: int = 10) -> list[dict]:
        """查找与指定节点最相似的其他节点 (基于嵌入向量)。

        Args:
            node_id: 种子节点 ID (必须有嵌入)
            limit: 返回数量上限

        Returns:
            list of {node_id, label, kind, distance, score} 排除自身

        Raises:
            ValueError: 如果节点不存在或没有嵌入
        """
        try:
            import sqlite_vec
        except ImportError:
            raise ImportError("sqlite-vec is required. Install: pip install sqlite-vec")

        self._ensure_rowid_table()
        row = self.conn.execute("SELECT rowid FROM node_rowids WHERE node_id = ?", (node_id,)).fetchone()
        if not row:
            raise ValueError(f"No embedding found for node: {node_id}")

        seed_rowid = row["rowid"]
        # 使用子查询直接获取种子向量并匹配
        rows = self.conn.execute(
            """
            SELECT v.rowid, v.distance, n.id, n.label, n.kind, n.weight
            FROM vec_nodes AS v
            JOIN node_rowids AS r ON v.rowid = r.rowid
            JOIN nodes AS n ON r.node_id = n.id
            WHERE v.embedding MATCH (
                SELECT embedding FROM vec_nodes WHERE rowid = ?
            ) AND v.k = ?
            ORDER BY v.distance
            """,
            (seed_rowid, limit + 1)
        ).fetchall()
        results = []
        for r in rows:
            if r["id"] == node_id:
                continue
            dist = r["distance"]
            score = 1.0 / (1.0 + dist)
            results.append({
                "node_id": r["id"],
                "label": r["label"],
                "kind": r["kind"],
                "distance": round(dist, 6),
                "score": round(score, 6),
                "weight": r["weight"],
            })
        return results[:limit]

    def vector_stats(self) -> dict:
        """返回向量存储的统计信息。"""
        count = self.embedding_count()
        if count == 0:
            return {"count": 0, "has_vectors": False}
        node_count = self.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        coverage = round(count / node_count, 4) if node_count > 0 else 0.0
        # 维度
        dims = getattr(self, '_vec_dims', None)
        if not dims:
            row = self.conn.execute("SELECT sql FROM sqlite_master WHERE name='vec_nodes'").fetchone()
            if row:
                import re
                m = re.search(r'float\[(\d+)\]', row["sql"])
                dims = int(m.group(1)) if m else None
        return {
            "count": count,
            "has_vectors": True,
            "dimensions": dims,
            "node_count": node_count,
            "coverage": coverage,
        }

    def has_embedding(self, node_id: str) -> bool:
        """检查节点是否有嵌入向量。"""
        self._ensure_rowid_table()
        row = self.conn.execute("SELECT rowid FROM node_rowids WHERE node_id = ?", (node_id,)).fetchone()
        if not row:
            return False
        vec_row = self.conn.execute("SELECT rowid FROM vec_nodes WHERE rowid = ?", (row["rowid"],)).fetchone()
        return vec_row is not None

    def update_embedding(self, node_id: str, embedding: list[float]) -> bool:
        """更新已有嵌入向量。如果节点没有嵌入则创建。返回是否成功。"""
        self.remove_embedding(node_id)
        self.add_embedding(node_id, embedding)
        return True

    def remove_embeddings_batch(self, node_ids: list[str]) -> int:
        """批量删除嵌入向量。返回实际删除数量。"""
        removed = 0
        for nid in node_ids:
            if self.remove_embedding(nid):
                removed += 1
        return removed

    def search_similar_by_kind(self, embedding: list[float], kind: str, limit: int = 10) -> list[dict]:
        """在特定 kind 的节点中搜索相似向量。"""
        all_results = self.search_similar(embedding, limit=limit * 5)
        return [r for r in all_results if self.get_node(r["node_id"]).kind == kind][:limit]

    def search_similar_by_tag(self, embedding: list[float], tag: str, limit: int = 10) -> list[dict]:
        """在特定标签的节点中搜索相似向量。"""
        tagged = self.search_by_tag(tag)
        tagged_ids = {n.id for n in tagged}
        if not tagged_ids:
            return []
        all_results = self.search_similar(embedding, limit=limit * 5)
        return [r for r in all_results if r["node_id"] in tagged_ids][:limit]

    # ── GraphRAG 统一检索 ─────────────────────────────────

    def search_graphrag(self, query: str, mode: str = "hybrid",
                        embedding: list[float] = None,
                        limit: int = 10,
                        expand_hops: int = 1) -> list[dict]:
        """GraphRAG-style unified retrieval with mode selection.

        Modes:
        - "naive": Direct text search (BM25/search_unified)
        - "local": Text search + 1-hop graph expansion
        - "global": Community-level search (find relevant communities first)
        - "hybrid": Full 3-way RRF fusion (text + vector + graph) via search_hybrid

        Each result includes: node_id, label, kind, score, sources, community (if detected).

        Args:
            query: Natural language query
            mode: Retrieval mode (naive/local/global/hybrid)
            embedding: Optional query vector for hybrid mode
            limit: Max results
            expand_hops: Graph expansion depth for local mode

        Returns:
            list of dicts sorted by score descending
        """
        if mode == "hybrid":
            results = self.search_hybrid(query, embedding=embedding, limit=limit)
            for r in results:
                r.setdefault("sources", ["hybrid"])
            return results

        if mode == "naive":
            results = self.search_bm25(query, limit=limit)
            if not results:
                results = [
                    {"node_id": r["node"].id, "label": r["node"].label,
                     "kind": r["node"].kind, "score": r["score"],
                     "sources": ["text"]}
                    for r in self.search_unified(query, limit=limit)
                ]
            return results

        if mode == "local":
            # Step 1: find seed nodes via text search
            seeds = self.search_bm25(query, limit=max(limit // 2, 3))
            if not seeds:
                seeds = [
                    {"node_id": r["node"].id, "label": r["node"].label,
                     "kind": r["node"].kind, "score": r["score"]}
                    for r in self.search_unified(query, limit=max(limit // 2, 3))
                ]
            if not seeds:
                return []
            # Step 2: expand with graph neighbors
            expanded = {}
            for seed in seeds:
                nid = seed["node_id"]
                expanded[nid] = seed
                expanded[nid]["sources"] = ["text"]
                # Get neighbors
                for nb in self.neighbors(nid, depth=expand_hops):
                    if nb.id not in expanded:
                        expanded[nb.id] = {
                            "node_id": nb.id, "label": nb.label,
                            "kind": nb.kind, "score": seed["score"] * 0.5,
                            "sources": ["graph"]
                        }
                    else:
                        if "graph" not in expanded[nb.id].get("sources", []):
                            expanded[nb.id]["sources"].append("graph")
            results = sorted(expanded.values(), key=lambda x: x.get("score", 0), reverse=True)
            return results[:limit]

        if mode == "global":
            # Community-level search: find which communities are relevant
            # Use Leiden for better community detection
            comm_map = self.detect_communities_leiden()
            if not comm_map:
                return self.search_graphrag(query, mode="naive", limit=limit)
            communities = {}
            for nid, cid in comm_map.items():
                communities.setdefault(cid, []).append(nid)
            summaries = self.community_summary(communities=communities)
            # Score communities by tag/keyword overlap with query
            query_lower = query.lower()
            scored_communities = []
            for summary in summaries:
                score = 0.0
                for tag, freq in summary.get("top_tags", []):
                    if tag.lower() in query_lower or query_lower in tag.lower():
                        score += freq * 2
                for member in summary.get("top_members", []):
                    if query_lower in member.get("label", "").lower():
                        score += 3
                scored_communities.append((summary["id"], score, summary))
            scored_communities.sort(key=lambda x: x[1], reverse=True)
            # Take top community and return its members
            if not scored_communities or scored_communities[0][1] == 0:
                return self.search_graphrag(query, mode="local", limit=limit,
                                           embedding=embedding) if embedding else \
                       self.search_graphrag(query, mode="naive", limit=limit)
            best_comm_id = scored_communities[0][0]
            node_ids = communities[best_comm_id]
            # Return community members sorted by weight
            placeholders = ",".join("?" * len(node_ids))
            rows = self.conn.execute(
                f"SELECT id, label, kind, weight FROM nodes WHERE id IN ({placeholders}) "
                "ORDER BY weight DESC LIMIT ?",
                (*node_ids, limit)
            ).fetchall()
            return [
                {"node_id": r["id"], "label": r["label"],
                 "kind": r["kind"], "score": r["weight"],
                 "sources": ["community"],
                 "community": best_comm_id}
                for r in rows
            ]

        # Unknown mode: fallback to hybrid
        return self.search_graphrag(query, mode="hybrid", embedding=embedding, limit=limit)

    def random_walk(self, start_id: str, steps: int = 10,
                    restart_prob: float = 0.0,
                    weight_key: str = None) -> list[str]:
        """Random walk on the graph from *start_id*.

        At each step, move to a random neighbor (weighted by edge weight
        if *weight_key* given).  With probability *restart_prob*, teleport
        back to the start node (PageRank-style random walk with restart).

        Useful for:
          - Graph sampling (node2vec / DeepWalk embedding prep)
          - Personalized PageRank approximation
          - GraphRAG local exploration

        Args:
            start_id: Starting node ID.
            steps: Number of steps to take.
            restart_prob: Probability of teleporting back to start (0-1).
            weight_key: Edge property key for weighted random selection.
                        If None, uniform random.

        Returns:
            List of visited node IDs (length ≤ steps + 1).
            Empty list if start_id not found.
        """
        import random as _rng
        _r = _rng.Random(42)

        existing = self.conn.execute(
            "SELECT id FROM nodes WHERE id = ?", (start_id,)).fetchone()
        if not existing:
            return []

        path = [start_id]
        current = start_id

        for _ in range(steps):
            if restart_prob > 0 and _r.random() < restart_prob:
                current = start_id
                path.append(current)
                continue

            rows = self.conn.execute(
                "SELECT target, weight FROM edges WHERE source = ? "
                "UNION "
                "SELECT source, weight FROM edges WHERE target = ?",
                (current, current)).fetchall()

            if not rows:
                break

            if weight_key and weight_key != "weight":
                # Look up custom property
                neighbors = []
                for r in rows:
                    props = self.get_edge_properties(
                        str(r["target"]) if str(r["target"]) != current else str(r["source"]),
                        current)
                    w = props.get(weight_key, float(r["weight"] or 1.0))
                    nb = str(r["target"]) if str(r["target"]) != current else str(r["source"])
                    neighbors.append((nb, w))
            else:
                neighbors = [(str(r["target"]) if str(r["target"]) != current
                             else str(r["source"]),
                             float(r["weight"] or 1.0)) for r in rows]

            total_w = sum(w for _, w in neighbors)
            if total_w <= 0:
                break

            pick = _r.random() * total_w
            cumulative = 0.0
            for nb, w in neighbors:
                cumulative += w
                if cumulative >= pick:
                    current = nb
                    break
            else:
                current = neighbors[-1][0]

            path.append(current)

        return path

    def graph_sample(self, start_id: str, max_nodes: int = 50,
                     strategy: str = "bfs") -> list[str]:
        """Extract a representative subgraph sample.

        Strategies:
          - ``bfs``: Breadth-first expansion from start_id.
          - ``dfs``: Depth-first expansion.
          - ``random_walk``: Random walk sampling (good for preserving
            structural properties with fewer nodes).

        Args:
            start_id: Seed node for sampling.
            max_nodes: Maximum nodes to include.
            strategy: Sampling strategy.

        Returns:
            List of node IDs in the sample (including start_id).
        """
        if strategy == "bfs":
            visited = []
            seen = {start_id}
            queue = [start_id]
            while queue and len(visited) < max_nodes:
                nid = queue.pop(0)
                if nid in seen and nid not in visited:
                    pass
                if nid not in visited:
                    visited.append(nid)
                rows = self.conn.execute(
                    "SELECT target FROM edges WHERE source = ? "
                    "UNION SELECT source FROM edges WHERE target = ?",
                    (nid, nid)).fetchall()
                for r in rows:
                    nb = str(r[0])
                    if nb not in seen:
                        seen.add(nb)
                        queue.append(nb)
            return visited[:max_nodes]

        elif strategy == "dfs":
            return self.dfs_order(start_id, max_depth=max_nodes)[:max_nodes]

        else:  # random_walk
            walk = self.random_walk(start_id, steps=max_nodes * 3)
            seen = []
            for nid in walk:
                if nid not in seen:
                    seen.append(nid)
                if len(seen) >= max_nodes:
                    break
            return seen

    def smart_query_route(self, query: str, embedding: list[float] = None,
                          limit: int = 10) -> dict:
        """Automatically choose the best GraphRAG mode based on query analysis.

        Heuristics (based on ICLR 2026 GraphRAG-Bench findings):
        - Single-entity lookups → naive (RAG beats GraphRAG on simple tasks)
        - Multi-entity / relational → local (graph expansion helps)
        - Aggregation / "all" / "every" → global (community-level)
        - Complex / multi-hop with embedding → hybrid (RRF fusion)

        Returns:
            dict with keys:
              - mode: chosen mode (naive/local/global/hybrid)
              - results: list of result dicts
              - reason: explanation for the routing decision
              - query_traits: analysed query characteristics
        """
        import re

        q_lower = query.lower().strip()
        traits = {
            "word_count": len(query.split()),
            "has_multiple_entities": False,
            "has_aggregation": False,
            "has_temporal": False,
            "has_relational": False,
        }

        # Aggregation cues
        agg_patterns = ["all", "every", "summary", "summarize", "overview",
                        "how many", "count", "total", "list all", "which.*all"]
        traits["has_aggregation"] = any(re.search(p, q_lower) for p in agg_patterns)

        # Temporal cues
        temporal_patterns = ["when", "latest", "oldest", "recent", "before",
                             "after", "since", "until", "timeline", "history"]
        traits["has_temporal"] = any(re.search(p, q_lower) for p in temporal_patterns)

        # Relational cues
        rel_patterns = ["relate", "connect", "link", "between", "path",
                        "neighbor", "influence", "depend", "parent", "child",
                        "cause", "effect"]
        traits["has_relational"] = any(re.search(p, q_lower) for p in rel_patterns)

        # Multi-entity: capitalised words or quoted strings as entity hints
        cap_words = re.findall(r'\b[A-Z][a-z]+\b', query)
        quoted = re.findall(r'["\']([^"\']+)["\']', query)
        entities = cap_words + quoted
        traits["has_multiple_entities"] = len(set(e.lower() for e in entities)) >= 2

        # --- Routing decision (priority order) ---
        if traits["has_aggregation"]:
            mode = "global"
            reason = "Aggregation cue detected → community-level search"
        elif traits["has_multiple_entities"] and traits["has_relational"]:
            mode = "local"
            reason = "Multi-entity + relational cues → graph expansion"
        elif embedding is not None and (
            traits["has_temporal"] or traits["has_multiple_entities"]
            or traits["word_count"] > 8
        ):
            mode = "hybrid"
            reason = "Complex query + embedding available → RRF fusion"
        elif traits["word_count"] <= 3 and not traits["has_relational"]:
            mode = "naive"
            reason = "Short lookup query → direct text search"
        elif traits["has_relational"]:
            mode = "local"
            reason = "Relational cue → graph expansion"
        else:
            mode = "hybrid" if embedding is not None else "naive"
            reason = f"Default → {mode} (embedding {'available' if embedding else 'absent'})"

        results = self.search_graphrag(
            query, mode=mode, embedding=embedding, limit=limit)

        return {
            "mode": mode,
            "results": results,
            "reason": reason,
            "query_traits": traits,
        }

    # ── 高级图分析 ────────────────────────────────────────

    def closeness_vitality(self, node_id: str) -> float | None:
        """计算节点删除后 Wiener 指数的变化量。

        closeness_vitality = W(G\{v}) - W(G)
        正值表示该节点对图连通性重要（删除后距离增加），
        负值表示该节点是瓶颈（删除后图更紧凑或断裂）。

        Args:
            node_id: 节点 ID

        Returns:
            Wiener 指数变化量，或 None（节点不存在）
        """
        if not self.has_node(node_id):
            return None

        # W(G)
        w_before = self.wiener_index() or 0

        # W(G\{v}) — 临时删除节点
        node_row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        edges_out = self.conn.execute("SELECT * FROM edges WHERE source=?", (node_id,)).fetchall()
        edges_in = self.conn.execute("SELECT * FROM edges WHERE target=?", (node_id,)).fetchall()

        self.conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        self.conn.execute("DELETE FROM edges WHERE source=? OR target=?", (node_id, node_id))
        self.conn.commit()

        w_after = self.wiener_index() or 0

        # 恢复
        self.conn.execute(
            "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
            (node_row["id"], node_row["label"], node_row["kind"], node_row["data"],
             node_row["created"], node_row["accessed"], node_row["weight"], node_row["tags"]))
        for e in edges_out + edges_in:
            self.conn.execute(
                "INSERT OR IGNORE INTO edges (source,target,relation,weight) VALUES (?,?,?,?)",
                (e["source"], e["target"], e["relation"], e["weight"]))
        self.conn.commit()

        return w_after - w_before

    def spectral_radius(self) -> float | None:
        """计算邻接矩阵的谱半径（最大特征值的绝对值）。

        使用幂迭代法（power iteration）求最大特征值。
        谱半径反映了图的"活跃程度":
        - 高谱半径 = 强连通、hub-hub 连接多
        - 低谱半径 = 稀疏、长链状结构

        Returns:
            谱半径，或 None（空图）
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if n == 0:
            return None

        idx = {nid: i for i, nid in enumerate(node_ids)}

        # 构建对称邻接表（无向处理）
        adj_sym: dict[int, set[int]] = defaultdict(set)
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if e["source"] in idx and e["target"] in idx:
                i, j = idx[e["source"]], idx[e["target"]]
                adj_sym[i].add(j)
                adj_sym[j].add(i)

        # 幂迭代（Power Iteration on A²）
        # 使用 A² 避免负特征值导致的振荡
        import random
        random.seed(42)
        v = [random.random() for _ in range(n)]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        v = [x / norm for x in v]

        eigenvalue = 0.0
        for _ in range(300):
            # v_new = A² @ v (两步)
            w = [sum(v[j] for j in adj_sym[i]) for i in range(n)]
            v_new = [sum(w[j] for j in adj_sym[i]) for i in range(n)]

            norm_new = math.sqrt(sum(x * x for x in v_new)) or 1e-15
            # 特征值估计 = ||A²v|| / ||v|| 的平方根
            new_eigenvalue = math.sqrt(norm_new)  # sqrt(||A²v||) ≈ |λ_max|
            v_new = [x / norm_new for x in v_new]

            if abs(new_eigenvalue - eigenvalue) < 1e-9:
                eigenvalue = new_eigenvalue
                break
            eigenvalue = new_eigenvalue
            v = v_new

        return abs(eigenvalue)

    def minimum_spanning_tree(self) -> list[dict] | None:
        """使用 Kruskal 算法计算最小生成树（MST）。

        对无向图（忽略边的方向）执行 Kruskal 算法，返回权重最小的生成树边集。
        使用 Union-Find（路径压缩 + 按秩合并）实现高效连通分量检测。

        Returns:
            MST 边列表 [{source, target, relation, weight}, ...]，按权重升序；
            None（图空或不连通）
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if n < 2:
            return None

        # 收集所有边（无向化：保留 source < target 的唯一边，取最小权重）
        raw_edges = self.conn.execute(
            "SELECT source, target, relation, weight FROM edges ORDER BY weight ASC"
        ).fetchall()

        edge_map: dict[tuple, dict] = {}
        for e in raw_edges:
            key = (min(e["source"], e["target"]), max(e["source"], e["target"]))
            if key not in edge_map or e["weight"] < edge_map[key]["weight"]:
                edge_map[key] = dict(source=e["source"], target=e["target"],
                                     relation=e["relation"], weight=e["weight"])

        edges_sorted = sorted(edge_map.values(), key=lambda e: e["weight"])

        # Union-Find
        parent = {nid: nid for nid in node_ids}
        rank = {nid: 0 for nid in node_ids}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra == rb:
                return False
            if rank[ra] < rank[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            if rank[ra] == rank[rb]:
                rank[ra] += 1
            return True

        mst = []
        for e in edges_sorted:
            if union(e["source"], e["target"]):
                mst.append(e)
                if len(mst) == n - 1:
                    break

        # 检查连通性
        if len(mst) < n - 1:
            return None

        return mst

    def mst_weight(self) -> float | None:
        """计算最小生成树的总权重。

        Returns:
            MST 总权重，或 None（图空或不连通）
        """
        mst = self.minimum_spanning_tree()
        if mst is None:
            return None
        return sum(e["weight"] for e in mst)

    # ── 谱分析（代数连通度 + Fiedler 向量）────────────────

    def algebraic_connectivity(self) -> float | None:
        """计算图的代数连通度（Fiedler value）——拉普拉斯矩阵的第二小特征值。

        代数连通度衡量图的整体连通强度:
        - 0 = 图不连通
        - 大值 = 强连通（移除少量边不会断开图）
        - 小正数 = 脆弱连通

        Returns:
            代数连通度，或 None（空图/单节点）
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if n < 2:
            return None

        idx = {nid: i for i, nid in enumerate(node_ids)}
        degree = [0] * n
        adj_sym: dict[int, set[int]] = defaultdict(set)
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if e["source"] in idx and e["target"] in idx:
                i, j = idx[e["source"]], idx[e["target"]]
                adj_sym[i].add(j)
                adj_sym[j].add(i)
                degree[i] += 1
                degree[j] += 1

        # 构建拉普拉斯矩阵 L = D - A
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            L[i][i] = float(degree[i])
            for j in adj_sym[i]:
                L[i][j] = -1.0

        eigenvalues = self._sym_eigenvalues(L)
        eigenvalues.sort()
        # 代数连通度 = 第二小特征值
        # 连通图: 第二小 > 0; 不连通图: 第二小 = 0
        if len(eigenvalues) < 2:
            return None
        return max(0.0, eigenvalues[1])

    def _sym_eigenvalues(self, M: list[list[float]], max_iter: int = 300) -> list[float]:
        """雅可比旋转求实对称矩阵全部特征值。"""
        n = len(M)
        A = [row[:] for row in M]
        for _ in range(max_iter):
            p, q = 0, 1
            max_val = abs(A[0][1])
            for i in range(n):
                for j in range(i + 1, n):
                    if abs(A[i][j]) > max_val:
                        max_val = abs(A[i][j])
                        p, q = i, j
            if max_val < 1e-12:
                break
            if abs(A[p][p] - A[q][q]) < 1e-15:
                theta = math.pi / 4
            else:
                theta = 0.5 * math.atan2(2 * A[p][q], A[p][p] - A[q][q])
            c, s = math.cos(theta), math.sin(theta)
            for i in range(n):
                if i == p or i == q:
                    continue
                aip, aiq = A[i][p], A[i][q]
                A[i][p] = c * aip + s * aiq; A[p][i] = A[i][p]
                A[i][q] = -s * aip + c * aiq; A[q][i] = A[i][q]
            app, aqq, apq = A[p][p], A[q][q], A[p][q]
            A[p][p] = c*c*app + 2*s*c*apq + s*s*aqq
            A[q][q] = s*s*app - 2*s*c*apq + c*c*aqq
            A[p][q] = 0.0; A[q][p] = 0.0
        return [A[i][i] for i in range(n)]

    def fiedler_vector(self) -> list[float] | None:
        """计算 Fiedler 向量——对应代数连通度的特征向量。

        Fiedler 向量可用于:
        - 谱二分（正/负分两组）
        - 节点排序（与连通性的关系）
        - 图嵌入（1D 谱嵌入）

        Returns:
            与 node_ids 顺序对应的 Fiedler 向量，或 None
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if n < 2:
            return None

        idx = {nid: i for i, nid in enumerate(node_ids)}
        degree = [0] * n
        adj_sym: dict[int, set[int]] = defaultdict(set)
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if e["source"] in idx and e["target"] in idx:
                i, j = idx[e["source"]], idx[e["target"]]
                adj_sym[i].add(j); adj_sym[j].add(i)
                degree[i] += 1; degree[j] += 1

        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            L[i][i] = float(degree[i])
            for j in adj_sym[i]:
                L[i][j] = -1.0

        import random; random.seed(123)
        v = [random.random() - 0.5 for _ in range(n)]
        mean = sum(v) / n
        v = [x - mean for x in v]
        norm = math.sqrt(sum(x * x for x in v)) or 1e-15
        v = [x / norm for x in v]

        eps = 1e-6
        for _ in range(500):
            x = self._cg_solve(L, v, eps)
            if x is None: break
            mean_x = sum(x) / n
            x = [xi - mean_x for xi in x]
            norm_x = math.sqrt(sum(xi * xi for xi in x)) or 1e-15
            x = [xi / norm_x for xi in x]
            diff = sum((x[i] - v[i]) ** 2 for i in range(n))
            v = x
            if diff < 1e-14: break
        return v

    def _cg_solve(self, L: list[list[float]], b: list[float], eps: float) -> list[float] | None:
        """共轭梯度法求解 (L + eps*I)x = b。"""
        n = len(b)
        def Mx(v: list[float]) -> list[float]:
            return [sum(L[i][j] * v[j] for j in range(n)) + eps * v[i] for i in range(n)]
        x = [0.0] * n
        r = b[:]
        p = r[:]
        rs_old = sum(r[i] * r[i] for i in range(n))
        if rs_old < 1e-30: return x
        for _ in range(n * 3):
            Mp = Mx(p)
            pMp = sum(p[i] * Mp[i] for i in range(n))
            if abs(pMp) < 1e-30: break
            alpha = rs_old / pMp
            x = [x[i] + alpha * p[i] for i in range(n)]
            r = [r[i] - alpha * Mp[i] for i in range(n)]
            rs_new = sum(r[i] * r[i] for i in range(n))
            if rs_new < 1e-20: break
            beta = rs_new / rs_old
            p = [r[i] + beta * p[i] for i in range(n)]
            rs_old = rs_new
        return x

    # ── 连通性分析（node/edge connectivity）─────────────────

    def node_connectivity(self) -> int:
        """计算图的节点连通度 κ(G)——使图不连通所需移除的最少节点数。

        使用 Menger 定理：κ(G) = min over all (s,t) of max node-disjoint paths。
        实现基于节点分裂最大流。

        Returns:
            节点连通度（0 = 不连通/单节点/空图）
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if n < 2:
            return 0

        idx = {nid: i for i, nid in enumerate(node_ids)}
        adj_sym: dict[int, set[int]] = defaultdict(set)
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if e["source"] in idx and e["target"] in idx:
                i, j = idx[e["source"]], idx[e["target"]]
                adj_sym[i].add(j); adj_sym[j].add(i)

        # BFS 连通性检查
        visited = {0}; queue = [0]
        while queue:
            u = queue.pop(0)
            for v in adj_sym[u]:
                if v not in visited:
                    visited.add(v); queue.append(v)
        if len(visited) < n:
            return 0

        # 优化: 只从度最小节点 s 出发
        degrees = [len(adj_sym[i]) for i in range(n)]
        s = min(range(n), key=lambda i: degrees[i])
        min_cut = n

        for t in range(n):
            if t == s: continue
            flow = self._node_split_maxflow(s, t, n, adj_sym)
            if flow < min_cut:
                min_cut = flow
                if min_cut == 0: break

        return min_cut

    def _node_split_maxflow(self, s: int, t: int, n: int,
                            adj_sym: dict[int, set[int]]) -> int:
        """节点分裂法求 s-t 最小节点割（Edmonds-Karp with bottleneck）。"""
        INF = n + 1
        source = s * 2 + 1  # s_out
        sink = t * 2        # t_in

        cap: dict[tuple[int,int], int] = {}
        for i in range(n):
            if i not in (s, t):
                cap[(i*2, i*2+1)] = 1
            for j in adj_sym[i]:
                # Direct s→t edge counts as 1 internally vertex-disjoint path
                if (i == s and j == t) or (i == t and j == s):
                    if i*2+1 not in [k for k,_v in [(a,b) for (a,b) in cap]]:
                        pass  # handled below
                cap[(i*2+1, j*2)] = INF
        # Override direct s_out→t_in to cap=1
        cap[(s*2+1, t*2)] = 1

        total_flow = 0
        while True:
            visited = {source}; parent = {}; queue = [source]
            while queue and sink not in visited:
                u = queue.pop(0)
                for (a, b), c in cap.items():
                    if a == u and b not in visited and c > 0:
                        visited.add(b); parent[b] = u; queue.append(b)
            if sink not in visited: break

            # Compute bottleneck
            bottleneck = INF
            v = sink
            while v in parent:
                u = parent[v]
                bottleneck = min(bottleneck, cap.get((u, v), 0))
                v = u

            total_flow += bottleneck
            if total_flow >= INF: break

            v = sink
            while v in parent:
                u = parent[v]
                cap[(u, v)] -= bottleneck
                cap[(v, u)] = cap.get((v, u), 0) + bottleneck
                v = u

        return total_flow

    def edge_connectivity(self) -> int:
        """计算图的边连通度 λ(G)——使图不连通所需移除的最少边数。

        Returns:
            边连通度（0 = 不连通/单节点/空图）
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if n < 2:
            return 0

        idx = {nid: i for i, nid in enumerate(node_ids)}
        adj_sym: dict[int, set[int]] = defaultdict(set)
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if e["source"] in idx and e["target"] in idx:
                i, j = idx[e["source"]], idx[e["target"]]
                adj_sym[i].add(j); adj_sym[j].add(i)

        # 连通性
        visited = {0}; queue = [0]
        while queue:
            u = queue.pop(0)
            for v in adj_sym[u]:
                if v not in visited:
                    visited.add(v); queue.append(v)
        if len(visited) < n:
            return 0

        degrees = [len(adj_sym[i]) for i in range(n)]
        s = min(range(n), key=lambda i: degrees[i])
        min_cut = degrees[s]

        for t in range(n):
            if t == s: continue
            flow = self._ek_unit(s, t, n, adj_sym)
            if flow < min_cut:
                min_cut = flow
                if min_cut == 0: break

        return min_cut

    def _ek_unit(self, s: int, t: int, n: int,
                 adj_sym: dict[int, set[int]]) -> int:
        """单位容量图 Edmonds-Karp。"""
        residual: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for u in range(n):
            for v in adj_sym[u]:
                residual[u][v] = 1

        total_flow = 0
        while True:
            visited = {s}; parent = {}; queue = [s]
            while queue and t not in visited:
                u = queue.pop(0)
                for v in range(n):
                    if v not in visited and residual[u][v] > 0:
                        visited.add(v); parent[v] = u; queue.append(v)
            if t not in visited: break
            total_flow += 1
            v = t
            while v in parent:
                u = parent[v]
                residual[u][v] -= 1
                residual[v][u] += 1
                v = u
        return total_flow

    def percolation_centrality(self, states: dict[str, float] | None = None) -> dict[str, float]:
        """计算渗透中心性（percolation centrality）。

        渗透中心性衡量节点在"渗透"过程中传播信息的重要性。
        每个节点有一个渗透状态 x ∈ [0,1]（默认用 degree/max_degree）。
        渗透中心性 = sum over (s,t): σ_st(v)/σ_st * x_s*x_t / sum(x_s*x_t)

        Args:
            states: 可选的 {node_id: state} 映射，默认用归一化度数

        Returns:
            {node_id: percolation_centrality} 字典
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if n < 3:
            return {nid: 0.0 for nid in node_ids}

        idx = {nid: i for i, nid in enumerate(node_ids)}
        adj_sym: dict[int, set[int]] = defaultdict(set)
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if e["source"] in idx and e["target"] in idx:
                i, j = idx[e["source"]], idx[e["target"]]
                adj_sym[i].add(j); adj_sym[j].add(i)

        # Default states = normalized degree
        if states is None:
            degrees = [len(adj_sym[i]) for i in range(n)]
            max_deg = max(degrees) if degrees else 1
            x = [d / max_deg for d in degrees]
        else:
            x = [states.get(nid, 0.0) for nid in node_ids]

        # BFS shortest paths for all pairs (unweighted)
        # σ[s][t] = number of shortest paths from s to t
        # σ_through[v][s][t] = 1 if v is on some shortest s-t path
        import collections
        sigma = [[0]*n for _ in range(n)]
        pred = [[[] for _ in range(n)] for _ in range(n)]
        dist = [[float('inf')]*n for _ in range(n)]

        for s in range(n):
            sigma[s][s] = 1; dist[s][s] = 0
            queue = collections.deque([s])
            while queue:
                u = queue.popleft()
                for v in adj_sym[u]:
                    if dist[s][v] == float('inf'):
                        dist[s][v] = dist[s][u] + 1
                        queue.append(v)
                    if dist[s][v] == dist[s][u] + 1:
                        sigma[s][v] += sigma[s][u]
                        pred[s][v].append(u)

        # For each node v, compute percolation centrality
        # p(v) = (1/(n-2)) * sum_{s≠v≠t} σ_sv(v)/σ_sv * x_s*x_t / (sum_{s<t} x_s*x_t)
        # Simplified: skip normalization denominator, use relative values

        # First compute dependency: δ[v] = sum_{s<t: v on s-t path} x_s * x_t / σ_st * σ_st(v)
        # Using Brandes-like accumulation
        delta = [[0.0]*n for _ in range(n)]  # delta[s][v]
        result = [0.0] * n

        for s in range(n):
            # Process nodes in reverse BFS order from s
            order = sorted(range(n), key=lambda v: -dist[s][v] if dist[s][v] != float('inf') else 0)
            for t in order:
                if t == s or dist[s][t] == float('inf'):
                    continue
                for w in pred[s][t]:
                    ratio = sigma[s][w] / sigma[s][t] if sigma[s][t] > 0 else 0
                    delta[s][w] += ratio * (x[t] + delta[s][t])

            for v in range(n):
                if v != s:
                    result[v] += x[s] * delta[s][v]

        # Normalize to [0, 1]
        max_result = max(result) if result else 1
        if max_result == 0:
            max_result = 1

        return {node_ids[i]: result[i] / max_result for i in range(n)}

    def triad_census(self) -> dict[str, int]:
        """计算有向图的三元组普查(triad census)。

        统计所有可能的有向三元组类型(共16种，MaaS convention)。
        三元组由3个节点和它们之间的有向边组成。
        编码方式: 每条边用数字表示:
            0 = 无边, 1 = i→j 方向, 2 = j→i 方向, 3 = 双向
        三元组编码: (ij)(ik)(jk) 三对关系的编码拼接。

        Returns:
            dict: 16种三元组类型的计数，键为3位编码字符串。
        """
        # 获取所有节点和邻接关系
        nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        node_list = [r[0] for r in nodes]
        n = len(node_list)
        if n < 3:
            # 不足3个节点，全部为0
            return {f"{a}{b}{c}": 0 for a in range(4) for b in range(4)
                    for c in range(4)
                    if not (a == 0 and b == 0 and c == 0)}

        # 构建邻接集合
        out_edges = {}
        rows = self.conn.execute("SELECT source, target FROM edges").fetchall()
        for s, t in rows:
            out_edges.setdefault(s, set()).add(t)

        # 初始化16种类型的计数
        census = {f"{a}{b}{c}": 0 for a in range(4) for b in range(4)
                  for c in range(4)
                  if not (a == 0 and b == 0 and c == 0)}

        def edge_code(u, v):
            """计算u和v之间的边编码。"""
            has_uv = v in out_edges.get(u, set())
            has_vu = u in out_edges.get(v, set())
            if has_uv and has_vu:
                return 3
            elif has_uv:
                return 1
            elif has_vu:
                return 2
            return 0

        # 遍历所有三元组 (i < j < k)
        for ii in range(n):
            i = node_list[ii]
            for jj in range(ii + 1, n):
                j = node_list[jj]
                ij = edge_code(i, j)
                for kk in range(jj + 1, n):
                    k = node_list[kk]
                    ik = edge_code(i, k)
                    jk = edge_code(j, k)
                    code = f"{ij}{ik}{jk}"
                    if code != "000":
                        census[code] = census.get(code, 0) + 1

        # 移除全零条目（已排除）
        return {k: v for k, v in census.items() if v >= 0}

    def average_neighbor_degree(self) -> dict[str, float]:
        """计算每个节点的平均邻居度数。

        k_nn(i) = (1/k_i) * sum(k_j for j in neighbors(i))
        高值 = 邻居是高度节点(hub连接), 低值 = 邻居是低度节点。

        Returns:
            dict: {node_id: average_neighbor_degree}，孤立节点不包含。
        """
        rows = self.conn.execute(
            "SELECT source, target FROM edges"
        ).fetchall()

        # 构建无向邻接表和度数
        neighbors_map = {}
        for s, t in rows:
            neighbors_map.setdefault(s, set()).add(t)
            neighbors_map.setdefault(t, set()).add(s)

        degree = {nid: len(nbrs) for nid, nbrs in neighbors_map.items()}
        result = {}
        all_nodes = self.conn.execute("SELECT id FROM nodes").fetchall()
        for (nid,) in all_nodes:
            k = degree.get(nid, 0)
            if k == 0:
                continue
            nbrs = neighbors_map.get(nid, set())
            if not nbrs:
                continue
            knn = sum(degree.get(n, 0) for n in nbrs) / k
            result[nid] = round(knn, 6)
        return result

    def degree_correlation(self) -> float | None:
        """计算度-度相关系数(Newman assortativity coefficient)。

        基于边端点度数的 Pearson 相关系数。
        r > 0: 同配(高度节点连接高度节点)
        r < 0: 异配(高度节点连接低度节点)
        r ≈ 0: 无相关

        Returns:
            float | None: 相关系数，无边图返回 None。
        """
        rows = self.conn.execute(
            "SELECT source, target FROM edges"
        ).fetchall()
        if not rows:
            return None

        # 构建无向度数
        degree = {}
        for s, t in rows:
            degree[s] = degree.get(s, 0) + 1
            degree[t] = degree.get(t, 0) + 1

        M = len(rows)
        # sum(j*k), sum(j+k), sum(j^2+k^2)
        sum_jk = 0.0
        sum_jpk = 0.0
        sum_j2k2 = 0.0
        for s, t in rows:
            j = degree.get(s, 0)
            k = degree.get(t, 0)
            sum_jk += j * k
            sum_jpk += j + k
            sum_j2k2 += j * j + k * k

        # Newman's formula
        # r = (M^-1 sum(jk) - [0.5 M^-1 sum(j+k)]^2) / (0.5 M^-1 sum(j^2+k^2) - [0.5 M^-1 sum(j+k)]^2)
        numerator = sum_jk / M - (sum_jpk / (2 * M)) ** 2
        denominator = sum_j2k2 / (2 * M) - (sum_jpk / (2 * M)) ** 2

        if abs(denominator) < 1e-12:
            return 0.0
        return round(numerator / denominator, 6)

    def node_similarity(self, id_a: str, id_b: str, mode: str = "jaccard") -> float:
        """计算两个节点的结构相似度。

        基于邻居集合的重叠程度。

        Args:
            id_a, id_b: 节点ID。
            mode: "jaccard" (Jaccard系数) 或 "overlap" (重叠系数/Szymkiewicz–Simpson)。

        Returns:
            float: 0.0~1.0 的相似度，任一节点不存在返回 0.0。
        """
        if not self.has_node(id_a) or not self.has_node(id_b):
            return 0.0
        if id_a == id_b:
            return 1.0

        # Build undirected neighbor sets from edges table
        def undirected_nbrs(nid):
            rows = self.conn.execute(
                "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
                (nid, nid)
            ).fetchall()
            return {r[0] for r in rows}

        nbrs_a = undirected_nbrs(id_a)
        nbrs_b = undirected_nbrs(id_b)

        if mode == "jaccard":
            union = nbrs_a | nbrs_b
            if not union:
                return 1.0 if not nbrs_a and not nbrs_b else 0.0
            return len(nbrs_a & nbrs_b) / len(union)
        elif mode == "overlap":
            min_size = min(len(nbrs_a), len(nbrs_b))
            if min_size == 0:
                return 1.0 if not nbrs_a and not nbrs_b else 0.0
            return len(nbrs_a & nbrs_b) / min_size
        raise ValueError(f"Unknown mode: {mode}. Use 'jaccard' or 'overlap'.")

    def resistance_distance(self, id_a: str, id_b: str) -> float | None:
        """计算两节点间的电阻距离（effective resistance）。

        电阻距离基于拉普拉斯矩阵伪逆: R(i,j) = L⁺ᵢᵢ + L⁺ⱼⱼ - 2L⁺ᵢⱼ。
        低电阻距离 = 节点间有多条路径（冗余连接）。
        高电阻距离 = 节点间依赖少数路径（脆弱连接）。

        Returns:
            电阻距离，或 None（节点不存在/不连通）
        """
        node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        n = len(node_ids)
        if id_a not in node_ids or id_b not in node_ids:
            return None
        if id_a == id_b:
            return 0.0
        if n < 2:
            return None

        idx = {nid: i for i, nid in enumerate(node_ids)}
        a, b = idx[id_a], idx[id_b]

        adj_sym: dict[int, set[int]] = defaultdict(set)
        for e in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if e["source"] in idx and e["target"] in idx:
                i, j = idx[e["source"]], idx[e["target"]]
                adj_sym[i].add(j); adj_sym[j].add(i)

        # Check connectivity (BFS from a)
        visited = {a}; queue = [a]
        while queue:
            u = queue.pop(0)
            for v in adj_sym[u]:
                if v not in visited: visited.add(v); queue.append(v)
        if b not in visited:
            return float('inf')

        # Build Laplacian and compute pseudoinverse via eigenvalues
        degree = [0] * n
        for i in range(n):
            degree[i] = len(adj_sym[i])

        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            L[i][i] = float(degree[i])
            for j in adj_sym[i]:
                L[i][j] = -1.0

        # Pseudoinverse via eigenvalue decomposition
        eigenvalues = self._sym_eigenvalues(L)
        # We also need eigenvectors — use Jacobi with eigenvector tracking
        eigvecs = self._sym_eigenvectors(L)

        # L⁺ = sum over k: (1/λ_k) * v_k * v_k^T (skip λ=0)
        # R(a,b) = L⁺[a,a] + L⁺[b,b] - 2*L⁺[a,b]
        # = sum_k (1/λ_k) * (v_k[a]² + v_k[b]² - 2*v_k[a]*v_k[b])
        # = sum_k (1/λ_k) * (v_k[a] - v_k[b])²

        r = 0.0
        for k in range(n):
            if eigenvalues[k] > 1e-10:
                diff = eigvecs[k][a] - eigvecs[k][b]
                r += (diff * diff) / eigenvalues[k]

        return max(0.0, r)

    def _sym_eigenvectors(self, M: list[list[float]], max_iter: int = 300) -> list[list[float]]:
        """雅可比旋转求实对称矩阵全部特征值和特征向量。返回 eigvecs[k] = 第k个特征向量。"""
        n = len(M)
        A = [row[:] for row in M]
        V = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

        for _ in range(max_iter):
            p, q = 0, 1
            max_val = abs(A[0][1])
            for i in range(n):
                for j in range(i + 1, n):
                    if abs(A[i][j]) > max_val:
                        max_val = abs(A[i][j]); p, q = i, j
            if max_val < 1e-12:
                break
            if abs(A[p][p] - A[q][q]) < 1e-15:
                theta = math.pi / 4
            else:
                theta = 0.5 * math.atan2(2 * A[p][q], A[p][p] - A[q][q])
            c, s = math.cos(theta), math.sin(theta)

            # Rotate A
            for i in range(n):
                if i == p or i == q: continue
                aip, aiq = A[i][p], A[i][q]
                A[i][p] = c * aip + s * aiq; A[p][i] = A[i][p]
                A[i][q] = -s * aip + c * aiq; A[q][i] = A[i][q]
            app, aqq, apq = A[p][p], A[q][q], A[p][q]
            A[p][p] = c*c*app + 2*s*c*apq + s*s*aqq
            A[q][q] = s*s*app - 2*s*c*apq + c*c*aqq
            A[p][q] = 0.0; A[q][p] = 0.0

            # Rotate V (accumulate eigenvectors)
            for i in range(n):
                vip, viq = V[i][p], V[i][q]
                V[i][p] = c * vip + s * viq
                V[i][q] = -s * vip + c * viq

        # V columns are eigenvectors, A diagonal has eigenvalues
        # Return as list of column vectors
        return [[V[i][k] for i in range(n)] for k in range(n)]

    def ego_graph(self, node_id: str, order: int = 1) -> dict:
        """提取以指定节点为中心的 ego graph（自我网络）。

        返回中心节点及其 order-hop 邻域内的所有节点和边。
        ego graph 是社会网络分析的基本单元，也用于 GraphRAG local search。

        Args:
            node_id: 中心节点 ID。
            order: 邻域半径（默认 1 = 直接邻居）。

        Returns:
            {"center": node_id, "nodes": [...], "edges": [...], "radius": order}
            节点不存在返回空结果。
        """
        if not self.has_node(node_id):
            return {"center": node_id, "nodes": [], "edges": [], "radius": order}

        # BFS to collect nodes within `order` hops
        visited = {node_id}
        frontier = {node_id}
        for _ in range(order):
            next_frontier = set()
            for nid in frontier:
                rows = self.conn.execute(
                    "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
                    (nid, nid)
                ).fetchall()
                for r in rows:
                    if r[0] not in visited:
                        next_frontier.add(r[0])
            visited |= next_frontier
            frontier = next_frontier

        # Collect edges within the ego graph (both endpoints in visited)
        placeholders = ",".join("?" for _ in visited)
        params = list(visited)
        edge_rows = self.conn.execute(
            f"SELECT source, target, weight, relation FROM edges WHERE source IN ({placeholders}) AND target IN ({placeholders})",
            params + params
        ).fetchall()

        edges = [{"source": r[0], "target": r[1], "weight": r[2], "relation": r[3]} for r in edge_rows]
        return {"center": node_id, "nodes": sorted(visited), "edges": edges, "radius": order}

    def transitivity(self) -> float:
        """计算全局传递性（聚类系数）= 3 × 三角形数 / 三元组数。

        传递性衡量网络中"朋友的朋友也是朋友"的程度。
        值域 [0, 1]，0 = 无三角形，1 = 完全图。

        Returns:
            float: 传递性，孤立或无三元组返回 0.0。
        """
        node_ids = [r[0] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        if len(node_ids) < 3:
            return 0.0

        # Build undirected adjacency
        adj = {nid: set() for nid in node_ids}
        for r in self.conn.execute("SELECT source, target FROM edges").fetchall():
            if r[0] in adj and r[1] in adj:
                adj[r[0]].add(r[1])
                adj[r[1]].add(r[0])

        triangles = 0
        triples = 0
        for nid in node_ids:
            k = len(adj[nid])
            if k >= 2:
                triples += k * (k - 1) // 2
                # Count triangles including nid
                nbrs = list(adj[nid])
                for i in range(len(nbrs)):
                    for j in range(i + 1, len(nbrs)):
                        if nbrs[j] in adj[nbrs[i]]:
                            triangles += 1

        if triples == 0:
            return 0.0
        # Each triangle counted 3 times (once per vertex)
        return triangles / triples  # Already normalized: 3*triangles/3 / triples

    def preferential_attachment(self, id_a: str, id_b: str) -> int | None:
        """计算两节点间的优先链接分数 = deg(A) × deg(B)。

        用于链路预测：度数高的节点对更可能连接。
        是 Adamic/Adar 和 Jaccard 的简化替代。

        Args:
            id_a, id_b: 节点 ID。

        Returns:
            int: 度数乘积，节点不存在返回 None。
        """
        if not self.has_node(id_a) or not self.has_node(id_b):
            return None

        deg_a = self.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source=? OR target=?",
            (id_a, id_a)
        ).fetchone()[0]
        deg_b = self.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source=? OR target=?",
            (id_b, id_b)
        ).fetchone()[0]
        return deg_a * deg_b

    # ── LLM 上下文导出 ────────────────────────────────────

    def to_markdown(self, node_ids: list[str] | None = None, max_nodes: int = 50,
                    include_edges: bool = True, include_data: bool = True) -> str:
        """将图谱导出为 Markdown 文本，适合注入 LLM 上下文。

        Args:
            node_ids: 仅导出指定节点（None=全部，按 weight 降序取 max_nodes）
            max_nodes: 最大节点数（防止 token 爆炸）
            include_edges: 是否包含关系列表
            include_data: 是否包含节点 data 字段

        Returns:
            Markdown 字符串，结构为：标题 + 节点列表 + 关系列表
        """
        if node_ids is not None:
            node_ids = set(node_ids)
            rows = self.conn.execute(
                "SELECT * FROM nodes WHERE id IN (%s) ORDER BY weight DESC LIMIT ?"
                % ",".join("?" * len(node_ids)),
                (*node_ids, max_nodes)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM nodes ORDER BY weight DESC LIMIT ?", (max_nodes,)
            ).fetchall()

        if not rows:
            return "# Memory Graph\n\n(empty)\n"

        lines = ["# Memory Graph", ""]
        id_set = {r["id"] for r in rows}

        # 按_kind 分组
        by_kind: dict[str, list] = defaultdict(list)
        for r in rows:
            by_kind[r["kind"]].append(r)

        for kind in sorted(by_kind):
            lines.append(f"## {kind} ({len(by_kind[kind])})")
            for r in by_kind[kind]:
                tags = json.loads(r["tags"]) if r["tags"] else []
                tag_str = f" `{'` `'.join(tags)}`" if tags else ""
                data_str = ""
                if include_data and r["data"] and r["data"] != "{}":
                    try:
                        d = json.loads(r["data"])
                        if d:
                            items = ", ".join(f"{k}={v!r}" for k, v in d.items())
                            data_str = f" — {items}"
                    except (json.JSONDecodeError, TypeError):
                        pass
                weight_str = f" (w={r['weight']:.2f})" if r["weight"] != 1.0 else ""
                lines.append(f"- **{r['label']}**{weight_str}{tag_str}{data_str}")
            lines.append("")

        if include_edges:
            edge_rows = self.conn.execute(
                "SELECT * FROM edges WHERE source IN (%s) OR target IN (%s) ORDER BY weight DESC"
                % (",".join("?" * len(id_set)), ",".join("?" * len(id_set))),
                (*id_set, *id_set)
            ).fetchall()
            if edge_rows:
                label_map = {r["id"]: r["label"] for r in rows}
                lines.append("## Relationships")
                shown = 0
                for e in edge_rows:
                    if shown >= max_nodes * 2:
                        break
                    src = label_map.get(e["source"], e["source"])
                    tgt = label_map.get(e["target"], e["target"])
                    w = f" (w={e['weight']:.2f})" if e["weight"] != 1.0 else ""
                    lines.append(f"- {src} —{e['relation']}→ {tgt}{w}")
                    shown += 1
                lines.append("")

        return "\n".join(lines)

    def context_window(self, node_ids: list[str], hops: int = 1, max_nodes: int = 30) -> str:
        """提取以指定节点为中心的局部子图，输出为 Markdown 上下文。

        比 to_markdown() 更聚焦：先 BFS 扩展 hops 跳邻居，再格式化。
        适合把「最相关的记忆」注入 prompt。

        Args:
            node_ids: 种子节点列表
            hops: BFS 扩展跳数（默认1跳=直接邻居）
            max_nodes: 最大节点数

        Returns:
            Markdown 字符串，种子节点标 ★
        """
        seed = set(node_ids)
        collected = dict()  # id → Row

        # 加载种子节点
        for nid in node_ids:
            r = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (nid,)).fetchone()
            if r:
                collected[nid] = r

        # BFS 扩展
        frontier = list(node_ids)
        for _ in range(hops):
            next_frontier = []
            for nid in frontier:
                for r in self.conn.execute(
                    "SELECT n.* FROM nodes n JOIN edges e ON n.id=e.target WHERE e.source = ?",
                    (nid,)
                ).fetchall():
                    if r["id"] not in collected and len(collected) < max_nodes:
                        collected[r["id"]] = r
                        next_frontier.append(r["id"])
                for r in self.conn.execute(
                    "SELECT n.* FROM nodes n JOIN edges e ON n.id=e.source WHERE e.target = ?",
                    (nid,)
                ).fetchall():
                    if r["id"] not in collected and len(collected) < max_nodes:
                        collected[r["id"]] = r
                        next_frontier.append(r["id"])
            frontier = next_frontier

        if not collected:
            return "# Context Window\n\n(no data)\n"

        lines = ["# Context Window", ""]

        # 按 kind 分组
        by_kind: dict[str, list] = defaultdict(list)
        for r in collected.values():
            by_kind[r["kind"]].append(r)

        for kind in sorted(by_kind):
            lines.append(f"## {kind}")
            for r in by_kind[kind]:
                marker = " ★" if r["id"] in seed else ""
                tags = json.loads(r["tags"]) if r["tags"] else []
                tag_str = f" `{'` `'.join(tags)}`" if tags else ""
                data_str = ""
                if r["data"] and r["data"] != "{}":
                    try:
                        d = json.loads(r["data"])
                        if d:
                            items = ", ".join(f"{k}={v!r}" for k, v in d.items())
                            data_str = f" — {items}"
                    except (json.JSONDecodeError, TypeError):
                        pass
                lines.append(f"- **{r['label']}**{marker}{tag_str}{data_str}")
            lines.append("")

        # 收集相关边
        id_set = set(collected.keys())
        edge_rows = self.conn.execute(
            "SELECT * FROM edges WHERE source IN (%s) OR target IN (%s) ORDER BY weight DESC"
            % (",".join("?" * len(id_set)), ",".join("?" * len(id_set))),
            (*id_set, *id_set)
        ).fetchall()
        if edge_rows:
            label_map = {nid: collected[nid]["label"] for nid in id_set}
            lines.append("## Relationships")
            for e in edge_rows[:max_nodes * 2]:
                src = label_map.get(e["source"], e["source"])
                tgt = label_map.get(e["target"], e["target"])
                lines.append(f"- {src} —{e['relation']}→ {tgt}")
            lines.append("")

        return "\n".join(lines)



    def resource_allocation_index(self, id_a: str, id_b: str) -> float | None:
        """计算两节点间的资源分配指数（链路预测）。
        RA(i,j) = Σ 1/|Γ(z)| for z ∈ Γ(i) ∩ Γ(j)
        共同邻居的度数越小权重越高（稀有共同邻居更有价值）。
        比 Adamic/Adar 更惩罚高度共同邻居。
        Args:
            id_a, id_b: 节点 ID。
        Returns:
            float: RA 分数，≥ 0。节点不存在返回 None。
        """
        if not self.has_node(id_a) or not self.has_node(id_b):
            return None
        def undirected_nbrs(nid):
            rows = self.conn.execute(
                "SELECT target FROM edges WHERE source=? UNION SELECT source FROM edges WHERE target=?",
                (nid, nid)
            ).fetchall()
            return {r[0] for r in rows}
        nbrs_a = undirected_nbrs(id_a)
        nbrs_b = undirected_nbrs(id_b)
        common = nbrs_a & nbrs_b
        if not common:
            return 0.0
        score = 0.0
        for z in common:
            deg_z = self.conn.execute(
                "SELECT COUNT(*) FROM edges WHERE source=? OR target=?",
                (z, z)
            ).fetchone()[0]
            if deg_z > 0:
                score += 1.0 / deg_z
        return score
    def degree_prestige(self, node_id: str) -> float | None:
        """计算节点的度声望 = 入度 / (n-1)。
        有向图中被多少比例的节点指向，衡量"知名度"。
        无向图中退化为归一化度数。
        Args:
            node_id: 节点 ID。
        Returns:
            float: [0, 1] 归一化声望，节点不存在返回 None。
        """
        if not self.has_node(node_id):
            return None
        n = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        if n <= 1:
            return 0.0
        in_deg = self.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE target=?",
            (node_id,)
        ).fetchone()[0]
        return in_deg / (n - 1)
    def core_ratio(self, k: int) -> float:
        """计算 k-core 占总节点的比例。
        衡量图的核密度：高比例意味着大部分节点高度互联。
        依赖 core_number() 的结果。
        Args:
            k: core 阶数。
        Returns:
            float: [0, 1] 比例，空图返回 0.0。
        """
        n = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        if n == 0:
            return 0.0
        cores = self.core_number()
        in_core = sum(1 for v in cores.values() if v >= k)
        return in_core / n

    # ── 演示 ──────────────────────────────────────────────────



    def density(self) -> float:
        """计算图的密度：实际边数 / 最大可能边数。

        density = m / (n*(n-1))  for directed
        density = 2m / (n*(n-1))  for undirected (standard analysis)

        完全图密度=1.0，空图=0.0。使用无向语义（与图分析惯例一致）。
        """
        n = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        if n < 2:
            return 0.0
        m = self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        return (2.0 * m) / (n * (n - 1))

    def local_clustering(self, node_id: str) -> float | None:
        """计算节点的局部聚类系数。

        C(v) = 2 * E(neighbors) / (deg(v) * (deg(v) - 1))

        衡量该节点的邻居之间互连的程度。值域 [0, 1]。
        节点不存在或度数 < 2 时返回 None（无法计算）。
        """
        if not self.has_node(node_id):
            return None
        # Get neighbors (undirected)
        nbrs = set()
        for r in self.conn.execute(
            "SELECT target AS nb FROM edges WHERE source=? "
            "UNION "
            "SELECT source AS nb FROM edges WHERE target=?",
            (node_id, node_id)
        ).fetchall():
            nbrs.add(str(r["nb"]))
        k = len(nbrs)
        if k < 2:
            return None
        # Count edges among neighbors
        nbr_list = list(nbrs)
        edges_among = 0
        for i in range(len(nbr_list)):
            for j in range(i + 1, len(nbr_list)):
                cnt = self.conn.execute(
                    "SELECT COUNT(*) FROM edges WHERE "
                    "(source=? AND target=?) OR (source=? AND target=?)",
                    (nbr_list[i], nbr_list[j], nbr_list[j], nbr_list[i])
                ).fetchone()[0]
                if cnt > 0:
                    edges_among += 1
        return (2.0 * edges_among) / (k * (k - 1))

    def efficiency(self, id_a: str, id_b: str) -> float:
        """计算两节点之间的效率：1 / 最短路径长度。

        效率越高表示两节点通信越高效。不可达时返回 0.0。
        """
        if not self.has_node(id_a) or not self.has_node(id_b):
            return 0.0
        if id_a == id_b:
            return 1.0
        path = self.shortest_path(id_a, id_b)
        if path is None:
            return 0.0
        return 1.0 / len(path)

    def assortativity_degree(self) -> float:
        """计算度同配系数 (Newman assortativity coefficient)。

        衡量图中节点是否倾向于连接度数相似的节点。
        r > 0: 同配网络（高连高、低连低）
        r < 0: 异配网络（高连低）
        r ≈ 0: 无明显相关性
        值域 [-1, 1]。
        """
        rows = self.conn.execute(
            "SELECT source, target FROM edges"
        ).fetchall()
        m = len(rows)
        if m < 2:
            return 0.0
        # Build undirected degree map
        deg: dict[str, int] = {}
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            deg[s] = deg.get(s, 0) + 1
            deg[t] = deg.get(t, 0) + 1
        # Newman's formula: each edge contributes two terms (j,k) and (k,j)
        # M = 2 * num_edges (standard undirected normalization)
        two_m = 2 * m
        sum_jk = 0.0
        sum_j = 0.0
        sum_k = 0.0
        sum_j2 = 0.0
        sum_k2 = 0.0
        for r in rows:
            j = deg[str(r["source"])]
            k = deg[str(r["target"])]
            # Both (j,k) and (k,j)
            sum_jk += j * k + k * j
            sum_j += j + k
            sum_k += k + j
            sum_j2 += j * j + k * k
            sum_k2 += k * k + j * j
        numerator = (sum_jk / two_m) - ((sum_j / two_m) * (sum_k / two_m))
        denominator = (
            (sum_j2 + sum_k2) / (2 * two_m)
            - ((sum_j + sum_k) / (2 * two_m)) ** 2
        )
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def degree_distribution(self) -> dict[int, float]:
        """计算度分布：每个度值对应的节点比例。

        返回 {degree: fraction} 字典。关键用途：
        - 判断是否为 scale-free 网络（幂律分布）
        - 识别 hub 节点（高度数）
        - 对比随机图与真实图的度分布差异
        """
        rows = self.conn.execute(
            "SELECT source, target FROM edges"
        ).fetchall()
        deg: dict[str, int] = {}
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            deg[s] = deg.get(s, 0) + 1
            deg[t] = deg.get(t, 0) + 1
        total_nodes = self.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        if total_nodes == 0:
            return {}
        # Count nodes at each degree (including degree-0 nodes)
        degree_counts: dict[int, int] = {}
        node_ids = {str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()}
        for nid in node_ids:
            d = deg.get(nid, 0)
            degree_counts[d] = degree_counts.get(d, 0) + 1
        return {d: round(c / total_nodes, 4) for d, c in sorted(degree_counts.items())}

    def network_summary(self) -> dict:
        """一站式网络分析摘要：密度、聚类、度分布、连通性等。

        聚合已有的分析 API 为单次调用，适合 dashboard 或快速诊断。
        """
        n = self.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        m = self.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        if n == 0:
            return {"nodes": 0, "edges": 0, "density": 0.0}

        # Average degree
        rows = self.conn.execute("SELECT source, target FROM edges").fetchall()
        deg: dict[str, int] = {}
        for r in rows:
            s, t = str(r["source"]), str(r["target"])
            deg[s] = deg.get(s, 0) + 1
            deg[t] = deg.get(t, 0) + 1
        avg_degree = (2.0 * m / n) if n > 0 else 0.0
        max_degree = max(deg.values()) if deg else 0

        # Density
        density = (2.0 * m) / (n * (n - 1)) if n > 1 else 0.0

        # Global clustering coefficient (transitivity)
        try:
            transitivity = self.transitivity()
        except Exception:
            transitivity = 0.0

        # Connected components
        try:
            components = self.find_components()
            num_components = len(components)
            largest_cc = max((len(c) for c in components), default=0)
        except Exception:
            num_components = 0
            largest_cc = 0

        # Reciprocity (directed)
        try:
            recip = self.reciprocity()
        except Exception:
            recip = 0.0

        return {
            "nodes": n,
            "edges": m,
            "density": round(density, 4),
            "avg_degree": round(avg_degree, 2),
            "max_degree": max_degree,
            "transitivity": round(transitivity, 4),
            "reciprocity": round(recip, 4),
            "components": num_components,
            "largest_component_size": largest_cc,
            "largest_component_ratio": round(largest_cc / n, 4) if n > 0 else 0.0,
        }

    def k_hop_neighbors(self, node_id: str, k: int = 2) -> dict[int, list[str]]:
        """获取节点 k 跳范围内的所有邻居。

        BFS 层次遍历，返回 {hop: [node_ids]} 字典。
        hop=0 为节点自身，hop=1 为直接邻居，hop=2 为二跳邻居，以此类推。
        已访问的节点不会重复出现。
        """
        if not self.has_node(node_id):
            return {}
        visited = {node_id}
        result = {0: [node_id]}
        frontier = [node_id]
        for hop in range(1, k + 1):
            next_frontier = []
            for cur in frontier:
                for r in self.conn.execute(
                    "SELECT target AS nb FROM edges WHERE source=? "
                    "UNION "
                    "SELECT source AS nb FROM edges WHERE target=?",
                    (cur, cur)
                ).fetchall():
                    nb = str(r["nb"])
                    if nb not in visited:
                        visited.add(nb)
                        next_frontier.append(nb)
            if next_frontier:
                result[hop] = sorted(next_frontier)
                frontier = next_frontier
            else:
                break
        return result

    def common_neighbors(self, node_id_a: str, node_id_b: str) -> list[str]:
        """返回两个节点的共同邻居（交集）。

        使用集合交集，复杂度 O(min(deg_a, deg_b))。
        对于链接预测、推荐系统和图分析有用。
        """
        if not self.has_node(node_id_a) or not self.has_node(node_id_b):
            return []
        nbrs_a = set()
        for r in self.conn.execute(
            "SELECT target AS nb FROM edges WHERE source=? "
            "UNION "
            "SELECT source AS nb FROM edges WHERE target=?",
            (node_id_a, node_id_a)
        ).fetchall():
            nbrs_a.add(str(r["nb"]))
        nbrs_b = set()
        for r in self.conn.execute(
            "SELECT target AS nb FROM edges WHERE source=? "
            "UNION "
            "SELECT source AS nb FROM edges WHERE target=?",
            (node_id_b, node_id_b)
        ).fetchall():
            nbrs_b.add(str(r["nb"]))
        return sorted(nbrs_a & nbrs_b)

    def graph_entropy(self) -> dict[str, float]:
        """Shannon entropy of the degree distribution.

        H = -sum(p_k * log2(p_k)) where p_k = fraction of nodes with degree k.
        Low entropy = uniform structure (e.g. regular graph).
        High entropy = heterogeneous (e.g. scale-free).
        Also returns normalized entropy (H / H_max) for cross-graph comparison.
        """
        n = self.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        if n == 0:
            return {"entropy": 0.0, "normalized": 0.0, "max_entropy": 0.0}

        dist = self.degree_distribution()
        total = sum(dist.values())
        if total == 0:
            return {"entropy": 0.0, "normalized": 0.0, "max_entropy": 0.0}

        h = 0.0
        for deg, frac in dist.items():
            p = frac / total
            if p > 0:
                h -= p * math.log2(p)

        h_max = math.log2(len(dist)) if len(dist) > 1 else 1.0
        return {
            "entropy": round(h, 4),
            "max_entropy": round(h_max, 4),
            "normalized": round(h / h_max, 4) if h_max > 0 else 0.0,
        }

    def connectivity_frontier(self, node_id: str, max_hop: int = 3) -> dict[int, int]:
        """BFS hop-distance census from a seed node.

        Returns {hop: count} — how many nodes are reachable at each distance.
        Useful for influence radius estimation and BFS-based exploration.
        """
        if not self.has_node(node_id):
            return {}

        visited = {node_id: 0}
        frontier = [node_id]
        for hop in range(1, max_hop + 1):
            next_frontier = []
            for nid in frontier:
                for r in self.conn.execute(
                    "SELECT target AS nb FROM edges WHERE source=? "
                    "UNION "
                    "SELECT source AS nb FROM edges WHERE target=?",
                    (nid, nid)
                ).fetchall():
                    nb = str(r["nb"])
                    if nb not in visited:
                        visited[nb] = hop
                        next_frontier.append(nb)
            frontier = next_frontier
            if not frontier:
                break

        census: dict[int, int] = {}
        for _, hop in visited.items():
            census[hop] = census.get(hop, 0) + 1
        return census

    def degree_centrality_normalized(self) -> dict[str, float]:
        """Normalized degree centrality: degree / (n-1).

        Freeman's classic centrality measure, normalized to [0, 1].
        A hub in a star graph scores 1.0, peripheral nodes score 1/(n-1).
        """
        n = self.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        if n <= 1:
            rows = self.conn.execute("SELECT id FROM nodes").fetchall()
            return {str(r["id"]): 0.0 for r in rows}

        rows = self.conn.execute(
            "SELECT id FROM nodes"
        ).fetchall()
        result = {}
        denom = n - 1
        for r in rows:
            nid = str(r["id"])
            deg = self.conn.execute(
                "SELECT COUNT(*) c FROM edges WHERE source=? OR target=?",
                (nid, nid)
            ).fetchone()["c"]
            result[nid] = round(deg / denom, 4)
        return result

    def edge_density_subgraph(self, node_ids: list[str]) -> float:
        """Edge density of an induced subgraph.

        Density = actual_edges / possible_edges (n*(n-1)/2 for undirected).
        Useful for evaluating community tightness or cluster cohesion.
        """
        n = len(node_ids)
        if n < 2:
            return 0.0
        node_set = set(node_ids)
        placeholders = ",".join("?" * n)
        actual = self.conn.execute(
            f"SELECT COUNT(*) c FROM edges WHERE source IN ({placeholders}) AND target IN ({placeholders})",
            (*node_ids, *node_ids)
        ).fetchone()["c"]
        possible = n * (n - 1) / 2
        return round(actual / possible, 4) if possible > 0 else 0.0


    # ===================================================================
    # Learnable Memory Management (Memory-R1 / AgeMem inspired)
    # ===================================================================

    @staticmethod
    def _content_similarity(text_a: str, text_b: str) -> float:
        """简易内容相似度: trigram Jaccard 系数。"""
        def trigrams(s: str) -> set:
            s = s.lower().strip()
            return {s[i:i+3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}
        a, b = trigrams(text_a), trigrams(text_b)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def score_memory_ops(self, content: str, existing_keys: list[str] = None,
                         noop_bias: float = 0.15) -> list[dict]:
        """对新信息评分 4 种操作 (ADD/UPDATE/DELETE/NOOP), Memory-R1 启发。"""
        existing_keys = existing_keys or []
        scores = []

        best_match = None
        best_sim = 0.0
        if existing_keys:
            for kid in existing_keys:
                node = self.get_node(kid)
                if node:
                    sim = self._content_similarity(content, node.label)
                    if sim > best_sim:
                        best_sim = sim
                        best_match = kid
        else:
            results = self.search_unified(content, limit=5)
            for r in results:
                sim = self._content_similarity(content, r["node"].label)
                if sim > best_sim:
                    best_sim = sim
                    best_match = r["node"].id

        novelty = 1.0 - best_sim
        add_score = novelty * (1.0 - noop_bias)
        scores.append({
            "op": "ADD",
            "score": round(add_score, 4),
            "reason": f"novelty={novelty:.2f}" + (f", best_match_sim={best_sim:.2f}" if best_match else ", no match"),
        })

        if best_match and best_sim > 0.3:
            update_score = best_sim * (1.0 - noop_bias)
            scores.append({
                "op": "UPDATE",
                "score": round(update_score, 4),
                "reason": f"similarity={best_sim:.2f} to existing node",
                "target_key": best_match,
            })
        else:
            scores.append({"op": "UPDATE", "score": 0.0,
                           "reason": "no similar existing entry"})

        scores.append({"op": "DELETE", "score": 0.0,
                       "reason": "DELETE only for contradictions/staleness (manual)"})

        noop_score = noop_bias + (best_sim * 0.3)
        scores.append({
            "op": "NOOP",
            "score": round(min(noop_score, 1.0), 4),
            "reason": "conservative default" + (f", high overlap={best_sim:.2f}" if best_sim > 0.5 else ""),
        })

        return sorted(scores, key=lambda x: x["score"], reverse=True)

    def decide_memory_op(self, content: str, threshold: float = 0.5,
                         noop_bias: float = 0.15) -> dict:
        """决策: 对新信息选择最优记忆操作。"""
        scores = self.score_memory_ops(content, noop_bias=noop_bias)
        best = scores[0]
        if best["op"] == "ADD" and best["score"] < threshold:
            return {"op": "NOOP", "score": best["score"],
                    "reason": f"ADD score {best['score']:.2f} < threshold {threshold}"}
        return best

    def execute_memory_op(self, content: str, kind: str = "fact",
                          threshold: float = 0.5, noop_bias: float = 0.15,
                          tags: list[str] = None) -> dict:
        """端到端: 决策 + 执行记忆操作。"""
        decision = self.decide_memory_op(content, threshold=threshold, noop_bias=noop_bias)
        op = decision["op"]

        if op == "ADD":
            node = self.add(content, kind)
            if tags:
                for t in tags:
                    self.tag_nodes(t, [node.id])
            return {"op": "ADD", "result": "created",
                    "detail": {"node_id": node.id, "label": content[:80]}}

        if op == "UPDATE" and decision.get("target_key"):
            kid = decision["target_key"]
            node = self.get_node(kid)
            if node:
                new_label = f"{node.label} + {content[:50]}"
                self.update_node(kid, label=new_label)
                return {"op": "UPDATE", "result": "merged",
                        "detail": {"node_id": kid, "old": node.label, "new": new_label}}

        if op == "DELETE":
            return {"op": "DELETE", "result": "skipped",
                    "detail": "DELETE requires explicit confirmation"}

        return {"op": "NOOP", "result": "no_action",
                "detail": decision["reason"]}

    def memory_decision_log(self, items: list[str], threshold: float = 0.5) -> list[dict]:
        """批量决策日志: 对多条信息生成操作建议 (不执行)。"""
        log = []
        for item in items:
            d = self.decide_memory_op(item, threshold=threshold)
            log.append({"content": item[:60], **d})
        return log

    def memory_audit(self, max_nodes: int = 500, staleness_days: int = 30) -> dict:
        """全局记忆审计: 健康评分 + 冗余分析 + 过期检测。

        MemoryArena (ICLR 2026) 启发的评估维度。

        Returns:
            {health_score, total_nodes, redundant_pairs, stale_nodes,
             avg_importance, noop_ratio, suggestions}
        """
        import time
        stats = self.stats()
        total = stats.get("nodes", 0)
        if total == 0:
            return {"health_score": 100, "total_nodes": 0, "redundant_pairs": 0,
                    "stale_nodes": 0, "avg_importance": 0, "noop_ratio": 0,
                    "suggestions": ["Empty graph"]}

        # 过期节点 (staleness)
        now = time.time()
        stale_cutoff = now - staleness_days * 86400
        stale_nodes = self.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE accessed < ?", (stale_cutoff,)
        ).fetchone()["c"]

        # 平均重要性 (weight)
        avg_w = self.conn.execute(
            "SELECT AVG(weight) as w FROM nodes"
        ).fetchone()["w"] or 0.0

        # 冗余分析: 对每对同 kind 的节点计算相似度
        all_nodes = self.conn.execute(
            "SELECT id, label, kind FROM nodes ORDER BY kind LIMIT ?", (max_nodes,)
        ).fetchall()
        redundant_count = 0
        by_kind: dict[str, list] = defaultdict(list)
        for row in all_nodes:
            by_kind[row["kind"]].append(row)
        for kind, nodes in by_kind.items():
            for i in range(len(nodes)):
                for j in range(i + 1, min(i + 20, len(nodes))):
                    sim = self._content_similarity(nodes[i]["label"], nodes[j]["label"])
                    if sim > 0.6:
                        redundant_count += 1

        # NOOP ratio (通过最近操作统计)
        noop_ratio = stale_nodes / total if total > 0 else 0

        # 健康评分 (0-100)
        health = 100
        if total > max_nodes:
            health -= min(20, (total - max_nodes) / max_nodes * 20)
        health -= min(15, stale_nodes / max(total, 1) * 30)
        health -= min(15, redundant_count / max(total, 1) * 30)
        health -= min(10, max(0, (0.3 - avg_w) / 0.3 * 10)) if avg_w < 0.3 else 0
        health = max(0, int(health))

        suggestions = []
        if stale_nodes > total * 0.3:
            suggestions.append(f"High staleness: {stale_nodes} nodes untouched in {staleness_days}d. Consider prune().")
        if redundant_count > total * 0.1:
            suggestions.append(f"{redundant_count} redundant pairs detected. Consider dedup_nodes().")
        if avg_w < 0.3:
            suggestions.append("Low average weight. Consider importance_rank() review.")
        if total > max_nodes:
            suggestions.append(f"Graph exceeds {max_nodes} nodes. Consider prune_by_relevance().")
        if not suggestions:
            suggestions.append("Graph is healthy.")

        return {
            "health_score": health,
            "total_nodes": total,
            "redundant_pairs": redundant_count,
            "stale_nodes": stale_nodes,
            "avg_importance": round(avg_w, 3),
            "noop_ratio": round(noop_ratio, 3),
            "suggestions": suggestions,
        }

    def fifa_forget(self, budget: int = 50, min_importance: float = 0.1) -> dict:
        """FiFA (Find-and-Forget): 有界遗忘策略。

        删除 budget 个最低重要性 + 最陈旧的节点, 保留高价值记忆。
        MemoryArena 启发: selective forgetting 是核心能力。

        Returns:
            {removed, kept, details}
        """
        import time
        all_nodes = self.conn.execute(
            "SELECT id, label, kind, weight, accessed FROM nodes ORDER BY weight ASC, accessed ASC LIMIT ?",
            (budget,)
        ).fetchall()

        removed = []
        for row in all_nodes:
            if row["weight"] < min_importance:
                self.delete_node(row["id"])
                removed.append({"id": row["id"], "label": row["label"],
                               "weight": row["weight"]})

        remaining = self.stats().get("nodes", 0)
        return {
            "removed": len(removed),
            "kept": remaining,
            "details": removed[:10],  # 前10个详情
        }

    def memory_compact(self, similarity_threshold: float = 0.7,
                       max_merge_per_pass: int = 20) -> dict:
        """记忆压缩: 合并高相似度节点, 减少冗余。

        Returns:
            {merged_count, freed_edges, details}
        """
        all_nodes = self.conn.execute(
            "SELECT id, label, kind FROM nodes ORDER BY kind"
        ).fetchall()

        merged = 0
        details = []
        by_kind: dict[str, list] = defaultdict(list)
        for row in all_nodes:
            by_kind[row["kind"]].append(dict(row))

        for kind, nodes in by_kind.items():
            skip = set()
            for i in range(min(len(nodes), max_merge_per_pass)):
                if i in skip or merged >= max_merge_per_pass:
                    break
                for j in range(i + 1, len(nodes)):
                    if j in skip or merged >= max_merge_per_pass:
                        break
                    sim = self._content_similarity(nodes[i]["label"], nodes[j]["label"])
                    if sim >= similarity_threshold:
                        # Merge j into i
                        self.merge_nodes(nodes[j]["id"], nodes[i]["id"])
                        skip.add(j)
                        merged += 1
                        details.append({
                            "merged": nodes[j]["label"][:30],
                            "into": nodes[i]["label"][:30],
                            "similarity": round(sim, 3),
                        })

        return {"merged_count": merged, "details": details}

    def memory_feedback(self, corrections: list[dict]) -> dict:
        """从反馈数据学习调整阈值 (AgeMem 在线学习启发)。

        corrections: [{content, correct_op, chosen_op, was_correct}]

        Returns:
            {adjusted_threshold, adjustments, samples}
        """
        if not corrections:
            return {"adjusted_threshold": 0.5, "adjustments": 0, "samples": 0}

        # 统计误判模式
        false_adds = sum(1 for c in corrections
                         if c.get("chosen_op") == "ADD"
                         and not c.get("was_correct", True))
        missed_adds = sum(1 for c in corrections
                          if c.get("correct_op") == "ADD"
                          and c.get("chosen_op") != "ADD")

        total = len(corrections)
        # 如果 ADD 误判多 → 提高阈值
        # 如果 ADD 遗漏多 → 降低阈值
        delta = (false_adds - missed_adds) / total * 0.2  # 最大调整 0.2
        new_threshold = max(0.1, min(0.9, 0.5 + delta))

        return {
            "adjusted_threshold": round(new_threshold, 3),
            "adjustments": delta != 0,
            "samples": total,
            "false_adds": false_adds,
            "missed_adds": missed_adds,
        }

    def memory_stats_summary(self) -> dict:
        """记忆概览仪表盘: 类型分布 + 权重分布 + 时间跨度。

        Returns:
            {total, by_kind, weight_dist, time_span, top_weighted}
        """
        import time
        stats = self.stats()
        total = stats.get("nodes", 0)

        if total == 0:
            return {"total": 0, "by_kind": {}, "weight_dist": {},
                    "time_span": 0, "top_weighted": []}

        # 类型分布
        by_kind = self.count_by_kind()

        # 权重分布
        rows = self.conn.execute(
            "SELECT weight FROM nodes ORDER BY weight DESC"
        ).fetchall()
        weights = [r["weight"] for r in rows]
        weight_dist = {
            "high": sum(1 for w in weights if w >= 0.7),
            "medium": sum(1 for w in weights if 0.3 <= w < 0.7),
            "low": sum(1 for w in weights if w < 0.3),
            "avg": round(sum(weights) / len(weights), 3),
        }

        # 时间跨度
        times = self.conn.execute(
            "SELECT MIN(created) as min_t, MAX(created) as max_t FROM nodes"
        ).fetchone()
        time_span = (times["max_t"] - times["min_t"]) if times["min_t"] else 0

        # Top weighted
        top_rows = self.conn.execute(
            "SELECT id, label, kind, weight FROM nodes ORDER BY weight DESC LIMIT 5"
        ).fetchall()
        top_weighted = [{"id": r["id"], "label": r["label"],
                         "kind": r["kind"], "weight": r["weight"]}
                        for r in top_rows]

        return {
            "total": total,
            "by_kind": dict(by_kind),
            "weight_dist": weight_dist,
            "time_span_days": round(time_span / 86400, 1),
            "top_weighted": top_weighted,
        }

    # ── memorywire 互操作 ──────────────────────────────────
    # memorywire v0.1 wire format: 5 ops × 4 types
    # Ops: remember, recall, forget, merge, expire
    # Types: semantic, episodic, procedural, emotional
    # See: https://arxiv.org/abs/2606.01138

    # Map internal kinds ↔ memorywire types
    _MW_TYPE_MAP = {
        "fact": "semantic",
        "concept": "semantic",
        "event": "episodic",
        "person": "episodic",
        "skill": "procedural",
        "emotion": "emotional",
    }
    _MW_TYPE_REVERSE = {
        "semantic": "fact",
        "episodic": "event",
        "procedural": "skill",
        "emotional": "emotion",
    }

    def to_memorywire(self, agent_id: str = "default",
                      node_ids: list[str] | None = None) -> dict:
        """Export graph memories to memorywire v0.1 wire format.

        Produces a JSON-serializable dict of 'remember' operations that
        can be replayed into any memorywire-compatible backend.

        Args:
            agent_id: Agent identifier for the exported memories.
            node_ids: Optional list of specific nodes to export.
                      If None, exports all nodes.

        Returns:
            {"version": "0.1", "agent_id": ..., "memories": [...]}
        """
        if node_ids is None:
            rows = self.conn.execute("SELECT * FROM nodes").fetchall()
        else:
            placeholders = ",".join("?" * len(node_ids))
            rows = self.conn.execute(
                f"SELECT * FROM nodes WHERE id IN ({placeholders})", node_ids
            ).fetchall()

        # Also export edges as relationship metadata
        edge_map: dict[str, list[dict]] = {}
        for r in rows:
            linked = self.conn.execute(
                "SELECT target, relation, weight FROM edges WHERE source=?",
                (r["id"],)
            ).fetchall()
            if linked:
                edge_map[r["id"]] = [
                    {"target": l["target"], "relation": l["relation"],
                     "weight": l["weight"]}
                    for l in linked
                ]

        memories = []
        for r in rows:
            tags = json.loads(r["tags"])
            mw_type = self._MW_TYPE_MAP.get(r["kind"], "semantic")
            entry = {
                "operation": "remember",
                "agent_id": agent_id,
                "type": mw_type,
                "content": r["label"],
                "confidence": round(r["weight"], 4),
                "source": tags[0] if tags else None,
                "metadata": {
                    "node_id": r["id"],
                    "kind": r["kind"],
                    "data": json.loads(r["data"]),
                    "tags": tags,
                    "created": r["created"],
                    "accessed": r["accessed"],
                },
                "expires_at": None,
                "approval_required": False,
            }
            if r["id"] in edge_map:
                entry["metadata"]["relationships"] = edge_map[r["id"]]
            memories.append(entry)

        return {"version": "0.1", "agent_id": agent_id, "memories": memories}

    def from_memorywire(self, wire_data: dict) -> int:
        """Import memorywire v0.1 wire format into this graph.

        Accepts the output of to_memorywire() or any memorywire-compatible
        'remember' operation list. Creates nodes and edges accordingly.

        Args:
            wire_data: Dict with 'memories' key containing a list of
                       remember operation dicts.

        Returns:
            Number of nodes imported.
        """
        memories = wire_data.get("memories", [])
        count = 0
        for mem in memories:
            if mem.get("operation") != "remember":
                continue

            mw_type = mem.get("type", "semantic")
            kind = self._MW_TYPE_REVERSE.get(mw_type, "fact")
            content = mem.get("content", "")
            meta = mem.get("metadata", {})

            # Preserve original node_id if present
            node_id = meta.get("node_id") or uuid.uuid4().hex[:12]
            tags = meta.get("tags", [])
            if mem.get("source") and mem["source"] not in tags:
                tags.insert(0, mem["source"])

            now = time.time()
            self.conn.execute(
                "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
                (node_id, content, kind,
                 json.dumps(meta.get("data", {})),
                 meta.get("created", now), meta.get("accessed", now),
                 mem.get("confidence", 1.0), json.dumps(tags))
            )
            self._fts_sync_node(node_id)

            # Restore edges if present
            for rel in meta.get("relationships", []):
                self.conn.execute(
                    "INSERT OR IGNORE INTO edges VALUES (?,?,?,?)",
                    (node_id, rel["target"], rel["relation"],
                     rel.get("weight", 1.0))
                )
            count += 1

        self.conn.commit()
        return count

    # ===================================================================
    # CRDT-based Multi-Agent Merge (06-16 research: LWW / OR-Set / Trust-weighted)
    # ===================================================================

    def merge_crdt(self, other_graph_data: dict, strategy: str = "lww",
                   trust_weight: float = 0.5) -> dict:
        """Merge another graph's data using CRDT-inspired conflict resolution.

        Strategies (from Multi-Agent Memory Consensus research, 06-16):
          - lww: Last-Writer-Wins by accessed timestamp (deterministic)
          - or_set: OR-Set union — keep both versions, link with crdt_merge
          - trust: Trust-weighted — blend weights, prefer higher-trust content

        Args:
            other_graph_data: Export dict from another MemoryGraph.export_json()
            strategy: Merge strategy (lww | or_set | trust)
            trust_weight: Weight for *other* graph's data (0-1, default 0.5)

        Returns:
            Summary dict: {nodes_added, nodes_updated, nodes_skipped, edges_added}
        """
        summary = {"nodes_added": 0, "nodes_updated": 0, "nodes_skipped": 0, "edges_added": 0}

        for node in other_graph_data.get("nodes", []):
            nid = str(node["id"])
            existing = self.get_node(nid)

            if existing is None:
                # New node — direct insert to preserve ID
                tags = node.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]
                self.conn.execute(
                    "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
                    (nid, node.get("label", ""), node.get("kind", "fact"),
                     json.dumps(node.get("data", {})),
                     node.get("created", time.time()), node.get("accessed", time.time()),
                     node.get("weight", 1.0), json.dumps(tags)))
                if self._fts_enabled:
                    self._fts_sync_node(nid)
                summary["nodes_added"] += 1
                continue

            if strategy == "lww":
                other_ts = node.get("accessed", node.get("created", 0))
                local_ts = existing.accessed or existing.created or 0
                if other_ts > local_ts:
                    self.update_node(nid, label=node.get("label", existing.label),
                                     kind=node.get("kind", existing.kind),
                                     data=node.get("data", {}),
                                     weight=node.get("weight", existing.weight))
                    summary["nodes_updated"] += 1
                else:
                    summary["nodes_skipped"] += 1

            elif strategy == "or_set":
                # OR-Set: preserve both versions
                merged_id = f"{nid}::crdt::{int(node.get('accessed', 0))}"
                self.conn.execute(
                    "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
                    (merged_id, node.get("label", ""), node.get("kind", "fact"),
                     json.dumps(node.get("data", {})),
                     node.get("created", time.time()), node.get("accessed", time.time()),
                     node.get("weight", 1.0), json.dumps(node.get("tags", []))))
                if self._fts_enabled:
                    self._fts_sync_node(merged_id)
                self.link(nid, merged_id, "crdt_merge")
                summary["nodes_added"] += 1

            elif strategy == "trust":
                other_w = node.get("weight", 1.0)
                local_w = existing.weight or 1.0
                blended = trust_weight * other_w + (1 - trust_weight) * local_w
                # Update content first, then set blended weight
                if trust_weight > 0.5:
                    self.update_node(nid, label=node.get("label", existing.label),
                                     data=node.get("data", {}),
                                     weight=blended)
                else:
                    self.reweight(nid, blended)
                summary["nodes_updated"] += 1

            else:
                summary["nodes_skipped"] += 1

        self.conn.commit()

        # Merge edges (always union)
        for edge in other_graph_data.get("edges", []):
            s, t = str(edge["source"]), str(edge["target"])
            if not self.is_linked(s, t):
                self.link(s, t, edge.get("relation", "rel"),
                          weight=edge.get("weight", 1.0))
                summary["edges_added"] += 1

        return summary

    # ===================================================================
    # Weighted Degree & Neighborhood Census
    # ===================================================================

    def weighted_degree(self, node_id: str) -> float:
        """Sum of edge weights for a node (in + out).

        Unlike degree count, this captures connection *strength*.
        """
        row = self.conn.execute(
            "SELECT COALESCE(SUM(weight), 0) AS w FROM edges WHERE source = ? OR target = ?",
            (node_id, node_id),
        ).fetchone()
        return float(row["w"]) if row else 0.0

    def weighted_degree_all(self) -> dict[str, float]:
        """Weighted degree for every node."""
        nodes = [str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        return {nid: self.weighted_degree(nid) for nid in nodes}

    def neighborhood_census(self) -> dict[str, dict]:
        """Per-node neighborhood census: degree, weighted_degree, neighbors list.

        Useful for batch analysis and exports.
        """
        nodes = [str(r["id"]) for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        edge_rows = self.conn.execute("SELECT source, target, weight FROM edges").fetchall()
        nbrs: dict[str, list[str]] = {n: [] for n in nodes}
        wsum: dict[str, float] = {n: 0.0 for n in nodes}
        for e in edge_rows:
            s, t = str(e["source"]), str(e["target"])
            w = float(e["weight"]) if e["weight"] is not None else 1.0
            if s in nbrs:
                nbrs[s].append(t)
                wsum[s] += w
            if t in nbrs:
                nbrs[t].append(s)
                wsum[t] += w
        return {
            n: {"degree": len(nbrs[n]), "weighted_degree": wsum[n], "neighbors": nbrs[n]}
            for n in nodes
        }

    # ===================================================================
    # Vector Clock & Incremental Sync (Multi-Agent Causal Consistency)
    # ===================================================================

    def vector_clock(self, node_id: str) -> dict[str, int]:
        """Return the vector clock for a node.

        Tracks causal version per agent (writer). Used by merge_crdt
        to detect concurrent updates vs causal ordering.

        The clock is stored in node metadata under '_vc'. If absent,
        returns a default clock {'_default': 0}.
        """
        node = self.get_node(node_id)
        if node is None:
            raise KeyError(f"Node not found: {node_id}")
        vc = node.data.get("_vc", {"_default": 0})
        if not isinstance(vc, dict):
            vc = {"_default": 0}
        return vc

    def _vector_clock_increment(self, node_id: str, agent_id: str = "_self"):
        """Increment the vector clock entry for *agent_id* on a node."""
        node = self.get_node(node_id)
        if node is None:
            return
        vc = dict(node.data.get("_vc", {}))
        vc[agent_id] = vc.get(agent_id, 0) + 1
        # Merge into data without clobbering other fields
        new_data = dict(node.data)
        new_data["_vc"] = vc
        self.conn.execute(
            "UPDATE nodes SET data=? WHERE id=?",
            (json.dumps(new_data), node_id))
        self.conn.commit()

    @staticmethod
    def _vc_compare(vc_a: dict[str, int], vc_b: dict[str, int]) -> str:
        """Compare two vector clocks.

        Returns:
          'before' — vc_a < vc_b (a happened-before b)
          'after'  — vc_a > vc_b (a happened-after b)
          'equal'  — identical
          'concurrent' — neither precedes (conflict)
        """
        keys = set(vc_a) | set(vc_b)
        a_le_b = True
        b_le_a = True
        for k in keys:
            a_val = vc_a.get(k, 0)
            b_val = vc_b.get(k, 0)
            if a_val > b_val:
                a_le_b = False
            if b_val > a_val:
                b_le_a = False
        if a_le_b and b_le_a:
            return "equal"
        if a_le_b:
            return "before"
        if b_le_a:
            return "after"
        return "concurrent"

    def subscribe(self, callback) -> None:
        """Register a callback for node change events.

        The callback receives a dict with keys:
          event: 'add' | 'update' | 'delete' | 'link'
          node_id: affected node id
          agent_id: writer agent (for multi-agent sync)
          timestamp: event time

        Multiple callbacks are supported (called in registration order).
        """
        if not hasattr(self, '_subscribers'):
            self._subscribers = []
        self._subscribers.append(callback)

    def _notify(self, event: str, node_id: str, agent_id: str = "_self") -> None:
        """Internal: fire subscriber callbacks."""
        if not hasattr(self, '_subscribers'):
            return
        evt = {
            "event": event,
            "node_id": node_id,
            "agent_id": agent_id,
            "timestamp": time.time(),
        }
        for cb in self._subscribers:
            try:
                cb(evt)
            except Exception:
                pass  # subscriber errors don't break the operation

    def get_changes(self, since: float = 0.0) -> dict:
        """Export all node/edge changes since a timestamp (epoch seconds).

        Used for incremental delta-sync between agents.
        Pairs with apply_changes() on the receiving side.

        Returns:
          {'nodes': [...], 'edges': [...], 'timestamp': current_time}
        """
        nodes = [
            {
                "id": str(r["id"]), "label": r["label"], "kind": r["kind"],
                "data": json.loads(r["data"]) if r["data"] else {},
                "created": r["created"], "accessed": r["accessed"],
                "weight": r["weight"],
                "tags": json.loads(r["tags"]) if r["tags"] else [],
            }
            for r in self.conn.execute(
                "SELECT * FROM nodes WHERE accessed >= ? OR created >= ?",
                (since, since)).fetchall()
        ]
        edges = [
            {"source": str(r["source"]), "target": str(r["target"]),
             "relation": r["relation"], "weight": r["weight"]}
            for r in self.conn.execute(
                "SELECT * FROM edges WHERE 1=1").fetchall()
        ]  # edges don't have timestamps; include all (small overhead)
        return {
            "nodes": nodes,
            "edges": edges,
            "timestamp": time.time(),
        }

    def apply_changes(self, delta: dict, agent_id: str = "_remote",
                      strategy: str = "lww") -> dict:
        """Apply a delta (from get_changes) using vector-clock-aware merge.

        Unlike merge_crdt (full export), this works with incremental deltas.
        Uses vector clocks to detect causal ordering:
          - 'before'/'equal': skip (remote is older or same)
          - 'after': accept (remote is newer)
          - 'concurrent': apply strategy (lww/or_set/trust)

        Args:
          delta: Output from another graph's get_changes()
          agent_id: Identifier for the remote agent
          strategy: Conflict strategy for concurrent updates

        Returns:
          Summary dict with counts + any concurrent conflicts detected.
        """
        summary = {"nodes_added": 0, "nodes_updated": 0, "nodes_skipped": 0,
                   "concurrent_conflicts": 0, "edges_added": 0}

        for node in delta.get("nodes", []):
            nid = str(node["id"])
            existing = self.get_node(nid)

            if existing is None:
                # New node — direct insert, seed its vector clock
                tags = node.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]
                data = dict(node.get("data", {}))
                # Ensure vector clock exists
                if "_vc" not in data:
                    data["_vc"] = {agent_id: 1}
                self.conn.execute(
                    "INSERT OR REPLACE INTO nodes (id,label,kind,data,created,accessed,weight,tags) VALUES (?,?,?,?,?,?,?,?)",
                    (nid, node.get("label", ""), node.get("kind", "fact"),
                     json.dumps(data),
                     node.get("created", time.time()), node.get("accessed", time.time()),
                     node.get("weight", 1.0), json.dumps(tags)))
                if self._fts_enabled:
                    self._fts_sync_node(nid)
                summary["nodes_added"] += 1
                self._notify("add", nid, agent_id)
                continue

            # Compare vector clocks
            local_vc = existing.data.get("_vc", {})
            remote_vc = node.get("data", {}).get("_vc", {})
            order = self._vc_compare(local_vc, remote_vc)

            if order in ("before", "equal"):
                # Local is same or newer — check if truly equal
                if order == "equal":
                    summary["nodes_skipped"] += 1
                    continue
                # Remote is newer — accept it
            if order == "concurrent":
                summary["concurrent_conflicts"] += 1
                if strategy == "lww":
                    other_ts = node.get("accessed", 0)
                    local_ts = existing.accessed or 0
                    if other_ts <= local_ts:
                        summary["nodes_skipped"] += 1
                        continue
                # For or_set/trust, fall through to merge_crdt logic

            # Apply the update
            merged_data = dict(node.get("data", {}))
            # Merge vector clocks
            merged_vc = dict(local_vc)
            for k, v in remote_vc.items():
                merged_vc[k] = max(merged_vc.get(k, 0), v)
            merged_data["_vc"] = merged_vc

            self.update_node(nid, label=node.get("label", existing.label),
                             data=merged_data,
                             weight=node.get("weight", existing.weight))
            summary["nodes_updated"] += 1
            self._notify("update", nid, agent_id)

        # Merge edges (union)
        for edge in delta.get("edges", []):
            s, t = str(edge["source"]), str(edge["target"])
            if not self.is_linked(s, t):
                self.link(s, t, edge.get("relation", "rel"),
                          weight=edge.get("weight", 1.0))
                summary["edges_added"] += 1

        self.conn.commit()
        return summary

    # ── Memory Consolidation (GAM ICLR 2026) ──────────────────────

    def semantic_divergence(self, node_id: str) -> dict | None:
        """检测节点与邻居的语义分歧程度 (GAM-inspired)。

        比较 node 的 label/kind 与其直接邻居，计算分歧分数 0-1。
        高分歧 → 该节点可能需要 consolidation (promote/demote/merge)。

        Returns:
            {node_id, label, kind, neighbor_count, divergence, avg_similarity,
             kind_mismatch_ratio, suggestion}
        """
        node = self.get_node(node_id)
        if not node:
            return None

        nbrs = self.neighbors(node_id)
        if not nbrs:
            return {
                "node_id": node_id, "label": node.label, "kind": node.kind,
                "neighbor_count": 0, "divergence": 0.0,
                "avg_similarity": 0.0, "kind_mismatch_ratio": 0.0,
                "suggestion": "isolated",
            }

        sims: list[float] = []
        kind_mismatches = 0
        for nbr in nbrs:
            sim = self._content_similarity(node.label, nbr.label)
            sims.append(sim)
            if nbr.kind != node.kind:
                kind_mismatches += 1

        avg_sim = sum(sims) / len(sims) if sims else 0.0
        # Divergence = 1 - avg_similarity (higher = more different from neighbors)
        divergence = round(1.0 - avg_sim, 4)
        kind_mismatch_ratio = round(kind_mismatches / len(nbrs), 4) if nbrs else 0.0

        # Suggestion based on divergence level
        if divergence > 0.8 and kind_mismatch_ratio > 0.7:
            suggestion = "promote"   # Very different from neighbors → new cluster
        elif divergence < 0.2:
            suggestion = "demote"    # Very similar → merge into neighborhood
        elif kind_mismatch_ratio > 0.5:
            suggestion = "reclassify"  # Kind doesn't match neighborhood
        else:
            suggestion = "keep"

        return {
            "node_id": node_id,
            "label": node.label,
            "kind": node.kind,
            "neighbor_count": len(nbrs),
            "divergence": divergence,
            "avg_similarity": round(avg_sim, 4),
            "kind_mismatch_ratio": kind_mismatch_ratio,
            "suggestion": suggestion,
        }

    def divergence_scan(self, threshold: float = 0.5,
                        limit: int = 100) -> list[dict]:
        """扫描全图，找出高分歧节点 (批量诊断)。

        Args:
            threshold: 最小分歧分数 (0-1)
            limit: 最大返回数量

        Returns:
            List of divergence reports sorted by divergence descending
        """
        all_ids = [r["id"] for r in self.conn.execute(
            "SELECT id FROM nodes ORDER BY accessed DESC LIMIT ?", (limit * 3,)
        ).fetchall()]

        results = []
        for nid in all_ids:
            report = self.semantic_divergence(nid)
            if report and report["divergence"] >= threshold:
                results.append(report)
            if len(results) >= limit:
                break

        results.sort(key=lambda r: r["divergence"], reverse=True)
        return results

    # divergence_scan uses semantic_divergence internally, no changes needed

    def consolidate_memory(self, strategy: str = "auto",
                           divergence_threshold: float = 0.7,
                           similarity_threshold: float = 0.25,
                           dry_run: bool = False) -> dict:
        """记忆固化: 基于语义分歧的记忆整理 (GAM ICLR 2026 inspired)。

        策略:
        - promote: 高分歧节点标记为新聚类种子 (kind 添加 'cluster_seed')
        - demote: 低分歧节点合并到最相似邻居
        - reclassify: kind 与邻居不一致 → 更新 kind 为多数邻居的 kind
        - auto: 自动选择最佳策略 per node (默认)

        Args:
            strategy: auto|promote|demote|reclassify
            divergence_threshold: promote 阈值
            similarity_threshold: demote 阈值 (1-similarity = divergence)
            dry_run: 仅报告不执行

        Returns:
            {scanned, promoted, demoted, reclassified, kept, details}
        """
        all_ids = [r["id"] for r in self.conn.execute(
            "SELECT id FROM nodes"
        ).fetchall()]

        result = {"scanned": 0, "promoted": 0, "demoted": 0,
                  "reclassified": 0, "kept": 0, "details": []}

        for nid in all_ids:
            report = self.semantic_divergence(nid)
            if not report:
                continue
            result["scanned"] += 1
            suggestion = report["suggestion"] if strategy == "auto" else strategy
            div = report["divergence"]

            if suggestion == "promote" or (suggestion == "auto" and div >= divergence_threshold):
                if not dry_run:
                    self.tag_nodes("cluster_seed", [nid])
                result["promoted"] += 1
                result["details"].append(
                    {"node_id": nid, "action": "promote", "divergence": div})

            elif suggestion == "demote" or (suggestion == "auto" and div <= similarity_threshold):
                # Find most similar neighbor and merge into it
                if not dry_run:
                    nbrs = self.neighbors(nid)
                    best_target = None
                    best_sim = 0.0
                    node = self.get_node(nid)
                    for nbr in nbrs:
                        if node:
                            sim = self._content_similarity(node.label, nbr.label)
                            if sim > best_sim:
                                best_sim = sim
                                best_target = nbr.id
                    if best_target and best_sim > 0.3:
                        self.merge_nodes(nid, best_target)
                result["demoted"] += 1
                result["details"].append(
                    {"node_id": nid, "action": "demote", "divergence": div})

            elif suggestion == "reclassify":
                if not dry_run:
                    # Set kind to majority neighbor kind
                    nbrs = self.neighbors(nid)
                    kind_counts: dict[str, int] = defaultdict(int)
                    for nbr in nbrs:
                        kind_counts[nbr.kind] += 1
                    if kind_counts:
                        majority_kind = max(kind_counts, key=kind_counts.get)
                        node = self.get_node(nid)
                        self.update_node(nid, label=node.label,
                                         kind=majority_kind, data=node.data)
                result["reclassified"] += 1
                result["details"].append(
                    {"node_id": nid, "action": "reclassify", "divergence": div})

            else:
                result["kept"] += 1

        if not dry_run:
            self.conn.commit()
        return result

    # ── Retention Scoring & Smart Eviction ────────────────────────

    def retention_score(self, node_id: str,
                        w_importance: float = 0.3,
                        w_recency: float = 0.25,
                        w_connectivity: float = 0.25,
                        w_divergence: float = 0.2) -> dict | None:
        """计算节点保留分数 (0-1), 综合重要性/时效/连接度/分歧度。

        用于智能驱逐决策: 低分节点优先驱逐。
        分数 = importance*w1 + recency*w2 + connectivity*w3 + divergence*w4

        Returns:
            {node_id, label, score, components: {importance, recency, connectivity, divergence}, recommendation}
        """
        node = self.get_node(node_id)
        if not node:
            return None

        # Importance: normalized weight (0-1)
        importance = min(node.weight, 1.0) if node.weight else 0.0

        # Recency: exponential decay based on age (half-life = 7 days)
        now = time.time()
        age_seconds = now - (node.accessed or node.created)
        recency = math.exp(-age_seconds / (7 * 86400))  # half-life ~7 days

        # Connectivity: degree / max_degree in graph (normalized)
        degree = len(self.neighbors(node_id))
        max_degree_row = self.conn.execute(
            "SELECT COUNT(*) as c FROM edges GROUP BY source ORDER BY c DESC LIMIT 1"
        ).fetchone()
        max_degree = max_degree_row["c"] if max_degree_row else 1
        connectivity = min(degree / max(max_degree, 1), 1.0)

        # Divergence: from semantic_divergence (high divergence = unique = keep)
        div_report = self.semantic_divergence(node_id)
        divergence = div_report["divergence"] if div_report else 0.0

        score = (importance * w_importance +
                 recency * w_recency +
                 connectivity * w_connectivity +
                 divergence * w_divergence)

        recommendation = "keep" if score >= 0.4 else ("review" if score >= 0.2 else "evict")

        return {
            "node_id": node_id,
            "label": node.label,
            "score": round(score, 4),
            "components": {
                "importance": round(importance, 4),
                "recency": round(recency, 4),
                "connectivity": round(connectivity, 4),
                "divergence": round(divergence, 4),
            },
            "recommendation": recommendation,
        }

    def memory_evict(self, budget: int = 20,
                     min_score: float = 0.15,
                     dry_run: bool = False) -> dict:
        """基于保留分数的智能驱逐 (FiFA + divergence-aware)。

        1. 计算所有节点 retention_score
        2. 按分数升序排序
        3. 驱逐分数 < min_score 的节点, 最多 budget 个

        Returns:
            {scanned, evicted, kept, details}
        """
        all_ids = [r["id"] for r in self.conn.execute(
            "SELECT id FROM nodes"
        ).fetchall()]

        scores = []
        for nid in all_ids:
            report = self.retention_score(nid)
            if report:
                scores.append(report)

        scores.sort(key=lambda r: r["score"])

        evicted = 0
        details = []
        for report in scores:
            if evicted >= budget:
                break
            if report["score"] >= min_score:
                break
            if not dry_run:
                self.delete_node(report["node_id"])
            evicted += 1
            details.append({
                "node_id": report["node_id"],
                "label": report["label"][:40],
                "score": report["score"],
            })

        if not dry_run:
            self.conn.commit()

        return {
            "scanned": len(scores),
            "evicted": evicted,
            "kept": len(scores) - evicted,
            "details": details,
        }

    # ── Cluster Seed Discovery (Consolidation follow-up) ──────────

    def cluster_seeds(self) -> list[dict]:
        """返回所有标记为 cluster_seed 的节点 (promote 操作的结果)。

        Returns:
            [{node_id, label, kind, weight, neighbor_count}]
        """
        rows = self.conn.execute(
            "SELECT id, label, kind, weight FROM nodes WHERE tags LIKE '%cluster_seed%'",
        ).fetchall()
        results = []
        for r in rows:
            nbrs = self.neighbors(r["id"])
            results.append({
                "node_id": r["id"],
                "label": r["label"],
                "kind": r["kind"],
                "weight": r["weight"],
                "neighbor_count": len(nbrs),
            })
        return results

    def seed_expansion(self, seed_id: str, max_hops: int = 2) -> dict | None:
        """从 cluster_seed 向外扩展，识别聚类边界 (BFS)。

        Returns:
            {seed_id, layers: {hop: [node_ids]}, boundary: [node_ids], size}
        """
        node = self.get_node(seed_id)
        if not node:
            return None

        layers = self.k_hop_neighbors(seed_id, max_hops)
        # Flatten all reached nodes
        all_reached = set()
        for hop, ids in layers.items():
            all_reached.update(ids)

        # Boundary = nodes in the outermost non-empty hop
        boundary = []
        for hop in range(max_hops, 0, -1):
            if hop in layers and layers[hop]:
                boundary = layers[hop]
                break

        return {
            "seed_id": seed_id,
            "seed_label": node.label,
            "layers": {str(k): v for k, v in layers.items()},
            "boundary": boundary,
            "size": len(all_reached) + 1,  # +1 for seed itself
        }

    def consolidation_report(self) -> dict:
        """生成完整记忆固化状态报告。

        Combines: divergence stats + cluster seeds + eviction candidates.

        Returns:
            {total_nodes, high_divergence_count, cluster_seeds,
             eviction_candidates, avg_retention, consolidation_health}
        """
        all_ids = [r["id"] for r in self.conn.execute(
            "SELECT id FROM nodes"
        ).fetchall()]

        if not all_ids:
            return {"total_nodes": 0, "high_divergence_count": 0,
                    "cluster_seeds": 0, "eviction_candidates": 0,
                    "avg_retention": 0.0, "consolidation_health": "empty"}

        high_div = 0
        scores = []
        for nid in all_ids:
            div_r = self.semantic_divergence(nid)
            if div_r and div_r["divergence"] > 0.5:
                high_div += 1
            ret_r = self.retention_score(nid)
            if ret_r:
                scores.append(ret_r["score"])

        seeds = self.cluster_seeds()
        evict_candidates = sum(1 for s in scores if s < 0.2)
        avg_retention = sum(scores) / len(scores) if scores else 0.0

        # Health: good if low high-div ratio + low eviction candidates
        high_div_ratio = high_div / len(all_ids)
        evict_ratio = evict_candidates / len(all_ids) if all_ids else 0
        if high_div_ratio < 0.2 and evict_ratio < 0.1:
            health = "healthy"
        elif high_div_ratio < 0.4 and evict_ratio < 0.3:
            health = "moderate"
        else:
            health = "needs_attention"

        return {
            "total_nodes": len(all_ids),
            "high_divergence_count": high_div,
            "high_divergence_ratio": round(high_div_ratio, 4),
            "cluster_seeds": len(seeds),
            "eviction_candidates": evict_candidates,
            "avg_retention": round(avg_retention, 4),
            "consolidation_health": health,
        }

    # ── Consolidation Pipeline (one-shot orchestrator) ────────────

    def consolidation_pipeline(self,
                               evict_budget: int = 10,
                               min_retention: float = 0.15,
                               dry_run: bool = False) -> dict:
        """一键记忆固化: scan → consolidate → evict → report.

        Orchestrates the full GAM pipeline in one call:
        1. divergence_scan — identify drifted nodes
        2. consolidate_memory(auto) — promote/demote/reclassify
        3. memory_evict — remove low-retention nodes (respects budget)
        4. consolidation_report — summary health dashboard

        Args:
            evict_budget: max nodes to evict (0 = skip eviction)
            min_retention: retention score below which nodes are eviction candidates
            dry_run: if True, report what *would* happen without modifying the graph

        Returns:
            {scan, consolidation, eviction, report, actions_total}
        """
        # Step 1: Scan for divergence issues
        scan_items = self.divergence_scan(threshold=0.5)
        scan = {"flagged": len(scan_items), "items": scan_items}

        # Step 2: Auto-consolidate (promote/demote/reclassify)
        cons = self.consolidate_memory(strategy="auto", dry_run=dry_run)

        # Step 3: Smart eviction (skip if budget is 0)
        if evict_budget > 0:
            evict = self.memory_evict(
                budget=evict_budget, min_score=min_retention, dry_run=dry_run)
        else:
            evict = {"scanned": 0, "evicted": 0, "kept": 0, "details": []}

        # Step 4: Generate report
        report = self.consolidation_report()

        actions = (cons.get("promoted", 0) + cons.get("demoted", 0) +
                   cons.get("reclassified", 0) + evict.get("evicted", 0))

        return {
            "scan": scan,
            "consolidation": cons,
            "eviction": evict,
            "report": report,
            "actions_total": actions,
            "dry_run": dry_run,
        }

    # ── Memory Decay (time-based weight management) ──────────────

    def memory_decay(self, half_life_days: float = 7.0,
                     min_weight: float = 0.01,
                     kinds: list[str] | None = None,
                     dry_run: bool = False) -> dict:
        """Apply exponential time-based weight decay to all (or filtered) nodes.

        Unlike decay_all() which is blunt-force, this provides:
        - Configurable half-life (weight halves every N days since last access)
        - Kind filtering (e.g., only decay 'event' nodes, preserve 'person')
        - Minimum weight floor (don't decay below this)
        - Dry-run preview

        Formula: new_weight = max(min_weight, weight * 0.5^(elapsed_days / half_life_days))

        Args:
            half_life_days: weight halves every this many days (default 7)
            min_weight: floor weight (don't decay below this)
            kinds: only decay these kinds (None = all)
            dry_run: preview without applying

        Returns:
            {scanned, decayed, skipped, total_before, total_after, min_accessed_age_days}
        """
        now = time.time()
        rows = self.conn.execute(
            "SELECT id, kind, accessed, weight FROM nodes"
        ).fetchall()

        scanned = 0
        decayed = 0
        skipped = 0
        total_before = 0.0
        total_after = 0.0
        max_age_days = 0.0

        for r in rows:
            if kinds and r["kind"] not in kinds:
                skipped += 1
                continue

            scanned += 1
            elapsed_days = (now - r["accessed"]) / 86400.0
            max_age_days = max(max_age_days, elapsed_days)
            old_w = r["weight"]
            total_before += old_w

            decay_factor = 0.5 ** (elapsed_days / half_life_days)
            new_w = max(min_weight, old_w * decay_factor)
            total_after += new_w

            if new_w < old_w:
                decayed += 1
                if not dry_run:
                    self.conn.execute(
                        "UPDATE nodes SET weight=? WHERE id=?",
                        (new_w, r["id"]))

        if not dry_run:
            self.conn.commit()

        return {
            "scanned": scanned,
            "decayed": decayed,
            "skipped": skipped,
            "total_before": round(total_before, 4),
            "total_after": round(total_after, 4),
            "weight_lost": round(total_before - total_after, 4),
            "max_accessed_age_days": round(max_age_days, 2),
            "half_life_days": half_life_days,
            "dry_run": dry_run,
        }

    # ── Neighborhood Agreement (multi-hop divergence) ─────────────

    def neighborhood_agreement(self, node_id: str,
                               hops: int = 2) -> dict | None:
        """Extended semantic agreement beyond immediate neighbors.

        While semantic_divergence only looks at 1-hop neighbors, this method
        explores the N-hop neighborhood to detect broader semantic drift:
        - Agreement decreases with hop distance (exponential decay)
        - High multi-hop agreement + low 1-hop agreement = bridge node
        - Low multi-hop agreement + high 1-hop agreement = boundary node

        Args:
            node_id: target node
            hops: max BFS depth (1 = same as semantic_divergence)

        Returns:
            {node_id, label, kind, layers: [{hop, nodes, avg_similarity, agreement}],
             overall_agreement, node_role}
        """
        node = self.get_node(node_id)
        if not node:
            return None

        visited = {node_id}
        frontier = [node_id]
        layers = []

        for hop in range(1, hops + 1):
            next_frontier = []
            sims = []

            for nid in frontier:
                nbrs = self.neighbors(nid)
                for nbr in nbrs:
                    if nbr.id in visited:
                        continue
                    visited.add(nbr.id)
                    next_frontier.append(nbr.id)
                    sim = self._content_similarity(node.label, nbr.label)
                    sims.append(sim)

            if not sims:
                layers.append({"hop": hop, "nodes": 0, "avg_similarity": 0.0,
                               "agreement": 0.0})
                break

            avg_sim = sum(sims) / len(sims)
            # Agreement = similarity weighted by hop distance (closer = more important)
            hop_weight = 1.0 / hop
            agreement = round(avg_sim * hop_weight, 4)

            layers.append({
                "hop": hop,
                "nodes": len(sims),
                "avg_similarity": round(avg_sim, 4),
                "agreement": agreement,
            })
            frontier = next_frontier

        # Check if node is isolated (first layer found nothing)
        if layers and layers[0]["nodes"] == 0:
            return {"node_id": node_id, "label": node.label, "kind": node.kind,
                    "layers": layers, "overall_agreement": 0.0, "node_role": "isolated"}

        if not layers:
            return {"node_id": node_id, "label": node.label, "kind": node.kind,
                    "layers": [], "overall_agreement": 0.0, "node_role": "isolated"}

        # Overall = weighted average of layer agreements
        total_weight = sum(l["nodes"] for l in layers)
        if total_weight > 0:
            overall = sum(l["agreement"] * l["nodes"] for l in layers) / total_weight
        else:
            overall = 0.0
        overall = round(overall, 4)

        # Classify node role
        if len(layers) >= 2:
            l1 = layers[0]["agreement"]
            l2 = layers[1]["agreement"] if len(layers) > 1 else 0.0
            if l1 < 0.3 and overall > 0.5:
                role = "bridge"  # Low local but high global → connects clusters
            elif l1 > 0.5 and overall < 0.3:
                role = "boundary"  # High local but low global → edge of cluster
            elif overall > 0.6:
                role = "core"  # High everywhere → central member
            else:
                role = "peripheral"
        else:
            role = "core" if overall > 0.5 else "peripheral"

        return {
            "node_id": node_id,
            "label": node.label,
            "kind": node.kind,
            "layers": layers,
            "overall_agreement": overall,
            "node_role": role,
        }

    # ── Memory Proximity (semantic neighborhood search) ────────────

    def memory_proximity(self, node_id: str, radius: float = 0.5,
                         limit: int = 20) -> list[dict] | None:
        """Find nodes within a semantic similarity radius of a target.

        Unlike graph-based neighbors(), this uses content similarity (trigram)
        to find semantically close nodes regardless of edge connections.
        Useful for discovering related memories that aren't explicitly linked.

        Args:
            node_id: anchor node
            radius: minimum trigram similarity (0-1) to include
            limit: max results

        Returns:
            List of {node_id, label, kind, similarity, weight, connected}
            sorted by similarity descending. Connected = has edge to anchor.
        """
        node = self.get_node(node_id)
        if not node:
            return None

        anchor_label = node.label
        connected_ids = set()
        for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? UNION "
            "SELECT source FROM edges WHERE target=?",
            (node_id, node_id)
        ).fetchall():
            connected_ids.add(r[0])

        results = []
        for r in self.conn.execute(
            "SELECT id, label, kind, weight FROM nodes WHERE id != ?",
            (node_id,)
        ).fetchall():
            sim = self._content_similarity(anchor_label, r["label"])
            if sim >= radius:
                results.append({
                    "node_id": r["id"],
                    "label": r["label"],
                    "kind": r["kind"],
                    "similarity": round(sim, 4),
                    "weight": r["weight"],
                    "connected": r["id"] in connected_ids,
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    # ── Tag Induced Subgraph ──────────────────────────────────────

    def tag_induced_subgraph(self, tags: list[str],
                             match: str = "any") -> dict | None:
        """Extract a subgraph of nodes matching the given tags.

        Unlike search_by_tag (returns node list only), this returns
        a full subgraph with edges preserved, enabling localized analysis.

        Args:
            tags: tag list to filter by
            match: 'any' (OR) or 'all' (AND)

        Returns:
            {nodes: [{id, label, kind, tags, weight}],
             edges: [{source, target, relation}],
             node_count, edge_count, tags_matched}
        """
        tag_set = set(tags)
        matching_ids = set()

        for r in self.conn.execute(
            "SELECT id, tags FROM nodes"
        ).fetchall():
            node_tags = set(json.loads(r["tags"]))
            if match == "all":
                if tag_set.issubset(node_tags):
                    matching_ids.add(r["id"])
            else:  # any
                if tag_set & node_tags:
                    matching_ids.add(r["id"])

        if not matching_ids:
            return {"nodes": [], "edges": [],
                    "node_count": 0, "edge_count": 0,
                    "tags_matched": tags}

        # Fetch nodes
        nodes_out = []
        id_list = list(matching_ids)
        placeholders = ",".join("?" * len(id_list))
        for r in self.conn.execute(
            f"SELECT * FROM nodes WHERE id IN ({placeholders})", id_list
        ).fetchall():
            nodes_out.append({
                "id": r["id"], "label": r["label"], "kind": r["kind"],
                "tags": json.loads(r["tags"]), "weight": r["weight"],
            })

        # Fetch internal edges (both endpoints in matching set)
        edges_out = []
        for r in self.conn.execute(
            f"SELECT source, target, relation FROM edges "
            f"WHERE source IN ({placeholders}) AND target IN ({placeholders})",
            id_list + id_list
        ).fetchall():
            edges_out.append({
                "source": r["source"], "target": r["target"],
                "relation": r["relation"],
            })

        return {
            "nodes": nodes_out,
            "edges": edges_out,
            "node_count": len(nodes_out),
            "edge_count": len(edges_out),
            "tags_matched": tags,
        }

    # ── Memory Annotations (structured searchable metadata) ────────

    def memory_annotate(self, node_id: str, key: str, value: str) -> bool:
        """Add a structured key-value annotation to a node.

        Annotations are searchable metadata stored alongside the node's data.
        Unlike tags (flat labels), annotations have explicit key-value structure.
        Useful for: confidence scores, source attribution, quality ratings, etc.

        Args:
            node_id: target node
            key: annotation key (e.g., 'confidence', 'source')
            value: annotation value (e.g., '0.95', 'paper')

        Returns:
            True if node existed and annotation was added.
        """
        node = self.get_node(node_id)
        if not node:
            return False
        data = dict(node.data) if node.data else {}
        if "_annotations" not in data:
            data["_annotations"] = {}
        data["_annotations"][key] = value
        self.conn.execute(
            "UPDATE nodes SET data=? WHERE id=?",
            (json.dumps(data), node_id))
        self.conn.commit()
        return True

    def annotation_get(self, node_id: str, key: str) -> str | None:
        """Retrieve a specific annotation value."""
        node = self.get_node(node_id)
        if not node or not node.data:
            return None
        annotations = node.data.get("_annotations", {})
        return annotations.get(key)

    def annotation_remove(self, node_id: str, key: str) -> bool:
        """Remove an annotation from a node. Returns True if removed."""
        node = self.get_node(node_id)
        if not node or not node.data:
            return False
        data = dict(node.data)
        annotations = data.get("_annotations", {})
        if key not in annotations:
            return False
        del annotations[key]
        if annotations:
            data["_annotations"] = annotations
        else:
            del data["_annotations"]
        self.conn.execute(
            "UPDATE nodes SET data=? WHERE id=?",
            (json.dumps(data), node_id))
        self.conn.commit()
        return True

    def annotation_search(self, key: str, value: str | None = None,
                          limit: int = 50) -> list[dict]:
        """Find nodes by annotation key (and optional value).

        Args:
            key: annotation key to search for
            value: if provided, only match nodes where annotation[key] == value
            limit: max results

        Returns:
            List of {node_id, label, kind, annotation_value}
        """
        results = []
        for r in self.conn.execute(
            "SELECT id, label, kind, data FROM nodes LIMIT ?", (limit * 5,)
        ).fetchall():
            data = json.loads(r["data"])
            annotations = data.get("_annotations", {})
            if key in annotations:
                ann_val = annotations[key]
                if value is not None and ann_val != value:
                    continue
                results.append({
                    "node_id": r["id"],
                    "label": r["label"],
                    "kind": r["kind"],
                    "annotation_value": ann_val,
                })
            if len(results) >= limit:
                break
        return results

    # ── Workflow Memory (AWM ICML 2025 / ReasoningBank ICLR 2026) ──────

    def add_workflow(self, goal: str, steps: list[dict],
                     source_trajectories: list[str] | None = None,
                     tags: list[str] | None = None) -> str:
        """Create a workflow node with ordered step nodes and edges.

        Implements Agent Workflow Memory (AWM) pattern: store reusable
        multi-step procedures extracted from execution trajectories.

        Args:
            goal: natural-language description of the workflow goal
            steps: ordered list of {label, action, detail} dicts
            source_trajectories: IDs of trajectory nodes this was extracted from
            tags: optional tags for retrieval

        Returns:
            workflow node ID
        """
        wf_id = self.add(
            goal, kind="workflow",
            data={
                "_workflow": True,
                "step_count": len(steps),
                "success_count": 0,
                "failure_count": 0,
                "source_trajectories": source_trajectories or [],
            },
            tags=tags or [],
        ).id
        for i, step in enumerate(steps):
            step_node = self.add(
                step.get("label", f"Step {i+1}"),
                kind="workflow_step",
                data={
                    "_workflow_step": True,
                    "workflow_id": wf_id,
                    "order": i,
                    "action": step.get("action", ""),
                    "detail": step.get("detail", ""),
                },
            )
            self.link(wf_id, step_node.id, "has_step", weight=1.0 - i * 0.01)
            if i > 0:
                prev = self.conn.execute(
                    "SELECT target FROM edges WHERE source=? AND relation='has_step' "
                    "ORDER BY weight DESC LIMIT 1 OFFSET ?",
                    (wf_id, i - 1),
                ).fetchone()
                if prev:
                    self.link(prev["target"], step_node.id, "next_step")
        for traj_id in (source_trajectories or []):
            if self.has_node(traj_id):
                self.link(wf_id, traj_id, "extracted_from")
        return wf_id

    def retrieve_workflows(self, goal: str | None = None,
                          tags: list[str] | None = None,
                          limit: int = 10) -> list[dict]:
        """Retrieve workflows matching goal text and/or tags.

        Uses tag intersection (Jaccard) and goal trigram overlap for ranking.
        Falls back to listing all workflows if no filters.

        Returns:
            Sorted list of {id, goal, step_count, success_count,
                             failure_count, score, steps}
        """
        candidates = []
        for r in self.conn.execute(
            "SELECT id, label, data, tags FROM nodes WHERE kind='workflow'"
        ).fetchall():
            data = json.loads(r["data"])
            if not data.get("_workflow"):
                continue
            score = 0.0
            has_tag_match = True
            if tags:
                wf_tags = set(json.loads(r["tags"])) if r["tags"] else set()
                overlap = len(wf_tags & set(tags))
                total = len(wf_tags | set(tags)) or 1
                score += overlap / total  # Jaccard
                has_tag_match = overlap > 0
            if not has_tag_match:
                continue
            if goal:
                wf_label_lower = r["label"].lower()
                goal_lower = goal.lower()
                goal_trigrams = {goal_lower[i:i+3] for i in range(len(goal_lower) - 2)}
                label_trigrams = {wf_label_lower[i:i+3] for i in range(len(wf_label_lower) - 2)}
                if goal_trigrams and label_trigrams:
                    score += len(goal_trigrams & label_trigrams) / len(goal_trigrams | label_trigrams)
            success_bonus = data.get("success_count", 0) * 0.1
            success_bonus -= data.get("failure_count", 0) * 0.05
            score += success_bonus
            candidates.append((score, r, data))
        candidates.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, r, data in candidates[:limit]:
            steps_out = []
            for s in self.conn.execute(
                "SELECT target FROM edges WHERE source=? AND relation='has_step' "
                "ORDER BY weight DESC", (r["id"],)
            ).fetchall():
                step_node = self.get_node(s["target"])
                if step_node and step_node.data.get("_workflow_step"):
                    steps_out.append({
                        "label": step_node.label,
                        "action": step_node.data.get("action", ""),
                        "detail": step_node.data.get("detail", ""),
                    })
            results.append({
                "id": r["id"],
                "goal": r["label"],
                "step_count": data.get("step_count", len(steps_out)),
                "success_count": data.get("success_count", 0),
                "failure_count": data.get("failure_count", 0),
                "score": round(score, 4),
                "steps": steps_out,
            })
        return results

    def record_workflow_outcome(self, workflow_id: str, success: bool,
                                detail: str = "") -> bool:
        """Record execution outcome for a workflow.

        Increments success/failure counter. Optional detail stored in data.
        Returns True if workflow existed.
        """
        node = self.get_node(workflow_id)
        if not node or node.kind != "workflow":
            return False
        data = dict(node.data) if node.data else {}
        if success:
            data["success_count"] = data.get("success_count", 0) + 1
        else:
            data["failure_count"] = data.get("failure_count", 0) + 1
        outcomes = data.get("_outcomes", [])
        outcomes.append({
            "success": success,
            "detail": detail,
            "ts": time.time(),
        })
        data["_outcomes"] = outcomes[-50:]  # keep last 50
        self.conn.execute(
            "UPDATE nodes SET data=? WHERE id=?",
            (json.dumps(data), workflow_id))
        self.conn.commit()
        return True

    def workflow_stats(self) -> dict:
        """Global workflow memory statistics.

        Returns counts, success rates, and coverage metrics.
        """
        workflows = self.conn.execute(
            "SELECT id, data FROM nodes WHERE kind='workflow'"
        ).fetchall()
        total = len(workflows)
        total_success = 0
        total_failure = 0
        total_steps = 0
        used = 0
        for r in workflows:
            data = json.loads(r["data"])
            s = data.get("success_count", 0)
            f = data.get("failure_count", 0)
            total_success += s
            total_failure += f
            total_steps += data.get("step_count", 0)
            if s + f > 0:
                used += 1
        step_nodes = self.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE kind='workflow_step'"
        ).fetchone()["c"]
        avg_steps = total_steps / total if total else 0
        total_attempts = total_success + total_failure
        success_rate = total_success / total_attempts if total_attempts else 0.0
        coverage = used / total if total else 0.0
        return {
            "total_workflows": total,
            "total_steps": step_nodes,
            "avg_steps_per_workflow": round(avg_steps, 1),
            "total_success": total_success,
            "total_failure": total_failure,
            "success_rate": round(success_rate, 4),
            "used_workflows": used,
            "coverage": round(coverage, 4),
        }

    def workflow_compose(self, workflow_a_id: str, workflow_b_id: str,
                         goal: str | None = None,
                         bridge_label: str | None = None) -> str | None:
        """Compose two workflows into a new one (AWM snowball effect).

        Creates a new workflow whose steps are A's steps followed by B's steps,
        with an optional bridge step connecting them. The new workflow references
        both sources via extracted_from edges.

        Args:
            workflow_a_id: first workflow (prefix steps)
            workflow_b_id: second workflow (suffix steps)
            goal: combined goal (defaults to "A + B")
            bridge_label: optional bridge step between A and B

        Returns:
            New workflow ID, or None if either source doesn't exist.
        """
        node_a = self.get_node(workflow_a_id)
        node_b = self.get_node(workflow_b_id)
        if not node_a or not node_b or node_a.kind != "workflow" or node_b.kind != "workflow":
            return None
        a_steps = self.conn.execute(
            "SELECT target FROM edges WHERE source=? AND relation='has_step' "
            "ORDER BY weight DESC", (workflow_a_id,)
        ).fetchall()
        b_steps = self.conn.execute(
            "SELECT target FROM edges WHERE source=? AND relation='has_step' "
            "ORDER BY weight DESC", (workflow_b_id,)
        ).fetchall()
        combined_steps = []
        for s in a_steps:
            sn = self.get_node(s["target"])
            if sn and sn.data.get("_workflow_step"):
                combined_steps.append({
                    "label": sn.label,
                    "action": sn.data.get("action", ""),
                    "detail": sn.data.get("detail", ""),
                })
        if bridge_label:
            combined_steps.append({"label": bridge_label, "action": "bridge", "detail": ""})
        for s in b_steps:
            sn = self.get_node(s["target"])
            if sn and sn.data.get("_workflow_step"):
                combined_steps.append({
                    "label": sn.label,
                    "action": sn.data.get("action", ""),
                    "detail": sn.data.get("detail", ""),
                })
        new_goal = goal or f"{node_a.label} + {node_b.label}"
        new_id = self.add_workflow(
            new_goal, combined_steps,
            source_trajectories=[workflow_a_id, workflow_b_id],
        )
        return new_id

    def workflow_dedup(self, similarity_threshold: float = 0.8,
                       dry_run: bool = False) -> dict:
        """Find and merge near-duplicate workflows.

        Uses goal trigram similarity to detect duplicates.
        Merges by keeping the one with more successes and merging steps.

        Args:
            similarity_threshold: trigram Jaccard above this = duplicate
            dry_run: if True, report only without merging

        Returns:
            {checked, duplicates_found, merged, details}
        """
        workflows = []
        for r in self.conn.execute(
            "SELECT id, label, data FROM nodes WHERE kind='workflow'"
        ).fetchall():
            data = json.loads(r["data"])
            if not data.get("_workflow"):
                continue
            workflows.append((r["id"], r["label"], data))
        duplicates = []
        merged_ids = set()
        merge_details = []
        for i, (id_a, label_a, data_a) in enumerate(workflows):
            if id_a in merged_ids:
                continue
            for j in range(i + 1, len(workflows)):
                id_b, label_b, data_b = workflows[j]
                if id_b in merged_ids:
                    continue
                la, lb = label_a.lower(), label_b.lower()
                ta = {la[k:k+3] for k in range(len(la) - 2)}
                tb = {lb[k:k+3] for k in range(len(lb) - 2)}
                if not ta or not tb:
                    continue
                sim = len(ta & tb) / len(ta | tb)
                if sim >= similarity_threshold:
                    duplicates.append((id_a, id_b, sim))
                    if not dry_run:
                        succ_a = data_a.get("success_count", 0)
                        succ_b = data_b.get("success_count", 0)
                        keep_id = id_a if succ_a >= succ_b else id_b
                        remove_id = id_b if keep_id == id_a else id_a
                        merged_ids.add(remove_id)
                        remove_node = self.get_node(remove_id)
                        keep_node = self.get_node(keep_id)
                        if remove_node and keep_node:
                            keep_data = dict(keep_node.data)
                            keep_data["success_count"] = (
                                keep_data.get("success_count", 0) +
                                remove_node.data.get("success_count", 0))
                            keep_data["failure_count"] = (
                                keep_data.get("failure_count", 0) +
                                remove_node.data.get("failure_count", 0))
                            self.conn.execute(
                                "UPDATE nodes SET data=? WHERE id=?",
                                (json.dumps(keep_data), keep_id))
                            self.conn.execute(
                                "DELETE FROM edges WHERE source=? OR target=?",
                                (remove_id, remove_id))
                            self.conn.execute(
                                "DELETE FROM nodes WHERE id=?", (remove_id,))
                            self.conn.commit()
                        merge_details.append({
                            "kept": keep_id,
                            "removed": remove_id,
                            "similarity": round(sim, 4),
                        })
        return {
            "checked": len(workflows),
            "duplicates_found": len(duplicates),
            "merged": len(merge_details),
            "details": merge_details,
        }

    def add_workflow_tip(self, workflow_id: str, tip_type: str,
                         content: str, detail: str = "") -> str | None:
        """Attach a success/recovery/optimization tip to a workflow.

        Inspired by ReasoningBank (ICLR 2026): distill reasoning strategies
        from both successful and failed executions.

        Args:
            workflow_id: target workflow
            tip_type: 'success' | 'failure' | 'recovery' | 'optimization'
            content: the tip text (natural language guidance)
            detail: optional supporting detail

        Returns:
            Tip node ID, or None if workflow doesn't exist.
        """
        if not self.get_node(workflow_id):
            return None
        tip_id = self.add(
            content[:80],
            kind="workflow_tip",
            data={
                "_workflow_tip": True,
                "workflow_id": workflow_id,
                "tip_type": tip_type,
                "content": content,
                "detail": detail,
                "created": time.time(),
            },
        ).id
        self.link(workflow_id, tip_id, "has_tip")
        return tip_id

    def retrieve_workflow_tips(self, workflow_id: str,
                               tip_type: str | None = None,
                               limit: int = 20) -> list[dict]:
        """Retrieve tips for a workflow, optionally filtered by type.

        Args:
            workflow_id: target workflow
            tip_type: filter by 'success'|'failure'|'recovery'|'optimization'
            limit: max results

        Returns:
            List of {tip_id, tip_type, content, detail}
        """
        results = []
        for r in self.conn.execute(
            "SELECT target FROM edges WHERE source=? AND relation='has_tip'",
            (workflow_id,)
        ).fetchall():
            node = self.get_node(r["target"])
            if not node or not node.data.get("_workflow_tip"):
                continue
            if tip_type and node.data.get("tip_type") != tip_type:
                continue
            results.append({
                "tip_id": node.id,
                "tip_type": node.data.get("tip_type", ""),
                "content": node.data.get("content", ""),
                "detail": node.data.get("detail", ""),
            })
            if len(results) >= limit:
                break
        return results

    def workflow_prompt_section(self, workflow_id: str,
                                max_tips: int = 5) -> str:
        """Generate an LLM-injectable prompt section for a workflow.

        Includes goal, steps, and relevant tips (success strategies +
        failure warnings). Designed for AWM-style context injection.

        Returns empty string if workflow doesn't exist.
        """
        node = self.get_node(workflow_id)
        if not node or node.kind != "workflow":
            return ""
        data = node.data
        lines = [f"## Workflow: {node.label}"]
        s = data.get("success_count", 0)
        f = data.get("failure_count", 0)
        if s or f:
            lines.append(f"(success: {s}, failed: {f})")
        steps = self.retrieve_workflows()
        wf_data = next((w for w in steps if w["id"] == workflow_id), None)
        if wf_data:
            lines.append("")
            lines.append("Steps:")
            for i, step in enumerate(wf_data["steps"], 1):
                lines.append(f"  {i}. {step['label']}")
        tips = self.retrieve_workflow_tips(workflow_id, limit=max_tips)
        if tips:
            success_tips = [t for t in tips if t["tip_type"] == "success"]
            failure_tips = [t for t in tips if t["tip_type"] in ("failure", "recovery")]
            if success_tips:
                lines.append("")
                lines.append("Success strategies:")
                for t in success_tips[:max_tips // 2]:
                    lines.append(f"  ✅ {t['content']}")
            if failure_tips:
                lines.append("")
                lines.append("Known pitfalls:")
                for t in failure_tips[:max_tips // 2]:
                    lines.append(f"  ⚠️  {t['content']}")
        return "\n".join(lines)

    def workflow_prune_tips(self, workflow_id: str,
                            tip_type: str | None = None) -> int:
        """Remove tips from a workflow. Returns count removed.

        Args:
            workflow_id: target workflow
            tip_type: if provided, only remove tips of this type
        """
        removed = 0
        tips = self.retrieve_workflow_tips(workflow_id, tip_type=tip_type,
                                            limit=10000)
        for tip in tips:
            self.conn.execute(
                "DELETE FROM edges WHERE source=? AND target=? AND relation='has_tip'",
                (workflow_id, tip["tip_id"]))
            self.conn.execute(
                "DELETE FROM nodes WHERE id=?", (tip["tip_id"],))
            removed += 1
        if removed:
            self.conn.commit()
        return removed

    def workflow_export(self, workflow_id: str) -> dict | None:
        """Export a workflow and all its components as a portable dict.

        Includes goal, steps, tips, outcomes, and stats.
        Useful for cross-agent workflow sharing (memorywire-compatible).
        """
        node = self.get_node(workflow_id)
        if not node or node.kind != "workflow":
            return None
        data = dict(node.data)
        wf_data = next((w for w in self.retrieve_workflows(limit=10000)
                        if w["id"] == workflow_id), None)
        tips = self.retrieve_workflow_tips(workflow_id, limit=10000)
        return {
            "goal": node.label,
            "steps": wf_data["steps"] if wf_data else [],
            "success_count": data.get("success_count", 0),
            "failure_count": data.get("failure_count", 0),
            "tips": tips,
            "source_trajectories": data.get("source_trajectories", []),
            "exported_at": time.time(),
        }

    def workflow_import(self, wf_data: dict,
                        tags: list[str] | None = None) -> str:
        """Import a workflow from an export dict (round-trip with workflow_export).

        Creates a new workflow with steps, tips, and outcome counters.
        Does NOT import source trajectory links (they may not exist).

        Returns:
            New workflow ID.
        """
        wf_id = self.add_workflow(
            wf_data.get("goal", "imported workflow"),
            wf_data.get("steps", []),
            tags=tags,
        )
        for _ in range(wf_data.get("success_count", 0)):
            self.record_workflow_outcome(wf_id, True)
        for _ in range(wf_data.get("failure_count", 0)):
            self.record_workflow_outcome(wf_id, False)
        for tip in wf_data.get("tips", []):
            self.add_workflow_tip(
                wf_id,
                tip.get("tip_type", "success"),
                tip.get("content", ""),
                tip.get("detail", ""),
            )
        return wf_id

    def workflow_success_patterns(self, min_workflows: int = 2,
                                  min_success_rate: float = 0.5) -> list[dict]:
        """Mine common action patterns across successful workflows.

        AWM insight: cross-trajectory pattern mining reveals reusable building
        blocks that no single workflow contains.  Finds actions that appear
        across multiple high-success-rate workflows, ranked by frequency.

        Args:
            min_workflows: minimum number of workflows an action must appear in
            min_success_rate: only consider workflows with success_rate >= this

        Returns:
            List of {action, frequency, workflow_ids, avg_order} sorted by
            frequency descending.
        """
        workflows = self.conn.execute(
            "SELECT id, data FROM nodes WHERE kind='workflow'"
        ).fetchall()
        qualified = []
        for r in workflows:
            data = json.loads(r["data"])
            s = data.get("success_count", 0)
            f = data.get("failure_count", 0)
            rate = s / (s + f) if (s + f) > 0 else 0.0
            if rate >= min_success_rate and (s + f) > 0:
                qualified.append(r["id"])
        if len(qualified) < min_workflows:
            return []
        action_map: dict[str, dict] = {}
        for wf_id in qualified:
            steps = self.conn.execute(
                "SELECT target FROM edges WHERE source=? AND relation='has_step'",
                (wf_id,),
            ).fetchall()
            for step_row in steps:
                step_node = self.get_node(step_row["target"])
                if not step_node:
                    continue
                step_data = step_node.data if isinstance(step_node.data, dict) else json.loads(step_node.data)
                action = step_data.get("action", step_node.label)
                if action not in action_map:
                    action_map[action] = {
                        "action": action,
                        "frequency": 0,
                        "workflow_ids": [],
                        "orders": [],
                    }
                entry = action_map[action]
                if wf_id not in entry["workflow_ids"]:
                    entry["frequency"] += 1
                    entry["workflow_ids"].append(wf_id)
                entry["orders"].append(step_data.get("order", 0))
        patterns = []
        for action, info in action_map.items():
            if info["frequency"] >= min_workflows:
                avg_order = sum(info["orders"]) / len(info["orders"])
                patterns.append({
                    "action": action,
                    "frequency": info["frequency"],
                    "workflow_ids": info["workflow_ids"],
                    "avg_order": round(avg_order, 1),
                })
        patterns.sort(key=lambda x: x["frequency"], reverse=True)
        return patterns

    def node_similarity(self, node_a_id: str, node_b_id: str) -> dict:
        """Compute multi-dimensional similarity between two nodes.

        Combines label trigram overlap, tag Jaccard, neighborhood overlap,
        and kind match into a composite score.

        Returns:
            {label_similarity, tag_similarity, neighbor_similarity,
             kind_match, composite} where composite is 0~1.
        """
        a = self.get_node(node_a_id)
        b = self.get_node(node_b_id)
        if not a or not b:
            return {"composite": 0.0}
        # Fetch tags from DB (Node dataclass has no tags field)
        row_a = self.conn.execute("SELECT tags FROM nodes WHERE id=?", (node_a_id,)).fetchone()
        row_b = self.conn.execute("SELECT tags FROM nodes WHERE id=?", (node_b_id,)).fetchone()
        # Label trigram overlap
        def _trigrams(s: str) -> set:
            s = s.lower().strip()
            return {s[i:i+3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}
        ta = _trigrams(a.label)
        tb = _trigrams(b.label)
        label_sim = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
        # Tag Jaccard
        tags_a = set(json.loads(row_a["tags"])) if row_a and row_a["tags"] else set()
        tags_b = set(json.loads(row_b["tags"])) if row_b and row_b["tags"] else set()
        tag_sim = len(tags_a & tags_b) / len(tags_a | tags_b) if (tags_a | tags_b) else 0.0
        # Neighborhood overlap
        na = {n["target"] for n in self.conn.execute(
            "SELECT target FROM edges WHERE source=?", (node_a_id,)
        ).fetchall()}
        na.update(n["source"] for n in self.conn.execute(
            "SELECT source FROM edges WHERE target=?", (node_a_id,)
        ).fetchall())
        nb = {n["target"] for n in self.conn.execute(
            "SELECT target FROM edges WHERE source=?", (node_b_id,)
        ).fetchall()}
        nb.update(n["source"] for n in self.conn.execute(
            "SELECT source FROM edges WHERE target=?", (node_b_id,)
        ).fetchall())
        neighbor_sim = len(na & nb) / len(na | nb) if (na | nb) else 0.0
        kind_match = 1.0 if a.kind == b.kind else 0.0
        composite = (
            label_sim * 0.35 + tag_sim * 0.25 +
            neighbor_sim * 0.25 + kind_match * 0.15
        )
        return {
            "label_similarity": round(label_sim, 4),
            "tag_similarity": round(tag_sim, 4),
            "neighbor_similarity": round(neighbor_sim, 4),
            "kind_match": kind_match,
            "composite": round(composite, 4),
        }

    def memory_clone(self, node_id: str,
                     new_label: str | None = None,
                     deep_edges: bool = True) -> str | None:
        """Clone a node with its data, tags, and optionally edges.

        Creates a new node with the same kind/data/tags as the original.
        If deep_edges=True, copies all edges (both directions) with the
        new node as source/target.  Annotations are also copied.

        Returns:
            New node ID, or None if original doesn't exist.
        """
        original = self.get_node(node_id)
        if not original:
            return None
        cloned = self.add(
            new_label or f"{original.label} (clone)",
            kind=original.kind,
            data=original.data if isinstance(original.data, dict) else json.loads(original.data),
            tags=json.loads(self.conn.execute("SELECT tags FROM nodes WHERE id=?", (node_id,)).fetchone()["tags"]),
        )
        if deep_edges:
            outgoing = self.conn.execute(
                "SELECT target, relation, weight FROM edges WHERE source=?",
                (node_id,),
            ).fetchall()
            for e in outgoing:
                self.link(cloned.id, e["target"], e["relation"], e["weight"])
            incoming = self.conn.execute(
                "SELECT source, relation, weight FROM edges WHERE target=?",
                (node_id,),
            ).fetchall()
            for e in incoming:
                self.link(e["source"], cloned.id, e["relation"], e["weight"])
        # Copy annotations (stored in data._annotations)
        original_data = original.data if isinstance(original.data, dict) else json.loads(original.data)
        annotations = original_data.get("_annotations", {})
        if annotations:
            cloned_data = cloned.data if isinstance(cloned.data, dict) else json.loads(cloned.data)
            cloned_data["_annotations"] = dict(annotations)
            self.conn.execute(
                "UPDATE nodes SET data=? WHERE id=?",
                (json.dumps(cloned_data), cloned.id))
            self.conn.commit()
        return cloned.id

    def graph_diff_summary(self, other: 'MemoryGraph') -> str:
        """Human-readable summary of differences between two graphs.

        Complements graph_diff() with a formatted multi-line string suitable
        for logging, reports, or LLM context injection.

        Returns:
            Newline-separated summary string.
        """
        diff = self.graph_diff(other)
        lines = []
        n_self = len(diff["nodes_only_self"])
        n_other = len(diff["nodes_only_other"])
        n_mod = len(diff["nodes_modified"])
        n_eself = len(diff["edges_only_self"])
        n_eother = len(diff["edges_only_other"])
        total = n_self + n_other + n_mod + n_eself + n_eother
        if total == 0:
            return "Graphs are identical."
        lines.append(f"Graph Diff Summary ({total} differences):")
        if n_self:
            lines.append(f"  Nodes only in self: {n_self}")
        if n_other:
            lines.append(f"  Nodes only in other: {n_other}")
        if n_mod:
            fields = {}
            for m in diff["nodes_modified"]:
                fields[m["field"]] = fields.get(m["field"], 0) + 1
            detail = ", ".join(f"{k}:{v}" for k, v in sorted(fields.items()))
            lines.append(f"  Modified nodes: {n_mod} ({detail})")
        if n_eself:
            lines.append(f"  Edges only in self: {n_eself}")
        if n_eother:
            lines.append(f"  Edges only in other: {n_eother}")
        return "\n".join(lines)

    def workflow_retrieve_by_tag(self, tags: list[str],
                                 match_all: bool = False,
                                 limit: int = 10) -> list[dict]:
        """Retrieve workflows by tag intersection.

        Complements retrieve_workflows (goal-based) with tag-based filtering.
        Useful for domain-scoped workflow lookup (e.g., tags=['ci', 'deploy']).

        Args:
            tags: tags to match
            match_all: if True require all tags (AND), else any (OR)
            limit: max results

        Returns:
            List of workflow dicts with goal, tags, success_rate, step_count.
        """
        workflows = self.conn.execute(
            "SELECT id, label, data, tags FROM nodes WHERE kind='workflow'"
        ).fetchall()
        results = []
        target_tags = set(tags)
        for r in workflows:
            wf_tags = set(json.loads(r["tags"])) if r["tags"] else set()
            if match_all:
                if not target_tags.issubset(wf_tags):
                    continue
            else:
                if not (target_tags & wf_tags):
                    continue
            data = json.loads(r["data"])
            s = data.get("success_count", 0)
            f = data.get("failure_count", 0)
            rate = s / (s + f) if (s + f) > 0 else 0.0
            results.append({
                "id": r["id"],
                "goal": r["label"],
                "tags": sorted(wf_tags),
                "success_rate": round(rate, 4),
                "step_count": data.get("step_count", 0),
                "success_count": s,
                "failure_count": f,
            })
            if len(results) >= limit:
                break
        results.sort(key=lambda x: x["success_rate"], reverse=True)
        return results

    def node_degree_summary(self, node_id: str) -> dict | None:
        """Compact in/out/total degree breakdown for a node.

        Returns:
            {in_degree, out_degree, total, by_relation: {relation: count}}
            or None if node doesn't exist.
        """
        if not self.has_node(node_id):
            return None
        outgoing = self.conn.execute(
            "SELECT relation, COUNT(*) as c FROM edges WHERE source=? GROUP BY relation",
            (node_id,),
        ).fetchall()
        incoming = self.conn.execute(
            "SELECT relation, COUNT(*) as c FROM edges WHERE target=? GROUP BY relation",
            (node_id,),
        ).fetchall()
        out_by_rel = {r["relation"]: r["c"] for r in outgoing}
        in_by_rel = {r["relation"]: r["c"] for r in incoming}
        by_relation = {}
        for rel in set(out_by_rel) | set(in_by_rel):
            by_relation[rel] = {
                "out": out_by_rel.get(rel, 0),
                "in": in_by_rel.get(rel, 0),
            }
        return {
            "in_degree": sum(in_by_rel.values()),
            "out_degree": sum(out_by_rel.values()),
            "total": sum(in_by_rel.values()) + sum(out_by_rel.values()),
            "by_relation": by_relation,
        }

    def tag_correlation_network(self, min_co_occurrence: int = 2) -> dict:
        """Build a tag co-occurrence correlation network.

        Analyzes which tags appear together on the same nodes and returns
        a weighted graph of tag pairs.  Useful for discovering latent
        semantic structure in the knowledge graph.

        Args:
            min_co_occurrence: minimum times two tags must co-occur

        Returns:
            {nodes: [{tag, frequency}], edges: [{source, target, weight}], summary}
        """
        rows = self.conn.execute(
            "SELECT tags FROM nodes WHERE tags != '[]'"
        ).fetchall()
        tag_freq: dict[str, int] = {}
        pair_freq: dict[tuple[str, str], int] = {}
        for r in rows:
            tags = sorted(set(json.loads(r["tags"])))
            for t in tags:
                tag_freq[t] = tag_freq.get(t, 0) + 1
            for i in range(len(tags)):
                for j in range(i + 1, len(tags)):
                    pair = (tags[i], tags[j])
                    pair_freq[pair] = pair_freq.get(pair, 0) + 1
        nodes = [
            {"tag": t, "frequency": f}
            for t, f in sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)
        ]
        edges = [
            {"source": a, "target": b, "weight": w}
            for (a, b), w in sorted(pair_freq.items(), key=lambda x: x[1], reverse=True)
            if w >= min_co_occurrence
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "total_tags": len(nodes),
            "total_correlations": len(edges),
            "strongest_correlation": edges[0] if edges else None,
        }

    def memory_path_explain(self, source_id: str, target_id: str) -> str | None:
        """Explain the path between two nodes as a narrative string.

        Finds the shortest path, then renders edge labels as a readable
        chain.  Useful for LLM context injection and debugging.

        Returns:
            Human-readable path string, or None if no path / nodes missing.
        """
        path = self.shortest_path(source_id, target_id)
        if not path:
            return None
        if len(path) == 1:
            node = self.get_node(path[0])
            return f"{node.label} (same node)"
        parts = []
        for i in range(len(path) - 1):
            node = self.get_node(path[i])
            next_node = self.get_node(path[i + 1])
            edge = self.conn.execute(
                "SELECT relation FROM edges WHERE source=? AND target=? "
                "ORDER BY weight DESC LIMIT 1",
                (path[i], path[i + 1]),
            ).fetchone()
            relation = edge["relation"] if edge else "→"
            parts.append(f"{node.label} --[{relation}]--> {next_node.label}")
        return "\n".join(parts)

    # ── Q-Value Utility Scoring (MemRL-inspired) ───────────────────

    def memory_qvalue(self, node_id: str,
                      alpha: float = 0.1,
                      gamma: float = 0.9) -> dict | None:
        """Compute Q-value utility score for a memory node.

        Inspired by MemRL (arXiv:2601.03192): memory management as a
        learning problem.  Each node gets a Q-value reflecting its
        demonstrated utility — how often it's accessed, how well
        connected it is, and whether neighbors are also high-value.

        Q(s) = α * immediate_reward + γ * max_neighbor_Q

        immediate_reward = access_frequency_norm * 0.4
                         + degree_norm * 0.3
                         + weight_norm * 0.3

        This is a single-pass approximation (not iterative Bellman) —
        fast enough for real-time query routing.

        Args:
            node_id: target node
            alpha: learning rate / immediate reward weight
            gamma: discount factor for neighbor propagation

        Returns:
            {qvalue, components, neighbors_checked} or None if not found
        """
        node = self.get_node(node_id)
        if not node:
            return None

        stats = self.stats()
        edge_count = stats.get("edges", 0)
        node_count = stats.get("nodes", 1)
        max_degree = max(2.0 * edge_count / max(node_count, 1), 1.0)

        # Access frequency: how many times touched vs created
        access_count = node.data.get("_access_count", 0)
        age_days = max((time.time() - node.created) / 86400.0, 0.01)
        access_freq = access_count / age_days if age_days > 0 else 0
        access_norm = min(access_freq / 10.0, 1.0)  # cap at 10/day

        # Degree normalisation
        degree = len(self.neighbors(node_id))
        degree_norm = degree / max_degree

        # Weight normalisation (0..1)
        weight_norm = max(0.0, min(1.0, node.weight))

        immediate = (access_norm * 0.4 + degree_norm * 0.3 + weight_norm * 0.3)

        # Neighbor Q: average weight of immediate neighbors as proxy
        nbrs = self.neighbors(node_id)
        neighbor_q = 0.0
        if nbrs:
            total_w = sum(
                self.get_node(n.id).weight for n in nbrs
                if self.get_node(n.id)
            )
            neighbor_q = total_w / len(nbrs)

        qvalue = alpha * immediate + gamma * neighbor_q

        return {
            "qvalue": round(qvalue, 4),
            "components": {
                "access": round(access_norm, 4),
                "degree": round(degree_norm, 4),
                "weight": round(weight_norm, 4),
                "immediate": round(immediate, 4),
                "neighbor_avg_weight": round(neighbor_q, 4),
            },
            "neighbors_checked": len(nbrs),
            "alpha": alpha,
            "gamma": gamma,
        }

    def memory_qvalue_batch(self, top_n: int = 20,
                            alpha: float = 0.1,
                            gamma: float = 0.9) -> list[dict]:
        """Compute Q-values for all nodes and return top-N ranked.

        Useful for: deciding which memories to keep active, which to
        consolidate, and which to evict.  Nodes with Q < 0.05 are
        candidates for eviction.

        Returns:
            List of {node_id, label, kind, qvalue, components} sorted desc
        """
        rows = self.conn.execute(
            "SELECT id FROM nodes ORDER BY weight DESC"
        ).fetchall()

        results = []
        for r in rows:
            q = self.memory_qvalue(r["id"], alpha, gamma)
            if q:
                node = self.get_node(r["id"])
                results.append({
                    "node_id": r["id"],
                    "label": node.label,
                    "kind": node.kind,
                    **q,
                })

        results.sort(key=lambda x: x["qvalue"], reverse=True)
        return results[:top_n]

    # ── Drift Detection (SSGM-inspired) ────────────────────────────

    def memory_drift_detect(self, node_id: str,
                            semantic: bool = True,
                            structural: bool = True,
                            temporal: bool = True) -> dict | None:
        """Detect multi-dimensional drift for a memory node.

        Inspired by SSGM (arXiv:2603.11768) drift taxonomy:
        - **Semantic drift**: node label/data diverges from neighbors
        - **Structural drift**: degree or connectivity pattern changed
        - **Temporal drift**: node hasn't been accessed recently

        Each dimension returns a 0..1 score (0 = stable, 1 = heavily
        drifted).  Overall drift = max of dimensions (worst case).

        Returns:
            {semantic, structural, temporal, overall, recommendation}
            or None if node not found
        """
        node = self.get_node(node_id)
        if not node:
            return None

        results = {}

        if semantic:
            # Use semantic_divergence if available
            div = self.semantic_divergence(node_id)
            if div:
                results["semantic"] = round(div.get("divergence_score", 0.0), 4)
            else:
                results["semantic"] = 0.0
        else:
            results["semantic"] = 0.0

        if structural:
            # Compare node degree to graph average
            edge_count = self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            node_count = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            avg_degree = (2.0 * edge_count / node_count) if node_count > 0 else 0.0
            node_degree = len(self.neighbors(node_id))
            if avg_degree > 0:
                # If node has much fewer/more edges than average → drift
                ratio = abs(node_degree - avg_degree) / max(avg_degree, 1.0)
                results["structural"] = round(min(ratio, 1.0), 4)
            else:
                results["structural"] = 0.0
        else:
            results["structural"] = 0.0

        if temporal:
            # Days since last access
            days_since = (time.time() - node.accessed) / 86400.0
            # 30+ days = max temporal drift
            results["temporal"] = round(min(days_since / 30.0, 1.0), 4)
        else:
            results["temporal"] = 0.0

        overall = max(results.values())

        # Recommendation based on dominant drift dimension
        if overall < 0.2:
            recommendation = "stable"
        elif overall < 0.5:
            dom = max(results, key=results.get)
            recommendation = f"minor_{dom}_drift"
        elif overall < 0.8:
            dom = max(results, key=results.get)
            recommendation = f"review_{dom}_drift"
        else:
            dom = max(results, key=results.get)
            recommendation = f"action_{dom}_drift"

        results["overall"] = round(overall, 4)
        results["recommendation"] = recommendation
        results["node_id"] = node_id
        return results

    def memory_drift_scan(self, threshold: float = 0.5,
                          kinds: list[str] | None = None) -> list[dict]:
        """Scan all nodes for drift, return those above threshold.

        Args:
            threshold: minimum overall drift score (0..1)
            kinds: filter to specific node kinds

        Returns:
            List of drift reports sorted by overall desc
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        drifted = []
        for r in rows:
            if kinds:
                node = self.get_node(r["id"])
                if not node or node.kind not in kinds:
                    continue
            report = self.memory_drift_detect(r["id"])
            if report and report["overall"] >= threshold:
                drifted.append(report)

        drifted.sort(key=lambda x: x["overall"], reverse=True)
        return drifted

    # ── Skill Discovery (EvoSkill/SAGE-inspired) ───────────────────

    def discover_skills(self, min_frequency: int = 2,
                        min_success_rate: float = 0.5) -> list[dict]:
        """Discover reusable skill candidates from workflow memory.

        Inspired by EvoSkill (arXiv:2603.02766) failure-driven discovery
        and SAGE (arXiv:2512.17102) sequential rollout.  This method:

        1. Mines common action sequences from successful workflows
        2. Identifies actions that co-occur frequently (skill candidates)
        3. Checks if those actions appear in failed workflows (failure signal)
        4. Ranks by Pareto retention: frequency * (1 - failure_contamination)

        Unlike workflow_success_patterns which just counts individual actions,
        this finds **paired action sequences** — the building blocks of skills.

        Returns:
            List of {action_pair, frequency, success_workflows,
                     failure_workflows, pareto_score} sorted desc.
        """
        # Get successful workflows
        workflows = self.conn.execute(
            "SELECT id, data FROM nodes WHERE kind='workflow'"
        ).fetchall()

        success_seqs: dict[str, list[str]] = {}  # wf_id → ordered actions
        failure_seqs: dict[str, list[str]] = {}

        for r in workflows:
            data = json.loads(r["data"])
            s = data.get("success_count", 0)
            f = data.get("failure_count", 0)
            total = s + f
            if total == 0:
                continue

            steps = self.conn.execute(
                "SELECT target FROM edges WHERE source=? AND relation='has_step'",
                (r["id"],),
            ).fetchall()

            actions = []
            for step_row in steps:
                step_node = self.get_node(step_row["target"])
                if step_node:
                    sd = step_node.data if isinstance(step_node.data, dict) else json.loads(step_node.data)
                    actions.append(sd.get("action", step_node.label))

            if s > f:
                success_seqs[r["id"]] = actions
            elif f > s:
                failure_seqs[r["id"]] = actions

        # Find co-occurring action pairs in success sequences
        pair_stats: dict[tuple[str, str], dict] = {}
        for wf_id, actions in success_seqs.items():
            seen_pairs = set()
            for i in range(len(actions) - 1):
                for j in range(i + 1, len(actions)):
                    pair = tuple(sorted((actions[i], actions[j])))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        if pair not in pair_stats:
                            pair_stats[pair] = {
                                "action_pair": list(pair),
                                "frequency": 0,
                                "success_workflows": [],
                                "failure_workflows": [],
                            }
                        pair_stats[pair]["frequency"] += 1
                        pair_stats[pair]["success_workflows"].append(wf_id)

        # Check contamination in failure sequences
        for wf_id, actions in failure_seqs.items():
            action_set = set(actions)
            for pair, info in pair_stats.items():
                if pair[0] in action_set and pair[1] in action_set:
                    info["failure_workflows"].append(wf_id)

        # Pareto scoring: frequency * (1 - failure_contamination)
        results = []
        for pair, info in pair_stats.items():
            if info["frequency"] < min_frequency:
                continue
            sf = len(info["success_workflows"])
            ff = len(info["failure_workflows"])
            rate = sf / (sf + ff) if (sf + ff) > 0 else 0.0
            if rate < min_success_rate:
                continue
            pareto = info["frequency"] * (1.0 - ff / max(sf + ff, 1))
            results.append({
                "action_pair": info["action_pair"],
                "frequency": info["frequency"],
                "success_workflows": sf,
                "failure_workflows": ff,
                "success_rate": round(rate, 4),
                "pareto_score": round(pareto, 4),
            })

        results.sort(key=lambda x: x["pareto_score"], reverse=True)
        return results

    # ── Memory Utilization Report ──────────────────────────────────

    def memory_utilization_report(self) -> dict:
        """Executive summary of memory store health and usage.

        Combines Q-value distribution, drift scan, workflow coverage,
        and kind distribution into a single dashboard report.

        Returns:
            {total_nodes, by_kind, avg_qvalue, top_qvalue_nodes,
             drifted_nodes, workflow_coverage, recommendations}
        """
        stats = self.stats()
        total = stats.get("nodes", 0)

        if total == 0:
            return {
                "total_nodes": 0,
                "by_kind": {},
                "avg_qvalue": 0.0,
                "top_qvalue_nodes": [],
                "drifted_nodes": [],
                "workflow_coverage": 0.0,
                "recommendations": ["empty_store"],
            }

        # Kind distribution
        by_kind = stats.get("by_kind", {})

        # Q-value stats (sample up to 50 for speed)
        q_batch = self.memory_qvalue_batch(top_n=50)
        q_values = [q["qvalue"] for q in q_batch]
        avg_q = sum(q_values) / len(q_values) if q_values else 0.0

        # Drift scan (threshold 0.5)
        drifted = self.memory_drift_scan(threshold=0.5)

        # Workflow coverage
        wf_stats = self.workflow_stats()
        wf_coverage = wf_stats.get("coverage", 0.0)

        # Build recommendations
        recs = []
        if avg_q < 0.1:
            recs.append("low_utilization")
        if len(drifted) > total * 0.3:
            recs.append("high_drift_ratio")
        if wf_coverage < 0.3:
            recs.append("low_workflow_coverage")
        if not recs:
            recs.append("healthy")

        return {
            "total_nodes": total,
            "by_kind": by_kind,
            "avg_qvalue": round(avg_q, 4),
            "top_qvalue_nodes": [
                {"label": q["label"], "qvalue": q["qvalue"]}
                for q in q_batch[:5]
            ],
            "drifted_count": len(drifted),
            "workflow_coverage": round(wf_coverage, 4),
            "recommendations": recs,
        }

    # ── Memory Reinforcement (MemRL operational) ───────────────────

    def memory_reinforce(self, node_id: str, outcome: str,
                         boost: float = 0.1) -> dict | None:
        """Reinforce a memory node based on observed outcome.

        Operationalises the MemRL insight: memory management is a learning
        problem.  Each outcome adjusts the node's weight, simulating
        Q-value updates without a full RL training loop.

        - "positive": weight += boost (capped at 1.0)
        - "negative": weight -= boost (floored at 0.01)
        - "neutral":  weight unchanged, but touch (update accessed)

        Records the reinforcement event in node metadata for auditability.

        Args:
            node_id: target node
            outcome: "positive" | "negative" | "neutral"
            boost: weight delta (default 0.1)

        Returns:
            {node_id, outcome, old_weight, new_weight, boost} or None
        """
        node = self.get_node(node_id)
        if not node:
            return None

        old_weight = node.weight

        if outcome == "positive":
            new_weight = min(1.0, old_weight + boost)
        elif outcome == "negative":
            new_weight = max(0.01, old_weight - boost)
        elif outcome == "neutral":
            new_weight = old_weight
        else:
            return None

        # Update weight, accessed time, and record event
        now = time.time()
        data = node.data if isinstance(node.data, dict) else json.loads(node.data)
        history = data.setdefault("_reinforcement_history", [])
        history.append({
            "outcome": outcome,
            "boost": boost,
            "old_weight": round(old_weight, 4),
            "new_weight": round(new_weight, 4),
            "timestamp": now,
        })
        # Keep only last 50 events
        if len(history) > 50:
            data["_reinforcement_history"] = history[-50:]

        self.conn.execute(
            "UPDATE nodes SET weight=?, accessed=?, data=? WHERE id=?",
            (new_weight, now, json.dumps(data), node_id),
        )
        self.conn.commit()

        return {
            "node_id": node_id,
            "outcome": outcome,
            "old_weight": round(old_weight, 4),
            "new_weight": round(new_weight, 4),
            "boost": boost,
        }

    def skill_gap_analysis(self, min_failures: int = 1) -> list[dict]:
        """Identify missing skills from failed workflow patterns.

        Insight from EvoSkill (arXiv:2603.02766): failures reveal which
        action transitions are missing.  If workflow A fails and workflow
        B succeeds, and A has steps [x, z] while B has [x, y, z], then
        action 'y' is a **skill gap** — a missing intermediate step.

        This method compares failed workflows to successful ones with
        overlapping actions, and identifies intermediate actions present
        in successes but absent in failures.

        Returns:
            List of {missing_action, in_workflows, failed_workflows,
                     gap_severity} sorted by gap_severity desc
        """
        workflows = self.conn.execute(
            "SELECT id, data FROM nodes WHERE kind='workflow'"
        ).fetchall()

        success_actions: dict[str, set[str]] = {}
        failure_actions: dict[str, set[str]] = {}

        for r in workflows:
            data = json.loads(r["data"])
            s = data.get("success_count", 0)
            f = data.get("failure_count", 0)
            total = s + f
            if total == 0:
                continue

            steps = self.conn.execute(
                "SELECT target FROM edges WHERE source=? AND relation='has_step'",
                (r["id"],),
            ).fetchall()

            actions = set()
            for step_row in steps:
                step_node = self.get_node(step_row["target"])
                if step_node:
                    sd = step_node.data if isinstance(step_node.data, dict) else json.loads(step_node.data)
                    actions.add(sd.get("action", step_node.label))

            if s > f:
                success_actions[r["id"]] = actions
            elif f >= min_failures:
                failure_actions[r["id"]] = actions

        # For each failure, find overlapping successes and identify missing
        gap_map: dict[str, dict] = {}
        for fail_id, fail_acts in failure_actions.items():
            for succ_id, succ_acts in success_actions.items():
                overlap = fail_acts & succ_acts
                if len(overlap) < 1:
                    continue
                missing = succ_acts - fail_acts
                for action in missing:
                    if action not in gap_map:
                        gap_map[action] = {
                            "missing_action": action,
                            "in_workflows": [],
                            "failed_workflows": [],
                            "gap_severity": 0,
                        }
                    gap_map[action]["in_workflows"].append(succ_id)
                    gap_map[action]["failed_workflows"].append(fail_id)

        # Severity = how many distinct failures would benefit
        results = []
        for action, info in gap_map.items():
            unique_failures = len(set(info["failed_workflows"]))
            unique_successes = len(set(info["in_workflows"]))
            info["in_workflows"] = unique_successes
            info["failed_workflows"] = unique_failures
            info["gap_severity"] = unique_failures * unique_successes
            results.append(info)

        results.sort(key=lambda x: x["gap_severity"], reverse=True)
        return results

    # ── Memory Attention Score ─────────────────────────────────────

    def memory_attention_score(self, node_id: str,
                               recency_window_hours: float = 24.0) -> dict | None:
        """Compute attention score — how "hot" a node is right now.

        Combines recent reinforcement events, access recency, and
        neighbor activity into a single 0..1 score.  Unlike Q-value
        (which is structural), attention is temporal — it decays.

        Attention = recency_boost * 0.4
                  + reinforcement_velocity * 0.4
                  + neighbor_activity * 0.2

        Use cases: prioritise which memories to surface in context,
        identify trending topics, detect attention sinkholes.

        Returns:
            {attention, recency_boost, reinforcement_velocity,
             neighbor_activity, recent_events} or None
        """
        node = self.get_node(node_id)
        if not node:
            return None

        now = time.time()
        window_sec = recency_window_hours * 3600

        # Recency boost: how recently was this node accessed?
        age_sec = now - node.accessed
        recency_boost = max(0.0, 1.0 - age_sec / window_sec)

        # Reinforcement velocity: rate of recent positive/negative events
        data = node.data if isinstance(node.data, dict) else json.loads(node.data)
        history = data.get("_reinforcement_history", [])
        recent_events = [
            e for e in history
            if (now - e.get("timestamp", 0)) < window_sec
        ]
        max_possible = 10  # normalize: 10 events in window = velocity 1.0
        reinforcement_velocity = min(len(recent_events) / max_possible, 1.0)

        # Neighbor activity: average recency of neighbor access
        nbrs = self.neighbors(node_id)
        if nbrs:
            neighbor_recencies = []
            for n in nbrs:
                n_age = now - n.accessed
                neighbor_recencies.append(max(0.0, 1.0 - n_age / window_sec))
            neighbor_activity = sum(neighbor_recencies) / len(neighbor_recencies)
        else:
            neighbor_activity = 0.0

        attention = (
            recency_boost * 0.4
            + reinforcement_velocity * 0.4
            + neighbor_activity * 0.2
        )

        return {
            "attention": round(attention, 4),
            "recency_boost": round(recency_boost, 4),
            "reinforcement_velocity": round(reinforcement_velocity, 4),
            "neighbor_activity": round(neighbor_activity, 4),
            "recent_events": len(recent_events),
        }

    def consolidation_priority(self, limit: int = 20) -> list[dict]:
        """Rank nodes by consolidation urgency.

        Combines drift score, Q-value, and attention into a priority
        ranking.  High-priority nodes are those that are:
        - Drifting (semantic/structural/temporal)
        - Low Q-value (low demonstrated utility)
        - Low attention (not recently active)

        These are prime candidates for: consolidation, archival, or eviction.

        Returns:
            List of {node_id, label, priority, drift, qvalue, attention}
            sorted by priority descending
        """
        rows = self.conn.execute("SELECT id FROM nodes").fetchall()

        results = []
        for r in rows:
            node = self.get_node(r["id"])
            if not node:
                continue

            drift = self.memory_drift_detect(r["id"])
            q = self.memory_qvalue(r["id"])
            att = self.memory_attention_score(r["id"])

            if not (drift and q and att):
                continue

            # Priority = drift * (1 - qvalue) * (1 - attention)
            # High drift + low Q + low attention = high priority
            priority = (
                drift["overall"]
                * (1.0 - q["qvalue"])
                * (1.0 - att["attention"])
            )

            results.append({
                "node_id": r["id"],
                "label": node.label,
                "kind": node.kind,
                "priority": round(priority, 4),
                "drift": drift["overall"],
                "qvalue": q["qvalue"],
                "attention": att["attention"],
                "recommendation": drift["recommendation"],
            })

        results.sort(key=lambda x: x["priority"], reverse=True)
        return results[:limit]

    # ── Bi-Temporal Validity Tracking ──────────────────────────────
    #
    # Inspired by Temporal Knowledge Graphs (T-KG) research.
    # Every edge can have a validity window [valid_from, valid_until].
    # Invalidated edges record *who* invalidated them and *when*.
    # This enables time-travel queries: "what was true at time T?"
    #
    # Storage: leverages the existing edge_props JSON column — zero
    # schema migration required.

    def edge_set_validity(self, source_id: str, target_id: str,
                          relation: str, valid_from: float = None,
                          valid_until: float = None) -> dict | None:
        """Set bi-temporal validity window on an edge.

        Args:
            valid_from:  Unix timestamp from which the edge is valid.
                         Default: now (edge creation time).
            valid_until: Unix timestamp after which the edge is invalid.
                         None means open-ended (still valid).

        Returns the stored validity dict, or None if edge doesn't exist.
        """
        edge = self.get_edge(source_id, target_id, relation)
        if not edge:
            return None
        now = time.time()
        props = self.edge_properties(source_id, target_id, relation) or {}
        props["_temporal"] = {
            "valid_from": valid_from if valid_from is not None else now,
            "valid_until": valid_until,          # None = open-ended
            "invalidated_by": props.get("_temporal", {}).get("invalidated_by"),
            "set_at": now,
        }
        self.set_edge_properties(source_id, target_id, relation, props)
        self.conn.commit()
        return props["_temporal"]

    def edge_invalidate(self, source_id: str, target_id: str,
                        relation: str, invalidated_by: str = None) -> dict | None:
        """Mark an edge as no longer valid.

        Sets valid_until to now and records who invalidated it.
        Idempotent — calling twice is a no-op.

        Args:
            invalidated_by: Identifier (node id or label) of the agent
                            or process that caused invalidation.

        Returns the updated validity dict, or None if edge doesn't exist.
        """
        edge = self.get_edge(source_id, target_id, relation)
        if not edge:
            return None
        now = time.time()
        props = self.edge_properties(source_id, target_id, relation) or {}
        existing = props.get("_temporal", {})
        if existing.get("valid_until") is not None:
            return existing  # already invalidated — idempotent
        props["_temporal"] = {
            "valid_from": existing.get("valid_from", now),
            "valid_until": now,
            "invalidated_by": invalidated_by,
            "set_at": now,
        }
        self.set_edge_properties(source_id, target_id, relation, props)
        self.conn.commit()
        return props["_temporal"]

    def edge_valid_at(self, source_id: str, target_id: str,
                      relation: str, timestamp: float = None) -> bool:
        """Check whether an edge was valid at the given time.

        An edge is valid at *timestamp* if:
        - The edge exists.
        - valid_from <= timestamp (or no temporal info → always valid).
        - valid_until is None or valid_until > timestamp.

        Default timestamp: now.
        """
        edge = self.get_edge(source_id, target_id, relation)
        if not edge:
            return False
        ts = timestamp if timestamp is not None else time.time()
        props = self.edge_properties(source_id, target_id, relation) or {}
        temporal = props.get("_temporal")
        if not temporal:
            return True  # no temporal constraint → always valid
        if temporal["valid_from"] > ts:
            return False
        vu = temporal.get("valid_until")
        if vu is not None and vu <= ts:
            return False
        return True

    def temporal_snapshot(self, timestamp: float = None) -> list[Edge]:
        """Return all edges valid at the given timestamp.

        Useful for time-travel queries: "what did the graph look like
        at time T?"  Edges without temporal info are always included.

        Returns a list of Edge namedtuples.
        """
        ts = timestamp if timestamp is not None else time.time()
        rows = self.conn.execute(
            "SELECT source, target, relation, weight FROM edges"
        ).fetchall()
        result = []
        for r in rows:
            props = self.edge_properties(r["source"], r["target"], r["relation"])
            temporal = (props or {}).get("_temporal")
            if not temporal:
                result.append(Edge(r["source"], r["target"], r["relation"], r["weight"]))
                continue
            if temporal["valid_from"] <= ts:
                vu = temporal.get("valid_until")
                if vu is None or vu > ts:
                    result.append(Edge(r["source"], r["target"], r["relation"], r["weight"]))
        return result

    def edge_temporal_history(self, node_id: str,
                              direction: str = "both") -> list[dict]:
        """Return temporal history of edges connected to a node.

        Each entry includes the edge triple, validity window, and
        invalidation info (if any).  Sorted by valid_from descending.

        direction: 'outgoing', 'incoming', or 'both'.
        """
        edges = self.edges_of(node_id, direction=direction)
        history = []
        for e in edges:
            props = self.edge_properties(e.source, e.target, e.relation)
            temporal = (props or {}).get("_temporal")
            if temporal:
                history.append({
                    "source": e.source,
                    "target": e.target,
                    "relation": e.relation,
                    "valid_from": temporal["valid_from"],
                    "valid_until": temporal.get("valid_until"),
                    "invalidated_by": temporal.get("invalidated_by"),
                    "status": "invalidated" if temporal.get("valid_until") is not None else "valid",
                })
        history.sort(key=lambda x: x["valid_from"], reverse=True)
        return history

    # ── Node-Level Bi-Temporal Validity ───────────────────────
    #
    # Extends bi-temporal tracking from edges to nodes.  Enables:
    #   - "This fact was true from 2024-01-01 to 2024-06-30"
    #   - "Show me all concepts that were valid at time T"
    #   - "Invalidate this node — it's no longer accurate"
    #
    # Storage: node.data['_node_temporal'] — zero schema migration.

    def node_set_validity(self, node_id: str,
                          valid_from: float = None,
                          valid_until: float = None) -> dict | None:
        """Set bi-temporal validity window on a node.

        Args:
            valid_from: Unix timestamp from which the node's content is
                        valid.  Default: node creation time.
            valid_until: Unix timestamp after which the node is invalid.
                         None means open-ended (currently valid).

        Returns the stored validity dict, or None if node doesn't exist.
        """
        node = self.get_node(node_id)
        if not node:
            return None
        now = time.time()
        data = node.data if isinstance(node.data, dict) else json.loads(node.data)
        existing = data.get("_node_temporal", {})
        data["_node_temporal"] = {
            "valid_from": valid_from if valid_from is not None else existing.get("valid_from", node.created),
            "valid_until": valid_until if valid_until is not None else existing.get("valid_until"),
            "invalidated_by": existing.get("invalidated_by"),
            "set_at": now,
        }
        self.conn.execute(
            "UPDATE nodes SET data=? WHERE id=?",
            (json.dumps(data), node_id))
        self.conn.commit()
        return data["_node_temporal"]

    def node_invalidate(self, node_id: str,
                        invalidated_by: str = None) -> dict | None:
        """Mark a node as no longer valid.

        Sets valid_until to now and records who invalidated it.
        Idempotent — calling twice is a no-op.

        Args:
            invalidated_by: Identifier (agent id or label) of the
                            process that caused invalidation.

        Returns the updated validity dict, or None if node doesn't exist.
        """
        node = self.get_node(node_id)
        if not node:
            return None
        now = time.time()
        data = node.data if isinstance(node.data, dict) else json.loads(node.data)
        existing = data.get("_node_temporal", {})
        if existing.get("valid_until") is not None:
            return existing  # already invalidated — idempotent
        data["_node_temporal"] = {
            "valid_from": existing.get("valid_from", node.created),
            "valid_until": now,
            "invalidated_by": invalidated_by,
            "set_at": now,
        }
        self.conn.execute(
            "UPDATE nodes SET data=? WHERE id=?",
            (json.dumps(data), node_id))
        self.conn.commit()
        return data["_node_temporal"]

    def node_valid_at(self, node_id: str,
                      timestamp: float = None) -> bool:
        """Check whether a node was valid at the given time.

        A node is valid at *timestamp* if:
        - The node exists.
        - valid_from <= timestamp (or no temporal info → always valid).
        - valid_until is None or valid_until > timestamp.

        Default timestamp: now.
        """
        node = self.get_node(node_id)
        if not node:
            return False
        ts = timestamp if timestamp is not None else time.time()
        data = node.data if isinstance(node.data, dict) else json.loads(node.data)
        temporal = data.get("_node_temporal")
        if not temporal:
            return True  # no temporal constraint → always valid
        if temporal["valid_from"] > ts:
            return False
        vu = temporal.get("valid_until")
        if vu is not None and vu <= ts:
            return False
        return True

    def temporal_graph_snapshot(self, timestamp: float = None) -> dict:
        """Return the full graph state (nodes + edges) valid at *timestamp*.

        Combines node-level and edge-level bi-temporal filtering.
        Nodes/edges without temporal info are always included.

        Returns:
            {timestamp, nodes: [...], edges: [...], stats: {nodes, edges}}
        """
        ts = timestamp if timestamp is not None else time.time()

        # Filter nodes
        valid_nodes = []
        for row in self.conn.execute("SELECT id FROM nodes").fetchall():
            if self.node_valid_at(row["id"], ts):
                node = self.get_node(row["id"])
                valid_nodes.append({
                    "id": node.id,
                    "label": node.label,
                    "kind": node.kind,
                    "weight": round(node.weight, 4),
                })

        # Filter edges using edge_valid_at
        valid_edges = []
        for row in self.conn.execute(
            "SELECT source, target, relation FROM edges"
        ).fetchall():
            if self.edge_valid_at(row["source"], row["target"], row["relation"], ts):
                valid_edges.append({
                    "source": row["source"],
                    "target": row["target"],
                    "relation": row["relation"],
                })

        return {
            "timestamp": ts,
            "nodes": valid_nodes,
            "edges": valid_edges,
            "stats": {
                "nodes": len(valid_nodes),
                "edges": len(valid_edges),
            },
        }

    # ── OWASP ASI06: Provenance & Quarantine ──────────────────

    def node_set_provenance(self, node_id: str, source: str = None,
                            trust_level: float = None,
                            parents: list[str] = None) -> bool:
        """Set provenance metadata on a node (OWASP ASI06 defense).

        Tracks WHERE a memory came from (source), HOW MUCH to trust it
        (trust_level 0-1), and WHICH nodes derived it (parents).
        Enables quarantine of untrusted/contaminated memory chains.
        """
        node = self.get_node(node_id)
        if not node:
            return False
        updates, params = [], []
        if source is not None:
            updates.append("source = ?")
            params.append(source)
        if trust_level is not None:
            updates.append("trust_level = ?")
            params.append(max(0.0, min(1.0, trust_level)))
        if parents is not None:
            updates.append("parents = ?")
            params.append(json.dumps(parents))
        if not updates:
            return False
        params.append(node_id)
        self.conn.execute(f"UPDATE nodes SET {', '.join(updates)} WHERE id = ?", params)
        self.conn.commit()
        return True

    def node_quarantine(self, node_id: str, reason: str = "") -> bool:
        """Quarantine a node — excluded from retrieval (recall/search/neighbors).

        Use when a memory is suspected of being contaminated, adversarial,
        or otherwise untrustworthy (OWASP ASI06).
        """
        node = self.get_node(node_id)
        if not node:
            return False
        self.conn.execute(
            "UPDATE nodes SET quarantined = 1, quarantine_reason = ? WHERE id = ?",
            (reason or "unspecified", node_id)
        )
        self.conn.commit()
        return True

    def node_unquarantine(self, node_id: str) -> bool:
        """Release a node from quarantine."""
        node = self.get_node(node_id)
        if not node:
            return False
        self.conn.execute(
            "UPDATE nodes SET quarantined = 0, quarantine_reason = NULL WHERE id = ?",
            (node_id,)
        )
        self.conn.commit()
        return True

    def quarantine_list(self) -> list[dict]:
        """List all quarantined nodes with reasons."""
        rows = self.conn.execute(
            "SELECT id, label, kind, trust_level, source, quarantine_reason "
            "FROM nodes WHERE quarantined = 1 ORDER BY label"
        ).fetchall()
        return [dict(r) for r in rows]

    def quarantine_scan(self, trust_threshold: float = 0.3) -> list[str]:
        """Auto-quarantine nodes with trust_level below threshold.

        Returns list of newly quarantined node IDs.
        """
        rows = self.conn.execute(
            "SELECT id FROM nodes WHERE quarantined = 0 AND trust_level < ?",
            (trust_threshold,)
        ).fetchall()
        quarantined_ids = []
        for r in rows:
            self.conn.execute(
                "UPDATE nodes SET quarantined = 1, quarantine_reason = ? WHERE id = ?",
                (f"auto: trust_level below {trust_threshold}", r["id"])
            )
            quarantined_ids.append(r["id"])
        self.conn.commit()
        return quarantined_ids

    # ── Graph Reasoning APIs (HopRAG / GR-Agent / GNN-RAG inspired) ────────

    def reasoning_path(self, seed_id: str, target_id: str,
                        max_hops: int = 3, strategy: str = "shortest",
                        top_k: int = 5) -> list[dict]:
        """带分数的推理路径 (Retrieve-Reason-Prune 范式).

        策略:
        - shortest: BFS 最短路径 (精确)
        - pagerank_guided: 经过高 PageRank 中间节点
        - random_walk: 多样化随机游走路径

        返回 [{path, edges, score, explanation, source}, ...]
        """
        if not self.has_node(seed_id) or not self.has_node(target_id):
            return []
        if seed_id == target_id:
            return [{"path": [seed_id], "edges": [], "score": 1.0,
                     "explanation": "seed and target are the same node",
                     "source": "trivial"}]
        results = []

        def _edge_label(s, t):
            r = self.conn.execute(
                "SELECT relation FROM edges WHERE source=? AND target=? ORDER BY weight DESC LIMIT 1",
                (s, t)).fetchone()
            if r:
                return r["relation"]
            r = self.conn.execute(
                "SELECT relation FROM edges WHERE source=? AND target=? ORDER BY weight DESC LIMIT 1",
                (t, s)).fetchone()
            return r["relation"] if r else "related"

        def _verbalize(path):
            parts = []
            for i in range(len(path) - 1):
                lbl = _edge_label(path[i], path[i + 1])
                n1 = self.conn.execute("SELECT label FROM nodes WHERE id=?", (path[i],)).fetchone()
                n2 = self.conn.execute("SELECT label FROM nodes WHERE id=?", (path[i + 1],)).fetchone()
                l1 = n1["label"] if n1 else path[i]
                l2 = n2["label"] if n2 else path[i + 1]
                parts.append(f"{l1} —({lbl})→ {l2}")
            return "; ".join(parts)

        if strategy in ("shortest", "auto"):
            sp = self.bfs_shortest_path(seed_id, target_id)
            if sp and len(sp) <= max_hops + 1:
                edges = [_edge_label(sp[i], sp[i + 1]) for i in range(len(sp) - 1)]
                results.append({
                    "path": sp,
                    "edges": edges,
                    "score": round(1.0 / len(sp), 4),
                    "explanation": _verbalize(sp),
                    "source": "shortest",
                })

        if strategy == "pagerank_guided" or (strategy == "shortest" and not results):
            pr = self.pagerank(max_iter=20)
            max_pr = max(pr.values()) if pr else 1.0
            all_paths = self.find_paths(seed_id, target_id, max_hops)
            scored = []
            for p in all_paths[:top_k * 3]:
                mid_pr = sum(pr.get(nid, 0) for nid in p[1:-1]) / max(1, len(p) - 2)
                edges = [_edge_label(p[i], p[i + 1]) for i in range(len(p) - 1)]
                path_score = (mid_pr / max_pr) * 0.5 + (1.0 / len(p)) * 0.5
                scored.append({
                    "path": p,
                    "edges": edges,
                    "score": round(path_score, 4),
                    "explanation": _verbalize(p),
                    "source": "pagerank_guided",
                })
            scored.sort(key=lambda x: x["score"], reverse=True)
            results.extend(scored[:top_k])

        if strategy == "random_walk":
            import random as _rng
            for _ in range(top_k * 2):
                current = seed_id
                path = [seed_id]
                visited = {seed_id}
                for _hop in range(max_hops):
                    nbrs = self.conn.execute(
                        "SELECT target FROM edges WHERE source=? AND target NOT IN ({})"
                        .format(",".join("?" * len(visited))),
                        [current] + list(visited)).fetchall()
                    rev_nbrs = self.conn.execute(
                        "SELECT source FROM edges WHERE target=? AND source NOT IN ({})"
                        .format(",".join("?" * len(visited))),
                        [current] + list(visited)).fetchall()
                    candidates = [r[0] for r in nbrs] + [r[0] for r in rev_nbrs]
                    if not candidates:
                        break
                    nxt = _rng.choice(candidates)
                    path.append(nxt)
                    visited.add(nxt)
                    if nxt == target_id:
                        break
                    current = nxt
                if path[-1] == target_id:
                    edges = [_edge_label(path[i], path[i + 1]) for i in range(len(path) - 1)]
                    results.append({
                        "path": path,
                        "edges": edges,
                        "score": round(1.0 / len(path), 4),
                        "explanation": _verbalize(path),
                        "source": "random_walk",
                    })
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]

        # Deduplicate by path tuple
        seen = set()
        unique = []
        for r in results:
            key = tuple(r["path"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique[:top_k]

    def explore(self, seed_id: str, max_hops: int = 2, budget: int = 50,
                direction: str = "both", min_score: float = 0.1) -> dict:
        """自适应图探索 (GR-Agent agent-environment 交互模式).

        从 seed 出发, 受预算约束地探索邻域, 返回发现的节点+推理路径+统计.
        """
        if not self.has_node(seed_id):
            return {"discovered": [], "paths": [],
                    "stats": {"nodes_visited": 0, "edges_traversed": 0,
                              "hops_completed": 0, "budget_used": 0.0}}

        pr = self.pagerank(max_iter=15)
        max_pr = max(pr.values()) if pr else 1.0

        visited = {seed_id}
        queue = [(seed_id, 0, 1.0)]
        discovered = []
        paths = []
        edges_traversed = 0

        def _edge_info(s, t):
            r = self.conn.execute(
                "SELECT relation, weight FROM edges WHERE source=? AND target=? ORDER BY weight DESC LIMIT 1",
                (s, t)).fetchone()
            if r:
                return r["relation"], r["weight"]
            r = self.conn.execute(
                "SELECT relation, weight FROM edges WHERE source=? AND target=? ORDER BY weight DESC LIMIT 1",
                (t, s)).fetchone()
            if r:
                return r["relation"], r["weight"]
            return "related", 1.0

        def _trace_back(src, intermediate):
            sp = self.bfs_shortest_path(src, intermediate)
            return sp or [src, intermediate]

        while queue and len(visited) < budget:
            current, depth, _score = queue.pop(0)
            if depth >= max_hops:
                continue

            if direction == "out":
                nbr_rows = self.conn.execute(
                    "SELECT target AS nb FROM edges WHERE source=?", (current,)).fetchall()
            elif direction == "in":
                nbr_rows = self.conn.execute(
                    "SELECT source AS nb FROM edges WHERE target=?", (current,)).fetchall()
            else:
                nbr_rows = self.conn.execute(
                    "SELECT target AS nb FROM edges WHERE source=? "
                    "UNION SELECT source AS nb FROM edges WHERE target=?",
                    (current, current)).fetchall()

            edges_traversed += len(nbr_rows)
            for row in nbr_rows:
                nb_id = row["nb"]
                if nb_id in visited:
                    continue
                visited.add(nb_id)

                rel, ew = _edge_info(current, nb_id)
                pr_score = pr.get(nb_id, 0) / max_pr
                depth_decay = 1.0 / (1 + depth)
                score = pr_score * 0.4 + ew * 0.3 + depth_decay * 0.3

                if score < min_score:
                    continue

                nb_row = self.conn.execute(
                    "SELECT label FROM nodes WHERE id=?", (nb_id,)).fetchone()
                nb_label = nb_row["label"] if nb_row else nb_id

                discovered.append({
                    "id": nb_id,
                    "label": nb_label,
                    "score": round(score, 4),
                    "depth": depth + 1,
                })

                back = _trace_back(seed_id, current)
                full_path = back + [nb_id]
                paths.append({
                    "path": full_path,
                    "edges": [_edge_info(full_path[i], full_path[i + 1])[0]
                              for i in range(len(full_path) - 1)],
                    "score": round(score, 4),
                    "explanation": f"{seed_id} →({rel})→ {nb_label}",
                    "source": "pagerank_guided",
                })

                queue.append((nb_id, depth + 1, score))

        discovered.sort(key=lambda x: x["score"], reverse=True)
        paths.sort(key=lambda x: x["score"], reverse=True)

        return {
            "discovered": discovered[:budget],
            "paths": paths[:10],
            "stats": {
                "nodes_visited": len(visited),
                "edges_traversed": edges_traversed,
                "hops_completed": max_hops,
                "budget_used": round(len(visited) / budget, 4),
            },
        }

    def infer_relation(self, node_a: str, node_b: str,
                        max_hops: int = 3) -> dict | None:
        """不完整知识下的关系推断.

        组合 link prediction (Adamic-Adar + common neighbors) + path finding.
        返回 {relation, confidence, evidence, link_scores}.
        """
        if not self.has_node(node_a) or not self.has_node(node_b):
            return None

        def _edge_label(s, t):
            r = self.conn.execute(
                "SELECT relation FROM edges WHERE source=? AND target=? ORDER BY weight DESC LIMIT 1",
                (s, t)).fetchone()
            if r:
                return r["relation"]
            r = self.conn.execute(
                "SELECT relation FROM edges WHERE source=? AND target=? ORDER BY weight DESC LIMIT 1",
                (t, s)).fetchone()
            return r["relation"] if r else "related"

        # Step 1: Direct edge check
        direct = self.conn.execute(
            "SELECT relation, weight FROM edges WHERE source=? AND target=? "
            "UNION SELECT relation, weight FROM edges WHERE source=? AND target=?",
            (node_a, node_b, node_b, node_a)).fetchone()
        if direct:
            return {
                "relation": direct["relation"],
                "confidence": 1.0,
                "evidence": [{
                    "path": [node_a, node_b],
                    "edges": [direct["relation"]],
                    "score": 1.0,
                    "explanation": f"Direct edge: {node_a} —({direct['relation']})→ {node_b}",
                    "source": "direct",
                }],
                "link_scores": {
                    "adamic_adar": 0.0,
                    "common_neighbors": 0,
                    "preferential_attachment": 0,
                },
            }

        # Step 2: Find indirect paths (reasoning evidence)
        paths = self.reasoning_path(node_a, node_b, max_hops=max_hops, top_k=3)

        # Step 3: Link prediction scores
        common = self.common_neighbors(node_a, node_b)
        deg_a = self.conn.execute(
            "SELECT COUNT(*) c FROM edges WHERE source=? OR target=?",
            (node_a, node_a)).fetchone()["c"]
        deg_b = self.conn.execute(
            "SELECT COUNT(*) c FROM edges WHERE source=? OR target=?",
            (node_b, node_b)).fetchone()["c"]

        aa_score = 0.0
        for cn in common:
            deg_cn = self.conn.execute(
                "SELECT COUNT(*) c FROM edges WHERE source=? OR target=?",
                (cn, cn)).fetchone()["c"]
            aa_score += 1.0 / math.log(max(deg_cn, 2))

        if not paths:
            # No path found, return link prediction only
            return {
                "relation": "unknown",
                "confidence": round(min(aa_score / 3.0, 0.3), 4),
                "evidence": [],
                "link_scores": {
                    "adamic_adar": round(aa_score, 4),
                    "common_neighbors": len(common),
                    "preferential_attachment": deg_a * deg_b,
                },
            }

        best = paths[0]
        inferred_rel = " → ".join(best["edges"])
        confidence = best["score"] * 0.7 + min(aa_score / 3.0, 0.3) * 0.3

        return {
            "relation": inferred_rel,
            "confidence": round(confidence, 4),
            "evidence": paths,
            "link_scores": {
                "adamic_adar": round(aa_score, 4),
                "common_neighbors": len(common),
                "preferential_attachment": deg_a * deg_b,
            },
        }

    def reasoning_subgraph(self, query: str = None, seed_ids: list[str] = None,
                             max_hops: int = 2, top_k: int = 20) -> dict:
        """查询相关的推理子图.

        从 BM25 搜索或指定种子节点出发, 构建完整推理子图.
        返回 {nodes, edges, paths, summary}.
        """
        if seed_ids is None:
            seed_ids = []

        if query and not seed_ids:
            results = self.search_bm25(query, limit=5)
            seed_ids = [r.get("id") or r.get("node_id") for r in results if r.get("id") or r.get("node_id")]

        # Filter to valid seeds
        seed_ids = [s for s in seed_ids if self.has_node(s)]
        if not seed_ids:
            return {"nodes": [], "edges": [], "paths": [], "summary": "no seed nodes found"}

        # BFS expand from seeds
        sub_nodes = set(seed_ids)
        sub_edges = []
        frontier = list(seed_ids)

        for hop in range(max_hops):
            next_frontier = []
            for nid in frontier:
                rows = self.conn.execute(
                    "SELECT target AS nb, relation, weight FROM edges WHERE source=? "
                    "UNION SELECT source AS nb, relation, weight FROM edges WHERE target=?",
                    (nid, nid)).fetchall()
                for r in rows:
                    nb = r["nb"]
                    edge = {
                        "source": nid, "target": nb,
                        "relation": r["relation"], "weight": r["weight"],
                    }
                    edge_key = (edge["source"], edge["target"], edge["relation"])
                    if not any(e.get("_key") == edge_key for e in sub_edges):
                        edge["_key"] = edge_key
                        sub_edges.append(edge)
                    if nb not in sub_nodes:
                        sub_nodes.add(nb)
                        if len(sub_nodes) < top_k * 2:
                            next_frontier.append(nb)
            frontier = next_frontier
            if not frontier:
                break

        # Build node list with labels
        node_list = []
        for nid in sub_nodes:
            row = self.conn.execute(
                "SELECT label, kind, weight FROM nodes WHERE id=?", (nid,)).fetchone()
            if row:
                node_list.append({
                    "id": nid, "label": row["label"],
                    "kind": row["kind"], "weight": row["weight"],
                })

        # Clean edges
        clean_edges = [{k: v for k, v in e.items() if k != "_key"} for e in sub_edges]

        # Build reasoning paths between seeds
        paths = []
        for i, s1 in enumerate(seed_ids):
            for s2 in seed_ids[i + 1:]:
                rp = self.reasoning_path(s1, s2, max_hops=max_hops, top_k=2)
                paths.extend(rp)

        # PageRank for node importance within subgraph
        pr = self.pagerank(max_iter=15)
        for n in node_list:
            n["importance"] = round(pr.get(n["id"], 0), 6)
        node_list.sort(key=lambda x: x["importance"], reverse=True)

        summary = (f"Subgraph with {len(node_list)} nodes, {len(clean_edges)} edges, "
                   f"{len(paths)} reasoning paths from {len(seed_ids)} seeds")

        return {
            "nodes": node_list[:top_k],
            "edges": clean_edges,
            "paths": paths,
            "summary": summary,
        }

    # ── Adaptive Retrieval APIs (Test-Time Scaling inspired) ─────────────

    def classify_query(self, query: str) -> dict:
        """查询复杂度分类 (Adaptive-RAG NAACL 2024 / AHR 4-tier).

        将查询分为 simple / moderate / complex / multi_hop,
        用于路由到不同检索管道。

        启发式规则, 零 LLM 调用。
        """
        import re
        q_lower = query.lower().strip()
        words = q_lower.split()
        word_count = len(words)

        multi_hop_indicators = [
            r'how.*relate', r'compare.*and', r'difference',
            r'between.*and', r'because', r'why.*then',
            r'cause', r'effect', r'impact', r'result',
            r'chain', r'sequence', r'flow',
        ]
        complex_indicators = [
            r'how', r'why', r'explain', r'analyze',
            r'design', r'architecture', r'trade.?off',
        ]

        multi_hop_score = sum(1 for p in multi_hop_indicators if re.search(p, q_lower))
        complex_score = sum(1 for p in complex_indicators if re.search(p, q_lower))

        reasoning = []
        if multi_hop_score >= 2 or (multi_hop_score >= 1 and word_count > 12):
            level = "multi_hop"
            reasoning.append(f"multi_hop_score={multi_hop_score}, words={word_count}")
        elif complex_score >= 1 and word_count >= 7:
            level = "complex"
            reasoning.append(f"complex_score={complex_score}, words={word_count}")
        elif word_count > 6:
            level = "moderate"
            reasoning.append(f"words={word_count} (>8, no complex indicators)")
        else:
            level = "simple"
            reasoning.append(f"words={word_count} (<=8, no complex indicators)")

        # Effort level mapping
        effort_map = {"simple": "low", "moderate": "medium",
                      "complex": "high", "multi_hop": "max"}
        # Strategy mapping
        strategy_map = {"simple": "bm25_only", "moderate": "bm25+vector",
                        "complex": "hybrid+graph", "multi_hop": "graph_reasoning"}

        return {
            "complexity": level,
            "effort": effort_map[level],
            "strategy": strategy_map[level],
            "word_count": word_count,
            "multi_hop_score": multi_hop_score,
            "complex_score": complex_score,
            "reasoning": "; ".join(reasoning),
            # QDAP-v2 enrichment: include fusion-relevant type for cross-reference
            "qdap_type": MemoryGraph._classify_query(query).get("type", "semantic"),
        }

    def grade_retrieval(self, query: str, results: list[dict],
                         threshold: float = 0.15) -> dict:
        """检索结果质量评分 (CRAG-inspired Correct/Ambiguous/Incorrect).

        不需要 LLM — 用分数分布 + 图连通性做评估。

        返回 {grade, relevant_count, scores, recommendation}.
        """
        if not results:
            return {
                "grade": "incorrect",
                "relevant_count": 0,
                "scores": {"avg": 0, "max": 0, "gap": 0},
                "recommendation": "retrieval_failed",
            }

        scores = [r.get("score", 0) for r in results]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        min_score = min(scores)
        score_gap = max_score - min_score

        # Count relevant results (above threshold)
        relevant = [r for r in results if r.get("score", 0) >= threshold]
        relevant_count = len(relevant)

        # Check graph connectivity among top results (if >1 result)
        connectivity = 0.0
        if len(results) > 1:
            top_ids = [r.get("id") or r.get("node_id") for r in results[:5]]
            top_ids = [t for t in top_ids if t]
            if len(top_ids) > 1:
                connected_pairs = 0
                total_pairs = 0
                for i, a in enumerate(top_ids):
                    for b in top_ids[i + 1:]:
                        total_pairs += 1
                        cn = self.common_neighbors(a, b)
                        if cn or self.conn.execute(
                            "SELECT 1 FROM edges WHERE source=? AND target=? "
                            "UNION SELECT 1 FROM edges WHERE source=? AND target=?",
                            (a, b, b, a)).fetchone():
                            connected_pairs += 1
                connectivity = connected_pairs / total_pairs if total_pairs else 0

        # CRAG-style grading
        if relevant_count >= 2 and avg_score >= threshold * 2:
            grade = "relevant"
            recommendation = "use_results"
        elif relevant_count == 0 and avg_score < threshold:
            grade = "incorrect"
            recommendation = "retry_with_graph_or_web"
        else:
            grade = "ambiguous"
            if connectivity > 0.3:
                recommendation = "use_top_k_and_expand_graph"
            else:
                recommendation = "use_top_k_and_rerank"

        return {
            "grade": grade,
            "relevant_count": relevant_count,
            "connectivity": round(connectivity, 4),
            "scores": {
                "avg": round(avg_score, 6),
                "max": round(max_score, 6),
                "min": round(min_score, 6),
                "gap": round(score_gap, 6),
            },
            "recommendation": recommendation,
        }

    def search_adaptive(self, query: str, embedding: list[float] = None,
                         limit: int = 10) -> dict:
        """自适应检索 — 根据查询复杂度路由到不同检索管道.

        Pipeline: classify_query → route → execute → grade_retrieval → (optional) expand

        Returns {results, classification, grade, strategy}.
        """
        classification = self.classify_query(query)

        # Trivial queries skip retrieval entirely
        qdap = self._classify_query(query, [r[0] for r in self.conn.execute(
            "SELECT DISTINCT label FROM nodes LIMIT 200").fetchall()])
        if not qdap.get("needs_retrieval", True):
            return {
                "results": [],
                "classification": classification,
                "grade": {"grade": "trivial", "relevant_count": 0,
                           "scores": {"avg": 0, "max": 0, "gap": 0},
                           "recommendation": "no_retrieval_needed"},
                "strategy": "skip",
                "query_type": qdap["type"],
            }

        strategy = classification["strategy"]

        # Execute based on strategy
        if strategy == "bm25_only":
            raw = self.search_bm25(query, limit=limit)
            results = [{"id": r.get("node_id", r.get("id")),
                        "label": r.get("label"),
                        "score": r.get("score", 0)} for r in raw]
        elif strategy in ("bm25+vector", "hybrid+graph") and embedding:
            raw = self.search_hybrid(query, embedding=embedding, limit=limit)
            results = [{"id": r.get("node_id", r.get("id")),
                        "label": r.get("label"),
                        "score": r.get("score", 0)} for r in raw]
        elif strategy == "graph_reasoning":
            # Multi-hop: BM25 seed → graph reasoning expand
            # FTS5 uses implicit AND, so use OR for broader seed coverage
            import re as _re
            terms = _re.findall(r'\b[a-zA-Z_]{3,}\b', query)
            # Filter out common stop words
            stop_words = {'the', 'and', 'how', 'what', 'why', 'for', 'they',
                          'are', 'was', 'were', 'been', 'have', 'has', 'had',
                          'that', 'this', 'with', 'from', 'into', 'their',
                          'them', 'then', 'there', 'these', 'those', 'than',
                          'but', 'not', 'nor', 'yet', 'both', 'each', 'all',
                          'any', 'some', 'most', 'none', 'one', 'two', 'three',
                          'first', 'second', 'other', 'another', 'same',
                          'different', 'between', 'compare', 'relate', 'relates'}
            meaningful = [t for t in terms if t.lower() not in stop_words]
            if meaningful:
                fts_query = " OR ".join(meaningful[:5])
            else:
                fts_query = query
            raw = self.search_bm25(fts_query, limit=5)
            seed_ids = [r.get("node_id", r.get("id")) for r in raw]
            seed_ids = [s for s in seed_ids if s]
            if seed_ids:
                sub = self.reasoning_subgraph(seed_ids=seed_ids, max_hops=2, top_k=limit)
                results = [{"id": n["id"], "label": n["label"],
                            "score": n.get("importance", 0)} for n in sub["nodes"]]
            else:
                results = []
        else:
            # Fallback: BM25
            raw = self.search_bm25(query, limit=limit)
            results = [{"id": r.get("node_id", r.get("id")),
                        "label": r.get("label"),
                        "score": r.get("score", 0)} for r in raw]

        # Grade the retrieval
        grade = self.grade_retrieval(query, results)

        # If ambiguous and graph expansion is recommended
        if grade["grade"] == "ambiguous" and "expand" in grade["recommendation"]:
            top_ids = [r["id"] for r in results[:3] if r.get("id")]
            if top_ids:
                expanded = self.explore(top_ids[0], max_hops=1, budget=10)
                for d in expanded["discovered"][:3]:
                    if d["id"] not in {r["id"] for r in results}:
                        results.append({
                            "id": d["id"],
                            "label": d["label"],
                            "score": d["score"],
                            "source": "graph_expansion",
                        })

        return {
            "results": results[:limit],
            "classification": classification,
            "grade": grade,
            "strategy": strategy,
        }

    # ── Evidence-Gap Tracker (MemR³ inspired) ────────────────────

    def search_with_gaps(self, query: str, results: list[dict] = None,
                          limit: int = 10) -> dict:
        """证据缺口追踪 — 识别检索结果中缺失的多跳推理环节.

        MemR³ (arXiv:2512.20237) 核心洞察: 多跳推理失败不是因为检索不到,
        而是因为中间实体/关系缺失. Evidence-Gap Tracker 提取查询实体,
        检查它们在结果中的覆盖, 并发现缺失的连接路径.

        零 LLM 调用 — 纯图结构 + BM25 实体匹配.

        Returns:
            {
                "entities": [{"entity": str, "covered": bool, "node_ids": [...]}],
                "gaps": [{"gap": str, "missing_entities": [...], "suggestion": str}],
                "gap_score": float (0=no gaps, 1=all gaps),
                "repair_strategy": "none" | "expand_neighbors" | "bridge_search",
            }
        """
        import re

        # Step 1: Extract entities from query (simple NER — noun-like tokens)
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'how', 'what', 'why', 'when', 'where', 'who', 'which',
            'and', 'or', 'but', 'not', 'nor', 'yet', 'so',
            'for', 'to', 'of', 'in', 'on', 'at', 'by', 'with',
            'from', 'into', 'about', 'between', 'through',
            'this', 'that', 'these', 'those',
            'do', 'does', 'did', 'has', 'have', 'had',
            'will', 'would', 'could', 'should', 'may', 'might',
            'compare', 'relate', 'relation', 'relationship',
            'difference', 'similar', 'same',
        }
        tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z_]{2,}\b', query.lower())
        entities = [t for t in tokens if t not in stop_words]
        # Deduplicate while preserving order
        seen = set()
        entities = [e for e in entities if not (e in seen or seen.add(e))]
        entities = entities[:8]  # cap at 8 entities

        # Step 2: Check coverage of each entity in results
        if results is None:
            raw = self.search_bm25(query, limit=limit)
            results = [{"id": r.get("node_id", r.get("id")),
                        "label": r.get("label", ""),
                        "score": r.get("score", 0),
                        "tags": r.get("tags", [])} for r in raw]

        result_labels = " ".join(r.get("label", "").lower() for r in results)
        result_ids = set(r.get("id") for r in results if r.get("id"))

        entity_coverage = []
        for ent in entities:
            # Check if entity appears in any result label
            in_labels = ent in result_labels
            # Check if any node in graph matches this entity
            matching_nodes = self.conn.execute(
                "SELECT id FROM nodes WHERE LOWER(label) LIKE ? AND quarantined = 0",
                (f"%{ent}%",)
            ).fetchall()
            matching_ids = [row["id"] for row in matching_nodes]
            covered = in_labels or len(matching_ids) > 0
            entity_coverage.append({
                "entity": ent,
                "covered": covered,
                "in_results": in_labels,
                "node_ids": matching_ids[:5],
            })

        # Step 3: Find gaps — uncovered entities
        uncovered = [e for e in entity_coverage if not e["covered"]]
        covered_with_nodes = [e for e in entity_coverage
                              if e["covered"] and e["node_ids"]]

        gaps = []
        for unc in uncovered:
            # Try to find a bridge from covered entities to uncovered
            suggestion = "no_path"
            bridge_target = None
            for cov in covered_with_nodes:
                for cov_id in cov["node_ids"][:2]:
                    nbrs = self.neighbors(cov_id, depth=2)
                    for nbr in nbrs:
                        if unc["entity"] in nbr.label.lower():
                            bridge_target = nbr.id
                            suggestion = "bridge_found"
                            break
                    if bridge_target:
                        break
                if bridge_target:
                    break

            gaps.append({
                "gap": f"missing_entity: {unc['entity']}",
                "missing_entities": [unc["entity"]],
                "suggestion": suggestion,
                "bridge_node": bridge_target,
            })

        # Step 4: Check connectivity among covered entities (missing links)
        if len(covered_with_nodes) >= 2:
            for i, a in enumerate(covered_with_nodes[:4]):
                for b in covered_with_nodes[i + 1:4]:
                    # Check if there's any path between them
                    a_ids = a["node_ids"][:1]
                    b_ids = b["node_ids"][:1]
                    for aid in a_ids:
                        for bid in b_ids:
                            path = self.shortest_path(aid, bid)
                            if path is None:
                                gaps.append({
                                    "gap": f"no_path: {a['entity']} → {b['entity']}",
                                    "missing_entities": [a["entity"], b["entity"]],
                                    "suggestion": "bridge_search",
                                    "bridge_node": None,
                                })

        # Step 5: Compute gap score and repair strategy
        total_entities = len(entities) if entities else 1
        gap_score = len(uncovered) / total_entities

        if gap_score == 0 and not gaps:
            repair_strategy = "none"
        elif any(g["suggestion"] == "bridge_found" for g in gaps):
            repair_strategy = "expand_neighbors"
        else:
            repair_strategy = "bridge_search"

        return {
            "entities": entity_coverage,
            "gaps": gaps,
            "gap_score": round(gap_score, 4),
            "repair_strategy": repair_strategy,
            "entity_count": len(entities),
            "covered_count": len(entities) - len(uncovered),
        }

    # ── Admission Controller (A-MAC ICLR 2026 inspired) ─────────

    def should_admit(self, candidate_node_id: str = None, label: str = None,
                     kind: str = None, data: dict = None, tags: list[str] = None,
                     conflict_check: bool = True) -> dict:
        """记忆准入控制 — A-MAC 5-factor admission scoring.

        A-MAC (ICLR 2026 Workshop, arXiv:2603.04549) defines 5 factors for
        deciding whether new information should be admitted to memory:

        - **U**niqueness: How different from existing nodes? (trigram overlap)
        - **C**onflict: Does it contradict existing knowledge? (label/kind clash)
        - **N**ovelty: Does it bring new tags or connections? (tag set diff)
        - **R**elevance: How connected to existing graph? (neighbor overlap)
        - **T**imeliness: Is it temporally relevant? (recency factor)

        Returns: {admit: bool, score: float, factors: {U,C,N,R,T},
                  reason: str, conflicts: [...]}

        Zero LLM — pure heuristics on the graph structure.
        """
        # If node already exists, evaluate it; otherwise evaluate hypothetical
        if candidate_node_id and self.has_node(candidate_node_id):
            node = self.get_node(candidate_node_id)
            label = node.label
            kind = node.kind
            data = node.data
            tags_existing = self.conn.execute(
                "SELECT tags FROM nodes WHERE id = ?", (candidate_node_id,)
            ).fetchone()
            import json as _json
            tags = _json.loads(tags_existing["tags"]) if tags_existing and tags_existing["tags"] else []
        elif label is None:
            return {
                "admit": False,
                "score": 0.0,
                "factors": {"U": 0, "C": 0, "N": 0, "R": 0, "T": 0},
                "reason": "no_label_provided",
                "conflicts": [],
            }

        label_lower = label.lower()
        label_words = set(label_lower.split())

        # Factor 1: Uniqueness (U) — trigram overlap with existing nodes
        def _trigrams(text: str) -> set:
            chars = text.lower().replace(" ", "")
            return {chars[i:i + 3] for i in range(len(chars) - 2)} if len(chars) > 2 else {chars}

        cand_trigrams = _trigrams(label)
        all_nodes = self.conn.execute(
            "SELECT id, label FROM nodes WHERE quarantined = 0"
        ).fetchall()

        if all_nodes:
            max_overlap = 0.0
            most_similar = None
            for row in all_nodes:
                existing_trigrams = _trigrams(row["label"])
                if existing_trigrams:
                    overlap = len(cand_trigrams & existing_trigrams) / len(
                        cand_trigrams | existing_trigrams)
                    if overlap > max_overlap:
                        max_overlap = overlap
                        most_similar = row["label"]
            uniqueness = round(1.0 - max_overlap, 4)
        else:
            uniqueness = 1.0
            max_overlap = 0.0
            most_similar = None

        # Factor 2: Conflict (C) — does same-kind node with high label similarity exist?
        conflicts = []
        if conflict_check and kind:
            same_kind = [row for row in all_nodes if row["label"]]
            for row in same_kind:
                existing_label = row["label"]
                if label_lower == existing_label.lower():
                    conflicts.append({
                        "node_id": row["id"],
                        "label": existing_label,
                        "type": "exact_duplicate",
                    })
                else:
                    existing_words = set(existing_label.lower().split())
                    word_overlap = len(label_words & existing_words) / max(
                        len(label_words | existing_words), 1)
                    if word_overlap >= 0.5 and word_overlap < 1.0:
                        conflicts.append({
                            "node_id": row["id"],
                            "label": existing_label,
                            "type": "potential_conflict",
                            "similarity": round(word_overlap, 4),
                        })
        # Conflict score: exact dups penalize heavily, potential conflicts lightly
        exact_dups = sum(1 for c in conflicts if c["type"] == "exact_duplicate")
        potential_dups = sum(1 for c in conflicts if c["type"] == "potential_conflict")
        conflict_score = max(0.0, 1.0 - 0.5 * exact_dups - 0.1 * potential_dups)

        # Factor 3: Novelty (N) — new tags not in current tag vocabulary
        existing_tags = set()
        tag_rows = self.conn.execute("SELECT tags FROM nodes WHERE tags != '[]'").fetchall()
        for tr in tag_rows:
            import json as _j
            try:
                existing_tags.update(_j.loads(tr["tags"]))
            except Exception:
                pass
        new_tags = set(tags) - existing_tags if tags else set()
        novelty = round(len(new_tags) / max(len(tags), 1), 4) if tags else 0.5

        # Factor 4: Relevance (R) — how connected would this be?
        # Check if any existing node shares words/tags with candidate
        relevant_neighbors = 0
        if label_words:
            for row in all_nodes:
                row_words = set(row["label"].lower().split())
                if label_words & row_words:
                    relevant_neighbors += 1
        if tags:
            for tag in tags:
                tagged = self.search_by_tag(tag)
                relevant_neighbors += len(tagged)
        # Normalize: sigmoid-like (3 matching nodes → 0.6 relevance)
        relevance = round(min(1.0, relevant_neighbors / 5.0), 4)

        # Factor 5: Timeliness (T) — always 1.0 for new nodes (just created)
        timeliness = 1.0

        # Weighted admission score: U*0.25 + C*0.20 + N*0.15 + R*0.25 + T*0.15
        weights = {"U": 0.25, "C": 0.20, "N": 0.15, "R": 0.25, "T": 0.15}
        factors = {"U": uniqueness, "C": conflict_score,
                   "N": novelty, "R": relevance, "T": timeliness}
        score = round(sum(weights[k] * factors[k] for k in weights), 4)

        # Decision logic (conflicts checked before score)
        has_exact_dup = any(c["type"] == "exact_duplicate" for c in conflicts)
        if has_exact_dup:
            admit = False
            reason = "exact_duplicate_exists"
        elif len(conflicts) > 3:
            admit = False
            reason = "too_many_conflicts"
        elif score >= 0.5:
            admit = True
            reason = "above_threshold"
        elif uniqueness < 0.30 and relevance > 0.3:
            admit = True
            reason = "complementary_to_existing"
        else:
            admit = False
            reason = "below_threshold"

        return {
            "admit": admit,
            "score": score,
            "factors": factors,
            "weights": weights,
            "reason": reason,
            "conflicts": conflicts[:5],
            "most_similar": most_similar,
            "max_similarity": round(max_overlap, 4),
            "new_tags": sorted(new_tags) if new_tags else [],
            "relevant_neighbor_count": relevant_neighbors,
        }

    # ── Memory Lifecycle Report ─────────────────────────────────────

    def memory_lifecycle_report(self) -> dict:
        """Unified memory lifecycle dashboard.

        Combines access recency, weight distribution, decay status,
        consolidation state, quarantine health, and reinforcement
        activity into a single executive report.

        Returns:
            {total_nodes, active_nodes, stale_nodes, decaying_nodes,
             avg_weight, weight_distribution, quarantine_count,
             consolidated_count, reinforcement_events,
             lifecycle_stage, recommendations}
        """
        stats = self.stats()
        total = stats.get("nodes", 0)

        if total == 0:
            return {
                "total_nodes": 0,
                "lifecycle_stage": "empty",
                "recommendations": ["seed_initial_memories"],
            }

        now = time.time()

        # Access recency tiers
        rows = self.conn.execute(
            "SELECT id, weight, accessed, quarantined, data FROM nodes"
        ).fetchall()

        active_threshold = 3600 * 24 * 7  # 7 days
        stale_threshold = 3600 * 24 * 30  # 30 days

        active = stale = decaying = dormant = 0
        weights = []
        quarantined_count = 0
        consolidated_count = 0
        reinforcement_count = 0

        for row in rows:
            age = now - (row["accessed"] or now)
            weights.append(row["weight"] or 0.0)

            if row["quarantined"]:
                quarantined_count += 1

            if age < active_threshold:
                active += 1
            elif age < stale_threshold:
                stale += 1
            elif age < stale_threshold * 3:  # 90 days
                decaying += 1
            else:
                dormant += 1

            # Check consolidation/reinforcement in data
            try:
                data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                if isinstance(data, dict):
                    if data.get("_consolidated"):
                        consolidated_count += 1
                    rh = data.get("_reinforcement_history", [])
                    if rh:
                        reinforcement_count += len(rh)
            except Exception:
                pass

        avg_weight = sum(weights) / len(weights) if weights else 0.0

        # Weight distribution buckets
        buckets = {"critical (<0.1)": 0, "low (0.1-0.3)": 0,
                   "medium (0.3-0.6)": 0, "high (0.6-0.9)": 0,
                   "peak (>=0.9)": 0}
        for w in weights:
            if w < 0.1:
                buckets["critical (<0.1)"] += 1
            elif w < 0.3:
                buckets["low (0.1-0.3)"] += 1
            elif w < 0.6:
                buckets["medium (0.3-0.6)"] += 1
            elif w < 0.9:
                buckets["high (0.6-0.9)"] += 1
            else:
                buckets["peak (>=0.9)"] += 1

        # Determine lifecycle stage
        active_ratio = active / total
        if total < 10:
            stage = "seed"
        elif active_ratio > 0.6 and avg_weight > 0.3:
            stage = "thriving"
        elif active_ratio > 0.3:
            stage = "active"
        elif dormant > active:
            stage = "declining"
        else:
            stage = "maintenance"

        # Build recommendations
        recs = []
        if quarantined_count > total * 0.1:
            recs.append("review_quarantine_backlog")
        if dormant > total * 0.3:
            recs.append("prune_dormant_memories")
        if avg_weight < 0.1:
            recs.append("reinforce_key_memories")
        if reinforcement_count == 0:
            recs.append("start_reinforcement_tracking")
        if consolidated_count == 0 and total > 50:
            recs.append("run_consolidation_pipeline")
        if not recs:
            recs.append("healthy")

        return {
            "total_nodes": total,
            "active_nodes": active,
            "stale_nodes": stale,
            "decaying_nodes": decaying,
            "dormant_nodes": dormant,
            "avg_weight": round(avg_weight, 4),
            "weight_distribution": buckets,
            "quarantine_count": quarantined_count,
            "consolidated_count": consolidated_count,
            "reinforcement_events": reinforcement_count,
            "lifecycle_stage": stage,
            "recommendations": recs,
        }

    # ── Memory Access Pattern Analysis ──────────────────────────────

    def memory_access_pattern(self, *, days: int = 30) -> dict:
        """Analyse temporal access patterns of memory nodes.

        Groups nodes by kind, identifies access hotspots (frequently
        accessed) and cold spots (never/rarely accessed), computes
        access velocity (accesses per day), and detects diurnal
        bias (are memories accessed more at certain hours?).

        Args:
            days: look-back window for pattern analysis (default 30)

        Returns:
            {window_days, total_nodes, hot_nodes, cold_nodes,
             access_velocity, diurnal_bias, kind_temperature,
             recommendations}
        """
        now = time.time()
        cutoff = now - (days * 86400)

        rows = self.conn.execute(
            "SELECT id, label, kind, accessed, created FROM nodes WHERE quarantined = 0"
        ).fetchall()

        total = len(rows)
        if total == 0:
            return {
                "window_days": days,
                "total_nodes": 0,
                "recommendations": ["empty_store"],
            }

        hot = []
        cold = []
        kind_access = {}

        for row in rows:
            kind = row["kind"] or "unknown"
            accessed = row["accessed"] or row["created"] or now
            created = row["created"] or now

            if kind not in kind_access:
                kind_access[kind] = {"total": 0, "hot": 0, "cold": 0}
            kind_access[kind]["total"] += 1

            if accessed >= cutoff:
                hot.append({"id": row["id"], "label": row["label"], "kind": kind})
                kind_access[kind]["hot"] += 1
            elif created < cutoff:
                cold.append({"id": row["id"], "label": row["label"], "kind": kind,
                             "days_idle": round((now - accessed) / 86400, 1)})
                kind_access[kind]["cold"] += 1

        velocity = round(len(hot) / max(days * total, 1), 4)

        # Diurnal bias: hour-of-day distribution
        hour_counts = [0] * 24
        for row in rows:
            accessed = row["accessed"] or row["created"] or now
            if accessed >= cutoff:
                dt_hour = int((accessed % 86400) // 3600)
                hour_counts[dt_hour] += 1

        total_hour_accesses = sum(hour_counts)
        if total_hour_accesses > 0:
            peak_hour = hour_counts.index(max(hour_counts))
            peak_ratio = round(max(hour_counts) / total_hour_accesses, 4)
            diurnal_bias = peak_ratio > 0.2
        else:
            peak_hour = None
            peak_ratio = 0.0
            diurnal_bias = False

        # Kind temperature classification
        kind_temp = {}
        for kind, counts in kind_access.items():
            if counts["total"] > 0:
                ratio = round(counts["hot"] / counts["total"], 4)
                if ratio >= 0.7:
                    temp = "hot"
                elif ratio >= 0.3:
                    temp = "warm"
                else:
                    temp = "cold"
                kind_temp[kind] = {
                    "temperature": temp,
                    "hot_ratio": ratio,
                    "total": counts["total"],
                    "hot": counts["hot"],
                    "cold": counts["cold"],
                }

        recs = []
        cold_ratio = len(cold) / total if total > 0 else 0
        if cold_ratio > 0.5:
            recs.append("high_cold_ratio")
        if velocity < 0.01:
            recs.append("low_access_velocity")
        if diurnal_bias:
            recs.append("diurnal_bias_detected")
        fully_cold_kinds = [k for k, v in kind_temp.items() if v["temperature"] == "cold"]
        if fully_cold_kinds:
            recs.append("review_cold_kinds:" + ",".join(fully_cold_kinds[:3]))
        if not recs:
            recs.append("balanced_access")

        return {
            "window_days": days,
            "total_nodes": total,
            "hot_nodes": len(hot),
            "cold_nodes": len(cold),
            "hot_examples": hot[:5],
            "cold_examples": sorted(cold, key=lambda x: x["days_idle"], reverse=True)[:5],
            "access_velocity": velocity,
            "diurnal_bias": diurnal_bias,
            "peak_hour": peak_hour,
            "peak_hour_ratio": peak_ratio,
            "kind_temperature": kind_temp,
            "recommendations": recs,
        }

    # ── Memory Health Score ──────────────────────────────────────────

    def memory_health_score(self) -> dict:
        """Single composite health score (0–100) for the memory store.

        Combines five dimensions into one executive KPI:
        1. Vitality (30): are nodes active and weighted?
        2. Integrity (20): quarantine ratio, exact duplicates
        3. Connectivity (20): graph density, isolation rate
        4. Diversity (15): kind distribution evenness
        5. Maintenance (15): consolidation, reinforcement tracking

        Returns:
            {score, grade, dimensions, issues, trends}
        """
        stats = self.stats()
        total = stats.get("nodes", 0)

        if total == 0:
            return {"score": 0, "grade": "N/A",
                    "issues": ["empty_store"], "dimensions": {}}

        rows = self.conn.execute(
            "SELECT id, kind, weight, accessed, quarantined, data FROM nodes"
        ).fetchall()

        # 1. Vitality (0-30): avg weight * active ratio
        now = time.time()
        week_ago = now - 86400 * 7
        weights = [r["weight"] or 0.0 for r in rows]
        avg_weight = sum(weights) / len(weights) if weights else 0.0
        active = sum(1 for r in rows if (r["accessed"] or 0) >= week_ago)
        active_ratio = active / total
        vitality = round(min(30.0, (avg_weight * 0.5 + active_ratio * 0.5) * 30.0), 1)

        # 2. Integrity (0-20): penalize quarantine and low trust
        quarantined = sum(1 for r in rows if r["quarantined"])
        q_ratio = quarantined / total
        integrity = round(max(0.0, 20.0 * (1.0 - q_ratio * 5.0)), 1)

        # 3. Connectivity (0-20): edge coverage
        edge_count = self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        max_edges = total * (total - 1)
        density = (2 * edge_count / max_edges) if max_edges > 0 else 0.0
        # Nodes with at least 1 edge
        connected = self.conn.execute(
            "SELECT COUNT(DISTINCT source) FROM edges UNION SELECT COUNT(DISTINCT target) FROM edges"
        ).fetchall()
        sources = self.conn.execute("SELECT COUNT(DISTINCT source) FROM edges").fetchone()[0]
        targets = self.conn.execute("SELECT COUNT(DISTINCT target) FROM edges").fetchone()[0]
        involved = len(set(r["id"] for r in rows if r["id"] in [
            row[0] for row in self.conn.execute("SELECT source FROM edges").fetchall()
        ] or []))
        isolation_rate = 1.0 - min(1.0, (sources + targets) / (2 * total)) if total > 0 else 1.0
        connectivity = round(min(20.0, (1.0 - isolation_rate) * 15.0 + density * 100.0), 1)

        # 4. Diversity (0-15): kind distribution evenness (Shannon entropy)
        kind_counts = {}
        for r in rows:
            k = r["kind"] or "unknown"
            kind_counts[k] = kind_counts.get(k, 0) + 1
        if len(kind_counts) > 1:
            import math as _m
            entropy = -sum((c / total) * _m.log2(c / total) for c in kind_counts.values())
            max_entropy = _m.log2(len(kind_counts))
            evenness = entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            evenness = 0.0
        diversity = round(evenness * 15.0, 1)

        # 5. Maintenance (0-15): consolidation + reinforcement
        consolidated = 0
        reinforced = 0
        for r in rows:
            try:
                data = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
                if isinstance(data, dict):
                    if data.get("_consolidated"):
                        consolidated += 1
                    if data.get("_reinforcement_history"):
                        reinforced += 1
            except Exception:
                pass
        maintenance_score = 0.0
        if total > 0:
            maintenance_score = min(15.0, (consolidated / total * 7.5) + (reinforced / total * 7.5))
        maintenance = round(maintenance_score, 1)

        score = round(vitality + integrity + connectivity + diversity + maintenance, 1)

        # Grade
        if score >= 80:
            grade = "A"
        elif score >= 65:
            grade = "B"
        elif score >= 50:
            grade = "C"
        elif score >= 35:
            grade = "D"
        else:
            grade = "F"

        # Issues
        issues = []
        if vitality < 10:
            issues.append("low_vitality")
        if integrity < 10:
            issues.append("quarantine_backlog")
        if connectivity < 5:
            issues.append("poor_connectivity")
        if diversity < 3:
            issues.append("low_diversity")
        if maintenance < 3:
            issues.append("no_maintenance")
        if not issues:
            issues.append("healthy")

        return {
            "score": score,
            "grade": grade,
            "dimensions": {
                "vitality": {"score": vitality, "max": 30,
                             "avg_weight": round(avg_weight, 4),
                             "active_ratio": round(active_ratio, 4)},
                "integrity": {"score": integrity, "max": 20,
                              "quarantine_ratio": round(q_ratio, 4)},
                "connectivity": {"score": connectivity, "max": 20,
                                 "density": round(density, 6),
                                 "isolation_rate": round(isolation_rate, 4)},
                "diversity": {"score": diversity, "max": 15,
                              "kind_count": len(kind_counts),
                              "evenness": round(evenness, 4)},
                "maintenance": {"score": maintenance, "max": 15,
                                "consolidated": consolidated,
                                "reinforced": reinforced},
            },
            "issues": issues,
        }

    # ── Diffusion Retrieval (ExpGraph-inspired Graph Diffusion) ────────────

    def diffusion_retrieve(
        self,
        query: str = "",
        *,
        seeds: list[str] | None = None,
        embedding: list[float] | None = None,
        limit: int = 10,
        alpha: float = 0.15,
        max_iter: int = 50,
        tol: float = 1e-4,
        edge_weight_factor: float = 1.0,
        merge_bm25: bool = True,
        bm25_boost: float = 0.3,
        explain: bool = False,
    ) -> list[dict]:
        """Personalized PageRank diffusion retrieval (ExpGraph-inspired).

        Replaces fixed-hop BFS neighborhood expansion with diffusion that
        naturally decays with graph distance. Seed nodes are identified via
        BM25 / vector search, then Personalized PageRank propagates relevance
        scores through the graph.

        Args:
            query: Text query for seed identification (used if ``seeds`` is None).
            seeds: Explicit seed node IDs (skips BM25/vector seed discovery).
            embedding: Optional query vector for vector-based seed discovery.
            limit: Number of results to return.
            alpha: Teleport probability (a.k.a. reset probability). Higher values
                bias toward seeds; lower values let diffusion spread further.
                Typical: 0.15 (standard PPR) to 0.3 (conservative).
            max_iter: Maximum power iterations.
            tol: Convergence tolerance (L1 norm).
            edge_weight_factor: Exponent applied to edge weights. 1.0 = linear,
                0.5 = square root (dampens strong edges), 2.0 = amplifies.
            merge_bm25: If True, blend diffusion scores with BM25 relevance.
            bm25_boost: Weight of BM25 scores in the final blend (0-1).
                ``1.0 - bm25_boost`` is the diffusion weight.
            explain: If True, include diffusion paths and step-by-step trace.

        Returns:
            List of dicts sorted by blended score (descending)::

                [{node_id, label, kind, score, diffusion_score,
                  bm25_score, hop_distance, sources}, ...]
        """
        # ── 1. Seed discovery ──────────────────────────────────────────
        if seeds is None:
            if not query:
                raise ValueError("Either query or seeds must be provided")
            # Use BM25 to find top seed candidates
            bm25_results = self.search_bm25(query, limit=limit * 3)
            if not bm25_results:
                bm25_results = [
                    {"node_id": r["node"].id, "label": r["node"].label,
                     "kind": r["node"].kind, "score": r["score"]}
                    for r in self.search_unified(query, limit=limit * 3)
                ]
            seed_ids = [item["node_id"] for item in bm25_results[:max(limit, 5)]]
            seed_scores = {item["node_id"]: item.get("score", 0.0)
                           for item in bm25_results}
        else:
            seed_ids = list(seeds)
            seed_scores = {sid: 1.0 for sid in seed_ids}
            bm25_results = []

        if not seed_ids:
            return []

        # Filter to existing nodes
        existing = set(
            str(r["id"]) for r in self.conn.execute(
                "SELECT id FROM nodes WHERE quarantined = 0"
            ).fetchall()
        )
        seed_ids = [sid for sid in seed_ids if sid in existing]
        if not seed_ids:
            return []

        # ── 2. Build weighted adjacency (subgraph around seeds) ────────
        # Collect all nodes reachable within a few hops from seeds.
        # To keep it efficient, we load edges once and build adjacency.
        all_edges = self.conn.execute(
            "SELECT source, target, weight FROM edges"
        ).fetchall()

        adj: dict[str, list[tuple[str, float]]] = {}
        out_degree: dict[str, float] = {}
        node_set: set[str] = set()

        for e in all_edges:
            s = str(e["source"])
            t = str(e["target"])
            w = e["weight"] if e["weight"] else 1.0
            w = w ** edge_weight_factor
            if s not in adj:
                adj[s] = []
                out_degree[s] = 0.0
            if t not in adj:
                adj[t] = []
                out_degree[t] = 0.0
            adj[s].append((t, w))
            out_degree[s] += w
            node_set.add(s)
            node_set.add(t)

        # Ensure seed nodes exist in adjacency (even if isolated)
        for sid in seed_ids:
            if sid not in adj:
                adj[sid] = []
                out_degree[sid] = 0.0
                node_set.add(sid)

        if not node_set:
            return []

        # ── 3. Personalized PageRank (power iteration) ────────────────
        # PPR: p = alpha * teleport + (1 - alpha) * W^T p
        # where teleport is uniform over seed nodes.
        n = len(node_set)
        teleport_mass = 1.0 / len(seed_ids)

        rank = {nid: 0.0 for nid in node_set}
        for sid in seed_ids:
            rank[sid] = teleport_mass

        # Normalize initial rank (handle seeds not in node_set)
        total = sum(rank.values())
        if total > 0:
            rank = {nid: v / total for nid, v in rank.items()}

        # Dangling mass redistribution
        for _ in range(max_iter):
            new_rank = {nid: 0.0 for nid in node_set}
            dangling_mass = 0.0

            for nid in node_set:
                if out_degree.get(nid, 0) > 0:
                    out_w = out_degree[nid]
                    for tgt, w in adj.get(nid, []):
                        new_rank[tgt] += rank[nid] * (w / out_w) * (1 - alpha)
                else:
                    dangling_mass += rank[nid]

            # Teleport + dangling redistribution to seeds
            for sid in seed_ids:
                new_rank[sid] += alpha * teleport_mass
                new_rank[sid] += dangling_mass * teleport_mass

            # Check convergence
            diff = sum(abs(new_rank[nid] - rank[nid]) for nid in node_set)
            rank = new_rank
            if diff < tol:
                break

        # ── 4. Compute hop distances from seeds (BFS) ──────────────────
        hop_distance: dict[str, int] = {}
        bfs_frontier = list(seed_ids)
        for sid in seed_ids:
            hop_distance[sid] = 0
        hop = 0
        while bfs_frontier:
            hop += 1
            next_frontier = []
            for nid in bfs_frontier:
                for tgt, _ in adj.get(nid, []):
                    if tgt not in hop_distance:
                        hop_distance[tgt] = hop
                        next_frontier.append(tgt)
            bfs_frontier = next_frontier
            if hop >= 5:  # limit BFS depth
                break

        # ── 5. Merge with BM25 scores (optional) ───────────────────────
        bm25_map = {item["node_id"]: item.get("score", 0.0) for item in bm25_results} if merge_bm25 else {}
        max_bm25 = max(bm25_map.values()) if bm25_map else 1.0

        # Normalize diffusion scores
        max_diffusion = max(rank.values()) if rank else 1.0
        if max_diffusion == 0:
            max_diffusion = 1.0

        # Fetch node info
        node_info = {}
        for r in self.conn.execute(
            "SELECT id, label, kind FROM nodes WHERE quarantined = 0"
        ).fetchall():
            node_info[str(r["id"])] = (r["label"], r["kind"])

        results = []
        for nid, diff_score in rank.items():
            if diff_score <= 0 and nid not in seed_scores:
                continue
            if nid not in node_info:
                continue

            norm_diff = diff_score / max_diffusion
            bm25_s = 0.0
            if merge_bm25 and nid in bm25_map:
                bm25_s = bm25_map[nid] / max_bm25 if max_bm25 > 0 else 0.0

            blended = (1 - bm25_boost) * norm_diff + bm25_boost * bm25_s

            sources = set()
            if nid in seed_scores:
                sources.add("seed")
            if nid in bm25_map:
                sources.add("bm25")
            if nid not in seed_ids and diff_score > 0:
                sources.add("diffusion")

            results.append({
                "node_id": nid,
                "label": node_info[nid][0],
                "kind": node_info[nid][1],
                "score": round(blended, 6),
                "diffusion_score": round(norm_diff, 6),
                "bm25_score": round(bm25_s, 6),
                "hop_distance": hop_distance.get(nid, -1),
                "sources": sorted(sources),
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        if explain:
            for r_item in results:
                r_item["diffusion_paths"] = self._diffusion_explain(
                    r_item["node_id"], seed_ids, adj, hop_distance
                )

        return results[:limit]

    def _diffusion_explain(
        self,
        target: str,
        seeds: list[str],
        adj: dict[str, list[tuple[str, float]]],
        hop_distance: dict[str, int],
    ) -> list[dict]:
        """Trace shortest diffusion paths from seeds to target."""
        paths = []
        target_hop = hop_distance.get(target, -1)
        if target_hop <= 0:
            return [{"path": [target], "length": 0, "note": "seed node"}]

        # BFS from each seed to find path to target
        for seed in seeds:
            if seed == target:
                paths.append({"path": [seed], "length": 0, "note": "seed"})
                continue

            # BFS with path tracking (limited depth)
            queue = [(seed, [seed])]
            visited = {seed}
            found = False
            for _ in range(target_hop + 2):
                next_queue = []
                for node, path in queue:
                    for tgt, w in adj.get(node, []):
                        if tgt == target:
                            paths.append({
                                "path": path + [tgt],
                                "length": len(path),
                                "edge_weight": round(w, 4),
                            })
                            found = True
                            break
                        if tgt not in visited:
                            visited.add(tgt)
                            next_queue.append((tgt, path + [tgt]))
                    if found:
                        break
                queue = next_queue
                if found or not queue:
                    break

        return paths[:3]  # limit explanation paths

    # ── Knowledge Graph Embeddings (TransE) ────────────────

    def train_kge(self, dim: int = 32, epochs: int = 200, lr: float = 0.01,
                  margin: float = 1.0, seed: int = None) -> dict:
        """Train TransE knowledge graph embeddings.

        TransE models relationships as translations in embedding space:
            h + r ≈ t  (head + relation ≈ tail)

        Uses margin-based ranking loss with negative sampling.
        Stores entity/relation embeddings in kge_embeddings table.

        Args:
            dim: Embedding dimensionality (default 32)
            epochs: Training epochs (default 200)
            lr: Learning rate (default 0.01)
            margin: Margin for hinge loss γ (default 1.0)
            seed: Random seed for reproducibility

        Returns:
            {"entities": N, "relations": N, "dim": dim, "epochs": epochs}
        """
        import struct

        if seed is not None:
            import random as _rng
            _rng.seed(seed)

        # Collect entities and relations
        node_rows = self.conn.execute(
            "SELECT id, label FROM nodes WHERE quarantined = 0 OR quarantined IS NULL"
        ).fetchall()
        if len(node_rows) < 2:
            raise ValueError("Need at least 2 nodes for KGE training")

        edge_rows = self.conn.execute(
            "SELECT source, target, relation FROM edges"
        ).fetchall()
        if not edge_rows:
            raise ValueError("Need at least 1 edge for KGE training")

        entities = {row["id"]: row["label"] for row in node_rows}
        entity_ids = list(entities.keys())
        entity_idx = {eid: i for i, eid in enumerate(entity_ids)}

        relations = list(set(r["relation"] for r in edge_rows))
        rel_idx = {r: i for i, r in enumerate(relations)}

        n_ent = len(entity_ids)
        n_rel = len(relations)

        # Initialize embeddings (uniform [-1, 1] / dim, normalized)
        import random as _r2
        _r2.seed(seed) if seed is not None else None

        ent_emb = [[_r2.uniform(-1, 1) / math.sqrt(dim) for _ in range(dim)]
                   for _ in range(n_ent)]
        rel_emb = [[_r2.uniform(-1, 1) / math.sqrt(dim) for _ in range(dim)]
                   for _ in range(n_rel)]

        # Normalize entity embeddings to unit length
        for i in range(n_ent):
            norm = math.sqrt(sum(x * x for x in ent_emb[i])) or 1.0
            ent_emb[i] = [x / norm for x in ent_emb[i]]

        # Training triples
        triples = [(r["source"], r["target"], r["relation"]) for r in edge_rows]

        # Training loop
        for epoch in range(epochs):
            _r2.shuffle(triples)
            total_loss = 0.0

            for h_id, t_id, rel in triples:
                h = entity_idx.get(h_id)
                t = entity_idx.get(t_id)
                r = rel_idx.get(rel)
                if h is None or t is None or r is None:
                    continue

                # Negative sampling: corrupt tail
                neg_t = _r2.randint(0, n_ent - 1)
                while neg_t == t:
                    neg_t = _r2.randint(0, n_ent - 1)

                # Compute scores: d(h+r, t) and d(h+r, neg_t)
                def _dist(h_idx, t_idx, r_idx):
                    return sum((ent_emb[h_idx][d] + rel_emb[r_idx][d] - ent_emb[t_idx][d]) ** 2
                               for d in range(dim))

                pos_dist = _dist(h, t, r)
                neg_dist = _dist(h, neg_t, r)

                # Hinge loss: max(0, margin + pos - neg)
                loss = max(0, margin + pos_dist - neg_dist)
                total_loss += loss

                if loss > 0:
                    # Gradient update: push h+r toward t, away from neg_t
                    for d in range(dim):
                        # Positive direction
                        diff_pos = 2 * (ent_emb[h][d] + rel_emb[r][d] - ent_emb[t][d])
                        diff_neg = 2 * (ent_emb[h][d] + rel_emb[r][d] - ent_emb[neg_t][d])
                        grad = diff_pos - diff_neg

                        ent_emb[h][d] -= lr * grad
                        ent_emb[t][d] += lr * grad
                        ent_emb[neg_t][d] -= lr * (-grad)
                        rel_emb[r][d] -= lr * grad

                    # Re-normalize h (TransE constraint)
                    norm = math.sqrt(sum(x * x for x in ent_emb[h])) or 1.0
                    ent_emb[h] = [x / norm for x in ent_emb[h]]

        # Store in SQLite
        self.conn.execute("DROP TABLE IF EXISTS kge_embeddings")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS kge_embeddings (
                entity TEXT PRIMARY KEY,
                entity_type TEXT DEFAULT 'node',
                embedding BLOB NOT NULL
            )
        """)

        for eid, idx in entity_idx.items():
            blob = struct.pack(f'{dim}f', *ent_emb[idx])
            self.conn.execute(
                "INSERT OR REPLACE INTO kge_embeddings (entity, entity_type, embedding) VALUES (?, ?, ?)",
                (eid, 'node', blob)
            )
        for rel, idx in rel_idx.items():
            blob = struct.pack(f'{dim}f', *rel_emb[idx])
            self.conn.execute(
                "INSERT OR REPLACE INTO kge_embeddings (entity, entity_type, embedding) VALUES (?, ?, ?)",
                (rel, 'relation', blob)
            )

        self.conn.commit()
        self._kge_dim = dim
        self._kge_trained = True

        return {"entities": n_ent, "relations": n_rel, "dim": dim, "epochs": epochs}

    def _kge_distance(self, h_id: str, t_id: str, rel: str) -> float:
        """Compute TransE L2 distance for a triple. Returns inf if any entity missing."""
        import struct

        h_row = self.conn.execute(
            "SELECT embedding FROM kge_embeddings WHERE entity=? AND entity_type='node'", (h_id,)
        ).fetchone()
        t_row = self.conn.execute(
            "SELECT embedding FROM kge_embeddings WHERE entity=? AND entity_type='node'", (t_id,)
        ).fetchone()
        r_row = self.conn.execute(
            "SELECT embedding FROM kge_embeddings WHERE entity=? AND entity_type='relation'", (rel,)
        ).fetchone()

        if not h_row or not t_row or not r_row:
            return float('inf')

        dim = getattr(self, '_kge_dim', 32)
        h_emb = struct.unpack(f'{dim}f', h_row["embedding"])
        t_emb = struct.unpack(f'{dim}f', t_row["embedding"])
        r_emb = struct.unpack(f'{dim}f', r_row["embedding"])

        return sum((h_emb[d] + r_emb[d] - t_emb[d]) ** 2 for d in range(dim))

    def kge_score(self, head_label: str, tail_label: str, relation: str) -> float:
        """Score a triple using trained TransE embeddings (L2 distance, lower = better).

        Args:
            head_label: Head node label (must exist in graph)
            tail_label: Tail node label (must exist in graph)
            relation: Relation type

        Returns:
            L2 distance (float). Lower means more plausible. inf if entities not found.

        Raises:
            ValueError: If train_kge() has not been called
        """
        if not getattr(self, '_kge_trained', False):
            raise ValueError("KGE not trained. Call train_kge() first.")

        h_row = self.conn.execute("SELECT id FROM nodes WHERE label=?", (head_label,)).fetchone()
        t_row = self.conn.execute("SELECT id FROM nodes WHERE label=?", (tail_label,)).fetchone()
        if not h_row or not t_row:
            return float('inf')

        return self._kge_distance(h_row["id"], t_row["id"], relation)

    def get_kge_embedding(self, entity: str) -> Optional[list[float]]:
        """Get the learned KGE embedding for an entity (node ID or label).

        Args:
            entity: Node ID or label

        Returns:
            List of floats, or None if not found
        """
        import struct

        if not getattr(self, '_kge_trained', False):
            return None

        # Try as node ID first, then label
        row = self.conn.execute(
            "SELECT embedding FROM kge_embeddings WHERE entity=? AND entity_type='node'", (entity,)
        ).fetchone()
        if not row:
            n_row = self.conn.execute("SELECT id FROM nodes WHERE label=?", (entity,)).fetchone()
            if n_row:
                row = self.conn.execute(
                    "SELECT embedding FROM kge_embeddings WHERE entity=? AND entity_type='node'",
                    (n_row["id"],)
                ).fetchone()

        if not row:
            return None

        dim = getattr(self, '_kge_dim', 32)
        return list(struct.unpack(f'{dim}f', row["embedding"]))

    def _kge_neighbors(self, node_id: str, limit: int = 10) -> list[dict]:
        """Find related nodes via KGE proximity (internal helper for search_hybrid)."""
        import struct

        if not getattr(self, '_kge_trained', False):
            return []

        h_row = self.conn.execute(
            "SELECT embedding FROM kge_embeddings WHERE entity=? AND entity_type='node'", (node_id,)
        ).fetchone()
        if not h_row:
            return []

        dim = self._kge_dim
        h_emb = struct.unpack(f'{dim}f', h_row["embedding"])

        # Get all relation embeddings
        rel_rows = self.conn.execute(
            "SELECT entity, embedding FROM kge_embeddings WHERE entity_type='relation'",
        ).fetchall()
        if not rel_rows:
            return []

        # For each relation, compute h+r and find nearest entities
        all_entities = self.conn.execute(
            "SELECT entity, embedding FROM kge_embeddings WHERE entity_type='node' AND entity != ?",
            (node_id,)
        ).fetchall()

        if not all_entities:
            return []

        # Score = min over all relations of distance(h+r, t)
        scores = []
        for ent_row in all_entities:
            t_emb = struct.unpack(f'{dim}f', ent_row["embedding"])
            best_score = float('inf')
            for rel_row in rel_rows:
                r_emb = struct.unpack(f'{dim}f', rel_row["embedding"])
                dist = sum((h_emb[d] + r_emb[d] - t_emb[d]) ** 2 for d in range(dim))
                if dist < best_score:
                    best_score = dist
            scores.append((ent_row["entity"], best_score))

        scores.sort(key=lambda x: x[1])
        return [{"node_id": eid, "kge_distance": dist} for eid, dist in scores[:limit]]

    # ------------------------------------------------------------------
    # Bi-temporal validity tracking
    # ------------------------------------------------------------------

    def set_validity(self, node_id: str, valid_from: float = None,
                     valid_to: float = None) -> bool:
        """Set the valid-time interval for a node.

        Valid time represents when the fact is true in the real world.
        None for valid_from means "beginning of time".
        None for valid_to means "valid until superseded" (open-ended).

        Args:
            node_id: Node ID
            valid_from: Unix timestamp when the fact became true
            valid_to: Unix timestamp when the fact ceased to be true (None = still valid)

        Returns:
            True if updated, False if node not found
        """
        row = self.conn.execute("SELECT id FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            return False
        if valid_from is not None:
            self.conn.execute("UPDATE nodes SET valid_from=? WHERE id=?", (valid_from, node_id))
        if valid_to is not None:
            self.conn.execute("UPDATE nodes SET valid_to=? WHERE id=?", (valid_to, node_id))
        self.conn.execute(
            "UPDATE nodes SET txn_time=? WHERE id=?",
            (time.time(), node_id)
        )
        self.conn.commit()
        return True

    def is_valid_at(self, node_id: str, timestamp: float) -> bool:
        """Check if a node's fact was valid at the given timestamp.

        A node is valid at time T if:
        - valid_from is NULL or valid_from <= T, AND
        - valid_to is NULL or valid_to > T

        Nodes without any validity metadata are always considered valid.

        Args:
            node_id: Node ID
            timestamp: Unix timestamp to check

        Returns:
            True if the node was valid at the given time
        """
        row = self.conn.execute(
            "SELECT valid_from, valid_to FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        if not row:
            return False
        vf, vt = row["valid_from"], row["valid_to"]
        if vf is not None and vf > timestamp:
            return False
        if vt is not None and vt <= timestamp:
            return False
        return True

    def supersede(self, node_id: str, new_label: str = None,
                  new_kind: str = None, new_data: dict = None) -> Optional[str]:
        """Mark an old node as superseded and create a replacement.

        Sets valid_to on the old node to 'now', creates a new node with
        valid_from='now', and links old → new with a 'superseded_by' edge.

        Args:
            node_id: ID of the node to supersede
            new_label: Label for the new node (defaults to old label)
            new_kind: Kind for the new node (defaults to old kind)
            new_data: Data for the new node (defaults to old data)

        Returns:
            New node ID, or None if old node not found
        """
        old = self.get_node(node_id)
        if not old:
            return None
        now = time.time()
        # Close the old node's valid time
        self.conn.execute(
            "UPDATE nodes SET valid_to=?, txn_time=? WHERE id=?",
            (now, now, node_id)
        )
        # Create replacement
        new_node = self.add(
            new_label or old.label,
            new_kind or old.kind,
            new_data or old.data
        )
        self.conn.execute(
            "UPDATE nodes SET valid_from=?, txn_time=? WHERE id=?",
            (now, now, new_node.id)
        )
        # Link old → new
        self.link(node_id, new_node.id, "superseded_by")
        self.conn.commit()
        return new_node.id

    def query_valid_at(self, timestamp: float, kind: str = None) -> list[Node]:
        """Query all nodes whose valid-time interval contains the given timestamp.

        Args:
            timestamp: Unix timestamp to query
            kind: Optional kind filter

        Returns:
            List of Node objects valid at that time
        """
        sql = (
            "SELECT * FROM nodes WHERE "
            "(valid_from IS NULL OR valid_from <= ?) AND "
            "(valid_to IS NULL OR valid_to > ?) AND "
            "(quarantined = 0 OR quarantined IS NULL)"
        )
        params = [timestamp, timestamp]
        if kind is not None:
            sql += " AND kind=?"
            params.append(kind)
        rows = self.conn.execute(sql, params).fetchall()
        return [
            Node(r["id"], r["label"], r["kind"],
                 json.loads(r["data"]), r["created"], r["accessed"], r["weight"])
            for r in rows
        ]

    def get_history(self, node_id: str) -> list[dict]:
        """Get the full validity history chain for a node.

        Follows 'superseded_by' edges forward and backward to reconstruct
        the complete timeline of a fact.

        Args:
            node_id: Starting node ID

        Returns:
            List of {node_id, label, valid_from, valid_to, txn_time} sorted chronologically
        """
        chain = []
        seen = set()
        # Walk forward (this node → successors)
        current = node_id
        while current and current not in seen:
            seen.add(current)
            row = self.conn.execute(
                "SELECT id, label, valid_from, valid_to, txn_time FROM nodes WHERE id=?",
                (current,)
            ).fetchone()
            if not row:
                break
            chain.append({
                "node_id": row["id"],
                "label": row["label"],
                "valid_from": row["valid_from"],
                "valid_to": row["valid_to"],
                "txn_time": row["txn_time"],
            })
            # Find successor
            succ = self.conn.execute(
                "SELECT target FROM edges WHERE source=? AND relation='superseded_by'",
                (current,)
            ).fetchone()
            current = succ["target"] if succ else None
        # Walk backward (predecessors → this node)
        current = node_id
        backward = []
        while True:
            pred = self.conn.execute(
                "SELECT source FROM edges WHERE target=? AND relation='superseded_by'",
                (current,)
            ).fetchone()
            if not pred or pred["source"] in seen:
                break
            seen.add(pred["source"])
            row = self.conn.execute(
                "SELECT id, label, valid_from, valid_to, txn_time FROM nodes WHERE id=?",
                (pred["source"],)
            ).fetchone()
            if row:
                backward.append({
                    "node_id": row["id"],
                    "label": row["label"],
                    "valid_from": row["valid_from"],
                    "valid_to": row["valid_to"],
                    "txn_time": row["txn_time"],
                })
            current = pred["source"]
        chain = list(reversed(backward)) + chain
        return chain

    # ------------------------------------------------------------------
    # Q-value scoring (RL-inspired retrieval feedback)
    # ------------------------------------------------------------------

    def update_q_value(self, node_id: str, reward: float,
                       alpha: float = 0.1, gamma: float = 0.9) -> bool:
        """Update a node's Q-value using temporal-difference learning.

        Q(s) ← Q(s) + α · (reward + γ · max_neighbor_Q − Q(s))

        This lets frequently-useful memories accumulate higher Q-values,
        while rarely-useful ones decay toward zero.

        Args:
            node_id: Node to update
            reward: Immediate reward (positive=useful, negative=not useful)
            alpha: Learning rate (default 0.1)
            gamma: Discount factor for neighbor contribution (default 0.9)

        Returns:
            True if updated, False if node not found
        """
        row = self.conn.execute(
            "SELECT q_value FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        if not row:
            return False
        old_q = row["q_value"] if row["q_value"] is not None else 0.0
        # Max Q among neighbors (propagate value through graph)
        neighbor_q = self.conn.execute(
            "SELECT MAX(n.q_value) as max_q FROM nodes n"
            " JOIN edges e ON n.id = e.target WHERE e.source = ?",
            (node_id,)
        ).fetchone()
        max_n_q = neighbor_q["max_q"] if neighbor_q and neighbor_q["max_q"] is not None else 0.0
        new_q = old_q + alpha * (reward + gamma * max_n_q - old_q)
        self.conn.execute(
            "UPDATE nodes SET q_value=? WHERE id=?", (new_q, node_id)
        )
        self.conn.commit()
        return True

    def get_q_value(self, node_id: str) -> Optional[float]:
        """Get the current Q-value for a node.

        Returns:
            Q-value float, or None if node not found
        """
        row = self.conn.execute(
            "SELECT q_value FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        if not row:
            return None
        return row["q_value"] if row["q_value"] is not None else 0.0

    def reward(self, node_id: str, amount: float = 1.0) -> bool:
        """Convenience: give positive reward to a node (shortcut for update_q_value).

        Args:
            node_id: Node to reward
            amount: Reward magnitude (default 1.0)

        Returns:
            True if updated, False if not found
        """
        return self.update_q_value(node_id, reward=amount)

    def penalize(self, node_id: str, amount: float = 1.0) -> bool:
        """Convenience: give negative reward to a node.

        Args:
            node_id: Node to penalize
            amount: Penalty magnitude (default 1.0)

        Returns:
            True if updated, False if not found
        """
        return self.update_q_value(node_id, reward=-amount)

    def recall_with_q(self, query: str, limit: int = 5,
                      q_bias: float = 0.3) -> list[dict]:
        """Recall memories, blending text relevance with Q-value scoring.

        Final score = (1 − q_bias) · text_score + q_bias · normalized_q

        Args:
            query: Search query
            limit: Number of results
            q_bias: Weight of Q-value in final score (0.0=text only, 1.0=Q only)

        Returns:
            List of {node_id, label, kind, score, q_value} sorted by blended score
        """
        results = self.recall(query, limit=limit * 3)
        if not results:
            return []
        # Normalize text scores to [0, 1]
        max_text = max((n.weight for n in results), default=1.0)
        if max_text <= 0:
            max_text = 1.0
        # Normalize Q-values to [0, 1]
        q_values = {}
        for n in results:
            q = self.get_q_value(n.id)
            q_values[n.id] = q if q is not None else 0.0
        all_q = list(q_values.values())
        min_q = min(all_q) if all_q else 0.0
        max_q = max(all_q) if all_q else 1.0
        q_range = max_q - min_q
        if q_range <= 0:
            q_range = 1.0
        # Blend scores
        scored = []
        for n in results:
            text_norm = n.weight / max_text
            q_norm = (q_values[n.id] - min_q) / q_range
            blended = (1.0 - q_bias) * text_norm + q_bias * q_norm
            scored.append({
                "node_id": n.id,
                "label": n.label,
                "kind": n.kind,
                "score": round(blended, 6),
                "q_value": round(q_values[n.id], 6),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def top_q_nodes(self, limit: int = 10, kind: str = None) -> list[dict]:
        """Return nodes with the highest Q-values.

        Args:
            limit: Number of nodes to return
            kind: Optional kind filter

        Returns:
            List of {node_id, label, kind, q_value} sorted by Q-value descending
        """
        sql = (
            "SELECT id, label, kind, q_value FROM nodes "
            "WHERE (quarantined = 0 OR quarantined IS NULL)"
        )
        params = []
        if kind is not None:
            sql += " AND kind=?"
            params.append(kind)
        sql += " ORDER BY q_value DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [
            {"node_id": r["id"], "label": r["label"],
             "kind": r["kind"], "q_value": r["q_value"] or 0.0}
            for r in rows
        ]

    # ── Vector Clock + Subscribe/Publish ──

    def _tick(self, op: str, node_id: str = None, details: dict = None):
        """Advance Lamport clock, log the event, and emit to subscribers."""
        self._lamport_clock += 1
        lamport = self._lamport_clock
        detail_str = json.dumps(details or {})
        self.conn.execute(
            "INSERT INTO clock_log (lamport, op, node_id, details, wall_time) VALUES (?,?,?,?,?)",
            (lamport, op, node_id, detail_str, time.time())
        )
        self.conn.commit()
        evt = {"lamport": lamport, "op": op, "node_id": node_id, **(details or {})}
        self._emit(op, evt)

    def _emit(self, op: str, evt: dict):
        """Dispatch event to matching subscribers."""
        for op_key in (op, "*"):
            for _sub_id, callback in self._typed_subscribers.get(op_key, []):
                try:
                    callback(evt)
                except Exception:
                    pass

    def lamport_clock(self) -> int:
        """Return the current Lamport logical clock value for this graph."""
        return self._lamport_clock

    def event_log(self) -> list[dict]:
        """Return the full event log ordered by Lamport time."""
        rows = self.conn.execute(
            "SELECT lamport, op, node_id, details FROM clock_log ORDER BY lamport"
        ).fetchall()
        result = []
        for r in rows:
            entry = {"lamport": r["lamport"], "op": r["op"],
                     "node_id": r["node_id"]}
            entry.update(json.loads(r["details"]))
            result.append(entry)
        return result

    def on(self, event_type: str, callback: callable) -> str:
        """Subscribe to graph mutation events (typed pub/sub).

        Args:
            event_type: One of 'add', 'link', 'delete', 'update', or '*' for all.
            callback: Called with event dict on each matching operation.

        Returns:
            Subscription ID for later removal via off().
        """
        import uuid as _uuid
        sub_id = _uuid.uuid4().hex[:8]
        self._typed_subscribers.setdefault(event_type, []).append((sub_id, callback))
        return sub_id

    def off(self, sub_id: str) -> bool:
        """Remove a typed subscription by ID. Returns True if found."""
        for op_key, subs in self._typed_subscribers.items():
            for i, (sid, _) in enumerate(subs):
                if sid == sub_id:
                    subs.pop(i)
                    return True
        return False

    # ── Memory Conflict Detection ──

    @staticmethod
    def _extract_entities(text: str) -> set[str]:
        """Extract simple entity tokens from text (non-stopword, length>2)."""
        import re
        stopwords = {
            'the', 'is', 'are', 'was', 'were', 'a', 'an', 'of', 'in', 'to',
            'and', 'or', 'not', 'for', 'with', 'by', 'on', 'at', 'from',
            'it', 'this', 'that', 'these', 'those', 'be', 'been', 'being',
        }
        tokens = re.findall(r'[A-Za-z]{3,}', text.lower())
        return {t for t in tokens if t not in stopwords}

    @staticmethod
    def _extract_numbers(text: str) -> list[str]:
        """Extract numeric values from text."""
        import re
        return re.findall(r'\d+(?:\.\d+)?', text)

    def conflict_detect(self, threshold: float = 0.5,
                        kind: str = None) -> list[dict]:
        """Detect contradictions between facts in the memory graph.

        Uses entity overlap + numeric mismatch heuristics:
        - Facts sharing key entities are candidates
        - If numbers differ → value_mismatch conflict
        - If high text similarity but different phrasing → potential restatement (not conflict)

        Args:
            threshold: Conflict score threshold (0-1). Higher = stricter.
            kind: Optional kind filter (e.g. 'fact').

        Returns:
            List of conflict dicts: {node_a, node_b, label_a, label_b,
                                     kind_a, kind_b, type, score}
        """
        sql = "SELECT id, label, kind FROM nodes WHERE (quarantined = 0 OR quarantined IS NULL)"
        params = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        sql += " ORDER BY kind, label"
        rows = self.conn.execute(sql, params).fetchall()

        conflicts = []
        # Group by entity overlap
        entities_map = {}
        for row in rows:
            ents = self._extract_entities(row["label"])
            for ent in ents:
                entities_map.setdefault(ent, []).append(row)

        checked = set()
        for ent, group in entities_map.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a["id"] == b["id"]:
                        continue
                    pair_key = tuple(sorted([a["id"], b["id"]]))
                    if pair_key in checked:
                        continue
                    checked.add(pair_key)

                    # Check if this is actually a conflict
                    nums_a = self._extract_numbers(a["label"])
                    nums_b = self._extract_numbers(b["label"])

                    # Shared entities beyond this one word
                    ents_a = self._extract_entities(a["label"])
                    ents_b = self._extract_entities(b["label"])
                    shared = ents_a & ents_b

                    if nums_a and nums_b:
                        # Both have numbers — if different, likely conflict
                        if set(nums_a) != set(nums_b):
                            overlap_score = len(shared) / max(len(ents_a | ents_b), 1)
                            if overlap_score >= threshold * 0.5:
                                conflicts.append({
                                    "node_a": a["id"], "node_b": b["id"],
                                    "label_a": a["label"], "label_b": b["label"],
                                    "kind_a": a["kind"], "kind_b": b["kind"],
                                    "type": "value_mismatch",
                                    "score": round(min(overlap_score + 0.3, 1.0), 3),
                                    "shared_entities": list(shared),
                                    "numbers_a": nums_a,
                                    "numbers_b": nums_b,
                                })
                        # Same numbers + high similarity = restatement, not conflict
                    elif len(shared) >= 2:
                        # High entity overlap but no numbers — check for semantic contradiction
                        sim = self._content_similarity(a["label"], b["label"])
                        only_a = ents_a - ents_b
                        only_b = ents_b - ents_a
                        # If they share most words but have different specific entities
                        # (e.g. "capital of France" vs "capital of Germany")
                        if only_a and only_b and sim >= 0.3:
                            # Different proper nouns with high overlap = likely contradiction
                            score = round(sim * len(shared) / max(len(ents_a | ents_b), 1) + 0.3, 3)
                            score = min(score, 1.0)
                            if score >= threshold:
                                conflicts.append({
                                    "node_a": a["id"], "node_b": b["id"],
                                    "label_a": a["label"], "label_b": b["label"],
                                    "kind_a": a["kind"], "kind_b": b["kind"],
                                    "type": "semantic_contradiction",
                                    "score": score,
                                    "shared_entities": list(shared),
                                })
                        elif sim < 0.6 and sim > 0.1:
                            score = round(len(shared) / max(len(ents_a | ents_b), 1) * (1 - sim), 3)
                            if score >= threshold:
                                conflicts.append({
                                    "node_a": a["id"], "node_b": b["id"],
                                    "label_a": a["label"], "label_b": b["label"],
                                    "kind_a": a["kind"], "kind_b": b["kind"],
                                    "type": "semantic_contradiction",
                                    "score": score,
                                    "shared_entities": list(shared),
                                })

        # Sort by score descending
        conflicts.sort(key=lambda c: c["score"], reverse=True)
        return conflicts

    def conflict_resolve(self, keep_id: str, supersede_id: str,
                         reason: str = "") -> bool:
        """Resolve a conflict by keeping keep_id and quarantining supersede_id.

        Args:
            keep_id: Node ID to keep as authoritative.
            supersede_id: Node ID to quarantine.
            reason: Optional reason for the resolution.

        Returns:
            True if both nodes existed and resolution was applied.
        """
        keep = self.conn.execute("SELECT id FROM nodes WHERE id=?", (keep_id,)).fetchone()
        sup = self.conn.execute("SELECT id FROM nodes WHERE id=?", (supersede_id,)).fetchone()
        if not keep or not sup:
            return False
        self.conn.execute(
            "UPDATE nodes SET quarantined=1, quarantine_reason=? WHERE id=?",
            (f"superseded by {keep_id}: {reason}", supersede_id)
        )
        self.conn.commit()
        self._tick("conflict_resolve", keep_id,
                   {"kept": keep_id, "superseded": supersede_id, "reason": reason})
        return True

    def conflict_report(self, conflicts: list[dict]) -> str:
        """Generate a human-readable conflict report.

        Args:
            conflicts: Output from conflict_detect()

        Returns:
            Formatted string suitable for logging or display.
        """
        if not conflicts:
            return "No memory conflicts detected. ✓"
        lines = [f"⚠️ {len(conflicts)} memory conflict(s) detected:\n"]
        for i, c in enumerate(conflicts, 1):
            lines.append(f"  {i}. [{c['type']}] score={c['score']}")
            lines.append(f"     A: \"{c['label_a']}\"")
            lines.append(f"     B: \"{c['label_b']}\"")
            if c.get('shared_entities'):
                lines.append(f"     Shared: {', '.join(c['shared_entities'])}")
            lines.append("")
        return "\n".join(lines)

    # ── Strategic Forget ──

    def strategic_forget(self, min_weight: float = None,
                         max_age_days: float = None,
                         protect_q_above: float = None,
                         kind: str = None,
                         target_count: int = None,
                         dry_run: bool = False) -> dict:
        """Deliberate, confidence-weighted forgetting.

        MemoryArena research insight: forgetting is the most under-appreciated
        memory operation. This method provides controlled, audited removal of
        low-value memories while protecting high-confidence ones.

        Args:
            min_weight: Forget nodes with weight below this.
            max_age_days: Forget nodes not accessed in this many days.
            protect_q_above: Never forget nodes with Q-value above this.
            kind: Only forget nodes of this kind.
            target_count: If set, forget lowest-value nodes until count remains.
            dry_run: If True, report without deleting.

        Returns:
            {forgotten, edges_removed, kept, details: [...]}
        """
        import time as _time
        now = _time.time()

        # Build candidate query
        sql = (
            "SELECT id, label, kind, weight, accessed, q_value FROM nodes "
            "WHERE (quarantined = 0 OR quarantined IS NULL)"
        )
        params = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        # Exclude protected nodes
        if protect_q_above is not None:
            sql += " AND (q_value IS NULL OR q_value < ?)"
            params.append(protect_q_above)

        # Apply age/weight filters for candidate selection
        conditions = []
        if min_weight is not None:
            conditions.append("weight < ?")
            params.append(min_weight)
        if max_age_days is not None:
            cutoff = now - max_age_days * 86400
            conditions.append("accessed < ?")
            params.append(cutoff)

        if target_count is not None:
            # Need to forget down to target — select all, sort by value ascending
            sql += " ORDER BY q_value ASC, weight ASC, accessed ASC"
            rows = self.conn.execute(sql, params).fetchall()
            current_count = self.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE (quarantined=0 OR quarantined IS NULL)"
                + (" AND kind=?" if kind else ""),
                [kind] if kind else []
            ).fetchone()[0]
            to_forget = max(0, current_count - target_count)
            rows = rows[:to_forget]
        else:
            if conditions:
                sql += " AND " + " AND ".join(conditions)
            sql += " ORDER BY weight ASC, accessed ASC"
            rows = self.conn.execute(sql, params).fetchall()

        forgotten = []
        edges_removed = 0
        for row in rows:
            # Double-check protection
            if protect_q_above is not None and (row["q_value"] or 0) >= protect_q_above:
                continue
            node_id = row["id"]
            # Count edges that will be removed
            edge_count = self.conn.execute(
                "SELECT COUNT(*) FROM edges WHERE source=? OR target=?",
                (node_id, node_id)
            ).fetchone()[0]
            if not dry_run:
                self.conn.execute("DELETE FROM edges WHERE source=? OR target=?",
                                  (node_id, node_id))
                self._fts_delete_node(node_id)
                self.conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
                self._tick("strategic_forget", node_id,
                           {"label": row["label"], "weight": row["weight"],
                            "kind": row["kind"]})
            edges_removed += edge_count
            forgotten.append({
                "node_id": node_id,
                "label": row["label"],
                "kind": row["kind"],
                "weight": row["weight"],
                "q_value": row["q_value"] or 0.0,
            })

        if not dry_run:
            self.conn.commit()

        remaining = self.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE (quarantined=0 OR quarantined IS NULL)"
        ).fetchone()[0]

        return {
            "forgotten": len(forgotten),
            "edges_removed": edges_removed,
            "kept": remaining,
            "details": forgotten[:50],  # cap details for large forgets
        }

    # ── Community Detection (Label Propagation Algorithm) ──

    def _build_adjacency(self) -> dict[str, set[str]]:
        """Build undirected adjacency map from directed edges.

        Excludes quarantined nodes.
        """
        active_ids = {
            row["id"] for row in self.conn.execute(
                "SELECT id FROM nodes WHERE quarantined=0 OR quarantined IS NULL"
            ).fetchall()
        }
        adj: dict[str, set[str]] = defaultdict(set)
        for row in self.conn.execute("SELECT source, target FROM edges").fetchall():
            s, t = row["source"], row["target"]
            if s in active_ids and t in active_ids:
                adj[s].add(t)
                adj[t].add(s)
        for nid in active_ids:
            adj.setdefault(nid, set())
        return dict(adj)

    def detect_communities(self, max_iterations: int = 20, resolution: float = 1.0) -> dict:
        """Label Propagation Algorithm (LPA) for community detection.

        Assigns each node to a community by iteratively adopting the most
        frequent community label among its neighbors.  Converges when no
        node changes label in a full pass, or after *max_iterations*.

        Args:
            max_iterations: Maximum LPA iterations.
            resolution: Weight multiplier for same-kind nodes (higher
                values bias toward forming communities among nodes of the
                same kind).

        Returns dict with:
            - communities: {community_id: [node_id, ...]}
            - node_community: {node_id: community_id}
            - num_communities: int
            - iterations: int
            - modularity: float (Q-score, [−0.5, 1])
        """
        adj = self._build_adjacency()
        if not adj:
            return {"communities": {}, "node_community": {},
                    "num_communities": 0, "iterations": 0, "modularity": 0.0}

        node_ids = sorted(adj.keys())
        # Initialise: each node is its own community
        labels: dict[str, int] = {nid: i for i, nid in enumerate(node_ids)}
        # Pre-fetch kind for resolution bias
        kind_map: dict[str, str] = {}
        for row in self.conn.execute("SELECT id, kind FROM nodes").fetchall():
            kind_map[row["id"]] = row["kind"] or "unknown"

        iterations = 0
        changed = True
        while changed and iterations < max_iterations:
            changed = False
            iterations += 1
            for nid in node_ids:
                neighbors = adj[nid]
                if not neighbors:
                    continue
                # Vote: weighted label count
                votes: dict[int, float] = defaultdict(float)
                for nb in neighbors:
                    nb_label = labels[nb]
                    weight = resolution
                    if resolution != 1.0 and kind_map.get(nid) == kind_map.get(nb):
                        weight *= resolution  # same-kind boost
                    votes[nb_label] += weight
                if not votes:
                    continue
                # Pick the label with the highest vote (deterministic tie-break)
                best_label = max(votes, key=lambda lb: (votes[lb], -lb))
                if best_label != labels[nid]:
                    labels[nid] = best_label
                    changed = True

        # Relabel to consecutive integers starting from 0
        unique = sorted(set(labels.values()))
        remap = {old: new for new, old in enumerate(unique)}
        node_community = {nid: remap[labels[nid]] for nid in node_ids}

        # Group by community
        communities: dict[int, list[str]] = defaultdict(list)
        for nid, cid in node_community.items():
            communities[cid].append(nid)

        # Compute modularity Q
        modularity = self._modularity(adj, node_community, len(node_ids))

        # Cache results in instance for later lookups
        self._community_cache = {
            "node_community": node_community,
            "communities": dict(communities),
        }

        return {
            "communities": dict(communities),
            "node_community": node_community,
            "num_communities": len(communities),
            "iterations": iterations,
            "modularity": round(modularity, 4),
        }

    @staticmethod
    def _modularity(adj: dict[str, set[str]], labels: dict[str, int],
                    n: int) -> float:
        """Compute modularity Q for the current partition.

        Q = (1/2m) * Σ_ij [A_ij - k_i*k_j/(2m)] * δ(c_i, c_j)
        """
        if n == 0:
            return 0.0
        # Build degree map
        degree: dict[str, int] = {nid: len(nbrs) for nid, nbrs in adj.items()}
        two_m = sum(degree.values())  # 2m
        if two_m == 0:
            return 0.0
        # Sum over same-community pairs
        intra = 0.0
        for nid, nbrs in adj.items():
            for nb in nbrs:
                if labels.get(nid) == labels.get(nb):
                    intra += 1.0
        # intra now counts each edge twice (undirected)
        q = (intra / two_m) - sum(
            (degree[nid] / two_m) ** 2 for nid in degree
        )
        return q

    def community_of(self, node_id: str) -> Optional[int]:
        """Return the community ID for a node, or None if not assigned.

        Runs detect_communities() on first call and caches the result.
        """
        cache = getattr(self, "_community_cache", None)
        if cache is None:
            self.detect_communities()
            cache = getattr(self, "_community_cache", None)
        if cache is None:
            return None
        return cache["node_community"].get(node_id)

    def community_members(self, community_id: int) -> list[Node]:
        """Return all nodes in a given community."""
        cache = getattr(self, "_community_cache", None)
        if cache is None:
            self.detect_communities()
            cache = getattr(self, "_community_cache", {})
        ids = cache.get("communities", {}).get(community_id, [])
        nodes = []
        for nid in ids:
            node = self.get_node(nid)
            if node:
                nodes.append(node)
        return nodes

    def community_stats(self) -> list[dict]:
        """Return per-community statistics.

        Each dict contains:
            - community_id: int
            - size: int
            - kinds: {kind: count}
            - avg_weight: float
            - avg_q_value: float
            - internal_edges: int
            - total_edges: int
            - density: float (internal_edges / (size*(size-1)/2))
        """
        cache = getattr(self, "_community_cache", None)
        if cache is None:
            self.detect_communities()
            cache = getattr(self, "_community_cache", {})
        node_community = cache.get("node_community", {})
        communities = cache.get("communities", {})
        if not communities:
            return []

        # Pre-load nodes
        all_nodes: dict[str, sqlite3.Row] = {
            r["id"]: r for r in self.conn.execute("SELECT * FROM nodes").fetchall()
        }
        # Pre-load edges
        all_edges = self.conn.execute("SELECT source, target FROM edges").fetchall()

        result = []
        for cid, members in sorted(communities.items()):
            member_set = set(members)
            kinds: dict[str, int] = defaultdict(int)
            weights = []
            q_values = []
            for nid in members:
                row = all_nodes.get(nid)
                if not row:
                    continue
                kinds[row["kind"] or "unknown"] += 1
                weights.append(row["weight"] or 0.0)
                q_values.append(row["q_value"] or 0.0)
            internal_edges = sum(
                1 for e in all_edges
                if e["source"] in member_set and e["target"] in member_set
            )
            total_edges = sum(
                1 for e in all_edges
                if e["source"] in member_set or e["target"] in member_set
            )
            size = len(members)
            max_internal = size * (size - 1) / 2 if size > 1 else 1
            result.append({
                "community_id": cid,
                "size": size,
                "kinds": dict(kinds),
                "avg_weight": round(sum(weights) / len(weights), 4) if weights else 0.0,
                "avg_q_value": round(sum(q_values) / len(q_values), 4) if q_values else 0.0,
                "internal_edges": internal_edges,
                "total_edges": total_edges,
                "density": round(internal_edges / max_internal, 4) if max_internal > 0 else 0.0,
            })
        return result

    def search_community(self, query: str, limit: int = 10) -> list[Node]:
        """Community-aware retrieval: find the best community first, then search within it.

        1. BM25 search across all nodes to find the top match.
        2. Identify its community.
        3. Search within that community (and optionally neighbors) for related nodes.

        Falls back to global search if no communities are detected.
        """
        cache = getattr(self, "_community_cache", None)
        if cache is None:
            self.detect_communities()
            cache = getattr(self, "_community_cache", None)
        if cache is None or not cache.get("communities"):
            return self.recall(query, limit=limit)

        # Step 1: global BM25 to find seed
        seed_results = self.search_bm25(query, limit=1)
        if not seed_results:
            return self.recall(query, limit=limit)
        seed_id = seed_results[0]["node_id"]
        cid = cache["node_community"].get(seed_id)
        if cid is None:
            return self.recall(query, limit=limit)

        # Step 2: gather community members + adjacent communities
        member_ids = set(cache["communities"].get(cid, []))
        # Also include nodes from adjacent communities (1-hop neighbors)
        adj = self._build_adjacency()
        for mid in list(member_ids):
            for nb in adj.get(mid, []):
                member_ids.add(nb)

        # Step 3: BM25 within the community subset
        member_list = tuple(member_ids) if member_ids else ("__none__",)
        placeholders = ",".join("?" * len(member_list))
        if self._fts_enabled:
            sql = (
                f"SELECT n.id, n.label, n.kind, n.weight, "
                f"bm25(nodes_fts) AS score "
                f"FROM nodes_fts JOIN nodes n ON nodes_fts.node_id = n.id "
                f"WHERE nodes_fts MATCH ? AND n.id IN ({placeholders}) "
                f"ORDER BY score LIMIT ?"
            )
            try:
                rows = self.conn.execute(
                    sql, (query, *member_list, limit)
                ).fetchall()
            except sqlite3.OperationalError:
                # Fallback if FTS query syntax fails
                rows = []
        else:
            rows = []

        if not rows:
            # Fallback: filter by label LIKE
            like = f"%{query}%"
            sql = (
                f"SELECT id, label, kind, weight, 0 AS score FROM nodes "
                f"WHERE label LIKE ? AND id IN ({placeholders}) "
                f"ORDER BY weight DESC LIMIT ?"
            )
            rows = self.conn.execute(sql, (like, *member_list, limit)).fetchall()

        now = time.time()
        nodes = []
        for r in rows:
            self.conn.execute(
                "UPDATE nodes SET accessed=? WHERE id=?", (now, r["id"])
            )
            nodes.append(Node(r["id"], r["label"], r["kind"], {},
                              0, now, r["weight"] or 1.0))
        self.conn.commit()
        return nodes

    def community_graph(self) -> dict:
        """Build a reduced graph where each community is a supernode.

        Returns:
            - supernodes: [{community_id, size, dominant_kind, avg_weight}]
            - superedges: [{source, target, edges}]
        """
        cache = getattr(self, "_community_cache", None)
        if cache is None:
            self.detect_communities()
            cache = getattr(self, "_community_cache", {})
        node_community = cache.get("node_community", {})
        communities = cache.get("communities", {})
        if not communities:
            return {"supernodes": [], "superedges": []}

        # Compute per-community aggregates
        stats = self.community_stats()
        supernodes = []
        for s in stats:
            dominant_kind = max(s["kinds"].items(), key=lambda x: x[1])[0] if s["kinds"] else "unknown"
            supernodes.append({
                "community_id": s["community_id"],
                "size": s["size"],
                "dominant_kind": dominant_kind,
                "avg_weight": s["avg_weight"],
                "density": s["density"],
            })

        # Build inter-community edge counts
        inter: dict[tuple[int, int], int] = defaultdict(int)
        for row in self.conn.execute("SELECT source, target FROM edges").fetchall():
            src_c = node_community.get(row["source"])
            tgt_c = node_community.get(row["target"])
            if src_c is not None and tgt_c is not None and src_c != tgt_c:
                key = (min(src_c, tgt_c), max(src_c, tgt_c))
                inter[key] += 1

        superedges = [
            {"source": s, "target": t, "edges": cnt}
            for (s, t), cnt in sorted(inter.items())
        ]
        return {"supernodes": supernodes, "superedges": superedges}

    def community_profile(self, community_id: int) -> dict:
        """Generate a structured deep-dive profile of a single community.

        Complements community_summary() (which returns an overview list).
        This method focuses on one community: its internal structure,
        bridge nodes, and cohesion score.

        Returns:
            - community_id: int
            - size: int
            - dominant_kind: str
            - representative_labels: list[str] (top-5 by weight)
            - kind_distribution: {kind: count}
            - avg_weight / avg_q_value: float
            - internal_relations: {relation: count} (edge types within)
            - bridge_nodes: list[{node_id, label, external_edges}]
            - cohesion: float (internal_edges / total_edges, [0, 1])
        """
        cache = getattr(self, "_community_cache", None)
        if cache is None:
            self.detect_communities()
            cache = getattr(self, "_community_cache", {})
        communities = cache.get("communities", {})
        members = communities.get(community_id, [])
        if not members:
            return {}

        member_set = set(members)
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE id IN (%s) ORDER BY weight DESC" %
            ",".join("?" * len(members)), members
        ).fetchall()

        kinds: dict[str, int] = defaultdict(int)
        weights = []
        for r in rows:
            kinds[r["kind"] or "unknown"] += 1
            weights.append(r["weight"] or 0.0)

        dominant_kind = max(kinds.items(), key=lambda x: x[1])[0] if kinds else "unknown"
        representative = [r["label"] for r in rows[:5]]

        # Internal edge relations
        rel_counts: dict[str, int] = defaultdict(int)
        internal_edges = 0
        total_edges_for_community = 0
        edge_rows = self.conn.execute(
            "SELECT source, target, relation FROM edges WHERE source IN (%s) OR target IN (%s)" %
            (",".join("?" * len(members)), ",".join("?" * len(members))),
            members + members
        ).fetchall()
        for e in edge_rows:
            is_internal = e["source"] in member_set and e["target"] in member_set
            if is_internal:
                internal_edges += 1
                rel_counts[e["relation"]] += 1
            total_edges_for_community += 1

        # Bridge nodes: nodes with edges to other communities
        bridge_nodes = []
        for r in rows:
            outgoing = self.conn.execute(
                "SELECT target FROM edges WHERE source=?", (r["id"],)
            ).fetchall()
            incoming = self.conn.execute(
                "SELECT source FROM edges WHERE target=?", (r["id"],)
            ).fetchall()
            external = 0
            for o in outgoing:
                if o["target"] not in member_set:
                    external += 1
            for ic in incoming:
                if ic["source"] not in member_set:
                    external += 1
            if external > 0:
                bridge_nodes.append({
                    "node_id": r["id"],
                    "label": r["label"],
                    "external_edges": external,
                })
        bridge_nodes.sort(key=lambda b: b["external_edges"], reverse=True)

        cohesion = internal_edges / total_edges_for_community if total_edges_for_community > 0 else 0.0

        return {
            "community_id": community_id,
            "size": len(members),
            "dominant_kind": dominant_kind,
            "representative_labels": representative,
            "kind_distribution": dict(kinds),
            "avg_weight": round(sum(weights) / len(weights), 4) if weights else 0.0,
            "avg_q_value": round(
                sum(r["q_value"] or 0.0 for r in rows) / len(rows), 4
            ) if rows else 0.0,
            "internal_relations": dict(sorted(rel_counts.items(), key=lambda x: -x[1])),
            "bridge_nodes": bridge_nodes[:10],
            "cohesion": round(cohesion, 4),
        }

    def community_bridge_nodes(self) -> list[dict]:
        """Find all bridge nodes across all communities.

        A bridge node has edges to nodes in other communities.
        Returns list of {node_id, label, community_id, external_edges, external_communities}.
        """
        cache = getattr(self, "_community_cache", None)
        if cache is None:
            self.detect_communities()
            cache = getattr(self, "_community_cache", {})
        node_community = cache.get("node_community", {})
        if not node_community:
            return []

        bridges = []
        seen = set()
        for row in self.conn.execute("SELECT source, target FROM edges").fetchall():
            s, t = row["source"], row["target"]
            sc = node_community.get(s)
            tc = node_community.get(t)
            if sc is None or tc is None or sc == tc:
                continue
            for nid, cid, other in [(s, sc, tc), (t, tc, sc)]:
                if nid not in seen:
                    seen.add(nid)
                    # Count external edges and communities
                    ext_edges = 0
                    ext_comms = set()
                    for nb_row in self.conn.execute(
                        "SELECT target FROM edges WHERE source=? UNION "
                        "SELECT source FROM edges WHERE target=?",
                        (nid, nid)
                    ).fetchall():
                        nb_id = nb_row[0]
                        nb_c = node_community.get(nb_id)
                        if nb_c is not None and nb_c != cid:
                            ext_edges += 1
                            ext_comms.add(nb_c)
                    node_row = self.conn.execute(
                        "SELECT label FROM nodes WHERE id=?", (nid,)
                    ).fetchone()
                    bridges.append({
                        "node_id": nid,
                        "label": node_row["label"] if node_row else "",
                        "community_id": cid,
                        "external_edges": ext_edges,
                        "external_communities": sorted(ext_comms),
                    })
        bridges.sort(key=lambda b: b["external_edges"], reverse=True)
        return bridges

    # ─── Cache Temperature ─────────────────────────────────────────────
    # CPU-cache-inspired memory temperature: hot/warm/cold zones.
    # Temperature = f(recency, access_count, weight, q_value)

    def cache_temperature(self, node_id: str) -> float:
        """Return cache temperature score [0, 1] for a node.

        Combines recency, weight, and Q-value into a single 0-1
        temperature where 1 = hot (likely needed soon), 0 = cold.
        """
        row = self.conn.execute(
            "SELECT weight, accessed, q_value FROM nodes WHERE id=?",
            (node_id,)
        ).fetchone()
        if row is None:
            return 0.0
        now = time.time()
        age = max(now - (row["accessed"] or now), 0)
        recency = math.exp(-age / 604800.0)  # half-life ~7 days
        weight = min(max(row["weight"] or 0.0, 0.0), 2.0) / 2.0
        q_norm = max(0.0, min(1.0, (row["q_value"] or 0.0)))
        return round(recency * 0.5 + weight * 0.3 + q_norm * 0.2, 4)

    def cache_snapshot(self) -> dict:
        """Return a cache-temperature snapshot of the entire graph.

        Partitions nodes into hot (>0.66), warm (0.33-0.66), cold (<0.33).
        """
        rows = self.conn.execute(
            "SELECT id, label, kind, weight, accessed, q_value FROM nodes WHERE quarantined = 0"
        ).fetchall()
        now = time.time()
        hot, warm, cold = [], [], []
        for r in rows:
            age = max(now - (r["accessed"] or now), 0)
            recency = math.exp(-age / 604800.0)
            weight_n = min(max(r["weight"] or 0.0, 0.0), 2.0) / 2.0
            q_norm = max(0.0, min(1.0, (r["q_value"] or 0.0)))
            temp = round(recency * 0.5 + weight_n * 0.3 + q_norm * 0.2, 4)
            entry = {
                "node_id": r["id"], "label": r["label"],
                "kind": r["kind"], "temperature": temp,
            }
            if temp > 0.66:
                hot.append(entry)
            elif temp > 0.33:
                warm.append(entry)
            else:
                cold.append(entry)
        hot.sort(key=lambda e: e["temperature"], reverse=True)
        warm.sort(key=lambda e: e["temperature"], reverse=True)
        cold.sort(key=lambda e: e["temperature"])
        return {
            "hot_count": len(hot),
            "warm_count": len(warm),
            "cold_count": len(cold),
            "total": len(rows),
            "hot": hot,
            "warm": warm,
            "cold": cold,
        }

    def warm_cache(self, query: str, limit: int = 10) -> int:
        """Pre-warm memories matching a search query.

        Boosts accessed timestamp and slightly bumps weight for
        matched nodes. Returns count of warmed nodes.
        """
        results = self.recall(query, limit=limit)
        now = time.time()
        count = 0
        for node in results:
            self.conn.execute(
                "UPDATE nodes SET accessed = ?, weight = MIN(weight + 0.05, 2.0) WHERE id = ?",
                (now, node.id)
            )
            self._tick("update", node.id, {"action": "warm_cache"})
            count += 1
        self.conn.commit()
        return count

    def evict_cold(self, max_temperature: float = 0.15, min_age_hours: float = 48.0,
                   dry_run: bool = False) -> list[str]:
        """Evict (quarantine) nodes below a temperature threshold.

        Only evicts nodes that are both cold AND old. Q-value > 0.5
        nodes are protected. Returns list of evicted node IDs.
        """
        snapshot = self.cache_snapshot()
        now = time.time()
        cutoff = now - min_age_hours * 3600
        candidates = []
        for entry in snapshot["cold"]:
            if entry["temperature"] > max_temperature:
                continue
            row = self.conn.execute(
                "SELECT accessed, q_value FROM nodes WHERE id = ?",
                (entry["node_id"],)
            ).fetchone()
            if row is None:
                continue
            if (row["accessed"] or now) > cutoff:
                continue
            if (row["q_value"] or 0.0) > 0.5:
                continue
            candidates.append(entry["node_id"])
        if not dry_run:
            for nid in candidates:
                self.conn.execute(
                    "UPDATE nodes SET quarantined = 1, quarantine_reason = ? WHERE id = ?",
                    (f"cache_eviction: temp <= {max_temperature}", nid)
                )
            self.conn.commit()
            for nid in candidates:
                self._tick("update", nid, {"action": "evict_cold"})
        return candidates

    # ─── Memorywire Compatibility ─────────────────────────────────────

    def to_memorywire_format(self, include_quarantined: bool = False) -> dict:
        """Export graph in Memorywire-compatible JSON format.

        Memorywire is a memory exchange format with nodes (memories),
        edges (associations), and metadata. This enables interoperability
        with other memory systems.

        Schema:
            {
              "format": "memorywire/v1",
              "exported_at": <epoch>,
              "stats": {nodes, edges, kinds},
              "memories": [{id, label, kind, data, weight, q_value, ...}],
              "associations": [{source, target, relation, weight}]
            }
        """
        node_filter = "WHERE quarantined = 0" if not include_quarantined else ""
        nodes = self.conn.execute(
            f"SELECT id, label, kind, data, created, accessed, weight, "
            f"q_value, valid_from, valid_to, quarantined "
            f"FROM nodes {node_filter}"
        ).fetchall()
        edges = self.conn.execute(
            "SELECT source, target, relation, weight FROM edges"
        ).fetchall()
        kind_counts: dict[str, int] = {}
        for n in nodes:
            kind_counts[n["kind"]] = kind_counts.get(n["kind"], 0) + 1
        return {
            "format": "memorywire/v1",
            "exported_at": time.time(),
            "stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "kinds": kind_counts,
            },
            "memories": [{
                "id": n["id"],
                "label": n["label"],
                "kind": n["kind"],
                "data": json.loads(n["data"]),
                "created": n["created"],
                "accessed": n["accessed"],
                "weight": n["weight"],
                "q_value": n["q_value"],
                "valid_from": n["valid_from"],
                "valid_to": n["valid_to"],
                "quarantined": bool(n["quarantined"]),
            } for n in nodes],
            "associations": [{
                "source": e["source"],
                "target": e["target"],
                "relation": e["relation"],
                "weight": e["weight"],
            } for e in edges],
        }

    def from_memorywire_format(self, data: dict) -> int:
        """Import a Memorywire-format dict into this graph.

        Adds all memories and associations from the import. Returns
        the number of memories imported.
        """
        if data.get("format") != "memorywire/v1":
            raise ValueError(f"Unsupported format: {data.get('format')}")
        count = 0
        id_map: dict[str, str] = {}  # original_id → new_id
        for mem in data.get("memories", []):
            node = self.add(
                label=mem["label"],
                kind=mem.get("kind", "fact"),
                data=mem.get("data", {}),
            )
            id_map[mem["id"]] = node.id
            # Preserve metadata
            updates = {}
            if "weight" in mem:
                updates["weight"] = mem["weight"]
            if updates:
                self.conn.execute(
                    "UPDATE nodes SET weight = ? WHERE id = ?",
                    (updates["weight"], node.id)
                )
            count += 1
        # Import edges
        for assoc in data.get("associations", []):
            src = id_map.get(assoc["source"])
            tgt = id_map.get(assoc["target"])
            if src and tgt:
                self.link(src, tgt, assoc.get("relation", "related_to"))
        self.conn.commit()
        return count

    # ─── Scope-Delete Guard ────────────────────────────────────────────

    def delete_node_safe(self, node_id: str, force: bool = False) -> dict:
        """Delete a node with scope-delete guard.

        Prevents accidental deletion of nodes that have dependents
        (edges pointing TO this node from non-quarantined nodes).
        Use force=True to override.

        Returns dict with keys: deleted (bool), blocked_by (list of
        dependent node labels), reason (str).
        """
        row = self.conn.execute(
            "SELECT id, label FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        if not row:
            return {"deleted": False, "blocked_by": [], "reason": "not_found"}
        # Find dependents: nodes with edges pointing TO this node
        dependents = self.conn.execute(
            "SELECT DISTINCT e.source, n.label FROM edges e "
            "JOIN nodes n ON e.source = n.id "
            "WHERE e.target = ? AND n.quarantined = 0 AND e.source != ?",
            (node_id, node_id)
        ).fetchall()
        if dependents and not force:
            return {
                "deleted": False,
                "blocked_by": [d["label"] for d in dependents],
                "reason": f"{len(dependents)} dependent node(s) reference this memory",
            }
        self.delete_node(node_id)
        return {"deleted": True, "blocked_by": [], "reason": "ok"}



    # ─── Temporal Staleness Scoring ──────────────────────────────────

    def staleness_score(self, node_id: str) -> float:
        """Return staleness score [0, 1] where 0 = fresh, 1 = fully stale.

        Inspired by Mem0's temporal degradation finding:
        benchmark 91.6 → 49.0% after 30 days in production.

        Combines:
        - Age decay (40%): exponential with 30-day half-life
        - Access recency (35%): how recently the node was accessed
        - Validity gap (25%): if bi-temporal valid_to is in the past
        """
        row = self.conn.execute(
            "SELECT created, accessed, valid_from, valid_to FROM nodes WHERE id=?",
            (node_id,)
        ).fetchone()
        if row is None:
            return 1.0
        now = time.time()
        # Age component: 30-day half-life
        age_seconds = max(now - (row["created"] or now), 0)
        age_staleness = 1.0 - math.exp(-age_seconds / 2592000.0)  # 30-day half-life
        # Access recency: 7-day half-life
        access_age = max(now - (row["accessed"] or row["created"] or now), 0)
        access_staleness = 1.0 - math.exp(-access_age / 604800.0)  # 7-day half-life
        # Validity gap: if valid_to is set and in the past
        validity_staleness = 0.0
        if row["valid_to"] is not None:
            vt = row["valid_to"]
            if isinstance(vt, str):
                vt = datetime.fromisoformat(vt.replace("Z", "+00:00")).timestamp()
            if vt < now:
                validity_staleness = 1.0
            else:
                # Approaching expiry
                time_left = vt - now
                if time_left < 604800:  # within 7 days
                    validity_staleness = 1.0 - (time_left / 604800.0)
        return round(
            age_staleness * 0.40 + access_staleness * 0.35 + validity_staleness * 0.25, 4
        )

    def stale_nodes(self, threshold: float = 0.7, limit: int = 100) -> list[dict]:
        """Return nodes with staleness >= threshold, most stale first.

        Args:
            threshold: Minimum staleness to include [0, 1]
            limit: Maximum nodes to return

        Returns:
            List of {node_id, label, kind, staleness, created, accessed}
        """
        rows = self.conn.execute(
            "SELECT id, label, kind, created, accessed FROM nodes WHERE quarantined = 0"
        ).fetchall()
        result = []
        for r in rows:
            s = self.staleness_score(r["id"])
            if s >= threshold:
                result.append({
                    "node_id": r["id"], "label": r["label"],
                    "kind": r["kind"], "staleness": s,
                    "created": r["created"], "accessed": r["accessed"],
                })
        result.sort(key=lambda x: x["staleness"], reverse=True)
        return result[:limit]

    def fresh_nodes(self, threshold: float = 0.3, limit: int = 100) -> list[dict]:
        """Return nodes with staleness <= threshold, most fresh first.

        Args:
            threshold: Maximum staleness to include [0, 1]
            limit: Maximum nodes to return

        Returns:
            List of {node_id, label, kind, staleness, created, accessed}
        """
        rows = self.conn.execute(
            "SELECT id, label, kind, created, accessed FROM nodes WHERE quarantined = 0"
        ).fetchall()
        result = []
        for r in rows:
            s = self.staleness_score(r["id"])
            if s <= threshold:
                result.append({
                    "node_id": r["id"], "label": r["label"],
                    "kind": r["kind"], "staleness": s,
                    "created": r["created"], "accessed": r["accessed"],
                })
        result.sort(key=lambda x: x["staleness"])
        return result[:limit]

    def refresh_node(self, node_id: str) -> bool:
        """Refresh a stale node by updating its access timestamp.

        Returns True if node was found and refreshed, False otherwise.
        """
        row = self.conn.execute(
            "SELECT id FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        if row is None:
            return False
        now = time.time()
        self.conn.execute(
            "UPDATE nodes SET accessed=? WHERE id=?", (now, node_id)
        )
        self.conn.commit()
        self._tick("update", node_id, {"action": "refresh"})
        return True

    # ─── Multi-Path Retrieval Fusion ───────────────────────────────────

    def search_multi(self, query: str, limit: int = 10,
                     paths: list[str] = None,
                     weights: dict[str, float] = None) -> list[dict]:
        """Multi-path retrieval with Reciprocal Rank Fusion (RRF).

        Combines multiple retrieval strategies and fuses their rankings.
        Research insight (MemRL, ICLR 2026): usefulness ≠ similarity —
        different retrieval paths capture different aspects of relevance.

        Available paths:
        - "bm25": label text matching (recall)
        - "q_value": Q-value ranking (top_q_nodes)
        - "community": community-aware retrieval (search_community)
        - "temperature": cache temperature ranking

        Args:
            query: Search query
            limit: Final number of results
            paths: List of paths to use (default: all available)
            weights: Per-path weight overrides {path: weight}

        Returns:
            List of {node_id, label, kind, fused_score, sources} sorted by fused score
        """
        if paths is None:
            paths = ["bm25", "q_value", "community", "temperature"]
        if weights is None:
            weights = {}

        k = 60  # RRF constant
        rrf_scores: dict[str, float] = {}
        node_sources: dict[str, set] = {}
        node_info: dict[str, dict] = {}

        for path_name in paths:
            path_weight = weights.get(path_name, 1.0)
            ranked: list[str] = []

            if path_name == "bm25":
                results = self.recall(query, limit=limit * 3)
                ranked = [n.id for n in results]
            elif path_name == "q_value":
                results = self.recall_with_q(query, limit=limit * 3)
                ranked = [r["node_id"] for r in results]
            elif path_name == "community":
                try:
                    results = self.search_community(query, limit=limit * 3)
                    ranked = [n.id for n in results]
                except Exception:
                    pass
            elif path_name == "temperature":
                snapshot = self.cache_snapshot()
                for entry in snapshot["hot"] + snapshot["warm"]:
                    ranked.append(entry["node_id"])

            for rank, nid in enumerate(ranked):
                rrf = path_weight / (k + rank + 1)
                rrf_scores[nid] = rrf_scores.get(nid, 0.0) + rrf
                node_sources.setdefault(nid, set()).add(path_name)
                if nid not in node_info:
                    node = self.get_node(nid)
                    if node:
                        node_info[nid] = {
                            "label": node.label,
                            "kind": node.kind,
                        }

        fused = []
        for nid, score in rrf_scores.items():
            info = node_info.get(nid, {})
            fused.append({
                "node_id": nid,
                "label": info.get("label", ""),
                "kind": info.get("kind", ""),
                "fused_score": round(score, 6),
                "sources": sorted(node_sources[nid]),
            })
        fused.sort(key=lambda x: x["fused_score"], reverse=True)
        return fused[:limit]

    # ─── Memory Sleep Consolidation ───────────────────────────────────

    def sleep_consolidate(self, similarity_threshold: float = 0.6,
                          min_weight: float = 0.3,
                          dry_run: bool = False) -> dict:
        """Consolidate memories by merging similar low-weight nodes.

        Inspired by biological sleep-time memory consolidation:
        - Weak memories with high overlap are merged into a single stronger node
        - Preserves the strongest node in each cluster as the 'anchor'
        - Edge relationships from merged nodes are redirected to anchor

        This is a destructive operation (unless dry_run=True) — merged nodes
        are quarantined, not deleted, preserving audit trail.

        Args:
            similarity_threshold: Minimum label similarity to merge [0, 1]
            min_weight: Only merge nodes below this weight
            dry_run: Report without executing

        Returns:
            {scanned, merged, kept, details}
        """
        import difflib

        rows = self.conn.execute(
            "SELECT id, label, kind, weight FROM nodes "
            "WHERE quarantined = 0 AND weight < ?",
            (min_weight,)
        ).fetchall()

        if len(rows) < 2:
            return {"scanned": len(rows), "merged": 0, "kept": len(rows),
                    "details": []}

        # Group by kind first for efficiency
        kind_groups: dict[str, list] = {}
        for r in rows:
            kind_groups.setdefault(r["kind"], []).append(r)

        result = {"scanned": len(rows), "merged": 0, "kept": 0, "details": []}
        merged_ids: set = set()

        for kind, group in kind_groups.items():
            for i, base in enumerate(group):
                if base["id"] in merged_ids:
                    continue
                cluster = [base]
                for candidate in group[i + 1:]:
                    if candidate["id"] in merged_ids:
                        continue
                    sim = difflib.SequenceMatcher(
                        None, base["label"].lower(), candidate["label"].lower()
                    ).ratio()
                    if sim >= similarity_threshold:
                        cluster.append(candidate)

                if len(cluster) < 2:
                    result["kept"] += 1
                    continue

                # Pick anchor: highest weight
                anchor = max(cluster, key=lambda r: r["weight"] or 0.0)
                merged_weight = sum(r["weight"] or 0.0 for r in cluster)

                if not dry_run:
                    for node in cluster:
                        if node["id"] == anchor["id"]:
                            continue
                        # Redirect edges to anchor
                        self.conn.execute(
                            "UPDATE edges SET source=? WHERE source=?",
                            (anchor["id"], node["id"])
                        )
                        self.conn.execute(
                            "UPDATE edges SET target=? WHERE target=?",
                            (anchor["id"], node["id"])
                        )
                        # Quarantine merged node
                        self.conn.execute(
                            "UPDATE nodes SET quarantined=1, weight=0.0 WHERE id=?",
                            (node["id"],)
                        )
                        self._tick("update", node["id"], {
                            "action": "consolidate_merge",
                            "anchor": anchor["id"],
                        })
                        merged_ids.add(node["id"])

                    # Boost anchor weight
                    self.conn.execute(
                        "UPDATE nodes SET weight=? WHERE id=?",
                        (merged_weight, anchor["id"])
                    )
                    self._tick("update", anchor["id"], {
                        "action": "consolidate_anchor",
                        "absorbed": len(cluster) - 1,
                    })

                result["merged"] += len(cluster) - 1
                result["kept"] += 1
                result["details"].append({
                    "anchor_id": anchor["id"],
                    "anchor_label": anchor["label"],
                    "merged_labels": [r["label"] for r in cluster if r["id"] != anchor["id"]],
                    "combined_weight": round(merged_weight, 4),
                })

        self.conn.commit()
        return result


    # ── Episodic Memory Replay ────────────────────────────

    def retrieve_episodes(self, start_time: float = None, end_time: float = None,
                           kind: str = None, node_id: str = None,
                           limit: int = 20) -> list[dict]:
        """Reconstruct temporal sequences of memories (episodes).

        Retrieves nodes ordered by creation time within a time window,
        optionally filtered by kind or anchored to a specific node's
        neighborhood. Each episode entry includes the node and its
        temporal distance from the previous node in the sequence.

        Inspired by episodic memory replay in biological systems —
        the ability to re-experience a sequence of events in order.

        Args:
            start_time: Unix timestamp lower bound (inclusive). Default: all.
            end_time: Upper bound (inclusive). Default: now.
            kind: Filter by node kind (e.g. 'event', 'fact').
            node_id: If provided, only include nodes within 2-hop neighborhood.
            limit: Maximum episodes to return.

        Returns:
            List of dicts: {node, prev_gap_seconds, cumulative_seconds}
        """
        now = time.time()
        if end_time is None:
            end_time = now
        if start_time is None:
            start_time = 0.0

        # Build neighborhood filter if node_id provided
        neighbor_ids = None
        if node_id:
            neighbor_ids = {node_id}
            # 1-hop neighbors
            rows = self.conn.execute(
                "SELECT DISTINCT target FROM edges WHERE source=? "
                "UNION SELECT DISTINCT source FROM edges WHERE target=?",
                (node_id, node_id)
            ).fetchall()
            neighbor_ids.update(r[0] for r in rows)
            # 2-hop neighbors
            for r in rows:
                nid = r[0]
                r2 = self.conn.execute(
                    "SELECT DISTINCT target FROM edges WHERE source=? "
                    "UNION SELECT DISTINCT source FROM edges WHERE target=?",
                    (nid, nid)
                ).fetchall()
                neighbor_ids.update(x[0] for x in r2)

        conditions = ["created >= ?", "created <= ?", "quarantined = 0"]
        params = [start_time, end_time]
        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        if neighbor_ids is not None:
            placeholders = ','.join('?' * len(neighbor_ids))
            conditions.append(f"id IN ({placeholders})")
            params.extend(list(neighbor_ids))

        where_clause = " AND ".join(conditions)
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT * FROM nodes WHERE {where_clause} ORDER BY created ASC LIMIT ?",
            params
        ).fetchall()

        episodes = []
        prev_time = None
        cumulative = 0.0
        for row in rows:
            node = Node(row["id"], row["label"], row["kind"],
                        json.loads(row["data"]), row["created"],
                        row["accessed"], row["weight"])
            gap = (node.created - prev_time) if prev_time is not None else 0.0
            cumulative += gap
            episodes.append({
                "node": node,
                "prev_gap_seconds": round(gap, 3),
                "cumulative_seconds": round(cumulative, 3),
            })
            prev_time = node.created
        return episodes

    def episode_timeline(self, episodes: list[dict] = None,
                         start_time: float = None, end_time: float = None,
                         kind: str = None) -> str:
        """Format episodes as a human-readable timeline.

        If episodes not provided, calls retrieve_episodes() with the
        given filters. Returns a formatted string with timestamps,
        temporal gaps, and node labels.
        """
        if episodes is None:
            episodes = self.retrieve_episodes(
                start_time=start_time, end_time=end_time, kind=kind, limit=50
            )
        if not episodes:
            return "(empty timeline)"

        lines = []
        for ep in episodes:
            node = ep["node"]
            ts = datetime.fromtimestamp(node.created).strftime("%Y-%m-%d %H:%M:%S")
            gap = ep["prev_gap_seconds"]
            gap_str = f" (+{gap:.0f}s)" if gap > 0 and gap < 3600 else (
                f" (+{gap/3600:.1f}h)" if gap >= 3600 and gap < 86400 else (
                    f" (+{gap/86400:.1f}d)" if gap >= 86400 else ""
                )
            )
            lines.append(f"  {ts}{gap_str} [{node.kind}] {node.label} (w={node.weight:.2f})")
        return "\n".join(lines)

    def replay_from(self, node_id: str, direction: str = "forward",
                    hops: int = 3, limit: int = 15) -> list[dict]:
        """Replay memories starting from a specific node, traversing edges.

        Traverses the graph from node_id either forward (outgoing edges)
        or backward (incoming edges), collecting nodes in temporal order.
        Each hop level is tracked. Useful for 'how did I get here?' or
        'what happened next?' queries.

        Args:
            node_id: Starting node.
            direction: 'forward' (outgoing edges) or 'backward' (incoming).
            hops: Maximum traversal depth.
            limit: Maximum nodes to return.

        Returns:
            List of dicts: {node, hop, edge_relation, prev_node_id}
        """
        if direction not in ("forward", "backward"):
            raise ValueError("direction must be 'forward' or 'backward'")

        visited = {node_id}
        results = []
        frontier = [(node_id, 0, None, None)]  # (id, hop, relation, prev_id)

        while frontier and len(results) < limit:
            curr_id, hop, relation, prev_id = frontier.pop(0)
            # Skip quarantined nodes entirely (don't expand or include)
            if self._is_quarantined(curr_id) and curr_id != node_id:
                continue
            if hop > 0:  # Don't include the starting node itself
                node = self.get_node(curr_id)
                if node and not self._is_quarantined(curr_id):
                    results.append({
                        "node": node,
                        "hop": hop,
                        "edge_relation": relation,
                        "prev_node_id": prev_id,
                    })
                    visited.add(curr_id)
            if hop >= hops:
                continue

            if direction == "forward":
                edges = self.conn.execute(
                    "SELECT target, relation FROM edges WHERE source=?", (curr_id,)
                ).fetchall()
            else:
                edges = self.conn.execute(
                    "SELECT source, relation FROM edges WHERE target=?", (curr_id,)
                ).fetchall()

            for edge in edges:
                neighbor_id = edge[0]
                if neighbor_id not in visited:
                    frontier.append((neighbor_id, hop + 1, edge["relation"], curr_id))

        # Sort by creation time for temporal replay
        results.sort(key=lambda r: r["node"].created)
        return results

    def _is_quarantined(self, node_id: str) -> bool:
        """Check if a node is quarantined."""
        row = self.conn.execute(
            "SELECT quarantined FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        return row is not None and row[0] == 1

    # ── Graph Analytics ─────────────────────────────────────

    def graph_analytics(self) -> dict:
        """Comprehensive graph analytics in a single call.

        Returns density, degree distribution, centrality metrics,
        memory health scores, and structural insights.
        Combines and extends stats() with deeper analysis.
        """
        nodes = self.conn.execute(
            "SELECT * FROM nodes WHERE quarantined=0"
        ).fetchall()
        n_count = len(nodes)

        edges = self.conn.execute("SELECT * FROM edges").fetchall()
        e_count = len(edges)

        # Density: actual / max possible edges (directed, no self-loops)
        max_edges = n_count * (n_count - 1) if n_count > 1 else 0
        density = e_count / max_edges if max_edges > 0 else 0.0

        # Degree analysis
        out_deg = defaultdict(int)
        in_deg = defaultdict(int)
        for e in edges:
            out_deg[e["source"]] += 1
            in_deg[e["target"]] += 1

        all_degrees = [out_deg.get(r["id"], 0) + in_deg.get(r["id"], 0) for r in nodes]
        avg_degree = sum(all_degrees) / len(all_degrees) if all_degrees else 0.0
        max_degree = max(all_degrees) if all_degrees else 0

        # Degree distribution buckets
        deg_dist = {"0": 0, "1-2": 0, "3-5": 0, "6-10": 0, "10+": 0}
        for d in all_degrees:
            if d == 0:
                deg_dist["0"] += 1
            elif d <= 2:
                deg_dist["1-2"] += 1
            elif d <= 5:
                deg_dist["3-5"] += 1
            elif d <= 10:
                deg_dist["6-10"] += 1
            else:
                deg_dist["10+"] += 1

        # Top nodes by degree (hub nodes)
        node_degrees = [
            (r["id"], r["label"], out_deg.get(r["id"], 0) + in_deg.get(r["id"], 0))
            for r in nodes
        ]
        node_degrees.sort(key=lambda x: x[2], reverse=True)
        hubs = [
            {"id": nid, "label": label, "degree": deg}
            for nid, label, deg in node_degrees[:5]
        ]

        # Weight distribution
        weights = [r["weight"] for r in nodes]
        avg_weight = sum(weights) / len(weights) if weights else 0.0
        low_weight = sum(1 for w in weights if w < 0.3)
        high_weight = sum(1 for w in weights if w >= 0.7)

        # Q-value distribution
        q_values = [r["q_value"] for r in nodes if r["q_value"] != 0.0]
        avg_q = sum(q_values) / len(q_values) if q_values else 0.0

        # Kind distribution
        kind_counts = defaultdict(int)
        for r in nodes:
            kind_counts[r["kind"]] += 1

        # Orphan nodes (no edges)
        connected_ids = set()
        for e in edges:
            connected_ids.add(e["source"])
            connected_ids.add(e["target"])
        orphans = sum(1 for r in nodes if r["id"] not in connected_ids)
        orphan_ratio = orphans / n_count if n_count > 0 else 0.0

        # Reciprocal edges (A→B and B→A)
        edge_pairs = set()
        reciprocal = 0
        for e in edges:
            pair = (e["source"], e["target"])
            reverse = (e["target"], e["source"])
            if reverse in edge_pairs:
                reciprocal += 1
            edge_pairs.add(pair)

        # Memory health score [0, 1] — composite
        # Lower orphans, good avg weight, high connectivity → higher score
        connectivity_score = 1.0 - orphan_ratio if n_count > 0 else 0.0
        weight_score = min(avg_weight, 1.0)
        density_score = min(density * 10, 1.0)  # Scale: 0.1 density → full score
        health = (connectivity_score * 0.4 + weight_score * 0.3 + density_score * 0.3)

        # Relation distribution
        relation_counts = defaultdict(int)
        for e in edges:
            relation_counts[e["relation"]] += 1
        top_relations = sorted(relation_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "node_count": n_count,
            "edge_count": e_count,
            "density": round(density, 4),
            "avg_degree": round(avg_degree, 2),
            "max_degree": max_degree,
            "degree_distribution": deg_dist,
            "hub_nodes": hubs,
            "avg_weight": round(avg_weight, 4),
            "low_weight_count": low_weight,
            "high_weight_count": high_weight,
            "avg_q_value": round(avg_q, 4),
            "kind_distribution": dict(kind_counts),
            "orphan_nodes": orphans,
            "orphan_ratio": round(orphan_ratio, 4),
            "reciprocal_edges": reciprocal,
            "top_relations": [{"relation": r, "count": c} for r, c in top_relations],
            "memory_health": round(health, 4),
        }

    # ── Memory Diff ─────────────────────────────────────────

    def diff_graph(self, other: 'MemoryGraph') -> dict:
        """Compute the difference between this graph and another.

        Returns added/removed/changed nodes and edges, useful for
        audit trails, before/after comparisons, and memory evolution
        tracking.

        Args:
            other: The other MemoryGraph to diff against.

        Returns dict with:
            nodes_added, nodes_removed, nodes_changed,
            edges_added, edges_removed,
            summary: {added, removed, changed totals}
        """
        self_nodes = {
            r["id"]: r for r in self.conn.execute(
                "SELECT * FROM nodes WHERE quarantined=0"
            ).fetchall()
        }
        other_nodes = {
            r["id"]: r for r in other.conn.execute(
                "SELECT * FROM nodes WHERE quarantined=0"
            ).fetchall()
        }

        self_ids = set(self_nodes.keys())
        other_ids = set(other_nodes.keys())

        nodes_added = []
        for nid in other_ids - self_ids:
            r = other_nodes[nid]
            nodes_added.append({
                "id": nid, "label": r["label"], "kind": r["kind"],
                "weight": r["weight"],
            })

        nodes_removed = []
        for nid in self_ids - other_ids:
            r = self_nodes[nid]
            nodes_removed.append({
                "id": nid, "label": r["label"], "kind": r["kind"],
                "weight": r["weight"],
            })

        nodes_changed = []
        for nid in self_ids & other_ids:
            old = self_nodes[nid]
            new = other_nodes[nid]
            changes = {}
            if old["label"] != new["label"]:
                changes["label"] = {"old": old["label"], "new": new["label"]}
            if old["kind"] != new["kind"]:
                changes["kind"] = {"old": old["kind"], "new": new["kind"]}
            if abs(old["weight"] - new["weight"]) > 0.001:
                changes["weight"] = {"old": old["weight"], "new": new["weight"]}
            old_data = json.loads(old["data"])
            new_data = json.loads(new["data"])
            if old_data != new_data:
                changes["data_added"] = {k: v for k, v in new_data.items() if k not in old_data}
                changes["data_removed"] = {k: v for k, v in old_data.items() if k not in new_data}
            if changes:
                nodes_changed.append({
                    "id": nid,
                    "label": new["label"],
                    "changes": changes,
                })

        # Edge diff
        self_edges = {
            (r["source"], r["target"], r["relation"])
            for r in self.conn.execute("SELECT * FROM edges").fetchall()
        }
        other_edges = {
            (r["source"], r["target"], r["relation"])
            for r in other.conn.execute("SELECT * FROM edges").fetchall()
        }

        edges_added = [
            {"source": s, "target": t, "relation": r}
            for s, t, r in other_edges - self_edges
        ]
        edges_removed = [
            {"source": s, "target": t, "relation": r}
            for s, t, r in self_edges - other_edges
        ]

        return {
            "nodes_added": nodes_added,
            "nodes_removed": nodes_removed,
            "nodes_changed": nodes_changed,
            "edges_added": edges_added,
            "edges_removed": edges_removed,
            "summary": {
                "added": len(nodes_added) + len(edges_added),
                "removed": len(nodes_removed) + len(edges_removed),
                "changed": len(nodes_changed),
            },
        }

    def diff_report(self, diff: dict = None, other: 'MemoryGraph' = None) -> str:
        """Format a diff as a human-readable report.

        Either pass a pre-computed diff dict, or pass another graph
        to compute diff on the fly.
        """
        if diff is None:
            if other is None:
                raise ValueError("Provide either diff dict or other graph")
            diff = self.diff_graph(other)

        lines = []
        s = diff["summary"]
        lines.append(
            f"Memory Diff: +{s['added']} added, -{s['removed']} removed, ~{s['changed']} changed"
        )

        if diff["nodes_added"]:
            lines.append(f"\n  ▲ Nodes added ({len(diff['nodes_added'])}):")
            for n in diff["nodes_added"]:
                lines.append(f"    + [{n['kind']}] {n['label']} (w={n['weight']:.2f})")

        if diff["nodes_removed"]:
            lines.append(f"\n  ▼ Nodes removed ({len(diff['nodes_removed'])}):")
            for n in diff["nodes_removed"]:
                lines.append(f"    - [{n['kind']}] {n['label']} (w={n['weight']:.2f})")

        if diff["nodes_changed"]:
            lines.append(f"\n  ◆ Nodes changed ({len(diff['nodes_changed'])}):")
            for n in diff["nodes_changed"]:
                parts = [f"    ~ {n['label']}"]
                for field, change in n["changes"].items():
                    if isinstance(change, dict) and "old" in change:
                        parts.append(f"    {field}: {change['old']} → {change['new']}")
                    elif field == "data_added":
                        keys = list(change.keys())
                        parts.append(f"    data +{keys}")
                    elif field == "data_removed":
                        keys = list(change.keys())
                        parts.append(f"    data -{keys}")
                lines.append("\n".join(parts))

        if diff["edges_added"]:
            lines.append(f"\n  ▲ Edges added ({len(diff['edges_added'])}):")
            for e in diff["edges_added"][:10]:
                lines.append(f"    + {e['source'][:8]}→{e['target'][:8]} [{e['relation']}]")
            if len(diff["edges_added"]) > 10:
                lines.append(f"    ... and {len(diff['edges_added']) - 10} more")

        if diff["edges_removed"]:
            lines.append(f"\n  ▼ Edges removed ({len(diff['edges_removed'])}):")
            for e in diff["edges_removed"][:10]:
                lines.append(f"    - {e['source'][:8]}→{e['target'][:8]} [{e['relation']}]")
            if len(diff["edges_removed"]) > 10:
                lines.append(f"    ... and {len(diff['edges_removed']) - 10} more")

        if s["added"] == 0 and s["removed"] == 0 and s["changed"] == 0:
            lines.append("  (no changes)")

        return "\n".join(lines)

    # ─── Batch Operations ───────────────────────────────────────────

    def batch_create_nodes(self, nodes_data: list[dict]) -> dict:
        """Create multiple nodes in a single transaction.

        Each item in *nodes_data* must be a dict with keys:
            label (required), kind (default 'fact'), data (default {}),
            tags (default []), weight (default 1.0).

        Returns a dict with keys ``created`` (list of Node),
        ``skipped`` (list of error strings), and ``count``.
        """
        created: list[Node] = []
        skipped: list[str] = []
        now = time.time()
        for item in nodes_data:
            label = item.get("label")
            if not label:
                skipped.append(f"missing label: {item}")
                continue
            try:
                node = Node(
                    id=uuid.uuid4().hex[:12],
                    label=label,
                    kind=item.get("kind", "fact"),
                    data=item.get("data", {}),
                    created=now, accessed=now,
                    weight=item.get("weight", 1.0),
                )
                self.conn.execute(
                    "INSERT INTO nodes (id,label,kind,data,created,accessed,weight,tags) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (node.id, node.label, node.kind, json.dumps(node.data),
                     node.created, node.accessed, node.weight,
                     json.dumps(item.get("tags", []))),
                )
                self._fts_sync_node(node.id)
                created.append(node)
            except Exception as exc:
                skipped.append(f"{label}: {exc}")
        self.conn.commit()
        self._tick("batch_create_nodes", None, {"count": len(created)})
        return {"created": created, "skipped": skipped, "count": len(created)}

    def batch_add_edges(self, edges_data: list[dict]) -> dict:
        """Add multiple edges in a single transaction.

        Each item in *edges_data* must be a dict with keys:
            source (required), target (required), relation (required),
            weight (default 1.0).

        Source and target may be either node IDs or labels
        (resolved via ``link_by_label`` semantics: ID first, then label).

        Returns a dict with keys ``added``, ``skipped``, and ``count``.
        """
        added = 0
        skipped: list[str] = []
        for item in edges_data:
            src = item.get("source")
            tgt = item.get("target")
            rel = item.get("relation")
            if not src or not tgt or not rel:
                skipped.append(f"missing fields: {item}")
                continue
            w = item.get("weight", 1.0)
            # Try direct ID first, then label lookup
            src_row = self.conn.execute(
                "SELECT id FROM nodes WHERE id=? OR label=? ORDER BY created DESC LIMIT 1",
                (src, src),
            ).fetchone()
            tgt_row = self.conn.execute(
                "SELECT id FROM nodes WHERE id=? OR label=? ORDER BY created DESC LIMIT 1",
                (tgt, tgt),
            ).fetchone()
            if not src_row or not tgt_row:
                skipped.append(f"node not found: {src}→{tgt}")
                continue
            try:
                self.conn.execute(
                    "INSERT OR REPLACE INTO edges VALUES (?,?,?,?)",
                    (src_row["id"], tgt_row["id"], rel, w),
                )
                added += 1
            except Exception as exc:
                skipped.append(f"{src}→{tgt}: {exc}")
        self.conn.commit()
        self._tick("batch_add_edges", None, {"count": added})
        return {"added": added, "skipped": skipped, "count": added}

    def batch_delete_nodes(self, node_ids: list[str], safe: bool = True) -> dict:
        """Delete multiple nodes.  If *safe* is True, nodes with live
        dependents are skipped (uses ``delete_node_safe``).

        Returns dict with ``deleted``, ``skipped``, ``count``.
        """
        deleted: list[str] = []
        skipped: list[str] = []
        for nid in node_ids:
            if safe:
                result = self.delete_node_safe(nid)
                if result["deleted"]:
                    deleted.append(nid)
                else:
                    skipped.append(f"{nid}: {result.get('reason', 'unknown')}")
            else:
                if self.delete_node(nid):
                    deleted.append(nid)
                else:
                    skipped.append(f"{nid}: not found")
        return {"deleted": deleted, "skipped": skipped, "count": len(deleted)}

    # ─── Link Prediction ────────────────────────────────────────────

    def predict_links(self, node_id: str = None, limit: int = 10,
                      min_score: float = 0.0) -> list[dict]:
        """Suggest missing edges using common-neighbor heuristics.

        For each pair of nodes (u, v) that are **not** directly connected,
        compute a prediction score from three signals:

        * **Common Neighbors** — number of shared neighbors.
        * **Adamic-Adar** — sum of 1/log(degree(w)) over shared neighbors w.
        * **Preferential Attachment** — degree(u) × degree(v).

        The final ``score`` is a weighted blend
        (0.4·CN + 0.4·AA + 0.2·PA_normalised).

        Args:
            node_id: If given, only predict links *from* this node.
                     If None, scan all nodes (may be slow on large graphs).
            limit: Maximum number of suggestions.
            min_score: Filter out predictions below this threshold.

        Returns a list of dicts sorted by score descending, each with keys:
            ``source``, ``target``, ``source_label``, ``target_label``,
            ``common_neighbors``, ``adamic_adar``, ``preferential_attachment``,
            ``score``.
        """
        # Build adjacency sets (undirected for neighbor computation)
        rows = self.conn.execute(
            "SELECT source, target FROM edges"
        ).fetchall()
        adj: dict[str, set[str]] = {}
        for r in rows:
            adj.setdefault(r["source"], set()).add(r["target"])
            adj.setdefault(r["target"], set()).add(r["source"])

        # Compute degree for every node
        all_nodes = set()
        for s, ts in adj.items():
            all_nodes.add(s)
            all_nodes |= ts
        # Include isolated nodes too
        node_rows = self.conn.execute("SELECT id FROM nodes").fetchall()
        for nr in node_rows:
            all_nodes.add(nr["id"])

        degree = {n: len(adj.get(n, set())) for n in all_nodes}

        import math

        # Determine source set
        sources = [node_id] if node_id else list(all_nodes)

        predictions: list[dict] = []
        seen_pairs: set[frozenset] = set()

        for u in sources:
            neighbors_u = adj.get(u, set())
            for v in all_nodes:
                if v == u:
                    continue
                pair = frozenset({u, v})
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                # Skip already-connected pairs
                if v in neighbors_u:
                    continue
                # Compute scores
                neighbors_v = adj.get(v, set())
                common = neighbors_u & neighbors_v
                cn = len(common)
                if cn == 0 and degree[u] * degree[v] == 0:
                    continue
                aa = sum(
                    1.0 / math.log(degree[w])
                    for w in common
                    if degree[w] > 1
                )
                pa = degree[u] * degree[v]
                # Normalise PA: divide by max possible (N-1)^2
                n_total = len(all_nodes)
                pa_norm = pa / ((n_total - 1) ** 2) if n_total > 1 else 0.0
                score = 0.4 * cn + 0.4 * aa + 0.2 * pa_norm
                if score <= min_score:
                    continue
                predictions.append({
                    "source": u,
                    "target": v,
                    "common_neighbors": cn,
                    "adamic_adar": round(aa, 4),
                    "preferential_attachment": pa,
                    "score": round(score, 4),
                })

        predictions.sort(key=lambda p: p["score"], reverse=True)

        # Resolve labels and truncate
        label_cache: dict[str, str] = {}
        for p in predictions[:limit]:
            for key in ("source", "target"):
                nid = p[key]
                if nid not in label_cache:
                    row = self.conn.execute(
                        "SELECT label FROM nodes WHERE id=?", (nid,)
                    ).fetchone()
                    label_cache[nid] = row["label"] if row else nid
                p[f"{key}_label"] = label_cache[nid]

        return predictions[:limit]

    # ─── Weighted Shortest Path (Dijkstra) ──────────────────────────

    def shortest_path_weighted(self, source_id: str, target_id: str,
                                default_weight: float = 1.0) -> Optional[dict]:
        """Find the minimum-cost path between two nodes using edge weights.

        Uses Dijkstra's algorithm.  Unlike ``shortest_path`` (BFS by hops),
        this accounts for edge ``weight`` values so that a 3-hop path
        through low-weight edges may beat a 2-hop path through high-weight
        edges.

        Args:
            source_id: Starting node ID.
            target_id: Ending node ID.
            default_weight: Weight to use if an edge has no weight column
                            or weight is NULL (default 1.0).

        Returns ``None`` if no path exists, otherwise a dict with:
            ``path`` (list of node IDs), ``cost`` (total weight),
            ``hops`` (number of edges).
        """
        if source_id == target_id:
            return {"path": [source_id], "cost": 0.0, "hops": 0}

        import heapq

        # Build weighted adjacency (directed)
        rows = self.conn.execute(
            "SELECT source, target, weight FROM edges"
        ).fetchall()
        adj: dict[str, list[tuple[str, float]]] = {}
        for r in rows:
            w = r["weight"] if r["weight"] is not None else default_weight
            adj.setdefault(r["source"], []).append((r["target"], w))

        # Dijkstra
        dist: dict[str, float] = {source_id: 0.0}
        prev: dict[str, str] = {}
        visited: set[str] = set()
        pq: list[tuple[float, str]] = [(0.0, source_id)]

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            if u == target_id:
                break
            for v, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))

        if target_id not in dist:
            return None

        # Reconstruct path
        path = [target_id]
        cur = target_id
        while cur != source_id:
            cur = prev[cur]
            path.append(cur)
        path.reverse()

        return {"path": path, "cost": round(dist[target_id], 6), "hops": len(path) - 1}

    def path_cost(self, path: list[str]) -> float:
        """Compute the total weight of a given node-ID path.

        Returns ``inf`` if any edge in the path does not exist.
        """
        if len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(len(path) - 1):
            row = self.conn.execute(
                "SELECT weight FROM edges WHERE source=? AND target=? "
                "ORDER BY weight ASC LIMIT 1",
                (path[i], path[i + 1]),
            ).fetchone()
            if not row:
                return float('inf')
            total += row["weight"] if row["weight"] is not None else 1.0
        return round(total, 6)

    # ─── Path Enumeration ───────────────────────────────────────────

    def all_paths(self, source_id: str, target_id: str,
                  max_hops: int = 5, limit: int = 20) -> list[list[str]]:
        """Find all simple paths (no repeated nodes) between two nodes.

        Uses DFS with pruning at *max_hops*.  Returns a list of paths
        (each a list of node IDs), sorted by length (shortest first).
        Limited to *limit* results to prevent combinatorial explosion.

        Args:
            source_id: Starting node ID.
            target_id: Ending node ID.
            max_hops: Maximum number of edges in a path.
            limit: Maximum number of paths to return.

        Returns an empty list if no path exists or nodes don't exist.
        """
        # Verify nodes exist
        for nid in (source_id, target_id):
            if not self.conn.execute(
                "SELECT 1 FROM nodes WHERE id=?", (nid,)
            ).fetchone():
                return []

        if source_id == target_id:
            return [[source_id]]

        # Build adjacency
        rows = self.conn.execute(
            "SELECT source, target FROM edges"
        ).fetchall()
        adj: dict[str, list[str]] = {}
        for r in rows:
            adj.setdefault(r["source"], []).append(r["target"])

        results: list[list[str]] = []

        def _dfs(current: str, path: list[str], visited: set[str]):
            if len(results) >= limit:
                return
            if len(path) - 1 >= max_hops:
                return
            for neighbor in adj.get(current, []):
                if neighbor == target_id:
                    results.append(path + [neighbor])
                    if len(results) >= limit:
                        return
                    continue
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                _dfs(neighbor, path + [neighbor], visited)
                visited.discard(neighbor)

        _dfs(source_id, [source_id], {source_id})
        results.sort(key=len)
        return results

    def k_shortest_paths(self, source_id: str, target_id: str,
                         k: int = 3, max_hops: int = 8) -> list[dict]:
        """Find the K lowest-cost simple paths between two nodes.

        Uses Yen's algorithm (simplified): repeatedly find shortest path,
        then spur from deviations.

        Args:
            source_id: Starting node ID.
            target_id: Ending node ID.
            k: Number of paths to find.
            max_hops: Maximum path length to consider.

        Returns a list of dicts with ``path``, ``cost``, ``hops``
        sorted by cost ascending.  May return fewer than *k* if not
        enough paths exist.
        """
        # Get candidate paths via all_paths
        candidates = self.all_paths(source_id, target_id,
                                     max_hops=max_hops, limit=k * 5)
        if not candidates:
            return []

        # Score each path by cost
        scored: list[dict] = []
        for p in candidates:
            cost = self.path_cost(p)
            if cost == float('inf'):
                continue
            scored.append({"path": p, "cost": cost, "hops": len(p) - 1})

        scored.sort(key=lambda x: x["cost"])
        return scored[:k]

    # ─────────────────────────────────────────────
    # Cycle 192: Subgraph Extraction
    # ─────────────────────────────────────────────

    def extract_subgraph(self, node_id: str, radius: int = 1,
                         max_nodes: int = 100,
                         include_quarantined: bool = False) -> 'MemoryGraph':
        """Extract a neighborhood subgraph around *node_id*.

        Performs BFS up to *radius* hops, collecting all reachable nodes
        and the edges between them.  Returns a **new** MemoryGraph instance
        containing only the extracted subset.

        Args:
            node_id: Centre node for extraction.
            radius: Maximum hop distance (1 = immediate neighbours).
            max_nodes: Safety cap to avoid extracting huge subgraphs.
            include_quarantined: If False, skip quarantined nodes.

        Returns a new MemoryGraph.  Raises ValueError if *node_id* not found.
        """
        if not self.conn.execute(
            "SELECT 1 FROM nodes WHERE id=?", (node_id,)
        ).fetchone():
            raise ValueError(f"Node not found: {node_id}")

        # BFS to collect node IDs within radius
        visited: set[str] = set()
        frontier: set[str] = {node_id}
        for hop in range(radius + 1):
            if not frontier or len(visited) >= max_nodes:
                break
            next_frontier: set[str] = set()
            for nid in frontier:
                if nid in visited or len(visited) >= max_nodes:
                    continue
                # Skip quarantined unless explicitly included
                if not include_quarantined and self._is_quarantined(nid):
                    continue
                visited.add(nid)
                # Get neighbors (both directions)
                for r in self.conn.execute(
                    "SELECT target FROM edges WHERE source=?", (nid,)
                ).fetchall():
                    if r["target"] not in visited:
                        next_frontier.add(r["target"])
                for r in self.conn.execute(
                    "SELECT source FROM edges WHERE target=?", (nid,)
                ).fetchall():
                    if r["source"] not in visited:
                        next_frontier.add(r["source"])
            frontier = next_frontier

        # Build subgraph
        sub = MemoryGraph()
        # Copy nodes
        for nid in visited:
            row = self.conn.execute(
                "SELECT * FROM nodes WHERE id=?", (nid,)
            ).fetchone()
            if row is None:
                continue
            sub.conn.execute(
                """INSERT OR REPLACE INTO nodes
                   (id,label,kind,data,created,accessed,weight,tags,
                    source,trust_level,parents,quarantined,quarantine_reason,
                    valid_from,valid_to,txn_time,q_value)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (row["id"], row["label"], row["kind"], row["data"],
                 row["created"], row["accessed"], row["weight"], row["tags"],
                 row["source"], row["trust_level"], row["parents"],
                 row["quarantined"], row["quarantine_reason"],
                 row["valid_from"], row["valid_to"], row["txn_time"],
                 row["q_value"])
            )
        # Copy edges between visited nodes
        for r in self.conn.execute("SELECT * FROM edges").fetchall():
            if r["source"] in visited and r["target"] in visited:
                sub.conn.execute(
                    "INSERT OR REPLACE INTO edges (source,target,relation,weight) VALUES (?,?,?,?)",
                    (r["source"], r["target"], r["relation"], r["weight"])
                )
        # Copy edge props
        for r in self.conn.execute("SELECT * FROM edge_props").fetchall():
            if r["source"] in visited and r["target"] in visited:
                sub.conn.execute(
                    "INSERT OR REPLACE INTO edge_props (source,target,relation,properties) VALUES (?,?,?,?)",
                    (r["source"], r["target"], r["relation"], r["properties"])
                )
        # Rebuild FTS
        sub._rebuild_fts()
        sub.conn.commit()
        return sub

    def neighborhood(self, node_id: str, radius: int = 1,
                     include_quarantined: bool = False) -> list[str]:
        """Return node IDs within *radius* hops of *node_id*.

        Lightweight alternative to :meth:`extract_subgraph` when you only
        need the ID list, not a full subgraph copy.

        Args:
            node_id: Centre node.
            radius: Maximum hop distance.
            include_quarantined: If False, skip quarantined nodes.

        Returns a list of node IDs (including *node_id* itself).
        Raises ValueError if node not found.
        """
        if not self.conn.execute(
            "SELECT 1 FROM nodes WHERE id=?", (node_id,)
        ).fetchone():
            raise ValueError(f"Node not found: {node_id}")

        visited: set[str] = set()
        frontier: set[str] = {node_id}
        for hop in range(radius + 1):
            if not frontier:
                break
            next_frontier: set[str] = set()
            for nid in frontier:
                if nid in visited:
                    continue
                if not include_quarantined and self._is_quarantined(nid):
                    continue
                visited.add(nid)
                for r in self.conn.execute(
                    "SELECT target FROM edges WHERE source=?", (nid,)
                ).fetchall():
                    if r["target"] not in visited:
                        next_frontier.add(r["target"])
                for r in self.conn.execute(
                    "SELECT source FROM edges WHERE target=?", (nid,)
                ).fetchall():
                    if r["source"] not in visited:
                        next_frontier.add(r["source"])
            frontier = next_frontier
        return sorted(visited)

    def _rebuild_fts(self):
        """Rebuild the FTS5 index from the nodes table."""
        if not getattr(self, '_fts_enabled', False):
            return
        self.conn.execute("DELETE FROM nodes_fts")
        for row in self.conn.execute("SELECT id,label,kind,data,tags FROM nodes").fetchall():
            self.conn.execute(
                "INSERT INTO nodes_fts (node_id,label,kind,data,tags) VALUES (?,?,?,?,?)",
                (row["id"], row["label"], row["kind"], row["data"], row["tags"])
            )

    # ─────────────────────────────────────────────
    # Cycle 193: Centrality Metrics
    # ─────────────────────────────────────────────

    def betweenness_all(self, normalized: bool = True,
                        include_quarantined: bool = False) -> dict[str, float]:
        """Compute betweenness centrality for all nodes (Brandes' algorithm).

        Betweenness = how many shortest paths pass through a node.
        High-betweenness nodes are "bridges" connecting different parts
        of the graph.

        Args:
            normalized: If True, divide by (N-1)(N-2)/2 for undirected.
            include_quarantined: If False, skip quarantined nodes.

        Returns {node_id: centrality_score}.
        """
        # Gather active node IDs
        if include_quarantined:
            node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        else:
            node_ids = [r["id"] for r in self.conn.execute(
                "SELECT id FROM nodes WHERE quarantined=0"
            ).fetchall()]
        n = len(node_ids)
        if n < 3:
            return {nid: 0.0 for nid in node_ids}

        # Build adjacency (undirected for centrality)
        node_set = set(node_ids)
        adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
        for r in self.conn.execute("SELECT source, target FROM edges").fetchall():
            s, t = r["source"], r["target"]
            if s in node_set and t in node_set:
                adj[s].append(t)
                adj[t].append(s)  # treat as undirected

        # Brandes' algorithm
        centrality: dict[str, float] = {nid: 0.0 for nid in node_ids}
        for s in node_ids:
            # Single-source BFS
            stack: list[str] = []
            pred: dict[str, list[str]] = {nid: [] for nid in node_ids}
            sigma: dict[str, float] = {nid: 0.0 for nid in node_ids}
            sigma[s] = 1.0
            dist: dict[str, int] = {nid: -1 for nid in node_ids}
            dist[s] = 0
            queue: list[str] = [s]
            while queue:
                v = queue.pop(0)
                stack.append(v)
                for w in adj[v]:
                    if dist[w] < 0:
                        queue.append(w)
                        dist[w] = dist[v] + 1
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)
            # Accumulation
            delta: dict[str, float] = {nid: 0.0 for nid in node_ids}
            while stack:
                w = stack.pop()
                for v in pred[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                if w != s:
                    centrality[w] += delta[w]

        # For undirected graphs, each pair is counted twice; halve
        for nid in centrality:
            centrality[nid] /= 2.0
        # Normalize (standard undirected normalization)
        if normalized and n > 2:
            factor = 2.0 / ((n - 1) * (n - 2))
            for nid in centrality:
                centrality[nid] *= factor

        return centrality

    def closeness_all(self, normalized: bool = True,
                      include_quarantined: bool = False) -> dict[str, float]:
        """Compute closeness centrality for all nodes.

        Closeness = reciprocal of average shortest-path distance to all
        other reachable nodes.  High-closeness nodes can reach the rest
        of the graph quickly.

        Uses multi-source BFS.  Disconnected nodes get 0.

        Args:
            normalized: If True, multiply by (reachable_count / (N-1)).
            include_quarantined: If False, skip quarantined nodes.

        Returns {node_id: centrality_score}.
        """
        if include_quarantined:
            node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        else:
            node_ids = [r["id"] for r in self.conn.execute(
                "SELECT id FROM nodes WHERE quarantined=0"
            ).fetchall()]
        n = len(node_ids)
        if n < 2:
            return {nid: 1.0 for nid in node_ids}

        node_set = set(node_ids)
        adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
        for r in self.conn.execute("SELECT source, target FROM edges").fetchall():
            s, t = r["source"], r["target"]
            if s in node_set and t in node_set:
                adj[s].append(t)
                adj[t].append(s)

        centrality: dict[str, float] = {}
        for s in node_ids:
            # BFS distances
            dist: dict[str, int] = {s: 0}
            queue: list[str] = [s]
            total_dist = 0
            reachable = 0
            while queue:
                v = queue.pop(0)
                for w in adj[v]:
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        total_dist += dist[w]
                        reachable += 1
                        queue.append(w)
            if total_dist == 0:
                centrality[s] = 0.0
            else:
                cc = reachable / total_dist
                if normalized:
                    cc *= reachable / (n - 1)
                centrality[s] = cc

        return centrality

    def eigenvector_all(self, iterations: int = 100,
                         tolerance: float = 1e-6,
                         include_quarantined: bool = False) -> dict[str, float]:
        """Compute eigenvector centrality for all nodes via power iteration.

        High-eigenvector nodes are those connected to other high-scoring
        nodes.  Identifies the "core" of influential memories.

        Args:
            iterations: Max power-iteration steps.
            tolerance: Convergence threshold (L1 norm).
            include_quarantined: If False, skip quarantined nodes.

        Returns {node_id: centrality_score}.  Empty dict if graph is empty.
        """
        if include_quarantined:
            node_ids = [r["id"] for r in self.conn.execute("SELECT id FROM nodes").fetchall()]
        else:
            node_ids = [r["id"] for r in self.conn.execute(
                "SELECT id FROM nodes WHERE quarantined=0"
            ).fetchall()]
        n = len(node_ids)
        if n == 0:
            return {}
        if n == 1:
            return {node_ids[0]: 1.0}

        node_set = set(node_ids)
        adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
        for r in self.conn.execute("SELECT source, target FROM edges").fetchall():
            s, t = r["source"], r["target"]
            if s in node_set and t in node_set:
                adj[s].append(t)
                adj[t].append(s)

        # Power iteration
        centrality = {nid: 1.0 / n for nid in node_ids}
        for _ in range(iterations):
            new_c = {nid: 0.0 for nid in node_ids}
            for v in node_ids:
                for w in adj[v]:
                    new_c[w] += centrality[v]
            # Normalize
            norm = sum(v * v for v in new_c.values()) ** 0.5
            if norm == 0:
                break
            new_c = {nid: v / norm for nid, v in new_c.items()}
            # Check convergence
            diff = sum(abs(new_c[nid] - centrality[nid]) for nid in node_ids)
            centrality = new_c
            if diff < tolerance:
                break

        return centrality

    # ─────────────────────────────────────────────
    # Cycle 194: Graph Merge & Serialization
    # ─────────────────────────────────────────────

    def merge_graph(self, other: 'MemoryGraph',
                    strategy: str = "union",
                    prefix: str = None,
                    on_conflict: str = "keep_both") -> dict:
        """Merge another MemoryGraph into this one.

        Useful for multi-agent memory fusion: each agent maintains its
        own graph, then merges results.

        Args:
            other: The graph to merge FROM.
            strategy: "union" (all nodes/edges) or "intersection"
                      (only nodes that exist in both, plus other's edges).
            prefix: If given, prefix other's node IDs with this string
                    to avoid ID collisions (e.g. "agent2_").
            on_conflict: "keep_both" (add with prefixed ID),
                         "skip" (don't add conflicting IDs),
                         "overwrite" (replace local data).

        Returns a dict with merge stats:
            nodes_added, nodes_skipped, edges_added, edges_skipped
        """
        stats = {"nodes_added": 0, "nodes_skipped": 0,
                 "edges_added": 0, "edges_skipped": 0}

        # Build ID mapping (other_id → target_id in self)
        id_map: dict[str, str] = {}

        if strategy == "intersection":
            # Only include nodes that already exist in self (by label match)
            local_labels = {r["label"]: r["id"] for r in
                            self.conn.execute("SELECT id, label FROM nodes").fetchall()}
            for row in other.conn.execute("SELECT * FROM nodes").fetchall():
                if row["label"] in local_labels:
                    id_map[row["id"]] = local_labels[row["label"]]
            # Only map edges between intersection nodes
            for r in other.conn.execute("SELECT * FROM edges").fetchall():
                if r["source"] in id_map and r["target"] in id_map:
                    try:
                        self.conn.execute(
                            "INSERT OR IGNORE INTO edges (source,target,relation,weight) VALUES (?,?,?,?)",
                            (id_map[r["source"]], id_map[r["target"]], r["relation"], r["weight"])
                        )
                        if self.conn.total_changes > 0:
                            stats["edges_added"] += 1
                        else:
                            stats["edges_skipped"] += 1
                    except sqlite3.IntegrityError:
                        stats["edges_skipped"] += 1
            self.conn.commit()
            self._rebuild_fts()
            return stats

        # Union strategy
        for row in other.conn.execute("SELECT * FROM nodes").fetchall():
            other_id = row["id"]
            # Check if ID collides
            existing = self.conn.execute(
                "SELECT 1 FROM nodes WHERE id=?", (other_id,)
            ).fetchone()

            if existing and prefix is None:
                # ID collision without prefix
                if on_conflict == "skip":
                    id_map[other_id] = other_id
                    stats["nodes_skipped"] += 1
                    continue
                elif on_conflict == "overwrite":
                    self.conn.execute(
                        """UPDATE nodes SET label=?, kind=?, data=?, weight=?, tags=?,
                           source=?, trust_level=?, q_value=?
                           WHERE id=?""",
                        (row["label"], row["kind"], row["data"],
                         row["weight"], row["tags"],
                         row["source"], row["trust_level"],
                         row["q_value"], other_id)
                    )
                    id_map[other_id] = other_id
                    stats["nodes_added"] += 1
                    continue
                # keep_both: fall through to prefix logic

            # Determine target ID
            target_id = f"{prefix}{other_id}" if prefix else other_id
            if existing and on_conflict == "keep_both" and prefix is None:
                # Auto-generate prefix to avoid collision
                target_id = f"m_{other_id}"

            id_map[other_id] = target_id

            # Insert node
            self.conn.execute(
                """INSERT OR REPLACE INTO nodes
                   (id,label,kind,data,created,accessed,weight,tags,
                    source,trust_level,parents,quarantined,quarantine_reason,
                    valid_from,valid_to,txn_time,q_value)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (target_id, row["label"], row["kind"], row["data"],
                 row["created"], row["accessed"], row["weight"], row["tags"],
                 row["source"], row["trust_level"], row["parents"],
                 row["quarantined"], row["quarantine_reason"],
                 row["valid_from"], row["valid_to"], row["txn_time"],
                 row["q_value"])
            )
            stats["nodes_added"] += 1

        # Copy edges (using ID mapping)
        for r in other.conn.execute("SELECT * FROM edges").fetchall():
            src = id_map.get(r["source"])
            tgt = id_map.get(r["target"])
            if src is None or tgt is None:
                stats["edges_skipped"] += 1
                continue
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO edges (source,target,relation,weight) VALUES (?,?,?,?)",
                    (src, tgt, r["relation"], r["weight"])
                )
                if self.conn.total_changes > 0:
                    stats["edges_added"] += 1
                else:
                    stats["edges_skipped"] += 1
            except sqlite3.IntegrityError:
                stats["edges_skipped"] += 1

        # Copy edge props
        for r in other.conn.execute("SELECT * FROM edge_props").fetchall():
            src = id_map.get(r["source"])
            tgt = id_map.get(r["target"])
            if src and tgt:
                self.conn.execute(
                    "INSERT OR REPLACE INTO edge_props (source,target,relation,properties) VALUES (?,?,?,?)",
                    (src, tgt, r["relation"], r["properties"])
                )

        self.conn.commit()
        self._rebuild_fts()
        return stats

    def to_dict(self) -> dict:
        """Serialize the graph to a plain dict (JSON-safe).

        Includes all nodes, edges, and edge_props.
        Useful for snapshotting, API responses, or inter-agent transfer.

        Returns a dict with 'nodes', 'edges', 'edge_props', 'meta'.
        """
        nodes = []
        for r in self.conn.execute("SELECT * FROM nodes").fetchall():
            nodes.append({
                "id": r["id"], "label": r["label"], "kind": r["kind"],
                "data": json.loads(r["data"]), "created": r["created"],
                "accessed": r["accessed"], "weight": r["weight"],
                "tags": json.loads(r["tags"]),
                "quarantined": bool(r["quarantined"]),
                "q_value": r["q_value"],
            })
        edges = []
        for r in self.conn.execute("SELECT * FROM edges").fetchall():
            edges.append({
                "source": r["source"], "target": r["target"],
                "relation": r["relation"], "weight": r["weight"],
            })
        return {
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryGraph':
        """Deserialize a graph from a dict produced by :meth:`to_dict`.

        Creates a new in-memory MemoryGraph and populates it.
        """
        mg = cls()
        for n in data.get("nodes", []):
            mg.conn.execute(
                """INSERT OR REPLACE INTO nodes
                   (id,label,kind,data,created,accessed,weight,tags)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (n["id"], n["label"], n.get("kind", "fact"),
                 json.dumps(n.get("data", {})),
                 n.get("created", time.time()), n.get("accessed", time.time()),
                 n.get("weight", 1.0), json.dumps(n.get("tags", [])))
            )
        for e in data.get("edges", []):
            mg.conn.execute(
                "INSERT OR IGNORE INTO edges (source,target,relation,weight) VALUES (?,?,?,?)",
                (e["source"], e["target"], e["relation"], e.get("weight", 1.0))
            )
        mg.conn.commit()
        if getattr(mg, '_fts_enabled', False):
            mg._rebuild_fts()
        return mg

    # ─────────────────────────────────────────────
    # Cycle 195: Graph Contraction (Supernode Collapse)
    # ─────────────────────────────────────────────

    def contract_nodes(self, node_ids: list[str],
                       supernode_label: str,
                       kind: str = "supernode",
                       data: dict = None,
                       quarantine_members: bool = True) -> dict:
        """Collapse a set of nodes into a single supernode.

        External edges to/from any member node are redirected to the
        supernode with aggregated weights (sum).  Internal edges between
        contracted members are dropped (not converted to self-loops).

        Use cases:
        - Multi-resolution graph views (collapse communities)
        - Entity merging / deduplication
        - Abstraction hierarchies

        Args:
            node_ids: IDs of nodes to contract (must exist).
            supernode_label: Label for the new supernode.
            kind: Kind for the supernode (default "supernode").
            data: Optional extra data to set on the supernode.
                  Member node data is merged under "contracted_from".
            quarantine_members: If True, quarantine member nodes
                                (preserving audit trail) instead of deleting.

        Returns a dict:
            supernode_id, member_ids, edges_redirected, internal_edges_dropped
        """
        # Validate	node_ids
        existing = set()
        for nid in node_ids:
            row = self.conn.execute(
                "SELECT id FROM nodes WHERE id = ?", (nid,)
            ).fetchone()
            if row:
                existing.add(nid)
        if len(existing) < 2:
            return {"supernode_id": None, "error": "Need ≥2 existing nodes to contract"}

        member_ids = list(existing)
        member_set = set(member_ids)

        # Create supernode
        sn = self.add(supernode_label, kind=kind,
                      data=data or {}, tags=["contracted"])

        # Merge member data
        contracted_from = {}
        for nid in member_ids:
            row = self.conn.execute(
                "SELECT label, kind, data, weight FROM nodes WHERE id = ?", (nid,)
            ).fetchone()
            if row:
                contracted_from[nid] = {
                    "label": row["label"],
                    "kind": row["kind"],
                    "weight": row["weight"],
                }
        sn_member_data = json.loads(
            self.conn.execute("SELECT data FROM nodes WHERE id = ?", (sn.id,)).fetchone()["data"]
        )
        sn_member_data["contracted_from"] = contracted_from
        self.conn.execute(
            "UPDATE nodes SET data = ? WHERE id = ?",
            (json.dumps(sn_member_data), sn.id)
        )

        edges_redirected = 0
        internal_edges_dropped = 0

        # Redirect external edges → supernode
        edges_to_process = []
        for nid in member_ids:
            for r in self.conn.execute(
                "SELECT source, target, relation, weight FROM edges WHERE source = ? OR target = ?",
                (nid, nid)
            ).fetchall():
                edges_to_process.append(dict(r))

        seen_edge_keys = {}  # (new_source, new_target, relation) → summed weight
        seen_internal = set()  # (src, tgt, rel) dedup for internal edges

        for e in edges_to_process:
            src, tgt, rel, w = e["source"], e["target"], e["relation"], e["weight"]
            is_internal = src in member_set and tgt in member_set
            if is_internal:
                # Count each internal edge once (skip duplicates from reverse scan)
                ikey = (src, tgt, rel)
                if ikey not in seen_internal:
                    internal_edges_dropped += 1
                    seen_internal.add(ikey)
                continue
            # Map endpoints
            new_src = sn.id if src in member_set else src
            new_tgt = sn.id if tgt in member_set else tgt
            key = (new_src, new_tgt, rel)
            if key in seen_edge_keys:
                seen_edge_keys[key] += w
            else:
                seen_edge_keys[key] = w
            edges_redirected += 1

        # Write aggregated edges
        for (new_src, new_tgt, rel), total_w in seen_edge_keys.items():
            self.conn.execute(
                """INSERT INTO edges (source, target, relation, weight)
                   VALUES (?,?,?,?)
                   ON CONFLICT(source,target,relation) DO UPDATE SET weight = weight + ?""",
                (new_src, new_tgt, rel, total_w, total_w)
            )
            # Merge edge props if any
            for old_nid in member_ids:
                old_src = old_nid if new_src == sn.id else new_src
                old_tgt = old_nid if new_tgt == sn.id else new_tgt
                prop_row = self.conn.execute(
                    "SELECT properties FROM edge_props WHERE source=? AND target=? AND relation=?",
                    (old_src, old_tgt, rel)
                ).fetchone()
                if prop_row:
                    props = json.loads(prop_row["properties"])
                    if props:
                        existing_prop = self.conn.execute(
                            "SELECT properties FROM edge_props WHERE source=? AND target=? AND relation=?",
                            (new_src, new_tgt, rel)
                        ).fetchone()
                        merged = json.loads(existing_prop["properties"]) if existing_prop else {}
                        merged.update(props)
                        self.conn.execute(
                            """INSERT OR REPLACE INTO edge_props (source,target,relation,properties)
                               VALUES (?,?,?,?)""",
                            (new_src, new_tgt, rel, json.dumps(merged))
                        )

        # Remove old edges touching members
        for nid in member_ids:
            self.conn.execute(
                "DELETE FROM edges WHERE source = ? OR target = ?", (nid, nid)
            )
            self.conn.execute(
                "DELETE FROM edge_props WHERE source = ? OR target = ?", (nid, nid)
            )

        # Quarantine or delete members
        if quarantine_members:
            for nid in member_ids:
                self.conn.execute(
                    """UPDATE nodes SET quarantined = 1, quarantine_reason = ?
                       WHERE id = ?""",
                    (f"contracted into {sn.id}", nid)
                )

        self.conn.commit()
        self._rebuild_fts()

        # Emit event
        self._emit("contract", {
            "supernode_id": sn.id,
            "member_ids": member_ids,
            "edges_redirected": edges_redirected,
        })

        return {
            "supernode_id": sn.id,
            "member_ids": member_ids,
            "edges_redirected": edges_redirected,
            "internal_edges_dropped": internal_edges_dropped,
        }

    def contract_communities(self, labels: list[str] = None,
                             max_iterations: int = 20,
                             resolution: float = 1.0) -> dict:
        """Detect communities and contract each into a supernode.

        Runs LPA community detection, then collapses each community
        into a single supernode.  Useful for multi-resolution analysis
        and graph summarisation.

        Args:
            labels: Optional list of labels for supernodes (one per
                    community).  If shorter than community count or None,
                    auto-generated as "community_N".
            max_iterations: Max LPA iterations.
            resolution: LPA resolution parameter.

        Returns a dict:
            communities_found, supernode_ids, total_edges_redirected
        """
        # Only contract non-quarantined nodes
        active_nodes = [
            r["id"] for r in self.conn.execute(
                "SELECT id FROM nodes WHERE quarantined = 0"
            ).fetchall()
        ]
        if len(active_nodes) < 2:
            return {"communities_found": 0, "supernode_ids": [], "total_edges_redirected": 0}

        result = self.detect_communities(
            max_iterations=max_iterations, resolution=resolution
        )
        partition = result.get("node_community", {})

        # Group node IDs by community
        comm_groups = defaultdict(list)
        for nid, cid in partition.items():
            if nid in active_nodes:
                comm_groups[cid].append(nid)

        # Only contract communities with ≥2 members
        comm_groups = {k: v for k, v in comm_groups.items() if len(v) >= 2}

        supernode_ids = []
        total_redirected = 0

        for i, (cid, nids) in enumerate(sorted(comm_groups.items())):
            label = labels[i] if labels and i < len(labels) else f"community_{cid}"
            r = self.contract_nodes(nids, label, kind="community_supernode")
            if r.get("supernode_id"):
                supernode_ids.append(r["supernode_id"])
                total_redirected += r.get("edges_redirected", 0)

        return {
            "communities_found": len(comm_groups),
            "supernode_ids": supernode_ids,
            "total_edges_redirected": total_redirected,
        }

    # ── Cycle Path Detection ─────────────────────────────────────

    def find_cycle(self) -> Optional[list[str]]:
        """Find and return a cycle path in the graph (directed edges).

        Uses DFS with an explicit stack to track the current path.
        When a back-edge is found (neighbor is on the current path),
        the cycle is extracted from the path stack.

        Returns:
            A list of node IDs representing the cycle, where the first
            and last elements are equal (closed path), e.g. [A, B, C, A].
            None if no cycle exists.

        Quarantined nodes are excluded.
        """
        nodes = [
            str(r["id"]) for r in self.conn.execute(
                "SELECT id FROM nodes WHERE quarantined = 0"
            ).fetchall()
        ]
        if not nodes:
            return None

        adj: dict[str, list[str]] = {}
        for r in self.conn.execute(
            "SELECT source, target FROM edges "
            "WHERE source IN (SELECT id FROM nodes WHERE quarantined = 0) "
            "AND target IN (SELECT id FROM nodes WHERE quarantined = 0)"
        ).fetchall():
            adj.setdefault(str(r["source"]), []).append(str(r["target"]))

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in nodes}
        parent: dict[str, Optional[str]] = {nid: None for nid in nodes}

        for start in nodes:
            if color[start] != WHITE:
                continue
            stack = [(start, iter(adj.get(start, [])))]
            color[start] = GRAY
            path = [start]

            while stack:
                node, it = stack[-1]
                advanced = False
                for nb in it:
                    if color.get(nb, WHITE) == GRAY:
                        # Found back-edge → extract cycle
                        cycle_start_idx = path.index(nb)
                        cycle = path[cycle_start_idx:] + [nb]
                        return cycle
                    if color.get(nb, WHITE) == WHITE:
                        color[nb] = GRAY
                        stack.append((nb, iter(adj.get(nb, []))))
                        path.append(nb)
                        advanced = True
                        break
                if not advanced:
                    color[node] = BLACK
                    stack.pop()
                    path.pop()

        return None

    # ── Graph Periphery ──────────────────────────────────────────

    def graph_periphery(self) -> Optional[list[str]]:
        """Return nodes with maximum eccentricity (= graph diameter).

        The periphery consists of the "most distant" nodes in the graph —
        those whose shortest path to some other node equals the diameter.
        Complementary to graph_center() (nodes with eccentricity = radius).

        Returns:
            List of node IDs with eccentricity equal to the diameter.
            None for an empty graph.

        Quarantined nodes are excluded.
        """
        rows = self.conn.execute(
            "SELECT id FROM nodes WHERE quarantined = 0"
        ).fetchall()
        if not rows:
            return None

        # Build quarantine-aware adjacency once for efficiency
        active_ids = {str(r["id"]) for r in rows}
        adj: dict[str, list[str]] = {}
        for r in self.conn.execute(
            "SELECT source, target FROM edges"
        ).fetchall():
            s, t = str(r["source"]), str(r["target"])
            if s in active_ids and t in active_ids:
                adj.setdefault(s, []).append(t)
                adj.setdefault(t, []).append(s)

        def _bfs_max_dist(start: str) -> int:
            """BFS returning max distance from start to any active node."""
            dists = {start: 0}
            queue = [start]
            while queue:
                cur = queue.pop(0)
                for nb in adj.get(cur, []):
                    if nb not in dists:
                        dists[nb] = dists[cur] + 1
                        queue.append(nb)
            return max(dists.values()) if dists else 0

        eccs: dict[str, int] = {}
        for row in rows:
            nid = str(row["id"])
            eccs[nid] = _bfs_max_dist(nid)

        if not eccs:
            return None

        max_ecc = max(eccs.values())
        return sorted([nid for nid, ecc in eccs.items() if ecc == max_ecc])


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


if __name__ == "__main__":
    demo()
