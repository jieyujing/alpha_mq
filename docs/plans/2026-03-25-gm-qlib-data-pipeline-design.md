# GM 数据下载与 Qlib 格式转换方案设计 (2026-03-25)

## 1. 概述 (Overview)

本项目旨在基于掘金 (gm) 接口为中证 1000 指数增强策略构建数据流。目标是从 2015-01-01 至今，下载中证 1000 的所有成分股、日线 OHLCV 数据以及所有可用的基本面因子，并将其转换成 qlib 所需的二进制格式。

## 2. 核心架构与目录结构

系统采用分层存储策略，分离原始数据与处理后数据：

```text
alpha_mq/
├── data/
│   ├── raw/                 # 从 gm 接口下载的原始数据 (Parquet/CSV)
│   │   ├── stock_pool/      # 中证1000成分股历史名单 (csv)
│   │   ├── price/           # OHLCV 日K线数据 (parquet)
│   │   └── fundamentals/    # 基本面因子数据 (parquet)
│   ├── processed/           # 清洗和整合后的数据
│   ├── qlib_data/           # 最终转换生成的 qlib 二进制格式 (CSI1000)
│   └── scripts/             # 执行脚本
│       ├── download_gm.py   # 主要下载逻辑
│       └── convert_qlib.py  # 格式转换逻辑
```

## 3. 数据流水线设计 (Data Pipeline)

数据获取和转换采用分年度、分模块并行块下载策略（方案 1）：

### 3.1 股票池名单获取 (Instruments)
*   **频率**：获取 2015 年至今所有的中证 1000 ('SHSE.000852') 成分股变动记录。
*   **接口**：`gm.get_index_constituents`。
*   **输出**：保存为统一的 `csi1000_history.csv` 或直接生成符合 qlib 格式的 `csi1000.txt`。

### 3.2 价格数据下载 (OHLCV)
*   **标的**：历年出现过的所有中证 1000 成分股。
*   **接口**：`gm.get_history_symbol` (frequency='1d', adjust=1 / 前复权)。
*   **策略**：按年、按股票批次下载，每批下载完进行 `jitter_sleep` 随机休眠（0.5s-1.5s），降低被限流的风险。
*   **存储**：按年存储于 `data/raw/price/` 目录下（例如 `price_2015.parquet`）。

### 3.3 基本面因子下载 (Fundamentals)
*   **范围**：包含掘金提供的所有核心基本面宽表（如 `trading_derivative_indicator`, `balance_sheet`, `income_statement`, `cashflow_statement` 等）。
*   **接口**：`gm.get_fundamentals`。
*   **策略**：按年、按表独立获取，同样采用容错与休眠机制。
*   **存储**：存于 `data/raw/fundamentals/`（例如 `fundamentals_2015_balance_sheet.parquet`）。

### 3.4 Qlib 格式转换 (Converter)
*   读取 `raw` 目录下的 Parquet 文件，按 `symbol` 和 `datetime` 关联 OHLCV 和基本面指标。
*   调用（或模拟运行） `qlib.data.dump_all` 功能。
*   生成对应的 `calendars/day.txt`，`instruments/csi1000.txt` 以及 `features/*.bin` 文件。

## 4. 稳健性与错误恢复 (Robustness)

*   **Jitter Sleep**：请求间增加随机延迟，模拟真实调用频率。
*   **Checkpoint & 续传**：每次启动检测已完成的年份与批次，避免重头下载。
*   **Retry 机制**：针对网络异常（如 `ReadTimeout`）实现自动重试（最多 3 次）。
*   **日志记录**：将所有的错误和状态变动记录在文件和控制台中。

## 5. 依赖及环境 (Dependencies)
*   Python 3.12 
*   polars, pandas (数据处理)
*   gm (掘金 SDK，版本 >= 3.0)
*   pyqlib
*   Token 管理：使用 `GM_TOKEN` 环境变量或在脚本启动时初始化。
