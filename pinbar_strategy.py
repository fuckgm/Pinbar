#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
博大行情版Pinbar策略 - 小仓位高杠杆博大利润
专注捕获大趋势，合理运用杠杆，严格风险控制
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
from trend_tracker import TrendTracker, TrendInfo, TrendDirection, TrendStrength

class SupportResistanceFinder:
    """支撑阻力位识别器 - 博大行情版"""
    
    def __init__(self):
        # 支撑阻力位识别器参数调整
        self.swing_period = 8               # 从12降到8
        self.min_touches = 2
        self.price_tolerance = 0.005        # 从0.003放宽到0.005
        self.lookback_period = 60           # 从80降到60
        self.time_decay_factor = 0.02       # 从0.015调到0.02
        
    def find_key_levels(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """识别关键支撑阻力位 - 重点识别重要突破位"""
        if len(data) < self.lookback_period:
            return []
        
        levels = []
        recent_data = data.tail(self.lookback_period).copy()
        
        swing_highs = self._find_swing_points(recent_data, 'high')
        swing_lows = self._find_swing_points(recent_data, 'low')
        
        # 只保留最重要的关键位，但降低强度要求
        for price, idx in swing_highs:
            strength = self._calculate_level_strength(recent_data, price, idx, 'resistance')
            if strength > 1.5:  # 从2.5降到1.5
                levels.append({
                    'price': price,
                    'type': 'resistance', 
                    'strength': strength,
                    'age': len(recent_data) - idx
                })
        
        for price, idx in swing_lows:
            strength = self._calculate_level_strength(recent_data, price, idx, 'support')
            if strength > 1.5:  # 从2.5降到1.5
                levels.append({
                    'price': price,
                    'type': 'support',
                    'strength': strength, 
                    'age': len(recent_data) - idx
                })
        
        return sorted(levels, key=lambda x: x['strength'], reverse=True)[:12]  # 从8个增加到12个
    
    def _find_swing_points(self, data: pd.DataFrame, column: str) -> List[Tuple[float, int]]:
        """识别摆动高低点"""
        points = []
        for i in range(self.swing_period, len(data) - self.swing_period):
            current_price = data[column].iloc[i]
            
            if column == 'high':
                is_peak = True
                for j in range(i - self.swing_period, i + self.swing_period + 1):
                    if j != i and data[column].iloc[j] >= current_price:
                        is_peak = False
                        break
                if is_peak:
                    points.append((current_price, i))
            else:
                is_valley = True
                for j in range(i - self.swing_period, i + self.swing_period + 1):
                    if j != i and data[column].iloc[j] <= current_price:
                        is_valley = False
                        break
                if is_valley:
                    points.append((current_price, i))
        
        return points
    
    def _calculate_level_strength(self, data: pd.DataFrame, price: float, 
                                original_idx: int, level_type: str) -> float:
        """计算关键位强度"""
        touches = 0
        volume_weight = 0
        
        for i, row in data.iterrows():
            if level_type == 'resistance':
                if abs(row['high'] - price) / price <= self.price_tolerance:
                    touches += 1
                    volume_weight += row.get('volume', 1)
            else:
                if abs(row['low'] - price) / price <= self.price_tolerance:
                    touches += 1
                    volume_weight += row.get('volume', 1)
        
        age = len(data) - original_idx
        time_factor = max(0.2, 1 - age * self.time_decay_factor)
        strength = touches * (1 + volume_weight / 1000000) * time_factor
        return strength
    
    def is_near_key_level(self, price: float, key_levels: List[Dict]) -> Tuple[bool, float]:
        """检查价格是否接近关键位"""
        for level in key_levels:
            distance = abs(price - level['price']) / level['price']
            if distance <= self.price_tolerance:
                return True, level['strength']
        return False, 0.0

class EnhancedPinbarStrategy(bt.Strategy):
    """
    博大行情版Pinbar策略 - 小仓位高杠杆博大利润
    
    核心特点：
    1. 小仓位博大利润，承受较大回调
    2. 合理运用杠杆，多币种时留足保证金
    3. 最多4个币种同时持仓
    4. 给大行情足够的发展空间
    """
    
    def __init__(self, trading_params: TradingParams, 
                 detector_config: Dict[str, Any] = None,
                 use_dynamic_leverage: bool = True):
        
        print("🚀 初始化博大行情版Pinbar策略...")
        
        # 基础参数
        self.trading_params = trading_params
        
        # === 博大行情核心参数 ===
        self.max_positions = 4                   # 最多4个币种
        self.max_single_risk = 0.015            # 单笔风险1.5%（小仓位）
        self.max_single_margin = 0.12           # 单币种最大保证金12%
        self.max_total_margin = 0.50            # 总保证金不超过50%
        self.margin_buffer_ratio = 0.30         # 保证金缓冲30%
        
        # === 杠杆策略 ===
        self.base_leverage = 3
        self.max_leverage = 8
        self.leverage_by_positions = {1: 8, 2: 5, 3: 3, 4: 2}  # 根据持仓数量调整杠杆
        
        # === 博大行情管理 ===
        self.profit_protection_trigger = 0.05   # 5%利润时保护
        self.partial_close_ratio = 0.30         # 平仓30%，保留70%博大行情
        self.big_move_thresholds = [0.08, 0.15, 0.35]  # 8%, 15%, 35%利润阶段（降低门槛）
        self.trailing_distances = [0.04, 0.06, 0.10]   # 对应的追踪距离（收紧一些）
        
        # === 智能持仓控制 ===
        self.min_holding_bars = 5               # 最少持仓3根K线
        self.max_holding_bars = 50              # 最多持仓50根K线
        self.consolidation_exit_bars = 8        # 盘整区间8根K线后考虑退出
        self.breakout_threshold = 0.015         # 突破盘整区间的阈值1.5%
        
        # === 方向记忆系统 ===
        self.direction_memory = {}              # 记录失败方向
        self.memory_decay_bars = 20             # 记忆衰减周期
        self.direction_bias_strength = 0.3      # 方向偏好强度
        self.recent_failures = []               # 最近失败记录
        
        # === 动态持仓判断 ===
        self.volatility_factor = 1.0            # 波动率因子
        self.trend_strength_threshold = 0.6     # 趋势强度门槛
        self.consolidation_range_pct = 0.02     # 盘整区间判断2%
        
        # === 交易成本简化 ===
        self.unified_cost_rate = 0.001          # 统一成本0.1%
        self.slippage_rate = 0.0005             # 滑点0.05%
        
        print(f"✅ 博大行情参数设置:")
        print(f"   - 最大持仓: {self.max_positions}个币种")
        print(f"   - 单笔风险: {self.max_single_risk*100:.1f}%")
        print(f"   - 杠杆策略: 1仓{self.leverage_by_positions[1]}x, 4仓{self.leverage_by_positions[4]}x")
        print(f"   - 利润保护: {self.profit_protection_trigger*100:.0f}%时平仓{self.partial_close_ratio*100:.0f}%")
        print(f"   - 最大浮亏: {self.max_floating_loss*100:.0f}%")
        print(f"   - 最少持仓: {self.min_holding_bars}根K线")
        print(f"   - 盘整阈值: {self.consolidation_range_pct*100:.1f}%")
        
        # 初始化组件
        self.sr_finder = SupportResistanceFinder()
        
        # 趋势跟踪器（简化版）
        trend_config = self._get_trend_config()
        self.trend_tracker = TrendTracker(trend_config)
        
        # 信号检测器（高质量配置）
        detector_config = detector_config or self._get_high_quality_detector_config()
        self.pinbar_detector = EnhancedPinbarDetector(detector_config)
        
        # 计算最小所需K线数量（减少）
        self.min_required_bars = 50
        
        # 交易状态管理
        self.active_trades = {}
        self.trade_counter = 0
        self.trade_history = []
        
        # 风险监控
        self.current_floating_loss = 0.0
        self.max_drawdown_seen = 0.0
        self.trading_paused = False
        self.pause_reason = ""
        
        # 信号统计
        self.signal_stats = {
            'total_signals': 0,
            'executed_signals': 0,
            'successful_signals': 0,
            'signal_success_rate': 0.0,
            'big_move_signals': 0,  # 大行情信号数
            'big_move_success': 0   # 大行情成功数
        }
        
        # 统计信息
        self.account_initial = self.broker.getcash()
        self.account_peak = self.account_initial
        self.max_dd = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profits = 0.0
        self.total_losses = 0.0
        
        # 数据缓存
        self.data_cache = []
        self.key_levels = []
        self.last_key_levels_update = 0
        self.current_trend_info = None
        
        print(f"✅ 博大行情版策略初始化完成")

    def _get_trend_config(self) -> Dict[str, Any]:
        """获取趋势跟踪配置 - 简化版"""
        return {
            'fast_ma_period': 8,
            'slow_ma_period': 21,
            'trend_ma_period': 50,
            'adx_period': 14,
            'weak_adx': 20,
            'moderate_adx': 30,      # 提高阈值，识别真正的强趋势
            'strong_adx': 40,
            'extreme_adx': 60,
            'volume_surge_threshold': 1.5,
            'breakout_threshold': 0.02,
            'atr_expansion_threshold': 1.3
        }

    def _get_high_quality_detector_config(self) -> Dict[str, Any]:
        """获取高质量信号检测配置 - 博大行情版（调整后的宽松版）"""
        return {
            # === Pinbar形态参数（适度放宽）===
            'min_shadow_body_ratio': 2.0,      # 从2.8降到2.0
            'max_body_ratio': 0.30,            # 从0.20放宽到0.30
            'min_candle_size': 0.005,          # 从0.008降到0.005
            'max_opposite_shadow_ratio': 0.40, # 从0.30放宽到0.40
            
            # === 确认机制（简化）===
            'require_confirmation': False,      # 暂时关闭确认机制
            'confirmation_strength': 0.3,      # 降低确认强度
            
            # === 技术指标（大幅放宽）===
            'min_signal_score': 2.5,          # 从4.5大幅降到2.5
            'rsi_oversold': 35,                # 从30放宽到35
            'rsi_overbought': 65,              # 从70收紧到65
            'volume_threshold': 1.2,           # 从1.6降到1.2
            'level_proximity': 0.008,          # 从0.004放宽到0.008
            'adx_threshold': 15,               # 从25降到15
            'atr_percentile': 25,              # 从35降到25
            
            # 其他参数（放宽）
            'trend_period': 20,
            'rsi_period': 14,
            'bb_period': 20,
            'sr_lookback': 40,                 # 从50降到40
            'adx_period': 14,
            'atr_period': 14,
            'volume_ma_period': 15,            # 从20降到15
            'volume_threshold_ratio': 1.1,     # 从1.2降到1.1
            'min_consolidation_bars': 8,       # 从12降到8
            'large_move_threshold': 0.03,      # 从0.05降到0.03
            'large_move_exclude_bars': 3       # 从5降到3
        }

    def prenext(self):
        """数据不足时调用"""
        self._update_data_cache()

    def next(self):
        """主交易逻辑 - 博大行情版"""
        # 1. 更新数据缓存
        self._update_data_cache()
        
        # 2. 检查数据是否充足
        if len(self.data_cache) < self.min_required_bars:
            return
        
        # 3. 更新趋势信息（每10根K线更新一次）
        if len(self.data_cache) % 10 == 0:
            self._update_trend_info()
        
        # 3. 更新关键位（每15根K线更新一次，从20降到15）
        if len(self.data_cache) - self.last_key_levels_update >= 15:
            self._update_key_levels()
        
        # 5. 风险监控和保证金检查
        if self._check_risk_controls():
            return
        
        # 6. 管理现有持仓（博大行情版）
        self._manage_big_move_positions()
        
        # 7. 检查新信号（如果没有暂停且有位置）
        if not self.trading_paused and len(self.active_trades) < self.max_positions:
            self._check_for_big_move_signals()
        
        # 8. 更新账户统计
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
        
        # 保留最近600根K线
        if len(self.data_cache) > 600:
            self.data_cache.pop(0)

    def _update_trend_info(self):
        """更新趋势信息"""
        try:
            df = pd.DataFrame(self.data_cache)
            self.current_trend_info = self.trend_tracker.analyze_trend(df)
        except Exception as e:
            print(f"❌ 趋势分析失败: {e}")

    def _update_key_levels(self):
        """更新关键支撑阻力位"""
        try:
            df = pd.DataFrame(self.data_cache)
            self.key_levels = self.sr_finder.find_key_levels(df)
            self.last_key_levels_update = len(self.data_cache)
            
            if self.key_levels:
                print(f"🎯 更新关键位: {len(self.key_levels)} 个")
        except Exception as e:
            print(f"❌ 更新关键位失败: {e}")

    def _check_risk_controls(self) -> bool:
        """风险控制检查 - 博大行情版"""
        current_value = self.broker.getvalue()
        current_cash = self.broker.getcash()
        
        # 1. 计算浮动损益
        self.current_floating_loss = self._calculate_floating_loss()
        
        # 2. 计算当前保证金使用率
        margin_usage = self._calculate_margin_usage()
        
        # 3. 浮亏控制
        if self.current_floating_loss > self.max_floating_loss:
            if not self.trading_paused:
                print(f"🚨 浮亏达到{self.current_floating_loss*100:.1f}%，暂停新开仓")
                self.trading_paused = True
                self.pause_reason = f"浮亏过大({self.current_floating_loss*100:.1f}%)"
            
            # 浮亏过大时考虑减仓
            if self.current_floating_loss > self.emergency_stop_loss:
                print(f"🚨 紧急止损！浮亏达到{self.current_floating_loss*100:.1f}%")
                self._emergency_reduce_positions()
                
        # 4. 保证金预警
        if margin_usage > 0.4:  # 40%预警
            print(f"⚠️ 保证金使用率{margin_usage*100:.1f}%，接近限制")
            
        if margin_usage > 0.5:  # 50%限制
            if not self.trading_paused:
                print(f"🚨 保证金使用率达到{margin_usage*100:.1f}%，暂停开仓")
                self.trading_paused = True
                self.pause_reason = f"保证金不足({margin_usage*100:.1f}%)"
                
        # 5. 如果风险降低，可以恢复交易
        if (self.trading_paused and 
            self.current_floating_loss < self.max_floating_loss * 0.8 and 
            margin_usage < 0.4):
            print(f"✅ 风险降低，恢复交易")
            self.trading_paused = False
            self.pause_reason = ""
        
        return self.trading_paused

    def _calculate_floating_loss(self) -> float:
        """计算当前浮动亏损比例"""
        if not self.active_trades:
            return 0.0
        
        total_floating_pnl = 0.0
        current_price = self.data.close[0]
        
        for trade_info in self.active_trades.values():
            entry_price = trade_info['entry_price']
            size = trade_info['size']
            direction = trade_info['direction']
            
            if direction == 'buy':
                pnl = (current_price - entry_price) * size
            else:
                pnl = (entry_price - current_price) * size
            
            total_floating_pnl += pnl
        
        return abs(min(0, total_floating_pnl)) / self.account_initial

    def _calculate_margin_usage(self) -> float:
        """计算保证金使用率"""
        if not self.active_trades:
            return 0.0
        
        total_margin = sum(trade['required_margin'] for trade in self.active_trades.values())
        return total_margin / self.broker.getvalue()

    def _emergency_reduce_positions(self):
        """紧急减仓"""
        print(f"🚨 执行紧急减仓")
        
        # 按浮亏大小排序，先平浮亏最大的
        trades_by_loss = []
        current_price = self.data.close[0]
        
        for trade_id, trade_info in self.active_trades.items():
            profit_pct = self._calculate_current_profit_pct(trade_info, current_price)
            if profit_pct < 0:  # 只考虑亏损的
                trades_by_loss.append((trade_id, profit_pct))
        
        # 按亏损从大到小排序
        trades_by_loss.sort(key=lambda x: x[1])
        
        # 平掉亏损最大的一半仓位
        positions_to_close = len(trades_by_loss) // 2 + 1
        for i in range(min(positions_to_close, len(trades_by_loss))):
            trade_id = trades_by_loss[i][0]
            self._close_position(trade_id, "紧急减仓")

    def _print_strategy_status(self):
        """定期打印策略状态"""
        current_bar = len(self.data_cache)
        current_price = self.data_cache[-1]['close']
        account_value = self.broker.getvalue()
        
        print(f"\n━━━ 第{current_bar}根K线 策略状态 ━━━")
        print(f"💰 账户价值: {account_value:.2f} USDT")
        print(f"📈 当前价格: {current_price:.4f}")
        print(f"📊 持仓数量: {len(self.active_trades)}/{self.max_positions}")
        print(f"🎯 关键位数量: {len(self.key_levels)}")
        print(f"📉 总信号数: {self.signal_stats['total_signals']}")
        print(f"✅ 执行信号: {self.signal_stats['executed_signals']}")
        print(f"🏆 成功信号: {self.signal_stats['successful_signals']}")
        
        if self.active_trades:
            print(f"🔥 当前持仓:")
            for trade_id, trade in self.active_trades.items():
                current_profit = self._calculate_current_profit_pct(trade, current_price)
                bars_held = len(self.data_cache) - trade['entry_bar_index']
                print(f"   {trade_id}: {trade['direction']} @ {trade['entry_price']:.4f}")
                print(f"   持仓{bars_held}根K线，当前{current_profit:+.1f}%")
        
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    def stop(self):
        """策略结束时的清理工作"""
        print(f"\n🏁 策略执行完成！")
        print(f"📊 总计处理 {len(self.data_cache)} 根K线")
        print(f"🎯 检测信号: {self.signal_stats['total_signals']} 个")
        print(f"✅ 执行交易: {self.signal_stats['executed_signals']} 个")
        print(f"🏆 成功交易: {self.signal_stats['successful_signals']} 个")
        
        if self.signal_stats['executed_signals'] > 0:
            success_rate = (self.signal_stats['successful_signals'] / self.signal_stats['executed_signals']) * 100
            print(f"📈 成功率: {success_rate:.1f}%")
        
        final_value = self.broker.getvalue()
        total_return = (final_value - 10000) / 10000 * 100
        print(f"💰 最终账户: {final_value:.2f} USDT ({total_return:+.2f}%)")
        
        # 强制平仓所有剩余持仓
        if self.active_trades:
            print(f"🔄 强制平仓剩余 {len(self.active_trades)} 个持仓")
            for trade_id in list(self.active_trades.keys()):
                self._close_position_smart(trade_id, "策略结束强制平仓")
        """检查大行情信号"""
        if len(self.data_cache) < self.min_required_bars:
            print(f"🔍 数据不足: {len(self.data_cache)} < {self.min_required_bars}")
            return

        df = pd.DataFrame(self.data_cache)
        df_for_signal = df[:-1]  # 检测已完成K线
        
        if len(df_for_signal) < self.min_required_bars:
            print(f"🔍 信号检测数据不足: {len(df_for_signal)} < {self.min_required_bars}")
            return
        
    def _check_for_big_move_signals(self):
        """检查大行情信号"""
        if len(self.data_cache) < self.min_required_bars:
            if len(self.data_cache) % 50 == 0:  # 每50根K线输出一次
                print(f"🔍 数据积累中: {len(self.data_cache)}/{self.min_required_bars}")
            return

        df = pd.DataFrame(self.data_cache)
        df_for_signal = df[:-1]  # 检测已完成K线
        
        if len(df_for_signal) < self.min_required_bars:
            if len(self.data_cache) % 50 == 0:
                print(f"🔍 信号检测数据积累中: {len(df_for_signal)}/{self.min_required_bars}")
            return
        
        try:
            # 每隔一段时间输出检测状态
            if len(self.data_cache) % 100 == 0:
                print(f"🔍 第{len(self.data_cache)}根K线：开始信号检测...")
                print(f"   检测数据长度: {len(df_for_signal)}")
                print(f"   当前关键位数量: {len(self.key_levels)}")
                print(f"   当前持仓数量: {len(self.active_trades)}")
            
            all_signals = self.pinbar_detector.detect_pinbar_patterns(df_for_signal)
            
            if all_signals:
                print(f"📍 第{len(self.data_cache)}根K线：检测到 {len(all_signals)} 个Pinbar信号")
                
                current_bar_index = len(df_for_signal) - 1
                new_signals = [s for s in all_signals if s.index == current_bar_index]
                
                print(f"   当前K线新信号数量: {len(new_signals)}")
                
                for signal in new_signals:
                    self.signal_stats['total_signals'] += 1
                    
                    print(f"🎯 发现新信号: {signal.direction} @ {signal.close_price:.4f}")
                    print(f"    信号强度: {signal.signal_strength:.1f} | 置信度: {signal.confidence_score:.2f}")
                    
                    if self._is_big_move_signal(signal):
                        print(f"✅ 执行大行情信号")
                        self._execute_big_move_signal(signal)
                    else:
                        print(f"❌ 信号未通过验证")
            else:
                # 降低输出频率，避免刷屏
                if len(self.data_cache) % 200 == 0:  # 每200根K线输出一次
                    print(f"🔍 第{len(self.data_cache)}根K线：暂无Pinbar信号")
                        
        except Exception as e:
            print(f"❌ 大行情信号检测失败: {e}")
            import traceback
            traceback.print_exc()

    def _is_big_move_signal(self, signal: PinbarSignal) -> bool:
        """验证是否为大行情信号 - 加入币种适应性"""
        
        print(f"🔍 信号验证: 强度{signal.signal_strength:.1f} 置信度{signal.confidence_score:.2f}")
        
        # 1. 基础质量要求
        if signal.confidence_score < 0.4:
            print(f"    ❌ 置信度不足: {signal.confidence_score:.2f} < 0.4")
            return False
        
        if signal.signal_strength < 2.5:
            print(f"    ❌ 信号强度不足: {signal.signal_strength:.1f} < 2.5")
            return False
        
        print(f"    ✅ 基础质量通过")
        
        # 2. 币种适应性检查 - 根据历史表现调整
        coin_performance = self._get_coin_performance()
        if coin_performance['win_rate'] < 0.3 and coin_performance['trades'] >= 5:
            # 如果这个币种历史胜率很低，提高门槛
            if signal.confidence_score < 0.6:
                print(f"    ❌ 低胜率币种需要更高置信度: {signal.confidence_score:.2f} < 0.6")
                return False
            if signal.signal_strength < 3.5:
                print(f"    ❌ 低胜率币种需要更强信号: {signal.signal_strength:.1f} < 3.5")
                return False
            print(f"    ✅ 低胜率币种高标准验证通过")
        
        # 3. 检查盘整环境
        if self._is_in_consolidation():
            print(f"    ❌ 当前处于盘整环境，跳过信号")
            return False
        
        # 4. 方向记忆检查
        direction_bias = self._get_direction_bias(signal.close_price)
        if direction_bias and direction_bias != signal.direction:
            print(f"    ❌ 方向记忆冲突: 建议{direction_bias}，信号{signal.direction}")
            return False
        
        # 5. 趋势环境检查
        if self.current_trend_info:
            trend_alignment = self._check_trend_alignment(signal.direction)
            if not trend_alignment:
                print(f"    ❌ 趋势环境不支持")
                return False
            print(f"    ✅ 趋势环境支持")
        
        # 6. 关键位检查（可选）
        key_level_bonus = 0
        if self.key_levels:
            near_key_level, level_strength = self.sr_finder.is_near_key_level(
                signal.close_price, self.key_levels
            )
            
            if near_key_level and level_strength >= 1.0:
                key_level_bonus = 0.2  # 关键位加分
                print(f"    ✅ 接近关键位，强度: {level_strength:.1f} (+0.2分)")
            else:
                print(f"    ⚠️ 不在关键位附近")
        
        # 7. 成交量确认
        volume_bonus = 0
        if self._check_volume_confirmation():
            volume_bonus = 0.1  # 成交量加分
            print(f"    ✅ 成交量确认 (+0.1分)")
        else:
            print(f"    ⚠️ 成交量未确认")
        
        # 8. 综合评分系统
        final_score = signal.confidence_score + key_level_bonus + volume_bonus
        min_required_score = 0.5  # 基础要求
        
        if coin_performance['win_rate'] < 0.3 and coin_performance['trades'] >= 5:
            min_required_score = 0.7  # 低胜率币种要求更高
        
        if final_score < min_required_score:
            print(f"    ❌ 综合评分不足: {final_score:.2f} < {min_required_score:.2f}")
            return False
        
        # 9. 保证金检查
        if not self._check_margin_sufficient(signal):
            print(f"    ❌ 保证金不足")
            return False
        
        print(f"✅ 信号验证通过！综合评分: {final_score:.2f}")
        self.signal_stats['big_move_signals'] += 1
        return True
    
    def _get_coin_performance(self) -> Dict[str, float]:
        """获取当前币种的历史表现"""
        if not self.trade_history:
            return {'win_rate': 0.5, 'avg_profit': 0, 'trades': 0}
        
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for trade in self.trade_history if trade['profit'] > 0)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.5
        avg_profit = np.mean([trade['profit_pct'] for trade in self.trade_history]) if total_trades > 0 else 0
        
        return {
            'win_rate': win_rate,
            'avg_profit': avg_profit, 
            'trades': total_trades
        }

    def _is_in_consolidation(self) -> bool:
        """判断是否处于盘整环境"""
        if len(self.data_cache) < 20:
            return False
        
        recent_data = self.data_cache[-20:]
        highs = [d['high'] for d in recent_data]
        lows = [d['low'] for d in recent_data]
        
        highest = max(highs)
        lowest = min(lows)
        range_pct = (highest - lowest) / lowest
        
        # 如果20根K线的波动范围小于2%，认为是盘整
        is_consolidating = range_pct < self.consolidation_range_pct
        
        if is_consolidating:
            print(f"    盘整检测: 20根K线波动{range_pct*100:.2f}% < {self.consolidation_range_pct*100:.1f}%")
        
        return is_consolidating
    
    def _get_direction_bias(self, current_price: float) -> Optional[str]:
        """获取方向偏好基于历史失败记录"""
        if not self.recent_failures:
            return None
        
        # 检查最近的失败记录
        recent_failures_near_price = []
        for failure in self.recent_failures:
            price_diff = abs(failure['price'] - current_price) / current_price
            if price_diff < 0.01:  # 1%价格范围内
                bars_ago = len(self.data_cache) - failure['bar_index']
                if bars_ago <= self.memory_decay_bars:  # 在记忆周期内
                    recent_failures_near_price.append(failure)
        
        if not recent_failures_near_price:
            return None
        
        # 统计失败方向
        failed_directions = [f['direction'] for f in recent_failures_near_price]
        buy_failures = failed_directions.count('buy')
        sell_failures = failed_directions.count('sell')
        
        # 如果某个方向失败次数明显更多，建议相反方向
        if buy_failures > sell_failures + 1:
            print(f"    方向记忆: 该价位买单失败{buy_failures}次，建议做空")
            return 'sell'
        elif sell_failures > buy_failures + 1:
            print(f"    方向记忆: 该价位卖单失败{sell_failures}次，建议做多")
            return 'buy'
        
        return None
    
    def _check_trend_alignment(self, signal_direction: str) -> bool:
        """检查趋势对齐"""
        if not self.current_trend_info:
            return True  # 无趋势信息时允许
        
        # 强趋势中只允许同向信号
        if self.current_trend_info.strength.value >= 3:
            if (self.current_trend_info.direction == TrendDirection.UP and signal_direction == 'sell') or \
               (self.current_trend_info.direction == TrendDirection.DOWN and signal_direction == 'buy'):
                return False
        
        return True
    
    def _check_volume_confirmation(self) -> bool:
        """检查成交量确认"""
        if len(self.data_cache) < 15:
            return True
        
        recent_volumes = [d['volume'] for d in self.data_cache[-15:]]
        current_volume = self.data_cache[-1]['volume']
        avg_volume = np.mean(recent_volumes[:-1])
        
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        return volume_ratio >= 1.1
    
    def _check_margin_sufficient(self, signal: PinbarSignal) -> bool:
        """检查保证金是否充足"""
        current_position_count = len(self.active_trades)
        expected_leverage = self.leverage_by_positions.get(current_position_count + 1, 2)
        
        try:
            required_margin = self._estimate_required_margin(signal, expected_leverage)
            available_margin = self.broker.getcash() * (1 - self.margin_buffer_ratio)
            return required_margin <= available_margin
        except:
    def _estimate_required_margin(self, signal: PinbarSignal, leverage: float) -> float:
        """估算所需保证金"""
        current_price = self.data.close[0]
        risk_amount = self.broker.getcash() * self.max_single_risk
        stop_distance = abs(current_price - signal.stop_loss)
        
        if stop_distance <= 0:
            return float('inf')
        
        position_value = risk_amount / (stop_distance / current_price)
        required_margin = position_value / leverage
        
        return required_margin
        """估算所需保证金"""
        current_price = self.data.close[0]
        risk_amount = self.broker.getcash() * self.max_single_risk
        stop_distance = abs(current_price - signal.stop_loss)
        
        if stop_distance <= 0:
            return float('inf')
        
        position_value = risk_amount / (stop_distance / current_price)
        required_margin = position_value / leverage
        
        return required_margin

    def _execute_big_move_signal(self, signal: PinbarSignal):
        """执行大行情信号"""
        print(f"📊 执行大行情信号: {signal.type} {signal.direction}")
        
        # 1. 计算杠杆
        current_position_count = len(self.active_trades)
        base_leverage = self.leverage_by_positions.get(current_position_count + 1, 2)
        
        # 根据信号质量调整杠杆
        leverage_multiplier = 1.0
        if signal.confidence_score >= 0.85:  # 极高质量信号
            leverage_multiplier = 1.2
        elif signal.confidence_score >= 0.80:  # 高质量信号
            leverage_multiplier = 1.1
        
        final_leverage = min(self.max_leverage, int(base_leverage * leverage_multiplier))
        
        # 2. 计算仓位大小
        current_price = self.data.close[0]
        position_size = self._calculate_big_move_position_size(current_price, signal.stop_loss, final_leverage)
        
        if position_size <= 0:
            print(f"❌ 仓位计算失败")
            return
        
        # 3. 计算实际入场价格（滑点处理）
        direction = signal.direction
        if direction == 'buy':
            actual_entry_price = current_price * (1 + self.slippage_rate)
        else:
            actual_entry_price = current_price * (1 - self.slippage_rate)
        
        # 4. 重新精确计算仓位
        position_size = self._calculate_big_move_position_size(actual_entry_price, signal.stop_loss, final_leverage)
        if position_size <= 0:
            print(f"❌ 最终仓位计算失败")
            return
        
        # 5. 计算成本和保证金
        position_value = position_size * actual_entry_price
        required_margin = position_value / final_leverage
        total_cost = position_value * self.unified_cost_rate
        
        # 6. 最终保证金安全检查
        current_margin_usage = self._calculate_margin_usage()
        new_margin_usage = (self._get_total_used_margin() + required_margin) / self.broker.getvalue()
        
        if new_margin_usage > self.max_total_margin:
            print(f"❌ 保证金超限: {new_margin_usage*100:.1f}% > {self.max_total_margin*100:.0f}%")
            return
        
        print(f"💰 大行情交易详情:")
        print(f"   仓位大小: {position_size:.6f}")
        print(f"   入场价格: {actual_entry_price:.4f}")
        print(f"   杠杆倍数: {final_leverage}x")
        print(f"   仓位价值: {position_value:.2f} USDT")
        print(f"   所需保证金: {required_margin:.2f} USDT")
        print(f"   保证金占用: {new_margin_usage*100:.1f}%")
        
        # 8. 记录大行情交易（加入持仓控制）
        try:
            if direction == 'buy':
                order = self.buy(size=position_size)
            else:
                order = self.sell(size=position_size)
            
            if order is None:
                print(f"❌ 订单执行失败")
                return
            
            # 8. 记录大行情交易（加入智能持仓控制）
            self.signal_stats['executed_signals'] += 1
            self._record_smart_trade(order, signal, actual_entry_price, position_size, 
                                   final_leverage, total_cost, required_margin)
            
        except Exception as e:
            print(f"❌ 执行开仓失败: {e}")

    def _calculate_big_move_position_size(self, entry_price: float, stop_loss: float, leverage: float) -> float:
        """计算大行情仓位大小"""
        current_cash = self.broker.getcash()
        
        # 基于风险的仓位计算（小仓位策略）
        risk_amount = current_cash * self.max_single_risk
        stop_distance = abs(entry_price - stop_loss)
        
        if stop_distance <= 0:
            return 0
        
        # 基于风险的仓位价值
        position_value_by_risk = risk_amount / (stop_distance / entry_price)
        
        # 基于保证金限制的仓位价值
        available_cash = current_cash * (1 - self.margin_buffer_ratio)
        max_margin_for_position = available_cash * (self.max_single_margin / (self.max_positions / len(self.active_trades) if self.active_trades else 1))
        position_value_by_margin = max_margin_for_position * leverage
        
        # 取较小值，确保风险可控
        max_position_value = min(position_value_by_risk, position_value_by_margin)
        position_size = max_position_value / entry_price
        
        # 最小仓位检查
        min_position_value = 100  # 最小100USDT
        if position_size * entry_price < min_position_value:
            position_size = min_position_value / entry_price
        
        return position_size

    def _get_total_used_margin(self) -> float:
        """获取当前已使用保证金总额"""
        if not self.active_trades:
            return 0.0
        return sum(trade['required_margin'] for trade in self.active_trades.values())

    def _record_smart_trade(self, order, signal: PinbarSignal, actual_entry_price: float, 
                          position_size: float, leverage: float, total_cost: float,
                          required_margin: float):
        """记录智能交易（加入持仓控制）"""
        self.trade_counter += 1
        trade_id = f"SM{self.trade_counter:04d}"  # SM = Smart Move
        
        position_value = position_size * actual_entry_price
        current_account_value = self.broker.getvalue()
        margin_ratio = (required_margin / current_account_value) * 100
        
        # 计算动态持仓时间
        min_bars = self._calculate_dynamic_min_holding(signal)
        
        self.active_trades[trade_id] = {
            'order': order,
            'direction': signal.direction,
            'entry_price': actual_entry_price,
            'entry_time': self.data.datetime.datetime(),
            'entry_bar_index': len(self.data_cache),
            'size': position_size,
            'original_size': position_size,
            'stop_loss': signal.stop_loss,
            'leverage': leverage,
            'position_value': position_value,
            'required_margin': required_margin,
            'margin_ratio': margin_ratio,
            'total_cost': total_cost,
            'signal_strength': signal.signal_strength,
            'confidence_score': signal.confidence_score,
            
            # 智能持仓控制
            'min_holding_bars': min_bars,
            'max_holding_bars': self.max_holding_bars,
            'consolidation_check_bar': self.consolidation_exit_bars,
            'bars_held': 0,
            'highest_price_seen': actual_entry_price if signal.direction == 'buy' else 0,
            'lowest_price_seen': actual_entry_price if signal.direction == 'sell' else float('inf'),
            'breakout_detected': False,
            
            # 大行情特有属性
            'is_big_move_trade': True,
            'partial_closed': False,
            'profit_protection_active': False,
            'trailing_stop_active': False,
            'max_profit_seen': 0.0,
            'big_move_stage': 0,
            
            # 防止过早出场
            'early_exit_protection': True,
            'can_stop_loss': False  # 初始不能止损
        }
        
        print(f"✅ 智能开仓 {trade_id}: {signal.direction} @ {actual_entry_price:.4f}")
        print(f"   最少持仓: {min_bars}根K线")
        print(f"   止损: {signal.stop_loss:.4f}")
        print(f"   杠杆: {leverage}x | 保证金: {required_margin:.2f} USDT ({margin_ratio:.1f}%)")
    
    def _calculate_dynamic_min_holding(self, signal: PinbarSignal) -> int:
        """根据信号质量和市场环境计算最少持仓时间"""
        base_bars = self.min_holding_bars
        
        # 根据信号强度调整
        if signal.signal_strength >= 4.0:
            base_bars += 2  # 强信号多持仓2根K线
        elif signal.signal_strength >= 3.5:
            base_bars += 1
        
        # 根据波动率调整
        if len(self.data_cache) >= 20:
            recent_data = self.data_cache[-20:]
            volatility = self._calculate_recent_volatility(recent_data)
            if volatility > 0.03:  # 高波动率
                base_bars += 1
            elif volatility < 0.01:  # 低波动率
                base_bars += 2  # 低波动需要更多时间
        
        return min(base_bars, 8)  # 最多8根K线
    
    def _calculate_recent_volatility(self, data_list: List[Dict]) -> float:
        """计算最近的波动率"""
        if len(data_list) < 2:
            return 0.02
        
        prices = [d['close'] for d in data_list]
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        return np.std(returns) if returns else 0.02

    def _manage_big_move_positions(self):
        """管理智能持仓"""
        current_price = self.data.close[0]
        current_high = self.data.high[0]
        current_low = self.data.low[0]
        trades_to_close = []
        
        for trade_id, trade_info in self.active_trades.items():
            
            # 更新持仓统计
            trade_info['bars_held'] = len(self.data_cache) - trade_info['entry_bar_index']
            
            # 更新价格追踪
            if trade_info['direction'] == 'buy':
                trade_info['highest_price_seen'] = max(trade_info['highest_price_seen'], current_high)
            else:
                trade_info['lowest_price_seen'] = min(trade_info['lowest_price_seen'], current_low)
            
            # 1. 计算当前利润
            current_profit_pct = self._calculate_current_profit_pct(trade_info, current_price)
            trade_info['max_profit_seen'] = max(trade_info['max_profit_seen'], current_profit_pct)
            
            # 2. 智能持仓控制
            should_close, reason = self._should_close_position(trade_info, current_price, current_profit_pct)
            if should_close:
                trades_to_close.append((trade_id, reason))
                continue
            
            # 3. 解除早期保护
            if (trade_info.get('early_exit_protection', False) and 
                trade_info['bars_held'] >= trade_info['min_holding_bars']):
                trade_info['early_exit_protection'] = False
                trade_info['can_stop_loss'] = True
                print(f"🔓 {trade_id} 解除早期保护，持仓{trade_info['bars_held']}根K线")
            
            # 4. 检查基础止损（只有在解除保护后）
            if (trade_info.get('can_stop_loss', False) and 
                self._check_stop_loss_smart(trade_info, current_high, current_low)):
                trades_to_close.append((trade_id, "智能止损"))
                continue
            
            # 5. 大行情利润管理
            if trade_info.get('is_big_move_trade', False):
                self._manage_big_move_profit(trade_info, current_price, current_profit_pct, trade_id)
        
        # 执行平仓
        for trade_id, reason in trades_to_close:
            self._close_position_smart(trade_id, reason)
    
    def _should_close_position(self, trade_info: Dict, current_price: float, current_profit_pct: float) -> Tuple[bool, str]:
        """智能判断是否应该平仓"""
        bars_held = trade_info['bars_held']
        direction = trade_info['direction']
        entry_price = trade_info['entry_price']
        
        # 1. 最大持仓时间限制
        if bars_held >= trade_info['max_holding_bars']:
            return True, f"最大持仓时间({bars_held}根K线)"
        
        # 2. 盘整环境检查（持仓一段时间后）
        if bars_held >= trade_info['consolidation_check_bar']:
            if self._is_position_in_consolidation(trade_info, current_price):
                return True, f"盘整环境退出(持仓{bars_held}根K线)"
        
        # 3. 突破检查（只有在最小持仓时间后）
        if bars_held >= trade_info['min_holding_bars']:
            breakout_detected = self._detect_breakout_from_entry(trade_info, current_price)
            if breakout_detected:
                trade_info['breakout_detected'] = True
                print(f"🚀 {direction} 突破检测成功，继续持仓")
            elif bars_held >= 8 and not trade_info.get('breakout_detected', False):
                # 8根K线后还没突破，考虑退出
                if current_profit_pct < 2:  # 且利润不足2%
                    return True, f"未突破盘整(持仓{bars_held}根K线，利润{current_profit_pct:.1f}%)"
        
        # 4. 极端亏损保护
        if current_profit_pct < -10:  # 亏损超过10%
            return True, f"极端亏损保护({current_profit_pct:.1f}%)"
        
        return False, ""
    
    def _is_position_in_consolidation(self, trade_info: Dict, current_price: float) -> bool:
        """检查持仓期间是否陷入盘整"""
        entry_price = trade_info['entry_price']
        direction = trade_info['direction']
        
        # 检查价格是否在入场价附近震荡
        price_range_pct = abs(current_price - entry_price) / entry_price
        
        if direction == 'buy':
            # 做多：价格应该向上，如果一直在入场价下方震荡就是盘整
            highest = trade_info['highest_price_seen']
            move_from_entry = (highest - entry_price) / entry_price
            current_from_high = (highest - current_price) / highest
            
            # 如果突破不足1%，且从高点回撤超过50%，认为是盘整
            if move_from_entry < 0.01 and current_from_high > 0.5:
                return True
                
        else:
            # 做空：价格应该向下
            lowest = trade_info['lowest_price_seen']
            move_from_entry = (entry_price - lowest) / entry_price
            current_from_low = (current_price - lowest) / lowest
            
            if move_from_entry < 0.01 and current_from_low > 0.5:
                return True
        
        return False
    
    def _detect_breakout_from_entry(self, trade_info: Dict, current_price: float) -> bool:
        """检测是否从入场价突破"""
        entry_price = trade_info['entry_price']
        direction = trade_info['direction']
        
        if direction == 'buy':
            breakout_price = entry_price * (1 + self.breakout_threshold)
            return current_price >= breakout_price
        else:
            breakout_price = entry_price * (1 - self.breakout_threshold)
            return current_price <= breakout_price
    
    def _check_stop_loss_smart(self, trade_info: Dict, current_high: float, current_low: float) -> bool:
        """智能止损检查"""
        direction = trade_info['direction']
        stop_loss = trade_info['stop_loss']
        
        if direction == 'buy' and current_low <= stop_loss:
            print(f"🔴 智能止损触发(买): 最低价{current_low:.4f} <= 止损{stop_loss:.4f}")
            return True
        elif direction == 'sell' and current_high >= stop_loss:
            print(f"🔴 智能止损触发(卖): 最高价{current_high:.4f} >= 止损{stop_loss:.4f}")
            return True
        
        return False

    def _manage_big_move_profit(self, trade_info: Dict, current_price: float, 
                              current_profit_pct: float, trade_id: str):
        """大行情利润管理"""
        current_stage = trade_info['big_move_stage']
        
        # 阶段1: 5%利润 - 部分平仓+启动保护
        if current_profit_pct >= 5 and current_stage == 0:
            print(f"📈 {trade_id} 达到5%利润，执行部分平仓")
            self._execute_partial_close(trade_info, self.partial_close_ratio, "利润保护")
            
            # 移动止损到成本价+1%
            self._move_stop_to_breakeven_plus(trade_info, 0.01)
            
            trade_info['big_move_stage'] = 1
            trade_info['partial_closed'] = True
            trade_info['profit_protection_active'] = True
        
        # 阶段2: 10%利润 - 启动宽松追踪
        elif current_profit_pct >= 10 and current_stage == 1:
            print(f"📈 {trade_id} 达到10%利润，启动宽松追踪止损")
            self._update_big_move_trailing_stop(trade_info, current_price, 0.05)  # 5%追踪距离
            trade_info['big_move_stage'] = 2
            trade_info['trailing_stop_active'] = True
        
        # 阶段3: 20%利润 - 中等追踪
        elif current_profit_pct >= 20 and current_stage == 2:
            print(f"📈 {trade_id} 达到20%利润，调整追踪止损")
            self._update_big_move_trailing_stop(trade_info, current_price, 0.08)  # 8%追踪距离
            trade_info['big_move_stage'] = 3
        
        # 阶段4: 50%利润 - 积极保护
        elif current_profit_pct >= 50 and current_stage == 3:
            print(f"📈 {trade_id} 达到50%利润，积极保护利润")
            self._update_big_move_trailing_stop(trade_info, current_price, 0.12)  # 12%追踪距离
            trade_info['big_move_stage'] = 4
        
        # 持续追踪止损更新
        elif trade_info.get('trailing_stop_active', False):
            stage_distances = [0.05, 0.05, 0.08, 0.12]  # 对应各阶段的追踪距离
            if current_stage < len(stage_distances):
                self._update_big_move_trailing_stop(trade_info, current_price, stage_distances[current_stage])

    def _execute_partial_close(self, trade_info: Dict, close_ratio: float, reason: str):
        """执行部分平仓"""
        direction = trade_info['direction']
        current_size = trade_info['size']
        close_size = current_size * close_ratio
        
        try:
            if direction == 'buy':
                self.sell(size=close_size)
            else:
                self.buy(size=close_size)
            
            trade_info['size'] = current_size - close_size
            
            print(f"🔄 部分平仓 {close_ratio*100:.0f}%: {reason}")
            print(f"    剩余仓位: {trade_info['size']:.6f} ({trade_info['size']/trade_info['original_size']*100:.0f}%)")
            
        except Exception as e:
            print(f"❌ 部分平仓失败: {e}")

    def _move_stop_to_breakeven_plus(self, trade_info: Dict, plus_pct: float):
        """移动止损到成本价+指定百分比"""
        entry_price = trade_info['entry_price']
        direction = trade_info['direction']
        
        if direction == 'buy':
            new_stop = entry_price * (1 + plus_pct)
            if new_stop > trade_info['stop_loss']:
                trade_info['stop_loss'] = new_stop
                print(f"🔺 止损移至成本价+{plus_pct*100:.1f}%: {new_stop:.4f}")
        else:
            new_stop = entry_price * (1 - plus_pct)
            if new_stop < trade_info['stop_loss']:
                trade_info['stop_loss'] = new_stop
                print(f"🔻 止损移至成本价+{plus_pct*100:.1f}%: {new_stop:.4f}")

    def _update_big_move_trailing_stop(self, trade_info: Dict, current_price: float, trail_distance: float):
        """更新大行情追踪止损"""
        direction = trade_info['direction']
        
        # 根据趋势强度调整追踪距离
        if self.current_trend_info and self.current_trend_info.strength.value >= 4:
            trail_distance *= 1.2  # 极强趋势给更多空间
        
        if direction == 'buy':
            new_stop = current_price * (1 - trail_distance)
            if new_stop > trade_info['stop_loss']:
                trade_info['stop_loss'] = new_stop
                print(f"🔺 更新追踪止损: {new_stop:.4f} (距离{trail_distance*100:.1f}%)")
        else:
            new_stop = current_price * (1 + trail_distance)
            if new_stop < trade_info['stop_loss']:
                trade_info['stop_loss'] = new_stop
                print(f"🔻 更新追踪止损: {new_stop:.4f} (距离{trail_distance*100:.1f}%)")

    def _handle_extreme_profit(self, trade_info: Dict, trade_id: str):
        """处理极端利润情况"""
        print(f"🎉 {trade_id} 达到极端利润100%+！")
        
        # 可以选择再次部分平仓，锁定更多利润
        if trade_info['size'] / trade_info['original_size'] > 0.5:  # 如果还有超过50%仓位
            self._execute_partial_close(trade_info, 0.3, "极端利润保护")
        
        # 调整追踪止损更积极一些
        current_price = self.data.close[0]
        self._update_big_move_trailing_stop(trade_info, current_price, 0.15)  # 15%追踪距离

    def _calculate_current_profit_pct(self, trade_info: Dict, current_price: float) -> float:
        """计算当前利润百分比"""
        entry_price = trade_info['entry_price']
        direction = trade_info['direction']
        
        if direction == 'buy':
            return (current_price - entry_price) / entry_price * 100
        else:
            return (entry_price - current_price) / entry_price * 100

    def _check_stop_loss(self, trade_info: Dict, current_price: float) -> bool:
        """检查止损"""
        direction = trade_info['direction']
        stop_loss = trade_info['stop_loss']
        
        # 使用当前Bar的最高最低价
        current_high = self.data.high[0]
        current_low = self.data.low[0]
        
        if direction == 'buy' and current_low <= stop_loss:
            print(f"🔴 买单止损触发: 最低价{current_low:.4f} <= 止损{stop_loss:.4f}")
            return True
        elif direction == 'sell' and current_high >= stop_loss:
            print(f"🔴 卖单止损触发: 最高价{current_high:.4f} >= 止损{stop_loss:.4f}")
            return True
        
        return False

    def _close_position_smart(self, trade_id: str, reason: str):
        """智能平仓 - 加入方向记忆"""
        if trade_id not in self.active_trades:
            return
        
        trade_info = self.active_trades[trade_id]
        current_price = self.data.close[0]
        direction = trade_info['direction']
        
        # 计算滑点后的出场价格
        if direction == 'buy':
            actual_exit_price = current_price * (1 - self.slippage_rate)
        else:
            actual_exit_price = current_price * (1 + self.slippage_rate)
        
        # 执行平仓
        try:
            if direction == 'buy':
                self.sell(size=trade_info['size'])
            else:
                self.buy(size=trade_info['size'])
            
            # 计算损益
            entry_price = trade_info['entry_price']
            original_size = trade_info['original_size']
            
            if direction == 'buy':
                gross_profit = (actual_exit_price - entry_price) * original_size
            else:
                gross_profit = (entry_price - actual_exit_price) * original_size
            
            net_profit = gross_profit - trade_info['total_cost']
            profit_pct = (net_profit / trade_info['required_margin']) * 100
            
            # 记录失败方向（用于方向记忆）
            if net_profit < 0:
                self._record_failure_direction(trade_info, reason)
            
            # 记录交易历史
            entry_time = trade_info['entry_time']
            exit_time = self.data.datetime.datetime()
            holding_duration = exit_time - entry_time
            holding_hours = holding_duration.total_seconds() / 3600
            
            trade_record = {
                'trade_id': trade_id,
                'direction': direction,
                'entry_time': entry_time,
                'exit_time': exit_time,
                'holding_hours': holding_hours,
                'bars_held': trade_info.get('bars_held', 0),
                'entry_price': entry_price,
                'exit_price': actual_exit_price,
                'size': original_size,
                'leverage': trade_info['leverage'],
                'position_value': trade_info['position_value'],  
                'required_margin': trade_info['required_margin'],
                'margin_ratio': trade_info['margin_ratio'],
                'total_costs': trade_info['total_cost'],
                'gross_profit': gross_profit,
                'profit': net_profit,
                'profit_pct': profit_pct,
                'max_profit_seen': trade_info['max_profit_seen'],
                'reason': reason,
                'signal_strength': trade_info['signal_strength'],
                'confidence_score': trade_info['confidence_score'],
                'is_big_move_trade': trade_info.get('is_big_move_trade', False),
                'partial_closed': trade_info.get('partial_closed', False),
                'big_move_stage': trade_info.get('big_move_stage', 0),
                'breakout_detected': trade_info.get('breakout_detected', False),
                'min_holding_bars': trade_info.get('min_holding_bars', 0),
                'early_exit_protection': trade_info.get('early_exit_protection', False)
            }
            
            self.trade_history.append(trade_record)
            
            # 更新统计
            if net_profit > 0:
                self.winning_trades += 1
                self.total_profits += net_profit
                self.signal_stats['successful_signals'] += 1
                
                if trade_info.get('is_big_move_trade', False):
                    self.signal_stats['big_move_success'] += 1
                
                print(f"✅ 盈利平仓 {trade_id}: +{net_profit:.2f} USDT ({profit_pct:.1f}%)")
                print(f"   持仓{trade_info.get('bars_held', 0)}根K线，最大浮盈: {trade_info['max_profit_seen']:.1f}%")
            else:
                self.losing_trades += 1
                self.total_losses += abs(net_profit)
                print(f"❌ 亏损平仓 {trade_id}: {net_profit:.2f} USDT ({profit_pct:.1f}%)")
                print(f"   持仓{trade_info.get('bars_held', 0)}根K线，失败原因: {reason}")
            
            del self.active_trades[trade_id]
            
        except Exception as e:
            print(f"❌ 智能平仓失败: {e}")
    
    def _record_failure_direction(self, trade_info: Dict, reason: str):
        """记录失败方向用于方向记忆"""
        failure_record = {
            'price': trade_info['entry_price'],
            'direction': trade_info['direction'],
            'bar_index': trade_info['entry_bar_index'],
            'reason': reason,
            'timestamp': self.data.datetime.datetime()
        }
        
        self.recent_failures.append(failure_record)
        
        # 清理过期记录
        current_bar = len(self.data_cache)
        self.recent_failures = [
            f for f in self.recent_failures 
            if current_bar - f['bar_index'] <= self.memory_decay_bars * 2
        ]
        
        print(f"📝 记录失败方向: {trade_info['direction']} @ {trade_info['entry_price']:.4f}")
        print(f"   当前失败记录数: {len(self.recent_failures)}")

    def _update_account_stats(self):
        """更新账户统计"""
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
        
        # 计算信号成功率
        if self.signal_stats['executed_signals'] > 0:
            self.signal_stats['signal_success_rate'] = (
                self.signal_stats['successful_signals'] / self.signal_stats['executed_signals'] * 100
            )
        
        # 统计分析
        total_trades = len(self.trade_history)
        big_move_trades = len([t for t in self.trade_history if t.get('is_big_move_trade', False)])
        
        print(f"\n📊 博大行情版回测结果:")
        print(f"    总交易: {total_trades}")
        print(f"    大行情交易: {big_move_trades} ({big_move_trades/total_trades*100 if total_trades > 0 else 0:.1f}%)")
        print(f"    盈利交易: {self.winning_trades}")
        print(f"    亏损交易: {self.losing_trades}")
        print(f"    最大回撤: {self.max_dd*100:.2f}%")
        print(f"    是否暂停交易: {'是' if self.trading_paused else '否'}")
        if self.trading_paused:
            print(f"    暂停原因: {self.pause_reason}")
        
        print(f"\n🎯 大行情信号统计:")
        print(f"    检测信号: {self.signal_stats['total_signals']}")
        print(f"    大行情信号: {self.signal_stats['big_move_signals']}")
        print(f"    执行信号: {self.signal_stats['executed_signals']}")
        print(f"    信号成功率: {self.signal_stats['signal_success_rate']:.1f}%")
        if self.signal_stats['big_move_signals'] > 0:
            big_move_success_rate = self.signal_stats['big_move_success'] / self.signal_stats['big_move_signals'] * 100
            print(f"    大行情成功率: {big_move_success_rate:.1f}%")
        
        if self.trade_history:
            # 分析大行情交易表现
            big_move_profits = [t['profit'] for t in self.trade_history if t.get('is_big_move_trade', False) and t['profit'] > 0]
            if big_move_profits:
                avg_big_move_profit = np.mean(big_move_profits)
                max_big_move_profit = max(big_move_profits)
                print(f"    大行情平均盈利: {avg_big_move_profit:.2f} USDT")
                print(f"    大行情最大盈利: {max_big_move_profit:.2f} USDT")
            
            max_profits_seen = [t.get('max_profit_seen', 0) for t in self.trade_history]
            avg_max_profit = np.mean(max_profits_seen)
            print(f"    平均最大浮盈: {avg_max_profit:.1f}%")
            
            total_costs = sum(t.get('total_costs', 0) for t in self.trade_history)
            print(f"    累计交易成本: {total_costs:.2f} USDT")


