#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告数据处理器 - 增强版
负责处理和准备回测报告所需的数据
新增：详细的交易成本分析（手续费、资金费率、滑点、保证金占用）
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import datetime

class ReportDataProcessor:
    """报告数据处理器 - 增强版"""
    
    def __init__(self):
        pass
    
    def prepare_enhanced_backtest_data(self, data: pd.DataFrame, results: Dict[str, Any],
                                config: Dict[str, Any]) -> Dict[str, Any]:
        """准备增强版回测数据 - 合并完整版（保留保证金修复+恢复完整统计）"""
        trades = results.get('trades', [])
        
        # 基本统计
        initial_cash = results.get('initial_cash', 20000)
        final_value = results.get('final_value', initial_cash)
        total_return = (final_value - initial_cash) / initial_cash * 100
        
        # === 增强统计计算（来自备份函数） ===
        if trades:
            profits = [t.get('profit', 0) for t in trades]
            win_trades = [p for p in profits if p > 0]
            lose_trades = [p for p in profits if p < 0]
            
            win_rate = len(win_trades) / len(trades) * 100
            avg_win = np.mean(win_trades) if win_trades else 0
            avg_loss = abs(np.mean(lose_trades)) if lose_trades else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
            
            # 新增统计指标（来自备份函数）
            max_win = max(profits) if profits else 0
            max_loss = min(profits) if profits else 0
            
            # 平均持仓时间
            holding_times = []
            for trade in trades:
                if 'entry_time' in trade and 'exit_time' in trade:
                    try:
                        entry = pd.to_datetime(trade['entry_time'])
                        exit = pd.to_datetime(trade['exit_time'])
                        duration = (exit - entry).total_seconds() / 3600  # 小时
                        holding_times.append(duration)
                    except:
                        continue
            
            avg_holding_time = np.mean(holding_times) if holding_times else 0
            
            # 连续盈亏分析
            consecutive_wins = self._calculate_consecutive_wins(profits)
            consecutive_losses = self._calculate_consecutive_losses(profits)
            
            # === 保留最新的成本分析（当前函数的修复） ===
            total_commission = sum(t.get('commission_costs', 0) for t in trades)
            total_funding = sum(t.get('funding_costs', 0) for t in trades)
            total_slippage = sum(t.get('slippage_costs', 0) for t in trades)
            total_costs = total_commission + total_funding + total_slippage
            
            avg_commission_per_trade = total_commission / len(trades) if len(trades) > 0 else 0
            avg_funding_per_trade = total_funding / len(trades) if len(trades) > 0 else 0
            avg_slippage_per_trade = total_slippage / len(trades) if len(trades) > 0 else 0
            
            # 成本占收益的比例
            gross_profit = sum(t.get('gross_profit', 0) for t in trades)
            cost_ratio = (total_costs / abs(gross_profit) * 100) if gross_profit != 0 else 0
            
            # === 保留最新的保证金使用统计（当前函数的修复） ===
            print(f"🔍 报告数据处理 - 保证金统计调试:")
            print(f"   总交易数: {len(trades)}")
            
            # 过滤有效的保证金数据
            valid_margin_trades = []
            invalid_margin_count = 0
            
            for i, trade in enumerate(trades):
                margin_ratio = trade.get('margin_ratio', -999)
                required_margin = trade.get('required_margin', -999)
                
                # 调试每笔交易的保证金数据
                if i < 5:  # 只显示前5笔的详细信息
                    print(f"   交易{i+1}: 保证金比例={margin_ratio:.2f}%, 保证金额={required_margin:.2f}")
                
                # 检查数据有效性
                if (margin_ratio >= 0 and margin_ratio <= 100 and  # 保证金比例在合理范围内
                    required_margin >= 0):  # 保证金金额非负
                    valid_margin_trades.append(trade)
                else:
                    invalid_margin_count += 1
                    if i < 5:  # 只显示前5笔的无效数据
                        print(f"   ❌ 交易{i+1} 数据无效: 比例={margin_ratio}, 金额={required_margin}")
            
            print(f"   有效保证金交易: {len(valid_margin_trades)}/{len(trades)}")
            print(f"   无效数据: {invalid_margin_count} 笔")
            
            if valid_margin_trades:
                # 提取有效数据
                margin_ratios = [t.get('margin_ratio', 0) for t in valid_margin_trades]
                leverages = [t.get('leverage', 1) for t in valid_margin_trades]
                position_values = [t.get('position_value', 0) for t in valid_margin_trades]
                required_margins = [t.get('required_margin', 0) for t in valid_margin_trades]
                
                # 基础统计
                avg_margin_ratio = np.mean(margin_ratios)
                max_margin_ratio = max(margin_ratios)
                min_margin_ratio = min(margin_ratios)
                avg_leverage = np.mean(leverages)
                max_leverage = max(leverages)
                total_position_value = sum(position_values)
                total_margin_used = sum(required_margins)
                
                # 分别统计盈利和亏损交易的保证金
                profitable_margin_trades = [t for t in valid_margin_trades if t.get('profit', 0) > 0]
                losing_margin_trades = [t for t in valid_margin_trades if t.get('profit', 0) <= 0]
                
                # 计算盈利和亏损交易的平均保证金占用
                if profitable_margin_trades:
                    profitable_margins = [t.get('margin_ratio', 0) for t in profitable_margin_trades]
                    avg_margin_profitable = np.mean(profitable_margins)
                else:
                    avg_margin_profitable = 0
                
                if losing_margin_trades:
                    losing_margins = [t.get('margin_ratio', 0) for t in losing_margin_trades]
                    avg_margin_losing = np.mean(losing_margins)
                else:
                    avg_margin_losing = 0
                
                print(f"   保证金统计结果:")
                print(f"     保证金比例范围: {min_margin_ratio:.1f}% - {max_margin_ratio:.1f}%")
                print(f"     平均保证金比例: {avg_margin_ratio:.1f}%")
                print(f"     盈利交易平均保证金: {avg_margin_profitable:.1f}%")
                print(f"     亏损交易平均保证金: {avg_margin_losing:.1f}%")
                print(f"     杠杆范围: {np.mean(leverages):.1f}x (最高: {max_leverage:.1f}x)")
                
            else:
                # 没有有效数据时的默认值
                avg_margin_ratio = max_margin_ratio = min_margin_ratio = 0
                avg_leverage = max_leverage = 1
                total_position_value = total_margin_used = 0
                avg_margin_profitable = avg_margin_losing = 0
                print(f"   ⚠️ 没有有效的保证金数据")
            
            # 部分平仓统计
            partial_closed_trades = [t for t in trades if t.get('partial_closed', False)]
            partial_close_count = len(partial_closed_trades)
            partial_close_rate = (partial_close_count / len(trades) * 100) if trades else 0
            
            # 计算增强交易信息（来自备份函数）
            enhanced_trades = self._enhance_trade_data(trades, initial_cash, config)
            
            # === 修复后的成本分析详细数据 ===
            cost_analysis = {
                'total_commission': total_commission,
                'total_funding': total_funding,
                'total_slippage': total_slippage,
                'total_costs': total_costs,
                'avg_commission_per_trade': avg_commission_per_trade,
                'avg_funding_per_trade': avg_funding_per_trade,
                'avg_slippage_per_trade': avg_slippage_per_trade,
                'cost_to_profit_ratio': cost_ratio,
                'commission_percentage': (total_commission / abs(gross_profit) * 100) if gross_profit != 0 else 0,
                'funding_percentage': (total_funding / abs(gross_profit) * 100) if gross_profit != 0 else 0,
                'slippage_percentage': (total_slippage / abs(gross_profit) * 100) if gross_profit != 0 else 0
            }
            
            # === 修复后的保证金分析详细数据 ===
            margin_analysis = {
                'avg_margin_ratio': avg_margin_ratio,
                'max_margin_ratio': max_margin_ratio,
                'min_margin_ratio': min_margin_ratio,
                'avg_leverage': avg_leverage,
                'max_leverage': max_leverage,
                'total_position_value': total_position_value,
                'total_margin_used': total_margin_used,
                'margin_efficiency': (total_position_value / total_margin_used) if total_margin_used > 0 else 0,
                'avg_margin_profitable_trades': avg_margin_profitable,
                'avg_margin_losing_trades': avg_margin_losing,
                'valid_margin_trades_count': len(valid_margin_trades),
                'valid_margin_trades_ratio': len(valid_margin_trades) / len(trades) * 100 if trades else 0,
                'invalid_margin_count': invalid_margin_count
            }
            
        else:
            # === 无交易时的完整默认值（合并两个函数的逻辑） ===
            win_rate = profit_factor = max_win = max_loss = 0
            avg_holding_time = consecutive_wins = consecutive_losses = 0
            partial_close_count = partial_close_rate = 0
            enhanced_trades = []
            
            # 完整的成本分析默认值
            cost_analysis = {
                'total_commission': 0,
                'total_funding': 0,
                'total_slippage': 0,
                'total_costs': 0,
                'avg_commission_per_trade': 0,
                'avg_funding_per_trade': 0,
                'avg_slippage_per_trade': 0,
                'cost_to_profit_ratio': 0,
                'commission_percentage': 0,
                'funding_percentage': 0,
                'slippage_percentage': 0
            }
            
            # 完整的保证金分析默认值
            margin_analysis = {
                'avg_margin_ratio': 0,
                'max_margin_ratio': 0,
                'min_margin_ratio': 0,
                'avg_leverage': 1,
                'max_leverage': 1,
                'total_position_value': 0,
                'total_margin_used': 0,
                'margin_efficiency': 0,
                'avg_margin_profitable_trades': 0,
                'avg_margin_losing_trades': 0,
                'valid_margin_trades_count': 0,
                'valid_margin_trades_ratio': 0,
                'invalid_margin_count': 0
            }
        
        # 最大回撤
        max_drawdown = results.get('max_drawdown', 0) * 100
        
        # 夏普比率（来自备份函数）
        sharpe_ratio = results.get('sharpe_ratio', 0)
        
        # 月度收益分析（来自备份函数）
        monthly_returns = self._calculate_enhanced_monthly_returns(enhanced_trades)
        
        # 信号质量统计（来自备份函数）
        signal_stats = results.get('signal_stats', {})
        signal_quality_stats = {
            'total_signals': signal_stats.get('total_signals', 0),
            'executed_signals': signal_stats.get('executed_signals', 0),
            'execution_rate': signal_stats.get('signal_execution_rate', 0),
            'trend_aligned_signals': signal_stats.get('trend_aligned_signals', 0),
            'high_quality_signals': signal_stats.get('high_quality_signals', 0),
            'signal_success_rate': signal_stats.get('signal_success_rate', 0),
            'avg_signal_strength': results.get('avg_signal_strength', 0),
            'avg_confidence_score': results.get('avg_confidence_score', 0),
            'trend_alignment_rate': results.get('trend_alignment_rate', 0)
        }
        
        return {
            'summary': {
                'initial_cash': initial_cash,
                'final_value': final_value,
                'total_return': total_return,
                'total_trades': len(trades),
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,           # 恢复
                'max_win': max_win,                     # 恢复
                'max_loss': max_loss,                   # 恢复
                'avg_holding_time': avg_holding_time,   # 恢复
                'max_consecutive_wins': consecutive_wins,    # 恢复
                'max_consecutive_losses': consecutive_losses, # 恢复
                'partial_close_count': partial_close_count,
                'partial_close_rate': partial_close_rate
            },
            'trades': enhanced_trades,              # 使用增强的交易数据
            'monthly_returns': monthly_returns,
            'cost_analysis': cost_analysis,        # 保留修复的成本分析
            'margin_analysis': margin_analysis,    # 保留修复的保证金分析
            'signal_quality_stats': signal_quality_stats,  # 恢复信号质量统计
            'config': config,
            'data_info': {
                'symbol': config.get('symbol', 'Unknown'),
                'interval': config.get('interval', 'Unknown'),
                'start_date': data['timestamp'].min().strftime('%Y-%m-%d') if 'timestamp' in data.columns else 'Unknown',
                'end_date': data['timestamp'].max().strftime('%Y-%m-%d') if 'timestamp' in data.columns else 'Unknown',
                'total_candles': len(data)
            }
        }




    def prepare_enhanced_backtest_data_back202505250908(self, data: pd.DataFrame, results: Dict[str, Any],
                                     config: Dict[str, Any]) -> Dict[str, Any]:
        """准备增强版回测数据 - 包含详细成本分析"""
        trades = results.get('trades', [])
        
        # 基本统计
        initial_cash = results.get('initial_cash', 20000)
        final_value = results.get('final_value', initial_cash)
        total_return = (final_value - initial_cash) / initial_cash * 100
        
        # === 增强统计计算 ===
        if trades:
            profits = [t.get('profit', 0) for t in trades]
            win_trades = [p for p in profits if p > 0]
            lose_trades = [p for p in profits if p < 0]
            
            win_rate = len(win_trades) / len(trades) * 100
            avg_win = np.mean(win_trades) if win_trades else 0
            avg_loss = abs(np.mean(lose_trades)) if lose_trades else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
            
            # 新增统计指标
            max_win = max(profits) if profits else 0
            max_loss = min(profits) if profits else 0
            
            # 平均持仓时间
            holding_times = []
            for trade in trades:
                if 'entry_time' in trade and 'exit_time' in trade:
                    try:
                        entry = pd.to_datetime(trade['entry_time'])
                        exit = pd.to_datetime(trade['exit_time'])
                        duration = (exit - entry).total_seconds() / 3600  # 小时
                        holding_times.append(duration)
                    except:
                        continue
            
            avg_holding_time = np.mean(holding_times) if holding_times else 0
            
            # 连续盈亏分析
            consecutive_wins = self._calculate_consecutive_wins(profits)
            consecutive_losses = self._calculate_consecutive_losses(profits)
            
            # === 新增：详细成本分析 ===
            cost_analysis = self._calculate_detailed_costs(trades)
            
            # === 新增：保证金使用分析 ===
            margin_analysis = self._calculate_margin_analysis(trades, initial_cash, config)
            
            # 计算增强交易信息
            enhanced_trades = self._enhance_trade_data(trades, initial_cash, config)
            
        else:
            win_rate = profit_factor = max_win = max_loss = 0
            avg_holding_time = consecutive_wins = consecutive_losses = 0
            cost_analysis = margin_analysis = {}
            enhanced_trades = []
        
        # 最大回撤
        max_drawdown = results.get('max_drawdown', 0) * 100
        
        # 夏普比率
        sharpe_ratio = results.get('sharpe_ratio', 0)
        
        # 月度收益分析
        monthly_returns = self._calculate_enhanced_monthly_returns(enhanced_trades)
        
        # 信号质量统计
        signal_stats = results.get('signal_stats', {})
        signal_quality_stats = {
            'total_signals': signal_stats.get('total_signals', 0),
            'executed_signals': signal_stats.get('executed_signals', 0),
            'execution_rate': signal_stats.get('signal_execution_rate', 0),
            'trend_aligned_signals': signal_stats.get('trend_aligned_signals', 0),
            'high_quality_signals': signal_stats.get('high_quality_signals', 0),
            'signal_success_rate': signal_stats.get('signal_success_rate', 0),
            'avg_signal_strength': results.get('avg_signal_strength', 0),
            'avg_confidence_score': results.get('avg_confidence_score', 0),
            'trend_alignment_rate': results.get('trend_alignment_rate', 0)
        }
        
        return {
            'summary': {
                'initial_cash': initial_cash,
                'final_value': final_value,
                'total_return': total_return,
                'total_trades': len(trades),
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'max_win': max_win,
                'max_loss': max_loss,
                'avg_holding_time': avg_holding_time,
                'max_consecutive_wins': consecutive_wins,
                'max_consecutive_losses': consecutive_losses
            },
            'trades': enhanced_trades,
            'monthly_returns': monthly_returns,
            'cost_analysis': cost_analysis,          # 新增：成本分析
            'margin_analysis': margin_analysis,      # 新增：保证金分析
            'signal_quality_stats': signal_quality_stats,
            'config': config,
            'data_info': {
                'symbol': config.get('symbol', 'Unknown'),
                'interval': config.get('interval', 'Unknown'),
                'start_date': data['timestamp'].min().strftime('%Y-%m-%d') if 'timestamp' in data.columns else 'Unknown',
                'end_date': data['timestamp'].max().strftime('%Y-%m-%d') if 'timestamp' in data.columns else 'Unknown',
                'total_candles': len(data)
            }
        }

    def _calculate_detailed_costs(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算详细的交易成本分析"""
        if not trades:
            return {
                'total_commission': 0,
                'total_funding': 0,
                'total_slippage': 0,
                'total_costs': 0,
                'avg_commission_per_trade': 0,
                'avg_funding_per_trade': 0,
                'avg_slippage_per_trade': 0,
                'commission_percentage': 0,
                'funding_percentage': 0,
                'cost_to_profit_ratio': 0
            }
        
        # 累计各项成本
        total_commission = sum(t.get('commission_costs', 0) for t in trades)
        total_funding = sum(t.get('funding_costs', 0) for t in trades)
        total_slippage = sum(t.get('slippage_costs', 0) for t in trades)
        total_costs = total_commission + total_funding + total_slippage
        
        # 平均成本
        avg_commission_per_trade = total_commission / len(trades)
        avg_funding_per_trade = total_funding / len(trades)
        avg_slippage_per_trade = total_slippage / len(trades)
        
        # 计算成本占收益的比例
        gross_profit = sum(t.get('gross_profit', t.get('profit', 0)) for t in trades)
        total_profit = sum(t.get('profit', 0) for t in trades)
        
        # 成本占比计算（避免除零）
        if abs(gross_profit) > 0:
            commission_percentage = (total_commission / abs(gross_profit)) * 100
            funding_percentage = (total_funding / abs(gross_profit)) * 100
            cost_to_profit_ratio = (total_costs / abs(gross_profit)) * 100
        else:
            commission_percentage = funding_percentage = cost_to_profit_ratio = 0
        
        # 成本效率分析
        profitable_trades = [t for t in trades if t.get('profit', 0) > 0]
        losing_trades = [t for t in trades if t.get('profit', 0) < 0]
        
        avg_cost_profitable = np.mean([
            t.get('commission_costs', 0) + t.get('funding_costs', 0) + t.get('slippage_costs', 0)
            for t in profitable_trades
        ]) if profitable_trades else 0
        
        avg_cost_losing = np.mean([
            t.get('commission_costs', 0) + t.get('funding_costs', 0) + t.get('slippage_costs', 0)
            for t in losing_trades
        ]) if losing_trades else 0
        
        return {
            'total_commission': total_commission,
            'total_funding': total_funding,
            'total_slippage': total_slippage,
            'total_costs': total_costs,
            'avg_commission_per_trade': avg_commission_per_trade,
            'avg_funding_per_trade': avg_funding_per_trade,
            'avg_slippage_per_trade': avg_slippage_per_trade,
            'commission_percentage': commission_percentage,
            'funding_percentage': funding_percentage,
            'cost_to_profit_ratio': cost_to_profit_ratio,
            'avg_cost_profitable_trades': avg_cost_profitable,
            'avg_cost_losing_trades': avg_cost_losing,
            'cost_efficiency': (avg_cost_losing / avg_cost_profitable) if avg_cost_profitable > 0 else 0
        }
    def _calculate_margin_analysis(self, trades: List[Dict[str, Any]],
                                initial_cash: float, config: Dict[str, Any]) -> Dict[str, Any]:
        """计算保证金使用分析 - 修复版"""
        if not trades:
            return {
                'avg_margin_ratio': 0,
                'max_margin_ratio': 0,
                'min_margin_ratio': 0,
                'avg_leverage': 1,
                'max_leverage': 1,
                'total_position_value': 0,
                'total_margin_used': 0,
                'margin_efficiency': 0,
                'leverage_distribution': {},
                'avg_margin_profitable_trades': 0,
                'avg_margin_losing_trades': 0,
                'margin_usage_efficiency': 0,
                'valid_trades_count': 0,
                'invalid_trades_count': 0,
                'data_quality_score': 0
            }

        print(f"🔍 保证金分析调试 - 开始处理 {len(trades)} 笔交易")

        # ✅ 修复：添加数据验证和过滤
        valid_trades = []
        invalid_count = 0
        
        for i, trade in enumerate(trades):
            # 获取原始数据
            margin_ratio = trade.get('margin_ratio', -999)
            required_margin = trade.get('required_margin', -999)
            leverage = trade.get('leverage', config.get('leverage', 1))
            position_value = trade.get('position_value', 0)
            
            # ✅ 数据有效性检查
            is_valid = True
            issues = []
            
            # 检查保证金比例
            if margin_ratio < 0 or margin_ratio > 100:
                is_valid = False
                issues.append(f"保证金比例异常: {margin_ratio:.2f}%")
            
            # 检查保证金金额
            if required_margin < 0:
                is_valid = False
                issues.append(f"保证金金额异常: {required_margin:.2f}")
            
            # 检查杠杆
            if leverage <= 0 or leverage > 100:
                is_valid = False
                issues.append(f"杠杆异常: {leverage}")
            
            # 检查仓位价值
            if position_value <= 0:
                is_valid = False
                issues.append(f"仓位价值异常: {position_value}")
            
            # ✅ 逻辑一致性检查
            if is_valid and required_margin > 0 and position_value > 0 and leverage > 0:
                # 验证 保证金 = 仓位价值 / 杠杆
                expected_margin = position_value / leverage
                margin_diff = abs(expected_margin - required_margin)
                margin_diff_pct = margin_diff / expected_margin * 100 if expected_margin > 0 else 0
                
                if margin_diff_pct > 5:  # 允许5%的误差
                    is_valid = False
                    issues.append(f"保证金计算不一致: 期望{expected_margin:.2f}, 实际{required_margin:.2f}")
            
            if is_valid:
                valid_trades.append(trade)
            else:
                invalid_count += 1
                if i < 5:  # 只显示前5笔异常数据的详情
                    print(f"   ❌ 交易{i+1} 数据异常: {', '.join(issues)}")

        print(f"   ✅ 有效交易: {len(valid_trades)}/{len(trades)} ({len(valid_trades)/len(trades)*100:.1f}%)")
        print(f"   ❌ 异常交易: {invalid_count}")

        if not valid_trades:
            print(f"   ⚠️ 没有有效的保证金数据！")
            return {
                'avg_margin_ratio': 0,
                'max_margin_ratio': 0,
                'min_margin_ratio': 0,
                'avg_leverage': 1,
                'max_leverage': 1,
                'total_position_value': 0,
                'total_margin_used': 0,
                'margin_efficiency': 0,
                'leverage_distribution': {},
                'avg_margin_profitable_trades': 0,
                'avg_margin_losing_trades': 0,
                'margin_usage_efficiency': 0,
                'valid_trades_count': 0,
                'invalid_trades_count': invalid_count,
                'data_quality_score': 0
            }

        # ✅ 修复：使用验证后的数据进行计算
        margin_ratios = []
        leverages = []
        position_values = []
        margin_amounts = []

        for trade in valid_trades:
            # 保证金占用比例
            margin_ratio = trade.get('margin_ratio', 0)
            margin_ratios.append(margin_ratio)
            
            # 杠杆
            leverage = trade.get('leverage', config.get('leverage', 1))
            leverages.append(leverage)
            
            # 仓位价值
            position_value = trade.get('position_value', 0)
            position_values.append(position_value)
            
            # 保证金金额 - 优先使用记录值，否则计算
            margin_amount = trade.get('required_margin')
            if margin_amount is None or margin_amount < 0:
                margin_amount = position_value / leverage if leverage > 0 else position_value
            margin_amounts.append(margin_amount)

        # ✅ 统计计算 - 添加安全检查
        if margin_ratios:
            avg_margin_ratio = np.mean(margin_ratios)
            max_margin_ratio = max(margin_ratios)
            min_margin_ratio = min(margin_ratios)
        else:
            avg_margin_ratio = max_margin_ratio = min_margin_ratio = 0

        if leverages:
            avg_leverage = np.mean(leverages)
            max_leverage = max(leverages)
        else:
            avg_leverage = max_leverage = 1

        total_position_value = sum(position_values)
        total_margin_used = sum(margin_amounts)

        # 保证金效率 = 总仓位价值 / 总保证金占用
        margin_efficiency = (total_position_value / total_margin_used) if total_margin_used > 0 else 0

        # ✅ 杠杆分布统计
        leverage_distribution = {}
        for lev in leverages:
            lev_str = f"{int(lev)}x"
            leverage_distribution[lev_str] = leverage_distribution.get(lev_str, 0) + 1

        # ✅ 修复：保证金使用效率分析 - 基于有效数据
        profitable_trades = [t for t in valid_trades if t.get('profit', 0) > 0]
        losing_trades = [t for t in valid_trades if t.get('profit', 0) < 0]

        if profitable_trades:
            profitable_margin_ratios = [t.get('margin_ratio', 0) for t in profitable_trades]
            avg_margin_profitable = np.mean(profitable_margin_ratios)
        else:
            avg_margin_profitable = 0

        if losing_trades:
            losing_margin_ratios = [t.get('margin_ratio', 0) for t in losing_trades]
            avg_margin_losing = np.mean(losing_margin_ratios)
        else:
            avg_margin_losing = 0

        # ✅ 计算数据质量分数
        data_quality_score = len(valid_trades) / len(trades) * 100 if trades else 0

        # ✅ 输出统计结果
        print(f"   📊 保证金统计结果:")
        print(f"     平均保证金占用: {avg_margin_ratio:.1f}% (范围: {min_margin_ratio:.1f}% - {max_margin_ratio:.1f}%)")
        print(f"     平均杠杆: {avg_leverage:.1f}x (最高: {max_leverage:.1f}x)")
        print(f"     总仓位价值: {total_position_value:,.0f} USDT")
        print(f"     总保证金使用: {total_margin_used:,.0f} USDT")
        print(f"     保证金效率: {margin_efficiency:.1f}")
        print(f"     盈利交易平均保证金: {avg_margin_profitable:.1f}%")
        print(f"     亏损交易平均保证金: {avg_margin_losing:.1f}%")
        print(f"     数据质量分数: {data_quality_score:.1f}%")

        return {
            'avg_margin_ratio': avg_margin_ratio,
            'max_margin_ratio': max_margin_ratio,
            'min_margin_ratio': min_margin_ratio,
            'avg_leverage': avg_leverage,
            'max_leverage': max_leverage,
            'total_position_value': total_position_value,
            'total_margin_used': total_margin_used,
            'margin_efficiency': margin_efficiency,
            'leverage_distribution': leverage_distribution,
            'avg_margin_profitable_trades': avg_margin_profitable,
            'avg_margin_losing_trades': avg_margin_losing,
            'margin_usage_efficiency': (avg_margin_losing / avg_margin_profitable) if avg_margin_profitable > 0 else 0,
            # ✅ 新增字段
            'valid_trades_count': len(valid_trades),
            'invalid_trades_count': invalid_count,
            'data_quality_score': data_quality_score,
            'margin_ratio_std': np.std(margin_ratios) if margin_ratios else 0,  # 保证金占用标准差
            'leverage_std': np.std(leverages) if leverages else 0  # 杠杆标准差
        }
   
    def _enhance_trade_data(self, trades: List[Dict[str, Any]], 
                          initial_cash: float, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """增强交易数据，添加缺失的成本和保证金信息"""
        enhanced_trades = []
        
        for i, trade in enumerate(trades):
            enhanced_trade = trade.copy()
            
            # === 基础数据补全 ===
            entry_price = trade.get('entry_price', trade.get('actual_entry_price', 0))
            exit_price = trade.get('exit_price', 0)
            size = trade.get('size', 0)
            leverage = trade.get('leverage', config.get('leverage', 1))
            
            # === 计算仓位和保证金信息 ===
            position_value = entry_price * size
            required_margin = position_value / leverage if leverage > 0 else position_value
            margin_ratio = (required_margin / initial_cash) * 100 if initial_cash > 0 else 0
            
            # === 补全缺失的保证金信息 ===
            if 'position_value' not in enhanced_trade:
                enhanced_trade['position_value'] = position_value
            if 'required_margin' not in enhanced_trade:
                enhanced_trade['required_margin'] = required_margin
            if 'margin_ratio' not in enhanced_trade:
                enhanced_trade['margin_ratio'] = margin_ratio
            
            # === 计算详细的交易成本 ===
            # 1. 手续费成本（如果没有，则按标准费率计算）
            if 'commission_costs' not in enhanced_trade:
                commission_rate = 0.0005  # 0.05%
                open_commission = position_value * commission_rate
                close_commission = (exit_price * size) * commission_rate if exit_price > 0 else 0
                enhanced_trade['commission_costs'] = open_commission + close_commission
            
            # 2. 资金费率成本（如果没有，则根据持仓时间估算）
            if 'funding_costs' not in enhanced_trade:
                funding_rate_per_8h = 0.0001  # 0.01% per 8 hours
                if 'entry_time' in trade and 'exit_time' in trade:
                    try:
                        entry_time = pd.to_datetime(trade['entry_time'])
                        exit_time = pd.to_datetime(trade['exit_time'])
                        holding_hours = (exit_time - entry_time).total_seconds() / 3600
                        funding_periods = max(1, holding_hours / 8)  # 按8小时计费
                        enhanced_trade['funding_costs'] = position_value * funding_rate_per_8h * funding_periods
                    except:
                        enhanced_trade['funding_costs'] = position_value * funding_rate_per_8h
                else:
                    enhanced_trade['funding_costs'] = 0
            
            # 3. 滑点成本（如果没有，则按标准滑点计算）
            if 'slippage_costs' not in enhanced_trade:
                slippage_rate = 0.0002  # 0.02%
                slippage_open = position_value * slippage_rate
                slippage_close = (exit_price * size) * slippage_rate if exit_price > 0 else 0
                enhanced_trade['slippage_costs'] = slippage_open + slippage_close
            
            # === 计算总成本 ===
            total_costs = (enhanced_trade.get('commission_costs', 0) + 
                          enhanced_trade.get('funding_costs', 0) + 
                          enhanced_trade.get('slippage_costs', 0))
            enhanced_trade['total_costs'] = total_costs
            
            # === 计算毛利润和净利润 ===
            if 'gross_profit' not in enhanced_trade:
                if direction := trade.get('direction'):
                    if direction == 'buy':
                        enhanced_trade['gross_profit'] = (exit_price - entry_price) * size
                    else:
                        enhanced_trade['gross_profit'] = (entry_price - exit_price) * size
                else:
                    enhanced_trade['gross_profit'] = enhanced_trade.get('profit', 0) + total_costs
            
            # 确保净利润正确
            enhanced_trade['net_profit'] = enhanced_trade.get('profit', 0)
            
            # === 添加成本效率指标 ===
            gross_profit = enhanced_trade.get('gross_profit', 0)
            if abs(gross_profit) > 0:
                enhanced_trade['cost_ratio'] = (total_costs / abs(gross_profit)) * 100
            else:
                enhanced_trade['cost_ratio'] = 0
            
            # === 添加保证金效率指标 ===
            if required_margin > 0:
                enhanced_trade['return_on_margin'] = (enhanced_trade.get('profit', 0) / required_margin) * 100
            else:
                enhanced_trade['return_on_margin'] = 0
            
            enhanced_trades.append(enhanced_trade)
        
        return enhanced_trades

    def prepare_multi_symbol_data(self, multi_results: Dict[str, Dict], 
                                config: Dict[str, Any]) -> Dict[str, Any]:
        """准备多币种数据"""
        symbol_stats = []
        total_trades = 0
        total_signals = 0
        
        # 处理每个币种的数据
        for symbol, data in multi_results.items():
            results = data['results']
            
            # 信号质量统计
            signal_stats = results.get('signal_stats', {})
            
            symbol_stat = {
                'symbol': symbol,
                'interval': data['interval'],
                'initial_cash': results['initial_cash'],
                'final_value': results['final_value'],
                'total_return': results['total_return'],
                'total_trades': results['total_trades'],
                'win_rate': results['win_rate'],
                'profit_factor': results['profit_factor'],
                'max_drawdown': results['max_drawdown'] * 100,
                'sharpe_ratio': results.get('sharpe_ratio', 0.0),
                'avg_leverage': results.get('avg_leverage', 1),
                # 信号质量信息
                'total_signals': signal_stats.get('total_signals', 0),
                'executed_signals': signal_stats.get('executed_signals', 0),
                'signal_execution_rate': signal_stats.get('signal_execution_rate', 0),
                'signal_success_rate': signal_stats.get('signal_success_rate', 0),
                'avg_signal_strength': results.get('avg_signal_strength', 0),
                'avg_confidence_score': results.get('avg_confidence_score', 0),
                'trend_alignment_rate': results.get('trend_alignment_rate', 0)
            }
            
            symbol_stats.append(symbol_stat)
            total_trades += results['total_trades']
            total_signals += signal_stats.get('total_signals', 0)
        
        # 计算汇总统计
        total_initial = sum(s['initial_cash'] for s in symbol_stats)
        total_final = sum(s['final_value'] for s in symbol_stats)
        total_return = (total_final - total_initial) / total_initial * 100 if total_initial > 0 else 0
        
        avg_win_rate = np.mean([s['win_rate'] for s in symbol_stats if s['total_trades'] > 0])
        avg_signal_execution_rate = np.mean([s['signal_execution_rate'] for s in symbol_stats if s['total_signals'] > 0])
        avg_signal_success_rate = np.mean([s['signal_success_rate'] for s in symbol_stats if s['executed_signals'] > 0])
        
        # 按收益率排序
        symbol_stats.sort(key=lambda x: x['total_return'], reverse=True)
        
        return {
            'symbol_stats': symbol_stats,
            'summary': {
                'total_symbols': len(symbol_stats),
                'total_initial_cash': total_initial,
                'total_final_value': total_final,
                'total_return': total_return,
                'total_trades': total_trades,
                'total_signals': total_signals,
                'avg_win_rate': avg_win_rate,
                'avg_signal_execution_rate': avg_signal_execution_rate,
                'avg_signal_success_rate': avg_signal_success_rate,
                'best_symbol': symbol_stats[0]['symbol'] if symbol_stats else 'None',
                'best_return': symbol_stats[0]['total_return'] if symbol_stats else 0,
                'worst_symbol': symbol_stats[-1]['symbol'] if symbol_stats else 'None',
                'worst_return': symbol_stats[-1]['total_return'] if symbol_stats else 0
            },
            'config': config
        }
    
    def _calculate_consecutive_wins(self, profits: List[float]) -> int:
        """计算最大连续盈利次数"""
        max_consecutive = 0
        current_consecutive = 0
        
        for profit in profits:
            if profit > 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_consecutive_losses(self, profits: List[float]) -> int:
        """计算最大连续亏损次数"""
        max_consecutive = 0
        current_consecutive = 0
        
        for profit in profits:
            if profit < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_enhanced_monthly_returns(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """计算增强版月度收益"""
        if not trades:
            return []
        
        monthly_data = {}
        
        for trade in trades:
            if 'exit_time' in trade and 'profit' in trade:
                try:
                    if isinstance(trade['exit_time'], str):
                        exit_time = pd.to_datetime(trade['exit_time'])
                    else:
                        exit_time = trade['exit_time']
                    
                    month_key = exit_time.strftime('%Y-%m')
                    
                    if month_key not in monthly_data:
                        monthly_data[month_key] = {
                            'profit': 0,
                            'trades': 0,
                            'wins': 0,
                            'losses': 0,
                            'total_costs': 0,
                            'total_commission': 0,
                            'total_funding': 0
                        }
                    
                    monthly_data[month_key]['profit'] += trade['profit']
                    monthly_data[month_key]['trades'] += 1
                    monthly_data[month_key]['total_costs'] += trade.get('total_costs', 0)
                    monthly_data[month_key]['total_commission'] += trade.get('commission_costs', 0)
                    monthly_data[month_key]['total_funding'] += trade.get('funding_costs', 0)
                    
                    if trade['profit'] > 0:
                        monthly_data[month_key]['wins'] += 1
                    else:
                        monthly_data[month_key]['losses'] += 1
                        
                except:
                    continue
        
        # 转换为列表格式
        monthly_returns = []
        for month, data in sorted(monthly_data.items()):
            win_rate = data['wins'] / data['trades'] * 100 if data['trades'] > 0 else 0
            monthly_returns.append({
                'month': month,
                'profit': data['profit'],
                'return_pct': data['profit'] / 20000 * 100,  # 假设基准资金
                'trades': data['trades'],
                'win_rate': win_rate,
                'wins': data['wins'],
                'losses': data['losses'],
                'total_costs': data['total_costs'],
                'total_commission': data['total_commission'],
                'total_funding': data['total_funding'],
                'cost_ratio': (data['total_costs'] / abs(data['profit']) * 100) if data['profit'] != 0 else 0
            })
        
        return monthly_returns