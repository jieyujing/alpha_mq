# CSI1000 Data Download Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 下载中证1000全部成分股的行情和因子数据，转换为 qlib .bin 格式

**Architecture:** 两阶段流程 - 首先通过 gm SDK 下载各类数据到 Parquet 中间文件，然后使用 qlib dump_bin.py 转换为二进制格式

**Tech Stack:** Python, gm SDK, polars, pyqlib, parquet

---

## Task 1: 创建数据下载器基础结构

**Files:**
- Create: `data/downloader.py`
- Test: `tests/test_downloader.py`

**Step 1: Write the failing test**

```python
# tests/test_downloader.py
"""测试 CSI1000 数据下载器"""
import pytest
from datetime import datetime
from pathlib import Path

from data.downloader import CSI1000Downloader


class TestCSI1000Downloader:
    def test_init_with_valid_dates(self):
        """测试使用有效日期初始化"""
        downloader = CSI1000Downloader(
            start_date="2020-01-01",
            end_date="2024-12-31"
        )
        assert downloader.start_date == "2020-01-01"
        assert downloader.end_date == "2024-12-31"

    def test_init_with_invalid_date_format(self):
        """测试无效日期格式抛出异常"""
        with pytest.raises(ValueError, match="日期格式"):
            CSI1000Downloader(
                start_date="2020/01/01",
                end_date="2024-12-31"
            )

    def test_get_constituents(self):
        """测试获取成分股列表"""
        downloader = CSI1000Downloader(
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        constituents = downloader.constituents
        assert len(constituents) > 0
        assert all("." in code for code in constituents)  # 格式: EXCHANGE.CODE
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'data.downloader'"

**Step 3: Write minimal implementation**

```python
# data/downloader.py
"""
中证1000数据下载器

从 gm SDK 下载行情、估值、市值、财务等数据。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl

try:
    import gm.api as gm
except ImportError:
    gm = None  # type: ignore
else:
    gm.set_token("478dc4635c5198dbfcc962ac3bb209e5327edbff")

logger = logging.getLogger(__name__)

CSI1000_INDEX = "SHSE.000852"


class CSI1000Downloader:
    """
    中证1000数据下载器。

    Parameters
    ----------
    start_date : str
        开始日期，格式 "YYYY-MM-DD"
    end_date : str
        结束日期，格式 "YYYY-MM-DD"
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
    ) -> None:
        self._validate_date(start_date, "start_date")
        self._validate_date(end_date, "end_date")

        self.start_date = start_date
        self.end_date = end_date
        self.constituents = self._get_constituents()

    def _validate_date(self, date_str: str, field: str) -> None:
        """验证日期格式。"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"{field} 日期格式错误: {date_str}，应为 YYYY-MM-DD")

    def _get_constituents(self) -> list[str]:
        """获取中证1000成分股列表。"""
        if gm is None:
            raise ImportError("gm 模块未安装，请执行 pip install gm")

        constituents = gm.stk_get_index_constituents(index=CSI1000_INDEX)
        if constituents is None or len(constituents) == 0:
            raise ValueError(f"无法获取中证1000成分股列表")

        return constituents["symbol"].tolist()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/downloader.py tests/test_downloader.py
git commit -m "feat: add CSI1000Downloader base structure"
```

---

## Task 2: 实现行情数据下载

**Files:**
- Modify: `data/downloader.py`
- Modify: `tests/test_downloader.py`

**Step 1: Write the failing test**

```python
# tests/test_downloader.py - 添加到 TestCSI1000Downloader 类

    def test_download_market_data(self, tmp_path):
        """测试下载行情数据"""
        downloader = CSI1000Downloader(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        # 只测试前3只股票
        codes = downloader.constituents[:3]
        df = downloader.download_market_data(codes)

        assert not df.is_empty()
        assert "date" in df.columns
        assert "code" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_market_data -v`
Expected: FAIL with "AttributeError: 'CSI1000Downloader' object has no attribute 'download_market_data'"

**Step 3: Write minimal implementation**

```python
# data/downloader.py - 添加到 CSI1000Downloader 类

    def download_market_data(
        self,
        codes: Optional[list[str]] = None,
    ) -> pl.DataFrame:
        """
        下载行情数据。

        Parameters
        ----------
        codes : list[str], optional
            股票代码列表，默认为全部成分股

        Returns
        -------
        pl.DataFrame
            包含 date, code, open, high, low, close, volume, amount 列
        """
        if gm is None:
            raise ImportError("gm 模块未安装")

        if codes is None:
            codes = self.constituents

        all_data = []
        total = len(codes)

        for i, code in enumerate(codes):
            try:
                kline = gm.history(
                    symbol=code,
                    frequency="1d",
                    start_time=self.start_date,
                    end_time=self.end_date,
                    fields="eob,open,high,low,close,volume,amount",
                    df=True,
                )
                if kline is not None and len(kline) > 0:
                    kline["code"] = code
                    kline["date"] = pd.to_datetime(kline["eob"]).dt.tz_convert(None).dt.normalize()
                    all_data.append(kline)

                if (i + 1) % 100 == 0:
                    logger.info(f"已下载 {i + 1}/{total} 只股票行情")

            except Exception as e:
                logger.warning(f"下载 {code} 行情失败: {e}")

        if not all_data:
            return pl.DataFrame(schema={
                "date": pl.Date,
                "code": pl.Utf8,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
                "amount": pl.Float64,
            })

        df = pd.concat(all_data, ignore_index=True)
        df = df[["date", "code", "open", "high", "low", "close", "volume", "amount"]]

        return pl.from_pandas(df)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_market_data -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/downloader.py tests/test_downloader.py
git commit -m "feat: add market data download to CSI1000Downloader"
```

---

## Task 3: 实现估值数据下载

**Files:**
- Modify: `data/downloader.py`
- Modify: `tests/test_downloader.py`

**Step 1: Write the failing test**

```python
# tests/test_downloader.py - 添加到 TestCSI1000Downloader 类

    def test_download_valuation_data(self):
        """测试下载估值数据"""
        downloader = CSI1000Downloader(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        codes = downloader.constituents[:3]
        df = downloader.download_valuation_data(codes)

        assert not df.is_empty()
        assert "date" in df.columns
        assert "code" in df.columns
        assert "pe_ttm" in df.columns
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_valuation_data -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# data/downloader.py - 添加到 CSI1000Downloader 类

    VALUATION_FIELDS = [
        "pe_ttm", "pe_lyr", "pe_mrq", "pb", "pb_mrq",
        "ps_ttm", "ps_lyr", "pcf_ttm"
    ]

    def download_valuation_data(
        self,
        codes: Optional[list[str]] = None,
    ) -> pl.DataFrame:
        """
        下载估值数据。

        Parameters
        ----------
        codes : list[str], optional
            股票代码列表

        Returns
        -------
        pl.DataFrame
            包含 PE, PB, PS 等估值指标
        """
        if gm is None:
            raise ImportError("gm 模块未安装")

        if codes is None:
            codes = self.constituents

        all_data = []
        fields = ",".join(self.VALUATION_FIELDS)

        for i, code in enumerate(codes):
            try:
                data = gm.stk_get_daily_valuation(
                    symbol=code,
                    fields=fields,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    df=True,
                )
                if data is not None and len(data) > 0:
                    data["code"] = code
                    all_data.append(data)

            except Exception as e:
                logger.warning(f"下载 {code} 估值数据失败: {e}")

        if not all_data:
            return self._empty_valuation_df()

        df = pd.concat(all_data, ignore_index=True)
        df = df.rename(columns={"trade_date": "date"})
        df["date"] = pd.to_datetime(df["date"])

        return pl.from_pandas(df[["date", "code"] + self.VALUATION_FIELDS])

    def _empty_valuation_df(self) -> pl.DataFrame:
        """返回空的估值 DataFrame。"""
        schema = {"date": pl.Date, "code": pl.Utf8}
        for field in self.VALUATION_FIELDS:
            schema[field] = pl.Float64
        return pl.DataFrame(schema=schema)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_valuation_data -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/downloader.py tests/test_downloader.py
git commit -m "feat: add valuation data download"
```

---

## Task 4: 实现市值和基础数据下载

**Files:**
- Modify: `data/downloader.py`
- Modify: `tests/test_downloader.py`

**Step 1: Write the failing test**

```python
# tests/test_downloader.py - 添加到 TestCSI1000Downloader 类

    def test_download_market_value_data(self):
        """测试下载市值数据"""
        downloader = CSI1000Downloader(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        codes = downloader.constituents[:3]
        df = downloader.download_market_value_data(codes)

        assert not df.is_empty()
        assert "tot_mv" in df.columns

    def test_download_basic_data(self):
        """测试下载基础数据"""
        downloader = CSI1000Downloader(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        codes = downloader.constituents[:3]
        df = downloader.download_basic_data(codes)

        assert not df.is_empty()
        assert "turnrate" in df.columns
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py -k "market_value or basic_data" -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# data/downloader.py - 添加到 CSI1000Downloader 类

    MARKET_VALUE_FIELDS = ["tot_mv", "a_mv"]
    BASIC_FIELDS = ["turnrate", "ttl_shr", "circ_shr"]

    def download_market_value_data(
        self,
        codes: Optional[list[str]] = None,
    ) -> pl.DataFrame:
        """下载市值数据。"""
        if gm is None:
            raise ImportError("gm 模块未安装")

        if codes is None:
            codes = self.constituents

        all_data = []
        fields = ",".join(self.MARKET_VALUE_FIELDS)

        for code in codes:
            try:
                data = gm.stk_get_daily_mktvalue(
                    symbol=code,
                    fields=fields,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    df=True,
                )
                if data is not None and len(data) > 0:
                    data["code"] = code
                    all_data.append(data)
            except Exception as e:
                logger.warning(f"下载 {code} 市值数据失败: {e}")

        if not all_data:
            schema = {"date": pl.Date, "code": pl.Utf8}
            for f in self.MARKET_VALUE_FIELDS:
                schema[f] = pl.Float64
            return pl.DataFrame(schema=schema)

        df = pd.concat(all_data, ignore_index=True)
        df = df.rename(columns={"trade_date": "date"})
        df["date"] = pd.to_datetime(df["date"])
        return pl.from_pandas(df[["date", "code"] + self.MARKET_VALUE_FIELDS])

    def download_basic_data(
        self,
        codes: Optional[list[str]] = None,
    ) -> pl.DataFrame:
        """下载基础数据。"""
        if gm is None:
            raise ImportError("gm 模块未安装")

        if codes is None:
            codes = self.constituents

        all_data = []
        fields = ",".join(self.BASIC_FIELDS)

        for code in codes:
            try:
                data = gm.stk_get_daily_basic(
                    symbol=code,
                    fields=fields,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    df=True,
                )
                if data is not None and len(data) > 0:
                    data["code"] = code
                    all_data.append(data)
            except Exception as e:
                logger.warning(f"下载 {code} 基础数据失败: {e}")

        if not all_data:
            schema = {"date": pl.Date, "code": pl.Utf8}
            for f in self.BASIC_FIELDS:
                schema[f] = pl.Float64
            return pl.DataFrame(schema=schema)

        df = pd.concat(all_data, ignore_index=True)
        df = df.rename(columns={"trade_date": "date"})
        df["date"] = pd.to_datetime(df["date"])
        return pl.from_pandas(df[["date", "code"] + self.BASIC_FIELDS])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py -k "market_value or basic_data" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/downloader.py tests/test_downloader.py
git commit -m "feat: add market value and basic data download"
```

---

## Task 5: 实现财务数据下载

**Files:**
- Modify: `data/downloader.py`
- Modify: `tests/test_downloader.py`

**Step 1: Write the failing test**

```python
# tests/test_downloader.py - 添加到 TestCSI1000Downloader 类

    def test_download_financial_data(self):
        """测试下载财务数据"""
        downloader = CSI1000Downloader(
            start_date="2023-01-01",
            end_date="2024-01-31"
        )
        codes = downloader.constituents[:3]
        df = downloader.download_financial_data(codes)

        assert not df.is_empty()
        assert "date" in df.columns
        # 财务数据可能不是每个交易日都有
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_financial_data -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# data/downloader.py - 添加到 CSI1000Downloader 类

    FINANCE_PRIME_FIELDS = [
        "eps_basic", "eps_dil", "bps", "cfps",
        "roe", "roa", "gross_profit_margin", "net_profit_margin"
    ]

    def download_financial_data(
        self,
        codes: Optional[list[str]] = None,
    ) -> pl.DataFrame:
        """
        下载财务数据。

        使用 Point-in-Time 接口获取历史财务指标。
        """
        if gm is None:
            raise ImportError("gm 模块未安装")

        if codes is None:
            codes = self.constituents

        all_data = []
        fields = ",".join(self.FINANCE_PRIME_FIELDS)

        for code in codes:
            try:
                data = gm.stk_get_finance_prime(
                    symbol=code,
                    fields=fields,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    df=True,
                )
                if data is not None and len(data) > 0:
                    data["code"] = code
                    all_data.append(data)
            except Exception as e:
                logger.warning(f"下载 {code} 财务数据失败: {e}")

        if not all_data:
            schema = {"date": pl.Date, "code": pl.Utf8}
            for f in self.FINANCE_PRIME_FIELDS:
                schema[f] = pl.Float64
            return pl.DataFrame(schema=schema)

        df = pd.concat(all_data, ignore_index=True)
        df = df.rename(columns={"pub_date": "date"})
        df["date"] = pd.to_datetime(df["date"])
        return pl.from_pandas(df[["date", "code"] + self.FINANCE_PRIME_FIELDS])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_financial_data -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/downloader.py tests/test_downloader.py
git commit -m "feat: add financial data download"
```

---

## Task 6: 实现数据合并和保存

**Files:**
- Modify: `data/downloader.py`
- Modify: `tests/test_downloader.py`

**Step 1: Write the failing test**

```python
# tests/test_downloader.py - 添加到 TestCSI1000Downloader 类

    def test_download_all(self, tmp_path):
        """测试下载所有数据并保存"""
        downloader = CSI1000Downloader(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        # 限制股票数量以加快测试
        downloader.constituents = downloader.constituents[:3]

        output_dir = tmp_path / "parquet"
        downloader.download_all(output_dir)

        # 检查生成的文件
        parquet_files = list(output_dir.glob("*.parquet"))
        assert len(parquet_files) == 3  # 每只股票一个文件

        # 检查文件内容
        import polars as pl
        df = pl.read_parquet(parquet_files[0])
        assert "close" in df.columns
        assert "pe_ttm" in df.columns
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_all -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# data/downloader.py - 添加到 CSI1000Downloader 类

    def download_all(self, output_dir: Path | str) -> None:
        """
        下载所有数据并保存为 Parquet 文件。

        Parameters
        ----------
        output_dir : Path | str
            输出目录，每只股票生成一个 Parquet 文件
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始下载 {len(self.constituents)} 只成分股数据...")

        # 下载数据
        market_df = self.download_market_data()
        valuation_df = self.download_valuation_data()
        mv_df = self.download_market_value_data()
        basic_df = self.download_basic_data()
        financial_df = self.download_financial_data()

        # 按股票合并
        codes = self.constituents
        for code in codes:
            try:
                # 筛选该股票的数据
                code_market = market_df.filter(pl.col("code") == code)
                code_val = valuation_df.filter(pl.col("code") == code)
                code_mv = mv_df.filter(pl.col("code") == code)
                code_basic = basic_df.filter(pl.col("code") == code)
                code_fin = financial_df.filter(pl.col("code") == code)

                # 合并所有数据
                merged = code_market
                for df in [code_val, code_mv, code_basic, code_fin]:
                    if not df.is_empty():
                        merged = merged.join(
                            df.drop("code"),
                            on="date",
                            how="left"
                        )

                # 保存
                if not merged.is_empty():
                    # 转换股票代码格式: SHSE.600000 -> 600000.SHSE
                    code_short = code.split(".")[1]
                    exchange = code.split(".")[0]
                    qlib_code = f"{code_short}.{exchange}"

                    output_path = output_dir / f"{qlib_code}.parquet"
                    merged.write_parquet(output_path)

            except Exception as e:
                logger.warning(f"处理 {code} 数据失败: {e}")

        logger.info(f"数据下载完成，保存到 {output_dir}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py::TestCSI1000Downloader::test_download_all -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/downloader.py tests/test_downloader.py
git commit -m "feat: add download_all method to save parquet files"
```

---

## Task 7: 实现 qlib 格式转换器

**Files:**
- Create: `data/qlib_converter.py`
- Test: `tests/test_qlib_converter.py`

**Step 1: Write the failing test**

```python
# tests/test_qlib_converter.py
"""测试 qlib 格式转换器"""
import pytest
from pathlib import Path

from data.qlib_converter import QlibBinConverter


class TestQlibBinConverter:
    def test_init(self):
        """测试初始化"""
        converter = QlibBinConverter()
        assert converter is not None

    def test_convert_parquet_to_bin(self, tmp_path):
        """测试 Parquet 转换为 qlib bin 格式"""
        # 创建测试数据
        import polars as pl
        from datetime import date

        parquet_dir = tmp_path / "parquet"
        parquet_dir.mkdir()

        # 创建测试 Parquet 文件
        df = pl.DataFrame({
            "date": [date(2024, 1, 2), date(2024, 1, 3)],
            "code": ["600000.SHSE", "600000.SHSE"],
            "open": [10.0, 10.5],
            "close": [10.2, 10.6],
            "volume": [1000.0, 1100.0],
        })
        df.write_parquet(parquet_dir / "600000.SHSE.parquet")

        # 转换
        qlib_dir = tmp_path / "qlib"
        converter = QlibBinConverter()
        converter.convert(parquet_dir, qlib_dir)

        # 验证输出
        assert (qlib_dir / "calendars" / "day.txt").exists()
        assert (qlib_dir / "instruments" / "all.txt").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qlib_converter.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# data/qlib_converter.py
"""
qlib 二进制格式转换器

将 Parquet 格式数据转换为 qlib .bin 格式。
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class QlibBinConverter:
    """
    将 Parquet 数据转换为 qlib .bin 格式。

    使用 qlib 官方的 dump_bin.py 脚本。
    """

    def convert(
        self,
        parquet_dir: Path | str,
        qlib_dir: Path | str,
        freq: str = "day",
        max_workers: int = 8,
    ) -> None:
        """
        转换数据。

        Parameters
        ----------
        parquet_dir : Path | str
            Parquet 文件目录
        qlib_dir : Path | str
            qlib 输出目录
        freq : str
            数据频率，默认 "day"
        max_workers : int
            并行工作线程数
        """
        parquet_dir = Path(parquet_dir)
        qlib_dir = Path(qlib_dir)

        if not parquet_dir.exists():
            raise FileNotFoundError(f"Parquet 目录不存在: {parquet_dir}")

        # 获取 qlib dump_bin.py 路径
        dump_bin_path = self._find_dump_bin()

        # 构建命令
        cmd = [
            sys.executable,
            str(dump_bin_path),
            "dump_all",
            "--data_path", str(parquet_dir),
            "--qlib_dir", str(qlib_dir),
            "--freq", freq,
            "--max_workers", str(max_workers),
            "--file_suffix", ".parquet",
            "--date_field_name", "date",
            "--symbol_field_name", "code",
        ]

        logger.info(f"执行转换命令: {' '.join(cmd)}")

        # 执行
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"转换失败: {result.stderr}")
            raise RuntimeError(f"qlib dump_bin.py 转换失败: {result.stderr}")

        logger.info(f"转换完成，输出目录: {qlib_dir}")

    def _find_dump_bin(self) -> Path:
        """查找 qlib dump_bin.py 脚本路径。"""
        # 尝试从 qlib 包中查找
        try:
            import qlib
            qlib_path = Path(qlib.__file__).parent
            dump_bin = qlib_path / "scripts" / "dump_bin.py"
            if dump_bin.exists():
                return dump_bin
        except ImportError:
            pass

        # 回退到系统 PATH
        return Path("dump_bin.py")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_qlib_converter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add data/qlib_converter.py tests/test_qlib_converter.py
git commit -m "feat: add QlibBinConverter for parquet to bin conversion"
```

---

## Task 8: 改造主脚本

**Files:**
- Modify: `data/scripts/build_qlib_data.py`

**Step 1: 改造主脚本**

```python
# data/scripts/build_qlib_data.py
#!/usr/bin/env python
"""
构建 qlib 数据集

从中证1000成分股下载K线数据和因子数据，并转换为qlib格式。
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from data.downloader import CSI1000Downloader
from data.qlib_converter import QlibBinConverter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def build_qlib_dataset(
    start_date: str,
    end_date: str,
    output_dir: str | Path,
    download_only: bool = False,
    convert_only: bool = False,
) -> None:
    """
    构建完整的 qlib 数据集。

    Parameters
    ----------
    start_date : str
        开始日期
    end_date : str
        结束日期
    output_dir : str | Path
        输出目录
    download_only : bool
        仅下载 Parquet，不转换
    convert_only : bool
        仅转换已有 Parquet
    """
    output_dir = Path(output_dir)
    parquet_dir = output_dir / "parquet" / "csi1000"
    qlib_dir = output_dir / "qlib_data" / "csi1000"

    try:
        if not convert_only:
            # 阶段1: 下载数据
            logger.info(f"开始下载数据: {start_date} ~ {end_date}")
            downloader = CSI1000Downloader(start_date, end_date)
            downloader.download_all(parquet_dir)
            logger.info(f"数据下载完成: {parquet_dir}")

        if not download_only:
            # 阶段2: 转换格式
            logger.info("开始转换为 qlib 格式...")
            converter = QlibBinConverter()
            converter.convert(parquet_dir, qlib_dir)
            logger.info(f"qlib 数据集构建完成: {qlib_dir}")

    except Exception as e:
        logger.exception(f"构建数据集失败: {e}")
        raise


def validate_date_format(date_str: str) -> bool:
    """验证日期格式。"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description="构建中证1000 qlib数据集")
    parser.add_argument("--start-date", default="2020-01-01", help="开始日期")
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y-%m-%d"), help="结束日期")
    parser.add_argument("--output-dir", default="data", help="输出目录")
    parser.add_argument("--download-only", action="store_true", help="仅下载 Parquet")
    parser.add_argument("--convert-only", action="store_true", help="仅转换已有 Parquet")

    args = parser.parse_args()

    if not validate_date_format(args.start_date):
        logger.error(f"开始日期格式错误: {args.start_date}")
        sys.exit(1)
    if not validate_date_format(args.end_date):
        logger.error(f"结束日期格式错误: {args.end_date}")
        sys.exit(1)

    build_qlib_dataset(
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=Path(args.output_dir).expanduser(),
        download_only=args.download_only,
        convert_only=args.convert_only,
    )


if __name__ == "__main__":
    main()
```

**Step 2: Run existing tests**

Run: `pytest tests/test_download.py tests/test_converter.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add data/scripts/build_qlib_data.py
git commit -m "refactor: update build_qlib_data.py with new downloader"
```

---

## Task 9: 运行完整测试

**Step 1: 运行所有相关测试**

Run: `pytest tests/test_downloader.py tests/test_qlib_converter.py -v`
Expected: All tests PASS

**Step 2: 运行实际下载测试（小范围）**

Run: `python data/scripts/build_qlib_data.py --start-date 2024-01-01 --end-date 2024-01-31`
Expected: 成功下载并转换数据

**Step 3: 验证 qlib 数据可用**

```python
# 验证脚本
import qlib
from qlib.data import D

qlib.init(provider_uri="data/qlib_data/csi1000")
instruments = D.instruments("csi1000")
print(f"股票数量: {len(instruments)}")
```

---

## Task 10: 更新文档

**Files:**
- Modify: `CLAUDE.md`

**Step 1: 更新 CLAUDE.md**

在 `## 核心模块` 部分添加:

```markdown
### data/ - 数据层
- `download.py`: 从 gm SDK 下载中证1000成分股日K线（保留兼容）
- `downloader.py`: 整合下载器，包含行情、估值、市值、财务数据
- `converter.py`: 转换为 qlib 格式（保留兼容）
- `qlib_converter.py`: 调用 qlib dump_bin.py 转换为二进制格式
- `scripts/build_qlib_data.py`: 数据构建入口脚本
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with new data modules"
```

---

## 完成检查清单

- [ ] CSI1000Downloader 可初始化并获取成分股列表
- [ ] 可下载行情数据 (OHLCV)
- [ ] 可下载估值数据 (PE/PB/PS)
- [ ] 可下载市值数据
- [ ] 可下载基础数据
- [ ] 可下载财务数据
- [ ] 可合并所有数据并保存为 Parquet
- [ ] QlibBinConverter 可将 Parquet 转换为 .bin 格式
- [ ] 主脚本可完整执行下载和转换流程
- [ ] 所有测试通过