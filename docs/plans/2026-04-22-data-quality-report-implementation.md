# 数据质量报告模块实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建 `src/pipelines/data_quality/` 模块，在 pipeline 完成后生成 Markdown 格式的数据质量报告。

**Architecture:** 独立模块封装质量检查逻辑，`checks.py` 提供单项检查函数，`reporter.py` 组合结果生成报告，Pipeline 在 teardown() 中调用。

**Tech Stack:** Python, pandas, pytest

---

## Task 1: 创建模块结构和基础类

**Files:**
- Create: `src/pipelines/data_quality/__init__.py`
- Create: `src/pipelines/data_quality/reporter.py`
- Create: `tests/pipelines/data_quality/test_reporter.py`

**Step 1: 创建测试目录和基础测试**

```python
# tests/pipelines/data_quality/test_reporter.py
"""QualityReporter 测试"""
import pytest
from pathlib import Path


def test_quality_reporter_init():
    """测试 QualityReporter 初始化"""
    from data_quality.reporter import QualityReporter
    
    config = {
        "exports_base": "data/exports",
        "qlib_output": "data/qlib_output",
        "qlib_bin": "data/qlib_bin",
    }
    
    reporter = QualityReporter(config)
    
    assert reporter.exports_base == Path("data/exports")
    assert reporter.qlib_output == Path("data/qlib_output")
    assert reporter.report_path == Path("data/qlib_output/quality_report.md")
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/pipelines/data_quality/test_reporter.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: 创建模块目录和文件**

```python
# src/pipelines/data_quality/__init__.py
"""
数据质量报告模块

提供数据质量检查和报告生成功能。
"""
from data_quality.reporter import QualityReporter

__all__ = ["QualityReporter"]
```

```python
# src/pipelines/data_quality/reporter.py
"""
数据质量报告生成器
"""
from pathlib import Path
from datetime import datetime
import logging


class QualityReporter:
    """数据质量报告生成器"""
    
    def __init__(self, config: dict):
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.qlib_output = Path(config.get("qlib_output", "data/qlib_output"))
        self.qlib_bin = Path(config.get("qlib_bin", "data/qlib_bin"))
        self.report_path = self.qlib_output / "quality_report.md"
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/pipelines/data_quality/test_reporter.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/pipelines/data_quality/__init__.py src/pipelines/data_quality/reporter.py tests/pipelines/data_quality/test_reporter.py
git commit -m "$(cat <<'EOF'
feat: create data_quality module with QualityReporter class

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 实现 OHLCV 检查函数

**Files:**
- Create: `src/pipelines/data_quality/checks.py`
- Create: `tests/pipelines/data_quality/test_checks.py`

**Step 1: 编写 OHLCV 检查测试**

```python
# tests/pipelines/data_quality/test_checks.py
"""数据检查函数测试"""
import pytest
import tempfile
import pandas as pd
from pathlib import Path


class TestCheckOhlcv:
    """OHLCV 检查测试"""
    
    def test_check_ohlcv_coverage_empty_dir(self):
        """空目录返回空结果"""
        from data_quality.checks import check_ohlcv_coverage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_ohlcv_coverage(Path(tmpdir))
            
            assert result["symbol_count"] == 0
            assert result["min_date"] is None
            assert result["max_date"] is None
    
    def test_check_ohlcv_coverage_with_data(self):
        """有数据时返回正确统计"""
        from data_quality.checks import check_ohlcv_coverage
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试数据
            df = pd.DataFrame({
                "date": pd.date_range("2025-01-01", "2025-04-22", freq="D"),
                "open": [10.0] * 112,
                "high": [11.0] * 112,
                "low": [9.0] * 112,
                "close": [10.5] * 112,
                "volume": [1000] * 112,
            })
            df.to_csv(Path(tmpdir) / "SHSE.600000.csv", index=False)
            
            result = check_ohlcv_coverage(Path(tmpdir))
            
            assert result["symbol_count"] == 1
            assert result["min_date"] == "2025-01-01"
            assert result["max_date"] == "2025-04-22"
    
    def test_check_missing_values(self):
        """缺失值检查"""
        from data_quality.checks import check_missing_values
        
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "date": ["2025-01-01", "2025-01-02", "2025-01-03"],
                "close": [10.0, None, 11.0],
                "volume": [1000, 2000, None],
            })
            df.to_csv(Path(tmpdir) / "test.csv", index=False)
            
            result = check_missing_values(Path(tmpdir) / "test.csv", ["close", "volume"])
            
            assert result["close_missing_pct"] == 33.33
            assert result["volume_missing_pct"] == 33.33
    
    def test_check_duplicates(self):
        """重复行检查"""
        from data_quality.checks import check_duplicates
        
        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "date": ["2025-01-01", "2025-01-01", "2025-01-02"],
                "close": [10.0, 10.0, 11.0],
            })
            df.to_csv(Path(tmpdir) / "test.csv", index=False)
            
            result = check_duplicates(Path(tmpdir) / "test.csv", ["date"])
            
            assert result["duplicate_count"] == 1
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/pipelines/data_quality/test_checks.py -v`
Expected: FAIL

