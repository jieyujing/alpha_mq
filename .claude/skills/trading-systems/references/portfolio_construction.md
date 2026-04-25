# 组合构建 (Portfolio Construction)

> 来源: Trading Systems by Tomasini & Jaekle
> 相关页码: Part III; Full_doc/full_content.md

## 概述

Part III 是本书最具价值的部分之一，详细介绍了如何将多个交易系统组合成一个稳健的投资组合。作者认为这是"关于如何构建组合的最新的最先进的研究"。

## 核心理念

### 组合构建的四大原则

1. **越多越好 (The more the better)**
   - 分散化是降低风险的最佳方式
   - 组合多个不相关的市场和系统

2. **价格序列只是价格序列 (A price series is a price series)**
   - 客观对待每个市场，不要赋予特殊情感
   - 每个市场都是独立的交易机会

3. **我们知道今天发生了什么，但不知道明天**
   - 承认未来的不确定性
   - 不要基于完美预测构建组合

4. **控制风险，利润自来**
   - 风险管理是组合构建的首要目标
   - 利润是良好风险控制的副产品

## 组合构建步骤

### 第一步：选择市场和系统

#### 市场选择标准
- **流动性**: 足够的交易量
- **数据质量**: 可靠的历史数据
- **可交易性**: 可以通过经纪商交易
- **低相关性**: 与其他组合成员相关性低

#### 系统选择
- 不同类型的策略（趋势、均值回归等）
- 不同时间周期
- 不同参数设置

### 第二步：相关性分析

#### 权益线相关性
- **计算**: 各系统权益线之间的相关系数
- **目标**: 选择低相关或负相关的系统
- **方法**: 
  ```python
  correlation = equity_line_1.corr(equity_line_2)
  ```

#### 相关性矩阵解读
| 相关系数 | 关系 | 组合效果 |
|---------|------|---------|
| 0.0-0.3 | 弱相关 | 良好分散 |
| 0.3-0.7 | 中等相关 | 一般 |
| 0.7-1.0 | 强相关 | 分散效果差 |

### 第三步：资金分配

#### 总权益投入 vs 部分权益投入

**总权益投入 (Total Equity Contribution)**
- 使用全部资金
- 每个系统按信号满仓交易
- 风险较高，收益潜力大

**部分权益投入 (Partial Equity Contribution)**
- 只使用部分资金
- 保留现金储备
- 风险较低，更稳健

### 第四步：动态管理

#### 权益线交叉法 (Equity Line Crossover)

**原理**
- 使用移动平均线监控每个系统的权益曲线
- 当权益线跌破均线时暂停该系统
- 当权益线回升至均线上方时恢复交易

**实现**
```python
def equity_line_crossover(equity_series, ma_period=20):
    ma = equity_series.rolling(ma_period).mean()
    signal = equity_series > ma  # True=交易, False=暂停
    return signal
```

**优点**
- 自动识别系统失效期
- 避免在系统表现不佳时持续亏损
- 保护资金

#### 前向分析激活器 (Walk Forward Analysis Activator)

**原理**
- 定期重新优化系统参数
- 根据最新数据调整组合配置
- 适应市场变化

**步骤**
1. 设定重新优化周期（如每月、每季度）
2. 滚动窗口优化参数
3. 根据优化结果调整仓位
4. 执行下一周期交易

## 组合优化工具

### 软件推荐

| 软件 | 特点 | 网址 |
|-----|------|------|
| Market System Analyzer | 组合分析专业工具 | adaptrade.com |
| MultiCharts | 图表和回测 | tssupport.com |
| Mechanica | 系统化交易 | mechanicasoftware.com |
| RINA Systems | Portfolio Maestro | rinasystems.com |

### 优化目标

#### 1. 风险调整收益最大化
- Sharpe Ratio 最大化
- Sortino Ratio 最大化
- Calmar Ratio 最大化

#### 2. 风险最小化
- 组合波动率最小化
- 最大回撤最小化
- 下行风险最小化

#### 3. 多目标优化
- 收益与风险的平衡
- 考虑交易成本
- 考虑流动性约束

## 实际案例

### 案例1: LUXOR系统组合 (Appendix 3)
- **基础**: 同一系统应用于多个债券市场
- **扩展**: 添加其他市场组（股指、商品等）
- **结果**: 分散化显著改善风险调整收益

