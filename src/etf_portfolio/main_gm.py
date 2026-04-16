# coding=utf-8
from __future__ import print_function, absolute_import
import pandas as pd
import numpy as np
import riskfolio as rp
from gm.api import *
from datetime import datetime, timedelta

# --- Configuration & Assets ---
FULL_ETF_POOL = {
    'SHSE.513120': '港股创新药ETF',
    'SZSE.159301': '公用事业ETF',
    'SZSE.159869': '游戏ETF',
    'SHSE.511260': '10年期国债ETF',
    'SHSE.511090': '30年期国债ETF',
    'SHSE.511380': '可转债ETF',
    'SHSE.518800': '黄金ETF',
    'SHSE.510300': '沪深300ETF',
    'SZSE.159915': '创业板ETF',
    'SHSE.513920': '港股通央企红利ETF',
    'SZSE.159920': '恒生ETF',
    'SZSE.159742': '恒生科技ETF',
    'SZSE.159941': '纳指ETF',
    'SHSE.501018': '南方原油ETF',
    'SZSE.162411': '华宝油气ETF'
}

# 调仓阈值：目标权重与当前实际权重偏差超过此值才下单（避免微调）
REBALANCE_THRESHOLD = 0.02  # 2%


def get_optimal_weights(returns, model='EW'):
    """
    Get optimal weights using riskfolio-lib with robust fallbacks.
    """
    if returns.empty:
        return pd.Series(dtype=float)

    n_assets = returns.shape[1]
    if n_assets == 0:
        return pd.Series(dtype=float)
    if n_assets == 1:
        return pd.Series([1.0], index=returns.columns)

    try:
        if model in ['HRP', 'HERC', 'NCO']:
            hc_port = rp.HCPortfolio(returns=returns)
            weights = hc_port.optimization(
                model=model,
                codependence='pearson',
                obj='MinRisk',
                rm='MV',
                rf=0,
                l=2,
                method_mu='hist',
                method_cov='ledoit',
                leaf_order=True,
            )
        else:
            port = rp.Portfolio(returns=returns)
            port.assets_stats(method_mu='hist', method_cov='ledoit')
            if model == 'GMV':
                weights = port.optimization(model='Classic', rm='MV', obj='MinRisk', rf=0, l=0, hist=True)
            elif model == 'MaxSharpe':
                weights = port.optimization(model='Classic', rm='MV', obj='Sharpe', rf=0, l=0, hist=True)
            elif model == 'ERC':
                weights = port.rp_optimization(model='Classic', rm='MV', rf=0, hist=True)
            else:
                return pd.Series(1.0 / n_assets, index=returns.columns)

        if weights is None or 'weights' not in weights.columns:
            return pd.Series(1.0 / n_assets, index=returns.columns)
        return weights['weights']
    except Exception as e:
        print(f"Riskfolio Error: {e}. Falling back to Equal Weight.")
        return pd.Series(1.0 / n_assets, index=returns.columns)


def get_safe_history(symbols, end_time, window):
    """
    Fetch history data up to T-1 for metrics calculation.
    Returns: (pivot_prices, latest_close, sma)
    """
    decision_date = end_time.date()
    safe_end = datetime.combine(decision_date - timedelta(days=1), datetime.max.time())

    # 增加 lookback 保证协方差矩阵稳定
    lookback = max(window + 10, 260)
    start_time = (safe_end - timedelta(days=lookback)).strftime('%Y-%m-%d')
    history_data = history(
        symbol=symbols, frequency='1d',
        start_time=start_time,
        end_time=safe_end.strftime('%Y-%m-%d %H:%M:%S'),
        fields='symbol,close,bob', df=True
    )

    if history_data.empty:
        return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=float)

    pivot_data = history_data.pivot(index='bob', columns='symbol', values='close').ffill()
    latest_close = pivot_data.iloc[-1]
    sma = pivot_data.rolling(window=window).mean().iloc[-1]

    return pivot_data, latest_close, sma


def get_current_weight_map(context):
    """
    计算当前各标的的实际持仓权重（占净值比例）。
    返回: Dict[symbol, float]
    """
    try:
        acc = context.account()
        nav = acc.cash.get('nav', 0)
        if nav <= 0:
            return {}
        positions = acc.positions()
        weight_map = {}
        for pos in positions:
            if pos['amount'] > 0:
                # Bug 1修复：market_value = 市值，若缺失则用数量*成本均价近似，绝不能用 fpnl（盈亏值）
                mv = pos.get('market_value') or (pos.get('amount', 0) * pos.get('vwap', 0))
                weight_map[pos['symbol']] = mv / nav
        return weight_map
    except Exception:
        return {}


