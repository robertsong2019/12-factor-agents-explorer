#!/usr/bin/env python3
"""
Edge Agent Dashboard - 功能测试脚本
"""

import requests
import time
import json
import sys


# API基础URL
BASE_URL = "http://localhost:8000"

def test_connection():
    """测试API连接"""
    print("🔍 测试API连接...")
    try:
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
        print("✅ API连接正常")
        return True
    except Exception as e:
        print(f"❌ API连接失败: {e}")
        return False


def test_list_agents():
    """测试获取Agent列表"""
    print("\n🔍 测试获取Agent列表...")
    try:
        response = requests.get(f"{BASE_URL}/api/agents")
        assert response.status_code == 200
        agents = response.json()
        print(f"✅ 获取到 {len(agents)} 个Agent")
        return agents
    except Exception as e:
        print(f"❌ 获取Agent列表失败: {e}")
        return []


def test_create_agent():
    """测试创建Agent"""
    print("\n🔍 测试创建Agent...")
    config = {
        "id": "test-agent",
        "name": "测试Agent",
        "command": "python /root/.openclaw/workspace/edge-agent-dashboard/example_agent.py",
        "working_dir": "/root/.openclaw/workspace/edge-agent-dashboard",
        "auto_start": False
    }
    try:
        response = requests.post(
            f"{BASE_URL}/api/agents",
            json=config,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        agent = response.json()
        print(f"✅ Agent创建成功: {agent['name']}")
        return agent
    except Exception as e:
        print(f"❌ 创建Agent失败: {e}")
        return None


def test_start_agent(agent_id):
    """测试启动Agent"""
    print(f"\n🔍 测试启动Agent: {agent_id}...")
    try:
        response = requests.post(f"{BASE_URL}/api/agents/{agent_id}/start")
        assert response.status_code == 200
        print(f"✅ Agent启动成功")
        return True
    except Exception as e:
        print(f"❌ 启动Agent失败: {e}")
        return False


def test_get_agent(agent_id):
    """测试获取单个Agent"""
    print(f"\n🔍 测试获取Agent状态: {agent_id}...")
    try:
        response = requests.get(f"{BASE_URL}/api/agents/{agent_id}")
        assert response.status_code == 200
        agent = response.json()
        print(f"✅ Agent状态: {agent['state']}, PID: {agent.get('pid')}")
        return agent
    except Exception as e:
        print(f"❌ 获取Agent状态失败: {e}")
        return None


def test_get_metrics():
    """测试获取资源指标"""
    print("\n🔍 测试获取资源指标...")
    try:
        response = requests.get(f"{BASE_URL}/api/metrics")
        assert response.status_code == 200
        metrics = response.json()
        print(f"✅ CPU: {metrics['cpu_percent']:.1f}%, "
              f"内存: {metrics['memory_percent']:.1f}%, "
              f"网络: {metrics['network_sent_mb']:.2f}MB/s")
        return metrics
    except Exception as e:
        print(f"❌ 获取资源指标失败: {e}")
        return None


def test_get_metrics_history():
    """测试获取历史指标"""
    print("\n🔍 测试获取历史指标...")
    try:
        response = requests.get(f"{BASE_URL}/api/metrics/history?seconds=10")
        assert response.status_code == 200
        history = response.json()
        print(f"✅ 历史数据点: {len(history['timestamps'])}")
        return history
    except Exception as e:
        print(f"❌ 获取历史指标失败: {e}")
        return None


def test_get_logs(agent_id):
    """测试获取日志"""
    print(f"\n🔍 测试获取日志: {agent_id}...")
    try:
        response = requests.get(f"{BASE_URL}/api/agents/{agent_id}/logs?lines=5")
        assert response.status_code == 200
        logs = response.json()
        print(f"✅ 日志条数: {len(logs)}")
        if logs:
            print(f"   最新日志: {logs[-1][:50]}...")
        return logs
    except Exception as e:
        print(f"❌ 获取日志失败: {e}")
        return []


def test_stop_agent(agent_id):
    """测试停止Agent"""
    print(f"\n🔍 测试停止Agent: {agent_id}...")
    try:
        response = requests.post(f"{BASE_URL}/api/agents/{agent_id}/stop")
        assert response.status_code == 200
        print(f"✅ Agent停止成功")
        return True
    except Exception as e:
        print(f"❌ 停止Agent失败: {e}")
        return False


def test_delete_agent(agent_id):
    """测试删除Agent"""
    print(f"\n🔍 测试删除Agent: {agent_id}...")
    try:
        response = requests.delete(f"{BASE_URL}/api/agents/{agent_id}")
        assert response.status_code == 200
        print(f"✅ Agent删除成功")
        return True
    except Exception as e:
        print(f"❌ 删除Agent失败: {e}")
        return False


def main():
    """主测试流程"""
    print("=" * 60)
    print("Edge Agent Dashboard - 功能测试")
    print("=" * 60)

    # 测试连接
    if not test_connection():
        print("\n❌ Dashboard未运行，请先启动: edge-agent-dashboard")
        sys.exit(1)

    # 获取初始Agent列表
    initial_agents = test_list_agents()

    # 创建测试Agent
    test_agent = test_create_agent()
    if not test_agent:
        print("\n❌ 创建测试Agent失败")
        sys.exit(1)

    agent_id = test_agent['id']

    # 启动Agent
    if test_start_agent(agent_id):
        # 等待Agent启动
        time.sleep(2)

        # 获取Agent状态
        test_get_agent(agent_id)

        # 获取资源指标
        test_get_metrics()

        # 等待历史数据积累
        time.sleep(3)

        # 获取历史指标
        test_get_metrics_history()

        # 获取日志
        test_get_logs(agent_id)

        # 停止Agent
        test_stop_agent(agent_id)

        # 等待Agent停止
        time.sleep(1)

        # 确认Agent已停止
        test_get_agent(agent_id)

    # 清理：删除测试Agent
    test_delete_agent(agent_id)

    print("\n" + "=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
