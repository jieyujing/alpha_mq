# 趋势跟踪策略 (Trend Following)

> 来源: Trading Systems by Tomasini & Jaekle
> 相关页码: 参见 Full_doc/full_content.md

## 概述

趋势跟踪是最经典的交易策略之一，其核心思想是"让利润奔跑，截断亏损"。当市场形成明确趋势时，趋势跟踪系统会顺势入场，直到趋势反转信号出现才离场。

## 核心概念

### 通道突破 (Channel Breakout)
- **原理**: 当价格突破过去N天的最高点时做多，突破过去N天的最低点时做空
- **示例代码** (EasyLanguage风格):
  ```
  Buy 2 contracts at the highest high in the last 20 days;
  Sell short 2 contracts at the lowest low in the last 20 days;
  ```
- **参考**: Part I, "An easy example of a trading system"

### 移动平均线交叉 (Moving Average Crossover)
- **原理**: 短期均线上穿长期均线产生买入信号，下穿产生卖出信号
- **应用**: 可用于信号生成，也可用于权益曲线管理
- **参考**: Part III, "A dynamic approach: equity line crossover"

## 关键指标

| 指标 | 说明 | 用途 |
|-----|------|------|
| Highest High | N周期最高价 | 入场信号、止损参考 |
| Lowest Low | N周期最低价 | 入场信号、止损参考 |
| Average True Range | 平均真实波幅 | 动态止损计算 |

## 风险管理

### 初始止损
```
If marketposition = 1 then sell at last close - avgtruerange(14) stop;
If marketposition = -1 then buy to cover at last close + avgtruerange(14) stop;
```

### 跟踪止损
- 基于ATR的动态止损
- 随盈利扩大而调整止损位置

## 实际案例

### LUXOR系统 (Part II核心案例)
- **类型**: 趋势跟踪系统
- **入场逻辑**: 双移动平均线交叉
- **特点**: 完整的开发流程示例，从代码编写到组合优化
- **参考**: Part II 全部章节

### 布林带系统 (Appendix 1)
- **类型**: 均值回归+趋势跟踪混合
- **逻辑**: 价格触及布林带下轨做多，触及上轨做空
- **应用**: 适用于多个市场的组合交易

## 代码示例

### Python伪代码
```python
def trend_following_system(data, short_ma=5, long_ma=20, atr_period=14):
    """
    双均线趋势跟踪系统
    """
    data['short_ma'] = data['close'].rolling(short_ma).mean()
    data['long_ma'] = data['close'].rolling(long_ma).mean()
    data['atr'] = calculate_atr(data, atr_period)
    
    position = 0
    for i in range(long_ma, len(data)):
        if position == 0:
            if data['short_ma'].iloc[i] > data['long_ma'].iloc[i]:
                # 金叉买入
                entry_price = data['close'].iloc[i]
                stop_loss = entry_price - 2 * data['atr'].iloc[i]
                position = 1
        elif position == 1:
            if data['short_ma'].iloc[i] < data['long_ma'].iloc[i]:
                # 死叉卖出
                position = 0
            else:
                # 更新跟踪止损
                new_stop = data['close'].iloc[i] - 2 * data['atr'].iloc[i]
                stop_loss = max(stop_loss, new_stop)
    
    return trades
```

## 相关文件

- `Full_doc/full_content.md` - 完整原文
- `examples/python/trend_following.py` - 完整实现
- `examples/pseudo/luxor_system.txt` - LUXOR系统伪代码

## 延伸阅读

- 海龟交易法则 (Turtle Trading)
- 唐奇安通道 (Donchian Channel)
- 考夫曼自适应移动平均线 (KAMA)
