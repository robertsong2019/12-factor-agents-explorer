# AKShare Finance Skill 📈

AKShare 财经数据接口库封装，提供股票、期货、期权、基金、外汇、债券、指数、加密货币等金融产品的数据查询。

## Features

- **A股数据** - 实时行情、历史K线、财务报表
- **期货/期权** - 合约信息、行情数据
- **基金** - 净值、持仓、排名
- **外汇/债券** - 汇率、债券收益率
- **指数** - 上证、深证、中证等指数数据
- **加密货币** - 主流币种行情

## Quick Start

```bash
# 安装依赖
pip install akshare>=1.12 pandas>=1.5

# 示例：查询A股实时行情
python3 -c "import akshare as ak; print(ak.stock_zh_a_spot_em())"
```

## Usage in OpenClaw

直接用自然语言提问即可：

- "查一下贵州茅台最近5天的行情"
- "今天的北向资金流向"
- "上证指数本月走势"

## Dependencies

```
pip install akshare>=1.12 pandas>=1.5
```

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | 完整接口文档和使用说明 |
| `references/` | AKShare 接口分类参考 |
