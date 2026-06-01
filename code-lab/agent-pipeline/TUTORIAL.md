# 🧪 Agent Pipeline 教程

> 从 "Hello World" 到多步工作流，理解管道式编程的力量。
> 零外部依赖，纯 Python 标准库。

## 前置知识

- Python 基础（函数、字典、列表）
- YAML 基本语法
- 对 Unix pipe（`|`）有概念会有帮助，但不是必须的

---

## 核心思想

Unix 哲学：**每个工具做好一件事，通过管道串联出强大工作流。**

```bash
# Unix pipe
cat log.txt | grep ERROR | wc -l

# Agent Pipeline 做同样的事，但更结构化
echo "log.txt" | python pipeline.py run examples/log-analysis.yaml
```

数据像水流一样经过每个步骤，上一步的输出就是下一步的输入。

---

## Step 1: Hello Pipeline — 三行 YAML 入门

创建 `hello.yaml`：

```yaml
name: hello-pipeline
description: 最简单的 pipeline

steps:
  - tool: text.clean
    config:
      lowercase: true
      trim_whitespace: true
```

运行：

```bash
echo "  Hello   WORLD!!!  " | python pipeline.py run hello.yaml
# 输出: "hello world!!!"
```

**发生了什么？**
1. 输入 `"  Hello   WORLD!!!  "` 进入 Step 1
2. `text.clean` 工具做了：小写化 + 去多余空白
3. 结果输出到 stdout

---

## Step 2: 串联多个工具 — 数据流转

管道的威力在于串联。每一步接收上一步的输出：

```yaml
name: word-counter
description: 清理 → 分词 → 统计

steps:
  - tool: text.clean
    config:
      lowercase: true
      remove_special_chars: true
      trim_whitespace: true

  - tool: text.tokenize
    config:
      method: word

  - tool: text.stats
    config:
      output_format: json
```

运行：

```bash
echo "The Quick Brown Fox Jumps Over The Lazy Dog!!!" | python pipeline.py run word-counter.yaml --debug
```

Debug 模式会显示每一步的输入输出：

```
--- Step 1/3 ---
  [text.clean] input: "The Quick Brown Fox..."
  [text.clean] output: "the quick brown fox jumps over the lazy dog"

--- Step 2/3 ---
  [text.tokenize] input: "the quick brown fox..."
  [text.tokenize] output: ["the", "quick", "brown", "fox", ...]

--- Step 3/3 ---
  [text.stats] input: ["the", "quick", ...]
  [text.stats] output: {"length": 43, "word_count": 9, ...}
```

**数据流图：**
```
"原始文本" → [clean] → "清理后文本" → [tokenize] → ["词", "词", ...] → [stats] → {统计}
```

---

## Step 3: 日志分析实战 — 提取有意义的信息

真实场景：从服务器日志中提取 ERROR 信息。

创建 `log-analysis.yaml`：

```yaml
name: log-analysis
description: 从日志中提取错误信息

steps:
  # Step 1: 清理日志格式
  - tool: text.clean
    config:
      trim_whitespace: true

  # Step 2: 用正则提取错误
  - tool: agent.extract
    config:
      patterns:
        - "ERROR: (?P<error>.+)"
        - "\\[(?P<timestamp>\\d{4}-\\d{2}-\\d{2}.*?)\\]"

  # Step 3: 转为 JSON 方便程序消费
  - tool: data.transform
    config:
      format: json
```

运行：

```bash
# 输入日志
cat <<EOF | python pipeline.py run log-analysis.yaml
[2026-06-01 10:00:01] INFO: Server started
[2026-06-01 10:05:23] ERROR: Database connection failed
[2026-06-01 10:06:00] WARNING: Retry attempt 1
[2026-06-01 10:10:45] ERROR: Timeout waiting for response
EOF
```

输出：
```json
{
  "error": "Timeout waiting for response",
  "timestamp": "2026-06-01 10:10:45"
}
```

---

## Step 4: 列表处理 — 批量操作

Pipeline 不仅能处理字符串，也能处理列表：

```yaml
name: list-processor
description: 处理一组标签

steps:
  - tool: text.split
    config:
      mode: separator
      separator: ","

  - tool: list.map
    config:
      operation: strip

  - tool: list.filter
    config:
      remove_empty: true
      min_length: 2

  - tool: list.sort
    config:
      reverse: false

  - tool: list.join
    config:
      separator: " | "
```

运行：

```bash
echo "python,  rust, , go, typescript, js,  rust" | python pipeline.py run list-processor.yaml
# 输出: "go | js | python | rust | typescript"
```

