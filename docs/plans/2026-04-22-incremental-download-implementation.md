# GM 数据增量下载模块实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建 `src/data_download/` 模块，实现增量下载逻辑，Pipeline 和 CLI 统一调用入口。

**Architecture:** 独立模块封装下载逻辑，增量检测（时间覆盖/标的覆盖）作为核心组件，Pipeline download stage 直接调用。

**Tech Stack:** Python, pandas, GM SDK, pytest

---

## Task 1: 创建模块结构和增量检测数据类

**Files:**
- Create: `src/data_download/__init__.py`
- Create: `src/data_download/incremental.py`
- Create: `tests/data_download/test_incremental.py`

**Step 1: 创建测试目录和测试文件**

```python
# tests/data_download/test_incremental.py
"""增量检测逻辑测试"""
import pytest
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass


# 先定义期望的数据类结构（测试将验证这些类存在）
def test_coverage_result_dataclass():
    """测试 CoverageResult 数据类定义"""
    from data_download.incremental import CoverageResult
    
    result = CoverageResult(
        covered=True,
        last_date=datetime(2025, 4, 22),
        gap_start=datetime(2025, 4, 23)
    )
    assert result.covered is True
    assert result.last_date == datetime(2025, 4, 22)


def test_symbol_gap_dataclass():
    """测试 SymbolGap 数据类定义"""
    from data_download.incremental import SymbolGap
    
    gap = SymbolGap(
        existing={"SHSE.600000", "SZSE.000001"},
        missing=["SHSE.600001"]
    )
    assert "SHSE.600000" in gap.existing
    assert "SHSE.600001" in gap.missing
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/data_download/test_incremental.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'data_download'"

**Step 3: 创建模块目录和 __init__.py**

```python
# src/data_download/__init__.py
"""
GM 数据下载模块

提供增量下载能力：
- 时间覆盖检测：只下载缺失时间段
- 标的覆盖检测：只下载缺失标的
"""
from data_download.incremental import CoverageResult, SymbolGap
from data_download.csi1000_downloader import CSI1000Downloader

