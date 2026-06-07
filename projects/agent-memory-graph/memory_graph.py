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
        self._fts_sync_node(node.id)
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
        self._fts_delete_node(node_id)
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
        self._fts_sync_node(node_id)
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
                self._fts_sync_node(nid)
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
            "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
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

    def modularity(self, communities: dict[str, int]) -> float:
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
            "INSERT OR IGNORE INTO nodes VALUES (?,?,?,?,?,?,?,?)",
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

    def community_summary(self, communities: dict = None, algorithm: str = "lp") -> list[dict]:
        """Summarize detected communities with key metrics.

        Args:
            communities: pre-computed {label: [node_ids]} dict. If None, auto-detects.
            algorithm: "lp" for label propagation, "greedy" for greedy modularity.

        Returns list of dicts with: id, size, top_members, density, top_tags, avg_weight.
        """
        if communities is None:
            if algorithm == "greedy":
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

    def search_hybrid(self, query: str, embedding: list[float] = None, limit: int = 10) -> list[dict]:
        """混合搜索: 文本 + 向量(可选) + 图邻居 RRF 融合。

        三路融合策略:
        1. 文本搜索 (search_unified 已有): label/data/tags/kind
        2. 向量搜索 (可选): embedding KNN
        3. 图邻居加权: 邻居节点 bonus

        使用 Reciprocal Rank Fusion (RRF) 合并排名, k=60.

        Args:
            query: 文本查询
            embedding: 可选查询向量
            limit: 返回数量上限

        Returns:
            list of {node_id, label, kind, score, sources} 按融合分数降序
        """
        K = 60  # RRF 常数
        rrf_scores: dict[str, float] = defaultdict(float)
        sources_map: dict[str, set] = defaultdict(set)

        # 路1: BM25 文本搜索 (fallback 到 search_unified)
        text_results = self.search_bm25(query, limit=limit * 3)
        if not text_results:
            text_results = [
                {"node_id": r["node"].id, "label": r["node"].label,
                 "kind": r["node"].kind, "score": r["score"],
                 "matched_fields": r["matched_fields"]}
                for r in self.search_unified(query, limit=limit * 3)
            ]
        for rank, item in enumerate(text_results):
            nid = item["node_id"]
            rrf_scores[nid] += 1.0 / (K + rank + 1)
            sources_map[nid].add("bm25" if "bm25" in item.get("matched_fields", []) else "text")

        # 路2: 向量搜索 (可选)
        if embedding is not None:
            try:
                vec_results = self.search_similar(embedding, limit=limit * 3)
                for rank, item in enumerate(vec_results):
                    nid = item["node_id"]
                    rrf_scores[nid] += 1.0 / (K + rank + 1)
                    sources_map[nid].add("vector")
            except (ImportError, ValueError):
                pass  # 向量不可用时静默跳过

        # 路3: 图邻居加权 (以文本搜索 top 结果为种子)
        if text_results:
            seed_id = text_results[0]["node_id"]
            if self.has_node(seed_id):
                for rank, neighbor in enumerate(self.neighbors(seed_id)):
                    nid = neighbor.id
                    rrf_scores[nid] += 0.5 / (K + rank + 1)  # 权重较低
                    sources_map[nid].add("graph")

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
