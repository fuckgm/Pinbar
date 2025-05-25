#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📄 文件名: optimized_signal_detector.py
📁 位置: 项目根目录

优化的Pinbar信号检测器
专门针对趋势转折点和关键阻力支撑位的信号识别
用于替换原有的 enhanced_signal_generator.py 中的检测逻辑
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class PinbarType(Enum):
    """Pinbar类型"""
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    NONE = "none"

class MarketContext(Enum):
    """市场环境"""
    TREND_REVERSAL = "trend_reversal"      # 趋势反转
    PULLBACK_ENTRY = "pullback_entry"      # 回调入场
    BREAKOUT_RETEST = "breakout_retest"    # 突破回踩
    SUPPORT_RESISTANCE = "support_resistance"  # 支撑阻力

@dataclass
class OptimizedPinbarSignal:
    """优化的Pinbar信号"""
    index: int
    timestamp: datetime
    type: PinbarType
    direction: str  # 'buy' or 'sell'
    
    # 价格信息
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    
    # Pinbar质量评估
    shadow_body_ratio: float
    body_candle_ratio: float
    candle_size_pct: float
    
    # 市场环境分析
    market_context: MarketContext
    trend_alignment: bool
    key_level_proximity: float
    
    # 信号强度评分
    technical_score: float      # 技术指标得分 (0-5)
    context_score: float        # 市场环境得分 (0-5)
    quality_score: float        # Pinbar质量得分 (0-5)
    final_score: float          # 综合得分 (0-15)
    
    # 交易参数
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_reward_ratio: float
    
    # 确认信息
    volume_confirmation: bool
    momentum_confirmation: bool
    pattern_confirmation: bool
    
    # 执行建议
    recommended_position_size: float
    confidence_level: str  # 'low', 'medium', 'high', 'very_high'
    entry_reason: str

