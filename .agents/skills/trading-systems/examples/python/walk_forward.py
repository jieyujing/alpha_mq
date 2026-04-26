#!/usr/bin/env python3
"""
前向分析 (Walk Forward Analysis) 实现
基于《Trading Systems》Part I, Chapter 6

实现方法:
1. 滚动式 WFA (Rolling WFA)
2. 锚定式 WFA (Anchored WFA)

WFA 步骤:
1. 选择样本内 (IS) 和样本外 (OOS) 比例
2. 在 IS 数据上优化参数
3. 在 OOS 数据上测试优化后的参数
4. 向前滚动，重复步骤 2-3
5. 汇总所有 OOS 结果
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class WFAWindow:
    """WFA 窗口数据类"""
    window_id: int
    is_start: int
    is_end: int
    oos_start: int
    oos_end: int
    is_data: pd.DataFrame
    oos_data: pd.DataFrame
    optimal_params: Dict
    is_metrics: Dict
    oos_metrics: Dict


class WalkForwardAnalyzer(ABC):
    """前向分析器基类"""
    
    def __init__(
        self,
        data: pd.DataFrame,
        optimizer: Callable,
        tester: Callable,
        param_ranges: Dict
    ):
        """
        Args:
            data: 完整数据集
            optimizer: 优化函数，接收 (data, param_ranges) 返回最优参数
            tester: 测试函数，接收 (data, params) 返回指标字典
            param_ranges: 参数范围字典
        """
        self.data = data
        self.optimizer = optimizer
        self.tester = tester
        self.param_ranges = param_ranges
        self.windows: List[WFAWindow] = []
    
    @abstractmethod
    def generate_windows(self) -> List[Tuple[int, int, int, int]]:
        """
        生成 WFA 窗口
        
        Returns:
            窗口列表，每个窗口为 (is_start, is_end, oos_start, oos_end)
        """
        pass
    
    def run_analysis(self) -> Dict:
        """
        执行完整的前向分析
        
        Returns:
            分析结果字典
        """
        windows_config = self.generate_windows()
        self.windows = []
        
        for i, (is_start, is_end, oos_start, oos_end) in enumerate(windows_config):
            # 分割数据
            is_data = self.data.iloc[is_start:is_end].copy()
            oos_data = self.data.iloc[oos_start:oos_end].copy()
            
            # IS 优化
            optimal_params = self.optimizer(is_data, self.param_ranges)
            is_metrics = self.tester(is_data, optimal_params)
            
            # OOS 测试
            oos_metrics = self.tester(oos_data, optimal_params)
            
            # 保存窗口结果
            window = WFAWindow(
                window_id=i,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                is_data=is_data,
                oos_data=oos_data,
                optimal_params=optimal_params,
                is_metrics=is_metrics,
                oos_metrics=oos_metrics
            )
            self.windows.append(window)
        
        # 汇总结果
        return self._aggregate_results()
    
    def _aggregate_results(self) -> Dict:
        """汇总所有窗口结果"""
        if not self.windows:
            return {}
        
        # 汇总 OOS 指标
        oos_metrics_list = [w.oos_metrics for w in self.windows]
        is_metrics_list = [w.is_metrics for w in self.windows]
        
        # 计算平均指标
        avg_oos = {}
        avg_is = {}
        
        # 假设指标是数值型
        sample_metrics = oos_metrics_list[0]
        for key in sample_metrics.keys():
            if isinstance(sample_metrics[key], (int, float)):
                oos_values = [m.get(key, 0) for m in oos_metrics_list if key in m]
                is_values = [m.get(key, 0) for m in is_metrics_list if key in m]
                
                if oos_values:
                    avg_oos[key] = np.mean(oos_values)
                if is_values:
                    avg_is[key] = np.mean(is_values)
        
        # 计算 OOS/IS 比率 (稳健性指标)
        oos_is_ratio = {}
        for key in avg_oos.keys():
            if key in avg_is and avg_is[key] != 0:
                oos_is_ratio[key] = avg_oos[key] / avg_is[key]
        
        # 汇总所有 OOS 数据的表现
        all_oos_results = []
        for window in self.windows:
            all_oos_results.extend(window.oos_metrics.get('trades', []))
        
        return {
            'avg_is_metrics': avg_is,
            'avg_oos_metrics': avg_oos,
            'oos_is_ratio': oos_is_ratio,
            'n_windows': len(self.windows),
            'total_oos_trades': len(all_oos_results),
            'windows': self.windows
        }


class RollingWFA(WalkForwardAnalyzer):
    """
    滚动式前向分析
    
    固定窗口大小，每次向前滚动固定步长
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        optimizer: Callable,
        tester: Callable,
        param_ranges: Dict,
        window_size: int,
        step_size: int,
        is_ratio: float = 0.7
    ):
        """
        Args:
            data: 完整数据集
            optimizer: 优化函数
            tester: 测试函数
            param_ranges: 参数范围
            window_size: 窗口总大小 (IS + OOS)
            step_size: 每次滚动的步长
            is_ratio: IS 数据占比 (默认 70%)
        """
        super().__init__(data, optimizer, tester, param_ranges)
        self.window_size = window_size
        self.step_size = step_size
        self.is_ratio = is_ratio
    
    def generate_windows(self) -> List[Tuple[int, int, int, int]]:
        """生成滚动窗口"""
        windows = []
        n_data = len(self.data)
        
        is_size = int(self.window_size * self.is_ratio)
        oos_size = self.window_size - is_size
        
        start = 0
        window_id = 0
        
        while start + self.window_size <= n_data:
            is_start = start
            is_end = start + is_size
            oos_start = is_end
            oos_end = start + self.window_size
            
            windows.append((is_start, is_end, oos_start, oos_end))
            
            start += self.step_size
            window_id += 1
        
        return windows


