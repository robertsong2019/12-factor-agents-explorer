"""
记忆管理系统 - 短期和长期记忆
"""

import json
import re
import copy
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class MemoryEntry:
    """记忆条目"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "importance": self.importance,
        }
        if self.tags:
            d["tags"] = self.tags
        return d

    def __eq__(self, other):
        if not isinstance(other, MemoryEntry):
            return False
        return self.content == other.content


class Memory:
    """记忆管理器"""

    def __init__(self, max_entries: int = 100, persistence_path: Optional[str] = None):
        self.max_entries = max_entries
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self._entries: List[MemoryEntry] = []
        self._archived: List[MemoryEntry] = []
        self._load()

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None, tags: Optional[List[str]] = None, importance: float = 0.5) -> None:
        """添加记忆"""
        entry = MemoryEntry(content=content, metadata=metadata or {}, tags=tags or [], importance=importance)
        self._entries.append(entry)

        # 限制条目数量
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

        self._save()

    def search(self, query: str, limit: int = 5, tags: Optional[List[str]] = None) -> List[MemoryEntry]:
        """搜索记忆（关键词匹配 + 可选标签过滤）"""
        query_lower = query.lower()
        matched = self._entries
        if tags:
            tag_set = set(tags)
            matched = [e for e in matched if tag_set & set(e.tags)]
        matched = [
            entry for entry in matched
            if query_lower in entry.content.lower()
        ]
        if limit <= 0:
            return matched
        return matched[-limit:]  # 返回最近的匹配

    def remove(self, index: int) -> bool:
        """按索引删除记忆，返回是否成功"""
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self._save()
            return True
        return False

    def update(self, index: int, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """按索引更新记忆内容，返回是否成功"""
        if 0 <= index < len(self._entries):
            self._entries[index].content = content
            if metadata is not None:
                self._entries[index].metadata = metadata
            self._entries[index].timestamp = datetime.now()
            self._save()
            return True
        return False

    def count(self) -> int:
        """返回记忆条目数"""
        return len(self._entries)

    def get_recent(self, n: int = 5) -> List[MemoryEntry]:
        """获取最近的记忆"""
        if n <= 0:
            return []
        return self._entries[-n:]

    def get_all(self) -> List[MemoryEntry]:
        """获取所有记忆"""
        return self._entries.copy()

    def clear(self) -> None:
        """清除所有记忆"""
        self._entries.clear()
        self._archived.clear()
        self._save()

    def _save(self) -> None:
        """保存到文件"""
        if not self.persistence_path:
            return

        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.persistence_path, "w", encoding="utf-8") as f:
            json.dump([entry.to_dict() for entry in self._entries], f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """从文件加载"""
        if not self.persistence_path or not self.persistence_path.exists():
            return

        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            return

        for item in data:
                entry = MemoryEntry(
                    content=item["content"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    metadata=item.get("metadata", {}),
                    tags=item.get("tags", []),
                    importance=item.get("importance", 0.5)
                )
                self._entries.append(entry)

    def set_importance(self, index: int, score: float) -> bool:
        """设置记忆重要度 (0.0-1.0)，返回是否成功"""
        if 0 <= index < len(self._entries):
            self._entries[index].importance = max(0.0, min(1.0, score))
            self._save()
            return True
        return False

    def importance_decay(self, factor: float = 0.95) -> int:
        """对所有记忆应用衰减因子，返回受影响条目数。

        每次调用将 importance *= factor，模拟时间流逝导致的遗忘。
        """
        if not (0 < factor < 1):
            return 0
        for entry in self._entries:
            entry.importance *= factor
        self._save()
        return len(self._entries)

    def forget(self, threshold: float = 0.1) -> int:
        """删除重要度低于阈值的记忆，返回删除条目数。"""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.importance >= threshold]
        removed = before - len(self._entries)
        if removed > 0:
            self._save()
        return removed

    def top_important(self, n: int = 5) -> List[MemoryEntry]:
        """按重要度降序返回前 n 条记忆"""
        return sorted(self._entries, key=lambda e: e.importance, reverse=True)[:n]

    def search_by_importance(self, min_importance: float = 0.5, limit: int = 0) -> List[MemoryEntry]:
        """按重要度阈值过滤搜索。

        Args:
            min_importance: 最低重要度阈值 (0-1)
            limit: 返回条目上限 (0=不限)

        Returns:
            按重要度降序排列的记忆列表
        """
        results = [e for e in self._entries if e.importance >= min_importance]
        results.sort(key=lambda e: e.importance, reverse=True)
        if limit > 0:
            results = results[:limit]
        return results

    def top_recent(self, minutes: int = 60) -> List[MemoryEntry]:
        """获取最近 N 分钟内添加的记忆。

        Args:
            minutes: 时间窗口（分钟），0=不限

        Returns:
            按时间倒序排列的记忆列表
        """
        if minutes <= 0:
            return list(reversed(self._entries))
        cutoff = datetime.now() - timedelta(minutes=minutes)
        results = [e for e in self._entries if e.timestamp >= cutoff]
        return list(reversed(results))

    def export_json(self) -> str:
        """导出所有记忆为JSON字符串（用于备份/迁移）"""
        return json.dumps([entry.to_dict() for entry in self._entries], ensure_ascii=False, indent=2)

    def import_json(self, data: str, merge: bool = True) -> int:
        """从JSON字符串导入记忆，返回导入条目数"""
        try:
            items = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return 0

        if not isinstance(items, list):
            return 0

        if not merge:
            self._entries.clear()

        count = 0
        for item in items:
            try:
                entry = MemoryEntry(
                    content=item["content"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    metadata=item.get("metadata", {}),
                    tags=item.get("tags", []),
                    importance=item.get("importance", 0.5)
                )
                self._entries.append(entry)
                count += 1
            except (KeyError, ValueError):
                continue

        # Enforce max_entries limit
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

        self._save()
        return count

    def stats(self) -> Dict[str, Any]:
        """返回记忆统计信息"""
        total = len(self._entries)
        if total == 0:
            return {"total": 0, "tags": {}, "date_range": None}

        # Per-tag counts
        tag_counts: Dict[str, int] = {}
        for entry in self._entries:
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Date range
        timestamps = [e.timestamp for e in self._entries]
        oldest = min(timestamps)
        newest = max(timestamps)

        avg_importance = sum(e.importance for e in self._entries) / total
        return {
            "total": total,
            "tags": tag_counts,
            "date_range": {
                "oldest": oldest.isoformat(),
                "newest": newest.isoformat()
            },
            "avg_importance": round(avg_importance, 4)
        }

    def add_tag(self, index: int, tag: str) -> bool:
        """给指定索引的记忆添加标签"""
        if 0 <= index < len(self._entries):
            if tag not in self._entries[index].tags:
                self._entries[index].tags.append(tag)
                self._save()
            return True
        return False

    def remove_tag(self, index: int, tag: str) -> bool:
        """从指定索引的记忆移除标签"""
        if 0 <= index < len(self._entries):
            tags = self._entries[index].tags
            if tag in tags:
                tags.remove(tag)
                self._save()
            return True
        return False

    def search_by_tag(self, tag: str, limit: int = 0) -> List[MemoryEntry]:
        """返回带有指定标签的所有记忆，按时间排序。

        Args:
            tag: 要搜索的标签
            limit: 返回条目上限，0 表示全部
        """
        matched = [e for e in self._entries if tag in e.tags]
        if limit > 0:
            return matched[-limit:]
        return matched

    def search_all_tags(self, tags: List[str], limit: int = 0) -> List[MemoryEntry]:
        """返回同时包含所有指定标签的记忆（AND 语义）。

        Args:
            tags: 需要同时匹配的标签列表
            limit: 返回条目上限，0 表示全部
        """
        if not tags:
            return []
        tag_set = set(tags)
        matched = [e for e in self._entries if tag_set <= set(e.tags)]
        if limit > 0:
            return matched[-limit:]
        return matched

    def distinct_tags(self) -> List[str]:
        """返回所有出现过的标签，按字母排序。"""
        all_tags = set()
        for entry in self._entries:
            all_tags.update(entry.tags)
        return sorted(all_tags)

    def merge(self, other: 'Memory') -> int:
        """合并另一个 Memory 实例到当前实例。

        去重逻辑：跳过 content 完全相同的条目。
        Returns: 实际新增的条目数。
        """
        existing_contents = {e.content for e in self._entries}
        added = 0
        for entry in other._entries:
            if entry.content not in existing_contents:
                self._entries.append(entry)
                existing_contents.add(entry.content)
                added += 1

        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

        if added > 0:
            self._save()
        return added

    def search_fuzzy(self, query: str, threshold: float = 0.3, limit: int = 5) -> List[MemoryEntry]:
        """模糊搜索记忆，使用 difflib SequenceMatcher 进行近似匹配。

        当精确关键词搜索无结果时，可用此方法找到内容相近的记忆。

        Args:
            query: 搜索查询
            threshold: 相似度阈值 (0.0-1.0)，默认 0.3
            limit: 返回条目上限，<=0 表示全部

        Returns:
            按相似度降序排列的记忆列表
        """
        if not self._entries or not query:
            return []

        query_lower = query.lower()
        scored: List[Tuple[float, MemoryEntry]] = []

        for entry in self._entries:
            content_lower = entry.content.lower()
            ratio = SequenceMatcher(None, query_lower, content_lower).ratio()
            # 也检查 query 是否匹配某个子串（提高短 query 的召回率）
            if query_lower in content_lower:
                ratio = max(ratio, 0.8)
            if ratio >= threshold:
                scored.append((ratio, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored]
        if limit > 0:
            results = results[:limit]
        return results

    def group_by_tag(self) -> Dict[str, List[MemoryEntry]]:
        """按标签分组记忆，返回 tag -> entries 映射。

        没有标签的记忆归入 "_untagged" 键。
        """
        groups: Dict[str, List[MemoryEntry]] = {}
        for entry in self._entries:
            tags = entry.tags if entry.tags else ["_untagged"]
            for tag in tags:
                if tag not in groups:
                    groups[tag] = []
                groups[tag].append(entry)
        return groups

    def deduplicate(self, threshold: float = 0.95) -> int:
        """移除内容相似度 >= threshold 的重复记忆条目，保留最早添加的。

        Args:
            threshold: 相似度阈值 (0.0-1.0)，默认 0.95（仅去重几乎完全相同的条目）

        Returns:
            被移除的条目数
        """
        if len(self._entries) < 2:
            return 0

        keep: List[MemoryEntry] = []
        removed = 0

        for entry in self._entries:
            is_dup = False
            for kept in keep:
                ratio = SequenceMatcher(None, entry.content.lower(), kept.content.lower()).ratio()
                if ratio >= threshold:
                    is_dup = True
                    break
            if is_dup:
                removed += 1
            else:
                keep.append(entry)

        if removed > 0:
            self._entries = keep
            self._save()

        return removed

    def chain_search(self, queries: List[str], limit: int = 0, fuzzy: bool = False, threshold: float = 0.3) -> List[MemoryEntry]:
        """多查询链式搜索，合并去重后按匹配查询数降序排列。

        每个条目按匹配的查询数量排序（匹配越多排名越高）。
        同一匹配数的按时间倒序。

        Args:
            queries: 搜索查询列表
            limit: 返回条目上限，0 表示全部
            fuzzy: 是否使用模糊匹配（基于 search_fuzzy）
            threshold: 模糊匹配阈值（仅 fuzzy=True 时生效）

        Returns:
            按匹配数排序的去重记忆列表
        """
        if not queries or not self._entries:
            return []

        # Count how many queries each entry matches
        match_counts: Dict[int, int] = {}  # id(entry) -> match count

        for query in queries:
            query_lower = query.lower()
            if fuzzy:
                results = self.search_fuzzy(query, threshold=threshold, limit=0)
                for entry in results:
                    match_counts[id(entry)] = match_counts.get(id(entry), 0) + 1
            else:
                for entry in self._entries:
                    if query_lower in entry.content.lower():
                        match_counts[id(entry)] = match_counts.get(id(entry), 0) + 1

        if not match_counts:
            return []

        # Build (match_count, original_index, entry) tuples for stable sort
        scored: List[Tuple[int, int, MemoryEntry]] = []
        for idx, entry in enumerate(self._entries):
            mc = match_counts.get(id(entry), 0)
            if mc > 0:
                scored.append((mc, idx, entry))

        # Sort: more matches first, then earlier (lower index = earlier) first
        scored.sort(key=lambda x: (-x[0], x[1]))

        results = [entry for _, _, entry in scored]
        if limit > 0:
            results = results[:limit]
        return results

    def snapshot(self) -> List[Dict[str, Any]]:
        """创建当前记忆的深拷贝快照，用于 undo/restore 场景。

        返回可序列化的列表，可直接传给 restore()。
        """
        return [copy.deepcopy(entry.to_dict()) for entry in self._entries]

    def restore(self, snapshot_data: List[Dict[str, Any]]) -> int:
        """从快照恢复记忆状态，返回恢复的条目数。

        警告：完全替换当前所有记忆条目。
        """
        if not isinstance(snapshot_data, list):
            return 0

        self._entries.clear()
        for item in snapshot_data:
            try:
                entry = MemoryEntry(
                    content=item["content"],
                    timestamp=datetime.fromisoformat(item["timestamp"]) if isinstance(item.get("timestamp"), str) else item.get("timestamp", datetime.now()),
                    metadata=item.get("metadata", {}),
                    tags=item.get("tags", []),
                    importance=item.get("importance", 0.5)
                )
                self._entries.append(entry)
            except (KeyError, ValueError):
                continue

        self._save()
        return len(self._entries)

    def search_regex(self, pattern: str, limit: int = 0) -> List[MemoryEntry]:
        """正则表达式搜索记忆，按时间排序。

        Args:
            pattern: 正则表达式模式
            limit: 返回条目上限，0 表示全部

        Returns:
            匹配的记忆列表

        Raises:
            re.error: 无效的正则表达式
        """
        compiled = re.compile(pattern, re.IGNORECASE)
        matched = [e for e in self._entries if compiled.search(e.content)]
        if limit > 0:
            return matched[-limit:]
        return matched

    def filter(self, predicate: Callable[[MemoryEntry], bool]) -> List[MemoryEntry]:
        """函数式过滤：返回满足 predicate 的所有记忆条目。

        Args:
            predicate: 接收 MemoryEntry 返回 bool 的回调

        Returns:
            匹配的记忆列表（按时间顺序）

        Example:
            # 所有重要度 > 0.7 的记忆
            m.filter(lambda e: e.importance > 0.7)
            # 所有带 "urgent" 标签的记忆
            m.filter(lambda e: "urgent" in e.tags)
        """
        return [e for e in self._entries if predicate(e)]

    def weighted_search(self, query: str, limit: int = 5, w_content: float = 0.5, w_importance: float = 0.3, w_recency: float = 0.2) -> List[MemoryEntry]:
        """加权多因子搜索，综合内容相似度、重要度和时间近度。

        三个因子归一化到 [0, 1] 后按权重加权求和：
        - content: SequenceMatcher 相似度
        - importance: entry.importance (已经是 0-1)
        - recency: 线性衰减 (最近=1.0, 最旧=0.0)

        Args:
            query: 搜索查询
            limit: 返回条目上限
            w_content: 内容相似度权重
            w_importance: 重要度权重
            w_recency: 时间近度权重

        Returns:
            按综合得分降序排列的记忆列表
        """
        if not self._entries or not query:
            return []

        query_lower = query.lower()
        n = len(self._entries)

        scored: List[Tuple[float, MemoryEntry]] = []
        for idx, entry in enumerate(self._entries):
            # Content similarity
            content_ratio = SequenceMatcher(None, query_lower, entry.content.lower()).ratio()
            if query_lower in entry.content.lower():
                content_ratio = max(content_ratio, 0.8)

            # Recency: linear decay (index 0 = oldest = lowest score)
            recency = (idx + 1) / n if n > 0 else 0

            total = (w_content * content_ratio
                     + w_importance * entry.importance
                     + w_recency * recency)

            scored.append((total, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored]
        if limit > 0:
            results = results[:limit]
        return results

    def search_semantic(self, query: str, limit: int = 5, boost_recent: float = 0.1) -> List[Tuple[MemoryEntry, float]]:
        """TF-IDF 加权语义搜索，基于词频-逆文档频率评分。

        无外部依赖实现：将 query 和每个 entry 分词，计算 TF-IDF 向量余弦相似度。
        可选的时间衰减因子 boost_recent 提升近期条目。

        Args:
            query: 搜索查询
            limit: 返回条目上限
            boost_recent: 时间衰减因子 (0=无衰减, 越大近期条目权重越高)

        Returns:
            [(entry, score), ...] 按 score 降序排列
        """
        import math
        if not self._entries or not query:
            return []

        def tokenize(text: str) -> List[str]:
            return [w.lower() for w in re.findall(r'\w+', text) if len(w) > 1]

        all_docs = [e.content for e in self._entries]
        all_docs.append(query)
        n = len(self._entries)

        # Build vocabulary and IDF
        vocab = {}
        for doc in all_docs:
            seen = set()
            for word in tokenize(doc):
                if word not in seen:
                    vocab[word] = vocab.get(word, 0) + 1
                    seen.add(word)
        idf = {w: math.log(n / (1 + df)) for w, df in vocab.items()}

        def tfidf_vector(text: str) -> Dict[str, float]:
            tokens = tokenize(text)
            if not tokens:
                return {}
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            total = len(tokens)
            return {t: (tf[t] / total) * idf.get(t, 0) for t in tf}

        query_vec = tfidf_vector(query)
        if not query_vec:
            return []

        def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
            common = set(a.keys()) & set(b.keys())
            if not common:
                return 0.0
            dot = sum(a[k] * b[k] for k in common)
            na = math.sqrt(sum(v * v for v in a.values()))
            nb = math.sqrt(sum(v * v for v in b.values()))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        scored = []
        for idx, entry in enumerate(self._entries):
            doc_vec = tfidf_vector(entry.content)
            sim = cosine(query_vec, doc_vec)
            # Time boost
            if boost_recent > 0 and n > 1:
                sim += boost_recent * (idx / (n - 1))
            scored.append((entry, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        if limit > 0:
            scored = scored[:limit]
        return scored

    def auto_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """自动选择最佳搜索策略并返回结果。

        依次尝试 tag_search → exact_match → semantic → fuzzy → weighted，
        返回最高置信度策略的结果，附带策略选择过程。

        Args:
            query: 搜索查询
            limit: 返回条目上限

        Returns:
            {"results": [...], "strategy": str, "score": float, "all_strategies": {...}}
        """
        if not self._entries or not query:
            return {"results": [], "strategy": "none", "score": 0.0, "all_strategies": {}}

        strategies = {}

        # 1. Tag search
        tag_results = self.search_by_tag(query, limit=limit)
        strategies["tag"] = {"results": tag_results, "score": len(tag_results) / max(len(self._entries), 1)}

        # 2. Exact match
        exact = [e for e in self._entries if query.lower() in e.content.lower()]
        strategies["exact"] = {"results": exact[:limit], "score": len(exact) / max(len(self._entries), 1)}

        # 3. Semantic (TF-IDF)
        semantic = self.search_semantic(query, limit=limit)
        sem_score = semantic[0][1] if semantic else 0.0
        strategies["semantic"] = {"results": [e for e, _ in semantic], "score": sem_score}

        # 4. Fuzzy
        fuzzy = self.search_fuzzy(query, threshold=0.2, limit=limit)
        fuzzy_score = max(
            (SequenceMatcher(None, query.lower(), e.content.lower()).ratio() for e in fuzzy),
            default=0.0
        )
        strategies["fuzzy"] = {"results": fuzzy, "score": fuzzy_score}

        # 5. Weighted multi-factor
        weighted = self.weighted_search(query, limit=limit)
        strategies["weighted"] = {"results": weighted, "score": 1.0 if weighted else 0.0}

        # Pick best non-empty strategy by score
        best_name = max(
            (name for name, s in strategies.items() if s["results"]),
            key=lambda name: strategies[name]["score"],
            default="none"
        )

        return {
            "results": strategies.get(best_name, {}).get("results", []),
            "strategy": best_name,
            "score": strategies.get(best_name, {}).get("score", 0.0),
            "all_strategies": {k: {"count": len(v["results"]), "score": v["score"]} for k, v in strategies.items()}
        }

    def paginate(self, page: int = 1, page_size: int = 10, order: str = "asc") -> Dict[str, Any]:
        """分页获取记忆条目。

        Args:
            page: 页码，从 1 开始
            page_size: 每页条目数
            order: "asc" = 从旧到新，"desc" = 从新到旧

        Returns:
            {"entries": [...], "page": int, "page_size": int, "total": int, "total_pages": int}
        """
        total = len(self._entries)
        if page < 1 or page_size < 1:
            return {"entries": [], "page": page, "page_size": page_size, "total": total, "total_pages": 0}

        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        entries = list(self._entries)
        if order == "desc":
            entries.reverse()

        start = (page - 1) * page_size
        end = start + page_size
        page_entries = entries[start:end]

        return {
            "entries": page_entries,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }

    def sample(self, n: int = 5, weighted: bool = True) -> List[MemoryEntry]:
        """随机采样 n 条记忆，可选按重要度加权。

        Args:
            n: 采样数量，如果 n >= 总数则返回全部（打乱顺序）
            weighted: True=按 importance 加权采样，False=均匀随机

        Returns:
            采样到的记忆列表
        """
        import random
        total = len(self._entries)
        if total == 0 or n <= 0:
            return []
        if n >= total:
            result = list(self._entries)
            random.shuffle(result)
            return result

        if weighted:
            weights = [max(e.importance, 0.001) for e in self._entries]
            return random.choices(self._entries, weights=weights, k=n)
        else:
            return random.sample(self._entries, n)

    def intersect(self, other: 'Memory') -> List[MemoryEntry]:
        """返回两个 Memory 实例共有的记忆条目（按 content 匹配）。

        与 diff() 互补：intersect 返回 common 部分，但作为独立方法更语义化。
        返回的是 self 中匹配的条目（保留 self 的元数据）。

        Args:
            other: 另一个 Memory 实例

        Returns:
            共有的记忆列表（按 self 中的顺序）
        """
        other_contents = {e.content for e in other._entries}
        return [e for e in self._entries if e.content in other_contents]

    def diff(self, other: 'Memory') -> Dict[str, List[MemoryEntry]]:
        """比较两个 Memory 实例的差异。

        返回三个列表：
        - "added": other 有但 self 没有的
        - "removed": self 有但 other 没有的
        - "common": 两边都有的（按 content 去重）

        Args:
            other: 另一个 Memory 实例

        Returns:
            {"added": [...], "removed": [...], "common": [...]}
        """
        self_contents = {e.content for e in self._entries}
        other_contents = {e.content for e in other._entries}

        added = [e for e in other._entries if e.content not in self_contents]
        removed = [e for e in self._entries if e.content not in other_contents]
        common = [e for e in self._entries if e.content in other_contents]

        return {"added": added, "removed": removed, "common": common}

    def timeline(self, bucket: str = "day") -> Dict[str, int]:
        """按时间桶聚合记忆数量，用于分析记忆的时间分布。

        Args:
            bucket: "hour" | "day" | "week" | "month" 时间桶粒度

        Returns:
            {bucket_key: count} 按时间正序排列
        """
        if not self._entries:
            return {}

        formats = {
            "hour": "%Y-%m-%d %H:00",
            "day": "%Y-%m-%d",
            "week": "%Y-W%W",
            "month": "%Y-%m",
        }
        fmt = formats.get(bucket, formats["day"])

        counts: Dict[str, int] = {}
        for entry in self._entries:
            key = entry.timestamp.strftime(fmt)
            counts[key] = counts.get(key, 0) + 1

        # Sort by key (time order)
        return dict(sorted(counts.items()))

    def to_context(self, max_tokens: int = 1000) -> str:
        """转换为上下文字符串"""
        entries = self.get_recent()
        if not entries:
            return ""

        context_parts = ["## 记忆\n"]
        for entry in entries:
            context_parts.append(f"- {entry.timestamp.strftime('%Y-%m-%d %H:%M')}: {entry.content}")

        # 简单的 token 估算（中文字符 * 2 + 英文字符）
        full_text = "\n".join(context_parts)
        if len(full_text.encode('utf-8')) > max_tokens:
            # 截断
            truncated = []
            current_length = 0
            for part in context_parts[1:]:  # 跳过标题
                part_length = len(part.encode('utf-8'))
                if current_length + part_length > max_tokens:
                    break
                truncated.append(part)
                current_length += part_length
            full_text = context_parts[0] + "\n".join(truncated)

        return full_text

    # ---- F31: Export formats ----

    def export_markdown(self, tags: Optional[List[str]] = None) -> str:
        """Export memories as a markdown document.

        Args:
            tags: If provided, only export entries with at least one matching tag.

        Returns:
            Markdown string with header, table of contents, and per-entry sections.
        """
        entries = self._filter_by_tags(tags) if tags else self._entries
        if not entries:
            return "# Memory Export\n\n_No entries._\n"

        lines = [f"# Memory Export", ""]
        lines.append(f"_ {len(entries)} entries | exported {datetime.now().strftime('%Y-%m-%d %H:%M')} _")
        lines.append("")

        # Table of contents
        lines.append("## Table of Contents")
        for i, entry in enumerate(entries):
            title = entry.content[:50].replace("\n", " ")
            lines.append(f"{i + 1}. {title}")
        lines.append("")

        # Entries
        lines.append("## Entries")
        lines.append("")
        for i, entry in enumerate(entries):
            lines.append(f"### {i + 1}. {entry.content[:60]}")
            lines.append(f"- **Timestamp:** {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"- **Importance:** {entry.importance:.2f}")
            if entry.tags:
                lines.append(f"- **Tags:** {', '.join(entry.tags)}")
            if entry.metadata:
                lines.append(f"- **Metadata:** {json.dumps(entry.metadata, ensure_ascii=False)}")
            lines.append("")
            lines.append(entry.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def export_csv(self, tags: Optional[List[str]] = None) -> str:
        """Export memories as CSV string.

        Columns: index,timestamp,importance,tags,content,metadata
        """
        entries = self._filter_by_tags(tags) if tags else self._entries
        lines = ["index,timestamp,importance,tags,content,metadata"]

        for i, entry in enumerate(entries):
            ts = entry.timestamp.strftime('%Y-%m-%dT%H:%M:%S')
            tags_str = ";".join(entry.tags) if entry.tags else ""
            # Escape CSV: wrap content and metadata in quotes, escape inner quotes
            content_escaped = entry.content.replace('"', '""')
            meta_escaped = json.dumps(entry.metadata, ensure_ascii=False).replace('"', '""')
            lines.append(f'{i},{ts},{entry.importance:.4f},"{tags_str}","{content_escaped}","{meta_escaped}"')

        return "\n".join(lines)

    def _filter_by_tags(self, tags: List[str]) -> List[MemoryEntry]:
        """Return entries matching at least one of the given tags."""
        tag_set = set(tags)
        return [e for e in self._entries if tag_set & set(e.tags)]

    # ---- F32: Similarity clustering ----

    def cluster(self, threshold: float = 0.5, limit: int = 0) -> Dict[int, List[MemoryEntry]]:
        """Group similar memories into clusters using greedy similarity.

        Uses SequenceMatcher ratio on content. Each entry joins the first
        cluster whose average similarity exceeds threshold. Unmatched entries
        form singleton clusters.

        Args:
            threshold: Similarity ratio (0-1) to consider entries as same cluster.
            limit: Max entries to consider (0 = all).

        Returns:
            Dict mapping cluster_id to list of MemoryEntry.
        """
        entries = self._entries[:limit] if limit > 0 else self._entries
        if not entries:
            return {}

        clusters: List[List[MemoryEntry]] = []

        for entry in entries:
            placed = False
            for cluster in clusters:
                # Average similarity to cluster members
                sims = [
                    SequenceMatcher(None, entry.content, m.content).ratio()
                    for m in cluster
                ]
                avg_sim = sum(sims) / len(sims)
                if avg_sim >= threshold:
                    cluster.append(entry)
                    placed = True
                    break
            if not placed:
                clusters.append([entry])

        return {i: c for i, c in enumerate(clusters)}

    # ---- F33: Compact summary ----

    def compact_summary(self, max_entries: int = 5) -> Dict[str, Any]:
        """Produce a compact summary of the memory store.

        Returns top entries by importance, tag distribution, and time span.
        Useful for quick inspection or feeding to an LLM for higher-level synthesis.

        Args:
            max_entries: Number of top-important entries to include.

        Returns:
            Dict with keys: total, top_entries, tag_distribution, time_span.
        """
        total = len(self._entries)
        top = self.top_important(max_entries)

        # Tag distribution
        tag_counts: Dict[str, int] = {}
        for e in self._entries:
            for t in e.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        # Time span
        if self._entries:
            timestamps = [e.timestamp for e in self._entries]
            time_span = {
                "earliest": min(timestamps).isoformat(),
                "latest": max(timestamps).isoformat(),
            }
        else:
            time_span = None

        return {
            "total": total,
            "top_entries": [
                {"content": e.content, "importance": e.importance, "tags": e.tags}
                for e in top
            ],
            "tag_distribution": dict(sorted(tag_counts.items(), key=lambda x: -x[1])),
            "time_span": time_span,
        }

    # ---- F34: Importance histogram ----

    def histogram(self, bins: int = 10) -> Dict[str, Any]:
        """Distribution histogram of importance scores.

        Args:
            bins: Number of equal-width bins in [0, 1].

        Returns:
            Dict with bin_edges, counts, labels, max_bin, min_importance, max_importance.
        """
        if not self._entries:
            return {"bins": [], "counts": [], "max_bin": None,
                    "min_importance": None, "max_importance": None}

        importances = [e.importance for e in self._entries]
        lo, hi = 0.0, 1.0
        width = (hi - lo) / bins
        edges = [lo + i * width for i in range(bins + 1)]
        counts = [0] * bins

        for val in importances:
            idx = min(int((val - lo) / width), bins - 1)
            counts[idx] += 1

        labels = [f"{edges[i]:.1f}-{edges[i+1]:.1f}" for i in range(bins)]
        max_idx = counts.index(max(counts)) if counts else None

        return {
            "bin_edges": [round(e, 4) for e in edges],
            "counts": counts,
            "labels": labels,
            "max_bin": labels[max_idx] if max_idx is not None else None,
            "min_importance": min(importances),
            "max_importance": max(importances),
        }

    # ---- F35: Correlation stats ----

    def correlation_stats(self) -> Dict[str, Any]:
        """Compute basic correlation statistics for the memory store.

        Returns Pearson correlation between importance and content length,
        tag frequency stats, and per-tag average importance.

        Returns:
            Dict with importance_length_r, tag_count, avg_importance_per_tag, total_chars.
        """
        if not self._entries:
            return {"importance_length_r": None, "tag_count": 0,
                    "avg_importance_per_tag": {}, "total_chars": 0}

        n = len(self._entries)
        importances = [e.importance for e in self._entries]
        lengths = [len(e.content) for e in self._entries]

        # Pearson correlation
        mean_i = sum(importances) / n
        mean_l = sum(lengths) / n
        num = sum((importances[i] - mean_i) * (lengths[i] - mean_l) for i in range(n))
        den_i = (sum((v - mean_i) ** 2 for v in importances)) ** 0.5
        den_l = (sum((v - mean_l) ** 2 for v in lengths)) ** 0.5
        r = num / (den_i * den_l) if den_i > 0 and den_l > 0 else 0.0

        # Per-tag average importance
        tag_imp: Dict[str, List[float]] = {}
        for e in self._entries:
            for t in e.tags:
                tag_imp.setdefault(t, []).append(e.importance)
        avg_per_tag = {t: round(sum(v) / len(v), 4) for t, v in tag_imp.items()}

        return {
            "importance_length_r": round(r, 4),
            "tag_count": len(tag_imp),
            "avg_importance_per_tag": avg_per_tag,
            "total_chars": sum(lengths),
        }

    # ---- F37: Tag cloud ----

    def tag_cloud(self, min_count: int = 1, max_tags: int = 50) -> Dict[str, float]:
        """Build a normalized tag cloud (weight 0-1 based on frequency).

        Args:
            min_count: Minimum occurrences to include.
            max_tags: Maximum number of tags to return (sorted by frequency).

        Returns:
            Dict mapping tag to weight (0.0-1.0), where 1.0 = most frequent.
        """
        counts: Dict[str, int] = {}
        for e in self._entries:
            for t in e.tags:
                counts[t] = counts.get(t, 0) + 1

        # Filter by min_count
        filtered = {t: c for t, c in counts.items() if c >= min_count}

        if not filtered:
            return {}

        # Sort by count descending, take top max_tags
        sorted_tags = sorted(filtered.items(), key=lambda x: -x[1])[:max_tags]
        max_count = sorted_tags[0][1] if sorted_tags else 1

        return {t: round(c / max_count, 4) for t, c in sorted_tags}

    # ---- F38: Field-specific search ----

    def search_in_fields(self, query: str, fields: List[str], limit: int = 5) -> List[MemoryEntry]:
        """Search within specific fields only.

        Args:
            query: Substring to search for.
            fields: List of field names to search. Valid: 'content', 'tags', 'metadata'.
            limit: Max results (0 = all matches).

        Returns:
            List of matching MemoryEntry, ranked by number of field matches.
        """
        query_lower = query.lower()
        scored: List[Tuple[int, MemoryEntry]] = []

        for entry in self._entries:
            score = 0
            for field in fields:
                if field == "content":
                    if query_lower in entry.content.lower():
                        score += 1
                elif field == "tags":
                    if any(query_lower in t.lower() for t in entry.tags):
                        score += 1
                elif field == "metadata":
                    meta_str = json.dumps(entry.metadata, ensure_ascii=False).lower()
                    if query_lower in meta_str:
                        score += 1
            if score > 0:
                scored.append((score, entry))

        # Sort by score descending, then by timestamp descending
        scored.sort(key=lambda x: (-x[0], -x[1].timestamp.timestamp()))
        results = [e for _, e in scored]
        return results[:limit] if limit > 0 else results

    # ---- F39: Auto-tagging ----

    def auto_tag(self, rules: Dict[str, List[str]], overwrite: bool = False) -> int:
        """Automatically assign tags based on keyword rules.

        Args:
            rules: Dict mapping tag name to list of keywords. If any keyword
                   appears in content (case-insensitive), the tag is applied.
            overwrite: If True, replace existing tags. If False, append.

        Returns:
            Number of entries that received at least one new tag.
        """
        tagged_count = 0
        for entry in self._entries:
            new_tags: List[str] = []
            content_lower = entry.content.lower()
            for tag, keywords in rules.items():
                if any(kw.lower() in content_lower for kw in keywords):
                    if tag not in new_tags:
                        new_tags.append(tag)

            if new_tags:
                if overwrite:
                    entry.tags = new_tags
                else:
                    for t in new_tags:
                        if t not in entry.tags:
                            entry.tags.append(t)
                tagged_count += 1

        if self.persistence_path:
            self._save()

        return tagged_count

    # ---- F40: JSONL export ----

    def export_jsonl(self, tags: Optional[List[str]] = None) -> str:
        """Export memories as JSON Lines (one JSON object per line).

        Each line is a self-contained JSON object, making this format ideal
        for streaming pipelines, log ingestion, and ML data loading.

        Args:
            tags: If provided, only export entries with at least one matching tag.

        Returns:
            Newline-separated JSON strings (no trailing newline).
        """
        entries = self._filter_by_tags(tags) if tags else self._entries
        if not entries:
            return ""
        return "\n".join(
            json.dumps(entry.to_dict(), ensure_ascii=False) for entry in entries
        )

    # ---- F41: Tag normalization ----

    def normalize_tags(self, mapping: Dict[str, str]) -> int:
        """Batch rename or merge tags across all entries.

        For each entry, any tag found in ``mapping`` is replaced with its
        corresponding value. This is useful for consolidating variants
        (e.g. {"bug": "issue", "bugs": "issue"}) or fixing typos.

        After remapping, duplicate tags within a single entry are deduplicated
        (preserving first occurrence order).

        Args:
            mapping: Dict of old_tag -> new_tag.

        Returns:
            Number of entries whose tag list changed.
        """
        if not mapping:
            return 0

        changed = 0
        for entry in self._entries:
            original = list(entry.tags)
            new_tags: List[str] = []
            seen: set = set()
            for tag in entry.tags:
                resolved = mapping.get(tag, tag)
                if resolved not in seen:
                    new_tags.append(resolved)
                    seen.add(resolved)
            if new_tags != original:
                entry.tags = new_tags
                changed += 1

        if changed > 0 and self.persistence_path:
            self._save()

        return changed

    # ---- F43: JSONL import ----

    def import_jsonl(self, data: str, merge: bool = True) -> int:
        """Import memories from JSON Lines string (complement to export_jsonl).

        Each line should be a self-contained JSON object with at least a
        ``content`` key. Lines that are empty, invalid JSON, or missing
        ``content`` are silently skipped.

        Args:
            data: JSONL string (one JSON object per line).
            merge: If True, append to existing entries. If False, replace.

        Returns:
            Number of entries successfully imported.
        """
        if not isinstance(data, str):
            return 0

        if not merge:
            self._entries.clear()

        count = 0
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(item, dict) or "content" not in item:
                continue
            try:
                entry = MemoryEntry(
                    content=item["content"],
                    timestamp=datetime.fromisoformat(item["timestamp"]) if isinstance(item.get("timestamp"), str) else datetime.now(),
                    metadata=item.get("metadata", {}),
                    tags=item.get("tags", []),
                    importance=item.get("importance", 0.5),
                )
                self._entries.append(entry)
                count += 1
            except (KeyError, ValueError):
                continue

        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

        if count > 0:
            self._save()
        return count

    # ---- F44: Union (set union of two Memory stores) ----

    def union(self, other: 'Memory') -> 'Memory':
        """Return a new Memory containing entries from both stores.

        Content-based deduplication: if an entry exists in both stores
        (by content), the entry from ``self`` is kept (preserving its
        metadata, tags, and importance).

        Returns:
            A new Memory instance.
        """
        result = Memory(max_entries=self.max_entries)
        seen_contents: set = set()

        for entry in self._entries:
            if entry.content not in seen_contents:
                result._entries.append(copy.deepcopy(entry))
                seen_contents.add(entry.content)

        for entry in other._entries:
            if entry.content not in seen_contents:
                result._entries.append(copy.deepcopy(entry))
                seen_contents.add(entry.content)

        if len(result._entries) > result.max_entries:
            result._entries = result._entries[-result.max_entries:]

        return result

    # ---- F45: Set difference (subtract) ----

    def subtract(self, other: 'Memory') -> 'Memory':
        """Return a new Memory containing entries from ``self`` that are NOT in ``other``.

        Content-based comparison: an entry is removed if its content matches
        any entry in *other*.

        Returns:
            A new Memory instance with the difference set.
        """
        other_contents = {e.content for e in other._entries}
        result = Memory(max_entries=self.max_entries)
        for entry in self._entries:
            if entry.content not in other_contents:
                result._entries.append(copy.deepcopy(entry))
        return result

    # ---- F46: Structured prompt formatter ----

    def to_prompt(self, include_metadata: bool = True, include_tags: bool = True, max_entries: int = 20) -> str:
        """Format memory entries as a structured prompt block for LLM consumption.

        Unlike ``to_context()`` (which is a simple timestamped list), this
        produces a richer, structured format with importance scores, tags,
        and metadata — designed to be injected into system prompts.

        Args:
            include_metadata: Include metadata dict in each entry line.
            include_tags: Include tags in each entry line.
            max_entries: Maximum entries to include (sorted by importance desc).

        Returns:
            A formatted string ready for prompt injection.
        """
        if not self._entries:
            return ""

        sorted_entries = sorted(self._entries, key=lambda e: e.importance, reverse=True)
        selected = sorted_entries[:max_entries]

        lines = [f"## Memory Store ({len(selected)} of {len(self._entries)} entries, sorted by importance)"]
        for i, entry in enumerate(selected, 1):
            parts = [f"{i}. [{entry.importance:.1f}] {entry.content}"]
            if include_tags and entry.tags:
                parts.append(f"   tags: {', '.join(entry.tags)}")
            if include_metadata and entry.metadata:
                meta_str = ", ".join(f"{k}={v}" for k, v in entry.metadata.items())
                parts.append(f"   metadata: {meta_str}")
            parts.append(f"   timestamp: {entry.timestamp.strftime('%Y-%m-%d %H:%M')}")
            lines.append("\n".join(parts))

        return "\n\n".join(lines)

    # ---- F42: Shannon entropy ----

    def entropy(self) -> Dict[str, Any]:
        """Compute Shannon entropy of memory content as a diversity metric.

        Treats each entry's content as a "token" and computes entropy over
        the distribution of content values. Higher entropy = more diverse
        memory store; entropy near 0 = highly repetitive.

        Also computes tag-level entropy and character-level statistics.

        Returns:
            Dict with content_entropy, tag_entropy, unique_contents,
            unique_tags, total_entries.
        """
        import math

        n = len(self._entries)
        if n == 0:
            return {"content_entropy": 0.0, "tag_entropy": 0.0,
                    "unique_contents": 0, "unique_tags": 0, "total_entries": 0}

        # Content entropy (by exact content match)
        content_counts: Dict[str, int] = {}
        for e in self._entries:
            content_counts[e.content] = content_counts.get(e.content, 0) + 1

        def _shannon(counts: Dict[str, int], total: int) -> float:
            h = 0.0
            for c in counts.values():
                if c > 0:
                    p = c / total
                    h -= p * math.log2(p)
            return round(h, 4)

        content_h = _shannon(content_counts, n)

        # Tag entropy
        tag_counts: Dict[str, int] = {}
        for e in self._entries:
            for t in e.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        total_tags = sum(tag_counts.values())
        tag_h = _shannon(tag_counts, total_tags) if total_tags > 0 else 0.0

        return {
            "content_entropy": content_h,
            "tag_entropy": tag_h,
            "unique_contents": len(content_counts),
            "unique_tags": len(tag_counts),
            "total_entries": n,
        }

    # F47: resize — trim memory to max_size using eviction strategies
    def resize(self, max_size: int, strategy: str = "oldest") -> Dict[str, Any]:
        """Trim memory to *max_size* entries using the given eviction strategy.

        Strategies:
          - ``oldest``: remove entries with the earliest timestamps.
          - ``least_important``: remove entries with the lowest importance scores.
          - ``random``: randomly remove entries.
          - ``clustered``: greedily keep cluster centroids (via similarity),
            removing near-duplicates first.

        Returns a dict with removed_count, remaining_count, and strategy.
        """
        import random as _random

        n = len(self._entries)
        if n <= max_size:
            return {"removed_count": 0, "remaining_count": n, "strategy": strategy}

        to_remove = n - max_size

        if strategy == "oldest":
            # Sort by timestamp ascending, remove oldest first
            indexed = sorted(enumerate(self._entries), key=lambda x: x[1].timestamp)
            remove_indices = {idx for idx, _ in indexed[:to_remove]}
        elif strategy == "least_important":
            # Sort by importance ascending, remove least important first
            indexed = sorted(enumerate(self._entries), key=lambda x: x[1].importance)
            remove_indices = {idx for idx, _ in indexed[:to_remove]}
        elif strategy == "random":
            remove_indices = set(_random.sample(range(n), to_remove))
        elif strategy == "clustered":
            # Greedily mark near-duplicates for removal
            remove_indices = set()
            kept_indices = list(range(n))
            for i in range(n):
                if i in remove_indices:
                    continue
                for j in range(i + 1, n):
                    if j in remove_indices:
                        continue
                    ratio = SequenceMatcher(None, self._entries[i].content,
                                            self._entries[j].content).ratio()
                    if ratio >= 0.7:
                        # Keep the one with higher importance
                        if self._entries[i].importance >= self._entries[j].importance:
                            remove_indices.add(j)
                        else:
                            remove_indices.add(i)
                        break
                if len(remove_indices) >= to_remove:
                    break
            # If clustered didn't remove enough, fall back to least_important
            if len(remove_indices) < to_remove:
                remaining_candidates = [i for i in range(n) if i not in remove_indices]
                remaining_candidates.sort(key=lambda i: self._entries[i].importance)
                still_need = to_remove - len(remove_indices)
                for idx in remaining_candidates[:still_need]:
                    remove_indices.add(idx)
            # If clustered removed too many, keep the extras by importance
            if len(remove_indices) > to_remove:
                extras = sorted(remove_indices, key=lambda i: -self._entries[i].importance)
                for idx in extras[:len(remove_indices) - to_remove]:
                    remove_indices.discard(idx)
        else:
            raise ValueError(f"Unknown strategy: {strategy}. "
                             "Use 'oldest', 'least_important', 'random', or 'clustered'.")

        # Apply removal in reverse order to preserve indices
        new_entries = [e for i, e in enumerate(self._entries) if i not in remove_indices]
        removed = len(self._entries) - len(new_entries)
        self._entries = new_entries

        return {
            "removed_count": removed,
            "remaining_count": len(self._entries),
            "strategy": strategy,
        }

    # F48: search_similar — find memories similar to a specific entry
    def search_similar(self, index: int, limit: int = 5) -> List[MemoryEntry]:
        """Find memories most similar to the entry at *index*.

        Uses SequenceMatcher ratio on content. Excludes the query entry itself.
        Returns entries sorted by similarity (descending), up to *limit*.
        """
        if index < 0 or index >= len(self._entries):
            raise IndexError(f"Index {index} out of range (0-{len(self._entries) - 1})")

        query_content = self._entries[index].content
        scored: List[Tuple[float, MemoryEntry]] = []

        for i, entry in enumerate(self._entries):
            if i == index:
                continue
            ratio = SequenceMatcher(None, query_content, entry.content).ratio()
            scored.append((ratio, entry))

        scored.sort(key=lambda x: -x[0])
        return [entry for _, entry in scored[:limit]]

    # ---- F49: Anomaly detection ----

    def anomaly_detection(self, window_minutes: int = 60) -> Dict[str, Any]:
        """Detect temporal anomalies in memory entries.

        Three anomaly types are detected:

        1. **Burst activity** — time windows where entry rate exceeds 3× the
           average rate (entries per ``window_minutes``).
        2. **Importance outliers** — entries whose importance is more than
           2 standard deviations from the mean.
        3. **Tag concentration** — when a single tag accounts for more than
           50% of all tag occurrences.

        Args:
            window_minutes: Size of the sliding window for burst detection.

        Returns:
            Dict with keys:
            - ``anomalies``: list of anomaly description dicts.
            - ``burst_windows``: list of ``{start, end, count}`` dicts.
            - ``importance_stats``: ``{mean, std, outliers}``.
            - ``tag_concentration``: ``{max_tag, max_share, total_tags}``.
        """
        import math

        n = len(self._entries)
        anomalies: List[Dict[str, Any]] = []

        # ── Burst detection ──
        burst_windows: List[Dict[str, Any]] = []
        if n >= 2:
            timestamps = sorted(e.timestamp for e in self._entries)
            total_span_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
            if total_span_seconds > 0:
                window_seconds = window_minutes * 60
                # Number of windows that fit in the span (at least 1)
                num_windows = max(total_span_seconds / window_seconds, 1.0)
                # Average entries per window
                avg_rate = n / num_windows
                # Burst threshold: 3x average, minimum 3 entries
                threshold = max(3 * avg_rate, 3.0)

                # Sliding window
                left = 0
                for right in range(n):
                    while (timestamps[right] - timestamps[left]).total_seconds() > window_seconds:
                        left += 1
                    count = right - left + 1
                    if count >= threshold:
                        burst_windows.append({
                            "start": timestamps[left].isoformat(),
                            "end": timestamps[right].isoformat(),
                            "count": count,
                        })

                # Merge overlapping windows
                merged: List[Dict[str, Any]] = []
                for bw in burst_windows:
                    if merged and bw["start"] <= merged[-1]["end"]:
                        merged[-1]["end"] = bw["end"]
                        merged[-1]["count"] = max(merged[-1]["count"], bw["count"])
                    else:
                        merged.append(dict(bw))
                burst_windows = merged

                for bw in burst_windows:
                    anomalies.append({
                        "type": "burst",
                        "detail": f"{bw['count']} entries in window starting {bw['start']}",
                        "data": bw,
                    })

        # ── Importance outliers ──
        importance_outliers: List[MemoryEntry] = []
        if n >= 2:
            importances = [e.importance for e in self._entries]
            mean_imp = sum(importances) / n
            variance = sum((x - mean_imp) ** 2 for x in importances) / n
            std_imp = math.sqrt(variance)
            if std_imp > 0:
                for entry in self._entries:
                    if abs(entry.importance - mean_imp) > 2 * std_imp:
                        importance_outliers.append(entry)
                for entry in importance_outliers:
                    anomalies.append({
                        "type": "importance_outlier",
                        "detail": f"Importance {entry.importance:.4f} deviates >2σ from mean {mean_imp:.4f}",
                        "data": {"content": entry.content, "importance": entry.importance},
                    })
        else:
            std_imp = 0.0
            mean_imp = self._entries[0].importance if n == 1 else 0.0

        importance_stats = {
            "mean": round(mean_imp, 4),
            "std": round(std_imp, 4),
            "outliers": [
                {"content": e.content, "importance": e.importance}
                for e in importance_outliers
            ],
        }

        # ── Tag concentration ──
        tag_counts: Dict[str, int] = {}
        for e in self._entries:
            for t in e.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        total_tag_occurrences = sum(tag_counts.values())

        max_tag = None
        max_share = 0.0
        if total_tag_occurrences > 0:
            max_tag = max(tag_counts, key=tag_counts.get)
            max_share = tag_counts[max_tag] / total_tag_occurrences
            if max_share > 0.5:
                anomalies.append({
                    "type": "tag_concentration",
                    "detail": f"Tag '{max_tag}' dominates with {max_share:.1%} of all tags",
                    "data": {"tag": max_tag, "share": round(max_share, 4)},
                })

        tag_concentration = {
            "max_tag": max_tag,
            "max_share": round(max_share, 4),
            "total_tags": total_tag_occurrences,
        }

        return {
            "anomalies": anomalies,
            "burst_windows": burst_windows,
            "importance_stats": importance_stats,
            "tag_concentration": tag_concentration,
        }

    # ---- F50: Conversation summary ----

    def conversation_summary(self, recent_n: int = 0) -> Dict[str, Any]:
        """Summarize recent memory as a structured report.

        Produces a comprehensive overview including entry count, time span,
        top tags, importance distribution, content themes (word frequency),
        and recent activity pattern.

        Args:
            recent_n: If > 0, only summarize the most recent *recent_n* entries.
                      If 0 or negative, summarize all entries.

        Returns:
            Dict with keys:
            - ``entry_count``
            - ``time_span``: ``{earliest, latest, duration_seconds}``
            - ``top_tags``: list of ``{tag, count}`` sorted by count desc
            - ``importance_distribution``: ``{mean, min, max, buckets}``
            - ``content_themes``: dict of word -> count (top 20, lowercased)
            - ``activity_pattern``: ``{rate_per_hour, burst_detected, gap_seconds}``
        """
        import math
        import re as _re

        if recent_n and recent_n > 0:
            entries = self._entries[-recent_n:]
        else:
            entries = self._entries

        n = len(entries)
        if n == 0:
            return {
                "entry_count": 0,
                "time_span": None,
                "top_tags": [],
                "importance_distribution": None,
                "content_themes": {},
                "activity_pattern": None,
            }

        # ── Time span ──
        timestamps = [e.timestamp for e in entries]
        earliest = min(timestamps)
        latest = max(timestamps)
        duration_seconds = (latest - earliest).total_seconds()

        # ── Top tags ──
        tag_counts: Dict[str, int] = {}
        for e in entries:
            for t in e.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        top_tags = [
            {"tag": t, "count": c}
            for t, c in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
        ]

        # ── Importance distribution ──
        importances = [e.importance for e in entries]
        mean_imp = sum(importances) / n
        # Buckets: low (<0.33), medium (0.33-0.66), high (>0.66)
        low = sum(1 for v in importances if v < 0.33)
        medium = sum(1 for v in importances if 0.33 <= v <= 0.66)
        high = sum(1 for v in importances if v > 0.66)

        importance_distribution = {
            "mean": round(mean_imp, 4),
            "min": min(importances),
            "max": max(importances),
            "buckets": {"low": low, "medium": medium, "high": high},
        }

        # ── Content themes (word frequency) ──
        word_freq: Dict[str, int] = {}
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "to", "of", "in", "on", "at", "by", "for", "with", "from",
            "and", "or", "not", "but", "if", "then", "else", "so", "no",
            "it", "this", "that", "these", "those", "i", "you", "he",
            "she", "we", "they", "my", "your", "his", "her", "our",
            "do", "does", "did", "have", "has", "had", "will", "would",
            "can", "could", "should", "shall", "may", "might", "must",
        }
        for e in entries:
            words = _re.findall(r"[a-zA-Z]\w*", e.content.lower())
            for w in words:
                if w not in stop_words and len(w) > 2:
                    word_freq[w] = word_freq.get(w, 0) + 1

        # Top 20 themes
        content_themes = dict(
            sorted(word_freq.items(), key=lambda x: (-x[1], x[0]))[:20]
        )

        # ── Activity pattern ──
        rate_per_hour = 0.0
        burst_detected = False
        gap_seconds = 0.0

        if n >= 2 and duration_seconds > 0:
            rate_per_hour = n / (duration_seconds / 3600)

            # Detect burst: any window where rate > 3x average
            anomaly = self.anomaly_detection(window_minutes=60)
            burst_detected = len(anomaly["burst_windows"]) > 0

            # Max gap between consecutive entries
            sorted_ts = sorted(timestamps)
            gaps = [
                (sorted_ts[i + 1] - sorted_ts[i]).total_seconds()
                for i in range(len(sorted_ts) - 1)
            ]
            gap_seconds = max(gaps) if gaps else 0.0

        activity_pattern = {
            "rate_per_hour": round(rate_per_hour, 4),
            "burst_detected": burst_detected,
            "gap_seconds": round(gap_seconds, 2),
        }

        return {
            "entry_count": n,
            "time_span": {
                "earliest": earliest.isoformat(),
                "latest": latest.isoformat(),
                "duration_seconds": round(duration_seconds, 2),
            },
            "top_tags": top_tags,
            "importance_distribution": importance_distribution,
            "content_themes": content_themes,
            "activity_pattern": activity_pattern,
        }

    # ── F49: Archive System ──────────────────────────────────────────

    def archive(self, index: int) -> bool:
        """Soft-delete: move entry from active to archived. Returns success."""
        if 0 <= index < len(self._entries):
            self._archived.append(self._entries.pop(index))
            self._save()
            return True
        return False

    def unarchive(self, index: int) -> bool:
        """Restore entry from archive back to active. Returns success."""
        if 0 <= index < len(self._archived):
            self._entries.append(self._archived.pop(index))
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]
            self._save()
            return True
        return False

    def archived(self) -> List[MemoryEntry]:
        """List archived entries."""
        return self._archived.copy()

    # ── F50: Time-based Forgetting ───────────────────────────────────

    def forget_older_than(self, days: int) -> int:
        """Remove entries older than N days. Returns count removed."""
        cutoff = datetime.now() - timedelta(days=days)
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.timestamp >= cutoff]
        removed = before - len(self._entries)
        if removed > 0:
            self._save()
        return removed

    # ── F52: Merge Metadata ──────────────────────────────────────────

    def merge_metadata(self, index: int, metadata: Dict[str, Any]) -> bool:
        """Merge metadata fields into an existing entry without replacing the dict.

        Returns True if the entry was found and updated.
        """
        if not (0 <= index < len(self._entries)):
            return False
        self._entries[index].metadata.update(metadata)
        self._save()
        return True

    # ── F53: Find Duplicate Pairs ────────────────────────────────────

    def find_duplicates(self, threshold: float = 0.85) -> List[Dict[str, Any]]:
        """Find all near-duplicate entry pairs above *threshold* similarity.

        Returns a list of dicts: {"i": idx_a, "j": idx_b, "similarity": float,
        "content_i": str, "content_j": str} sorted by descending similarity.
        """
        n = len(self._entries)
        if n < 2:
            return []
        pairs: List[Dict[str, Any]] = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = SequenceMatcher(
                    None,
                    self._entries[i].content.lower(),
                    self._entries[j].content.lower(),
                ).ratio()
                if sim >= threshold:
                    pairs.append({
                        "i": i,
                        "j": j,
                        "similarity": round(sim, 4),
                        "content_i": self._entries[i].content,
                        "content_j": self._entries[j].content,
                    })
        pairs.sort(key=lambda p: p["similarity"], reverse=True)
        return pairs

    # ── F54: Tag Statistics ───────────────────────────────────────────

    def tag_stats(self) -> Dict[str, Any]:
        """Return tag frequency distribution and co-occurrence matrix.

        Returns dict with:
        - frequency: {tag: count} sorted by count desc
        - total_tags: unique tag count
        - tagged_entries: entries with ≥1 tag
        - untagged_entries: entries with 0 tags
        - co_occurrence: {tag_a: {tag_b: count}} — how often tags appear together
        """
        from collections import Counter, defaultdict
        freq = Counter()
        co_occ: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        tagged = 0

        for entry in self._entries:
            if entry.tags:
                tagged += 1
            for t in set(entry.tags):
                freq[t] += 1
            # co-occurrence
            tags = sorted(set(entry.tags))
            for i, a in enumerate(tags):
                for b in tags[i + 1:]:
                    co_occ[a][b] += 1
                    co_occ[b][a] += 1

        return {
            "frequency": dict(freq.most_common()),
            "total_tags": len(freq),
            "tagged_entries": tagged,
            "untagged_entries": len(self._entries) - tagged,
            "co_occurrence": {k: dict(v) for k, v in sorted(co_occ.items())},
        }

    # F55: batch_add — bulk insert entries, return list of assigned indices
    def batch_add(self, entries: List[Dict[str, Any]]) -> List[int]:
        """Add multiple entries at once.

        Each dict in entries supports keys: content (required),
        metadata, tags, importance.

        Returns list of indices assigned to each entry (in order).
        If max_entries is exceeded, oldest entries are evicted;
        returned indices reflect positions after all insertions.
        """
        if not entries:
            return []

        indices: List[int] = []
        for spec in entries:
            content = spec.get("content", "")
            if not content:
                indices.append(-1)
                continue
            idx = len(self._entries)
            entry = MemoryEntry(
                content=content,
                metadata=spec.get("metadata", {}),
                tags=spec.get("tags", []),
                importance=spec.get("importance", 0.5),
            )
            self._entries.append(entry)
            indices.append(idx)

        # Enforce max_entries
        if len(self._entries) > self.max_entries:
            evicted = len(self._entries) - self.max_entries
            self._entries = self._entries[-self.max_entries:]
            # Shift indices to account for eviction
            indices = [i - evicted if i >= 0 else i for i in indices]

        self._save()
        return indices

    # F56: search_snippet — search returning context-windowed snippets
    def search_snippet(self, query: str, context_chars: int = 50, limit: int = 5) -> List[Dict[str, Any]]:
        """Search and return snippets with surrounding context.

        Returns list of dicts: {entry, index, snippet, match_pos}.
        snippet is the content around the first match, with the
        query highlighted via [[HIGHLIGHT]]...[[/HIGHLIGHT]] markers.
        """
        query_lower = query.lower()
        results: List[Dict[str, Any]] = []

        for idx, entry in enumerate(self._entries):
            pos = entry.content.lower().find(query_lower)
            if pos == -1:
                continue

            start = max(0, pos - context_chars)
            end = min(len(entry.content), pos + len(query) + context_chars)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(entry.content) else ""

            snippet_text = entry.content[start:end]
            # Insert highlight markers around the match in the snippet
            rel_pos = pos - start
            match_end = rel_pos + len(query)
            snippet = (
                prefix
                + snippet_text[:rel_pos]
                + "[[HIGHLIGHT]]"
                + snippet_text[rel_pos:match_end]
                + "[[/HIGHLIGHT]]"
                + snippet_text[match_end:]
                + suffix
            )

            results.append({
                "entry": entry,
                "index": idx,
                "snippet": snippet,
                "match_pos": pos,
            })

            if len(results) >= limit:
                break

        return results

    # F57: health_check — comprehensive memory health report
    def health_check(self) -> Dict[str, Any]:
        """Run a comprehensive health check on the memory store.

        Returns dict with:
        - status: 'healthy' | 'warning' | 'critical'
        - issues: list of issue descriptions
        - stats: {total, archived, tagged, duplicates, avg_importance, oldest_days}
        - recommendations: list of suggested actions
        """
        issues: List[str] = []
        recommendations: List[str] = []

        total = len(self._entries)
        archived = len(self._archived)
        tagged = sum(1 for e in self._entries if e.tags)
        dupes = self.find_duplicates(threshold=0.9)
        avg_imp = sum(e.importance for e in self._entries) / total if total else 0.0

        oldest_days = 0.0
        if self._entries:
            oldest = min(e.timestamp for e in self._entries)
            oldest_days = (datetime.now() - oldest).days

        # Capacity warnings
        capacity_ratio = total / self.max_entries if self.max_entries > 0 else 0.0
        if capacity_ratio >= 0.95:
            issues.append(f"Memory at {capacity_ratio:.0%} capacity ({total}/{self.max_entries})")
            recommendations.append("Consider increasing max_entries or running resize()")
        elif capacity_ratio >= 0.8:
            issues.append(f"Memory at {capacity_ratio:.0%} capacity ({total}/{self.max_entries})")

        # Duplicate detection
        if dupes:
            issues.append(f"{len(dupes)} near-duplicate pairs found (threshold=0.9)")
            recommendations.append("Run deduplicate() to merge similar entries")

        # Low average importance
        if total > 10 and avg_imp < 0.2:
            issues.append(f"Low average importance: {avg_imp:.2f}")
            recommendations.append("Consider forgetting low-importance entries")

        # Stale entries
        if oldest_days > 90:
            stale = self.forget_older_than(days=90) if hasattr(self, '_entries') else 0
            # Don't actually delete in health check, just report
            old_count = sum(
                1 for e in self._entries
                if (datetime.now() - e.timestamp).days > 90
            )
            if old_count:
                issues.append(f"{old_count} entries older than 90 days")
                recommendations.append("Consider forget_older_than(90) to clean up")

        # Untagged entries
        untagged = total - tagged
        if total > 5 and untagged / total > 0.8:
            issues.append(f"{untagged}/{total} entries have no tags ({untagged/total:.0%})")
            recommendations.append("Consider using auto_tag() to organize entries")

        # Determine status
        if any("critical" in i.lower() or "100%" in i for i in issues):
            status = "critical"
        elif issues:
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "issues": issues,
            "stats": {
                "total": total,
                "archived": archived,
                "tagged": tagged,
                "untagged": untagged,
                "duplicates": len(dupes),
                "avg_importance": round(avg_imp, 3),
                "oldest_days": oldest_days,
                "capacity_ratio": round(capacity_ratio, 2),
            },
            "recommendations": recommendations,
        }

    # ---- F49: tag_summary (per-tag analytics) ----

    def tag_summary(self, min_count: int = 0) -> Dict[str, Dict[str, Any]]:
        """Generate analytics summary per tag.

        For each tag, computes: count, average importance, most recent
        entry timestamp, and representative content (shortest entry).

        Args:
            min_count: Only include tags with >= min_count entries.

        Returns:
            Dict mapping tag name to {count, avg_importance, latest,
            representative}.
        """
        tag_entries: Dict[str, List[MemoryEntry]] = {}
        for i, entry in enumerate(self._entries):
            for tag in entry.tags:
                tag_entries.setdefault(tag, []).append(entry)

        result: Dict[str, Dict[str, Any]] = {}
        for tag, entries in sorted(tag_entries.items()):
            if len(entries) < min_count:
                continue
            avg_imp = sum(e.importance for e in entries) / len(entries)
            latest = max(entries, key=lambda e: e.timestamp)
            representative = min(entries, key=lambda e: len(e.content))
            result[tag] = {
                "count": len(entries),
                "avg_importance": round(avg_imp, 3),
                "latest": latest.timestamp.isoformat(),
                "representative": representative.content[:100],
            }
        return result

    # ---- F50: export_tsv ----

    def export_tsv(self, tags: Optional[List[str]] = None) -> str:
        """Export memories as TSV (tab-separated values) string.

        Columns: index, timestamp, content, importance, tags, metadata_json.
        Useful for data analysis pipelines and spreadsheet import.

        Args:
            tags: If provided, only export entries matching any of these tags.

        Returns:
            TSV string with header row.
        """
        entries = self._entries if not tags else self._filter_by_tags(tags)
        entry_indices = {id(e): i for i, e in enumerate(self._entries)}
        lines = ["index\ttimestamp\tcontent\timportance\ttags\tmetadata"]
        for entry in entries:
            idx = entry_indices.get(id(entry), 0)
            content_safe = entry.content.replace("\t", " ").replace("\n", " ")
            tags_str = ",".join(entry.tags)
            meta_str = json.dumps(entry.metadata, ensure_ascii=False)
            lines.append(f"{idx}\t{entry.timestamp.isoformat()}\t{content_safe}\t{entry.importance}\t{tags_str}\t{meta_str}")
        return "\n".join(lines)

    # ---- F51: batch_remove / batch_update ----

    def batch_remove(self, indices: List[int]) -> int:
        """Remove multiple entries by index in a single pass.

        Indices are processed in reverse order to maintain validity
        of remaining indices.

        Args:
            indices: List of entry indices to remove.

        Returns:
            Number of entries successfully removed.
        """
        if not isinstance(indices, list):
            return 0
        removed = 0
        valid_indices = [idx for idx in indices if isinstance(idx, int)]
        for idx in sorted(set(valid_indices), reverse=True):
            if 0 <= idx < len(self._entries):
                self._entries.pop(idx)
                removed += 1
        if removed > 0:
            self._save()
        return removed

    def batch_update(self, updates: List[Dict[str, Any]]) -> int:
        """Update multiple entries in a single pass.

        Each update dict must contain "index" and at least one of
        "content", "importance", "tags", or "metadata".

        Args:
            updates: List of {index, content?, importance?, tags?, metadata?}.

        Returns:
            Number of entries successfully updated.
        """
        if not isinstance(updates, list):
            return 0
        updated = 0
        for u in updates:
            if not isinstance(u, dict) or "index" not in u:
                continue
            idx = u["index"]
            if not isinstance(idx, int):
                continue
            if not (0 <= idx < len(self._entries)):
                continue
            entry = self._entries[idx]
            if "content" in u and isinstance(u["content"], str):
                entry.content = u["content"]
                entry.timestamp = datetime.now()
            if "importance" in u and isinstance(u["importance"], (int, float)):
                entry.importance = max(0.0, min(1.0, float(u["importance"])))
            if "tags" in u and isinstance(u["tags"], list):
                entry.tags = [str(t) for t in u["tags"]]
            if "metadata" in u and isinstance(u["metadata"], dict):
                entry.metadata = u["metadata"]
            updated += 1
        if updated > 0:
            self._save()
        return updated

    # F58: Boolean search (AND/OR/NOT)
    def search_boolean(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Boolean search supporting AND, OR, NOT operators.

        Query syntax:
        - 'python AND web' — entries containing both terms
        - 'python OR rust' — entries containing either term
        - 'python NOT web' — entries with python but not web
        - 'python AND (web OR api)' — parenthesized grouping
        - Plain 'python' — same as simple search

        Args:
            query: Boolean expression string
            limit: Max results to return

        Returns:
            List of matching MemoryEntry, sorted by relevance (importance desc)
        """
        query_upper = query.upper()
        has_boolean = any(op in query_upper for op in [' AND ', ' OR ', ' NOT '])

        if not has_boolean:
            return self.search(query, limit=limit)

        # Parse into tokens and operators
        tokens = re.findall(r'\(|\)|[^\s()]+', query)

        def _evaluate(expr_tokens, entries):
            """Evaluate boolean expression against entries. Returns set of indices."""
            if not expr_tokens:
                return set()

            result = set()
            op = 'AND'
            i = 0
            while i < len(expr_tokens):
                tok = expr_tokens[i]
                tok_upper = tok.upper()

                if tok_upper in ('AND', 'OR', 'NOT'):
                    op = tok_upper
                    i += 1
                    continue

                if tok == '(':
                    # Find matching close paren
                    depth = 1
                    j = i + 1
                    sub_tokens = []
                    while j < len(expr_tokens) and depth > 0:
                        if expr_tokens[j] == '(':
                            depth += 1
                        elif expr_tokens[j] == ')':
                            depth -= 1
                            if depth == 0:
                                break
                        sub_tokens.append(expr_tokens[j])
                        j += 1
                    term_set = _evaluate(sub_tokens, entries)
                    i = j + 1
                elif tok == ')':
                    i += 1
                    continue
                else:
                    # Plain term — find entries containing it
                    tok_lower = tok.lower()
                    term_set = {idx for idx, e in enumerate(entries)
                                if tok_lower in e.content.lower()}
                    i += 1

                if op == 'AND':
                    result = result & term_set if result else term_set
                elif op == 'OR':
                    result = result | term_set
                elif op == 'NOT':
                    result = result - term_set

                # Default to AND for next term unless explicit op follows
                if i < len(expr_tokens) and expr_tokens[i].upper() not in ('AND', 'OR', 'NOT'):
                    op = 'AND'

            return result

        matching_indices = _evaluate(tokens, self._entries)
        results = [self._entries[idx] for idx in matching_indices
                    if idx < len(self._entries)]
        results.sort(key=lambda e: e.importance, reverse=True)
        return results[:limit]

    # F59: Condense near-duplicate entries
    def condense(self, min_similarity: float = 0.8) -> Dict[str, Any]:
        """Merge near-duplicate entries into consolidated entries.

        Groups entries by similarity, merges each group into a single entry
        with combined tags, max importance, and earliest timestamp.

        Args:
            min_similarity: Threshold for considering entries duplicates

        Returns:
            Dict with 'merged_count', 'removed_count', 'groups' details
        """
        if len(self._entries) < 2:
            return {"merged_count": 0, "removed_count": 0, "groups": []}

        # Build clusters using union-find
        n = len(self._entries)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i in range(n):
            for j in range(i + 1, n):
                ratio = SequenceMatcher(None,
                                        self._entries[i].content,
                                        self._entries[j].content).ratio()
                if ratio >= min_similarity:
                    union(i, j)

        # Group by root
        groups: Dict[int, List[int]] = {}
        for i in range(n):
            root = find(i)
            groups.setdefault(root, []).append(i)

        merged_groups = []
        new_entries = []
        removed_count = 0

        for indices in groups.values():
            if len(indices) <= 1:
                # Keep as-is
                new_entries.append(self._entries[indices[0]])
                continue

            # Merge the group
            group_entries = [self._entries[i] for i in indices]
            merged_tags = list(set(t for e in group_entries for t in e.tags))
            merged_importance = max(e.importance for e in group_entries)
            merged_timestamp = min(e.timestamp for e in group_entries)
            # Use the longest content as the representative
            best = max(group_entries, key=lambda e: len(e.content))

            merged_entry = MemoryEntry(
                content=best.content,
                timestamp=merged_timestamp,
                metadata=best.metadata,
                tags=merged_tags,
                importance=merged_importance
            )
            new_entries.append(merged_entry)
            removed_count += len(indices) - 1
            merged_groups.append({
                "indices": indices,
                "count": len(indices),
                "representative": best.content[:80]
            })

        self._entries = new_entries
        if removed_count > 0:
            self._save()

        return {
            "merged_count": len(merged_groups),
            "removed_count": removed_count,
            "groups": merged_groups
        }

    # F60: Export as Markdown table
    def export_markdown_table(self, tags: Optional[List[str]] = None,
                              limit: int = 50) -> str:
        """Export entries as a GitHub-flavored Markdown table.

        Columns: # | Timestamp | Tags | Importance | Content (truncated)

        Args:
            tags: Optional tag filter
            limit: Max entries to include

        Returns:
            Markdown table string
        """
        entries = self._entries
        if tags:
            tag_set = set(tags)
            entries = [e for e in entries if tag_set & set(e.tags)]

        # Sort by timestamp descending (newest first)
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        entries = entries[:limit]

        lines = [
            "| # | Timestamp | Tags | Importance | Content |",
            "|---|-----------|------|------------|---------|"
        ]

        for i, e in enumerate(entries, 1):
            ts = e.timestamp.strftime("%Y-%m-%d %H:%M")
            tag_str = ", ".join(e.tags) if e.tags else "—"
            imp_bar = "★" * round(e.importance * 5)
            content = e.content[:60].replace("|", "\\|").replace("\n", " ")
            if len(e.content) > 60:
                content += "…"
            lines.append(f"| {i} | {ts} | {tag_str} | {imp_bar} ({e.importance:.2f}) | {content} |")

        return "\n".join(lines)

    def range_query(self, start_time: datetime, end_time: Optional[datetime] = None,
                    tags: Optional[List[str]] = None, content_filter: Optional[str] = None,
                    limit: int = 50, sort_desc: bool = True) -> List[MemoryEntry]:
        """Time-bounded memory search with optional tag and content filters.

        Args:
            start_time: Inclusive start of time range
            end_time: Exclusive end (defaults to now)
            tags: Optional tag filter (entries must have ANY of these tags)
            content_filter: Optional substring match on content
            limit: Max results
            sort_desc: True=newest first, False=oldest first

        Returns:
            Matching entries within the time window
        """
        if end_time is None:
            end_time = datetime.now()

        results = [
            e for e in self._entries
            if start_time <= e.timestamp < end_time
        ]

        if tags:
            tag_set = set(tags)
            results = [e for e in results if tag_set & set(e.tags)]

        if content_filter:
            results = [e for e in results if content_filter.lower() in e.content.lower()]

        results.sort(key=lambda e: e.timestamp, reverse=sort_desc)
        return results[:limit]

    def annotate(self, index: int, note: str) -> bool:
        """Attach a human-readable annotation to a memory entry.

        Annotations are stored in metadata["_annotations"] as a list of
        {"note": str, "timestamp": str} dicts.

        Args:
            index: Entry index
            note: Annotation text

        Returns:
            True if entry exists and was annotated
        """
        if index < 0 or index >= len(self._entries):
            return False
        entry = self._entries[index]
        anns = entry.metadata.setdefault("_annotations", [])
        anns.append({"note": note, "timestamp": datetime.now().isoformat()})
        self._save()
        return True

    def annotations(self, index: int) -> List[Dict[str, str]]:
        """Retrieve all annotations for a memory entry.

        Args:
            index: Entry index

        Returns:
            List of {"note": str, "timestamp": str} dicts, empty if not found
        """
        if index < 0 or index >= len(self._entries):
            return []
        return list(self._entries[index].metadata.get("_annotations", []))

    def most_annotated(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return entries with the most annotations, sorted by count descending.

        Returns:
            List of {"index": int, "content_preview": str, "annotation_count": int, "annotations": list}
        """
        scored = []
        for i, e in enumerate(self._entries):
            count = len(e.metadata.get("_annotations", []))
            if count > 0:
                scored.append({
                    "index": i,
                    "content_preview": e.content[:80],
                    "annotation_count": count,
                    "annotations": e.metadata["_annotations"],
                })
        scored.sort(key=lambda x: x["annotation_count"], reverse=True)
        return scored[:limit]
