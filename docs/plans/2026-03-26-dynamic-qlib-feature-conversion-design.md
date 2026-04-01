# 动态全字段 Qlib 转换设计 (Dynamic Qlib Feature Conversion Design)

**Date:** 2026-03-26
**Topic:** 升级数据转换流水线，支持原始数据的自动数值特征发现。

## 1. 目标 (Goals)
1. 废除硬编码的特征列表，自动识别 Parquet 中所有的数值型指标（Float/Int）。
2. 在 Qlib 二进制格式中保留原始字段缩写名，方便回测与掘金原始数据对照。
3. 建立黑名单机制，排除非特征的元数据（如 `rpt_type`）。

## 2. 核心架构 (Architecture)

### 2.1 特征发现 (Feature Discovery)
在 `QlibBinConverter` 类中引入动态列识别逻辑：
- 使用 Polars 的类型选择器识别 `Int` 和 `Float` 族类型。
- 排除关键字段（`symbol`, `pub_date`, `trade_date`, `bob`, `rpt_date`）及黑名单字段。

### 2.2 全局 Schema 对齐 (Global Schema Alignment)
- 由于不同数据表、不同年份的指标集合可能不同，脚本将扫描所有待处理数据以确定 **Union 字段集**。
- 生成的中间 CSV 将统一包含该字段全集，缺失值用 `null` 填充，以满足 Qlib `dump_bin` 对表头一致性的要求。

### 2.3 动态 Dump 集成 (Dynamic Dump Integration)
- `build_qlib_data.py` 将在运行时读取生成的样本 CSV 表头。
- 自动构建 `--include_fields` 参数传给 `qlib.utils.dump_bin`。

## 3. 设计细节 (Design Details)

### 特征过滤黑名单 (Blacklist)
目前确定的排除列表：
- `rpt_type`: 报告类型代码
- `data_type`: 数据来源标记
- `is_audit`: 审计状态（如果是数值型）

### 转换后的特征命名
直接映射关系：
- Parquet: `mny_cptl` -> Qlib: `mny_cptl`
- Parquet: `ttl_liab` -> Qlib: `ttl_liab`

## 4. 方案风险 (Risks)
- **存储空间增加**: 自动提取所有字段会导致 `qlib_data/features` 下产生的 `.bin` 文件数量剧增。
- **转换耗时**: 由于字段增加，物理落盘（`dump_bin`）的耗时会比例增加。

## 5. 验收标准
- 运行脚本后，`data/qlib_data/features/sh600006/` 目录下应包含 `mny_cptl.day.bin`, `ps_ttm.day.bin` 等新增字段。
- Qlib 能够成功初始化并读取这些新增特征进行表达式计算。
