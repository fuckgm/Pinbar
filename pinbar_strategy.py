#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版Pinbar策略 - 集成趋势跟踪 (修复版)
解决过早止盈问题，增加趋势跟踪能力，修复成本计算和保证金统计

版本: v3.0 - 止损后反向开仓修复版
修复日期: 2024年12月
主要修复:
1. ✅ 修复止损后没有反向开仓的问题
2. ✅ 添加持仓时间与波动率分析
3. ✅ 增强趋势逆转检测机制
4. ✅ 优化信号验证逻辑
5. ✅ 完善反向信号检测窗口
6. ✅ 修复成本计算和保证金统计

核心改进:
- 持仓时间分析: 短期/中期/长期持仓的不同处理
- 波动率状态检测: 低波动+长时间止损 = 高逆转概率
- 趋势逆转概率计算: 多因子综合评估
- 反向信号特殊通道: 止损后开启反向信号检测窗口
- 动态趋势更新: 止损后立即重新评估趋势状态
"""

import pandas as pd
import numpy as np
import backtrader as bt
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from config import TradingParams, BacktestParams
from data_manager import CustomDataFeed
from enhanced_signal_generator import EnhancedPinbarDetector, PinbarSignal
from dynamic_leverage_manager import DynamicLeverageManager
from trend_tracker import TrendTracker, TrendInfo, TrendDirection, TrendStrength

class SupportResistanceFinder:
    """
    支撑阻力位识别器 - 保持原有逻辑
    
    功能:
    - 识别摆动高低点
    - 计算关键位强度
    - 检查价格接近度
    """
    
    def __init__(self):
        self.swing_period = 10          # 摆动点识别周期
        self.min_touches = 2            # 最小触碰次数
        self.price_tolerance = 0.002    # 价格容忍度 (0.2%)
        self.lookback_period = 100      # 回看周期
        self.time_decay_factor = 0.01   # 时间衰减因子
        # 🔧 新增：反向信号检测增强属性
        self.reverse_signal_start_time = None       # 反向信号开始时间
        self.reverse_signal_end_time = None          # 添加这一行
        self.reverse_signal_window_seconds = 0      # 反向信号窗口秒数
        self.reverse_signal_counter = 0             # 反向信号计数器（降级方案）
    def find_key_levels(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """识别关键支撑阻力位"""
        if len(data) < self.lookback_period:
            return []
        
        levels = []
        recent_data = data.tail(self.lookback_period).copy()
        
        swing_highs = self._find_swing_points(recent_data, 'high')
        swing_lows = self._find_swing_points(recent_data, 'low')
        
        for price, idx in swing_highs:
            strength = self._calculate_level_strength(recent_data, price, idx, 'resistance')
            if strength > 1.0:
                levels.append({
                    'price': price,
                    'type': 'resistance', 
                    'strength': strength,
                    'age': len(recent_data) - idx
                })
        
        for price, idx in swing_lows:
            strength = self._calculate_level_strength(recent_data, price, idx, 'support')
            if strength > 1.0:
                levels.append({
                    'price': price,
                    'type': 'support',
                    'strength': strength, 
                    'age': len(recent_data) - idx
                })
        
        return sorted(levels, key=lambda x: x['strength'], reverse=True)[:20]
    
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
        time_factor = max(0.1, 1 - age * self.time_decay_factor)
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
    增强版Pinbar策略 - 趋势跟踪 + 止损后反向开仓修复版
    
    主要特性:
    1. 趋势跟踪系统: 识别强趋势并延长持仓
    2. 智能部分平仓: 分批锁定利润并保留核心仓位
    3. 动态止盈调整: 根据趋势强度自适应调整目标
    4. 🆕 持仓时间分析: 根据持仓时长判断趋势逆转概率
    5. 🆕 波动率状态检测: 低波动+长持仓=高逆转概率
    6. 🆕 反向信号特殊通道: 止损后开启反向信号检测窗口
    7. 🆕 趋势逆转分析: 综合多因子评估逆转概率
    8. 成本控制优化: 完整的手续费、滑点、资金费率计算
    9. 保证金管理: 动态保证金计算和风险控制
    """
    
    def __init__(self, trading_params: TradingParams, 
                 detector_config: Dict[str, Any] = None,
                 use_dynamic_leverage: bool = False):
        
        print("🚀 初始化增强版Pinbar策略 - 止损后反向开仓修复版...")
        
        # 基础参数
        self.trading_params = trading_params
        self.use_dynamic_leverage = use_dynamic_leverage
        
        # === 优化后的风险控制参数 ===
        self.max_account_loss_pct = 30.0        # 最大账户亏损限制 30%
        self.max_margin_per_trade_pct = 20.0    # 单笔最大保证金占用 20%
        self.min_account_balance = 100.0        # 最小账户余额
        
        # === 趋势跟踪参数 ===
        self.enable_trend_tracking = True       # 启用趋势跟踪
        self.trend_profit_extension = True      # 趋势中延长止盈
        self.min_trend_profit_pct = 1.0         # 趋势中最小利润1%
        self.max_trend_profit_pct = 15.0        # 趋势中最大利润15%
        
        # === 动态止盈参数 ===
        self.enable_dynamic_targets = True     # 启用动态止盈
        self.profit_lock_threshold = 3.0       # 3%利润后开始锁定
        self.trailing_stop_buffer = 1.5        # 追踪止损缓冲1.5%
        
        # === 部分平仓优化参数 ===
        self.smart_partial_close = True        # 智能部分平仓
        self.first_partial_ratio = 0.4         # 第一次部分平仓40%
        self.second_partial_ratio = 0.3        # 第二次部分平仓30%
        self.final_position_ratio = 0.3        # 保留30%追趋势
        
        # === 🆕 持仓时间与趋势逆转分析参数 ===
        self.short_holding_threshold = 4        # 短期持仓阈值（小时）
        self.long_holding_threshold = 24        # 长期持仓阈值（小时）
        self.low_volatility_threshold = 0.02    # 低波动率阈值（2%）
        self.consolidation_atr_ratio = 0.8      # 盘整时ATR比例
        self.reversal_probability_threshold = 0.6  # 逆转概率阈值
        
        # === 🆕 反向信号检测参数 ===
        self.enable_reverse_signal_detection = True  # 启用反向信号检测
        self.reverse_signal_max_window = 6           # 最大反向信号窗口（小时）
        self.reverse_signal_confidence_boost = 0.2   # 反向信号置信度加成
        self.max_recent_stop_losses = 5             # 最大保留止损记录数
        
        # === 修复：标准化交易成本参数 ===
        # 币安标准费率 (2024年标准)
        self.commission_rate = 0.001           # 0.1% 手续费
        self.taker_fee_rate = 0.001           # Taker费率 0.1%
        self.maker_fee_rate = 0.001           # Maker费率 0.1%
        self.funding_rate = 0.0001            # 资金费率 0.01%（每8小时）
        self.slippage_rate = 0.0005           # 滑点 0.05%
        self.funding_interval_hours = 8        # 资金费率收取间隔
        
        print(f"✅ 标准化交易成本参数:")
        print(f"   Taker手续费: {self.taker_fee_rate*100:.3f}%")
        print(f"   Maker手续费: {self.maker_fee_rate*100:.3f}%")
        print(f"   滑点率: {self.slippage_rate*100:.3f}%")
        print(f"   资金费率: {self.funding_rate*100:.4f}% (每{self.funding_interval_hours}小时)")
        
        # === 🆕 反向信号检测状态 ===
        self.reverse_signal_active = False          # 反向信号检测是否激活
        self.reverse_signal_end_time = None         # 反向信号窗口结束时间
        self.reverse_confidence_boost = 0.0         # 当前反向信号置信度加成
        self.recent_stop_losses = []                # 近期止损记录
        
        # 初始化组件
        self.sr_finder = SupportResistanceFinder()
        
        # 初始化趋势跟踪器
        trend_config = self._get_trend_tracker_config()
        self.trend_tracker = TrendTracker(trend_config)
        
        # 初始化信号检测器（放宽参数）
        detector_config = detector_config or self._get_relaxed_detector_config()
        self.pinbar_detector = EnhancedPinbarDetector(detector_config)
        
        # 计算最小所需K线数量
        self.min_required_bars = max(
            self.pinbar_detector.trend_period,
            self.trend_tracker.trend_ma_period,
            self.sr_finder.lookback_period,
            80  # 降低到80根K线
        )
        
        # 动态杠杆管理器
        if use_dynamic_leverage:
            self.leverage_manager = DynamicLeverageManager()
            print("✅ 启用动态杠杆管理")
        
        # 交易状态管理
        self.active_trades = {}
        self.trade_counter = 0
        self.trade_history = []
        self.signal_history = []
        self.pending_signals = {}
        
        # ✅ 信号统计收集
        self.signal_stats = {
            'total_signals': 0,              # 总检测信号数
            'executed_signals': 0,           # 执行信号数  
            'high_quality_signals': 0,       # 高质量信号数
            'trend_aligned_signals': 0,      # 趋势对齐信号数
            'reverse_signals': 0,            # 反向信号数
            'reverse_successful': 0,         # 成功的反向信号数
            'signal_strengths': [],          # 信号强度列表
            'confidence_scores': [],         # 置信度分数列表
            'successful_signals': 0,         # 成功信号数（盈利的交易）
            'signal_success_rate': 0.0       # 信号成功率
        }
        
        # 趋势状态缓存
        self.current_trend_info = None
        self.last_trend_update = 0
        
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
        
        # 账户保护状态
        self.account_protection_active = False
        
        print(f"✅ 策略初始化完成 (止损后反向开仓修复版):")
        print(f"   - 趋势跟踪: {self.enable_trend_tracking}")
        print(f"   - 动态止盈: {self.enable_dynamic_targets}")
        print(f"   - 智能部分平仓: {self.smart_partial_close}")
        print(f"   - 🆕 反向信号检测: {self.enable_reverse_signal_detection}")
        print(f"   - 🆕 持仓时间分析: 短期{self.short_holding_threshold}h/长期{self.long_holding_threshold}h")
        print(f"   - 🆕 逆转概率阈值: {self.reversal_probability_threshold}")
        print(f"   - 最大账户亏损: {self.max_account_loss_pct}%")
        print(f"   - 单笔最大保证金: {self.max_margin_per_trade_pct}%")

    def _get_trend_tracker_config(self) -> Dict[str, Any]:
        """获取趋势跟踪器配置"""
        return {
            'fast_ma_period': 8,
            'slow_ma_period': 21,
            'trend_ma_period': 50,
            'adx_period': 14,
            'roc_period': 10,
            'momentum_period': 14,
            'weak_adx': 20,
            'moderate_adx': 25,      # 降低阈值，更容易识别趋势
            'strong_adx': 35,        # 降低阈值
            'extreme_adx': 50,       # 降低阈值
            'volume_ma_period': 20,
            'volume_surge_threshold': 1.3,  # 降低成交量要求
            'breakout_lookback': 20,
            'breakout_threshold': 0.015,    # 降低突破要求到1.5%
            'atr_expansion_threshold': 1.2,
            'atr_lookback': 10
        }

    def _get_relaxed_detector_config(self) -> Dict[str, Any]:
        """获取放宽的检测器配置 - 增加信号频率"""
        return {
            # === 放宽Pinbar形态参数 ===
            'min_shadow_body_ratio': 2.0,      # 降低到2倍（原3倍）
            'max_body_ratio': 0.30,            # 提高到30%（原20%）
            'min_candle_size': 0.003,          # 降低最小K线大小
            'max_opposite_shadow_ratio': 0.4,  # 提高对侧影线容忍度
            
            # === 放宽确认机制 ===
            'require_confirmation': True,
            'confirmation_strength': 0.2,      # 降低确认强度（原0.3）
            
            # === 技术指标参数 ===
            'trend_period': 20,
            'rsi_period': 14,
            'rsi_oversold': 30,               # 放宽到30（原25）
            'rsi_overbought': 70,             # 放宽到70（原75）
            'bb_period': 20,
            'volume_threshold': 1.2,          # 降低成交量要求（原1.5）
            'sr_lookback': 50,
            'level_proximity': 0.005,         # 提高关键位接近度（原0.003）
            'min_signal_score': 3,            # 降低最低评分（原4）
            'adx_period': 14,
            'adx_threshold': 20,              # 降低ADX要求（原25）
            'atr_period': 14,
            'atr_percentile': 25,             # 降低ATR要求（原30）
            'volume_ma_period': 20,
            'volume_threshold_ratio': 0.7,    # 降低成交量比例要求
            'min_consolidation_bars': 10,     # 降低最小盘整期（原15）
            'large_move_threshold': 0.04,     # 降低大幅波动阈值
            'large_move_exclude_bars': 3      # 降低排除周期（原5）
        }

    # === 🆕 趋势逆转分析核心方法 ===
    
    def _analyze_trend_reversal_probability(self, trade_info: Dict, holding_hours: float) -> Dict:
        """
        分析趋势逆转概率 - 核心逆转检测算法
        
        逆转概率计算逻辑:
        1. 持仓时间因子: 长时间持仓 = 高逆转概率
        2. 波动率因子: 低波动率止损 = 高逆转概率  
        3. 特殊加权: 长时间+低波动 = 极高逆转概率
        
        Args:
            trade_info: 交易信息字典
            holding_hours: 持仓时间（小时）
            
        Returns:
            Dict: 包含逆转分析的完整结果
        """
        
        # === 1. 持仓时间分析 ===
        if holding_hours <= self.short_holding_threshold:
            holding_category = "短期"
            time_factor = 0.3  # 短期止损，逆转概率较低
            print(f"   持仓分析: {holding_hours:.1f}h -> 短期 (逆转概率低)")
        elif holding_hours <= self.long_holding_threshold:
            holding_category = "中期"
            time_factor = 0.6  # 中期止损，逆转概率中等
            print(f"   持仓分析: {holding_hours:.1f}h -> 中期 (逆转概率中等)")
        else:
            holding_category = "长期"
            time_factor = 0.9  # 长期止损，逆转概率高
            print(f"   持仓分析: {holding_hours:.1f}h -> 长期 (逆转概率高)")
        
        # === 2. 波动率分析 ===
        volatility_factor = 0.5  # 默认值
        volatility_state = "数据不足"
        
        try:
            if len(self.data_cache) >= 20:
                df = pd.DataFrame(self.data_cache[-20:])  # 最近20根K线
                
                # 计算最近期间的简单ATR
                recent_atr = self._calculate_simple_atr(df, 10)
                
                # 计算持仓期间的价格波动
                entry_price = trade_info['actual_entry_price']
                entry_time = trade_info['entry_time']
                price_changes = []
                
                # 收集持仓期间的价格变化数据
                for candle in self.data_cache:
                    candle_time = candle['timestamp']
                    if candle_time >= entry_time:
                        price_change = abs(candle['close'] - entry_price) / entry_price
                        price_changes.append(price_change)
                
                if price_changes:
                    avg_price_change = np.mean(price_changes)
                    max_price_change = max(price_changes)
                    
                    # 波动率状态判断
                    if max_price_change < self.low_volatility_threshold:
                        volatility_state = "低波动"
                        volatility_factor = 0.9  # 低波动止损，逆转概率高
                        print(f"   波动率分析: 最大变化{max_price_change*100:.1f}% -> 低波动 (逆转概率高)")
                    elif avg_price_change < self.low_volatility_threshold * 0.5:
                        volatility_state = "盘整"
                        volatility_factor = 0.85  # 盘整中止损，逆转概率很高
                        print(f"   波动率分析: 平均变化{avg_price_change*100:.1f}% -> 盘整 (逆转概率很高)")
                    else:
                        volatility_state = "正常波动"
                        volatility_factor = 0.5
                        print(f"   波动率分析: 正常波动 (逆转概率中等)")
                else:
                    volatility_state = "无持仓数据"
                    volatility_factor = 0.5
                    print(f"   波动率分析: 无有效持仓数据")
            else:
                print(f"   波动率分析: K线数据不足({len(self.data_cache)})")
                
        except Exception as e:
            print(f"⚠️ 波动率分析失败: {e}")
            volatility_state = "分析失败"
            volatility_factor = 0.5
        
        # === 3. 综合逆转概率计算 ===
        # 基础概率: 时间因子60% + 波动率因子40%
        base_probability = (time_factor * 0.6 + volatility_factor * 0.4)
        
        # === 4. 特殊情况加权 ===
        final_probability = base_probability
        reversal_confidence = base_probability
        
        # 长时间 + 低波动 = 极高逆转概率
        if holding_hours > self.long_holding_threshold and volatility_state in ["低波动", "盘整"]:
            final_probability = min(0.95, base_probability * 1.3)
            reversal_confidence = 0.9
            print(f"   特殊加权: 长时间+低波动 -> 极高逆转概率")
        # 中期 + 盘整 = 高逆转概率
        elif holding_hours > self.short_holding_threshold and volatility_state == "盘整":
            final_probability = min(0.85, base_probability * 1.2)
            reversal_confidence = 0.8
            print(f"   特殊加权: 中期+盘整 -> 高逆转概率")
        
        # === 5. 决策建议 ===
        should_seek_reverse = final_probability > self.reversal_probability_threshold
        
        # 构建分析结果
        analysis_result = {
            'reversal_probability': final_probability,      # 逆转概率
            'reversal_confidence': reversal_confidence,     # 逆转置信度
            'holding_category': holding_category,            # 持仓时间类别
            'volatility_state': volatility_state,           # 波动率状态
            'should_seek_reverse': should_seek_reverse,     # 是否寻找反向信号
            'holding_hours': holding_hours,                 # 持仓小时数
            'time_factor': time_factor,                     # 时间因子
            'volatility_factor': volatility_factor          # 波动率因子
        }
        
        print(f"📊 逆转概率分析完成:")
        print(f"   最终概率: {final_probability:.1%} (置信度: {reversal_confidence:.1%})")
        print(f"   建议寻找反向信号: {'是' if should_seek_reverse else '否'}")
        
        return analysis_result

    def _calculate_simple_atr(self, df: pd.DataFrame, period: int) -> float:
        """
        计算简单ATR (Average True Range)
        
        用于波动率分析，避免依赖talib库
        
        Args:
            df: 包含OHLC的数据框
            period: 计算周期
            
        Returns:
            float: ATR值
        """
        try:
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            
            true_ranges = []
            for i in range(1, len(df)):
                # 真实范围 = max(高-低, |高-前收|, |低-前收|)
                tr1 = highs[i] - lows[i]
                tr2 = abs(highs[i] - closes[i-1])
                tr3 = abs(lows[i] - closes[i-1])
                true_ranges.append(max(tr1, tr2, tr3))
            
            if len(true_ranges) >= period:
                return np.mean(true_ranges[-period:])
            else:
                return np.mean(true_ranges) if true_ranges else 0.01
                
        except Exception as e:
            print(f"⚠️ ATR计算失败: {e}")
            return 0.01

    def _set_reverse_signal_window(self, reversal_analysis: Dict):
        """
        设置反向信号检测窗口 - 修复版
        
        修复内容:
        1. 使用Backtrader兼容的时间格式
        2. 添加详细调试信息
        3. 确保窗口状态正确设置
        """
        if not self.enable_reverse_signal_detection:
            print(f"🔍 [DEBUG] 反向信号检测未启用")
            return
        
        # 根据逆转概率设置窗口期长度
        prob = reversal_analysis['reversal_probability']
        if prob > 0.8:
            window_hours = 6
        elif prob > 0.6:
            window_hours = 4
        else:
            window_hours = 2
        
        window_hours = min(window_hours, self.reverse_signal_max_window)
        
        # 🔧 修复：使用更兼容的时间处理方式
        try:
            # 获取当前时间并转换为标准datetime
            current_bt_time = self.data.datetime.datetime()
            if hasattr(current_bt_time, 'replace'):
                # 如果是datetime对象，直接使用
                current_time = current_bt_time
            else:
                # 如果是其他格式，尝试转换
                current_time = datetime.fromtimestamp(current_bt_time)
            
            # 计算窗口结束时间 - 使用简单的秒数计算
            window_seconds = window_hours * 3600
            self.reverse_signal_end_time = current_time + timedelta(seconds=window_seconds)
            self.reverse_signal_active = True
            self.reverse_signal_window_seconds = window_seconds  # 新增：用秒数记录窗口期
            self.reverse_signal_start_time = current_time        # 新增：记录开始时间
            self.reverse_confidence_boost = reversal_analysis['reversal_confidence'] * self.reverse_signal_confidence_boost
            
            print(f"🎯 开启反向信号窗口 (修复版):")
            print(f"   窗口期: {window_hours}小时 ({window_seconds}秒)")
            print(f"   当前时间: {current_time}")
            print(f"   反向信号状态: {self.reverse_signal_active}")
            print(f"   置信度加成: +{self.reverse_confidence_boost:.1%}")
            
        except Exception as e:
            print(f"❌ 设置反向信号窗口失败: {e}")
            # 降级方案：使用简单的计数器
            self.reverse_signal_active = True
            self.reverse_signal_counter = window_hours * 12  # 假设5分钟K线，每小时12根
            self.reverse_confidence_boost = reversal_analysis['reversal_confidence'] * self.reverse_signal_confidence_boost
            print(f"🔧 使用降级方案：计数器模式，剩余{self.reverse_signal_counter}根K线")

    def _check_reverse_signal_window_status(self) -> bool:
        """
        检查反向信号窗口状态 - 修复版
        
        修复内容:
        1. 双重检查机制（时间+计数器）
        2. 详细的状态调试信息
        3. 异常处理机制
        """
        if not self.reverse_signal_active:
            return False
        
        try:
            # 方法1: 时间检查
            if hasattr(self, 'reverse_signal_start_time') and hasattr(self, 'reverse_signal_window_seconds'):
                current_bt_time = self.data.datetime.datetime()
                if hasattr(current_bt_time, 'replace'):
                    current_time = current_bt_time
                else:
                    current_time = datetime.fromtimestamp(current_bt_time)
                
                elapsed_seconds = (current_time - self.reverse_signal_start_time).total_seconds()
                time_remaining = self.reverse_signal_window_seconds - elapsed_seconds
                
                print(f"🔍 [DEBUG] 反向信号窗口检查:")
                print(f"   已过时间: {elapsed_seconds:.0f}秒 ({elapsed_seconds/3600:.1f}小时)")
                print(f"   剩余时间: {time_remaining:.0f}秒 ({time_remaining/3600:.1f}小时)")
                
                if time_remaining <= 0:
                    print(f"🔚 反向信号窗口关闭 (时间到期)")
                    self.reverse_signal_active = False
                    self.reverse_confidence_boost = 0.0
                    return False
                else:
                    return True
                    
        except Exception as e:
            print(f"⚠️ 时间检查失败: {e}")
            
        # 方法2: 计数器检查（降级方案）
        if hasattr(self, 'reverse_signal_counter'):
            self.reverse_signal_counter -= 1
            print(f"🔍 [DEBUG] 反向信号计数器: 剩余{self.reverse_signal_counter}根K线")
            
            if self.reverse_signal_counter <= 0:
                print(f"🔚 反向信号窗口关闭 (计数器到期)")
                self.reverse_signal_active = False
                self.reverse_confidence_boost = 0.0
                return False
            else:
                return True
        
        # 如果两种方法都不可用，默认关闭
        print(f"⚠️ 反向信号窗口状态无法确定，默认关闭")
        self.reverse_signal_active = False
        return False

    def _analyze_recent_stop_loss_patterns(self, signal: PinbarSignal) -> Tuple[bool, Dict]:
        """
        分析最近止损模式 - 增强调试版
        
        增强内容:
        1. 详细的步骤调试信息
        2. 每个判断条件的输出
        3. 时间计算的兼容性处理
        """
        print(f"🔍 [DEBUG] 分析止损模式开始...")
        print(f"🔍 [DEBUG] 当前信号: {signal.direction}")
        print(f"🔍 [DEBUG] 止损记录数量: {len(self.recent_stop_losses)}")
        
        if not self.recent_stop_losses:
            print(f"🔍 [DEBUG] 无止损记录")
            return False, {}
        
        try:
            current_bt_time = self.data.datetime.datetime()
            if hasattr(current_bt_time, 'replace'):
                current_time = current_bt_time
            else:
                current_time = datetime.fromtimestamp(current_bt_time)
            
            print(f"🔍 [DEBUG] 当前时间: {current_time}")
            
            # 分析最近2次止损
            for i, stop_info in enumerate(self.recent_stop_losses[-2:]):
                print(f"🔍 [DEBUG] 检查止损记录 {i+1}:")
                print(f"   止损时间: {stop_info['time']}")
                print(f"   止损方向: {stop_info['direction']}")
                print(f"   持仓时长: {stop_info['holding_hours']:.1f}小时")
                
                # 计算时间差
                try:
                    if hasattr(stop_info['time'], 'replace'):
                        stop_time = stop_info['time']
                    else:
                        stop_time = datetime.fromtimestamp(stop_info['time'])
                    
                    time_diff_hours = (current_time - stop_time).total_seconds() / 3600
                    print(f"   时间差: {time_diff_hours:.1f}小时")
                    
                except Exception as e:
                    print(f"   时间计算失败: {e}，使用备用方案")
                    time_diff_hours = 1.0  # 默认1小时前
                
                # 6小时内的止损才考虑
                if time_diff_hours <= 6:
                    reversal_analysis = stop_info['reversal_analysis']
                    print(f"   逆转概率: {reversal_analysis['reversal_probability']:.1%}")
                    print(f"   建议寻找反向: {reversal_analysis['should_seek_reverse']}")
                    print(f"   方向相反: {stop_info['direction'] != signal.direction}")
                    
                    # 检查是否为高逆转概率的止损
                    if (reversal_analysis['should_seek_reverse'] and
                        stop_info['direction'] != signal.direction):  # 方向相反
                        
                        print(f"🎯 发现高概率逆转信号!")
                        print(f"   止损时间: {time_diff_hours:.1f}小时前")
                        print(f"   止损方向: {stop_info['direction']} -> 信号方向: {signal.direction}")
                        print(f"   持仓时长: {stop_info['holding_hours']:.1f}小时")
                        print(f"   波动率状态: {reversal_analysis['volatility_state']}")
                        print(f"   逆转概率: {reversal_analysis['reversal_probability']:.1%}")
                        
                        return True, {
                            'stop_time_diff': time_diff_hours,
                            'stop_direction': stop_info['direction'],
                            'holding_hours': stop_info['holding_hours'],
                            'volatility_state': reversal_analysis['volatility_state'],
                            'reversal_probability': reversal_analysis['reversal_probability'],
                            'original_trend': stop_info.get('original_trend', 'unknown')
                        }
                    else:
                        print(f"   不符合反向信号条件")
                else:
                    print(f"   时间超过6小时，跳过")
            
            print(f"🔍 [DEBUG] 未发现反向信号机会")
            return False, {}
            
        except Exception as e:
            print(f"❌ 分析止损模式失败: {e}")
            return False, {}

    # === 主交易逻辑方法 ===

    def prenext(self):
        """数据不足时调用"""
        self._update_data_cache()

    def next(self):
        """
        主交易逻辑 - 增强版 (修复版)
        
        执行顺序:
        1. 更新数据缓存
        2. 检查数据充足性
        3. 账户保护检查
        4. 趋势分析更新 (智能频率)
        5. 关键位更新
        6. 现有持仓管理 (趋势感知)
        7. 待确认信号检查
        8. 新信号检测 (含反向信号特殊处理)
        9. 账户统计更新
        """
        # 1. 更新数据缓存
        self._update_data_cache()
        
        # 2. 检查数据是否充足
        if len(self.data_cache) < self.min_required_bars:
            return
        
        # 3. 检查账户保护
        if self._check_account_protection():
            return
        
        # 4. 🆕 智能趋势更新: 正常每5根K线，止损后立即更新
        should_update_trend = self._should_update_trend_analysis()
        if should_update_trend:
            self._update_trend_analysis()
        
        # 5. 更新关键位（每20根K线更新一次）
        if len(self.data_cache) - self.last_key_levels_update >= 20:
            self._update_key_levels()
        
        # 6. 管理现有持仓（趋势感知版）
        self._manage_active_trades_with_trend()
        
        # 7. 检查待确认信号
        self._check_signal_confirmations()
        
        # 8. 检查新信号 (含反向信号特殊处理)
        self._check_for_new_signals()
        
        # 9. 更新账户统计
        self._update_account_stats()
        
    def _should_update_trend_analysis(self) -> bool:
        """
        判断是否应该更新趋势分析
        
        更新触发条件:
        1. 正常情况: 每5根K线更新
        2. 止损后: 立即更新 (1小时内有止损)
        3. 反向信号窗口: 更频繁更新
        
        Returns:
            bool: True表示应该更新
        """
        # 正常更新间隔
        normal_update = (len(self.data_cache) - self.last_trend_update >= 5)
        
        # 止损后加速更新
        recent_stop_loss = False
        if self.recent_stop_losses:
            last_stop = self.recent_stop_losses[-1]
            hours_since_stop = (self.data.datetime.datetime() - last_stop['time']).total_seconds() / 3600
            recent_stop_loss = hours_since_stop <= 1  # 1小时内有止损
        
        # 反向信号窗口期间加速更新
        in_reverse_window = self._check_reverse_signal_window_status()
        
        should_update = normal_update or recent_stop_loss or in_reverse_window
        
        if should_update and not normal_update:
            print(f"🔄 加速趋势更新: 止损后={recent_stop_loss}, 反向窗口={in_reverse_window}")
        
        return should_update

    def _update_trend_analysis(self):
        """更新趋势分析"""
        try:
            df = pd.DataFrame(self.data_cache)
            self.current_trend_info = self.trend_tracker.analyze_trend(df)
            self.last_trend_update = len(self.data_cache)
            
            # 调试信息
            if self.current_trend_info:
                trend = self.current_trend_info
                print(f"📈 趋势更新: {trend.direction.value} | "
                      f"强度: {trend.strength.value} | "
                      f"置信度: {trend.confidence:.2f} | "
                      f"动量: {trend.momentum_score:.2f}")
                      
        except Exception as e:
            print(f"❌ 趋势分析失败: {e}")

    def _check_account_protection(self) -> bool:
        """检查账户保护机制"""
        current_value = self.broker.getvalue()
        loss_pct = (self.account_initial - current_value) / self.account_initial * 100
        
        if loss_pct >= self.max_account_loss_pct:
            if not self.account_protection_active:
                print(f"🚨 账户保护激活！亏损 {loss_pct:.2f}% >= {self.max_account_loss_pct}%")
                self.account_protection_active = True
                
                # 平掉所有持仓
                for trade_id in list(self.active_trades.keys()):
                    self._close_position(trade_id, "账户保护")
            return True
        
        return False

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
        
        # 保留最近1000根K线
        if len(self.data_cache) > 1000:
            self.data_cache.pop(0)

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

    def _check_for_new_signals(self):
        """
        检查新信号 - 趋势感知版 + 反向信号特殊处理
        
        增强功能:
        1. 原有信号检测逻辑
        2. 🆕 反向信号窗口状态检查
        3. 🆕 止损模式分析
        4. 🆕 反向信号统计
        """
         # 🔍 增强调试信息
        print(f"🔍 [DEBUG] 检查新信号开始...")
        print(f"🔍 [DEBUG] 反向信号窗口状态: {self.reverse_signal_active}")
        print(f"🔍 [DEBUG] 近期止损记录数: {len(self.recent_stop_losses)}")
        if self.reverse_signal_active:
            current_time = self.data.datetime.datetime()
            print(f"🔍 [DEBUG] 当前时间: {current_time}")
            print(f"🔍 [DEBUG] 窗口结束时间: {self.reverse_signal_end_time}")
            if self.reverse_signal_end_time is not None:
                time_left = (self.reverse_signal_end_time - current_time).total_seconds() / 3600
                print(f"🔍 [DEBUG] 窗口剩余时间: {time_left:.2f}小时")
            else:
                print(f"🔍 [DEBUG] 窗口结束时间未设置")


        if len(self.active_trades) >= self.trading_params.max_positions:
            return
        
        if self.account_protection_active:
            return
        
        if len(self.data_cache) < self.min_required_bars:
            return

        df = pd.DataFrame(self.data_cache)
        df_for_signal = df[:-1]  # 检测已完成K线
        
        if len(df_for_signal) < self.min_required_bars:
            return
        
        try:
            all_signals = self.pinbar_detector.detect_pinbar_patterns(df_for_signal)
            
            if all_signals:
                current_bar_index = len(df_for_signal) - 1
                new_signals = [s for s in all_signals if s.index == current_bar_index]
                
                for signal in new_signals:
                    # ✅ 收集信号统计
                    self.signal_stats['total_signals'] += 1
                    self.signal_stats['signal_strengths'].append(signal.signal_strength)
                    self.signal_stats['confidence_scores'].append(signal.confidence_score)
                    
                    # 统计高质量信号
                    if signal.signal_strength >= 4 and signal.confidence_score >= 0.7:
                        self.signal_stats['high_quality_signals'] += 1
                    
                    # 统计趋势对齐信号
                    if self.current_trend_info:
                        trend_aligned = (
                            (self.current_trend_info.direction == TrendDirection.UP and signal.direction == 'buy') or
                            (self.current_trend_info.direction == TrendDirection.DOWN and signal.direction == 'sell')
                        )
                        if trend_aligned:
                            self.signal_stats['trend_aligned_signals'] += 1
                    
                    # 🆕 检查是否为反向信号
                    is_reverse_signal, reverse_details = self._analyze_recent_stop_loss_patterns(signal)
                    if is_reverse_signal:
                        self.signal_stats['reverse_signals'] += 1
                    
                    # 验证信号 (含反向信号特殊处理)
                    if self._is_valid_pinbar_signal_with_trend(signal, is_reverse_signal, reverse_details):
                        signal_id = f"signal_{len(self.pending_signals)}"
                        self.pending_signals[signal_id] = {
                            'signal': signal,
                            'timestamp': signal.timestamp,
                            'waiting_for_confirmation': True,
                            'trend_info': self.current_trend_info,
                            'is_reverse_signal': is_reverse_signal,  # 🆕 标记反向信号
                            'reverse_details': reverse_details       # 🆕 反向信号详情
                        }
                        
                        signal_type = "反向信号" if is_reverse_signal else "常规信号"
                        print(f"🎯 发现Pinbar{signal_type} {signal_id}: {signal.direction} @ {signal.close_price:.4f}")
                        if self.current_trend_info:
                            print(f"    趋势状态: {self.current_trend_info.direction.value} "
                                  f"强度:{self.current_trend_info.strength.value}")
                        
        except Exception as e:
            print(f"❌ 信号检测失败: {e}")

    def _is_valid_pinbar_signal_with_trend(self, signal: PinbarSignal, 
                                        is_reverse_signal: bool = False,
                                        reverse_details: Dict = None) -> bool:
        """
        验证Pinbar信号 - 调试增强版
        
        增强内容:
        1. 每个判断步骤的详细输出
        2. 反向信号路径的完整追踪
        3. 简化的判断逻辑便于调试
        """
        
        print(f"🔍 [DEBUG] ========== 信号验证开始 ==========")
        print(f"🔍 [DEBUG] 信号方向: {signal.direction}")
        print(f"🔍 [DEBUG] 信号强度: {signal.signal_strength}")
        print(f"🔍 [DEBUG] 置信度: {signal.confidence_score:.2f}")
        print(f"🔍 [DEBUG] 是否反向信号: {is_reverse_signal}")
        
        # === 1. 基础质量检查 ===
        min_confidence = 0.1  # 极度放宽用于调试
        min_strength = 1      # 极度放宽用于调试
        
        if signal.confidence_score < min_confidence:
            print(f"🔍 [DEBUG] ❌ 置信度不足: {signal.confidence_score:.2f} < {min_confidence}")
            return False
        
        if signal.signal_strength < min_strength:
            print(f"🔍 [DEBUG] ❌ 强度不足: {signal.signal_strength} < {min_strength}")
            return False
        
        print(f"🔍 [DEBUG] ✅ 基础质量检查通过")
        
        # === 2. 反向信号检查 ===
        in_reverse_window = self._check_reverse_signal_window_status()
        print(f"🔍 [DEBUG] 反向信号窗口状态: {in_reverse_window}")
        
        # 检查近期止损情况
        recent_reverse_opportunity = False
        if self.recent_stop_losses:
            last_stop = self.recent_stop_losses[-1]
            try:
                current_bt_time = self.data.datetime.datetime()
                if hasattr(current_bt_time, 'replace'):
                    current_time = current_bt_time
                else:
                    current_time = datetime.fromtimestamp(current_bt_time)
                
                if hasattr(last_stop['time'], 'replace'):
                    stop_time = last_stop['time']
                else:
                    stop_time = datetime.fromtimestamp(last_stop['time'])
                
                time_diff = (current_time - stop_time).total_seconds() / 3600
                print(f"🔍 [DEBUG] 最近止损: {time_diff:.1f}小时前")
                print(f"🔍 [DEBUG] 止损方向: {last_stop['direction']}")
                print(f"🔍 [DEBUG] 当前信号方向: {signal.direction}")
                print(f"🔍 [DEBUG] 方向相反: {last_stop['direction'] != signal.direction}")
                
                if (time_diff <= 6 and 
                    last_stop['direction'] != signal.direction and
                    last_stop['reversal_analysis']['should_seek_reverse']):
                    recent_reverse_opportunity = True
                    print(f"🔍 [DEBUG] ✅ 发现近期反向机会!")
                
            except Exception as e:
                print(f"🔍 [DEBUG] 时间计算失败: {e}")
        
        # === 3. 反向信号特殊通道 ===
        if is_reverse_signal or in_reverse_window or recent_reverse_opportunity:
            print(f"🔍 [DEBUG] ========== 反向信号特殊通道 ==========")
            print(f"🔍 [DEBUG] ✅ 通过反向信号特殊通道验证")
            print(f"🔍 [DEBUG] 原因: is_reverse={is_reverse_signal}, in_window={in_reverse_window}, recent_opp={recent_reverse_opportunity}")
            
            # 资金检查
            current_cash = self.broker.getcash()
            if current_cash < self.min_account_balance:
                print(f"🔍 [DEBUG] ❌ 资金不足: {current_cash:.2f} < {self.min_account_balance}")
                return False
            
            print(f"🔍 [DEBUG] ✅ 反向信号验证完全通过!")
            return True
        
        # === 4. 常规信号路径 ===
        print(f"🔍 [DEBUG] 进入常规信号验证路径")
        
        # 简化常规验证 - 用于调试
        current_cash = self.broker.getcash()
        if current_cash < self.min_account_balance:
            print(f"🔍 [DEBUG] ❌ 资金不足")
            return False
        
        print(f"🔍 [DEBUG] ✅ 常规信号验证通过")
        return True

    def _check_signal_funds_availability(self, signal: PinbarSignal) -> bool:
        """
        检查信号的资金可用性
        
        Args:
            signal: Pinbar信号
            
        Returns:
            bool: True表示资金充足
        """
        current_cash = self.broker.getcash()
        if current_cash < self.min_account_balance:
            print(f"    账户余额不足: {current_cash:.2f} < {self.min_account_balance}")
            return False
        
        print(f"✅ 信号验证通过")
        return True

    def _check_signal_confirmations(self):
        """
        检查信号确认 - 考虑趋势因素 + 反向信号特殊处理
        """
        current_candle = self.data_cache[-1]
        confirmed_signals = []
        
        for signal_id, signal_info in self.pending_signals.items():
            signal = signal_info['signal']
            is_reverse_signal = signal_info.get('is_reverse_signal', False)
            
            # 🆕 反向信号和强趋势时可以更快确认
            quick_confirm = is_reverse_signal
            if not quick_confirm and self.current_trend_info and self.current_trend_info.strength.value >= 3:
                trend_aligned = (
                    (self.current_trend_info.direction == TrendDirection.UP and signal.direction == 'buy') or
                    (self.current_trend_info.direction == TrendDirection.DOWN and signal.direction == 'sell')
                )
                if trend_aligned:
                    quick_confirm = True
            
            # 检查确认条件
            if self._is_signal_confirmed_with_trend(signal, current_candle, quick_confirm):
                signal_type = "反向信号" if is_reverse_signal else "常规信号"
                print(f"✅ {signal_type} {signal_id} 获得确认")
                
                # 🆕 反向信号成功确认时，更新统计
                # if is_reverse_signal:
                #     self.signal_stats['reverse_signals'] += 1
                
                self._execute_confirmed_signal(signal, signal_id, signal_info.get('trend_info'))
                confirmed_signals.append(signal_id)
            else:
                # 检查超时
                age = len(self.data_cache) - signal.index - 1
                timeout = 1 if quick_confirm else 2  # 快速确认1根K线超时，否则2根
                if age > timeout:
                    signal_type = "反向信号" if is_reverse_signal else "常规信号"
                    print(f"❌ {signal_type} {signal_id} 超时失效")
                    confirmed_signals.append(signal_id)
        
        # 移除已处理信号
        for signal_id in confirmed_signals:
            del self.pending_signals[signal_id]

    def _is_signal_confirmed_with_trend(self, signal: PinbarSignal, 
                                      current_candle: Dict, quick_confirm: bool = False) -> bool:
        """信号确认 - 考虑趋势因素"""
        
        if quick_confirm:
            # 强趋势或反向信号的快速确认
            if signal.direction == 'buy':
                return current_candle['close'] >= signal.close_price * 0.999  # 几乎不下跌即确认
            else:
                return current_candle['close'] <= signal.close_price * 1.001  # 几乎不上涨即确认
        else:
            # 常规确认
            if signal.direction == 'buy':
                return current_candle['close'] > signal.low_price
            else:
                return current_candle['close'] < signal.high_price

    def _execute_confirmed_signal(self, signal: PinbarSignal, signal_id: str, 
                                signal_trend_info: Optional[TrendInfo] = None):
        """
        执行确认信号 - 修复版本
        
        执行流程:
        1. 预检查保证金充足性
        2. 计算滑点后入场价格  
        3. 趋势感知杠杆调整
        4. 仓位大小计算
        5. 成本详细计算
        6. 执行开仓订单
        7. 记录交易信息
        """
        print(f"📊 执行确认信号: {signal.type} {signal.direction}")
        
        # 1. 预先检查保证金充足性
        margin_check_result = self._pre_check_margin_requirement(signal, signal_trend_info)
        
        if not margin_check_result['sufficient']:
            # 记录保证金不足的信号
            self._record_insufficient_margin_signal(signal_id, signal, margin_check_result)
            print(f"❌ 信号 {signal_id} 保证金不足，跳过开仓")
            return
            
        current_price = self.data.close[0]
        direction = signal.direction
        
        # 2. 计算滑点后的入场价格
        if direction == 'buy':
            actual_entry_price = current_price * (1 + self.slippage_rate)
            print(f"   买入滑点: {current_price:.4f} -> {actual_entry_price:.4f} (+{self.slippage_rate*100:.3f}%)")
        else:
            actual_entry_price = current_price * (1 - self.slippage_rate)
            print(f"   卖出滑点: {current_price:.4f} -> {actual_entry_price:.4f} (-{self.slippage_rate*100:.3f}%)")
        
        # 3. 根据趋势调整杠杆
        leverage = self._calculate_trend_aware_leverage(signal, signal_trend_info)
        
        # 4. 计算仓位大小
        position_size = self._calculate_position_size(actual_entry_price, signal.stop_loss, leverage)
        
        if position_size <= 0:
            print(f"❌ 仓位计算失败")
            return
            
        # 5. 详细的成本计算
        position_value = position_size * actual_entry_price  # 仓位价值
        required_margin = position_value / leverage           # 所需保证金
        
        # 开仓手续费计算（使用Taker费率，因为市价单）
        entry_commission = position_value * self.taker_fee_rate
        
        # 滑点成本
        entry_slippage_cost = abs(actual_entry_price - current_price) * position_size
        
        print(f"💰 成本详情:")
        print(f"   仓位大小: {position_size:.6f}")
        print(f"   仓位价值: {position_value:.2f} USDT")
        print(f"   杠杆倍数: {leverage}x")
        print(f"   所需保证金: {required_margin:.2f} USDT")
        print(f"   开仓手续费: {entry_commission:.2f} USDT ({self.taker_fee_rate*100:.3f}%)")
        print(f"   开仓滑点成本: {entry_slippage_cost:.2f} USDT")
        
        # 6. 检查保证金充足性
        available_margin = self.broker.getcash() * 0.9  # 留10%缓冲
        if required_margin > available_margin:
            print(f"❌ 保证金不足: 需要{required_margin:.2f}, 可用{available_margin:.2f}")
            return
            
        # 7. 执行开仓
        try:
            if direction == 'buy':
                order = self.buy(size=position_size)
            else:
                order = self.sell(size=position_size)
            
            if order is None:
                print(f"❌ 订单执行失败")
                return
            
            # 8. 统计已执行信号
            self.signal_stats['executed_signals'] += 1
            
            # 9. 记录交易信息（包含趋势信息）
            self._record_new_trade_with_trend(
                order, signal, actual_entry_price, position_size, 
                leverage, entry_commission, required_margin,
                entry_slippage_cost, signal_trend_info
            )
            
        except Exception as e:
            print(f"❌ 执行开仓失败: {e}")
    
    def _pre_check_margin_requirement(self, signal: PinbarSignal, 
                                trend_info: Optional[TrendInfo] = None) -> Dict:
        """预检查保证金需求"""
        current_cash = self.broker.getcash()
        current_price = self.data.close[0]
        
        # 计算预期杠杆
        expected_leverage = self._calculate_trend_aware_leverage(signal, trend_info)
        
        # 计算预期仓位大小
        expected_position_size = self._calculate_position_size(
            current_price, signal.stop_loss, expected_leverage
        )
        
        if expected_position_size <= 0:
            return {
                'sufficient': False,
                'reason': '仓位计算失败',
                'required_margin': 0,
                'available_cash': current_cash
            }
        
        # 计算所需保证金
        position_value = expected_position_size * current_price
        required_margin = position_value / expected_leverage
        
        # 检查是否充足（留10%缓冲）
        available_for_margin = current_cash * 0.9
        sufficient = required_margin <= available_for_margin
        
        return {
            'sufficient': sufficient,
            'reason': '保证金充足' if sufficient else '保证金不足',
            'required_margin': required_margin,
            'available_cash': current_cash,
            'expected_leverage': expected_leverage,
            'expected_position_size': expected_position_size
        }
        
    def _record_insufficient_margin_signal(self, signal_id: str, signal: PinbarSignal, 
                                     margin_info: Dict):
        """记录保证金不足的信号信息"""
        insufficient_signal = {
            'signal_id': signal_id,
            'timestamp': self.data.datetime.datetime(),
            'symbol': self.trading_params.symbol if hasattr(self.trading_params, 'symbol') else 'unknown',
            'direction': signal.direction,
            'entry_price': signal.close_price,
            'signal_strength': signal.signal_strength,
            'confidence_score': signal.confidence_score,
            'required_margin': margin_info['required_margin'],
            'available_cash': margin_info['available_cash'],
            'margin_shortage': margin_info['required_margin'] - margin_info['available_cash'],
            'reason': margin_info['reason']
        }
        
        # 添加到专门的列表中
        if not hasattr(self, 'insufficient_margin_signals'):
            self.insufficient_margin_signals = []
        
        self.insufficient_margin_signals.append(insufficient_signal)
        
        print(f"📝 记录保证金不足信号: {signal_id}")
        print(f"    所需保证金: {margin_info['required_margin']:.2f} USDT")
        print(f"    可用现金: {margin_info['available_cash']:.2f} USDT")
        print(f"    缺口: {insufficient_signal['margin_shortage']:.2f} USDT")

    def _calculate_trend_aware_leverage(self, signal: PinbarSignal, 
                                      trend_info: Optional[TrendInfo] = None) -> float:
        """根据趋势调整杠杆"""
        base_leverage = self.trading_params.leverage
        
        if not self.use_dynamic_leverage or not trend_info:
            return base_leverage
        
        try:
            # 基础质量因子
            quality_factor = signal.confidence_score * (signal.signal_strength / 5.0)
            
            # 趋势因子
            trend_factor = 1.0
            if trend_info.strength.value >= 3:  # 强趋势
                trend_factor = 1.3
            if trend_info.strength.value >= 4:  # 极强趋势
                trend_factor = 1.5
            
            # 趋势一致性因子
            trend_aligned = (
                (trend_info.direction == TrendDirection.UP and signal.direction == 'buy') or
                (trend_info.direction == TrendDirection.DOWN and signal.direction == 'sell')
            )
            alignment_factor = 1.2 if trend_aligned else 0.8
            
            # 置信度因子
            confidence_factor = 0.5 + trend_info.confidence
            
            adjusted_leverage = (base_leverage * quality_factor * 
                               trend_factor * alignment_factor * confidence_factor)
            
            return max(1, min(base_leverage * 1.5, int(adjusted_leverage)))
            
        except Exception as e:
            print(f"❌ 趋势感知杠杆计算失败: {e}")
            return base_leverage

    def _calculate_position_size(self, entry_price: float, stop_loss: float, leverage: float) -> float:
        """计算仓位大小 - 优化版"""
        current_cash = self.broker.getcash()
        
        # 基于风险的仓位计算
        risk_amount = current_cash * self.trading_params.risk_per_trade
        stop_distance = abs(entry_price - stop_loss)
        
        if stop_distance <= 0:
            return 0
        
        # 最大仓位基于风险
        max_position_value_by_risk = risk_amount / (stop_distance / entry_price)
        
        # 基于保证金限制
        # 使用更保守的可用资金计算
        available_cash = current_cash * 0.8  # 保留20%缓冲
        max_margin_amount = available_cash * (self.max_margin_per_trade_pct / 100)
        max_position_value_by_margin = max_margin_amount * leverage
        
        print(f"   风险额度: {risk_amount:.2f} USDT")
        print(f"   止损距离: {stop_distance:.4f} ({stop_distance/entry_price*100:.2f}%)")
        print(f"   基于风险最大仓位: {max_position_value_by_risk:.2f} USDT")
        print(f"   可用现金: {available_cash:.2f} USDT")
        print(f"   最大保证金额度: {max_margin_amount:.2f} USDT ({self.max_margin_per_trade_pct}%)")
        print(f"   基于保证金最大仓位: {max_position_value_by_margin:.2f} USDT")
        
        # 取较小值
        max_position_value = min(max_position_value_by_risk, max_position_value_by_margin)
        position_size = max_position_value / entry_price
        
        # 最小仓位检查
        min_position_value = 10
        if position_size * entry_price < min_position_value:
            position_size = min_position_value / entry_price
        
        # 保证金充足性检查
        final_position_value = position_size * entry_price
        required_margin = final_position_value / leverage
        if required_margin > available_cash:
            print(f"❌ 保证金不足: 需要{required_margin:.2f}, 可用{available_cash:.2f}")
            return 0
        
        print(f"   最终仓位大小: {position_size:.6f}")
        print(f"   最终仓位价值: {final_position_value:.2f} USDT")
        print(f"   所需保证金: {required_margin:.2f} USDT")
        print(f"   保证金占用: {required_margin/current_cash*100:.2f}%")
        
        return position_size

    def _record_new_trade_with_trend(self, order, signal: PinbarSignal, actual_entry_price: float, 
                               position_size: float, leverage: float, entry_commission: float,
                               required_margin: float, entry_slippage_cost: float,
                               trend_info: Optional[TrendInfo] = None):
        """记录新交易 - 修复版本包含完整成本信息"""
        self.trade_counter += 1
        trade_id = f"T{self.trade_counter:04d}"
        
        position_value = position_size * actual_entry_price
        # 修复保证金计算 - 确保数据正确性
        current_account_value = self.broker.getvalue()  # 使用总资产而不是现金
        current_cash = self.broker.getcash()
        # 重新验证保证金计算
        calculated_margin = position_value / leverage   

        # 保证金占用比例应该基于账户总价值，而不是现金
        # 因为现金会因为开仓而减少，但总资产价值更稳定
        margin_ratio_by_value = (calculated_margin / current_account_value) * 100
        margin_ratio_by_cash = (calculated_margin / current_cash) * 100 if current_cash > 0 else 0
    
        # 使用账户总价值计算更合理的保证金占用比例
        margin_ratio = margin_ratio_by_value
        
        # 调试信息
        print(f"🔍 保证金计算调试:")
        print(f"   仓位价值: {position_value:.2f} USDT")
        print(f"   杠杆: {leverage}x")
        print(f"   计算保证金: {calculated_margin:.2f} USDT")
        print(f"   传入保证金: {required_margin:.2f} USDT")
        print(f"   当前现金: {current_cash:.2f} USDT")
        print(f"   当前资产: {current_account_value:.2f} USDT")
        print(f"   保证金占比(现金): {margin_ratio_by_cash:.2f}%")
        print(f"   保证金占比(资产): {margin_ratio_by_value:.2f}%")

        # 确保保证金数据一致性
        if abs(calculated_margin - required_margin) > 0.01:
            print(f"⚠️ 保证金计算不一致，使用重新计算值")
            required_margin = calculated_margin
        
        # 确保保证金为正数
        if required_margin < 0:
            print(f"❌ 保证金为负数: {required_margin:.2f}，设为0")
            required_margin = 0
            margin_ratio = 0

        # 计算预估资金费用（基于持仓时间估算）
        estimated_holding_hours = 24  # 假设平均持仓24小时
        estimated_funding_periods = estimated_holding_hours / self.funding_interval_hours
        estimated_funding_cost = position_value * self.funding_rate * estimated_funding_periods
        
        # 根据趋势动态调整止盈目标
        if trend_info and self.enable_dynamic_targets:
            dynamic_tp1 = self.trend_tracker.calculate_dynamic_profit_target(
                trend_info, actual_entry_price, signal.direction
            )
        else:
            dynamic_tp1 = signal.take_profit_1
        
        # 安全获取趋势信息
        if trend_info:
            try:
                trend_direction = trend_info.direction.value if hasattr(trend_info.direction, 'value') else str(trend_info.direction)
                trend_strength = trend_info.strength.value if hasattr(trend_info.strength, 'value') else str(trend_info.strength)
                trend_confidence = trend_info.confidence if hasattr(trend_info, 'confidence') else 0.0
            except Exception as e:
                print(f"⚠️ 趋势信息获取失败: {e}")
                trend_direction = 'unknown'
                trend_strength = 'unknown'
                trend_confidence = 0.0
        else:
            trend_direction = 'unknown'
            trend_strength = 'unknown'
            trend_confidence = 0.0
        
        self.active_trades[trade_id] = {
            'order': order,
            'direction': signal.direction,
            'entry_price': self.data.close[0],
            'actual_entry_price': actual_entry_price,
            'entry_time': self.data.datetime.datetime(),
            'size': position_size,
            'original_size': position_size,
            'stop_loss': signal.stop_loss,
            'take_profit_1': dynamic_tp1,
            'take_profit_2': signal.take_profit_2,
            'take_profit_3': signal.take_profit_3,
            'leverage': leverage,
            'signal_info': signal,
            'trend_info': trend_info,
            
            # 完整的成本和保证金信息
            'position_value': position_value,
            'required_margin': required_margin,
            'margin_ratio': margin_ratio,
            'entry_commission': entry_commission,
            'margin_ratio_by_cash': margin_ratio_by_cash,
            'margin_ratio_by_value': margin_ratio_by_value,
            'account_value_at_entry': current_account_value,
            'cash_at_entry': current_cash,
            'entry_commission': entry_commission,
            'entry_slippage_cost': entry_slippage_cost,
            'estimated_funding_cost': estimated_funding_cost,
            'actual_funding_cost': 0.0,  # 实际资金费用（平仓时计算）
            'total_commission': entry_commission,  # 总手续费（平仓时累加）
            'total_slippage_cost': entry_slippage_cost,  # 总滑点成本（平仓时累加）
            
            # 交易状态
            'trailing_stop': signal.stop_loss,
            'trailing_activated': False,
            'highest_price': actual_entry_price if signal.direction == 'buy' else 0,
            'lowest_price': actual_entry_price if signal.direction == 'sell' else float('inf'),
            
            # 信号和趋势信息
            'signal_type': signal.type,
            'signal_strength': signal.signal_strength,
            'confidence_score': signal.confidence_score,
            'trend_alignment': signal.trend_alignment,
            'entry_reason': signal.entry_reason,
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'trend_confidence': trend_confidence,
            
            # 趋势跟踪状态
            'partial_close_count': 0,
            'break_even_moved': False,
            'trend_tracking_active': trend_info is not None and hasattr(trend_info, 'is_strong_trend'),
            'last_profit_check': 0,
            'max_profit_seen': 0,
            'profit_lock_active': False
        }
        
        print(f"✅ 成功开仓 {trade_id}: {signal.direction} @ {actual_entry_price:.4f}")
        print(f"   杠杆: {leverage}x | 保证金: {required_margin:.2f} USDT ({margin_ratio:.1f}%)")
        print(f"   手续费: {entry_commission:.2f} USDT | 滑点成本: {entry_slippage_cost:.2f} USDT")
        print(f"   动态止盈: {dynamic_tp1:.4f} | 趋势跟踪: {self.active_trades[trade_id]['trend_tracking_active']}")

    # === 持仓管理方法 ===

    def _manage_active_trades_with_trend(self):
        """管理现有持仓 - 趋势感知版"""
        current_price = self.data.close[0]
        trades_to_close = []
        
        for trade_id, trade_info in self.active_trades.items():
            
            # 1. 更新最高/最低价格
            self._update_trade_extremes(trade_info, current_price)
            
            # 2. 计算当前利润
            current_profit_pct = self._calculate_current_profit_pct(trade_info, current_price)
            trade_info['last_profit_check'] = current_profit_pct
            trade_info['max_profit_seen'] = max(trade_info['max_profit_seen'], current_profit_pct)
            
            # 3. 趋势感知的持仓管理
            if trade_info['trend_tracking_active']:
                self._manage_trend_following_position(trade_info, current_price, trade_id)
            
            # 4. 智能部分平仓
            if self.smart_partial_close and not trade_info.get('all_closed', False):
                self._smart_partial_close_management(trade_info, current_price, current_profit_pct)
            
            # 5. 检查止损
            if self._check_stop_loss(trade_info, current_price):
                trades_to_close.append((trade_id, "止损"))
                continue
            
            # 6. 检查常规止盈
            exit_reason = self._check_take_profit_with_trend(trade_info, current_price)
            if exit_reason:
                trades_to_close.append((trade_id, exit_reason))
        
        # 执行平仓
        for trade_id, reason in trades_to_close:
            self._close_position(trade_id, reason)

    def _manage_trend_following_position(self, trade_info: Dict, current_price: float, trade_id: str):
        """趋势跟踪持仓管理"""
        trend_info = trade_info.get('trend_info')
        if not trend_info:
            return
        
        direction = trade_info['direction']
        current_profit_pct = trade_info['last_profit_check']
        
        # 更新当前趋势状态
        current_trend = self.current_trend_info
        
        # 检查趋势是否仍然强劲
        if current_trend and hasattr(current_trend, 'should_hold_position'):
            # 趋势延续，检查是否应该延长止盈
            should_extend = self.trend_tracker.should_extend_profit_target(
                current_trend, current_profit_pct
            )
            
            if should_extend and current_profit_pct >= self.min_trend_profit_pct:
                # 延长止盈目标
                new_target = self.trend_tracker.calculate_dynamic_profit_target(
                    current_trend, trade_info['actual_entry_price'], direction
                )
                
                # 只在新目标更好时更新
                if direction == 'buy' and new_target > trade_info['take_profit_1']:
                    trade_info['take_profit_1'] = new_target
                    print(f"📈 {trade_id} 趋势延续，调整止盈到: {new_target:.4f}")
                elif direction == 'sell' and new_target < trade_info['take_profit_1']:
                    trade_info['take_profit_1'] = new_target
                    print(f"📉 {trade_id} 趋势延续，调整止盈到: {new_target:.4f}")
            
            # 动态追踪止损
            if current_profit_pct >= self.profit_lock_threshold:
                self._update_trend_trailing_stop(trade_info, current_price, current_trend)
        
        else:
            # 趋势弱化，准备退出
            if current_profit_pct >= self.min_trend_profit_pct:
                print(f"📉 {trade_id} 趋势弱化，触发退出机制")
                trade_info['trend_tracking_active'] = False
                # 收紧止盈目标
                self._tighten_profit_target(trade_info, current_price)

    def _update_trend_trailing_stop(self, trade_info: Dict, current_price: float, 
                                  trend_info: TrendInfo):
        """更新趋势追踪止损"""
        direction = trade_info['direction']
        
        # 获取动态止损距离
        stop_distance_pct = self.trend_tracker.get_trailing_stop_distance(trend_info)
        
        if direction == 'buy':
            new_stop = current_price * (1 - stop_distance_pct / 100)
            if new_stop > trade_info['trailing_stop']:
                trade_info['trailing_stop'] = new_stop
                trade_info['stop_loss'] = new_stop
                print(f"🔺 更新追踪止损(买): {new_stop:.4f} (距离{stop_distance_pct:.1f}%)")
        else:
            new_stop = current_price * (1 + stop_distance_pct / 100)
            if new_stop < trade_info['trailing_stop']:
                trade_info['trailing_stop'] = new_stop
                trade_info['stop_loss'] = new_stop
                print(f"🔻 更新追踪止损(卖): {new_stop:.4f} (距离{stop_distance_pct:.1f}%)")

    def _smart_partial_close_management(self, trade_info: Dict, current_price: float, 
                                      current_profit_pct: float):
        """智能部分平仓管理"""
        partial_count = trade_info['partial_close_count']
        
        # 第一次部分平仓：达到2%利润
        if partial_count == 0 and current_profit_pct >= 2.0:
            self._execute_partial_close(trade_info, self.first_partial_ratio, "首次获利")
            trade_info['partial_close_count'] = 1
        
        # 第二次部分平仓：达到5%利润
        elif partial_count == 1 and current_profit_pct >= 5.0:
            self._execute_partial_close(trade_info, self.second_partial_ratio, "二次获利")
            trade_info['partial_close_count'] = 2
        
        # 如果趋势很强，保留最后30%追更大利润
        elif partial_count == 2 and current_profit_pct >= 10.0:
            trend_info = trade_info.get('trend_info')
            if not (trend_info and hasattr(trend_info, 'strength') and trend_info.strength.value >= 4):
                # 趋势不够强时，平掉剩余仓位
                remaining_ratio = trade_info['size'] / trade_info['original_size']
                self._execute_partial_close(trade_info, remaining_ratio, "完全平仓")
                trade_info['all_closed'] = True

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
            print(f"    剩余仓位: {trade_info['size']:.6f}")
            
        except Exception as e:
            print(f"❌ 部分平仓失败: {e}")

    def _update_trade_extremes(self, trade_info: Dict, current_price: float):
        """更新交易的极值价格"""
        if trade_info['direction'] == 'buy':
            trade_info['highest_price'] = max(trade_info['highest_price'], current_price)
        else:
            trade_info['lowest_price'] = min(trade_info['lowest_price'], current_price)

    def _calculate_current_profit_pct(self, trade_info: Dict, current_price: float) -> float:
        """计算当前利润百分比"""
        entry_price = trade_info['actual_entry_price']
        direction = trade_info['direction']
        
        if direction == 'buy':
            return (current_price - entry_price) / entry_price * 100
        else:
            return (entry_price - current_price) / entry_price * 100

    def _tighten_profit_target(self, trade_info: Dict, current_price: float):
        """收紧止盈目标"""
        direction = trade_info['direction']
        
        if direction == 'buy':
            # 设置为当前价格上方0.5%
            new_target = current_price * 1.005
            if new_target < trade_info['take_profit_1']:
                trade_info['take_profit_1'] = new_target
        else:
            # 设置为当前价格下方0.5%
            new_target = current_price * 0.995
            if new_target > trade_info['take_profit_1']:
                trade_info['take_profit_1'] = new_target

    def _check_stop_loss(self, trade_info: Dict[str, Any], current_price: float) -> bool:
        """检查止损"""
        direction = trade_info['direction']
        stop_loss = trade_info['stop_loss']
        
        if direction == 'buy' and current_price <= stop_loss:
            return True
        elif direction == 'sell' and current_price >= stop_loss:
            return True
        
        return False

    def _check_take_profit_with_trend(self, trade_info: Dict[str, Any], current_price: float) -> Optional[str]:
        """检查止盈 - 考虑趋势因素"""
        direction = trade_info['direction']
        tp1 = trade_info['take_profit_1']
        
        # 如果正在趋势跟踪，不使用常规止盈
        if trade_info.get('trend_tracking_active', False):
            return None
        
        if direction == 'buy' and current_price >= tp1:
            return "止盈"
        elif direction == 'sell' and current_price <= tp1:
            return "止盈"
        
        return None

    def _close_position(self, trade_id: str, reason: str):
        """
        平仓 - 修复版本包含完整成本计算 + 🆕 止损后逆转分析
        
        平仓流程:
        1. 计算滑点后出场价格
        2. 计算平仓成本
        3. 执行平仓订单
        4. 🆕 止损特殊处理: 逆转概率分析
        5. 记录完整交易记录
        6. 更新统计信息
        """
        if trade_id not in self.active_trades:
            return
        
        trade_info = self.active_trades[trade_id]
        current_price = self.data.close[0]
        direction = trade_info['direction']
        
        # 1. 计算滑点后的出场价格
        if direction == 'buy':
            actual_exit_price = current_price * (1 - self.slippage_rate)  # 卖出时价格更低
            print(f"   平仓滑点: {current_price:.4f} -> {actual_exit_price:.4f} (-{self.slippage_rate*100:.3f}%)")
        else:
            actual_exit_price = current_price * (1 + self.slippage_rate)  # 买入时价格更高
            print(f"   平仓滑点: {current_price:.4f} -> {actual_exit_price:.4f} (+{self.slippage_rate*100:.3f}%)")
        
        remaining_size = trade_info['size']
        original_size = trade_info['original_size']
        entry_price = trade_info['actual_entry_price']
        
        # 2. 计算平仓成本
        exit_position_value = remaining_size * actual_exit_price
        exit_commission = exit_position_value * self.taker_fee_rate
        exit_slippage_cost = abs(actual_exit_price - current_price) * remaining_size
        
        # 计算实际资金费用（基于实际持仓时间）
        entry_time = trade_info['entry_time']
        exit_time = self.data.datetime.datetime()
        holding_duration = exit_time - entry_time
        holding_hours = holding_duration.total_seconds() / 3600
        funding_periods = max(1, holding_hours / self.funding_interval_hours)  # 至少收取一次
        actual_funding_cost = trade_info['position_value'] * self.funding_rate * funding_periods
        
        # 3. 执行平仓
        try:
            if direction == 'buy':
                self.sell(size=remaining_size)
            else:
                self.buy(size=remaining_size)
            
            # 4. 🆕 止损特殊处理: 分析逆转概率
            if reason == "止损":
                print(f"🔍 [DEBUG] 检测到止损，开始逆转分析...")
                print(f"🔍 [DEBUG] 当前启用反向信号检测: {self.enable_reverse_signal_detection}")
                print(f"🔍 [DEBUG] 持仓时间: {holding_hours:.2f} 小时")
                # 分析趋势逆转概率
                reversal_analysis = self._analyze_trend_reversal_probability(trade_info, holding_hours)
                print(f"🔍 [DEBUG] 逆转分析结果: {reversal_analysis}")

                print(f"📊 止损分析:")
                print(f"   持仓时间: {holding_hours:.1f}小时 ({reversal_analysis['holding_category']})")
                print(f"   波动率状态: {reversal_analysis['volatility_state']}")
                print(f"   逆转概率: {reversal_analysis['reversal_probability']:.1%}")
                print(f"   逆转置信度: {reversal_analysis['reversal_confidence']:.1%}")
                print(f"   建议寻找反向信号: {'是' if reversal_analysis['should_seek_reverse'] else '否'}")
                
                # 记录止损信息（增强版）
                stop_loss_info = {
                    'time': exit_time,
                    'direction': direction,
                    'price': current_price,
                    'trade_id': trade_id,
                    'holding_hours': holding_hours,
                    'reversal_analysis': reversal_analysis,
                    'original_trend': self.current_trend_info.direction.value if self.current_trend_info else 'unknown'
                }
                self.recent_stop_losses.append(stop_loss_info)
                
                # 只保留最近的止损记录
                if len(self.recent_stop_losses) > self.max_recent_stop_losses:
                    self.recent_stop_losses.pop(0)
                
                # 如果逆转概率高，立即重新评估趋势并开启反向信号窗口
                if reversal_analysis['should_seek_reverse']:
                    print(f"🔄 [DEBUG] 高逆转概率，立即更新趋势分析")
                    self._update_trend_analysis()
                    
                    # 设置反向信号检测窗口
                    print(f"🔍 [DEBUG] 设置反向信号检测窗口")
                    self._set_reverse_signal_window(reversal_analysis)
                    print(f"🔍 [DEBUG] 反向信号窗口状态: {self.reverse_signal_active}")
            
            # 5. 计算交易盈亏
            if direction == 'buy':
                # 买入：出场价 > 入场价 = 盈利
                gross_profit_per_unit = actual_exit_price - entry_price
            else:
                # 卖出：入场价 > 出场价 = 盈利  
                gross_profit_per_unit = entry_price - actual_exit_price
            
            # 总毛利润 = 利润每单位 × 原始总仓位
            gross_profit = gross_profit_per_unit * original_size
            
            # 总成本计算
            total_commission = trade_info['entry_commission'] + exit_commission
            total_funding_cost = actual_funding_cost
            total_slippage_cost = trade_info['entry_slippage_cost'] + exit_slippage_cost
            
            total_costs = total_commission + total_funding_cost + total_slippage_cost
            
            # 净利润 = 毛利润 - 总成本
            net_profit = gross_profit - total_costs
            
            # 利润率基于保证金
            profit_pct = (net_profit / trade_info['required_margin']) * 100 if trade_info['required_margin'] > 0 else 0
            
            print(f"💰 平仓成本详情:")
            print(f"   持仓时间: {holding_hours:.1f} 小时")
            print(f"   平仓手续费: {exit_commission:.2f} USDT")
            print(f"   资金费用: {actual_funding_cost:.2f} USDT ({funding_periods:.1f} 次)")
            print(f"   总滑点成本: {total_slippage_cost:.2f} USDT")
            print(f"   总成本: {total_costs:.2f} USDT")
            
            # 安全获取趋势信息
            trend_info = trade_info.get('trend_info')
            if trend_info:
                try:
                    trend_direction = trend_info.direction.value if hasattr(trend_info.direction, 'value') else str(trend_info.direction)
                    trend_strength = trend_info.strength.value if hasattr(trend_info.strength, 'value') else str(trend_info.strength)
                    trend_confidence = trend_info.confidence if hasattr(trend_info, 'confidence') else 0.0
                except Exception as e:
                    print(f"⚠️ 平仓时趋势信息获取失败: {e}")
                    trend_direction = 'unknown'
                    trend_strength = 'unknown'
                    trend_confidence = 0.0
            else:
                trend_direction = 'unknown'
                trend_strength = 'unknown'
                trend_confidence = 0.0
            
            # 6. 完整的交易记录
            trade_record = {
                'trade_id': trade_id,
                'direction': direction,
                'entry_time': entry_time,
                'exit_time': exit_time,
                'holding_hours': holding_hours,
                'entry_price': entry_price,
                'exit_price': actual_exit_price,
                'size': original_size,  # 使用原始仓位大小
                'leverage': trade_info['leverage'],
                'position_value': trade_info['position_value'],
                'required_margin': trade_info['required_margin'],
                'margin_ratio': trade_info['margin_ratio'],
                
                # 完整成本明细
                'commission_costs': total_commission,        # 总手续费 
                'funding_costs': actual_funding_cost,        # 资金费率
                'slippage_costs': total_slippage_cost,       # 滑点成本
                'total_costs': total_costs,                  # 总成本
                
                # 收益信息
                'gross_profit': gross_profit,                # 毛利润
                'profit': net_profit,                        # 净利润 (报告需要这个字段)
                'profit_pct': profit_pct,                    # 基于保证金的收益率
                
                # 其他信息
                'max_profit_seen': trade_info['max_profit_seen'],
                'reason': reason,
                'trend_tracking_used': trade_info.get('trend_tracking_active', False),
                'partial_closed': trade_info.get('partial_close_count', 0) > 0,
                'partial_close_count': trade_info.get('partial_close_count', 0),
                'signal_type': trade_info['signal_type'],
                'signal_strength': trade_info['signal_strength'],
                'confidence_score': trade_info['confidence_score'],
                'trend_direction': trend_direction,
                'trend_strength': trend_strength,
                'trend_confidence': trend_confidence
            }
            
            self.trade_history.append(trade_record)
            
            # 7. 更新统计
            if net_profit > 0:
                self.winning_trades += 1
                self.total_profits += net_profit
                # 统计成功信号
                self.signal_stats['successful_signals'] += 1
                
                # 🆕 如果是反向信号成功，单独统计
                if any(stop['trade_id'] == trade_id for stop in self.recent_stop_losses[-3:]):
                    self.signal_stats['reverse_successful'] += 1
                    print(f"✅ 反向信号交易成功!")
            else:
                self.losing_trades += 1
                self.total_losses += abs(net_profit)
            
            del self.active_trades[trade_id]
            
            print(f"🔄 平仓 {trade_id}: {direction} @ {actual_exit_price:.4f}")
            print(f"    毛利: {gross_profit:.2f} USDT | 净利: {net_profit:.2f} USDT | 利润率: {profit_pct:.2f}%")
            print(f"    成本: {total_costs:.2f} USDT | 原因: {reason}")
            
        except Exception as e:
            print(f"❌ 平仓失败: {e}")

    def _update_account_stats(self):
        """更新账户统计"""
        current_value = self.broker.getvalue()
        
        if current_value > self.account_peak:
            self.account_peak = current_value
        
        drawdown = (self.account_peak - current_value) / self.account_peak
        if drawdown > self.max_dd:
            self.max_dd = drawdown

    def stop(self):
        """
        回测结束处理 - 增强版统计
        
        处理流程:
        1. 平掉所有持仓
        2. 计算信号统计
        3. 输出详细统计报告
        """
        # 1. 平掉所有持仓
        for trade_id in list(self.active_trades.keys()):
            self._close_position(trade_id, "回测结束")
        
        # 2. 计算信号统计
        if self.signal_stats['executed_signals'] > 0:
            self.signal_stats['signal_success_rate'] = (
                self.signal_stats['successful_signals'] / self.signal_stats['executed_signals'] * 100
            )
        
        # 3. 输出详细统计报告
        total_trades = len(self.trade_history)
        trend_tracking_trades = len([t for t in self.trade_history if t.get('trend_tracking_used', False)])
        
        print(f"\n📊 回测结束统计 (止损后反向开仓修复版):")
        print(f"    总交易: {total_trades}")
        print(f"    趋势跟踪交易: {trend_tracking_trades} ({trend_tracking_trades/total_trades*100 if total_trades > 0 else 0:.1f}%)")
        print(f"    盈利交易: {self.winning_trades}")
        print(f"    账户保护激活: {'是' if self.account_protection_active else '否'}")
        
        # 🆕 反向信号统计
        print(f"\n🔄 反向信号统计:")
        print(f"    检测的反向信号: {self.signal_stats['reverse_signals']}")
        print(f"    成功的反向信号: {self.signal_stats['reverse_successful']}")
        if self.signal_stats['reverse_signals'] > 0:
            reverse_success_rate = self.signal_stats['reverse_successful'] / self.signal_stats['reverse_signals'] * 100
            print(f"    反向信号成功率: {reverse_success_rate:.1f}%")
        
        # 止损分析统计
        if self.recent_stop_losses:
            high_prob_stops = len([s for s in self.recent_stop_losses if s['reversal_analysis']['should_seek_reverse']])
            print(f"    总止损次数: {len(self.recent_stop_losses)}")
            print(f"    高逆转概率止损: {high_prob_stops}")
        
        # 信号质量统计输出
        print(f"\n🎯 信号质量统计:")
        print(f"    总检测信号: {self.signal_stats['total_signals']}")
        print(f"    执行信号: {self.signal_stats['executed_signals']}")
        print(f"    信号执行率: {self.signal_stats['executed_signals']/self.signal_stats['total_signals']*100 if self.signal_stats['total_signals'] > 0 else 0:.1f}%")
        print(f"    信号成功率: {self.signal_stats['signal_success_rate']:.1f}%")
        print(f"    高质量信号: {self.signal_stats['high_quality_signals']}")
        print(f"    趋势对齐信号: {self.signal_stats['trend_aligned_signals']}")
        
        if self.trade_history:
            avg_max_profit = np.mean([t['max_profit_seen'] for t in self.trade_history])
            total_commission = sum(t.get('commission_costs', 0) for t in self.trade_history)
            total_funding = sum(t.get('funding_costs', 0) for t in self.trade_history)
            total_slippage = sum(t.get('slippage_costs', 0) for t in self.trade_history)
            
            print(f"    平均最大浮盈: {avg_max_profit:.2f}%")
            print(f"    累计手续费: {total_commission:.2f} USDT")
            print(f"    累计资金费率: {total_funding:.2f} USDT")
            print(f"    累计滑点成本: {total_slippage:.2f} USDT")
            print(f"    总交易成本: {total_commission + total_funding + total_slippage:.2f} USDT")