class OptimizedPinbarDetector:
    """优化的Pinbar检测器 - 专注于关键转折点"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._get_default_config()
        
        # 关键技术指标周期
        self.trend_period = self.config.get('trend_period', 20)
        self.rsi_period = self.config.get('rsi_period', 14)
        self.atr_period = self.config.get('atr_period', 14)
        self.volume_period = self.config.get('volume_period', 20)
        
        # Pinbar识别参数 - 放宽标准
        self.min_shadow_body_ratio = self.config.get('min_shadow_body_ratio', 1.5)  # 从2.0降低
        self.max_body_ratio = self.config.get('max_body_ratio', 0.4)  # 从0.35提高
        self.min_candle_size = self.config.get('min_candle_size', 0.002)  # 从0.003降低
        
        # 市场环境参数
        self.key_level_tolerance = self.config.get('key_level_tolerance', 0.015)  # 1.5%
        self.trend_strength_threshold = self.config.get('trend_strength_threshold', 0.02)  # 2%
        self.reversal_confirmation_bars = self.config.get('reversal_confirmation_bars', 3)
        
        # 信号质量阈值 - 降低要求
        self.min_technical_score = self.config.get('min_technical_score', 2.0)  # 从3.0降低
        self.min_final_score = self.config.get('min_final_score', 6.0)  # 从9.0降低
        
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'trend_period': 20,
            'rsi_period': 14,
            'atr_period': 14,
            'volume_period': 20,
            'min_shadow_body_ratio': 1.5,
            'max_body_ratio': 0.4,
            'min_candle_size': 0.002,
            'key_level_tolerance': 0.015,
            'trend_strength_threshold': 0.02,
            'reversal_confirmation_bars': 3,
            'min_technical_score': 2.0,
            'min_final_score': 6.0,
            # 新增关键转折点识别参数
            'pivot_lookback': 10,  # 转折点回望周期
            'momentum_threshold': 0.05,  # 动量阈值
            'volume_spike_threshold': 1.5,  # 成交量异常阈值
            'multi_timeframe_confirmation': True,  # 多时间框架确认
        }
    
    def detect_optimized_signals(self, df: pd.DataFrame) -> List[OptimizedPinbarSignal]:
        """检测优化的Pinbar信号 - 主入口函数"""
        if len(df) < 50:
            return []
        
        # 计算技术指标
        df_enhanced = self._calculate_enhanced_indicators(df.copy())
        
        # 识别关键价位
        df_enhanced = self._identify_key_levels(df_enhanced)
        
        # 分析市场结构
        df_enhanced = self._analyze_market_structure(df_enhanced)
        
        signals = []
        
        # 扫描每根K线寻找Pinbar模式
        for i in range(50, len(df_enhanced) - 1):  # 预留缓冲区
            pinbar_type = self._detect_pinbar_pattern(df_enhanced, i)
            
            if pinbar_type != PinbarType.NONE:
                signal = self._analyze_signal_quality(df_enhanced, i, pinbar_type)
                
                if signal and self._validate_signal(signal, df_enhanced, i):
                    signals.append(signal)
        
        # 过滤和排序信号
        filtered_signals = self._filter_and_rank_signals(signals, df_enhanced)
        
        return filtered_signals
    
    def _calculate_enhanced_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算增强技术指标"""
        
        # 基础移动平均线
        df['sma_fast'] = df['close'].rolling(window=10).mean()
        df['sma_slow'] = df['close'].rolling(window=self.trend_period).mean()
        df['ema_fast'] = df['close'].ewm(span=12).mean()
        df['ema_slow'] = df['close'].ewm(span=26).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR - 真实波动范围
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = np.abs(df['high'] - df['close'].shift(1))
        df['low_close'] = np.abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['true_range'].rolling(window=self.atr_period).mean()
        
        # 布林带
        bb_period = 20
        df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
        bb_std = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 成交量指标
        df['volume_sma'] = df['volume'].rolling(window=self.volume_period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # MACD
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # 动量指标
        df['momentum'] = df['close'].pct_change(periods=10)
        df['roc'] = ((df['close'] - df['close'].shift(14)) / df['close'].shift(14)) * 100
        
        # 价格位置指标
        lookback = 20
        df['highest_high'] = df['high'].rolling(window=lookback).max()
        df['lowest_low'] = df['low'].rolling(window=lookback).min()
        df['price_position'] = (df['close'] - df['lowest_low']) / (df['highest_high'] - df['lowest_low'])
        
        return df
    
    def _identify_key_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """识别关键支撑阻力位"""
        lookback = self.config.get('pivot_lookback', 10)
        
        # 识别转折点
        df['pivot_high'] = False
        df['pivot_low'] = False
        df['resistance_level'] = np.nan
        df['support_level'] = np.nan
        
        for i in range(lookback, len(df) - lookback):
            # 寻找局部高点
            if df['high'].iloc[i] == df['high'].iloc[i-lookback:i+lookback+1].max():
                df.loc[df.index[i], 'pivot_high'] = True
                # 将这个高点作为阻力位向前传播
                for j in range(i, min(i + 50, len(df))):
                    if pd.isna(df['resistance_level'].iloc[j]):
                        df.loc[df.index[j], 'resistance_level'] = df['high'].iloc[i]
            
            # 寻找局部低点
            if df['low'].iloc[i] == df['low'].iloc[i-lookback:i+lookback+1].min():
                df.loc[df.index[i], 'pivot_low'] = True
                # 将这个低点作为支撑位向前传播
                for j in range(i, min(i + 50, len(df))):
                    if pd.isna(df['support_level'].iloc[j]):
                        df.loc[df.index[j], 'support_level'] = df['low'].iloc[i]
        
        # 计算距离关键位的距离
        df['resistance_distance'] = abs(df['close'] - df['resistance_level']) / df['close']
        df['support_distance'] = abs(df['close'] - df['support_level']) / df['close']
        df['key_level_proximity'] = np.minimum(df['resistance_distance'], df['support_distance'])
        
        return df
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        """分析市场结构"""
        
        # 趋势强度分析
        df['trend_strength'] = abs(df['close'] - df['sma_slow']) / df['close']
        df['trend_direction'] = np.where(df['close'] > df['sma_slow'], 1, -1)
        
        # 趋势一致性
        df['ma_alignment'] = np.where(
            (df['sma_fast'] > df['sma_slow']) & (df['close'] > df['sma_fast']), 1,
            np.where((df['sma_fast'] < df['sma_slow']) & (df['close'] < df['sma_fast']), -1, 0)
        )
        
        # 价格动量
        df['price_momentum'] = df['close'].pct_change(periods=5).rolling(window=3).mean()
        
        # 超买超卖状态
        df['oversold'] = df['rsi'] < 30
        df['overbought'] = df['rsi'] > 70
        df['rsi_extreme'] = df['oversold'] | df['overbought']
        
        # 波动性分析
        df['volatility'] = df['atr'] / df['close']
        df['volatility_rank'] = df['volatility'].rolling(window=50).rank(pct=True)
        
        # 成交量确认
        df['volume_confirmation'] = df['volume_ratio'] > 1.2
        
        return df
    
    def _detect_pinbar_pattern(self, df: pd.DataFrame, i: int) -> PinbarType:
        """检测Pinbar模式 - 放宽识别标准"""
        
        if i < 1 or i >= len(df):
            return PinbarType.NONE
        
        current = df.iloc[i]
        
        # 基础价格数据
        open_price = current['open']
        high_price = current['high']
        low_price = current['low']
        close_price = current['close']
        
        # 计算K线各部分长度
        body_size = abs(close_price - open_price)
        candle_range = high_price - low_price
        upper_shadow = high_price - max(open_price, close_price)
        lower_shadow = min(open_price, close_price) - low_price
        
        # 避免除零错误
        if candle_range == 0 or body_size == 0:
            return PinbarType.NONE
        
        # 计算比例
        body_candle_ratio = body_size / candle_range
        upper_shadow_body_ratio = upper_shadow / body_size if body_size > 0 else 0
        lower_shadow_body_ratio = lower_shadow / body_size if body_size > 0 else 0
        
        # K线大小检查（相对于ATR）
        atr_value = current['atr']
        candle_size_pct = candle_range / current['close']
        
        # 放宽的Pinbar识别标准
        min_shadow_ratio = self.min_shadow_body_ratio
        max_body_ratio = self.max_body_ratio
        min_size = self.min_candle_size
        
        # 动态调整标准（在关键位置放宽标准）
        if current['key_level_proximity'] < 0.01:  # 靠近关键位
            min_shadow_ratio *= 0.8  # 放宽20%
            max_body_ratio *= 1.2    # 放宽20%
        
        if current['rsi_extreme']:  # 极端RSI区域
            min_shadow_ratio *= 0.7  # 放宽30%
            max_body_ratio *= 1.3    # 放宽30%
        
        # 检测锤形线（看涨）
        if (lower_shadow_body_ratio >= min_shadow_ratio and 
            body_candle_ratio <= max_body_ratio and
            upper_shadow_body_ratio <= 0.3 and  # 上影线不能太长
            candle_size_pct >= min_size):
            
            # 额外的锤形线确认
            if self._confirm_hammer_context(df, i):
                return PinbarType.HAMMER
        
        # 检测射击线（看跌）
        if (upper_shadow_body_ratio >= min_shadow_ratio and 
            body_candle_ratio <= max_body_ratio and
            lower_shadow_body_ratio <= 0.3 and  # 下影线不能太长
            candle_size_pct >= min_size):
            
            # 额外的射击线确认
            if self._confirm_shooting_star_context(df, i):
                return PinbarType.SHOOTING_STAR
        
        return PinbarType.NONE
    
    def _confirm_hammer_context(self, df: pd.DataFrame, i: int) -> bool:
        """确认锤形线的市场环境"""
        current = df.iloc[i]
        
        # 基础确认条件
        confirmations = 0
        
        # 1. 下跌趋势或支撑位确认
        if (current['trend_direction'] == -1 or  # 下跌趋势
            current['support_distance'] < 0.01 or  # 靠近支撑
            current['oversold']):  # 超卖
            confirmations += 1
        
        # 2. 价格位置确认
        if current['price_position'] < 0.3:  # 在区间下方
            confirmations += 1
        
        # 3. 动量背离确认
        if len(df) > i + 3:
            recent_lows = df['low'].iloc[i-3:i+1].min()
            if current['low'] <= recent_lows:  # 创新低
                confirmations += 1
        
        # 4. 成交量确认
        if current['volume_ratio'] > 1.0:  # 成交量放大
            confirmations += 1
        
        return confirmations >= 2  # 至少2个确认条件
    
    def _confirm_shooting_star_context(self, df: pd.DataFrame, i: int) -> bool:
        """确认射击线的市场环境"""
        current = df.iloc[i]
        
        # 基础确认条件
        confirmations = 0
        
        # 1. 上涨趋势或阻力位确认
        if (current['trend_direction'] == 1 or  # 上涨趋势
            current['resistance_distance'] < 0.01 or  # 靠近阻力
            current['overbought']):  # 超买
            confirmations += 1
        
        # 2. 价格位置确认
        if current['price_position'] > 0.7:  # 在区间上方
            confirmations += 1
        
        # 3. 动量背离确认
        if len(df) > i + 3:
            recent_highs = df['high'].iloc[i-3:i+1].max()
            if current['high'] >= recent_highs:  # 创新高
                confirmations += 1
        
        # 4. 成交量确认
        if current['volume_ratio'] > 1.0:  # 成交量放大
            confirmations += 1
        
        return confirmations >= 2  # 至少2个确认条件
    
    def _analyze_signal_quality(self, df: pd.DataFrame, i: int, pinbar_type: PinbarType) -> Optional[OptimizedPinbarSignal]:
        """分析信号质量"""
        
        if i < 10 or i >= len(df) - 5:
            return None
        
        current = df.iloc[i]
        
        # 确定方向
        direction = 'buy' if pinbar_type == PinbarType.HAMMER else 'sell'
        
        # 计算Pinbar质量分数
        quality_score = self._calculate_pinbar_quality(df, i, pinbar_type)
        
        # 计算技术指标分数
        technical_score = self._calculate_technical_score(df, i, direction)
        
        # 计算市场环境分数
        context_score = self._calculate_context_score(df, i, direction)
        
        # 综合评分
        final_score = quality_score + technical_score + context_score
        
        # 基础过滤
        if technical_score < self.min_technical_score or final_score < self.min_final_score:
            return None
        
        # 计算交易参数
        entry_price, stop_loss, take_profits = self._calculate_trade_levels(df, i, direction)
        
        if not entry_price or not stop_loss:
            return None
        
        # 计算风险回报比
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profits[0] - entry_price) if take_profits[0] else risk * 2
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # 确定市场环境
        market_context = self._determine_market_context(df, i, direction)
        
        # 各种确认
        volume_confirmation = current['volume_ratio'] > 1.1
        momentum_confirmation = self._check_momentum_confirmation(df, i, direction)
        pattern_confirmation = self._check_pattern_confirmation(df, i, pinbar_type)
        
        # 趋势对齐
        trend_alignment = self._check_trend_alignment(df, i, direction)
        
        # 信号置信度
        confidence_level = self._determine_confidence_level(final_score, risk_reward_ratio)
        
        # 入场理由
        entry_reason = self._generate_entry_reason(df, i, direction, market_context)
        
        return OptimizedPinbarSignal(
            index=i,
            timestamp=current['timestamp'] if 'timestamp' in current else pd.Timestamp.now(),
            type=pinbar_type,
            direction=direction,
            
            # 价格信息
            open_price=current['open'],
            high_price=current['high'],
            low_price=current['low'],
            close_price=current['close'],
            
            # Pinbar质量
            shadow_body_ratio=self._get_shadow_body_ratio(current, direction),
            body_candle_ratio=abs(current['close'] - current['open']) / (current['high'] - current['low']),
            candle_size_pct=(current['high'] - current['low']) / current['close'],
            
            # 市场环境
            market_context=market_context,
            trend_alignment=trend_alignment,
            key_level_proximity=current['key_level_proximity'],
            
            # 评分
            technical_score=technical_score,
            context_score=context_score,
            quality_score=quality_score,
            final_score=final_score,
            
            # 交易参数
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profits[0],
            take_profit_2=take_profits[1],
            take_profit_3=take_profits[2],
            risk_reward_ratio=risk_reward_ratio,
            
            # 确认信息
            volume_confirmation=volume_confirmation,
            momentum_confirmation=momentum_confirmation,
            pattern_confirmation=pattern_confirmation,
            
            # 执行建议
            recommended_position_size=self._calculate_position_size(risk_reward_ratio, final_score),
            confidence_level=confidence_level,
            entry_reason=entry_reason
        )
    
    def _calculate_pinbar_quality(self, df: pd.DataFrame, i: int, pinbar_type: PinbarType) -> float:
        """计算Pinbar质量分数 (0-5)"""
        current = df.iloc[i]
        
        body_size = abs(current['close'] - current['open'])
        candle_range = current['high'] - current['low']
        
        if candle_range == 0:
            return 0
        
        score = 0.0
        
        # 1. 影线长度评分 (0-2分)
        if pinbar_type == PinbarType.HAMMER:
            lower_shadow = min(current['open'], current['close']) - current['low']
            shadow_ratio = lower_shadow / body_size if body_size > 0 else 0
        else:
            upper_shadow = current['high'] - max(current['open'], current['close'])
            shadow_ratio = upper_shadow / body_size if body_size > 0 else 0
        
        if shadow_ratio >= 3.0:
            score += 2.0
        elif shadow_ratio >= 2.0:
            score += 1.5
        elif shadow_ratio >= 1.5:
            score += 1.0
        
        # 2. 实体大小评分 (0-1.5分)
        body_ratio = body_size / candle_range
        if body_ratio <= 0.2:
            score += 1.5
        elif body_ratio <= 0.3:
            score += 1.0
        elif body_ratio <= 0.4:
            score += 0.5
        
        # 3. K线相对大小评分 (0-1.5分)
        atr_value = current['atr']
        if atr_value > 0:
            size_ratio = candle_range / atr_value
            if size_ratio >= 1.5:
                score += 1.5
            elif size_ratio >= 1.0:
                score += 1.0
            elif size_ratio >= 0.7:
                score += 0.5
        
        return min(score, 5.0)
    
    def _calculate_technical_score(self, df: pd.DataFrame, i: int, direction: str) -> float:
        """计算技术指标分数 (0-5)"""
        current = df.iloc[i]
        score = 0.0
        
        # 1. RSI评分 (0-1.5分)
        rsi = current['rsi']
        if direction == 'buy':
            if rsi <= 25:
                score += 1.5
            elif rsi <= 35:
                score += 1.0
            elif rsi <= 45:
                score += 0.5
        else:
            if rsi >= 75:
                score += 1.5
            elif rsi >= 65:
                score += 1.0
            elif rsi >= 55:
                score += 0.5
        
        # 2. 布林带位置评分 (0-1分)
        bb_pos = current['bb_position']
        if direction == 'buy' and bb_pos <= 0.2:
            score += 1.0
        elif direction == 'sell' and bb_pos >= 0.8:
            score += 1.0
        elif direction == 'buy' and bb_pos <= 0.4:
            score += 0.5
        elif direction == 'sell' and bb_pos >= 0.6:
            score += 0.5
        
        # 3. MACD评分 (0-1分)
        macd_hist = current['macd_histogram']
        if direction == 'buy' and macd_hist > 0:
            score += 1.0
        elif direction == 'sell' and macd_hist < 0:
            score += 1.0
        elif direction == 'buy' and macd_hist > -0.001:
            score += 0.5
        elif direction == 'sell' and macd_hist < 0.001:
            score += 0.5
        
        # 4. 价格位置评分 (0-1分)
        price_pos = current['price_position']
        if direction == 'buy' and price_pos <= 0.3:
            score += 1.0
        elif direction == 'sell' and price_pos >= 0.7:
            score += 1.0
        elif direction == 'buy' and price_pos <= 0.5:
            score += 0.5
        elif direction == 'sell' and price_pos >= 0.5:
            score += 0.5
        
        # 5. 成交量确认 (0-0.5分)
        if current['volume_ratio'] > 1.2:
            score += 0.5
        elif current['volume_ratio'] > 1.0:
            score += 0.25
        
        return min(score, 5.0)
    
    def _calculate_context_score(self, df: pd.DataFrame, i: int, direction: str) -> float:
        """计算市场环境分数 (0-5)"""
        current = df.iloc[i]
        score = 0.0
        
        # 1. 关键位置评分 (0-2分)
        if current['key_level_proximity'] < 0.005:  # 0.5%以内
            score += 2.0
        elif current['key_level_proximity'] < 0.01:  # 1%以内
            score += 1.5
        elif current['key_level_proximity'] < 0.02:  # 2%以内
            score += 1.0
        
        # 2. 趋势对齐评分 (0-1.5分)
        trend_dir = current['trend_direction']
        ma_align = current['ma_alignment']
        
        if direction == 'buy':
            if trend_dir == 1 and ma_align == 1:
                score += 1.5  # 完全对齐
            elif trend_dir == 1 or ma_align == 1:
                score += 1.0  # 部分对齐
            elif trend_dir == -1 and current['oversold']:
                score += 1.0  # 反转机会
        else:
            if trend_dir == -1 and ma_align == -1:
                score += 1.5  # 完全对齐
            elif trend_dir == -1 or ma_align == -1:
                score += 1.0  # 部分对齐
            elif trend_dir == 1 and current['overbought']:
                score += 1.0  # 反转机会
        
        # 3. 动量背离评分 (0-1分)
        if i >= 5:
            momentum_div = self._check_momentum_divergence(df, i, direction)
            if momentum_div:
                score += 1.0
            elif self._check_momentum_slowdown(df, i, direction):
                score += 0.5
        
        # 4. 波动性评分 (0-0.5分)
        vol_rank = current['volatility_rank']
        if 0.3 <= vol_rank <= 0.8:  # 适中的波动性
            score += 0.5
        elif 0.2 <= vol_rank <= 0.9:
            score += 0.25
        
        return min(score, 5.0)
    
    def _check_momentum_divergence(self, df: pd.DataFrame, i: int, direction: str) -> bool:
        """检查动量背离"""
        if i < 10:
            return False
        
        current_momentum = df['momentum'].iloc[i]
        past_momentum = df['momentum'].iloc[i-5:i].mean()
        
        if direction == 'buy':
            # 价格新低但动量没有新低
            current_low = df['low'].iloc[i]
            past_low = df['low'].iloc[i-10:i].min()
            return current_low <= past_low and current_momentum > past_momentum
        else:
            # 价格新高但动量没有新高
            current_high = df['high'].iloc[i]
            past_high = df['high'].iloc[i-10:i].max()
            return current_high >= past_high and current_momentum < past_momentum
    
    def _check_momentum_slowdown(self, df: pd.DataFrame, i: int, direction: str) -> bool:
        """检查动量放缓"""
        if i < 5:
            return False
        
        recent_momentum = df['momentum'].iloc[i-3:i+1].mean()
        past_momentum = df['momentum'].iloc[i-8:i-3].mean()
        
        if direction == 'buy':
            return recent_momentum > past_momentum  # 下跌动量减缓
        else:
            return recent_momentum < past_momentum  # 上涨动量减缓
    
    def _calculate_trade_levels(self, df: pd.DataFrame, i: int, direction: str) -> Tuple[float, float, List[float]]:
        """计算交易价位"""
        current = df.iloc[i]
        atr = current['atr']
        
        if direction == 'buy':
            entry_price = current['close']
            stop_loss = current['low'] - atr * 0.5
            
            # 多级止盈
            tp1 = entry_price + (entry_price - stop_loss) * 1.5
            tp2 = entry_price + (entry_price - stop_loss) * 2.5
            tp3 = entry_price + (entry_price - stop_loss) * 4.0
            
        else:
            entry_price = current['close']
            stop_loss = current['high'] + atr * 0.5
            
            # 多级止盈
            tp1 = entry_price - (stop_loss - entry_price) * 1.5
            tp2 = entry_price - (stop_loss - entry_price) * 2.5
            tp3 = entry_price - (stop_loss - entry_price) * 4.0
        
        return entry_price, stop_loss, [tp1, tp2, tp3]
    
    def _get_shadow_body_ratio(self, candle: pd.Series, direction: str) -> float:
        """获取影线实体比"""
        body_size = abs(candle['close'] - candle['open'])
        
        if direction == 'buy':
            shadow = min(candle['open'], candle['close']) - candle['low']
        else:
            shadow = candle['high'] - max(candle['open'], candle['close'])
        
        return shadow / body_size if body_size > 0 else 0
    
    def _determine_market_context(self, df: pd.DataFrame, i: int, direction: str) -> MarketContext:
        """确定市场环境"""
        current = df.iloc[i]
        
        # 检查是否在关键位置
        if current['key_level_proximity'] < 0.01:
            return MarketContext.SUPPORT_RESISTANCE
        
        # 检查趋势状态
        trend_strength = current['trend_strength']
        trend_dir = current['trend_direction']
        
        if trend_strength > 0.03:  # 强趋势
            if (direction == 'buy' and trend_dir == -1) or (direction == 'sell' and trend_dir == 1):
                return MarketContext.TREND_REVERSAL
            else:
                return MarketContext.PULLBACK_ENTRY
        else:
            return MarketContext.BREAKOUT_RETEST
    
    def _check_trend_alignment(self, df: pd.DataFrame, i: int, direction: str) -> bool:
        """检查趋势对齐"""
        current = df.iloc[i]
        
        # 多重趋势确认
        sma_trend = current['close'] > current['sma_slow']
        ema_trend = current['ema_fast'] > current['ema_slow']
        ma_align = current['ma_alignment']
        
        if direction == 'buy':
            return sma_trend or ema_trend or ma_align >= 0
        else:
            return not sma_trend or not ema_trend or ma_align <= 0
    
    def _check_momentum_confirmation(self, df: pd.DataFrame, i: int, direction: str) -> bool:
        """检查动量确认"""
        if i < 3:
            return False
        
        current_momentum = df['momentum'].iloc[i]
        
        if direction == 'buy':
            return current_momentum > -0.02  # 下跌动量减缓
        else:
            return current_momentum < 0.02   # 上涨动量减缓
    
    def _check_pattern_confirmation(self, df: pd.DataFrame, i: int, pinbar_type: PinbarType) -> bool:
        """检查模式确认"""
        if i < 2 or i >= len(df) - 1:
            return False
        
        # 检查后续确认
        next_candle = df.iloc[i + 1]
        current = df.iloc[i]
        
        if pinbar_type == PinbarType.HAMMER:
            # 锤形线后应该有上涨确认
            return next_candle['close'] > current['close']
        else:
            # 射击线后应该有下跌确认
            return next_candle['close'] < current['close']
    
    def _determine_confidence_level(self, final_score: float, risk_reward: float) -> str:
        """确定信号置信度"""
        if final_score >= 12 and risk_reward >= 3.0:
            return 'very_high'
        elif final_score >= 10 and risk_reward >= 2.5:
            return 'high'
        elif final_score >= 8 and risk_reward >= 2.0:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_position_size(self, risk_reward: float, final_score: float) -> float:
        """计算建议仓位大小"""
        base_size = 0.02  # 基础2%
        
        # 根据风险回报比调整
        rr_multiplier = min(risk_reward / 2.0, 2.0)
        
        # 根据信号质量调整
        quality_multiplier = min(final_score / 10.0, 1.5)
        
        return base_size * rr_multiplier * quality_multiplier
    
    def _generate_entry_reason(self, df: pd.DataFrame, i: int, direction: str, context: MarketContext) -> str:
        """生成入场理由"""
        current = df.iloc[i]
        reasons = []
        
        # 基础模式
        pattern_name = "锤形线" if direction == 'buy' else "射击线"
        reasons.append(f"{pattern_name}反转信号")
        
        # 市场环境
        if context == MarketContext.SUPPORT_RESISTANCE:
            level_type = "支撑位" if direction == 'buy' else "阻力位"
            reasons.append(f"关键{level_type}确认")
        elif context == MarketContext.TREND_REVERSAL:
            reasons.append("趋势反转信号")
        elif context == MarketContext.PULLBACK_ENTRY:
            reasons.append("趋势回调入场")
        
        # RSI确认
        if current['oversold'] and direction == 'buy':
            reasons.append("RSI超卖反弹")
        elif current['overbought'] and direction == 'sell':
            reasons.append("RSI超买回调")
        
        # 成交量确认
        if current['volume_ratio'] > 1.3:
            reasons.append("放量确认")
        
        return " + ".join(reasons)
    
    def _validate_signal(self, signal: OptimizedPinbarSignal, df: pd.DataFrame, i: int) -> bool:
        """验证信号有效性"""
        
        # 基础验证
        if signal.risk_reward_ratio < 1.0:
            return False
        
        if signal.final_score < self.min_final_score:
            return False
        
        # 避免过于密集的信号
        if i >= 10:
            recent_signals = self._count_recent_signals(df, i, 10)
            if recent_signals > 2:  # 10根K线内不超过2个信号
                return False
        
        return True
    
    def _count_recent_signals(self, df: pd.DataFrame, current_i: int, lookback: int) -> int:
        """统计最近的信号数量"""
        # 这里需要额外的逻辑来跟踪历史信号
        # 简化实现，返回0
        return 0
    
    def _filter_and_rank_signals(self, signals: List[OptimizedPinbarSignal], df: pd.DataFrame) -> List[OptimizedPinbarSignal]:
        """过滤和排序信号"""
        if not signals:
            return []
        
        # 按最终得分排序
        signals.sort(key=lambda x: x.final_score, reverse=True)
        
        # 过滤重复信号（同方向且时间接近）
        filtered_signals = []
        
        for signal in signals:
            should_add = True
            
            for existing in filtered_signals:
                # 检查时间间隔
                time_diff = abs(signal.index - existing.index)
                
                # 如果方向相同且时间间隔小于5根K线
                if (signal.direction == existing.direction and time_diff < 5):
                    should_add = False
                    break
            
            if should_add:
                filtered_signals.append(signal)
        
        return filtered_signals[:20]  # 最多返回20个信号

