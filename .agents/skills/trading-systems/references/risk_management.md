# 风险管理 (Risk Management)

> 来源: Trading Systems by Tomasini & Jaekle
> 相关页码: Part I, Part III; Full_doc/full_content.md

## 概述

风险管理是交易系统开发的核心环节。本书强调："如果我们控制风险，利润会自己照顾自己"（If we limit risks, profits will take care of themselves）。

## 核心原则

### 四大风险管理原则 (Part III)

1. **越多越好 (The more the better)**
   - 分散化投资降低风险
   - 组合多个不相关市场

2. **价格序列只是价格序列 (A price series is a price series)**
   - 不要给价格赋予特殊含义
   - 客观对待每个市场

3. **我们知道今天发生了什么，但不知道明天 (We know what happened today but not tomorrow)**
   - 承认未来的不确定性
   - 不要过度拟合历史数据

4. **控制风险，利润自来 (If we limit risks, profits will take care of themselves)**
   - 风险管理优先于利润最大化

## 风险评估指标

### 1. 最大回撤 (Maximum Drawdown)
- **定义**: 权益曲线从峰值到谷底的最大跌幅
- **计算**: 
  ```
  Max Drawdown = (Peak - Trough) / Peak × 100%
  ```
- **重要性**: 衡量最坏情况下的亏损
- **参考**: Part I, Chapter 2

### 2. 最大亏损交易 (Largest Losing Trade)
- **定义**: 单笔交易的最大亏损金额
- **用途**: 评估单笔交易风险
- **参考**: Part III

### 3. 最大亏损连续 (Largest Losing Streak)
- **定义**: 连续亏损交易的最大次数
- **用途**: 心理准备和资金管理
- **参考**: Part III

### 4. RINA Index
- **定义**: 综合考虑净利润、最大回撤和交易时间的指标
- **公式**:
  ```
  RINA Index = (Net Profit × Trade Efficiency) / (Max Drawdown × Time in Market)
  ```
- **用途**: 综合评估系统质量
- **参考**: Part I, Chapter 2

## 止损策略

### 初始止损 (Initial Stop Loss)
- **作用**: 限制单笔交易最大亏损
- **设置方法**:
  - 固定金额止损
  - ATR倍数止损
  - 技术位止损（支撑/阻力）

### ATR止损示例
```
多头止损 = 入场价 - ATR(14) × N
空头止损 = 入场价 + ATR(14) × N
```

### 跟踪止损 (Trailing Stop)
- **作用**: 保护已有利润
- **方法**:
  - 移动均线跟踪
  - 抛物线SAR
  - ATR跟踪

## 组合层面的风险管理

### 相关性管理
- **目标**: 降低组合整体波动
- **方法**: 选择低相关性市场
- **指标**: 权益线相关系数
- **参考**: Part III, "Correlation among equity lines"

### 动态组合调整

#### 权益线交叉法 (Equity Line Crossover)
- **原理**: 使用移动平均线判断系统是否失效
- **方法**: 当权益线跌破N日均线时暂停交易
- **优点**: 自动识别系统失效期
- **参考**: Part III

#### 前向分析激活器 (Walk Forward Analysis Activator)
- **原理**: 基于前向分析结果动态调整组合
- **方法**: 定期重新优化参数并调整仓位
- **参考**: Part III

## 风险度量方法

### 风险调整收益指标

| 指标 | 公式 | 说明 |
|-----|------|------|
| Sharpe Ratio | (Rp - Rf) / σp | 每单位风险超额收益 |
| Sortino Ratio | (Rp - Rf) / σd | 只考虑下行风险 |
| Calmar Ratio | 年化收益 / 最大回撤 | 收益与最大回撤比 |
| RINA Index | 见上文 | 综合评估指标 |

### 破产风险 (Risk of Ruin)
- **定义**: 账户权益跌至无法恢复水平的概率
- **影响因素**:
  - 胜率
  - 盈亏比
  - 每笔风险比例
- **参考**: Monte Carlo分析

## 实际应用

### 组合构建中的风险控制

1. **部分权益投入 (Partial Equity Contribution)**
   - 不投入全部资金
   - 保留现金应对极端情况

2. **总权益投入 (Total Equity Contribution)**
   - 使用全部资金
   - 需要更严格的风控

3. **动态调整**
   - 根据市场状态调整暴露
   - 权益线管理

### 代码示例

```python
class RiskManager:
    def __init__(self, max_drawdown=0.2, max_risk_per_trade=0.02):
        self.max_drawdown = max_drawdown
        self.max_risk_per_trade = max_risk_per_trade
        self.peak_equity = 0
        self.current_drawdown = 0
    
    def update_equity(self, current_equity):
        """更新权益并计算回撤"""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
        
        # 检查是否超过最大回撤
        if self.current_drawdown > self.max_drawdown:
            return False  # 触发风控，停止交易
        return True
    
    def calculate_position_size(self, equity, stop_distance, point_value):
        """计算仓位大小"""
        risk_amount = equity * self.max_risk_per_trade
        risk_per_contract = stop_distance * point_value
        contracts = int(risk_amount / risk_per_contract)
        return max(0, contracts)
    
    def check_equity_line_crossover(self, equity_series, ma_period=20):
        """权益线交叉检查"""
        if len(equity_series) < ma_period:
            return True
        
        ma = equity_series.rolling(ma_period).mean()
        current_equity = equity_series.iloc[-1]
        current_ma = ma.iloc[-1]
        
        # 权益线在均线之上，继续交易
        return current_equity >= current_ma
```

## 关键要点

1. **风险优先**: 永远把风险控制放在第一位
2. **分散化**: 通过多市场组合降低风险
3. **动态监控**: 持续监控权益曲线和回撤
4. **心理准备**: 对最大回撤有心理准备
5. **系统失效**: 有应对系统失效的机制

## 相关文件

- `Full_doc/full_content.md` - 完整原文 (Part I, Part III)
- `examples/python/risk_management.py` - 风险管理实现
- `references/position_sizing.md` - 仓位管理详情

## 延伸阅读

- Van Tharp 的《Trade Your Way to Financial Freedom》
- Ralph Vince 的风险管理系列著作
- Monte Carlo模拟方法