__all__ = [
    "CoverageResult",
    "SymbolGap",
    "CSI1000Downloader",
]
```

**Step 4: 创建 incremental.py 数据类定义**

```python
# src/data_download/incremental.py
"""
增量检测逻辑

提供时间覆盖和标的覆盖检测函数。
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Set
import pandas as pd


@dataclass
class CoverageResult:
    """时间覆盖检测结果"""
    covered: bool           # 是否已覆盖到结束日期
    last_date: datetime     # 已有数据最新日期
    gap_start: datetime     # 缺口起始日期 (若 covered=False)


@dataclass
class SymbolGap:
    """标的覆盖检测结果"""
    existing: Set[str]      # 已有标的集合
    missing: List[str]      # 缺失标的列表
```

**Step 5: 运行测试验证通过**

Run: `uv run pytest tests/data_download/test_incremental.py -v`
Expected: PASS (2 tests)

**Step 6: 提交**

```bash
git add src/data_download/__init__.py src/data_download/incremental.py tests/data_download/test_incremental.py
git commit -m "$(cat <<'EOF'
feat: create data_download module with CoverageResult and SymbolGap dataclasses

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 实现 check_time_coverage 函数

**Files:**
- Modify: `src/data_download/incremental.py`
- Modify: `tests/data_download/test_incremental.py`

**Step 1: 编写测试用例**

```python
# tests/data_download/test_incremental.py (追加以下测试)

import tempfile
import os


class TestCheckTimeCoverage:
    """时间覆盖检测测试"""
    
    def test_file_not_exists(self):
        """文件不存在时返回 covered=False"""
        from data_download.incremental import check_time_coverage
        
        end_date = datetime(2025, 4, 22)
        result = check_time_coverage(Path("/nonexistent/file.parquet"), end_date)
        
        assert result.covered is False
        assert result.last_date is None
        assert result.gap_start is None
    
    def test_parquet_covered(self):
        """数据已覆盖到结束日期"""
        from data_download.incremental import check_time_coverage
        
        # 创建临时 parquet 文件
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.parquet"
            df = pd.DataFrame({
                "bob": pd.date_range("2025-01-01", "2025-04-22", freq="D")
            })
            df.to_parquet(file_path)
            
            end_date = datetime(2025, 4, 22)
            result = check_time_coverage(file_path, end_date)
            
            assert result.covered is True
            assert result.last_date == datetime(2025, 4, 22)
    
    def test_parquet_has_gap(self):
        """数据有缺口，未覆盖到结束日期"""
        from data_download.incremental import check_time_coverage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.parquet"
            df = pd.DataFrame({
                "bob": pd.date_range("2025-01-01", "2025-03-15", freq="D")
            })
            df.to_parquet(file_path)
            
            end_date = datetime(2025, 4, 22)
            result = check_time_coverage(file_path, end_date)
            
            assert result.covered is False
            assert result.last_date == datetime(2025, 3, 15)
            assert result.gap_start == datetime(2025, 3, 16)  # last_date + 1 day
    
    def test_csv_covered(self):
        """CSV 文件已覆盖"""
        from data_download.incremental import check_time_coverage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.csv"
            df = pd.DataFrame({
                "bob": pd.date_range("2025-01-01", "2025-04-22", freq="D")
            })
            df.to_csv(file_path, index=False)
            
            end_date = datetime(2025, 4, 22)
            result = check_time_coverage(file_path, end_date)
            
            assert result.covered is True
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/data_download/test_incremental.py::TestCheckTimeCoverage -v`
Expected: FAIL with "NameError: name 'check_time_coverage' is not defined"

**Step 3: 实现 check_time_coverage 函数**

```python
# src/data_download/incremental.py (追加以下函数)

def check_time_coverage(file_path: Path, end_date: datetime, time_col: str = "bob") -> CoverageResult:
    """
    检查文件内数据是否已覆盖到请求的结束日期
    
    Args:
        file_path: 数据文件路径 (.parquet 或 .csv)
        end_date: 请求的结束日期
        time_col: 时间列名称 (默认 "bob")
    
    Returns:
        CoverageResult: 覆盖检测结果
    """
    if not file_path.exists():
        return CoverageResult(covered=False, last_date=None, gap_start=None)
    
    try:
        # 根据文件类型读取
        if file_path.suffix == ".parquet":
            df = pd.read_parquet(file_path, columns=[time_col])
        elif file_path.suffix == ".csv":
            df = pd.read_csv(file_path, usecols=[time_col])
        else:
            return CoverageResult(covered=False, last_date=None, gap_start=None)
        
        if df.empty:
            return CoverageResult(covered=False, last_date=None, gap_start=None)
        
        # 解析时间列
        dates = pd.to_datetime(df[time_col])
        last_date = dates.max().to_pydatetime()
        
        # 判断是否覆盖
        if last_date >= end_date:
            return CoverageResult(covered=True, last_date=last_date, gap_start=None)
        else:
            # 缺口起始日期 = last_date + 1 天
            from datetime import timedelta
            gap_start = last_date + timedelta(days=1)
            return CoverageResult(covered=False, last_date=last_date, gap_start=gap_start)
    
    except Exception:
        return CoverageResult(covered=False, last_date=None, gap_start=None)
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/data_download/test_incremental.py::TestCheckTimeCoverage -v`
Expected: PASS (4 tests)

**Step 5: 提交**

```bash
git add src/data_download/incremental.py tests/data_download/test_incremental.py
git commit -m "$(cat <<'EOF'
feat: implement check_time_coverage function

- Detect file existence
- Parse parquet/csv time column
- Return CoverageResult with gap detection

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 实现 check_symbol_coverage 函数

**Files:**
- Modify: `src/data_download/incremental.py`
- Modify: `tests/data_download/test_incremental.py`

**Step 1: 编写测试用例**

```python
# tests/data_download/test_incremental.py (追加以下测试)

class TestCheckSymbolCoverage:
    """标的覆盖检测测试"""
    
    def test_dir_not_exists(self):
        """目录不存在时返回全部缺失"""
        from data_download.incremental import check_symbol_coverage
        
        target_pool = ["SHSE.600000", "SHSE.600001", "SZSE.000001"]
        result = check_symbol_coverage(Path("/nonexistent/dir"), target_pool)
        
        assert result.existing == set()
        assert result.missing == target_pool
    
    def test_partial_missing(self):
        """部分标的缺失"""
        from data_download.incremental import check_symbol_coverage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建部分文件
            Path(tmpdir, "SHSE.600000.parquet").touch()
            Path(tmpdir, "SZSE.000001.parquet").touch()
            
            target_pool = ["SHSE.600000", "SHSE.600001", "SZSE.000001"]
            result = check_symbol_coverage(Path(tmpdir), target_pool)
            
            assert result.existing == {"SHSE.600000", "SZSE.000001"}
            assert result.missing == ["SHSE.600001"]
    
    def test_all_covered(self):
        """全部标的已存在"""
        from data_download.incremental import check_symbol_coverage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for symbol in ["SHSE.600000", "SHSE.600001", "SZSE.000001"]:
                Path(tmpdir, f"{symbol}.parquet").touch()
            
            target_pool = ["SHSE.600000", "SHSE.600001", "SZSE.000001"]
            result = check_symbol_coverage(Path(tmpdir), target_pool)
            
            assert result.existing == set(target_pool)
            assert result.missing == []
    
    def test_csv_format(self):
        """CSV 格式文件检测"""
        from data_download.incremental import check_symbol_coverage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "SHSE.600000.csv").touch()
            
            target_pool = ["SHSE.600000", "SHSE.600001"]
            result = check_symbol_coverage(Path(tmpdir), target_pool, file_format="csv")
            
            assert "SHSE.600000" in result.existing
            assert result.missing == ["SHSE.600001"]
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/data_download/test_incremental.py::TestCheckSymbolCoverage -v`
Expected: FAIL with "NameError: name 'check_symbol_coverage' is not defined"

**Step 3: 实现 check_symbol_coverage 函数**

```python
# src/data_download/incremental.py (追加以下函数)

import glob


def check_symbol_coverage(category_dir: Path, target_pool: List[str], 
                          file_format: str = "parquet") -> SymbolGap:
    """
    检查目录下缺失的标的
    
    Args:
        category_dir: 数据类别目录
        target_pool: 目标标的列表
        file_format: 文件格式 (parquet/csv)
    
    Returns:
        SymbolGap: 标的覆盖检测结果
    """
    if not category_dir.exists():
        return SymbolGap(existing=set(), missing=list(target_pool))
    
    # 扫描已有文件
    pattern = str(category_dir / f"*.{file_format}")
    files = glob.glob(pattern)
    
    # 提取已有标的
    existing = {Path(f).stem for f in files}
    
    # 计算缺失标的
    missing = [s for s in target_pool if s not in existing]
    
    return SymbolGap(existing=existing, missing=missing)
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/data_download/test_incremental.py::TestCheckSymbolCoverage -v`
Expected: PASS (4 tests)

**Step 5: 提交**

```bash
git add src/data_download/incremental.py tests/data_download/test_incremental.py
git commit -m "$(cat <<'EOF'
feat: implement check_symbol_coverage function

- Scan directory for existing files
- Detect missing symbols against target pool
- Support parquet and csv formats

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 实现 gm_api.py RateLimiter

**Files:**
- Create: `src/data_download/gm_api.py`
- Create: `tests/data_download/test_gm_api.py`

**Step 1: 编写测试用例**

```python
# tests/data_download/test_gm_api.py
"""GM API 封装测试"""
import pytest
import time


class TestRateLimiter:
    """流控器测试"""
    
    def test_wait_blocks_when_limit_reached(self):
        """达到限制时阻塞"""
        from data_download.gm_api import RateLimiter
        
        limiter = RateLimiter(max_req=2)  # 每秒最多 2 次
        
        # 前两次应该很快
        start = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed < 0.1
        
        # 第三次应该阻塞
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed >= 0.5  # 至少等待 0.5 秒
    
    def test_request_count_reset_after_window(self):
        """窗口结束后计数重置"""
        from data_download.gm_api import RateLimiter
        
        limiter = RateLimiter(max_req=1)
        
        limiter.wait()
        time.sleep(1.1)  # 等待窗口重置
        
        # 应该不再阻塞
        start = time.time()
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed < 0.1
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/data_download/test_gm_api.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: 实现 RateLimiter**

```python
# src/data_download/gm_api.py
"""
GM API 封装

