# PathTargetBuilder 内存优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 Numba JIT 编译优化 PathTargetBuilder，解决内存溢出问题

**Architecture:** 在 `_barrier_scan()` 和 `_compute_market_pnl_matched()` 方法上添加 `@numba.jit` 装饰器，消除循环中的临时数组创建，预计内存峰值从 ~500 MB 降至 ~100 MB

**Tech Stack:** Python, Numba, NumPy, Polars

---

## File Structure

| 文件 | 职责 |
|------|------|
| `path_target.py` | 添加 Numba JIT 函数，修改 `PathTargetBuilder.build()` 调用 JIT 版本 |
| `pyproject.toml` | 添加 `numba` 依赖 |
| `workflow_by_code.py` | 切换回 `Alpha158PathTargetHandler` 验证优化效果 |

---

### Task 1: 添加 Numba 依赖

**Files:**
- Modify: `pyproject.toml:7-24`

- [ ] **Step 1: 添加 numba 到 dependencies**

```toml
[project]
name = "alpha-mq"
version = "0.1.0"
description = "中证1000多因子选股系统"
readme = "README.md"
requires-python = ">=3.10,<3.13"
dependencies = [
    "pyqlib",
    "lightgbm",
    "polars",
    "pandas>=2.0.0,<2.2.0",
    "numpy<2.0.0",
    "scipy",
    "scikit-learn",
    "joblib",
    "protobuf<=3.20.3",
    "pyarrow>=23.0.1",
    "tqdm>=4.67.3",
    "gm>=3.0.0; sys_platform != 'darwin'",
    "fire>=0.7.1",
    "loguru>=0.7.3",
    "plotly>=6.6.0",
    "statsmodels>=0.14.6",
    "numba>=0.58.0",
]
```

- [ ] **Step 2: 安装依赖**

Run: `uv sync` 或 `pip install numba>=0.58.0`
Expected: 成功安装 numba

- [ ] **Step 3: 验证安装**

Run: `/Users/link/Documents/alpha_mq/.venv/bin/python -c "import numba; print(f'Numba version: {numba.__version__}')"`
Expected: 输出 `Numba version: x.xx.x`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add numba dependency for JIT optimization"
```

---

### Task 2: 添加 Numba JIT 函数

**Files:**
- Modify: `path_target.py`

- [ ] **Step 1: 在文件顶部添加 numba 导入**

在 `import numpy as np` 后添加：

```python
import numba
```

- [ ] **Step 2: 在 `_barrier_scan` 方法前添加 Numba 版本函数**

在 `class PathTargetBuilder` 类定义之前，添加以下函数：

```python
# ──────────────────────────────────────────────────────────
# Numba JIT 优化函数
# ──────────────────────────────────────────────────────────

@numba.jit(nopython=True, parallel=True, cache=True)
def _barrier_scan_numba(close_np, vol_np, k_upper, k_lower, max_holding, shift):
    """
    Numba JIT 优化的 Triple Barrier 扫描。

    Parameters
    ----------
    close_np : np.ndarray, shape (T, N)
        收盘价矩阵 (float64)
    vol_np : np.ndarray, shape (T, N)
        波动率矩阵 (float64)
    k_upper, k_lower : float
        止盈/止损系数
    max_holding : int
        最大持有期
    shift : int
        T+1 偏移

    Returns
    -------
    pnl_arr, mae_arr, hold_len_arr : np.ndarray, shape (T, N)
    """
    T, N = close_np.shape
    pnl_arr = np.full((T, N), np.nan)
    mae_arr = np.full((T, N), np.nan)
    hold_len_arr = np.full((T, N), np.nan)

    for t in numba.prange(T - shift - 1):
        entry_idx = t + shift
        end_limit = min(entry_idx + max_holding, T - 1)

        for n in range(N):
            entry_price = close_np[entry_idx, n]
            v = vol_np[t, n]

            if np.isnan(entry_price) or np.isnan(v) or entry_price <= 0 or v <= 0:
                continue

            upper = entry_price * (1 + k_upper * v)
            lower = entry_price * (1 - k_lower * v)

            pnl = np.nan
            mae = 0.0
            hold_len = max_holding
            exited = False

            for h in range(1, min(max_holding + 1, T - entry_idx)):
                price = close_np[entry_idx + h, n]
                if np.isnan(price):
                    continue

                ret = price / entry_price - 1

                if ret < mae:
                    mae = ret

                if price >= upper or price <= lower:
                    pnl = ret
                    hold_len = h
                    exited = True
                    break

            if not exited:
                final_idx = min(entry_idx + max_holding, T - 1)
                final_price = close_np[final_idx, n]
                if not np.isnan(final_price):
                    pnl = final_price / entry_price - 1
                    hold_len = final_idx - entry_idx

            pnl_arr[t, n] = pnl
            mae_arr[t, n] = mae
            hold_len_arr[t, n] = hold_len

    return pnl_arr, mae_arr, hold_len_arr


@numba.jit(nopython=True, cache=True)
def _compute_market_pnl_numba(mkt_price, hold_len_arr, shift):
    """
    Numba JIT 优化的市场收益计算。

    Parameters
    ----------
    mkt_price : np.ndarray, shape (T,)
        市场基准价格序列 (float64)
    hold_len_arr : np.ndarray, shape (T, N)
        持有期矩阵
    shift : int
        T+1 偏移

    Returns
    -------
    mkt_pnl : np.ndarray, shape (T, N)
        市场收益矩阵
    """
    T, N = hold_len_arr.shape
    mkt_pnl = np.full((T, N), np.nan)

    for t in range(T - shift - 1):
        entry = t + shift
        for n in range(N):
            h = hold_len_arr[t, n]
            if not np.isnan(h):
                exit_idx = min(int(entry + h), T - 1)
                mkt_pnl[t, n] = mkt_price[exit_idx] / mkt_price[entry] - 1

    return mkt_pnl
