# PathTargetBuilder 内存优化设计

## 问题背景

`PathTargetBuilder` 在处理中证1000数据集（~1000股票 × ~2700交易日）时发生内存溢出。

### 根因分析

`_barrier_scan()` 方法循环 ~2700 次，每次创建 5-6 个临时数组：

```python
for t in range(T - cfg.shift - 1):
    future = close_np[entry_idx + 1:end_idx + 1]  # 切片
    returns = future / entry_price - 1            # 新数组
    hit_up = future >= upper                       # bool 矩阵
    hit_dn = future <= lower                       # bool 矩阵
    mask = np.arange(H)[:, None] <= exit_step      # mask 矩阵
    masked = np.where(mask, returns, np.inf)       # 新数组
```

Python GC 无法及时回收，累积峰值 ~500 MB，加上 Alpha158 特征导致总峰值 ~1 GB+。

## 解决方案：Numba JIT 编译

### 原理

- `@numba.jit(nopython=True)` 将 Python 编译为机器码
- `parallel=True` 自动并行化外层循环
- 所有计算在一个函数内完成，无临时数组创建
- 额外收益：速度提升 2-5x

### 内存优化效果

| 组件 | 优化前 | 优化后 |
|------|--------|--------|
| 循环临时数组 | ~300 MB (累积) | ~0 MB (原地) |
| 结果数组 | ~65 MB | ~65 MB |
| **峰值** | **~500 MB** | **~100 MB** |

## 实现方案

### 文件改动

| 文件 | 改动 |
|------|------|
| `path_target.py` | 添加 Numba JIT 函数，替换原有方法 |
| `requirements.txt` 或 `pyproject.toml` | 添加 `numba >= 0.58.0` |

### 1. 新增 Numba JIT 函数

```python
import numba

@numba.jit(nopython=True, parallel=True, cache=True)
def _barrier_scan_numba(close_np, vol_np, k_upper, k_lower, max_holding, shift):
    """
    Numba JIT 优化的 Triple Barrier 扫描。

    Parameters
    ----------
    close_np : np.ndarray, shape (T, N)
        收盘价矩阵
    vol_np : np.ndarray, shape (T, N)
        波动率矩阵
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

### 2. 修改 PathTargetBuilder 类

```python
class PathTargetBuilder:
    def build(self, ohlc, market_close, beta_df):
        # ... 前置处理不变 ...

        # Step 2: 使用 Numba JIT 版本
        pnl_arr, mae_arr, hold_len_arr = _barrier_scan_numba(
            close_np.astype(np.float64),
            vol_np.astype(np.float64),
            cfg.k_upper,
            cfg.k_lower,
            cfg.max_holding,
            cfg.shift
        )

        # Step 3: 使用 Numba JIT 版本
        mkt_pnl_arr = _compute_market_pnl_numba(
            mkt_np.astype(np.float64),
            hold_len_arr,
            cfg.shift
        )

        # ... 后续处理不变 ...
```

### 3. 依赖添加

```toml
# pyproject.toml
[project]
dependencies = [
    # ... existing deps ...
    "numba >= 0.58.0",
]
```

或

```
# requirements.txt
numba >= 0.58.0
```

## 测试验证

### 单元测试

```python
def test_barrier_scan_numba_equivalence():
    """验证 Numba 版本与原版本结果一致"""
    # 小规模测试数据
    close_np = np.random.randn(100, 10).cumsum(axis=0) + 100
    vol_np = np.abs(np.random.randn(100, 10)) * 0.02 + 0.01

    # 原版本
    pnl_old, mae_old, hold_old = _barrier_scan_original(close_np, vol_np, cfg)

    # Numba 版本
    pnl_new, mae_new, hold_new = _barrier_scan_numba(close_np, vol_np, 2.0, 2.0, 10, 1)

    np.testing.assert_allclose(pnl_old, pnl_new, rtol=1e-10)
    np.testing.assert_allclose(mae_old, mae_new, rtol=1e-10)
    np.testing.assert_allclose(hold_old, hold_new, rtol=1e-10)
```

### 内存测试

```bash
# 运行时监控内存
/usr/bin/time -l python workflow_by_code.py
```

### 预期结果

- 内存峰值 < 500 MB（原 ~1 GB+）
- 运行时间减少 2-5x（首次编译开销除外）

## 回滚方案

如果 Numba 导致问题，可保留原方法作为 fallback：

```python
USE_NUMBA = True

if USE_NUMBA:
    try:
        import numba
        _barrier_scan_impl = _barrier_scan_numba
    except ImportError:
        _barrier_scan_impl = _barrier_scan_original
else:
    _barrier_scan_impl = _barrier_scan_original
```

## 风险评估

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| Numba 编译失败 | 低 | fallback 到原方法 |
| 数值精度差异 | 低 | 单元测试验证 |
| 首次运行慢（编译）| 中 | 缓存编译结果 (`cache=True`) |

## 文件清单

```
path_target.py          # 主要改动
requirements.txt        # 添加 numba
tests/test_path_target.py  # 新增测试（可选）
```