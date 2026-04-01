# 脚本合并逻辑实施计划 (Script Consolidation Plan)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将转换器逻辑与编排逻辑整合为单一入口脚本 `data/scripts/build_qlib_data.py`。

**Architecture:** 
1. 将 `QlibBinConverter` 类完整迁移至 `build_qlib_data.py`。
2. 保持对 `data/scripts/dump_bin.py` 的外部调用。
3. 确保所有动态特征发现逻辑在合并后依然生效。

---

### Task 1: 整合代码至 `build_qlib_data.py`

**Files:**
- Modify: `data/scripts/build_qlib_data.py`
- Read: `data/qlib_converter.py`

**Step 1: 搬迁 Import 和 Class**
将 `data/qlib_converter.py` 中的所有必要导入（Polars, Typing等）和 `QlibBinConverter` 类定义复制到 `build_qlib_data.py` 的顶部。

**Step 2: 修正内部引用**
确保类中的所有方法正常工作，且脚本不再需要 `from data.qlib_converter import ...`。

**Step 3: 提交**
```bash
git commit -m "feat: merge QlibBinConverter class into build_qlib_data.py"
```

---

### Task 4: 最终一致性验证与清理

**Step 1: 全流程测试**
运行合并后的脚本确保在单文件模式下依然能成功完成 4 个 Step。
Run: `uv run python data/scripts/build_qlib_data.py --years 2015`

**Step 2: 物理文件清理**
删除已不再需要的 `data/qlib_converter.py`。

**Step 3: 提交**
```bash
git commit -m "cleanup: remove redundant qlib_converter.py after merge"
```
