# Agent Trust Network 教程

> 从零开始理解和使用多 Agent 信任网络可视化

---

## 1. 这是什么？

Agent Trust Network 是一个交互式 Web 应用，用于模拟和可视化多 Agent 系统中的信任关系。

核心问题：**在多个 AI Agent 协作时，如何评估谁值得信任？**

答案：使用 PageRank 算法（Google 搜索排名的同一算法）计算每个 Agent 的信任分数。

---

## 2. 快速启动

```bash
cd agent-trust-web
npm install
npm run dev
```

打开 http://localhost:5173

---

## 3. 5 分钟上手

### Step 1：添加 Agent

在左侧面板输入名称，选择行为类型：

| 类型 | 成功率 | 说明 |
|------|--------|------|
| 🟢 Cooperative | 90% | 总是合作，信任网络的正面力量 |
| 🟡 Neutral | 依当前信任 | 看人下菜碟 |
| 🔴 Malicious | 20% | 偶尔合作，大多数时候不靠谱 |
| ⚫ Adversarial | 10% | 主动破坏，信任网络的毒瘤 |

建议先添加：2 个 Cooperative + 1 个 Malicious，观察区别。

### Step 2：运行模拟

- 点击 **▶ Step** 运行一步（所有 Agent 随机交互一次）
- 点击 **×10** 快速推进 10 步
- 点击 **×50** 观察长期趋势

### Step 3：观察结果

- **节点大小** → 信任分数越高，节点越大
- **连线粗细** → 两个 Agent 之间信任权重越高，线越粗
- **节点颜色** → 绿色=高信任，红色=低信任
- **悬停** → 查看具体分数和趋势

---

## 4. 理解信任算法

### PageRank 公式

```
Trust(A) = (1 - d) / n + d × Σ [ Trust(S) × Weight(S→A) / OutDegree(S) ]
```

- `d = 0.85`（阻尼系数，防止信任无限累积）
- `n` = Agent 总数
- 每个指向 A 的信任源 S 都贡献一部分分数

### 直觉理解

1. 每个人一开始信任度相同
2. 每次交互后，根据结果调整信任权重
3. 被高信任者信任的人，自己也获得高信任
4. 长期不合作的人，信任分数会持续下降

---

## 5. 实验建议

### 实验 1：Malicious Agent 的衰落

1. 添加 5 个 Cooperative Agent
2. 添加 1 个 Malicious Agent
3. 运行 ×50
4. 观察 Malicious Agent 的信任分数持续下降

### 实验 2：信任恢复有多难

1. 先做实验 1
2. 导出网络（JSON）
3. 手动修改 JSON，把 Malicious 改为 Cooperative
4. 导入并继续运行 ×50
5. 观察：恢复信任比建立信任慢得多

### 实验 3：Adversarial Agent 的影响

1. 添加 3 个 Cooperative + 1 个 Adversarial
2. 运行 ×20
3. 观察 Adversarial 不仅自己分数低，还会拉低与之交互的 Agent 的分数

---

## 6. 进阶功能

### 导出/导入

- **导出**：点击顶部「Export」→ 下载 JSON 文件（包含所有 Agent、信任关系、分数）
- **导入**：点击「Import」→ 上载之前保存的 JSON

用途：保存实验快照、分享配置、A/B 对比。

### 查看详细指标

点击任意 Agent 节点，右侧面板显示：

- **Trust Score** — 当前信任分数（0-100%）
- **Confidence Index** — 这个分数有多可靠
- **Trend** — 上升/下降/稳定
- **Interaction History** — 最近交互记录

### 网络健康指标

右上角 Stats 面板：

- **Network Health** — 整体信任分布质量
- **Volatility** — 信任分数变动幅度
- **Avg Trust** — 平均信任分数

---

## 7. 技术细节

### 技术栈

- React 18 + TypeScript
- D3.js 力导向图
- Tailwind CSS
- Vite 构建

### 关键文件

| 文件 | 作用 |
|------|------|
| `src/trustNetwork.ts` | 核心模拟逻辑（PageRank 计算） |
| `src/components/NetworkGraph.tsx` | D3.js 可视化 |
| `src/components/ControlPanel.tsx` | 控制面板 |
| `src/types.ts` | 类型定义 |

### 扩展开发

```bash
# 开发模式
npm run dev

# 类型检查
npm run type-check

# 代码检查
npm run lint

# 生产构建
npm run build
```

---

## 8. 部署

```bash
# Vercel（最简单）
npx vercel

# Docker
docker build -t agent-trust-web .
docker run -p 8080:80 agent-trust-web

# 静态托管
npm run build
# 上传 dist/ 目录
```

---

## 常见问题

**Q: 为什么 Cooperative Agent 的分数也会波动？**
信任分数取决于交互对象。即使你总是合作，如果和你交互的人不靠谱，你的分数也会间接受影响。

**Q: PageRank 的阻尼系数可以调吗？**
当前固定 0.85。如需修改，编辑 `trustNetwork.ts` 中的 `DAMPING_FACTOR`。

**Q: 能模拟多少个 Agent？**
浏览器端计算，100+ Agent 会有性能问题。D3.js 力导向图在 50 个以内最流畅。

---

## 下一步

- 修改 `src/trustNetwork.ts` 中的行为参数，设计你自己的 Agent 类型
- 扩展 `types.ts` 添加新的指标维度
- 集成后端 API 实现持久化存储
