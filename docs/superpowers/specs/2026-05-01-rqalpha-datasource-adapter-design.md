# RQAlpha 数据源适配器设计文档 (2026-05-01)

## 1. 背景与目标
本项目目前主要使用掘金量化 (GM API) 作为在线数据源。为了支持本地离线研究并利用 RQAlpha 的 Bundle 数据，需要通过 **适配器模式** 添加对 RQAlpha 本地数据束的支持。

数据源路径定为: `/Users/link/.rqalpha/bundle`

## 2. 架构设计 (Adapter Pattern)
我们将 `RQAlpha` 的数据访问接口适配到项目现有的 `DataSource` 协议 (Protocol)。

### 2.1 协议定义回顾
`DataSource` 协议要求实现以下方法：
- `fetch_history(symbol, start_time, end_time, frequency, fields, **kw)`
- `fetch_valuation(symbol, start_date, end_date, fields, **kw)`
- `fetch_basic(symbol, start_date, end_date, fields, **kw)`
- `set_token(token)`

### 2.2 类结构
- **类名**: `RQAlphaDataSource`
- **文件**: `src/etf_portfolio/rqalpha_data.py`
- **核心依赖**: `rqalpha.data.data_proxy.DataProxy`, `rqalpha.data.local_data_source.LocalDataSource`

## 3. 实现细节

### 3.1 符号转换 (Symbol Translation)
适配器内部需处理从 GM 格式到 RQAlpha 格式的转换：
- `SHSE.600000` -> `600000.XSHG`
- `SZSE.000001` -> `000001.XSHE`

### 3.2 核心方法实现
- **`__init__(bundle_path)`**:
    - 初始化 `LocalDataSource(bundle_path)`。
    - 初始化 `DataProxy(data_source)`。
- **`fetch_history`**:
    - 调用 `data_proxy.get_history_bars`。
    - 频率支持映射：`1d` -> `1d`, `1m` -> `1m`。
    - 将结果转换回 `pd.DataFrame`，并确保 `datetime` 列为 DatetimeIndex 或标准格式。
- **`fetch_valuation` / `fetch_basic`**:
    - 根据用户要求，直接返回空 `pd.DataFrame()`。
- **`set_token`**:
    - 空实现（RQAlpha 本地数据不需要 token）。

### 3.3 异常处理
- 若 `bundle_path` 不存在，抛出清晰的 `FileNotFoundError`。
- 若 `symbol` 转换失败，记录警告并返回空 DataFrame。

## 4. 验证计划 (Validation)
1. **单元测试**:
    - 测试符号转换逻辑。
    - 测试在模拟/真实 Bundle 下的行情抓取。
    - 测试空数据的边界情况。
2. **集成测试**:
    - 在现有的 ETF 策略流程中，将 `GMDataSource` 替换为 `RQAlphaDataSource`，验证流程是否能够跑通。

## 5. 依赖项
- `rqalpha`: 已在 `pyproject.toml` 中列出。
- `pandas`: 用于数据处理。