def run_enhanced_backtest(data: pd.DataFrame, trading_params: TradingParams, 
                         backtest_params: BacktestParams,
                         detector_config: Dict[str, Any] = None,
                         use_dynamic_leverage: bool = False) -> Dict[str, Any]:
    """
    运行增强版回测 - 趋势跟踪版（修复版）
    
    Args:
        data: 历史价格数据
        trading_params: 交易参数
        backtest_params: 回测参数
        detector_config: 信号检测器配置
        use_dynamic_leverage: 是否使用动态杠杆
        
    Returns:
        Dict: 完整的回测结果包含新增的反向信号统计
    """
    print(f"🚀 开始趋势跟踪版回测: {backtest_params.symbol} {backtest_params.interval}")
    
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
    
    # 详细统计 - 修复版本包含完整成本信息
    total_trades = len(strategy.trade_history)
    
    if total_trades > 0:
        win_rate = (strategy.winning_trades / total_trades * 100)
        avg_profit = strategy.total_profits / strategy.winning_trades if strategy.winning_trades > 0 else 0
        avg_loss = strategy.total_losses / strategy.losing_trades if strategy.losing_trades > 0 else 0
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
        
        # 趋势跟踪相关统计
        trend_trades = [t for t in strategy.trade_history if t.get('trend_tracking_used', False)]
        trend_win_rate = len([t for t in trend_trades if t['profit'] > 0]) / len(trend_trades) * 100 if trend_trades else 0
        
        # 成本和保证金统计
        leverages = []
        margin_ratios = []
        margin_amounts = []
        position_values = []
        
        for trade in strategy.trade_history:
            if 'leverage' in trade and trade['leverage'] > 0:
                leverages.append(trade['leverage'])
            
            if 'margin_ratio' in trade and trade['margin_ratio'] >= 0:  # 过滤负数
                margin_ratios.append(trade['margin_ratio'])
            
            if 'required_margin' in trade and trade['required_margin'] >= 0:  # 过滤负数
                margin_amounts.append(trade['required_margin'])
            
            if 'position_value' in trade and trade['position_value'] > 0:
                position_values.append(trade['position_value'])
        
         # 计算统计值
        avg_leverage = np.mean(leverages) if leverages else 1.0
        max_leverage = max(leverages) if leverages else 1.0
        avg_margin_ratio = np.mean(margin_ratios) if margin_ratios else 0.0
        max_margin_ratio = max(margin_ratios) if margin_ratios else 0.0
        total_margin_used = sum(margin_amounts) if margin_amounts else 0.0
        total_position_value = sum(position_values) if position_values else 0.0
        
        # 分别统计盈利和亏损交易的保证金使用
        profitable_trades = [t for t in strategy.trade_history if t.get('profit', 0) > 0]
        losing_trades = [t for t in strategy.trade_history if t.get('profit', 0) <= 0]
        
        avg_margin_profitable = np.mean([t.get('margin_ratio', 0) for t in profitable_trades if t.get('margin_ratio', 0) >= 0]) if profitable_trades else 0.0
        avg_margin_losing = np.mean([t.get('margin_ratio', 0) for t in losing_trades if t.get('margin_ratio', 0) >= 0]) if losing_trades else 0.0
        
        # 成本统计
        commissions = [t.get('commission_costs', 0) for t in strategy.trade_history]
        funding_costs = [t.get('funding_costs', 0) for t in strategy.trade_history]
        slippage_costs = [t.get('slippage_costs', 0) for t in strategy.trade_history]
        
        total_commission = sum(commissions)
        total_funding = sum(funding_costs)
        total_slippage = sum(slippage_costs)
        total_costs = total_commission + total_funding + total_slippage

        # 最大浮盈统计
        max_profits_seen = [t.get('max_profit_seen', 0) for t in strategy.trade_history]
        avg_max_profit = np.mean(max_profits_seen)
        
        # 部分平仓统计
        partial_trades = [t for t in strategy.trade_history if t.get('partial_closed', False)]
        partial_close_rate = len(partial_trades) / total_trades * 100 if total_trades > 0 else 0
        
        print(f"📊 保证金使用统计:")
        print(f"   平均杠杆: {avg_leverage:.1f}x (最高: {max_leverage:.1f}x)")
        print(f"   平均保证金占用: {avg_margin_ratio:.1f}% (最高: {max_margin_ratio:.1f}%)")
        print(f"   盈利交易平均保证金: {avg_margin_profitable:.1f}%")
        print(f"   亏损交易平均保证金: {avg_margin_losing:.1f}%")
        print(f"   总保证金使用: {total_margin_used:.2f} USDT")
        print(f"   总仓位价值: {total_position_value:.2f} USDT")
    else:
        # 无交易时的默认值
        win_rate = profit_factor = trend_win_rate = 0
        avg_leverage = max_leverage = 1.0
        avg_margin_ratio = max_margin_ratio = 0.0
        avg_margin_profitable = avg_margin_losing = 0.0
        total_margin_used = total_position_value = 0.0
        avg_max_profit = 0
        total_commission = total_funding = total_slippage = total_costs = 0
        partial_close_rate = 0
    
    # 🆕 反向信号统计
    reverse_signal_stats = {
        'reverse_signals_detected': strategy.signal_stats.get('reverse_signals', 0),
        'reverse_signals_successful': strategy.signal_stats.get('reverse_successful', 0),
        'reverse_signal_success_rate': 0.0
    }
    
    if reverse_signal_stats['reverse_signals_detected'] > 0:
        reverse_signal_stats['reverse_signal_success_rate'] = (
            reverse_signal_stats['reverse_signals_successful'] / 
            reverse_signal_stats['reverse_signals_detected'] * 100
        )
    
    # 返回完整结果包含成本分析和反向信号统计
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
        
         # 修复后的杠杆和保证金信息
        'avg_leverage': avg_leverage,
        'max_leverage': max_leverage,
        'avg_margin_usage': avg_margin_ratio,
        'max_margin_usage': max_margin_ratio,
        'avg_margin_profitable_trades': avg_margin_profitable,
        'avg_margin_losing_trades': avg_margin_losing,
        'total_margin_used': total_margin_used,
        'total_position_value': total_position_value,
        'margin_efficiency': total_position_value / total_margin_used if total_margin_used > 0 else 0,
        
        # 成本分析
        'total_commission': total_commission,
        'total_funding': total_funding,
        'total_slippage': total_slippage,
        'total_costs': total_costs,
        'avg_commission_per_trade': total_commission / total_trades if total_trades > 0 else 0,
        'avg_funding_per_trade': total_funding / total_trades if total_trades > 0 else 0,
        
        # 趋势跟踪统计
        'avg_max_profit_seen': avg_max_profit,
        'trend_tracking_win_rate': trend_win_rate,
        'trend_tracking_trades': len([t for t in strategy.trade_history if t.get('trend_tracking_used', False)]),
        'partial_close_rate': partial_close_rate,
        
        # 🆕 反向信号统计
        'reverse_signal_stats': reverse_signal_stats,
        
        # 信号质量统计
        'signal_stats': {
            'total_signals': strategy.signal_stats['total_signals'],
            'executed_signals': strategy.signal_stats['executed_signals'],
            'signal_execution_rate': strategy.signal_stats['executed_signals']/strategy.signal_stats['total_signals']*100 if strategy.signal_stats['total_signals'] > 0 else 0,
            'signal_success_rate': strategy.signal_stats['signal_success_rate'],
            'high_quality_signals': strategy.signal_stats['high_quality_signals'],
            'trend_aligned_signals': strategy.signal_stats['trend_aligned_signals'],
            'avg_signal_strength': np.mean(strategy.signal_stats['signal_strengths']) if strategy.signal_stats['signal_strengths'] else 0,
            'avg_confidence_score': np.mean(strategy.signal_stats['confidence_scores']) if strategy.signal_stats['confidence_scores'] else 0
        },
        
        # 原有数据
        'trades': strategy.trade_history,
        'account_protection_triggered': strategy.account_protection_active,
        'use_dynamic_leverage': use_dynamic_leverage,
        'trend_tracking_enabled': True
    }