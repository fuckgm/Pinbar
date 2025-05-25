#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pinbar策略核心逻辑
包含策略类和回测执行函数
"""

import pandas as pd
import numpy as np
import backtrader as bt
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from config import TradingParams, BacktestParams
from data_manager import CustomDataFeed
from enhanced_signal_generator import EnhancedPinbarDetector, PinbarSignal
from dynamic_leverage_manager import DynamicLeverageManager

class EnhancedPinbarStrategy(bt.Strategy):
    """
    增强版Pinbar策略 - 核心交易逻辑
    """
    
    def __init__(self, trading_params: TradingParams, 
                 detector_config: Dict[str, Any] = None,
                 use_dynamic_leverage: bool = False):
        
        print("🚀 初始化增强版Pinbar策略...")
        
        # 基础参数
        self.trading_params = trading_params
        self.use_dynamic_leverage = use_dynamic_leverage
        
        # 交易成本参数
        self.commission_rate = 0.0005  # 0.05% 手续费
        self.funding_rate = 0.0001     # 0.01% 资金费率（8小时）
        self.slippage_rate = 0.0002    # 0.02% 滑点
        self.funding_interval_hours = 8  # 资金费率收取间隔
        
        # 初始化信号检测器
        self.pinbar_detector = EnhancedPinbarDetector(detector_config or self._get_default_detector_config())
        
        # 计算最小所需K线数量
        self.min_required_bars = max(
            self.pinbar_detector.trend_period,
            self.pinbar_detector.rsi_period,
            self.pinbar_detector.bb_period,
            self.pinbar_detector.adx_period,
            self.pinbar_detector.atr_period,
            50  # 最少需要50根K线
        )
        
        # 动态杠杆管理器（可选）
        if use_dynamic_leverage:
            self.leverage_manager = DynamicLeverageManager()
            print("✅ 启用动态杠杆管理")
        
        # 交易状态管理
        self.active_trades = {}
        self.trade_counter = 0
        self.trade_history = []
        self.signal_history = []
        self.executed_signals = []
        
        # 统计信息
        self.account_initial = self.broker.getcash()
        self.account_peak = self.account_initial
        self.max_dd = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profits = 0.0
        self.total_losses = 0.0
        
        # 信号质量统计
        self.signal_stats = {
            'total_signals': 0,
            'executed_signals': 0,
            'trend_aligned_signals': 0,
            'high_quality_signals': 0,
            'signal_success_rate': 0.0
        }
        
        # 数据缓存
        self.data_cache = []
        self.last_signal_check = 0
        
        print(f"✅ 策略初始化完成:")
        print(f"   - 动态杠杆: {use_dynamic_leverage}")
        print(f"   - 最小K线数: {self.min_required_bars}")
        print(f"   - 初始资金: {self.account_initial:,.2f} USDT")

    def _get_default_detector_config(self) -> Dict[str, Any]:
        """获取默认检测器配置"""
        return {
            'min_shadow_body_ratio': 2.0,
            'max_body_ratio': 0.35,
            'min_candle_size': 0.003,
            'trend_period': 20,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'bb_period': 20,
            'volume_threshold': 1.3,
            'sr_lookback': 50,
            'level_proximity': 0.002,
            'min_signal_score': 3,
            'adx_period': 14,
            'adx_threshold': 25,
            'atr_period': 14,
            'atr_percentile': 30,
            'volume_ma_period': 20,
            'volume_threshold_ratio': 0.7,
            'min_consolidation_bars': 10,
            'large_move_threshold': 0.05,
            'large_move_exclude_bars': 3
        }

    def prenext(self):
        """数据不足时调用"""
        self._update_data_cache()

    def next(self):
        """主交易逻辑"""
        # 1. 更新当前K线数据到缓存
        self._update_data_cache()
        
        # 2. 检查数据是否充足
        if len(self.data_cache) < self.min_required_bars:
            return
            
        # 3. 管理现有持仓
        self._manage_active_trades()
        
        # 4. 检查新信号
        self._check_for_new_signals()
        
        # 5. 更新账户统计
        self._update_account_stats()

    def _update_data_cache(self):
        """更新数据缓存"""
        current_data = {
            'timestamp': self.data.datetime.datetime(0),
            'open': self.data.open[0],
            'high': self.data.high[0],
            'low': self.data.low[0],
            'close': self.data.close[0],
            'volume': self.data.volume[0]
        }
        
        self.data_cache.append(current_data)
        
        # 保留最近1000根K线数据
        if len(self.data_cache) > 1000:
            self.data_cache.pop(0)

    def _check_for_new_signals(self):
        """检查当前K线是否产生新信号 - 优化版"""
        
        # 检查是否达到最大持仓数
        if len(self.active_trades) >= self.trading_params.max_positions:
            return
        
        # 准备数据
        if len(self.data_cache) < self.min_required_bars:
            return

        df = pd.DataFrame(self.data_cache)
        
        # 只检测到倒数第二根K线（已完成的K线）
        df_for_signal = df[:-1]
        
        if len(df_for_signal) < self.min_required_bars:
            return
        
        try:
            # 使用增强信号检测器
            all_signals = self.pinbar_detector.detect_pinbar_patterns(df_for_signal)
            
            if all_signals:
                # 只处理最新完成K线的信号
                current_bar_index = len(df_for_signal) - 1
                new_signals = [s for s in all_signals if s.index == current_bar_index]
                
                for signal in new_signals:
                    # 记录信号统计
                    self.signal_stats['total_signals'] += 1
                    
                    signal_info = {
                        'timestamp': signal.timestamp,
                        'type': signal.type,
                        'direction': signal.direction,
                        'confidence_score': signal.confidence_score,
                        'signal_strength': signal.signal_strength,
                        'trend_alignment': signal.trend_alignment,
                        'entry_reason': signal.entry_reason,
                        'executed': False,
                        'execution_reason': ''
                    }
                    
                    # 统计信号质量
                    if signal.trend_alignment:
                        self.signal_stats['trend_aligned_signals'] += 1
                    
                    if signal.confidence_score >= 0.7 and signal.signal_strength >= 4:
                        self.signal_stats['high_quality_signals'] += 1
                    
                    # 判断是否执行信号 - 放宽条件
                    if self._should_execute_signal_relaxed(signal):
                        print(f"🎯 执行信号: {signal.type} {signal.direction} @ {signal.close_price:.4f}")
                        self._execute_signal(signal)
                        signal_info['executed'] = True
                        signal_info['execution_reason'] = '信号质量达标'
                        self.signal_stats['executed_signals'] += 1
                    else:
                        signal_info['execution_reason'] = '信号质量不足'
                    
                    self.signal_history.append(signal_info)
                    
        except Exception as e:
            print(f"❌ 信号检测失败: {e}")
            import traceback
            traceback.print_exc()

    def _should_execute_signal_relaxed(self, signal: PinbarSignal) -> bool:
        """判断是否应该执行信号 - 放宽版本"""
        print(f"🔍 检查信号执行条件: {signal.type} {signal.direction}")
        print(f"    置信度: {signal.confidence_score:.2f}, 强度: {signal.signal_strength}")

        # 1. 基础质量检查 - 大幅放宽
        if signal.confidence_score < 0.1:  # 从0.3降低到0.1
            print(f"❌ 信号质量不足: 置信度{signal.confidence_score:.2f} < 0.1")
            return False
        
        if signal.signal_strength < 1:  # 从2降低到1
            print(f"❌ 信号强度不足: {signal.signal_strength} < 1")
            return False
        
        # 2. 检查资金是否充足
        current_cash = self.broker.getcash()
        if current_cash < 100:  # 至少需要100 USDT
            print(f"❌ 资金不足: {current_cash:.2f} < 100")
            return False
        
        # 3. 简化的风险检查
        current_price = signal.close_price
        stop_distance = abs(current_price - signal.stop_loss)
        
        if stop_distance <= 0:
            print(f"❌ 止损距离无效: {stop_distance}")
            return False
        
        # 4. 检查风险回报比
        take_profit_distance = abs(signal.take_profit_1 - current_price)
        risk_reward_ratio = take_profit_distance / stop_distance
        
        if risk_reward_ratio < 1.0:  # 至少1:1
            print(f"❌ 风险回报比不足: {risk_reward_ratio:.2f} < 1.0")
            return False
        
        print(f"✅ 信号通过检查，准备执行")
        return True

    def _execute_signal(self, signal: PinbarSignal):
        """执行信号开仓 - 优化版"""
        print(f"📊 开始执行信号: {signal.type} {signal.direction}")
        
        current_price = self.data.close[0]
        direction = signal.direction
        
        # 考虑滑点的实际成交价
        if direction == 'buy':
            actual_entry_price = current_price * (1 + self.slippage_rate)
        else:
            actual_entry_price = current_price * (1 - self.slippage_rate)
        
        # 计算杠杆
        leverage = self._calculate_dynamic_leverage(signal)
        
        # 计算仓位大小 - 简化版本
        cash = self.broker.getcash()
        risk_amount = cash * self.trading_params.risk_per_trade
        
        # 止损距离
        stop_distance = abs(actual_entry_price - signal.stop_loss)
        
        # 计算仓位大小
        # 仓位大小 = 风险金额 / 止损距离
        if stop_distance > 0:
            position_value = risk_amount / (stop_distance / actual_entry_price)
            position_size = position_value / actual_entry_price
            
            # 考虑杠杆
            position_size = min(position_size * leverage, cash * 0.9 / actual_entry_price)
        else:
            print(f"❌ 止损距离为0，无法计算仓位")
            return
        
        # 最小仓位检查
        min_position_value = 10  # 最小10 USDT
        if position_size * actual_entry_price < min_position_value:
            position_size = min_position_value / actual_entry_price
        
        print(f"💰 仓位计算:")
        print(f"    现金: {cash:.2f} USDT")
        print(f"    风险金额: {risk_amount:.2f} USDT")
        print(f"    仓位大小: {position_size:.6f}")
        print(f"    仓位价值: {position_size * actual_entry_price:.2f} USDT")
        print(f"    杠杆: {leverage}x")
        
        # 执行开仓
        try:
            if direction == 'buy':
                print(f"📈 执行买入订单: {position_size:.6f} @ {actual_entry_price:.4f}")
                order = self.buy(size=position_size)
            else:
                print(f"📉 执行卖出订单: {position_size:.6f} @ {actual_entry_price:.4f}")
                order = self.sell(size=position_size)
            
            if order is None:
                print(f"❌ 订单执行失败")
                return
            
            # 记录交易信息
            self.trade_counter += 1
            trade_id = f"T{self.trade_counter:04d}"
            
            # 计算手续费
            commission_cost = position_size * actual_entry_price * self.commission_rate
            
            self.active_trades[trade_id] = {
                'order': order,
                'direction': direction,
                'entry_price': current_price,
                'actual_entry_price': actual_entry_price,
                'entry_time': self.data.datetime.datetime(),
                'size': position_size,
                'stop_loss': signal.stop_loss,
                'take_profit_1': signal.take_profit_1,
                'take_profit_2': signal.take_profit_2,
                'take_profit_3': signal.take_profit_3,
                'leverage': leverage,
                'signal_info': signal,
                'trailing_stop': signal.stop_loss,
                'trailing_activated': False,
                'highest_price': actual_entry_price if direction == 'buy' else 0,
                'lowest_price': actual_entry_price if direction == 'sell' else float('inf'),
                'commission_paid': commission_cost,
                'funding_paid': 0,
                'total_costs': commission_cost,
                'position_amount': position_size * actual_entry_price,
                'signal_type': signal.type,
                'signal_strength': signal.signal_strength,
                'confidence_score': signal.confidence_score,
                'trend_alignment': signal.trend_alignment,
                'entry_reason': signal.entry_reason
            }
            
            print(f"✅ 成功开仓 {trade_id}: {direction} @ {actual_entry_price:.4f}")
            print(f"    杠杆: {leverage}x | 信号: {signal.type} | 强度: {signal.signal_strength}")
            print(f"    置信度: {signal.confidence_score:.2f} | 止损: {signal.stop_loss:.4f}")
            
        except Exception as e:
            print(f"❌ 执行开仓失败: {e}")
            import traceback
            traceback.print_exc()

    def _calculate_dynamic_leverage(self, signal: PinbarSignal) -> float:
        """计算动态杠杆"""
        base_leverage = self.trading_params.leverage
        
        if not self.use_dynamic_leverage:
            return base_leverage
        
        try:
            # 根据信号质量调整杠杆
            quality_factor = signal.confidence_score * (signal.signal_strength / 5.0)
            trend_bonus = 1.1 if signal.trend_alignment else 0.9
            
            adjusted_leverage = base_leverage * quality_factor * trend_bonus
            
            # 限制杠杆范围
            return max(1, min(base_leverage, int(adjusted_leverage)))
            
        except Exception as e:
            print(f"❌ 动态杠杆计算失败: {e}")
            return base_leverage

    def _manage_active_trades(self):
        """管理现有持仓"""
        current_price = self.data.close[0]
        current_time = self.data.datetime.datetime(0)
        trades_to_close = []
        
        for trade_id, trade_info in self.active_trades.items():
            # 检查止损
            if self._check_stop_loss(trade_info, current_price):
                trades_to_close.append((trade_id, "止损"))
                continue
            
            # 检查止盈
            exit_reason = self._check_take_profit(trade_info, current_price)
            if exit_reason:
                trades_to_close.append((trade_id, exit_reason))
        
        # 执行平仓
        for trade_id, reason in trades_to_close:
            self._close_position(trade_id, reason)

    def _check_stop_loss(self, trade_info: Dict[str, Any], current_price: float) -> bool:
        """检查是否触发止损"""
        direction = trade_info['direction']
        stop_loss = trade_info['stop_loss']
        
        if direction == 'buy' and current_price <= stop_loss:
            return True
        elif direction == 'sell' and current_price >= stop_loss:
            return True
        
        return False

    def _check_take_profit(self, trade_info: Dict[str, Any], current_price: float) -> Optional[str]:
        """检查是否触发止盈"""
        direction = trade_info['direction']
        tp1 = trade_info['take_profit_1']
        
        if direction == 'buy' and current_price >= tp1:
            return "止盈"
        elif direction == 'sell' and current_price <= tp1:
            return "止盈"
        
        return None

    def _close_position(self, trade_id: str, reason: str):
        """平仓"""
        if trade_id not in self.active_trades:
            return
        
        trade_info = self.active_trades[trade_id]
        current_price = self.data.close[0]
        direction = trade_info['direction']
        
        # 考虑滑点的实际成交价
        if direction == 'buy':
            actual_exit_price = current_price * (1 - self.slippage_rate)
        else:
            actual_exit_price = current_price * (1 + self.slippage_rate)
        
        # 计算平仓手续费
        exit_commission = trade_info['size'] * actual_exit_price * self.commission_rate
        
        # 执行平仓
        try:
            if direction == 'buy':
                self.sell(size=trade_info['size'])
            else:
                self.buy(size=trade_info['size'])
            
            # 计算收益
            if direction == 'buy':
                gross_profit = (actual_exit_price - trade_info['actual_entry_price']) * trade_info['size']
            else:
                gross_profit = (trade_info['actual_entry_price'] - actual_exit_price) * trade_info['size']
            
            # 总成本
            total_costs = trade_info['total_costs'] + exit_commission
            net_profit = gross_profit - total_costs
            
            # 记录交易结果
            trade_record = {
                'trade_id': trade_id,
                'direction': direction,
                'entry_time': trade_info['entry_time'],
                'exit_time': self.data.datetime.datetime(),
                'entry_price': trade_info['actual_entry_price'],
                'exit_price': actual_exit_price,
                'size': trade_info['size'],
                'gross_profit': gross_profit,
                'net_profit': net_profit,
                'profit': net_profit,
                'profit_pct': net_profit / (trade_info['actual_entry_price'] * trade_info['size']) * 100,
                'reason': reason,
                'leverage': trade_info['leverage'],
                'commission_costs': trade_info['commission_paid'] + exit_commission,
                'funding_costs': trade_info['funding_paid'],
                'total_costs': total_costs,
                'signal_type': trade_info['signal_type'],
                'signal_strength': trade_info['signal_strength'],
                'confidence_score': trade_info['confidence_score'],
                'trend_alignment': trade_info['trend_alignment'],
                'entry_reason': trade_info['entry_reason']
            }
            
            self.trade_history.append(trade_record)
            
            # 更新统计
            if net_profit > 0:
                self.winning_trades += 1
                self.total_profits += net_profit
            else:
                self.losing_trades += 1
                self.total_losses += abs(net_profit)
            
            del self.active_trades[trade_id]
            
            print(f"🔄 平仓 {trade_id}: {direction} @ {actual_exit_price:.4f}")
            print(f"    净利: {net_profit:.2f} USDT | 原因: {reason}")
            
        except Exception as e:
            print(f"❌ 平仓失败: {e}")

    def _update_account_stats(self):
        """更新账户统计信息"""
        current_value = self.broker.getvalue()
        
        if current_value > self.account_peak:
            self.account_peak = current_value
        
        drawdown = (self.account_peak - current_value) / self.account_peak
        if drawdown > self.max_dd:
            self.max_dd = drawdown

    def stop(self):
        """回测结束处理"""
        # 平掉所有持仓
        for trade_id in list(self.active_trades.keys()):
            self._close_position(trade_id, "回测结束")
        
        # 计算最终信号统计
        if self.signal_stats['total_signals'] > 0:
            self.signal_stats['signal_execution_rate'] = (
                self.signal_stats['executed_signals'] / self.signal_stats['total_signals'] * 100
            )
        
        if self.signal_stats['executed_signals'] > 0:
            winning_signals = sum(1 for t in self.trade_history if t['profit'] > 0)
            self.signal_stats['signal_success_rate'] = (
                winning_signals / self.signal_stats['executed_signals'] * 100
            )
        
        print(f"\n📊 回测结束统计:")
        print(f"    总信号: {self.signal_stats['total_signals']}")
        print(f"    执行信号: {self.signal_stats['executed_signals']}")
        print(f"    执行率: {self.signal_stats.get('signal_execution_rate', 0):.1f}%")
        print(f"    总交易: {len(self.trade_history)}")
        print(f"    盈利交易: {self.winning_trades}")

def run_enhanced_backtest(data: pd.DataFrame, trading_params: TradingParams, 
                         backtest_params: BacktestParams,
                         detector_config: Dict[str, Any] = None,
                         use_dynamic_leverage: bool = False) -> Dict[str, Any]:
    """运行增强版回测"""
    print(f"🚀 开始增强版回测: {backtest_params.symbol} {backtest_params.interval}")
    
    # 设置Backtrader环境
    cerebro = bt.Cerebro()
    
    # 添加数据
    data_feed = CustomDataFeed(dataname=data)
    cerebro.adddata(data_feed)
    
    # 添加增强策略
    cerebro.addstrategy(EnhancedPinbarStrategy, 
                       trading_params=trading_params,
                       detector_config=detector_config,
                       use_dynamic_leverage=use_dynamic_leverage)
    
    # 设置初始资金和手续费
    cerebro.broker.setcash(backtest_params.initial_cash)
    cerebro.broker.setcommission(commission=backtest_params.commission)
    
    # 运行回测
    print(f'💰 初始资金: {backtest_params.initial_cash:,.2f} USDT')
    results = cerebro.run()
    strategy = results[0]
    
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - backtest_params.initial_cash) / backtest_params.initial_cash * 100
    
    print(f'💰 最终资金: {final_value:,.2f} USDT')
    print(f'📈 总收益率: {total_return:.2f}%')
    
    # 计算详细统计
    total_trades = len(strategy.trade_history)
    signal_stats = strategy.signal_stats
    
    if total_trades > 0:
        win_rate = (strategy.winning_trades / total_trades * 100)
        avg_profit = strategy.total_profits / strategy.winning_trades if strategy.winning_trades > 0 else 0
        avg_loss = strategy.total_losses / strategy.losing_trades if strategy.losing_trades > 0 else 0
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
        
        # 杠杆使用分析
        if strategy.trade_history:
            leverages = [t.get('leverage', 1) for t in strategy.trade_history]
            avg_leverage = np.mean(leverages)
            max_leverage = max(leverages)
            
            # 信号质量分析
            signal_strengths = [t.get('signal_strength', 0) for t in strategy.trade_history]
            confidence_scores = [t.get('confidence_score', 0) for t in strategy.trade_history]
            trend_alignments = [t.get('trend_alignment', False) for t in strategy.trade_history]
            
            avg_signal_strength = np.mean(signal_strengths)
            avg_confidence = np.mean(confidence_scores)
            trend_alignment_rate = sum(trend_alignments) / len(trend_alignments) * 100
        else:
            avg_leverage = max_leverage = 1
            avg_signal_strength = avg_confidence = trend_alignment_rate = 0
    else:
        win_rate = profit_factor = 0
        avg_leverage = max_leverage = 1
        avg_signal_strength = avg_confidence = trend_alignment_rate = 0
    
    # 夏普比率
    if strategy.trade_history:
        returns = [trade['profit'] for trade in strategy.trade_history]
        sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
    else:
        sharpe_ratio = 0
    
    # 打印信号质量统计
    print(f"\n📊 信号质量统计:")
    print(f"   总信号数: {signal_stats['total_signals']}")
    print(f"   执行信号数: {signal_stats['executed_signals']}")
    print(f"   执行率: {signal_stats.get('signal_execution_rate', 0):.1f}%")
    print(f"   信号成功率: {signal_stats.get('signal_success_rate', 0):.1f}%")
    
    return {
        'initial_cash': backtest_params.initial_cash,
        'final_value': final_value,
        'total_return': total_return,
        'total_trades': total_trades,
        'win_trades': strategy.winning_trades,
        'lose_trades': strategy.losing_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_drawdown': strategy.max_dd,
        'sharpe_ratio': sharpe_ratio,
        'avg_leverage': avg_leverage,
        'max_leverage': max_leverage,
        'trades': strategy.trade_history,
        'signals': strategy.signal_history,
        'executed_signals': strategy.executed_signals,
        'use_dynamic_leverage': use_dynamic_leverage,
        'signal_stats': signal_stats,
        'avg_signal_strength': avg_signal_strength,
        'avg_confidence_score': avg_confidence,
        'trend_alignment_rate': trend_alignment_rate
    }