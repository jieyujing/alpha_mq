#!/usr/bin/env python3
"""
仓位管理模块实现
基于《Trading Systems》Part I, Chapter 7

实现方法:
1. 固定合约数 (Fixed Contract)
2. 最大回撤法 (Maximum Drawdown MM)
3. 固定分数法 (Fixed Fractional MM)
4. 固定比率法 (Fixed Ratio MM)
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
from abc import ABC, abstractmethod


class PositionSizer(ABC):
    """仓位管理器基类"""
    
    @abstractmethod
    def calculate_position(
        self,
        equity: float,
        stop_distance: float,
        point_value: float,
        **kwargs
    ) -> int:
        """
        计算仓位大小
        
        Args:
            equity: 当前账户权益
            stop_distance: 止损距离 (点数)
            point_value: 每点价值
            **kwargs: 其他参数
        
        Returns:
            建议交易合约数
        """
        pass


class FixedPositionSizer(PositionSizer):
    """固定合约数仓位管理"""
    
    def __init__(self, contracts: int = 1):
        """
        Args:
            contracts: 固定交易合约数
        """
        self.contracts = contracts
    
    def calculate_position(self, equity: float, stop_distance: float, point_value: float, **kwargs) -> int:
        return self.contracts


class FixedFractionalPositionSizer(PositionSizer):
    """
    固定分数仓位管理
    
    每笔交易风险固定比例的账户权益
    公式：合约数 = (账户权益 × 风险比例) / (每点价值 × 止损距离)
    """
    
    def __init__(self, risk_percent: float = 0.02):
        """
        Args:
            risk_percent: 每笔交易风险比例 (如 0.02 表示 2%)
        """
        self.risk_percent = risk_percent
    
    def calculate_position(self, equity: float, stop_distance: float, point_value: float, **kwargs) -> int:
        """
        计算固定分数仓位
        
        Args:
            equity: 当前账户权益
            stop_distance: 止损距离 (点数)
            point_value: 每点价值
        
        Returns:
            建议交易合约数
        """
        risk_amount = equity * self.risk_percent
        risk_per_contract = stop_distance * point_value
        
        if risk_per_contract <= 0:
            return 0
        
        contracts = int(risk_amount / risk_per_contract)
        return max(1, contracts)  # 至少交易 1 手


class FixedRatioPositionSizer(PositionSizer):
    """
    固定比率仓位管理
    
    根据累计盈利逐步增加仓位
    公式：每增加 1 单位合约需要盈利 = Delta × 当前合约数
    
    参考：Ryan Jones - Trading Risk Advantage
    """
    
    def __init__(
        self,
        delta: float = 1000.0,
        starting_contracts: int = 1,
        starting_equity: float = 10000.0
    ):
        """
        Args:
            delta: 固定比率参数 (每增加 1 手需要的盈利)
            starting_contracts: 起始合约数
            starting_equity: 起始权益门槛
        """
        self.delta = delta
        self.starting_contracts = starting_contracts
        self.starting_equity = starting_equity
    
    def calculate_position(
        self,
        equity: float,
        stop_distance: float,
        point_value: float,
        current_contracts: Optional[int] = None,
        total_profit: Optional[float] = None,
        **kwargs
    ) -> int:
        """
        计算固定比率仓位
        
        Args:
            equity: 当前账户权益
            stop_distance: 止损距离
            point_value: 每点价值
            current_contracts: 当前持仓合约数 (可选)
            total_profit: 累计盈利 (可选)
        
        Returns:
            建议交易合约数
        """
        if current_contracts is None:
            current_contracts = self.starting_contracts
        
        if total_profit is None:
            total_profit = equity - self.starting_equity
        
        if total_profit <= 0:
            return self.starting_contracts
        
        # 计算可以增加的合约数
        # 公式：additional = floor(profit / (delta * current_contracts))
        additional = 0
        test_contracts = current_contracts
        
        while True:
            threshold = self.delta * test_contracts
            if total_profit >= threshold:
                additional += 1
                test_contracts += 1
            else:
                break
        
        return current_contracts + additional


class MaxDrawdownPositionSizer(PositionSizer):
    """
    最大回撤仓位管理
    
    根据历史最大回撤动态调整仓位
    当回撤超过阈值时减少仓位
    """
    
    def __init__(
        self,
        max_drawdown_percent: float = 0.20,
        base_contracts: int = 1,
        reduction_factor: float = 0.5
    ):
        """
        Args:
            max_drawdown_percent: 最大回撤阈值
            base_contracts: 基础合约数
            reduction_factor: 触发回撤时的仓位减少比例
        """
        self.max_drawdown_percent = max_drawdown_percent
        self.base_contracts = base_contracts
        self.reduction_factor = reduction_factor
        self.peak_equity = 0
        self.last_contracts = base_contracts
    
    def update_equity(self, equity: float) -> float:
        """
        更新权益并返回当前回撤
        
        Args:
            equity: 当前权益
        
        Returns:
            当前回撤比例
        """
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        if self.peak_equity == 0:
            return 0
        
        current_drawdown = (self.peak_equity - equity) / self.peak_equity
        return current_drawdown
    
    def calculate_position(
        self,
        equity: float,
        stop_distance: float,
        point_value: float,
        **kwargs
    ) -> int:
        """
        计算最大回撤仓位
        
        Args:
            equity: 当前账户权益
            stop_distance: 止损距离
            point_value: 每点价值
        
        Returns:
            建议交易合约数
        """
        current_drawdown = self.update_equity(equity)
        
        if current_drawdown > self.max_drawdown_percent:
            # 超过最大回撤，减少仓位
            contracts = max(1, int(self.base_contracts * self.reduction_factor))
        else:
            contracts = self.base_contracts
        
        self.last_contracts = contracts
        return contracts


class MonteCarloAnalyzer:
    """
    Monte Carlo 分析器
    
    用于评估不同仓位管理方案的风险
    """
    
    def __init__(self, trades: list, n_simulations: int = 1000):
        """
        Args:
            trades: 交易列表，每个交易包含 'pnl' 字段
            n_simulations: 模拟次数
        """
        self.trades = trades
        self.n_simulations = n_simulations
        self.pnl_array = np.array([t['pnl'] for t in trades])
    
    def run_analysis(
        self,
        position_sizer: PositionSizer,
        initial_equity: float = 100000.0,
        point_value: float = 1.0
    ) -> Dict:
        """
        运行 Monte Carlo 分析
        
        Args:
            position_sizer: 仓位管理器
            initial_equity: 初始权益
            point_value: 每点价值
        
        Returns:
            分析结果字典
        """
        n_trades = len(self.trades)
        equity_paths = []
        max_drawdowns = []
        final_equities = []
        ruin_count = 0
        
        for _ in range(self.n_simulations):
            # 随机打乱交易顺序
            shuffled_indices = np.random.permutation(n_trades)
            shuffled_pnls = self.pnl_array[shuffled_indices]
            
            # 模拟权益曲线
            equity = initial_equity
            peak = initial_equity
            max_dd = 0
            ruined = False
            
            for pnl in shuffled_pnls:
                if ruined:
                    break
                
                # 计算仓位 (简化：假设固定止损距离)
                stop_distance = abs(pnl) / point_value if pnl != 0 else 10
                contracts = position_sizer.calculate_position(
                    equity=equity,
                    stop_distance=stop_distance,
                    point_value=point_value
                )
                
                # 更新权益
                equity += pnl * contracts
                
                # 更新峰值和回撤
                if equity > peak:
                    peak = equity
                
                current_dd = (peak - equity) / peak if peak > 0 else 0
                max_dd = max(max_dd, current_dd)
                
                # 检查破产
                if equity < initial_equity * 0.1:  # 亏损超过 90% 视为破产
                    ruined = True
                    ruin_count += 1
            
            equity_paths.append(equity)
            max_drawdowns.append(max_dd)
            final_equities.append(equity)
        
        # 统计结果
        results = {
            'mean_final_equity': np.mean(final_equities),
            'median_final_equity': np.median(final_equities),
            'std_final_equity': np.std(final_equities),
            'mean_max_drawdown': np.mean(max_drawdowns),
            'median_max_drawdown': np.median(max_drawdowns),
            'ruin_probability': ruin_count / self.n_simulations,
            'win_probability': np.mean([e > initial_equity for e in final_equities]),
            'percentile_5': np.percentile(final_equities, 5),
            'percentile_95': np.percentile(final_equities, 95)
        }
        
        return results


def compare_position_sizers(trades: list, initial_equity: float = 100000.0):
    """
    比较不同仓位管理方法
    
    Args:
        trades: 交易列表
        initial_equity: 初始权益
    
    Returns:
        比较结果
    """
    sizers = {
        'Fixed (1 contract)': FixedPositionSizer(contracts=1),
        'Fixed Fractional (2%)': FixedFractionalPositionSizer(risk_percent=0.02),
        'Fixed Ratio (Delta=1000)': FixedRatioPositionSizer(delta=1000, starting_equity=initial_equity),
        'Max Drawdown (20%)': MaxDrawdownPositionSizer(max_drawdown_percent=0.20)
    }
    
    analyzer = MonteCarloAnalyzer(trades, n_simulations=500)
    
    results = {}
    for name, sizer in sizers.items():
        result = analyzer.run_analysis(sizer, initial_equity)
        results[name] = result
    
    return results


def example_usage():
    """使用示例"""
    # 生成示例交易数据
    np.random.seed(42)
    n_trades = 100
    
    # 模拟交易：胜率 45%，盈亏比 2:1
    wins = np.random.choice([1, 0], size=n_trades, p=[0.45, 0.55])
    pnls = np.where(
        wins == 1,
        np.random.uniform(500, 2000, n_trades),  # 盈利
        np.random.uniform(-1000, -100, n_trades)  # 亏损
    )
    
    trades = [{'pnl': pnl} for pnl in pnls]
    
    # 比较不同仓位管理方法
    print("=" * 70)
    print("仓位管理方法比较 (Monte Carlo 分析，500 次模拟)")
    print("=" * 70)
    
    results = compare_position_sizers(trades)
    
    # 打印结果表格
    print(f"\n{'方法':<25} {'最终权益均值':>12} {'最大回撤中位数':>12} {'破产概率':>10} {'胜率':>10}")
    print("-" * 70)
    
    for name, result in results.items():
        print(f"{name:<25} ${result['mean_final_equity']:>10,.0f} {result['median_max_drawdown']*100:>11.2f}% "
              f"{result['ruin_probability']*100:>9.2f}% {result['win_probability']*100:>9.2f}%")
    
    print("-" * 70)
    
    # 详细分析固定分数法
    print("\n固定分数法 (2%) 详细分析:")
    ff_result = results['Fixed Fractional (2%)']
    print(f"  最终权益均值：${ff_result['mean_final_equity']:,.2f}")
    print(f"  最终权益中位数：${ff_result['median_final_equity']:,.2f}")
    print(f"  最终权益标准差：${ff_result['std_final_equity']:,.2f}")
    print(f"  5% 分位数：${ff_result['percentile_5']:,.2f}")
    print(f"  95% 分位数：${ff_result['percentile_95']:,.2f}")
    print(f"  最大回撤中位数：{ff_result['median_max_drawdown']*100:.2f}%")
    print(f"  破产概率：{ff_result['ruin_probability']*100:.2f}%")
    print(f"  盈利概率：{ff_result['win_probability']*100:.2f}%")
    
    return results


if __name__ == '__main__':
    example_usage()
