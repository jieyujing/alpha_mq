# 数据说明文档 (Data Specification)

## 1. 目录结构
所有下载的数据均以 CSV 格式存储在 `data/exports/` 目录下，采用“维度划分 + 个股独立成表 (One File Per Symbol)”的结构：

```text
data/exports/
├── history_1d/           # 每日行情数据 (包含个股及指数基准)
├── valuation/            # 每日估值衍生指标
├── mktvalue/             # 每日市值数据
├── basic/                # 每日基础指标 (换手率、股本等)
├── fundamentals_balance/ # 资产负债表 (季度)
├── fundamentals_income/  # 利润表 (季度)
└── fundamentals_cashflow/# 现金流量表 (季度)
```

## 2. 字段定义

### 2.1 每日行情 (history_1d)
*   `symbol`: 标的代码 (如 SHSE.600012)
*   `bob`: 行情开始时间 (Beginning of Bar)
*   `eob`: 行情结束时间 (End of Bar)
*   `open`: 开盘价
*   `high`: 最高价
*   `low`: 最低价
*   `close`: 收盘价
*   `volume`: 成交量
*   `amount`: 成交额

### 2.2 每日估值 (valuation)
*   `trade_date`: 交易日期
*   `pe_ttm`: 滚动市盈率 (Price-to-Earnings Ratio, Trailing Twelve Months)
*   `pb_mrq`: 市净率 (Price-to-Book Ratio, Most Recent Quarter)
*   `ps_ttm`: 市销率 (Price-to-Sales Ratio, TTM)
*   `pcf_ttm_oper`: 经营活动现金流市现率 (Price-to-Cash Flow Ratio, TTM)

### 2.3 每日市值 (mktvalue)
*   `tot_mv`: 总市值 (Total Market Value)
*   `a_mv`: A股总市值 / 流通市值

### 2.4 每日基础指标 (basic)
*   `tclose`: 当日收盘价
*   `turnrate`: 换手率 (%)
*   `ttl_shr`: 总股本 (Total Shares)
*   `circ_shr`: 流通股本 (Circulating Shares)

### 2.5 财务报表 (fundamentals_*)
包含各个季度披露的财务明细字段。核心字段包括：
*   `pub_date`: 公告日期
*   `rpt_date`: 报表截止日期
*   资产、负债、权益、营收、利润、现金流等明细项目（具体字段名遵循掘金 SDK 定义）。

## 3. 重要说明
*   **时区处理**：所有时间戳字段均已移除时区信息 (`tz_localize(None)`)，方便直接加载到 Pandas 或进行特征工程，避免时区冲突。
*   **断点续传**：脚本运行时会自动扫描目录，若某个 Symbol 的 CSV 已存在则会跳过，无需重新下载。
*   **指数基准**：指数本身（如 SHSE.000852）的数据仅存在于 `history_1d` 中，不包含估值和财务数据。
*   **空数据处理**：对于停牌或新上市标的，若 API 返回空结果，脚本会记录日志并跳过，不会产生空文件。
