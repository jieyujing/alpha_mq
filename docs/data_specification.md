# 数据说明文档 (Data Specification)

## 1. 目录结构
所有下载的数据均以 CSV 格式存储在 `data/exports/` 目录下，采用“维度划分 + 个股独立成表 (One File Per Symbol)”的结构：

```text
data/exports/
├── history_1d/           # 每日行情数据 (包含个股及指数基准)
├── valuation/            # 每日估值衍生指标 (PE/PB等)
├── mktvalue/             # 每日市值数据 (总市值、A股市值)
├── basic/                # 每日基础指标 (收盘价、换手率、总股本、流通股本)
├── fundamentals_balance/ # [全量] 资产负债表 (季度明细)
├── fundamentals_income/  # [全量] 利润表 (季度明细)
└── fundamentals_cashflow/# [全量] 现金流量表 (季度明细)
```

---

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
*   核心字段：`pe_ttm` (滚动市盈率), `pb_mrq` (市净率), `ps_ttm` (市销率), `pcf_ttm_oper` (现金流市现率)。

### 2.3 每日市值 (mktvalue)
*   `tot_mv`: 总市值 (Total Market Value)
*   `a_mv`: A股总市值 / 流通市值

### 2.4 每日基础指标 (basic)
*   `tclose`: 当日收盘价
*   `turnrate`: 换手率 (%)
*   `ttl_shr`: 总股本 (Total Shares)
*   `circ_shr`: 流通股本 (Circulating Shares)

### 2.5 财务报表 (Fundamentals - 全量字段)
财务报表已通过**分段抓取技术**实现了全科目覆盖。
- **公共维度列**：
    - `symbol`: 股票代码
    - `pub_date`: 公告披露日期 (用于实盘由于“后视偏差”的规避)
    - `rpt_date`: 报表所属截止日期 (用于计算季度同比/环比)
- **明细科目**：
    - 采用掘金官方缩写 ID 命名 (例如 `ttl_ast` 代表总资产, `net_prof` 代表净利润)。
    - 字段库包含：资产负债表（约 140 项）、利润表（约 80 项）、现金流量表（约 130 项）。
    - 完整 ID 字典可参考 `gm_skill` 或掘金官方文档。

---

## 3. 工程化抓取逻辑 (Engineering Logic)

### 3.1 字段分段与合并 (Chunked Merging)
由于掘金 API 限制单次请求不能超过 20 个字段，脚本采用了以下策略：
- **切片**：将 100+ 字段按每 15 个一组切分。
- **循环请求**：对同一 Symbol 依次请求所有字段切片。
- **横向对齐**：使用 Pandas `outer merge`，基于 `(symbol, pub_date, rpt_date)` 三元核心键进行精确对齐，确保生成一张完整的宽表 CSV。

### 3.2 鲁棒性保障
- **RateLimiter**：严格遵守单 Token 每 5 分钟 1000 次的请求限制（配置为 950 次安全水位）。
- **断点续传**：脚本启动时自动识别存储目录中已存在的 Symbol 列表，仅下载增量或缺失数据。
- ** timezone-free**：所有时间戳统一移除时区，确保存储与后续分析的一致性。

### 3.3 数据更新建议
财务报表随上市公司公告实时披露。建议在财报季（4月、8月、10月）结束后全量跑一次下载脚本，以补全最新披露的季报数据。

---

## 4. 注意事项
- **停牌处理**：停牌期间估值和基础指标可能缺失，历史行情会保持上一交易日价格（或取决于 API 填充策略）。
- **指数基准**：指数（如 SHSE.000852）本身没有财务报表数据，相关文件夹下不会生成对应的 CSV。
