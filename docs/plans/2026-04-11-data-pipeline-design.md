# Polars Data Pipeline Design

## Context
放弃了限制极多、生态封闭的 Qlib 底座，全面转向自研的高性能全内存计算框架。
底层数据存储和计算引擎更迭为 `polars` + `parquet`，这为接下来的时序信号和截面回归提供了亿行级别秒级处理的性能支撑。

## Architecture

架构依旧基于之前的构想（L1层提取数据结构，L2层提取交易规则结构，L3层提取研究池）：

1. **L1 结构清洗层 `clean_basic_l1.py`**
   - 读取散落在 `data/exports/` 的小 CSV 文件 (`history_1d`, `basic`, `adj_factor`, `calendar`)。
   - 使用 Polars LazyFrame 高并发读取合并，复权价格运算 (使用 `close * adj_factor` 生成 `close_adj` 等)。
   - 对齐全局交易日，填补停牌带来的缺失行记录（Forward fill / Dummy fill）。
   - 输出物理表：`data/backend/l1_basic.parquet`。

2. **L2 交易状态层 `tradability_l2.py`**
   - 依赖 `l1_basic.parquet`。
   - 判定每日是否涨停 `is_limit_up`，跌停 `is_limit_down`，一字涨跌停 `is_one_word_limit_xx`。
   - 纳入静态文件 `static/instruments.csv`，计算 `listed_days`（上市天数）。
   - 保留退市和停牌记录，打标签不筛除。
   - 输出物理表：`data/backend/l2_status.parquet`。

3. **L3 研究股票池层 `universe_l3.py`**
   - 依赖 `l2_status.parquet`。
   - 生成基础宇宙 `in_universe_base`（非ST，非停牌，上市满一年等）。
   - 获取流动性宇宙 `in_universe_liquidity`（近期20日日均成交额高于某分位数）。
   - 生成最终投资域，判定真正的交易可行性（次日开盘非一字板或停牌才能买入等 `can_buy_next_open` 等）。
   - 输出物理表：`data/backend/l3_universe.parquet`。
