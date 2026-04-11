# GM SDK CSI 1000 数据下载器设计文档

## 1. 概述 (Overview)
这是一个基于掘金 (GM) SDK 的高可靠性 Python 独立脚本。其核心目标是为回测和机器学习特征工程提供干净、完整的中证 1000 相关数据。
脚本将涵盖过去 1 年的行情、每日估值与基本面指标。同时，由于加入了策略回测基准等需求，本工具将一并获取中证 1000 自身的指数历史数据。

## 2. 核心组件 (Components)
*   **Constituent/Index Fetcher (标的解析器)**
    获取目前中证 1000 最新成分股作为 Base Pool。此外，主动将指数自身的代码（`SHSE.000852`）加入待处理清单，以获取对比基准的指数行情数据（对于指数，排除不能获取的财务和个股估值接口）。
*   **Rate Limiter (滑动窗速率流控)**
    应对 GM `1000次/5分钟` 的请求极限，类内采用 `collections.deque` 实现记录；超限前主动带抖动(Jitter)阻塞。
*   **Checkpoint & State Tracker (持久化与断点续传)**
    支持在任务挂掉后重启时，扫描 `data/exports` 下已经存在的数据，通过识别已成功的 `Symbol` 继续爬取，而不必重头发送全部 API。
*   **Categories Specific Fetcher (接口分发)**
    *   **历史行情队列 (`history`)**：支持成分股的批量查询（避免请求频次浪费）。
    *   **每日衍生变量队列 (`stk_get_daily_*`)**：针对 `valuation` / `basic` / `mktvalue` 分别发起。
    *   **基本面财报队列 (`stk_get_fundamentals_*`)**：针对 `balance` / `income` / `cashflow` 单独循环拉取。

## 3. 数据层与存储 (Storage Architecture)
由于不同金融数据维度的更新频率不同，且为了避免单表文件过于庞大，我们采用“维度划分 + 个股独立成表 (One File Per Symbol)”的树状存储结构。
数据最终落地至 `data/exports/` 对应的子目录中：
*   `data/exports/history_1d/{symbol}.csv` (存放个股每日行情，以及指数本身的行情)
*   `data/exports/valuation/{symbol}.csv` (存放个股日频估值衍生与市值因子)
*   `data/exports/fundamentals/{symbol}.csv` (存放个股的季度基本面表合并数据)

## 4. 容错防御与清洗 (Error Handling)
*   **时区剥离**: 数据取出后强制 `tz_localize(None)` 以避免 Parquet/CSV 长时间戳时区污染。
*   **空载跳过**: 对于新上市或者停牌导致特定时间段获取不到 DataFrame 的情形，实施 logging 忽略而不抛出 Exception 崩溃。
*   **请求重试**: 底层请求加入 3 次递增时长等待的 Retry 修饰。