def execute_targets(context, active_targets):
    """
    与当前实际持仓对比，只在以下情况下单：
    1. 目标权重为 0（止损/清仓）
    2. 当前未持仓但目标 > 0（新建仓）
    3. 目标与实际偏差超过 REBALANCE_THRESHOLD（月度重平衡纠偏）
    这样可以避免每日由持仓市值波动引发的无谓微调。
    """
    # 先取消所有未成交订单
    for order in get_unfinished_orders():
        cancel_order(order)

    current_weight_map = get_current_weight_map(context)
    positions = context.account().positions()
    current_symbols = set(p['symbol'] for p in positions if p['amount'] > 0)

    # 先处理需要清仓的标的（状态变化：从持仓变为 0）
    for sym in current_symbols:
        target = active_targets.get(sym, 0.0)
        if target < 0.001:
            order_target_percent(
                symbol=sym, percent=0,
                position_side=PositionSide_Long,
                order_type=OrderType_Market
            )

    # 再处理需要建仓/调仓的标的
    for sym, target_pct in active_targets.items():
        if target_pct < 0.001:
            continue  # 已在上方处理清仓

        current_pct = current_weight_map.get(sym, 0.0)
        deviation = abs(current_pct - target_pct)

        # 只有在新建仓或偏差超过阈值时才下单
        if sym not in current_symbols or deviation > REBALANCE_THRESHOLD:
            order_target_percent(
                symbol=sym, percent=target_pct,
                position_side=PositionSide_Long,
                order_type=OrderType_Market
            )


def init(context):
    params = getattr(context, 'params', {})
    context.model_name = params.get('model_name', 'EW')
    context.sma_window = params.get('sma_window', 20)
    context.fallback_asset = 'SHSE.511260'  # 10年期国债ETF 作为安全资产
    
    # Bug 3修复：方案A，将fallback_asset从优化池中完全剥离，仅作安全资产
    context.etf_symbols = [s for s in FULL_ETF_POOL.keys() if s != context.fallback_asset]

    context.blueprint = {}          # {symbol: target_weight}，月度优化结果
    context.last_rebalance_month = -1
    context.rebalanced_date = None  # 用于记录这天是否已经做过月度重平衡

    subscribe(symbols=context.etf_symbols + [context.fallback_asset], frequency='1d')

    # 月初第一个交易日重平衡
    schedule(handle_monthly_rebalance, date_rule='1m', time_rule='09:35:00')
    # 每日趋势检查（仅做止损，不做权重纠偏）
    schedule(handle_daily_routine, date_rule='1d', time_rule='09:35:00')

    print(f"Strategy Initiated. Model: {context.model_name}, SMA Window: {context.sma_window}")


def handle_daily_routine(context):
    """
    每日趋势检查：
    - 功能：将已跌破 SMA 的持仓清零（止损），将重新上穿 SMA 的资产按 blueprint 权重买回
    - 关键约束：权重纠偏（rebalancing）不在此处触发，避免每日微调造成的过度交易
    """
    if not context.blueprint:
        return
        
    # Bug 2修复：如果是月初重平衡日，跳过每日止损逻辑以免双重下单
    if getattr(context, 'rebalanced_date', None) == context.now.date():
        return

    # 1. 日志
    try:
        acc = context.account()
        nav = acc.cash.get('nav', 0)
        available = acc.cash.get('available', 0)
        print(f"[{context.now}] Equity: {nav:,.2f}, Available Cash: {available:,.2f}")
    except Exception:
        pass

    # 2. 获取 T-1 SMA（避免前视偏差）
    symbols_to_check = list(set(list(context.blueprint.keys()) + [context.fallback_asset]))
    _, latest_prices_series, sma_values = get_safe_history(symbols_to_check, context.now, context.sma_window)
    if latest_prices_series.empty:
        return

    # 3. 计算当日目标权重（仅考虑趋势状态，不做权重纠偏）
    active_targets = {}
    total_assigned_weight = 0.0

    for sym, b_weight in context.blueprint.items():
        price = latest_prices_series.get(sym)
        sma = sma_values.get(sym)

        if price is not None and sma is not None and price > sma:
            # 资产在趋势上：保留其 blueprint 权重
            active_targets[sym] = b_weight
            total_assigned_weight += b_weight
        else:
            # 资产跌破趋势：目标清零（止损）
            active_targets[sym] = 0.0

    # 4. 处理剩余权重 -> 安全资产（国债 / 空仓）
    remaining_weight = 1.0 - total_assigned_weight
    if remaining_weight > 0.01:
        f_price = latest_prices_series.get(context.fallback_asset)
        f_sma = sma_values.get(context.fallback_asset)

        if f_price is not None and f_sma is not None and f_price > f_sma:
            # 安全资产处于上升趋势，才转入；否则保持现金
            prev = active_targets.get(context.fallback_asset, 0.0)
            active_targets[context.fallback_asset] = prev + remaining_weight

    # 5. 执行（带阈值过滤，避免微调）
    execute_targets(context, active_targets)


