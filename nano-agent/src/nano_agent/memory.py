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