### 案例2: 布林带系统组合 (Appendix 1)
- **方法**: 同一参数应用于7个不同市场
- **特点**: 展示策略的跨市场稳健性
- **优势**: 简单策略的组合效果

### 案例3: 三角形系统组合 (Appendix 2)
- **策略**: 形态识别系统
- **应用**: 多个流动性期货市场
- **结果**: 组合分散化降低整体风险

## 组合监控指标

### 1. 组合层面指标

| 指标 | 说明 | 目标 |
|-----|------|------|
| 组合收益 | 总收益 | 稳定增长 |
| 组合波动 | 收益标准差 | 尽可能低 |
| 最大回撤 | 峰值到谷底 | < 20% |
| 夏普比率 | 风险调整收益 | > 1.0 |
|  Beta | 相对市场波动 | 可控范围 |

### 2. 单个系统监控
- 每个系统的权益曲线
- 与预期的偏离
- 相关性变化

### 3. 再平衡信号
- 权重偏离目标
- 相关性显著变化
- 系统失效信号

## 代码示例

### 组合构建框架
```python
class Portfolio:
    def __init__(self, systems, markets):
        self.systems = systems
        self.markets = markets
        self.weights = None
        self.equity_lines = {}
    
    def calculate_correlation_matrix(self):
        """计算系统间相关性矩阵"""
        equity_df = pd.DataFrame(self.equity_lines)
        return equity_df.corr()
    
    def optimize_weights(self, method='risk_parity'):
        """优化组合权重"""
        if method == 'equal':
            self.weights = {s: 1/len(self.systems) for s in self.systems}
        elif method == 'risk_parity':
            self.weights = self._risk_parity_weights()
        elif method == 'mean_variance':
            self.weights = self._mean_variance_optimization()
        return self.weights
    
    def _risk_parity_weights(self):
        """风险平价权重"""
        volatilities = {s: self.equity_lines[s].std() 
                       for s in self.systems}
        inv_vol = {s: 1/v for s, v in volatilities.items()}
        total = sum(inv_vol.values())
        return {s: v/total for s, v in inv_vol.items()}
    
    def apply_equity_line_filter(self, ma_period=20):
        """应用权益线交叉过滤器"""
        active_systems = {}
        for system, equity in self.equity_lines.items():
            ma = equity.rolling(ma_period).mean()
            active = equity.iloc[-1] > ma.iloc[-1]
            active_systems[system] = active
        return active_systems
    
    def calculate_portfolio_equity(self):
        """计算组合总权益曲线"""
        portfolio_equity = pd.Series(0, index=self.equity_lines.index)
        for system, weight in self.weights.items():
            portfolio_equity += self.equity_lines[system] * weight
        return portfolio_equity
    
    def rebalance(self, frequency='monthly'):
        """定期再平衡"""
        # 根据频率触发再平衡
        # 调整权重至目标配置
        pass
```

### 相关性分析
```python
def analyze_correlations(equity_lines):
    """分析系统间相关性"""
    import seaborn as sns
    import matplotlib.pyplot as plt
    
    # 计算相关性矩阵
    corr_matrix = equity_lines.corr()
    
    # 可视化
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', 
                center=0, vmin=-1, vmax=1)
    plt.title('System Correlation Matrix')
    plt.show()
    
    # 找出高相关对
    high_corr = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            if abs(corr_matrix.iloc[i, j]) > 0.7:
                high_corr.append((corr_matrix.columns[i], 
                                corr_matrix.columns[j],
                                corr_matrix.iloc[i, j]))
    
    return corr_matrix, high_corr
```

## 关键要点

1. **分散化是关键**: 多市场、多系统、多策略
2. **低相关性优先**: 选择相关性低的组合成员
3. **动态管理**: 使用权益线交叉等方法动态调整
4. **风险控制**: 组合层面的风险管理优先
5. **定期再平衡**: 保持目标配置，适应市场变化

## 相关文件

- `Full_doc/full_content.md` - 完整原文 (Part III)
- `examples/python/portfolio_construction.py` - 组合构建实现
- `examples/python/equity_line_filter.py` - 权益线过滤器
- `references/risk_management.md` - 风险管理详情
- `references/position_sizing.md` - 仓位管理详情

## 延伸阅读

- Modern Portfolio Theory (MPT)
- Risk Parity 策略
- 因子投资 (Factor Investing)
- 动态资产配置 (Dynamic Asset Allocation)