def handle_monthly_rebalance(context):
    """
    月初重平衡：重新优化权重并更新 blueprint。
    重平衡完成后强制调用 execute_targets 实现 *完整* 的权重纠偏。
    """
    current_month = context.now.month
    if current_month == context.last_rebalance_month:
        return

    print(f"[{context.now}] New Month Detected. Updating Blueprint...")
    context.last_rebalance_month = current_month
    context.rebalanced_date = context.now.date()  # 记录重平衡日期供 daily_routine 检查

    # 1. 获取 T-1 历史数据
    pivot_prices, current_prices, sma_values = get_safe_history(
        context.etf_symbols, context.now, context.sma_window
    )
    if pivot_prices.empty:
        return

    # Bug 4修复：剔除上市时间较短、历史数据不丰满（有NaN）的标的，避免污染协方差矩阵
    valid_history = pivot_prices.dropna(axis=1)

    # 2. 筛选趋势资产
    eligible_symbols = [
        s for s in context.etf_symbols
        if s in valid_history.columns
        and s in current_prices.index 
        and current_prices[s] > sma_values[s]
    ]

    # 3. 优化权重
    if not eligible_symbols:
        context.blueprint = {context.fallback_asset: 1.0}
        print(f"Blueprint updated. No trending assets, 100% in fallback.")
    else:
        # returns_df 此时是完整的（剔除了含有 NaN 的列），用 dropna() 去掉第一行的 NaN
        returns_df = valid_history[eligible_symbols].pct_change().dropna()
        try:
            weights = get_optimal_weights(returns_df, model=context.model_name)
            context.blueprint = weights.to_dict()
            print(f"Blueprint updated. Assets: {len(eligible_symbols)}")
        except Exception as e:
            print(f"Optimization Failure: {e}")
            avg = 1.0 / len(eligible_symbols)
            context.blueprint = {s: avg for s in eligible_symbols}

    # 4. 月度重平衡时强制执行完整权重纠偏
    #    临时关闭阈值过滤（直接调用底层，不走阈值）
    _force_rebalance(context)


def _force_rebalance(context):
    """
    月初强制重平衡：不受 REBALANCE_THRESHOLD 限制，全量执行目标权重。
    """
    if not context.blueprint:
        return

    symbols_to_check = list(set(list(context.blueprint.keys()) + [context.fallback_asset]))
    _, latest_prices_series, sma_values = get_safe_history(symbols_to_check, context.now, context.sma_window)
    if latest_prices_series.empty:
        return

    active_targets = {}
    total_assigned_weight = 0.0

    for sym, b_weight in context.blueprint.items():
        price = latest_prices_series.get(sym)
        sma = sma_values.get(sym)
        if price is not None and sma is not None and price > sma:
            active_targets[sym] = b_weight
            total_assigned_weight += b_weight
        else:
            active_targets[sym] = 0.0

    remaining_weight = 1.0 - total_assigned_weight
    if remaining_weight > 0.01:
        f_price = latest_prices_series.get(context.fallback_asset)
        f_sma = sma_values.get(context.fallback_asset)
        if f_price is not None and f_sma is not None and f_price > f_sma:
            prev = active_targets.get(context.fallback_asset, 0.0)
            active_targets[context.fallback_asset] = prev + remaining_weight

    # 强制：取消旧订单 + 对所有目标下单（无阈值）
    for order in get_unfinished_orders():
        cancel_order(order)

    positions = context.account().positions()
    current_symbols = set(p['symbol'] for p in positions if p['amount'] > 0)

    # 先清仓不在目标中的
    for sym in current_symbols:
        if active_targets.get(sym, 0.0) < 0.001:
            order_target_percent(symbol=sym, percent=0,
                                 position_side=PositionSide_Long,
                                 order_type=OrderType_Market)

    # 再建立新目标
    for sym, target_pct in active_targets.items():
        if target_pct >= 0.001:
            order_target_percent(symbol=sym, percent=target_pct,
                                 position_side=PositionSide_Long,
                                 order_type=OrderType_Market)


def on_backtest_finished(context, indicator):
    print("\n" + "=" * 50)
    print("BACKTEST RESULTS SUMMARY")
    print(f"Cumulative Return: {indicator.get('pnl_ratio', 0) * 100:.2f}%")
    print(f"Max Drawdown: {indicator.get('max_drawdown', 0) * 100:.2f}%")
    print(f"Sharpe Ratio: {indicator.get('sharpe_ratio', 0):.2f}")
    print("=" * 50 + "\n")


def on_order_status(context, order):
    if order['status'] == OrderStatus_Filled:
        print(f"[{context.now}] FILL: {order['symbol']} {order['side']} "
              f"Amt:{order['filled_amount']} @ {order['filled_vwap']:.4f}")


if __name__ == '__main__':
    run(strategy_id='ba1e1529-3953-11f1-bc4b-00155d321918',
        filename='main_gm.py',
        mode=MODE_BACKTEST,
        token='478dc4635c5198dbfcc962ac3bb209e5327edbff',
        backtest_start_time='2020-01-01 08:00:00',  # 修复：与 main.py 对齐
        backtest_end_time='2026-04-16 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
