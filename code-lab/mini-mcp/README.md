# Mini-MCP: 轻量级工具注册与调用框架

一个用 Python 实现的微型 MCP (Model Context Protocol) 概念演示。约 150 行代码，展示了工具注册、发现和调用的核心思想。

## 核心特性

- **工具注册**: 装饰器式工具定义，自动提取参数类型
- **工具发现**: 列出所有可用工具及其 schema
- **工具调用**: JSON 参数 → 函数调用 → JSON 返回
- **交互式 REPL**: 直接在命令行与工具交互
- **CLI 模式**: 支持脚本化调用

## 内置工具

| 工具名 | 功能 |
|--------|------|
| `time` | 获取当前时间（支持时区） |
| `calc` | 安全数学表达式求值 |
| `hash` | 生成字符串哈希（md5/sha1/sha256） |
| `json_fmt` | JSON 格式化与验证 |
| `color` | 生成随机调色板（含亮度） |
| `base64` | Base64 编码/解码 |
| `stats` | 基础统计计算（均值/中位数/标准差） |

## 使用方法

```bash
# 交互式模式
python3 mini_mcp.py

# 列出工具
python3 mini_mcp.py --list

# 调用工具
python3 mini_mcp.py --call time
python3 mini_mcp.py --call calc '{"expr": "sin(pi/4) * 2"}'
python3 mini_mcp.py --call stats '{"numbers": [1,2,3,4,5]}'
```

## 交互式命令

- `list` - 列出所有工具
- `call <name> [json_args]` - 调用工具
- `schema <name>` - 查看工具 schema
- `help` - 显示帮助
- `quit` - 退出

## 相关项目

- **[mini-agent](../mini-agent/)** — Agent 框架（用工具的大脑）
- **[agent-pipeline](../agent-pipeline/)** — 工具串联工作流
- **[综合教程](../TUTORIAL.md)** — 从零构建 AI Agent

## 设计理念

MCP (Model Context Protocol) 的核心思想：**工具是独立可调用的单元，有明确的输入输出契约**。

Mini-MCP 模拟了这一概念：
1. 工具通过装饰器注册
2. 自动生成工具 schema（名称、描述、参数）
3. 统一的调用接口
4. JSON 作为通用数据格式

## 代码亮点

- 使用 `dataclass` 定义工具元数据
- `inspect` 模块自动提取函数签名
- 安全的数学表达式求值（仅允许特定函数）
- 完整的错误处理和友好的交互提示

## 扩展方法

```python
@registry.register("my_tool", description="自定义工具", param1="参数说明")
def my_tool(param1: str, param2: int = 10) -> dict:
    """工具函数"""
    return {"result": f"{param1} x {param2}"}
```

## 演示输出示例

```
$ python3 mini_mcp.py --call color '{"count": 3}'
{
  "count": 3,
  "colors": [
    {"hex": "#a8d4cb", "rgb": "rgb(168,212,203)", "luminance": 197.8},
    {"hex": "#d67c6a", "rgb": "rgb(214,124,106)", "luminance": 148.9},
    {"hex": "#55dd1d", "rgb": "rgb(85,221,29)", "luminance": 158.4}
  ]
}
```

---

**代码实验室产物** - 2026-04-09 晚间场
