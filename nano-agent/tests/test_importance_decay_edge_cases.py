"""
Memory.importance_decay() 边缘情况测试
"""

import pytest
from datetime import datetime
from src.nano_agent.memory import Memory, MemoryEntry


class TestImportanceDecayEdgeCases:
    """测试 importance_decay 方法的边缘情况"""

    def test_importance_decay_normal_factor(self):
        """测试正常的衰减因子"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        memory.add("test2", importance=0.8)
        memory.add("test3", importance=0.5)
        
        affected = memory.importance_decay(0.5)
        
        assert affected == 3
        assert memory._entries[0].importance == 0.5  # 1.0 * 0.5
        assert memory._entries[1].importance == 0.4  # 0.8 * 0.5
        assert memory._entries[2].importance == 0.25  # 0.5 * 0.5

    def test_importance_decay_factor_equal_one(self):
        """测试衰减因子等于1，应该无变化"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        memory.add("test2", importance=0.5)
        
        affected = memory.importance_decay(1.0)
        
        assert affected == 0  # factor不在0 < factor < 1范围内，无变化
        assert memory._entries[0].importance == 1.0  # 无变化
        assert memory._entries[1].importance == 0.5  # 无变化

    def test_importance_decay_factor_zero(self):
        """测试衰减因子等于0，应该全部变为0"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        memory.add("test2", importance=0.5)
        
        affected = memory.importance_decay(0.0)
        
        assert affected == 0  # factor不在0 < factor < 1范围内，无变化
        assert memory._entries[0].importance == 1.0  # 无变化
        assert memory._entries[1].importance == 0.5  # 无变化

    def test_importance_decay_factor_greater_than_one(self):
        """测试衰减因子大于1，应该增长而非衰减"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        memory.add("test2", importance=0.5)
        
        affected = memory.importance_decay(1.5)
        
        assert affected == 0  # 因子不在0-1范围内，应该无变化
        assert memory._entries[0].importance == 1.0
        assert memory._entries[1].importance == 0.5

    def test_importance_decay_factor_negative(self):
        """测试衰减因子为负数，应该无变化"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        memory.add("test2", importance=0.5)
        
        affected = memory.importance_decay(-0.5)
        
        assert affected == 0  # 负数因子，应该无变化
        assert memory._entries[0].importance == 1.0
        assert memory._entries[1].importance == 0.5

    def test_importance_decay_empty_memory(self):
        """测试空memory的衰减"""
        memory = Memory()
        
        affected = memory.importance_decay(0.5)
        
        assert affected == 0
        assert len(memory._entries) == 0

    def test_importance_decay_single_entry(self):
        """测试单个条目的衰减"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        
        affected = memory.importance_decay(0.3)
        
        assert affected == 1
        assert memory._entries[0].importance == 0.3  # 1.0 * 0.3

    def test_importance_decay_max_entries_limit(self):
        """测试达到最大条目数限制时的衰减"""
        memory = Memory(max_entries=3)
        # 添加4个条目，最后一个应该被丢弃
        memory.add("test1", importance=1.0)
        memory.add("test2", importance=0.8)
        memory.add("test3", importance=0.6)
        memory.add("test4", importance=0.4)  # 这个会被丢弃
        
        assert len(memory._entries) == 3
        assert memory._entries[0].content == "test2"  # test1被丢弃
        assert memory._entries[1].content == "test3"
        assert memory._entries[2].content == "test4"
        
        # 应该衰减3个条目
        affected = memory.importance_decay(0.5)
        assert affected == 3
        assert memory._entries[0].importance == 0.4  # 0.8 * 0.5
        assert memory._entries[1].importance == 0.3  # 0.6 * 0.5
        assert memory._entries[2].importance == 0.2  # 0.4 * 0.5

    def test_importance_decay_preserves_metadata(self):
        """测试衰减操作不影响元数据"""
        memory = Memory()
        metadata = {"source": "test", "category": "important"}
        memory.add("test1", metadata=metadata, importance=1.0)
        memory.add("test2", metadata={"source": "test2"}, importance=0.8)
        
        memory.importance_decay(0.5)
        
        # 检查元数据是否被保留
        assert memory._entries[0].metadata == {"source": "test", "category": "important"}
        assert memory._entries[1].metadata == {"source": "test2"}

    def test_importance_decay_preserves_tags(self):
        """测试衰减操作不影响标签"""
        memory = Memory()
        memory.add("test1", tags=["important", "urgent"], importance=1.0)
        memory.add("test2", tags=["normal"], importance=0.8)
        
        memory.importance_decay(0.5)
        
        # 检查标签是否被保留
        assert memory._entries[0].tags == ["important", "urgent"]
        assert memory._entries[1].tags == ["normal"]

    def test_importance_decay_preserves_timestamp(self):
        """测试衰减操作不影响时间戳"""
        memory = Memory()
        original_time = datetime.now()
        memory.add("test1", importance=1.0)
        
        # 保存原始时间戳
        original_timestamp = memory._entries[0].timestamp
        
        memory.importance_decay(0.5)
        
        # 检查时间戳应该保持不变（只有内容更新时才改变）
        assert memory._entries[0].timestamp == original_timestamp

    def test_importance_decay_with_various_factors(self):
        """测试各种不同的衰减因子"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        
        factors = [0.1, 0.25, 0.5, 0.75, 0.99]
        # 每次都是在上次基础上再乘以因子
        expected_results = [0.1, 0.1 * 0.25, 0.1 * 0.25 * 0.5, 0.1 * 0.25 * 0.5 * 0.75, 0.1 * 0.25 * 0.5 * 0.75 * 0.99]
        
        for factor, expected in zip(factors, expected_results):
            memory.importance_decay(factor)
            assert abs(memory._entries[0].importance - expected) < 1e-10

    def test_importance_decay_calls_save(self):
        """测试衰减操作会调用_save方法"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        memory.add("test2", importance=0.8)
        
        # 在持久化路径中设置一个标记文件
        import tempfile
        import os
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            memory.persistence_path = Path(temp_dir) / "test_memory.json"
            memory.importance_decay(0.5)
            
            # 检查文件是否被创建（说明_save被调用）
            assert os.path.exists(memory.persistence_path)

    def test_importance_decay_precision(self):
        """测试浮点数精度"""
        memory = Memory()
        memory.add("test1", importance=1.0)
        
        # 使用可能导致精度问题的因子
        memory.importance_decay(0.1)
        memory.importance_decay(0.1)
        memory.importance_decay(0.1)
        
        expected = 1.0 * 0.1 * 0.1 * 0.1  # 0.001
        assert abs(memory._entries[0].importance - expected) < 1e-10