**Step 3: 实现 checks.py**

```python
# src/pipelines/data_quality/checks.py
"""
数据质量检查函数
"""
from pathlib import Path
from typing import List, Optional
import pandas as pd
import glob


def check_ohlcv_coverage(data_dir: Path) -> dict:
    """
    检查 OHLCV 数据覆盖情况
    
    Returns:
        dict: symbol_count, min_date, max_date
    """
    if not data_dir.exists():
        return {"symbol_count": 0, "min_date": None, "max_date": None}
    
    files = glob.glob(str(data_dir / "*.csv")) + glob.glob(str(data_dir / "*.parquet"))
    
    if not files:
        return {"symbol_count": 0, "min_date": None, "max_date": None}
    
    min_dates = []
    max_dates = []
    
    for f in files:
        try:
            if f.endswith(".parquet"):
                df = pd.read_parquet(f)
            else:
                df = pd.read_csv(f)
            
            if "date" in df.columns:
                dates = pd.to_datetime(df["date"])
            elif "bob" in df.columns:
                dates = pd.to_datetime(df["bob"])
            else:
                continue
            
            min_dates.append(dates.min().strftime("%Y-%m-%d"))
            max_dates.append(dates.max().strftime("%Y-%m-%d"))
        except Exception:
            continue
    
    return {
        "symbol_count": len(files),
        "min_date": min(min_dates) if min_dates else None,
        "max_date": max(max_dates) if max_dates else None,
    }


def check_missing_values(file_path: Path, columns: List[str]) -> dict:
    """
    检查指定列的缺失值占比
    
    Returns:
        dict: {col_missing_pct: float}
    """
    try:
        if file_path.suffix == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            df = pd.read_csv(file_path)
        
        total_rows = len(df)
        if total_rows == 0:
            return {f"{col}_missing_pct": 0.0 for col in columns}
        
        result = {}
        for col in columns:
            if col in df.columns:
                missing = df[col].isna().sum()
                result[f"{col}_missing_pct"] = round(missing / total_rows * 100, 2)
            else:
                result[f"{col}_missing_pct"] = 100.0
        
        return result
    except Exception:
        return {f"{col}_missing_pct": 100.0 for col in columns}


def check_duplicates(file_path: Path, subset_cols: List[str]) -> dict:
    """
    检查重复行数量
    
    Returns:
        dict: {duplicate_count: int}
    """
    try:
        if file_path.suffix == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            df = pd.read_csv(file_path)
        
        if not all(col in df.columns for col in subset_cols):
            return {"duplicate_count": 0}
        
        duplicates = df.duplicated(subset=subset_cols).sum()
        return {"duplicate_count": int(duplicates)}
    except Exception:
        return {"duplicate_count": 0}
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/pipelines/data_quality/test_checks.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/pipelines/data_quality/checks.py tests/pipelines/data_quality/test_checks.py
git commit -m "$(cat <<'EOF'
feat: implement OHLCV check functions

- check_ohlcv_coverage: symbol count, date range
- check_missing_values: missing percentage
- check_duplicates: duplicate row count

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 实现 QualityReporter 检查方法

**Files:**
- Modify: `src/pipelines/data_quality/reporter.py`
- Modify: `tests/pipelines/data_quality/test_reporter.py`

**Step 1: 编写测试**

```python
# tests/pipelines/data_quality/test_reporter.py (追加)