提供流控、重试装饰器等基础设施。
"""
import time
import logging
from functools import wraps
from typing import Callable, Optional


class RateLimiter:
    """
    简单的速率限制器
    
    基于 sliding window 实现每秒请求限制。
    """
    
    def __init__(self, max_req: int = 950, window_seconds: float = 1.0):
        self.max_req = max_req
        self.window_seconds = window_seconds
        self.requests: list = []  # 记录请求时间戳
    
    def wait(self):
        """等待直到可以发起请求"""
        now = time.time()
        
        # 清理过期记录
        self.requests = [t for t in self.requests if now - t < self.window_seconds]
        
        # 如果达到限制，等待
        if len(self.requests) >= self.max_req:
            wait_time = self.window_seconds - (now - self.requests[0])
            if wait_time > 0:
                time.sleep(wait_time)
                # 清理过期记录
                now = time.time()
                self.requests = [t for t in self.requests if now - t < self.window_seconds]
        
        # 记录本次请求
        self.requests.append(time.time())
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/data_download/test_gm_api.py::TestRateLimiter -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/data_download/gm_api.py tests/data_download/test_gm_api.py
git commit -m "$(cat <<'EOF'
feat: implement RateLimiter for GM API throttling

- Sliding window based rate limiting
- Configurable max requests per window

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 实现 retry 装饰器

**Files:**
- Modify: `src/data_download/gm_api.py`
- Modify: `tests/data_download/test_gm_api.py`

**Step 1: 编写测试用例**

```python
# tests/data_download/test_gm_api.py (追加以下测试)

class TestRetryDecorator:
    """重试装饰器测试"""
    
    def test_success_no_retry(self):
        """成功时不重试"""
        from data_download.gm_api import with_retry
        
        call_count = 0
        
        @with_retry(max_attempts=3, backoff_base=1.0)
        def success_func():
            call_count += 1
            return "ok"
        
        result = success_func()
        assert result == "ok"
        assert call_count == 1
    
    def test_retry_on_exception(self):
        """失败时重试"""
        from data_download.gm_api import with_retry
        
        call_count = 0
        
        @with_retry(max_attempts=3, backoff_base=0.1)
        def failing_func():
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"
        
        result = failing_func()
        assert result == "ok"
        assert call_count == 3
    
    def test_max_attempts_reached(self):
        """达到最大重试次数后抛出异常"""
        from data_download.gm_api import with_retry
        
        call_count = 0
        
        @with_retry(max_attempts=2, backoff_base=0.1)
        def always_fail():
            call_count += 1
            raise ValueError("always fail")
        
        with pytest.raises(ValueError):
            always_fail()
        
        assert call_count == 2
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/data_download/test_gm_api.py::TestRetryDecorator -v`
Expected: FAIL with "NameError"

**Step 3: 实现 with_retry 装饰器**

```python
# src/data_download/gm_api.py (追加以下函数)

def with_retry(max_attempts: int = 3, backoff_base: float = 2.0, 
               exceptions: tuple = (Exception,)):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        backoff_base: 指数退避基数
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff_base ** attempt
                    logging.warning(f"Retry {attempt + 1}/{max_attempts} after {wait_time}s: {e}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/data_download/test_gm_api.py::TestRetryDecorator -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/data_download/gm_api.py tests/data_download/test_gm_api.py
git commit -m "$(cat <<'EOF'
feat: implement with_retry decorator

- Exponential backoff retry
- Configurable max attempts and exception types

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 实现 GMDownloader 基类

**Files:**
- Create: `src/data_download/base.py`
- Create: `tests/data_download/test_base.py`

**Step 1: 编写测试用例**

```python
# tests/data_download/test_base.py
"""GMDownloader 基类测试"""
import pytest
from abc import ABC


class TestGMDownloaderBase:
    """基类结构测试"""
    
    def test_is_abstract(self):
        """验证是抽象基类"""
        from data_download.base import GMDownloader
        
        assert ABC in GMDownloader.__bases__
    
    def test_abstract_methods(self):
        """验证抽象方法定义"""
        from data_download.base import GMDownloader
        
        # 尝试直接实例化应失败
        with pytest.raises(TypeError):
            GMDownloader({})
    
    def test_subclass_must_implement(self):
        """子类必须实现抽象方法"""
        from data_download.base import GMDownloader
        
        class IncompleteDownloader(GMDownloader):
            pass
        
        with pytest.raises(TypeError):
            IncompleteDownloader({})
    
    def test_config_attribute(self):
        """验证 config 属性"""
        from data_download.base import GMDownloader
        
        # 创建完整实现用于测试
        class CompleteDownloader(GMDownloader):
            def get_target_pool(self):
                return []
            
            def get_categories(self):
                return {}
            
            def run(self):
                pass
        
        config = {"test_key": "test_value"}
        downloader = CompleteDownloader(config)
        assert downloader.config == config
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/data_download/test_base.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: 实现 GMDownloader 基类**

```python
# src/data_download/base.py
"""
GM 数据下载器基类

