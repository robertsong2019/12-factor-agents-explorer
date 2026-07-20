"""
记忆管理系统 - 短期和长期记忆
"""

import json
import re
import copy
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
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