def run_enhanced_backtest(data: pd.DataFrame, trading_params: TradingParams, 
                         backtest_params: BacktestParams,
                         detector_config: Dict[str, Any] = None,
                         use_dynamic_leverage: bool = True) -> Dict[str, Any]:
    """运行博大行情版回测"""
    print(f"🚀 开始博大行情版回测: {backtest_params.symbol} {backtest_params.interval}")
    
    # 设置Backtrader环境
    cerebro = bt.Cerebro()
    
    # 添加数据
    data_feed = CustomDataFeed(dataname=data)
    cerebro.adddata(data_feed)
    
    # 添加博大行情策略
    cerebro.addstrategy(EnhancedPinbarStrategy, 
                       trading_params=trading_params,
                       detector_config=detector_config,
                       use_dynamic_leverage=True)  # 强制启用动态杠杆
    
    # 设置初始资金和手续费
    cerebro.broker.setcash(backtest_params.initial_cash)
    cerebro.broker.setcommission(commission=0.001)  # 统一手续费0.1%
    
    # 运行回测
    print(f'💰 初始资金: {backtest_params.initial_cash:,.2f} USDT')
    results = cerebro.run()
    strategy = results[0]
    
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - backtest_params.initial_cash) / backtest_params.initial_cash * 100
    
    print(f'💰 最终资金: {final_value:,.2f} USDT')
    print(f'📈 总收益率: {total_return:.2f}%')
    
    # 统计信息
    total_trades = len(strategy.trade_history)
    
    if total_trades > 0:
        win_rate = (strategy.winning_trades / total_trades * 100)
        avg_profit = strategy.total_profits / strategy.winning_trades if strategy.winning_trades > 0 else 0
        avg_loss = strategy.total_losses / strategy.losing_trades if strategy.losing_trades > 0 else 0
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
        
        # 博大行情特殊统计
        big_move_trades = [t for t in strategy.trade_history if t.get('is_big_move_trade', False)]
        big_move_count = len(big_move_trades)
        big_move_win_count = len([t for t in big_move_trades if t['profit'] > 0])
        big_move_win_rate = big_move_win_count / big_move_count * 100 if big_move_count > 0 else 0
        
        # 成本和利润统计
        total_costs = sum(t.get('total_costs', 0) for t in strategy.trade_history)
        leverages = [t.get('leverage', 1) for t in strategy.trade_history]
        avg_leverage = np.mean(leverages) if leverages else 1.0
        max_leverage = max(leverages) if leverages else 1.0
        
        margin_ratios = [t.get('margin_ratio', 0) for t in strategy.trade_history if t.get('margin_ratio', 0) > 0]
        avg_margin_ratio = np.mean(margin_ratios) if margin_ratios else 0.0
        max_margin_ratio = max(margin_ratios) if margin_ratios else 0.0
        
        max_profits_seen = [t.get('max_profit_seen', 0) for t in strategy.trade_history]
        avg_max_profit = np.mean(max_profits_seen)
        max_single_profit = max([t['profit'] for t in strategy.trade_history]) if strategy.trade_history else 0
        
        print(f"📊 博大行情统计:")
        print(f"   大行情交易: {big_move_count}/{total_trades} ({big_move_count/total_trades*100:.1f}%)")
        print(f"   大行情胜率: {big_move_win_rate:.1f}%")
        print(f"   平均杠杆: {avg_leverage:.1f}x (最高: {max_leverage:.1f}x)")
        print(f"   平均保证金占用: {avg_margin_ratio:.1f}%")
        print(f"   最大单笔盈利: {max_single_profit:.2f} USDT")
        print(f"   平均最大浮盈: {avg_max_profit:.1f}%")
    else:
        win_rate = profit_factor = big_move_win_rate = 0
        avg_leverage = max_leverage = 1.0
        avg_margin_ratio = max_margin_ratio = 0.0
        total_costs = avg_max_profit = max_single_profit = 0
        big_move_count = 0
    
    # 返回结果
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
        'avg_leverage': avg_leverage,
        'max_leverage': max_leverage,
        'avg_margin_usage': avg_margin_ratio,
        'max_margin_usage': max_margin_ratio,
        'total_costs': total_costs,
        'avg_max_profit_seen': avg_max_profit,
        'max_single_profit': max_single_profit,
        
        # 博大行情特殊指标
        'big_move_trades': big_move_count,
        'big_move_win_rate': big_move_win_rate,
        'signal_stats': {
            'total_signals': strategy.signal_stats['total_signals'],
            'executed_signals': strategy.signal_stats['executed_signals'],
            'signal_execution_rate': strategy.signal_stats['executed_signals']/strategy.signal_stats['total_signals']*100 if strategy.signal_stats['total_signals'] > 0 else 0,
            'signal_success_rate': strategy.signal_stats['signal_success_rate'],
            'big_move_signals': strategy.signal_stats['big_move_signals'],
            'big_move_success': strategy.signal_stats['big_move_success'],
            'high_quality_signals': strategy.signal_stats['executed_signals'],
            'trend_aligned_signals': 0,
            'avg_signal_strength': 0,
            'avg_confidence_score': 0
        },
        'trades': strategy.trade_history,
        'trading_paused': strategy.trading_paused,
        'pause_reason': strategy.pause_reason,
        'account_protection_triggered': strategy.trading_paused,
        'use_dynamic_leverage': True,
        'trend_tracking_enabled': True
    }