定义下载流程骨架，子类实现特定逻辑。
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List
import logging


class GMDownloader(ABC):
    """
    GM 数据下载器抽象基类
    
    子类需实现:
    - get_target_pool(): 获取目标标的池
    - get_categories(): 获取数据类别配置
    - run(): 执行下载流程
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.limiter = None  # 子类初始化
        
    @abstractmethod
    def get_target_pool(self) -> List[str]:
        """获取目标标的池"""
        pass
    
    @abstractmethod
    def get_categories(self) -> Dict:
        """获取数据类别配置"""
        pass
    
    @abstractmethod
    def run(self):
        """执行完整下载流程"""
        pass
    
    def setup(self):
        """创建输出目录"""
        self.exports_base.mkdir(parents=True, exist_ok=True)
        for category in self.get_categories().keys():
            cat_dir = self.exports_base / category
            cat_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Downloader setup complete: {self.exports_base}")
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/data_download/test_base.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/data_download/base.py tests/data_download/test_base.py
git commit -m "$(cat <<'EOF'
feat: implement GMDownloader abstract base class

- Define download skeleton
- Abstract methods for target pool, categories, run
- Setup directory creation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: 实现 CSI1000Downloader

**Files:**
- Create: `src/data_download/csi1000_downloader.py`
- Modify: `src/data_download/__init__.py`

**Step 1: 实现 CSI1000Downloader 类**

```python
# src/data_download/csi1000_downloader.py
"""
CSI 1000 指数数据下载器