**流程：**
```
"python,  rust, , go, typescript, js,  rust"
  → split → ["python", "  rust", "", " go", "typescript", "js", "  rust"]
  → map(strip) → ["python", "rust", "", "go", "typescript", "js", "rust"]
  → filter → ["python", "rust", "go", "typescript", "js", "rust"]
  → sort → ["go", "js", "python", "rust", "rust", "typescript"]
  → join → "go | js | python | rust | rust | typescript"
```

---

## Step 5: 交互式 REPL — 边试边调

不需要写 YAML，直接在 REPL 中构建管道：

```bash
python pipeline.py repl
```

```
pipeline> tools
  text.clean                - Clean text: lowercase, remove...
  text.tokenize             - Tokenize text...
  text.stats                - Calculate text statistics...
  ...

pipeline> add text.clean {"lowercase": true}
✓ 添加步骤: text.clean

pipeline> add text.tokenize {"method": "word"}
✓ 添加步骤: text.tokenize

pipeline> add text.stats {"output_format": "json"}
✓ 添加步骤: text.stats

pipeline> steps
当前 Pipeline (3 步):
  1. text.clean {"lowercase": true}
  2. text.tokenize {"method": "word"}
  3. text.stats {"output_format": "json"}

pipeline> run "Hello Agent Pipeline World"
{"length": 25, "word_count": 4, ...}
```

---

## Step 6: 编写自定义工具

扩展 Pipeline 只需 3 步：

```python
from pipeline import Tool, Pipeline, ToolRegistry, register_builtin_tools

# 1. 定义工具
class SentimentTool(Tool):
    name = "text.sentiment"
    description = "Simple keyword-based sentiment analysis"
    
    def process(self, input_data, config):
        text = str(input_data).lower()
        positive_words = config.get("positive", ["good", "great", "awesome", "love"])
        negative_words = config.get("negative", ["bad", "terrible", "hate", "awful"])
        
        pos_score = sum(1 for w in positive_words if w in text)
        neg_score = sum(1 for w in negative_words if w in text)
        
        if pos_score > neg_score:
            sentiment = "positive"
        elif neg_score > pos_score:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "positive_score": pos_score,
            "negative_score": neg_score,
        }

# 2. 注册工具
register_builtin_tools()  # 先注册内置工具
Pipeline.register_tool(SentimentTool())

# 3. 在 YAML 中使用
```

对应 YAML：
```yaml
steps:
  - tool: text.clean
    config:
      lowercase: true
  - tool: text.sentiment
    config:
      positive: ["棒", "好", "喜欢", "awesome"]
      negative: ["糟", "坏", "讨厌", "terrible"]
```

---

## 架构总览

```
                    ┌─────────────┐
   输入 ──────────→ │  Pipeline    │
                    │  (引擎)      │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Step 1   │ │ Step 2   │ │ Step 3   │
        │ text.clean│ │ extract │ │ transform│
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             ▼            ▼            ▼
          数据流 ──────→ 数据流 ──────→ 最终输出
```

**核心类：**

| 类 | 职责 | 关键方法 |
|---|------|---------|
| `Tool` | 工具基类 | `process(input, config)` |
| `ToolRegistry` | 工具注册表 | `register()`, `get()`, `list()` |
| `PipelineStep` | 单个步骤 | `execute(input)` |
| `Pipeline` | 管道引擎 | `run()`, `from_yaml()`, `add_step()` |

---

## 常见模式

### 模式 1: ETL（提取-转换-加载）
```yaml
steps:
  - tool: file.read        # 提取
  - tool: text.clean       # 转换
  - tool: data.transform   # 转换
    config: {format: json}
  - tool: file.write       # 加载
    config: {path: output.json}
```

### 模式 2: 日志管道
```yaml
steps:
  - tool: file.lines       # 按行读取
  - tool: list.filter      # 过滤 ERROR
    config: {min_length: 5}
  - tool: list.take
    config: {n: 10}        # 取前 10 条
  - tool: list.join
    config: {separator: "\n"}
```

### 模式 3: LLM 输出处理
```yaml
steps:
  - tool: agent.json_extract    # 从 LLM 回复提取 JSON
  - tool: data.transform        # 格式化
    config: {format: json}
```

---

## 练习

1. **基础**: 写一个 pipeline，输入一篇文章，输出字数统计
2. **进阶**: 写一个 pipeline，从 git log 中提取每周提交数最多的开发者
3. **挑战**: 写一个自定义工具 `text.encrypt`（凯撒密码），然后用 pipeline 加密 → base64 编码 → 输出

---

## 下一步

- 阅读 [pipeline.py](pipeline.py) 源码了解完整实现
- 浏览 [examples/](examples/) 目录获取更多 YAML 配置
- 阅读 [README.md](README.md) 了解所有内置工具

---

*Code Lab 产物 · 2026-06-02*
