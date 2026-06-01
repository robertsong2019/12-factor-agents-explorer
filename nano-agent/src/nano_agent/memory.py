"""
记忆管理系统 - 短期和长期记忆
"""

import json
from typing import List, Dict, Any, Optional
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

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
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

    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None, tags: Optional[List[str]] = None) -> None:
        """添加记忆"""
        entry = MemoryEntry(content=content, metadata=metadata or {}, tags=tags or [])
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
                    tags=item.get("tags", [])
                )
                self._entries.append(entry)

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
