# 📅 2026-03-25 期货品种代码转换工具 (CTP <-> GM) 设计文档

## 1. 项目背景
在量化交易中，掘金量化 (GM SDK) 使用其特有的 `Exchange.InstrumentID` 格式（如 `SHFE.rb2110`），而 CTP 系统直接使用 `InstrumentID`（如 `rb2110`）。此外，各交易所在字母大小写、年份位数（尤其是郑商所 CZCE）以及期权连字符规则上存在差异。本项目旨在提供一个健壮的 Python 类，实现两者的无缝相互转换。

## 2. 转换规则详解

### 2.1 期货合约 (Futures)

| 交易所 | CTP 格式示例 | 掘金 GM 格式示例 | 规则说明 |
| :--- | :--- | :--- | :--- |
| **中金所 (CFFEX)** | `IF2103` | `CFFEX.IF2103` | 全大写, 2位年+2位月 |
| **上期所 (SHFE)** | `rb1910` | `SHFE.rb1910` | 品种小写, 2位年+2位月 |
| **能源中心 (INE)** | `sc1910` | `INE.sc1910` | 品种小写, 2位年+2位月 |
| **大商所 (DCE)** | `m1911` | `DCE.m1911` | 品种小写, 2位年+2位月 |
| **郑商所 (CZCE)** | `TA910` | `CZCE.TA910` | 全大写, **1位年**+2位月 |
| **广期所 (GFEX)** | `si2405` | `GFEX.si2405` | 品种小写, 2位年+2位月 |

### 2.2 期权合约 (Options)

| 交易所 | CTP 格式示例 | 掘金 GM 格式示例 | 规则 |
| :--- | :--- | :--- | :--- |
| **上期所 (SHFE)** | `cu2110C55000` | `SHFE.cu2110C55000` | 品种小写, YYMM, C/P, 行权价 |
| **大商所 (DCE)** | `m2110-C-5000` | `DCE.m2110-C-5000` | 品种小写, YYMM, **连字符**, C/P, 行权价 |
| **广期所 (GFEX)** | `si2405-C-5000` | `GFEX.si2405-C-5000` | 同大商所 |
| **中金所 (CFFEX)** | `IF2110-C-5000` | `CFFEX.IF2110-C-5000` | 品种大写, YYMM, **连字符**, C/P, 行权价 |
| **郑商所 (CZCE)** | `TA910C5000` | `CZCE.TA910C5000` | 品种大写, YMM, C/P, 行权价 |

### 2.3 主力合约 (Main/Continuous Contracts)
*   **CTP**: 通常无内置主力合约代码，由用户自定义（如 `rb`）。
*   **GM**: 使用交易所+大写品种名（如 `SHFE.RB`）。
*   **用户要求**: 遵循 `品种名.交易所` 规则（如 `RB.SHFE`）。

## 3. 技术设计

### 3.1 核心挑战
*   **CZCE 年份解析**：1 位数字 `9` 对应 2019 还是 2029？
    *   *方案*：引入 `pivot_year` 参数（默认当前年），假设合约在当前年附近（-2y 到 +8y）。
*   **期权正则匹配**：使用专门的正则表达式拆解 CTP 代码中的品种、年月、类型与行权价。

### 3.2 类结构
```python
class FuturesSymbolConverter:
    def __init__(self, main_contract_suffix_exchange=True):
        # 决定转换主力合约时是 SHFE.RB 还是 RB.SHFE
        self.main_as_suffix = main_contract_suffix_exchange
    
    def ctp_to_gm(self, ctp_symbol: str, exchange: str) -> str:
        # CTP 字符串 + 交易所 -> 掘金完整 Symbol
        ...
        
    def gm_to_ctp(self, gm_symbol: str) -> tuple[str, str]:
        # 掘金完整 Symbol -> (CTP 字符串, 交易所)
        ...
```

## 4. 实施计划 (Implementation Plan)
1. 创建工具模块 `data/utils/symbol_utils.py`。
2. 实现转换类及静态映射。
3. 编写回归测试脚本，覆盖上述所有交易所和期权格式。