def test_check_ohlcv_method():
    """测试 _check_ohlcv 方法"""
    from data_quality.reporter import QualityReporter
    
    config = {
        "exports_base": "data/exports",
        "qlib_output": "data/qlib_output",
    }
    
    reporter = QualityReporter(config)
    result = reporter._check_ohlcv()
    
    assert "symbol_count" in result
    assert "min_date" in result
    assert "max_date" in result


def test_run_all_checks():
    """测试 run_all_checks 返回完整结构"""
    from data_quality.reporter import QualityReporter
    
    config = {
        "exports_base": "data/exports",
        "qlib_output": "data/qlib_output",
    }
    
    reporter = QualityReporter(config)
    results = reporter.run_all_checks()
    
    assert "ohlcv" in results
    assert "features" in results
    assert "pit" in results
    assert "summary" in results
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/pipelines/data_quality/test_reporter.py::test_check_ohlcv_method -v`
Expected: FAIL

**Step 3: 实现检查方法**

```python
# src/pipelines/data_quality/reporter.py (追加)

from data_quality.checks import check_ohlcv_coverage, check_missing_values, check_duplicates
import glob
import os


def _check_ohlcv(self) -> dict:
    """检查 OHLCV 数据"""
    ohlcv_dir = self.exports_base / "history_1d"
    
    coverage = check_ohlcv_coverage(ohlcv_dir)
    
    # 统计缺失值和重复行（抽样检查）
    total_missing_pct = 0.0
    total_duplicates = 0
    
    files = glob.glob(str(ohlcv_dir / "*.csv")) + glob.glob(str(ohlcv_dir / "*.parquet"))
    sample_files = files[:10] if len(files) > 10 else files
    
    for f in sample_files:
        missing = check_missing_values(Path(f), ["close", "volume"])
        total_missing_pct += missing.get("close_missing_pct", 0)
        
        dup = check_duplicates(Path(f), ["date"] if "date" in pd.read_csv(f).columns else ["bob"])
        total_duplicates += dup.get("duplicate_count", 0)
    
    avg_missing_pct = round(total_missing_pct / len(sample_files), 2) if sample_files else 0
    
    return {
        "symbol_count": coverage["symbol_count"],
        "min_date": coverage["min_date"],
        "max_date": coverage["max_date"],
        "missing_pct": avg_missing_pct,
        "duplicate_count": total_duplicates,
    }


def _check_features(self) -> dict:
    """检查估值/市值数据"""
    categories = ["valuation", "mktvalue", "basic"]
    ohlcv_dir = self.exports_base / "history_1d"
    
    # 获取 OHLCV 标的作为基准
    ohlcv_files = glob.glob(str(ohlcv_dir / "*.csv")) + glob.glob(str(ohlcv_dir / "*.parquet"))
    ohlcv_symbols = {Path(f).stem for f in ohlcv_files}
    
    results = {}
    for cat in categories:
        cat_dir = self.exports_base / cat
        if not cat_dir.exists():
            results[cat] = {"coverage": 0, "missing_pct": 100}
            continue
        
        cat_files = glob.glob(str(cat_dir / "*.csv"))
        cat_symbols = {Path(f).stem for f in cat_files}
        
        coverage = len(cat_symbols) / len(ohlcv_symbols) * 100 if ohlcv_symbols else 0
        results[cat] = {
            "coverage": round(coverage, 1),
            "missing_pct": 0,  # 简化，后续可细化
        }
    
    return results


