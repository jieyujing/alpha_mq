# 均值回归策略 (Mean Reversion)

> 来源: Trading Systems by Tomasini & Jaekle
> 相关页码: 参见 Full_doc/full_content.md

## 概述

均值回归策略基于价格会围绕某个均值波动的假设。当价格偏离均值过远时，系统预期价格会回归均值，从而产生交易机会。

## 核心概念

### 布林带系统 (Bollinger Band System)
- **原理**: 价格触及布林带下轨时做多，触及上轨时做空
- **假设**: 价格会在布林带范围内波动，极端偏离后会回归
- **布林带计算**:
  - 中轨 = N周期简单移动平均线
  - 上轨 = 中轨 + K × 标准差
  - 下轨 = 中轨 - K × 标准差
- **参考**: Appendix 1

### 三角形系统 (Triangle System)
- **原理**: 利用价格形态的收敛特征
- **逻辑**: 识别三角形整理形态，在突破时入场
- **参考**: Appendix 2

## 关键指标

| 指标 | 说明 | 用途 |
|-----|------|------|
| Bollinger Bands | 布林带 | 识别超买超卖 |
| Standard Deviation | 标准差 | 衡量价格波动 |
| RSI | 相对强弱指标 | 辅助确认极端状态 |
| Z-Score | Z分数 | 标准化偏离程度 |

## 布林带系统详解 (Appendix 1)

### 入场逻辑
```
当收盘价 < 下轨 → 做多
当收盘价 > 上轨 → 做空
```

### EasyLanguage代码
```easylanguage
inputs: Length(20), NumDevs(2);
variables: UpperBand(0), LowerBand(0);

UpperBand = BollingerBand(Close, Length, NumDevs);
LowerBand = BollingerBand(Close, Length, -NumDevs);

if Close < LowerBand then Buy next bar at market;
if Close > UpperBand then SellShort next bar at market;
```

### 多市场应用
- 使用相同参数应用于7个不同市场
- 展示策略的稳健性
- 适合构建组合策略

## 风险管理

### 均值回归的特殊风险
- **趋势延续风险**: 价格可能继续偏离，而非回归
- **黑天鹅风险**: 极端事件导致均值本身发生变化
- **应对方法**:
  - 设置严格的止损
  - 使用仓位管理控制暴露
  - 结合趋势过滤

## 与趋势跟踪的结合

### 混合策略思路
- 使用趋势指标过滤均值回归信号
- 只在趋势方向上进行均值回归交易
- 示例: 上升趋势中只做布林带下轨反弹

## 代码示例

### Python伪代码
```python
def bollinger_mean_reversion(data, length=20, num_devs=2):
    """
    布林带均值回归系统
    """
    data['ma'] = data['close'].rolling(length).mean()
    data['std'] = data['close'].rolling(length).std()
    data['upper'] = data['ma'] + num_devs * data['std']
    data['lower'] = data['ma'] - num_devs * data['std']
    
    position = 0
    for i in range(length, len(data)):
        if position == 0:
            if data['close'].iloc[i] < data['lower'].iloc[i]:
                # 价格低于下轨，做多
                position = 1
            elif data['close'].iloc[i] > data['upper'].iloc[i]:
                # 价格高于上轨，做空
                position = -1
        elif position == 1:
            if data['close'].iloc[i] > data['ma'].iloc[i]:
                # 回归均值，平仓
                position = 0
        elif position == -1:
            if data['close'].iloc[i] < data['ma'].iloc[i]:
                # 回归均值，平仓
                position = 0
    
    return trades
```

## 实际案例

### 附录1: 布林带系统
- 应用于7个市场的完整回测结果
- 相同参数下的稳健性表现
- 组合构建的优势

### 附录2: 三角形系统
- 形态识别策略
- 不同期货市场的应用
- 组合分散化效果

## 相关文件

- `Full_doc/full_content.md` - 完整原文 (Appendix 1 & 2)
- `examples/python/bollinger_system.py` - 布林带系统实现
- `examples/pseudo/triangle_system.txt` - 三角形系统伪代码

## 注意事项

均值回归策略在震荡市场表现良好，但在强趋势市场中可能产生连续亏损。建议:
1. 与趋势跟踪策略组合使用
2. 严格的风险管理
3. 定期评估策略有效性