实现中证 1000 成分股数据的增量下载。
"""
import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from tqdm import tqdm

from data_download.base import GMDownloader
from data_download.incremental import check_time_coverage, check_symbol_coverage
from data_download.gm_api import RateLimiter


class CSI1000Downloader(GMDownloader):
    """
    CSI 1000 指数数据下载器
    
    支持增量下载：
    - 时间范围补全：只下载缺失时间段
    - 标的补全：只下载新增成分股
    """
    
    # 数据类别配置
    CATEGORIES = {
        "history_1d": {
            "func_name": "history",
            "format": "parquet",
            "time_col": "bob",
            "fields": None,
            "frequency": "1d",
        },
        "valuation": {
            "func_name": "stk_get_daily_valuation",
            "format": "csv",
            "time_col": "bob",
            "fields": "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper",
        },
        "mktvalue": {
            "func_name": "stk_get_daily_mktvalue",
            "format": "csv",
            "time_col": "bob",
            "fields": "tot_mv,a_mv",
        },
        "basic": {
            "func_name": "stk_get_daily_basic",
            "format": "csv",
            "time_col": "bob",
            "fields": "tclose,turnrate,ttl_shr,circ_shr,is_st,is_suspended",
        },
    }
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.index_code = config.get("index_code", "SHSE.000852")
        self.start_date = config.get("start_date", "2020-01-01")
        self.end_date = config.get("end_date", datetime.now().strftime("%Y-%m-%d"))
        self.token = config.get("token")
        
        # 初始化 GM SDK
        if self.token:
            from gm.api import set_token
            set_token(self.token)
        
        self.limiter = RateLimiter(max_req=950)
        self._constituents = None
    
    def get_target_pool(self) -> List[str]:
        """获取 CSI 1000 成分股"""
        if self._constituents is None:
            from gm.api import stk_get_index_constituents
            logging.info(f"Fetching {self.index_code} constituents...")
            self._constituents = stk_get_index_constituents(index=self.index_code)
        
        if self._constituents is None or self._constituents.empty:
            logging.error("Failed to get constituents")
            return []
        
        symbols = self._constituents['symbol'].tolist()
        # 加入指数自身
        return symbols + [self.index_code]
    
    def get_categories(self) -> Dict:
        """返回数据类别配置"""
        return self.CATEGORIES
    
    def _get_fetch_func(self, func_name: str):
        """获取 GM API 函数"""
        from gm import api as gm_api
        return getattr(gm_api, func_name, None)
    
    def download_category_incremental(self, category: str, cat_config: Dict):
        """执行单个类别的增量下载"""
        target_pool = self.get_target_pool()
        cat_dir = self.exports_base / category
        file_format = cat_config.get("format", "csv")
        time_col = cat_config.get("time_col", "bob")
        
        # 1. 检查标的覆盖
        symbol_gap = check_symbol_coverage(cat_dir, target_pool, file_format)
        
        logging.info(f"{category}: {len(symbol_gap.existing)} existing, {len(symbol_gap.missing)} missing")
        
        # 2. 确定需要下载的标的和时间范围
        end_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
        
        download_tasks = []
        
        # 缺失标的：从配置起点开始下载
        for symbol in symbol_gap.missing:
            download_tasks.append((symbol, self.start_date, self.end_date))
        
        # 已有标的：检查时间缺口
        for symbol in symbol_gap.existing:
            file_path = cat_dir / f"{symbol}.{file_format}"
            coverage = check_time_coverage(file_path, end_dt, time_col)
            
            if not coverage.covered and coverage.gap_start:
                gap_start_str = coverage.gap_start.strftime("%Y-%m-%d")
                download_tasks.append((symbol, gap_start_str, self.end_date))
        
        if not download_tasks:
            logging.info(f"{category}: all data covered, skipping")
            return
        
        # 3. 执行下载
        fetch_func = self._get_fetch_func(cat_config["func_name"])
        if fetch_func is None:
            logging.error(f"GM API function not found: {cat_config['func_name']}")
            return
        
        logging.info(f"{category}: downloading {len(download_tasks)} tasks")
        
        for symbol, start, end in tqdm(download_tasks, desc=f"Downloading {category}"):
            self._download_single(symbol, start, end, cat_dir, cat_config, fetch_func)
    
    def _download_single(self, symbol: str, start_date: str, end_date: str,
                         cat_dir: Path, cat_config: Dict, fetch_func):
        """下载单个标的"""
        file_format = cat_config.get("format", "csv")
        file_path = cat_dir / f"{symbol}.{file_format}"
        
        try:
            self.limiter.wait()
            
            kwargs = {"symbol": symbol, "df": True}
            
            if cat_config["func_name"] == "history":
                kwargs.update({
                    "start_time": f"{start_date} 09:00:00",
                    "end_time": f"{end_date} 16:00:00",
                    "frequency": cat_config.get("frequency", "1d"),
                })
            else:
                kwargs.update({
                    "start_date": start_date,
                    "end_date": end_date,
                })
            
            if cat_config.get("fields"):
                kwargs["fields"] = cat_config["fields"]
            
            df = fetch_func(**kwargs)
            
            if df is None or df.empty:
                return
            
            # 处理时区
            df = self._clean_tz(df)
            
            # 合并已有数据
            if file_path.exists():
                if file_format == "parquet":
                    old_df = pd.read_parquet(file_path)
                else:
                    old_df = pd.read_csv(file_path)
                
                merge_col = cat_config.get("time_col", "bob")
                df = pd.concat([old_df, df]).drop_duplicates(subset=["symbol", merge_col])
            
            # 保存
            if file_format == "parquet":
                df.to_parquet(file_path, index=False)
            else:
                df.to_csv(file_path, index=False)
            
            logging.debug(f"Saved {symbol} to {file_path}")
            
        except Exception as e:
            logging.warning(f"Failed to download {symbol}: {e}")
    
    def _clean_tz(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除时区信息"""
        if df is None:
            return pd.DataFrame()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                if getattr(df[col].dt, 'tz', None) is not None:
                    df[col] = df[col].dt.tz_localize(None)
        return df
    
    def run(self):
        """执行完整下载流程"""
        self.setup()
        
        for category, cat_config in self.get_categories().items():
            logging.info(f"Processing category: {category}")
            self.download_category_incremental(category, cat_config)
        
        logging.info("Download completed")