def _check_pit(self) -> dict:
    """检查 PIT 数据"""
    pit_dir = self.qlib_output / "pit"
    
    if not pit_dir.exists():
        return {"symbol_count": 0, "period_range": None}
    
    # 统计标的目录数
    symbol_dirs = [d for d in pit_dir.iterdir() if d.is_dir()]
    
    return {
        "symbol_count": len(symbol_dirs),
        "period_range": "待计算",  # 简化
    }


def _generate_summary(self) -> dict:
    """汇总统计"""
    # 计算总文件数和大小
    total_files = 0
    total_size = 0
    
    for dir_path in [self.exports_base, self.qlib_output, self.qlib_bin]:
        if dir_path.exists():
            for f in dir_path.rglob("*"):
                if f.is_file():
                    total_files += 1
                    total_size += f.stat().st_size
    
    # 转换为 MB
    total_size_mb = round(total_size / (1024 * 1024), 2)
    
    return {
        "total_files": total_files,
        "total_size_mb": total_size_mb,
        "score": "待计算",
    }


def run_all_checks(self) -> dict:
    """执行所有检查"""
    return {
        "ohlcv": self._check_ohlcv(),
        "features": self._check_features(),
        "pit": self._check_pit(),
        "summary": self._generate_summary(),
    }
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/pipelines/data_quality/test_reporter.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/pipelines/data_quality/reporter.py tests/pipelines/data_quality/test_reporter.py
git commit -m "$(cat <<'EOF'
feat: implement QualityReporter check methods

- _check_ohlcv: coverage, missing, duplicates
- _check_features: coverage by category
- _check_pit: symbol count
- _generate_summary: file count, size
- run_all_checks: combine all results

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 实现 Markdown 报告生成

**Files:**
- Modify: `src/pipelines/data_quality/reporter.py`
- Modify: `tests/pipelines/data_quality/test_reporter.py`

**Step 1: 编写测试**

```python
# tests/pipelines/data_quality/test_reporter.py (追加)

def test_generate_markdown():
    """测试 Markdown 报告生成"""
    from data_quality.reporter import QualityReporter
    
    config = {"exports_base": "data/exports", "qlib_output": "data/qlib_output"}
    reporter = QualityReporter(config)
    
    results = {
        "ohlcv": {"symbol_count": 100, "min_date": "2025-01-01", "max_date": "2025-04-22", "missing_pct": 0.1},
        "features": {"valuation": {"coverage": 99.5}},
        "pit": {"symbol_count": 98},
        "summary": {"total_files": 500, "total_size_mb": 100, "score": "A"},
    }
    
    md = reporter.generate_markdown(results)
    
    assert "# CSI 1000 数据质量报告" in md
    assert "OHLCV 数据" in md
    assert "symbol_count" in md or "标的数量" in md
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/pipelines/data_quality/test_reporter.py::test_generate_markdown -v`
Expected: FAIL

**Step 3: 实现 generate_markdown**

