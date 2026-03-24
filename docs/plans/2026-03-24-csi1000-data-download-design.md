# 中证1000数据下载设计文档

## 概述

从中证1000指数成分股下载完整的行情和因子数据，并转换为 qlib 二进制格式。

## 目标

- 下载中证1000全部成分股的历史数据
- 包含 OHLCV 行情数据 + 全部可用因子数据
- 时间范围: 2020-01-01 至今
- 存储格式: qlib .bin 格式

## 数据源

使用 gm SDK (掘金量化) 提供的数据接口。

### 可用数据类型

| 数据类型 | API 函数 | 更新频率 | 字段示例 |
|---------|---------|---------|---------|
| 行情数据 | `history()` | 每日 | open, high, low, close, volume, amount |
| 估值数据 | `stk_get_daily_valuation` | 每日 | pe_ttm, pe_lyr, pb, ps_ttm |
| 市值数据 | `stk_get_daily_mktvalue` | 每日 | tot_mv, a_mv |
| 基础数据 | `stk_get_daily_basic` | 每日 | turnrate, ttl_shr, circ_shr |
| 财务指标 | `stk_get_finance_prime` | 季度 | eps_basic, eps_dil, roe |
| 资产负债 | `stk_get_fundamentals_balance` | 季度 | total_ast, total_liab |
| 利润表 | `stk_get_fundamentals_income` | 季度 | revenue, net_profit |
| 现金流 | `stk_get_fundamentals_cashflow` | 季度 | ncf_oper, ncf_inv |

## 架构设计

### 整体流程

```
gm API → Parquet 中间文件 → qlib dump_bin.py → .bin 格式
```

### 两阶段流程

**阶段1: 数据下载**
- 调用 gm SDK API 获取各类数据
- 合并数据为 Parquet 格式
- 每只股票一个 Parquet 文件

**阶段2: 格式转换**
- 使用 qlib `dump_bin.py` 脚本
- 转换为 qlib 二进制格式
- 生成交易日历和股票池文件

### 目录结构

```
data/
├── download.py              # 现有，保留行情下载
├── downloader.py            # 新增，整合所有数据下载
├── qlib_converter.py        # 新增，调用 dump_bin.py
└── scripts/
    └── build_qlib_data.py   # 改造，整合流程

data/parquet/csi1000/        # 中间文件目录
├── 000001.SZSE.parquet
├── 000002.SZSE.parquet
└── ...

data/qlib_data/csi1000/      # 最终 qlib 数据目录
├── calendars/day.txt
├── instruments/csi1000.txt
├── features/
│   └── 000001.SZSE/
│       ├── open.day.bin
│       ├── close.day.bin
│       ├── pe_ttm.day.bin
│       └── ...
└── bench/csi1000_index.bin
```

## 模块设计

### CSI1000Downloader (`data/downloader.py`)

```python
class CSI1000Downloader:
    """中证1000数据下载器"""

    def __init__(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        self.constituents = self._get_constituents()

    def download_all(self, output_dir: Path) -> None:
        """下载所有数据到 Parquet 文件"""

    def download_market_data(self, codes: list[str]) -> pl.DataFrame:
        """下载行情数据"""

    def download_valuation_data(self, codes: list[str]) -> pl.DataFrame:
        """下载估值数据"""

    def download_market_value_data(self, codes: list[str]) -> pl.DataFrame:
        """下载市值数据"""

    def download_basic_data(self, codes: list[str]) -> pl.DataFrame:
        """下载基础数据"""

    def download_financial_data(self, codes: list[str]) -> pl.DataFrame:
        """下载财务数据"""
```

### QlibBinConverter (`data/qlib_converter.py`)

```python
class QlibBinConverter:
    """将 Parquet 数据转换为 qlib .bin 格式"""

    def convert(self, parquet_dir: Path, qlib_dir: Path) -> None:
        """调用 qlib dump_bin.py 转换数据"""
```

### 主脚本改造 (`data/scripts/build_qlib_data.py`)

```python
def build_qlib_dataset(start_date, end_date, output_dir):
    # 阶段1: 下载所有数据到 Parquet
    downloader = CSI1000Downloader(start_date, end_date)
    parquet_dir = output_dir / "parquet"
    downloader.download_all(parquet_dir)

    # 阶段2: 转换为 qlib .bin 格式
    converter = QlibBinConverter()
    qlib_dir = output_dir / "qlib"
    converter.convert(parquet_dir, qlib_dir)
```

## 数据字段规划

### 行情字段 (每日)
- `open`, `high`, `low`, `close`, `volume`, `amount`

### 估值因子 (每日)
- `pe_ttm`, `pe_lyr`, `pe_mrq`, `pb`, `pb_mrq`, `ps_ttm`, `ps_lyr`, `pcf_ttm`

### 市值因子 (每日)
- `tot_mv` (总市值), `a_mv` (流通市值)

### 基础因子 (每日)
- `turnrate` (换手率), `ttl_shr` (总股本), `circ_shr` (流通股本)

### 财务因子 (季度，前值填充)
- 主要指标: `eps_basic`, `eps_dil`, `roe`, `roa`, `net_profit_margin`
- 资产负债: `total_ast`, `total_liab`, `total_eqy`
- 利润表: `revenue`, `net_profit`, `oper_profit`
- 现金流: `ncf_oper`, `ncf_inv`, `ncf_fin`

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 网络错误 | 重试机制，最多3次 |
| 数据缺失 | 用 NaN 填充，记录日志 |
| API 限流 | 自动等待后重试 |
| 成分股变动 | 使用最新成分股列表 |

## 测试策略

- 单元测试：测试每个下载函数
- 集成测试：测试完整下载流程
- 数据验证：检查 Parquet 文件完整性
- 格式验证：验证 qlib 数据可正常加载

## 使用方式

```bash
# 下载并转换数据
python data/scripts/build_qlib_data.py --start-date 2020-01-01 --end-date 2026-03-24

# 仅下载 Parquet
python data/scripts/build_qlib_data.py --download-only

# 仅转换已有 Parquet
python data/scripts/build_qlib_data.py --convert-only --parquet-dir data/parquet/csi1000
```

## 风险与缓解

| 风险 | 缓解措施 |
|-----|---------|
| API 调用限制 | 添加延时，批量请求 |
| 数据量较大 | 分批下载，支持断点续传 |
| 财务数据对齐 | 使用报告期+发布日期对齐 |