```

**Step 2: 更新 __init__.py 导出**

```python
# src/data_download/__init__.py (修改)

"""
GM 数据下载模块
"""
from data_download.incremental import CoverageResult, SymbolGap, check_time_coverage, check_symbol_coverage
from data_download.gm_api import RateLimiter, with_retry
from data_download.base import GMDownloader
from data_download.csi1000_downloader import CSI1000Downloader

__all__ = [
    "CoverageResult",
    "SymbolGap",
    "check_time_coverage",
    "check_symbol_coverage",
    "RateLimiter",
    "with_retry",
    "GMDownloader",
    "CSI1000Downloader",
]
```

**Step 3: 提交**

```bash
git add src/data_download/__init__.py src/data_download/csi1000_downloader.py
git commit -m "$(cat <<'EOF'
feat: implement CSI1000Downloader with incremental download

- Time coverage check for gap detection
- Symbol coverage check for missing symbols
- Merge new data with existing files
- Support history_1d, valuation, mktvalue, basic categories

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: 集成到 CSI1000QlibPipeline

**Files:**
- Modify: `src/pipelines/data_ingest/csi1000_pipeline.py`

**Step 1: 实现 download stage**

```python
# src/pipelines/data_ingest/csi1000_pipeline.py (修改 download 方法)

def download(self):
    """
    从 GM API 增量下载数据
    
    调用 CSI1000Downloader 执行增量下载：
    - 检查已有数据的时间覆盖
    - 只下载缺失时间段
    - 检查成分股变动，只下载新增标的
    """
    from data_download import CSI1000Downloader
    
    # 构建下载配置
    download_config = {
        "token": self.config.get("token"),  # 需用户提供 GM token
        "index_code": "SHSE.000852",
        "exports_base": str(self.exports_base),
        "start_date": self.config.get("start_date", "2020-01-01"),
        "end_date": self.config.get("end_date"),
    }
    
    downloader = CSI1000Downloader(download_config)
    downloader.run()
```

