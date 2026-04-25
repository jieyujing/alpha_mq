---
name: akshare
description: 使用 akshare 获取中国金融市场实时数据和历史数据。当需要查询 A 股、港股、美股、指数、基金、期货等金融产品的实时行情、历史数据、财务报表时使用该技能。
license: MIT
metadata:
  author: Alice
  version: 1.0.0
  category: finance
  language: python
---

# Akshare 财经数据技能

此技能允许浮浮酱使用 akshare 库获取中国金融市场的实时和历史数据，包括股票、指数、基金、期货等各类金融产品。

## 核心功能

- **实时行情 (realtime)**: 获取股票/指数的实时行情数据
- **历史数据 (history)**: 获取股票/指数的历史 K 线数据
- **指数行情 (index)**: 获取各类指数（上证、深证、创业板等）的行情
- **板块数据 (sector)**: 获取行业板块和概念板块数据
- **财务数据 (financial)**: 获取个股财务指标和报表数据

## 使用方法

### 命令行接口

```bash
# 查询股票实时行情
python ~/.openclaw/skills/akshare/akshare_tool.py --code 000001

# 查询指数实时行情
python ~/.openclaw/skills/akshare/akshare_tool.py --code 000001 --type index

# 查询历史数据
python ~/.openclaw/skills/akshare/akshare_tool.py --code 000001 --mode history --start 20250101

# 查看指数概览
python ~/.openclaw/skills/akshare/akshare_tool.py --mode index-overview

# 查看热门板块
python ~/.openclaw/skills/akshare/akshare_tool.py --mode sector-top

# 查询股票信息
python ~/.openclaw/skills/akshare/akshare_tool.py --code 000001 --mode info

# 查询财务数据
python ~/.openclaw/skills/akshare/akshare_tool.py --code 000001 --mode financial
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--code`, `-c` | 股票/指数代码 | 无 |
| `--type`, `-t` | 代码类型 (stock/index) | stock |
| `--mode`, `-m` | 查询模式 | realtime |
| `--period`, `-p` | K 线周期 (daily/weekly/monthly) | daily |
| `--start` | 开始日期 (YYYYMMDD) | 无 |
| `--end` | 结束日期 (YYYYMMDD) | 当前日期 |

### 查询模式

- `realtime`: 实时行情（需要 `--code`）
- `history`: 历史 K 线（需要 `--code`，可选 `--start`, `--end`, `--period`）
- `index-overview`: A 股主要指数概览（无需参数）
- `sector-top`: 热门板块排行（无需参数）
- `info`: 股票基本信息（需要 `--code`）
- `financial`: 财务指标（需要 `--code`）

## 依赖安装

```bash
pip install akshare pandas
```

## 使用场景

- 查询某只股票的实时价格、涨跌幅、成交量等
- 获取股票历史 K 线数据进行技术分析
- 查看大盘指数（上证、深证、创业板）行情
- 发现热门行业板块和概念板块
- 分析个股财务指标和经营状况
- 配合反身性分析系统进行市场数据验证

## 注意事项

- 数据来源于东方财富网等公开数据源
- 实时行情数据有约 15 分钟延迟
- A 股交易时间：工作日 9:30-11:30, 13:00-15:00
- 非交易时间获取的是最新收盘价
