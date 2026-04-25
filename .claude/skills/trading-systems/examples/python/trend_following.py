#!/usr/bin/env python3
"""
趋势跟踪策略实现
基于《Trading Systems》书中的双均线交叉逻辑 (LUXOR 系统简化版)

策略逻辑:
- 短期均线上穿长期均线 → 做多
- 短期均线下穿长期均线 → 做空/平仓
- 使用 ATR 动态止损
"""

import pandas as pd
import numpy as np
from typing import Tuple, List, Dict


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    计算平均真实波幅 (ATR)
    
    Args:
        data: 包含 'high', 'low', 'close' 列的 DataFrame
        period: ATR 计算周期
    
    Returns:
        ATR 序列
    """
    high = data['high']
    low = data['low']
    close = data['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(period).mean()
    
    return atr


def generate_ma_crossover_signals(
    data: pd.DataFrame,
    short_ma: int = 5,
    long_ma: int = 20
) -> pd.Series:
    """
    生成均线交叉信号
    
    Args:
        data: 包含 'close' 列的 DataFrame
        short_ma: 短期均线周期
        long_ma: 长期均线周期
    
    Returns:
        信号序列：1=做多，-1=做空，0=观望
    """
    data = data.copy()
    
    # 计算均线
    data['short_ma'] = data['close'].rolling(short_ma).mean()
    data['long_ma'] = data['close'].rolling(long_ma).mean()
    
    # 生成信号
    signals = pd.Series(0, index=data.index)
    
    # 金叉：短期上穿长期
    golden_cross = (data['short_ma'] > data['long_ma']) & \
                   (data['short_ma'].shift(1) <= data['long_ma'].shift(1))
    signals[golden_cross] = 1
    
    # 死叉：短期下穿长期
    death_cross = (data['short_ma'] < data['long_ma']) & \
                  (data['short_ma'].shift(1) >= data['long_ma'].shift(1))
    signals[death_cross] = -1
    
    return signals


class TrendFollowingSystem:
    """
    趋势跟踪交易系统
    
    基于 LUXOR 系统简化版，包含:
    - 双均线交叉入场
    - ATR 动态止损
    - 仓位管理接口
    """
    
    def __init__(
        self,
        short_ma: int = 5,
        long_ma: int = 20,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        initial_capital: float = 100000.0
    ):
        """
        初始化系统
        
        Args:
            short_ma: 短期均线周期
            long_ma: 长期均线周期
            atr_period: ATR 计算周期
            atr_multiplier: ATR 止损倍数
            initial_capital: 初始资金
        """
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.initial_capital = initial_capital
        
        # 交易状态
        self.position = 0  # 1=多头，-1=空头，0=空仓
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.trades = []
        self.equity_curve = []
    
    def run_backtest(self, data: pd.DataFrame) -> Dict:
        """
        执行回测
        
        Args:
            data: 包含 'open', 'high', 'low', 'close' 列的 DataFrame
        
        Returns:
            回测结果字典
        """
        data = data.copy()
        
        # 计算指标
        data['atr'] = calculate_atr(data, self.atr_period)
        data['signal'] = generate_ma_crossover_signals(
            data, self.short_ma, self.long_ma
        )
        
        # 初始化
        cash = self.initial_capital
        self.position = 0
        self.trades = []
        equity_curve = [self.initial_capital]
        
        for i in range(self.long_ma, len(data)):
            current_price = data['close'].iloc[i]
            signal = data['signal'].iloc[i]
            current_atr = data['atr'].iloc[i]
            
            # 开仓逻辑
            if self.position == 0 and signal != 0:
                # 开仓
                self.position = signal
                self.entry_price = current_price
                self.stop_loss = current_price - signal * self.atr_multiplier * current_atr
                
                trade = {
                    'entry_idx': i,
                    'entry_date': data.index[i],
                    'entry_price': self.entry_price,
                    'direction': 'long' if signal == 1 else 'short',
                    'stop_loss': self.stop_loss,
                    'atr': current_atr
                }
                self.trades.append(trade)
            
            # 持仓管理
            elif self.position != 0:
                # 更新跟踪止损
                if self.position == 1:  # 多头
                    new_stop = current_price - self.atr_multiplier * current_atr
                    self.stop_loss = max(self.stop_loss, new_stop)
                    
                    # 检查止损或反转信号
                    if current_price <= self.stop_loss or signal == -1:
                        # 平仓
                        trade = self.trades[-1]
                        trade['exit_idx'] = i
                        trade['exit_date'] = data.index[i]
                        trade['exit_price'] = current_price
                        trade['pnl'] = (current_price - self.entry_price) * 1  # 假设 1 手
                        trade['pnl_pct'] = (current_price - self.entry_price) / self.entry_price
                        
                        self.position = 0
                
                elif self.position == -1:  # 空头
                    new_stop = current_price + self.atr_multiplier * current_atr
                    self.stop_loss = min(self.stop_loss, new_stop)
                    
                    # 检查止损或反转信号
                    if current_price >= self.stop_loss or signal == 1:
                        # 平仓
                        trade = self.trades[-1]
                        trade['exit_idx'] = i
                        trade['exit_date'] = data.index[i]
                        trade['exit_price'] = current_price
                        trade['pnl'] = (self.entry_price - current_price) * 1
                        trade['pnl_pct'] = (self.entry_price - current_price) / self.entry_price
                        
                        self.position = 0
            
            # 计算权益
            if self.position != 0 and len(self.trades) > 0:
                unrealized_pnl = (current_price - self.trades[-1]['entry_price']) * self.position
            else:
                unrealized_pnl = 0
            
            current_equity = self.initial_capital + sum(t.get('pnl', 0) for t in self.trades) + unrealized_pnl
            equity_curve.append(current_equity)
        
        # 计算回测指标
        results = self._calculate_metrics(equity_curve)
        results['trades'] = self.trades
        results['equity_curve'] = equity_curve
        
        return results
    
    def _calculate_metrics(self, equity_curve: List[float]) -> Dict:
        """
        计算回测指标
        
        Args:
            equity_curve: 权益曲线
        
        Returns:
            指标字典
        """
        equity_series = pd.Series(equity_curve)
        
        # 净利润
        net_profit = equity_series.iloc[-1] - equity_series.iloc[0]
        
        # 最大回撤
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # 计算交易指标
        completed_trades = [t for t in self.trades if 'pnl' in t]
        
        if len(completed_trades) > 0:
            wins = [t for t in completed_trades if t['pnl'] > 0]
            losses = [t for t in completed_trades if t['pnl'] <= 0]
            
            gross_profit = sum(t['pnl'] for t in wins)
            gross_loss = abs(sum(t['pnl'] for t in losses))
            
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            win_rate = len(wins) / len(completed_trades)
            avg_trade = net_profit / len(completed_trades)
        else:
            profit_factor = 0
            win_rate = 0
            avg_trade = 0
        
        return {
            'net_profit': net_profit,
            'net_profit_pct': net_profit / self.initial_capital * 100,
            'max_drawdown': max_drawdown * 100,
            'profit_factor': profit_factor,
            'win_rate': win_rate * 100,
            'avg_trade': avg_trade,
            'total_trades': len(completed_trades),
            'final_equity': equity_series.iloc[-1]
        }


def example_usage():
    """使用示例"""
    # 生成示例数据
    np.random.seed(42)
    n_days = 500
    
    # 模拟价格序列（带趋势）
    returns = np.random.normal(0.0005, 0.02, n_days)
    prices = 100 * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, n_days)),
        'high': prices * (1 + np.random.uniform(0, 0.03, n_days)),
        'low': prices * (1 - np.random.uniform(0, 0.03, n_days)),
        'close': prices
    }, index=pd.date_range('2020-01-01', periods=n_days))
    
    # 运行回测
    system = TrendFollowingSystem(
        short_ma=5,
        long_ma=20,
        atr_period=14,
        atr_multiplier=2.0,
        initial_capital=100000
    )
    
    results = system.run_backtest(data)
    
    # 打印结果
    print("=" * 50)
    print("趋势跟踪系统回测结果")
    print("=" * 50)
    print(f"初始资金：${results['final_equity'] - results['net_profit']:,.2f}")
    print(f"最终权益：${results['final_equity']:,.2f}")
    print(f"净利润：${results['net_profit']:,.2f} ({results['net_profit_pct']:.2f}%)")
    print(f"最大回撤：{results['max_drawdown']:.2f}%")
    print(f"盈亏比：{results['profit_factor']:.2f}")
    print(f"胜率：{results['win_rate']:.2f}%")
    print(f"平均交易：${results['avg_trade']:.2f}")
    print(f"总交易次数：{results['total_trades']}")
    print("=" * 50)
    
    return results


if __name__ == '__main__':
    example_usage()