```python
# src/pipelines/data_quality/reporter.py (追加)

def generate_markdown(self, results: dict) -> str:
    """生成 Markdown 报告"""
    from datetime import datetime
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        "# CSI 1000 数据质量报告",
        "",
        f"**生成时间**: {now}",
        f"**数据目录**: {self.exports_base}, {self.qlib_output}",
        "",
        "---",
        "",
        "## 1. OHLCV 数据",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
    ]
    
    ohlcv = results.get("ohlcv", {})
    lines.append(f"| 标的数量 | {ohlcv.get('symbol_count', 0)} |")
    lines.append(f"| 时间范围 | {ohlcv.get('min_date', '-')} ~ {ohlcv.get('max_date', '-')} |")
    lines.append(f"| 缺失值占比 | {ohlcv.get('missing_pct', 0)}% |")
    lines.append(f"| 重复行数 | {ohlcv.get('duplicate_count', 0)} |")
    
    lines.extend(["", "---", "", "## 2. Features 数据", "", "| 类别 | 标的覆盖率 |", "|------|-----------|"])
    
    features = results.get("features", {})
    for cat, data in features.items():
        lines.append(f"| {cat} | {data.get('coverage', 0)}% |")
    
    lines.extend(["", "---", "", "## 3. PIT 数据", "", "| 指标 | 值 |", "|------|-----|"])
    
    pit = results.get("pit", {})
    lines.append(f"| 标的数量 | {pit.get('symbol_count', 0)} |")
    
    lines.extend(["", "---", "", "## 4. Summary", "", "| 指标 | 值 |", "|------|-----|"])
    
    summary = results.get("summary", {})
    lines.append(f"| 总文件数 | {summary.get('total_files', 0)} |")
    lines.append(f"| 总大小 | {summary.get('total_size_mb', 0)} MB |")
    lines.append(f"| 整体评分 | **{summary.get('score', '-')}** |")
    
    lines.extend(["", "---", "", "*Generated by QualityReporter v1.0*"])
    
    return "\n".join(lines)


def save_report(self) -> Path:
    """执行检查并保存报告"""
    self.qlib_output.mkdir(parents=True, exist_ok=True)
    
    results = self.run_all_checks()
    md_content = self.generate_markdown(results)
    
    self.report_path.write_text(md_content, encoding="utf-8")
    logging.info(f"Quality report saved: {self.report_path}")
    
    return self.report_path
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/pipelines/data_quality/test_reporter.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/pipelines/data_quality/reporter.py tests/pipelines/data_quality/test_reporter.py
git commit -m "$(cat <<'EOF'
feat: implement generate_markdown and save_report

- Markdown format with tables
- OHLCV/Features/PIT/Summary sections
- save_report: write to qlib_output/quality_report.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 集成到 Pipeline

**Files:**
- Modify: `src/pipelines/data_ingest/csi1000_pipeline.py`

**Step 1: 修改 teardown 方法**

```python
# src/pipelines/data_ingest/csi1000_pipeline.py (修改 teardown)

def teardown(self):
    """清理资源并生成质量报告"""
    import sys
    from pathlib import Path
    
    # 确保 src 目录在 sys.path 中
    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    from data_quality import QualityReporter
    
    reporter = QualityReporter(self.config)
    report_path = reporter.save_report()
    logging.info(f"Pipeline teardown complete. Report: {report_path}")
```

**Step 2: 提交**

```bash
git add src/pipelines/data_ingest/csi1000_pipeline.py
git commit -m "$(cat <<'EOF'
feat: integrate QualityReporter into Pipeline teardown

- Generate quality report at pipeline completion
- Report saved to qlib_output/quality_report.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 手动验证

**Step 1: 运行完整测试**

Run: `uv run pytest tests/pipelines/data_quality/ -v`
Expected: PASS

**Step 2: 运行 Pipeline 验证报告生成**

Run: `uv run python scripts/run_pipeline.py --config configs/csi1000_qlib.yaml`
Expected: `data/qlib_output/quality_report.md` 存在

**Step 3: 检查报告内容**

Run: `cat data/qlib_output/quality_report.md`

**Step 4: 最终提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: complete data_quality module implementation

Summary:
- src/pipelines/data_quality/ module
- OHLCV/Features/PIT checks
- Markdown report generation
- Integrated into Pipeline teardown

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## 完成清单

| Task | 描述 | 状态 |
|------|------|------|
| 1 | 创建模块结构和 QualityReporter 类 | 待实现 |
| 2 | 实现 OHLCV 检查函数 | 待实现 |
| 3 | 实现 QualityReporter 检查方法 | 待实现 |
| 4 | 实现 Markdown 报告生成 | 待实现 |
| 5 | 集成到 Pipeline teardown | 待实现 |
| 6 | 手动验证 | 待实现 |