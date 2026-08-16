# 2026-08-17 文档完善报告（documentation-morning）

## 变更范围（commit 4228629）

### agent-memory-graph README
- **追平 Cycles 449-457**（昨日报错停在 448）：新增「压缩残差、保留遗忘与对抗鲁棒」章节，11 个条目
  - C449 `extract_residuals` / `residual_report` / `consolidate_with_residuals`（压缩残差三件套）
  - C450 `forget_preserving` / `batch_forget_preserving`（保留式遗忘，与 safe_forget 互补）
  - C451 LoCoMo 适配器 / C452 对抗调参负发现 / C453 全量基线
  - C454 `run_eval` 每题独立 haystack + CLI --mode eval
  - C455 `subject_support_gate`（零 LLM 主语调包检测）
  - C456 when-日期解析 / C457 temporal-arithmetic 4.0x
- badge 9241 → **9406**（pytest --collect-only 实测验证）
- 统计行：457 cycles / 295 天零回滚
- 纪律遵守：全部 API 签名源码 grep 后撰写，无凭记忆写

### code-lab README
- 进化史表 +9 行（449-457）
- 里程碑段落重写为「压缩残差 + 对抗鲁棒 + 时间推理（Cycles 449-457，9406 tests）」，441-448 降为"此前"

## 无重叠确认
- knowledge-org（02:00）只动 HEARTBEAT/MEMORY，无 README 冲突
