# 🧪 Agent Pipeline

> 轻量级工具链引擎 — 用 YAML 声明工作流，组合小型工具构建复杂处理管道

类似 Unix pipe 的哲学：每个工具做好一件事，通过管道串联出强大工作流。纯 Python 标准库，零外部依赖。

## 核心概念

```
输入 → [Tool A] → [Tool B] → [Tool C] → 输出
```

一个 Pipeline 由多个 **Step** 组成，每个 Step 调用一个注册的 **Tool**。数据在步骤间流转，上一步的输出是下一步的输入。

## 快速开始

```bash
# 运行示例 pipeline
python pipeline.py run examples/basic.yaml

# 从 stdin 传入数据
echo "Hello World!!!" | python pipeline.py run examples/basic.yaml

# 调试模式
python pipeline.py run examples/basic.yaml --debug

# 交互式 REPL
python pipeline.py repl
```

## 内置工具

### 文本处理

| 工具 | 说明 | 关键配置 |
|------|------|----------|
| `text.clean` | 清理文本（大小写、特殊字符、空白） | `lowercase`, `remove_special_chars`, `trim_whitespace` |
| `text.tokenize` | 文本分词 | `method` (split/char/ngram), `max_tokens` |
| `text.stats` | 文本统计（字数、词数、行数） | `output_format` (json/table) |

### 数据处理

| 工具 | 说明 | 关键配置 |
|------|------|----------|
| `data.filter` | 过滤数据 | `remove_empty`, `pattern` |
| `data.transform` | 数据格式转换 | `format` (json/yaml/csv) |

### 列表处理

| 工具 | 说明 | 关键配置 |
|------|------|----------|
| `list.filter` | 列表过滤 | `condition` (non_empty/length/pattern) |
| `list.map` | 列表映射 | `operation` (trim/lowercase/uppercase/strip/length) |
| `list.join` | 列表合并为字符串 | `separator` |
| `list.take` | 取前 N 个元素 | `count` |
| `list.sort` | 排序 | `reverse`, `key` |

### AI Agent 工具

| 工具 | 说明 | 关键配置 |
|------|------|----------|
| `agent.extract` | 正则提取 | `patterns` (命名正则列表) |
| `agent.classify` | 关键词分类 | `categories` (关键词→类别映射) |
| `agent.json_extract` | 从文本提取 JSON | 无配置 |
| `agent.prompt_template` | 模板渲染 | `template`, 变量从输入中取 |

## YAML 配置格式

```yaml
name: my-pipeline
description: 做什么用的

steps:
  - tool: text.clean
    config:
      lowercase: true
      trim_whitespace: true

  - tool: agent.extract
    config:
      patterns:
        - "ERROR: (?P<error>.+)"
        - "\\[(?P<timestamp>\\d{4}-\\d{2}-\\d{2}.*?)\\]"

  - tool: data.transform
    config:
      format: json
```

## 示例

### 日志分析 (`examples/log-analysis.yaml`)

清理日志文本 → 提取 ERROR/WARNING → 过滤空结果 → 输出 JSON

```bash
python pipeline.py run examples/log-analysis.yaml -i server.log
```

### 中文文本处理 (`examples/chinese-text.yaml`)

清洗中文文本 → 分词 → 统计

### 文本分类 (`examples/text-classification.yaml`)

清理文本 → 关键词分类 → 过滤

## CLI 命令

```bash
python pipeline.py run <config.yaml>    # 运行 pipeline
python pipeline.py run <config.yaml> --debug  # 调试模式
python pipeline.py run <config.yaml> -i input.txt  # 指定输入
python pipeline.py run <config.yaml> -o output.json  # 指定输出
python pipeline.py tools               # 列出所有注册工具
python pipeline.py info <tool.name>    # 查看工具详情
python pipeline.py repl                # 交互式 REPL
```

## 自定义工具

继承 `Tool` 类并注册：

```python
from pipeline import Tool, ToolRegistry, Pipeline

class MyTool(Tool):
    name = "my.custom"
    description = "我的自定义工具"
    
    def process(self, input_data, config):
        result = do_something(input_data)
        return result

Pipeline.register_tool(MyTool())
```

## 测试

```bash
python -m pytest tests/
```

## 相关项目

- **[mini-agent](../mini-agent/)** — Agent 框架（编排 Pipeline 的大脑）
- **[mini-mcp](../mini-mcp/)** — 工具注册与调用协议
- **[综合教程](../TUTORIAL.md)** — 从零构建 AI Agent

## 设计理念

- **零依赖** — 纯标准库，拿来就用
- **声明式** — YAML 定义工作流，代码只写工具
- **可组合** — 小工具自由组合，像搭积木
- **可调试** — debug 模式输出每步的输入输出和耗时

## License

MIT
