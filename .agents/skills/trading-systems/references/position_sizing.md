# 仓位管理 (Position Sizing / Money Management)

> 来源: Trading Systems by Tomasini & Jaekle
> 相关页码: Part I, Chapter 7; Full_doc/full_content.md

## 概述

仓位管理（Money Management）是交易系统成功的关键因素。本书明确区分了风险管理（Risk Management）和仓位管理（Money Management）:
- **风险管理**: 单笔交易的止损设置
- **仓位管理**: 决定投入多少资金到每笔交易

## 核心概念

### 定义区分

| 概念 | 定义 | 示例 |
|-----|------|------|
| Risk Management (RM) | 单笔交易的风险控制 | 设置止损价位 |
| Money Management (MM) | 资金配置和仓位大小 | 投入多少合约/股数 |

## 仓位管理方法

### 1. 固定合约数 (Fixed Contract)
- **方法**: 每笔交易固定交易1手/1股
- **优点**: 简单，易于回测
- **缺点**: 没有考虑账户权益变化
- **用途**: 作为基准参考

### 2. 最大回撤法 (Maximum Drawdown MM)
- **原理**: 根据历史最大回撤调整仓位
- **公式**: 仓位 = f(当前权益, 最大回撤)
- **目的**: 防止账户权益大幅回撤

### 3. 固定分数法 (Fixed Fractional MM)
- **原理**: 每笔交易风险固定比例的资金
- **公式**: 
  ```
  合约数 = (账户权益 × 风险比例) / (每点价值 × 止损距离)
  ```
- **示例**: 风险2%账户权益，止损5个点
- **优点**: 风险与账户规模成比例
- **参考**: Part I, Chapter 7

### 4. 固定比率法 (Fixed Ratio MM)
- **原理**: 根据盈利情况逐步增加仓位
- **公式**: 
  ```
  每增加1单位合约需要盈利 = Delta × 当前合约数
  ```
- **特点**: 盈利越多，加仓越难
- **优点**: 保护前期利润
- **参考**: Part I, Chapter 7

## 仓位管理方案对比

| 方法 | 风险特征 | 盈利潜力 | 适用场景 |
|-----|---------|---------|---------|
| 固定合约 | 固定绝对风险 | 线性增长 | 初学者、测试阶段 |
| 最大回撤 | 动态调整 | 保守 | 大资金、稳健型 |
| 固定分数 | 固定相对风险 | 指数增长可能 | 大多数交易系统 |
| 固定比率 | 递增难度 | 稳健增长 | 趋势跟踪系统 |

## 关键公式

### 固定分数法计算
```python
def fixed_fractional_sizing(equity, risk_percent, stop_points, point_value):
    """
    固定分数仓位计算
    
    Args:
        equity: 当前账户权益
        risk_percent: 每笔交易风险比例 (如 0.02 表示2%)
        stop_points: 止损距离 (点数)
        point_value: 每点价值
    
    Returns:
        contracts: 建议交易合约数
    """
    risk_amount = equity * risk_percent
    risk_per_contract = stop_points * point_value
    contracts = int(risk_amount / risk_per_contract)
    return max(1, contracts)  # 至少交易1手
```

### 固定比率法计算
```python
def fixed_ratio_sizing(current_contracts, profit, delta):
    """
    固定比率仓位计算
    
    Args:
        current_contracts: 当前持仓合约数
        profit: 当前累计盈利
        delta: 固定比率参数
    
    Returns:
        new_contracts: 新的建议合约数
    """
    threshold = delta * current_contracts
    additional = int(profit / threshold)
    return current_contracts + additional
```

## Monte Carlo分析

### 目的
- 评估不同仓位管理方案的风险
- 模拟多种可能的市场路径
- 确定最优风险参数

### 方法
1. 从历史交易中随机抽样构建新权益曲线
2. 重复1000次以上
3. 分析最大回撤、破产概率等指标
- **参考**: Part I, Chapter 7

## 实际应用 (LUXOR系统案例)

### 测试步骤
1. 基准测试: 固定1手交易
2. 应用最大回撤MM
3. 应用固定分数MM (2%风险)
4. 应用固定比率MM (Delta=1000)
5. Monte Carlo验证

### 结果对比
- 不同MM方案下的权益曲线
- 最大回撤变化
- 收益风险比改善

## 代码示例

### Python实现
```python
class PositionSizing:
    def __init__(self, method='fixed_fractional', **params):
        self.method = method
        self.params = params
    
    def calculate(self, equity, **kwargs):
        if self.method == 'fixed':
            return 1
        elif self.method == 'fixed_fractional':
            return self._fixed_fractional(equity, **kwargs)
        elif self.method == 'fixed_ratio':
            return self._fixed_ratio(**kwargs)
        elif self.method == 'max_drawdown':
            return self._max_drawdown(equity, **kwargs)
    
    def _fixed_fractional(self, equity, risk_percent, stop_points, point_value):
        risk_amount = equity * risk_percent
        risk_per_contract = stop_points * point_value
        return max(1, int(risk_amount / risk_per_contract))
    
    def _fixed_ratio(self, current_contracts, profit, delta):
        threshold = delta * current_contracts
        additional = int(profit / threshold)
        return current_contracts + additional
    
    def _max_drawdown(self, equity, max_dd_percent, current_dd):
        # 根据回撤调整仓位
        if current_dd > max_dd_percent:
            return max(1, int(self.last_contracts * 0.5))
        return self.last_contracts
```

## 关键要点

1. **仓位管理 > 入场信号**: 好的仓位管理比完美的入场更重要
2. **风险控制优先**: 永远不要让单笔交易风险超过账户的2-3%
3. **复利效应**: 固定分数法可实现复利增长
4. **心理承受**: 选择的MM方案必须能承受心理考验

## 相关文件

- `Full_doc/full_content.md` - 完整原文 (Chapter 7)
- `examples/python/position_sizing.py` - 仓位管理实现
- `examples/python/monte_carlo.py` - Monte Carlo分析

## 延伸阅读

- Kelly Criterion (凯利公式)
- Optimal f (最优f)
- Ralph Vince 的 Portfolio Management Formulas