```

- [ ] **Step 3: Commit**

```bash
git add path_target.py
git commit -m "feat: add Numba JIT optimized barrier scan functions"
```

---

### Task 3: 修改 PathTargetBuilder 调用 JIT 版本

**Files:**
- Modify: `path_target.py:150-156` (Step 2 调用)
- Modify: `path_target.py:154-156` (Step 3 调用)

- [ ] **Step 1: 修改 build() 方法中 Step 2 的调用**

将：
```python
# ── Step 2: Triple Barrier 路径扫描 ─────────────────────
pnl_arr, mae_arr, hold_len_arr = self._barrier_scan(close_np, vol_np, cfg)
```

替换为：
```python
# ── Step 2: Triple Barrier 路径扫描 (Numba JIT) ─────────
pnl_arr, mae_arr, hold_len_arr = _barrier_scan_numba(
    close_np.astype(np.float64),
    vol_np.astype(np.float64),
    cfg.k_upper,
    cfg.k_lower,
    cfg.max_holding,
    cfg.shift
)
```

- [ ] **Step 2: 修改 build() 方法中 Step 3 的调用**

将：
```python
# ── Step 3: 市场 pnl（匹配个股持有期）──────────────────
mkt_col = market_close.columns[1]
mkt_np = market_close.select(mkt_col).to_numpy().flatten()
mkt_pnl_arr = self._compute_market_pnl_matched(mkt_np, hold_len_arr, cfg)
```

替换为：
```python
# ── Step 3: 市场 pnl（匹配个股持有期，Numba JIT）───────
mkt_col = market_close.columns[1]
mkt_np = market_close.select(mkt_col).to_numpy().flatten()
mkt_pnl_arr = _compute_market_pnl_numba(
    mkt_np.astype(np.float64),
    hold_len_arr,
    cfg.shift
)
```

- [ ] **Step 3: Commit**

```bash
git add path_target.py
git commit -m "feat: integrate Numba JIT into PathTargetBuilder.build()"
```

---

### Task 4: 切换回 Alpha158PathTargetHandler 验证

**Files:**
- Modify: `workflow_by_code.py:58-77`

- [ ] **Step 1: 修改 handler 配置使用 Alpha158PathTargetHandler**

将：
```python
"handler": {
    # 使用固定 beta 版本，省去 rolling beta 计算（~300-500 MB）
    "class": "Alpha158FixedBetaHandler",
    "module_path": "data.handler_fixed_beta",
    "kwargs": {
        "start_time": "2015-01-05",
        "end_time": "2026-03-26",
        "fit_start_time": "2015-01-05",
        "fit_end_time": "2022-12-31",
        "instruments": CSI1000_MARKET,
        "benchmark": CSI1000_BENCH,
        "beta_alpha": 0.5,  # 市场 neutral 强度
        "filter_pipe": [
            {
                "filter_type": "ExpressionDFilter",
                "rule_expression": "$volume > 0",
                "filter_start_time": None,
                "filter_end_time": None,
                "keep": True,
            }
        ],
    },
},
```

替换为：
```python
"handler": {
    "class": "Alpha158PathTargetHandler",
    "module_path": "data.handler",
    "kwargs": {
        "start_time": "2015-01-05",
        "end_time": "2026-03-26",
        "fit_start_time": "2015-01-05",
        "fit_end_time": "2022-12-31",
        "instruments": CSI1000_MARKET,
        "benchmark": CSI1000_BENCH,
        "filter_pipe": [
            {
                "filter_type": "ExpressionDFilter",
                "rule_expression": "$volume > 0",
                "filter_start_time": None,
                "filter_end_time": None,
                "keep": True,
            }
        ],
    },
},
```

- [ ] **Step 2: Commit**

```bash
git add workflow_by_code.py
git commit -m "feat: switch back to Alpha158PathTargetHandler for testing"
```

---

### Task 5: 运行验证

**Files:**
- Test: `workflow_by_code.py`

- [ ] **Step 1: 运行完整工作流**

Run: `/Users/link/Documents/alpha_mq/.venv/bin/python workflow_by_code.py 2>&1 | grep -E "INFO|ERROR|报告|年化|risk"`
Expected: 成功完成，输出回测结果（年化收益、最大回撤等）

- [ ] **Step 2: 验证内存使用**

Run: `/usr/bin/time -l /Users/link/Documents/alpha_mq/.venv/bin/python workflow_by_code.py 2>&1 | tail -5`
Expected: 最大内存峰值 < 2 GB（优化前会溢出）

- [ ] **Step 3: 检查输出报告**

Run: `ls -la outputs/visualizations/report.html`
Expected: 文件存在且为新生成

---

### Task 6: 清理冗余文件（可选）

**Files:**
- Delete: `data/handler_fixed_beta.py`

- [ ] **Step 1: 删除不再需要的固定 beta handler**

```bash
rm data/handler_fixed_beta.py
git rm data/handler_fixed_beta.py
git commit -m "chore: remove obsolete Alpha158FixedBetaHandler"
```

---

## Self-Review Checklist

- [x] Spec coverage: 所有设计文档中的改动都有对应任务
- [x] Placeholder scan: 无 TBD/TODO
- [x] Type consistency: 函数签名在定义和调用处一致