class AnchoredWFA(WalkForwardAnalyzer):
    """
    锚定式前向分析
    
    起始点固定，窗口逐渐增大
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        optimizer: Callable,
        tester: Callable,
        param_ranges: Dict,
        min_window_size: int,
        step_size: int,
        is_ratio: float = 0.7
    ):
        """
        Args:
            data: 完整数据集
            optimizer: 优化函数
            tester: 测试函数
            param_ranges: 参数范围
            min_window_size: 最小窗口大小
            step_size: 每次增加的步长
            is_ratio: IS 数据占比
        """
        super().__init__(data, optimizer, tester, param_ranges)
        self.min_window_size = min_window_size
        self.step_size = step_size
        self.is_ratio = is_ratio
    
    def generate_windows(self) -> List[Tuple[int, int, int, int]]:
        """生成锚定窗口"""
        windows = []
        n_data = len(self.data)
        
        window_size = self.min_window_size
        
        while window_size <= n_data:
            is_size = int(window_size * self.is_ratio)
            oos_size = window_size - is_size
            
            is_start = 0  # 锚定在起点
            is_end = is_size
            oos_start = is_end
            oos_end = window_size
            
            windows.append((is_start, is_end, oos_start, oos_end))
            
            window_size += self.step_size
        
        return windows


class SimpleTrendOptimizer:
    """
    简单趋势策略优化器 (用于示例)
    
    优化双均线策略的参数
    """
    
    def __init__(self, data: pd.DataFrame):
        self.data = data
    
    def optimize(
        self,
        param_ranges: Dict,
        metric: str = 'profit_factor'
    ) -> Dict:
        """
        网格搜索优化
        
        Args:
            param_ranges: 参数范围，如 {'short_ma': [5, 10, 15], 'long_ma': [20, 30, 40]}
            metric: 优化目标指标
        
        Returns:
            最优参数
        """
        import itertools
        
        best_params = None
        best_value = -float('inf')
        
        # 生成参数网格
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        
        for param_combo in itertools.product(*param_values):
            params = dict(zip(param_names, param_combo))
            
            # 确保 short_ma < long_ma
            if 'short_ma' in params and 'long_ma' in params:
                if params['short_ma'] >= params['long_ma']:
                    continue
            
            # 测试参数
            metrics = self._test_params(params)
            
            if metric in metrics:
                value = metrics[metric]
                if value > best_value:
                    best_value = value
                    best_params = params
        
        return best_params if best_params else param_ranges[param_names[0]][0]
    
    def _test_params(self, params: Dict) -> Dict:
        """测试参数组合 (简化版)"""
        # 这里应该调用实际的回测函数
        # 简化示例：返回模拟指标
        short_ma = params.get('short_ma', 5)
        long_ma = params.get('long_ma', 20)
        
        # 模拟：中等长度参数表现更好
        base_pf = 1.5 - abs(short_ma - 10) * 0.05 - abs(long_ma - 30) * 0.02
        profit_factor = max(0.5, base_pf + np.random.normal(0, 0.1))
        
        return {
            'profit_factor': profit_factor,
            'net_profit': np.random.normal(10000, 5000),
            'max_drawdown': np.random.uniform(0.1, 0.3),
            'win_rate': np.random.uniform(0.35, 0.55)
        }


def example_usage():
    """使用示例"""
    print("=" * 70)
    print("前向分析 (Walk Forward Analysis) 示例")
    print("=" * 70)
    
    # 生成示例数据
    np.random.seed(42)
    n_days = 1000
    
    returns = np.random.normal(0.0005, 0.02, n_days)
    prices = 100 * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'close': prices,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, n_days)),
        'high': prices * (1 + np.random.uniform(0, 0.03, n_days)),
        'low': prices * (1 - np.random.uniform(0, 0.03, n_days))
    }, index=pd.date_range('2020-01-01', periods=n_days))
    
    # 定义优化器和测试器
    def optimizer(is_data, param_ranges):
        opt = SimpleTrendOptimizer(is_data)
        return opt.optimize(param_ranges)
    
    def tester(test_data, params):
        opt = SimpleTrendOptimizer(test_data)
        return opt._test_params(params)
    
    # 参数范围
    param_ranges = {
        'short_ma': [5, 10, 15, 20],
        'long_ma': [20, 30, 40, 50]
    }
    
    # 滚动式 WFA
    print("\n1. 滚动式 WFA (Rolling)")
    print("-" * 50)
    
    rolling_wfa = RollingWFA(
        data=data,
        optimizer=optimizer,
        tester=tester,
        param_ranges=param_ranges,
        window_size=200,
        step_size=50,
        is_ratio=0.7
    )
    
    rolling_results = rolling_wfa.run_analysis()
    
    print(f"窗口数量：{rolling_results['n_windows']}")
    print(f"OOS 总交易数：{rolling_results['total_oos_trades']}")
    print(f"\n平均 IS 指标:")
    for key, value in rolling_results['avg_is_metrics'].items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
    
    print(f"\n平均 OOS 指标:")
    for key, value in rolling_results['avg_oos_metrics'].items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
    
    print(f"\nOOS/IS 比率 (稳健性):")
    for key, value in rolling_results['oos_is_ratio'].items():
        if isinstance(value, float):
            quality = "✓ 稳健" if value > 0.5 else "⚠ 可能过拟合"
            print(f"  {key}: {value:.4f} {quality}")
    
    # 锚定式 WFA
    print("\n" + "=" * 70)
    print("2. 锚定式 WFA (Anchored)")
    print("-" * 50)
    
    anchored_wfa = AnchoredWFA(
        data=data,
        optimizer=optimizer,
        tester=tester,
        param_ranges=param_ranges,
        min_window_size=200,
        step_size=100,
        is_ratio=0.7
    )
    
    anchored_results = anchored_wfa.run_analysis()
    
    print(f"窗口数量：{anchored_results['n_windows']}")
    print(f"OOS 总交易数：{anchored_results['total_oos_trades']}")
    
    print(f"\n平均 OOS 指标:")
    for key, value in anchored_results['avg_oos_metrics'].items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
    
    # 打印每个窗口的最优参数
    print("\n" + "=" * 70)
    print("各窗口最优参数:")
    print("-" * 50)
    
    for i, window in enumerate(rolling_wfa.windows[:5]):  # 显示前 5 个窗口
        print(f"窗口 {i+1}: IS[{window.is_start}:{window.is_end}] → OOS[{window.oos_start}:{window.oos_end}]")
        print(f"  最优参数：{window.optimal_params}")
        print(f"  IS 盈亏比：{window.is_metrics.get('profit_factor', 'N/A'):.4f}")
        print(f"  OOS 盈亏比：{window.oos_metrics.get('profit_factor', 'N/A'):.4f}")
    
    print("\n" + "=" * 70)
    print("WFA 分析完成!")
    
    return rolling_results, anchored_results


if __name__ == '__main__':
    example_usage()