**Step 2: 更新配置文件支持 download 参数**

```yaml
# configs/csi1000_qlib.yaml (修改)

pipeline:
  name: csi1000_qlib
  stages:
    - download                  # 新增: 增量下载
    - validate
    - clean
    - ingest

# 下载配置
token: null                     # GM token (建议从环境变量获取)
start_date: "2020-01-01"        # 数据起始日期
end_date: null                  # 数据结束日期 (默认 today)

exports_base: data/exports
qlib_output: data/qlib_output
qlib_bin: data/qlib_bin
```

**Step 3: 提交**

```bash
git add src/pipelines/data_ingest/csi1000_pipeline.py configs/csi1000_qlib.yaml
git commit -m "$(cat <<'EOF'
feat: integrate CSI1000Downloader into Pipeline download stage

- Call CSI1000Downloader.run() for incremental download
- Add token, start_date, end_date config options
- Enable download stage in csi1000_qlib.yaml

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: 更新 CLI 入口

**Files:**
- Modify: `scripts/download_gm.py`

**Step 1: 重构 CLI 使用新模块**

```python
# scripts/download_gm.py (修改为 CLI 入口)

"""
GM 数据下载 CLI 入口

使用 src/data_download 模块执行增量下载。
"""
import argparse
import logging
from datetime import datetime, timedelta