# 使用示例和测试函数
def test_optimized_detector():
    """测试优化的检测器"""
    # 创建测试数据
    import random
    
    dates = pd.date_range('2024-01-01', periods=1000, freq='1H')
    
    # 生成模拟价格数据
    close_prices = []
    price = 50000
    
    for i in range(1000):
        change = random.gauss(0, 0.02)  # 2%标准差
        price = price * (1 + change)
        close_prices.append(price)
    
    # 创建OHLCV数据
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [p * random.uniform(0.995, 1.005) for p in close_prices],
        'close': close_prices,
        'volume': [random.uniform(1000, 10000) for _ in range(1000)]
    })
    
    # 生成high和low
    df['high'] = df[['open', 'close']].max(axis=1) * np.random.uniform(1.0, 1.02, len(df))
    df['low'] = df[['open', 'close']].min(axis=1) * np.random.uniform(0.98, 1.0, len(df))
    
    # 测试检测器
    detector = OptimizedPinbarDetector()
    signals = detector.detect_optimized_signals(df)
    
    print(f"检测到 {len(signals)} 个优化信号")
    
    for signal in signals[:5]:  # 显示前5个信号
        print(f"\n信号: {signal.type.value} {signal.direction}")
        print(f"时间: {signal.timestamp}")
        print(f"最终得分: {signal.final_score:.2f}")
        print(f"置信度: {signal.confidence_level}")
        print(f"风险回报比: {signal.risk_reward_ratio:.2f}")
        print(f"入场理由: {signal.entry_reason}")

if __name__ == "__main__":
    test_optimized_detector()