from data_download import CSI1000Downloader


def main():
    parser = argparse.ArgumentParser(description="Download CSI 1000 Data from GM")
    parser.add_argument("--token", type=str, required=True, help="GM SDK Token")
    parser.add_argument("--index", type=str, default="SHSE.000852", help="Index code")
    parser.add_argument("--start", type=str, default="2020-01-01", help="Start date")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="End date")
    parser.add_argument("--exports", type=str, default="data/exports", help="Exports directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime) s - %(levelname) s - %(message) s"
    )
    
    config = {
        "token": args.token,
        "index_code": args.index,
        "exports_base": args.exports,
        "start_date": args.start,
        "end_date": args.end,
    }
    
    downloader = CSI1000Downloader(config)
    downloader.run()


if __name__ == "__main__":
    main()
```

**Step 2: 提交**

```bash
git add scripts/download_gm.py
git commit -m "$(cat <<'EOF'
refactor: simplify download_gm.py to CLI entrypoint

- Use CSI1000Downloader from data_download module
- Remove duplicated download logic
- Keep only argument parsing and module invocation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: 手动验证

**Files:**
- 无新增文件

**Step 1: 运行完整测试**

Run: `uv run pytest tests/data_download/ -v`
Expected: PASS (all tests)

**Step 2: 手动验证小范围下载**

Run: 
```bash
uv run python scripts/download_gm.py \
  --token $GM_TOKEN \
  --start 2025-04-01 \
  --end 2025-04-22 \
  --exports data/exports_test
```

Expected: 增量下载日志显示覆盖情况

**Step 3: 验证 Pipeline 集成**

Run:
```bash
uv run python scripts/run_pipeline.py \
  --config configs/csi1000_qlib.yaml \
  -v
```

Expected: download stage 执行增量下载

**Step 4: 最终提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: complete data_download module implementation

Summary:
- src/data_download/ module with incremental download support
- Time coverage check for gap detection
- Symbol coverage check for missing symbols
- CSI1000Downloader integrated into Pipeline
- CLI entrypoint simplified

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## 完成清单

| Task | 描述 | 状态 |
|------|------|------|
| 1 | 创建模块结构和数据类 | 待实现 |
| 2 | 实现 check_time_coverage | 待实现 |
| 3 | 实现 check_symbol_coverage | 待实现 |
| 4 | 实现 RateLimiter | 待实现 |
| 5 | 实现 with_retry | 待实现 |
| 6 | 实现 GMDownloader 基类 | 待实现 |
| 7 | 实现 CSI1000Downloader | 待实现 |
| 8 | 集成到 Pipeline | 待实现 |
| 9 | 更新 CLI 入口 | 待实现 |
| 10 | 手动验证 | 待实现 |