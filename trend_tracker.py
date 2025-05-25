#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
趋势跟踪模块 - 解决过早止盈问题
识别强势趋势并动态调整止盈策略
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

class TrendStrength(Enum):
    """趋势强度等级"""
    WEAK = 1
    MODERATE = 2  
    STRONG = 3
    VERY_STRONG = 4
    EXTREME = 5

class TrendDirection(Enum):
    """趋势方向"""
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"

@dataclass
class TrendInfo:
    """趋势信息"""
    direction: TrendDirection
    strength: TrendStrength
    confidence: float
    momentum_score: float
    volume_support: bool
    breakout_strength: float
    volatility_expansion: bool
    trend_age: int
    expected_duration: int
    
    def is_strong_trend(self) -> bool:
        """判断是否为强趋势"""
        return self.strength.value >= 3 and self.confidence >= 0.7
    
    def should_hold_position(self) -> bool:
        """判断是否应该继续持仓"""
        return (self.strength.value >= 3 and 
                self.confidence >= 0.6 and
                self.momentum_score >= 0.5)

class TrendTracker:
    """趋势跟踪器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        
        # === 趋势识别参数 ===
        self.fast_ma_period = config.get('fast_ma_period', 8)
        self.slow_ma_period = config.get('slow_ma_period', 21)
        self.trend_ma_period = config.get('trend_ma_period', 50)
        
        # === 动量指标参数 ===
        self.roc_period = config.get('roc_period', 10)
        self.momentum_period = config.get('momentum_period', 14)
        self.adx_period = config.get('adx_period', 14)
        self.atr_period = config.get('atr_period', 14)
        
        # === 趋势强度阈值 ===
        self.weak_adx = config.get('weak_adx', 20)
        self.moderate_adx = config.get('moderate_adx', 30)
        self.strong_adx = config.get('strong_adx', 40)
        self.extreme_adx = config.get('extreme_adx', 60)
        
        # === 成交量确认参数 ===
        self.volume_ma_period = config.get('volume_ma_period', 20)
        self.volume_surge_threshold = config.get('volume_surge_threshold', 1.5)
        
        # === 突破强度参数 ===
        self.breakout_lookback = config.get('breakout_lookback', 20)
        self.breakout_threshold = config.get('breakout_threshold', 0.02)  # 2%突破
        
        # === 波动率扩张参数 ===
        self.atr_expansion_threshold = config.get('atr_expansion_threshold', 1.3)
        self.atr_lookback = config.get('atr_lookback', 10)
        
    def analyze_trend(self, data: pd.DataFrame) -> TrendInfo:
        """
        综合分析当前趋势状态
        
        Args:
            data: 包含OHLCV的数据
            
        Returns:
            TrendInfo: 趋势分析结果
        """
        if len(data) < max(self.slow_ma_period, self.trend_ma_period) + 10:
            return self._create_default_trend_info()
        
        # 计算技术指标
        indicators = self._calculate_trend_indicators(data)
        
        # 1. 趋势方向识别
        direction = self._identify_trend_direction(data, indicators)
        
        # 2. 趋势强度评估
        strength = self._assess_trend_strength(indicators)
        
        # 3. 趋势置信度计算
        confidence = self._calculate_trend_confidence(data, indicators, direction)
        
        # 4. 动量得分
        momentum_score = self._calculate_momentum_score(indicators)
        
        # 5. 成交量支撑检查
        volume_support = self._check_volume_support(data, direction)
        
        # 6. 突破强度评估
        breakout_strength = self._assess_breakout_strength(data, direction)
        
        # 7. 波动率扩张检查
        volatility_expansion = self._check_volatility_expansion(indicators)
        
        # 8. 趋势年龄估算
        trend_age = self._estimate_trend_age(data, indicators, direction)
        
        # 9. 预期持续时间
        expected_duration = self._estimate_trend_duration(
            strength, momentum_score, volume_support, breakout_strength
        )
        
        return TrendInfo(
            direction=direction,
            strength=strength,
            confidence=confidence,
            momentum_score=momentum_score,
            volume_support=volume_support,
            breakout_strength=breakout_strength,
            volatility_expansion=volatility_expansion,
            trend_age=trend_age,
            expected_duration=expected_duration
        )
    
    def _calculate_trend_indicators(self, data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """计算趋势相关指标"""
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        volume = data['volume'].values
        
        indicators = {
            # 移动平均线
            'ema_fast': talib.EMA(close, timeperiod=self.fast_ma_period),
            'ema_slow': talib.EMA(close, timeperiod=self.slow_ma_period),
            'sma_trend': talib.SMA(close, timeperiod=self.trend_ma_period),
            
            # 趋势强度指标
            'adx': talib.ADX(high, low, close, timeperiod=self.adx_period),
            'plus_di': talib.PLUS_DI(high, low, close, timeperiod=self.adx_period),
            'minus_di': talib.MINUS_DI(high, low, close, timeperiod=self.adx_period),
            
            # 动量指标
            'roc': talib.ROC(close, timeperiod=self.roc_period),
            'momentum': talib.MOM(close, timeperiod=self.momentum_period),
            'macd': talib.MACD(close)[0],  # 只要MACD线
            
            # 波动率指标
            'atr': talib.ATR(high, low, close, timeperiod=self.atr_period),
            'bbands_upper': talib.BBANDS(close)[0],
            'bbands_lower': talib.BBANDS(close)[2],
            
            # 成交量指标
            'volume_sma': talib.SMA(volume.astype(float), timeperiod=self.volume_ma_period),
            'obv': talib.OBV(close, volume.astype(float))
        }
        
        return indicators
    
    def _identify_trend_direction(self, data: pd.DataFrame, indicators: Dict) -> TrendDirection:
        """识别趋势方向"""
        close = data['close'].iloc[-1]
        ema_fast = indicators['ema_fast'][-1]
        ema_slow = indicators['ema_slow'][-1]
        sma_trend = indicators['sma_trend'][-1]
        
        # 多重确认趋势方向
        signals = []
        
        # 1. 均线排列
        if ema_fast > ema_slow > sma_trend:
            signals.append('up')
        elif ema_fast < ema_slow < sma_trend:
            signals.append('down')
        else:
            signals.append('sideways')
        
        # 2. 价格与趋势线关系
        if close > sma_trend * 1.01:  # 高于趋势线1%
            signals.append('up')
        elif close < sma_trend * 0.99:  # 低于趋势线1%
            signals.append('down')
        else:
            signals.append('sideways')
        
        # 3. DI指标确认
        plus_di = indicators['plus_di'][-1]
        minus_di = indicators['minus_di'][-1]
        
        if plus_di > minus_di * 1.1:
            signals.append('up')
        elif minus_di > plus_di * 1.1:
            signals.append('down')
        else:
            signals.append('sideways')
        
        # 投票机制确定方向
        up_votes = signals.count('up')
        down_votes = signals.count('down')
        sideways_votes = signals.count('sideways')
        
        if up_votes >= 2:
            return TrendDirection.UP
        elif down_votes >= 2:
            return TrendDirection.DOWN
        else:
            return TrendDirection.SIDEWAYS
    
    def _assess_trend_strength(self, indicators: Dict) -> TrendStrength:
        """评估趋势强度"""
        adx = indicators['adx'][-1]
        
        if pd.isna(adx):
            return TrendStrength.WEAK
        
        if adx >= self.extreme_adx:
            return TrendStrength.EXTREME
        elif adx >= self.strong_adx:
            return TrendStrength.VERY_STRONG
        elif adx >= self.moderate_adx:
            return TrendStrength.STRONG
        elif adx >= self.weak_adx:
            return TrendStrength.MODERATE
        else:
            return TrendStrength.WEAK
    
    def _calculate_trend_confidence(self, data: pd.DataFrame, 
                                  indicators: Dict, direction: TrendDirection) -> float:
        """计算趋势置信度 (0-1)"""
        confidence_factors = []
        
        # 1. ADX强度因子
        adx = indicators['adx'][-1]
        if not pd.isna(adx):
            adx_factor = min(adx / self.extreme_adx, 1.0)
            confidence_factors.append(adx_factor)
        
        # 2. 均线一致性因子
        ema_fast = indicators['ema_fast'][-1]
        ema_slow = indicators['ema_slow'][-1]
        sma_trend = indicators['sma_trend'][-1]
        
        if direction == TrendDirection.UP:
            if ema_fast > ema_slow > sma_trend:
                confidence_factors.append(1.0)
            elif ema_fast > ema_slow:
                confidence_factors.append(0.7)
            else:
                confidence_factors.append(0.3)
        elif direction == TrendDirection.DOWN:
            if ema_fast < ema_slow < sma_trend:
                confidence_factors.append(1.0)
            elif ema_fast < ema_slow:
                confidence_factors.append(0.7)
            else:
                confidence_factors.append(0.3)
        
        # 3. 动量一致性因子
        roc = indicators['roc'][-1]
        momentum = indicators['momentum'][-1]
        
        if direction == TrendDirection.UP and roc > 0 and momentum > 0:
            confidence_factors.append(0.8)
        elif direction == TrendDirection.DOWN and roc < 0 and momentum < 0:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.4)
        
        # 4. 价格位置因子
        close = data['close'].iloc[-1]
        bb_upper = indicators['bbands_upper'][-1]
        bb_lower = indicators['bbands_lower'][-1]
        bb_middle = (bb_upper + bb_lower) / 2
        
        if direction == TrendDirection.UP and close > bb_middle:
            confidence_factors.append(0.7)
        elif direction == TrendDirection.DOWN and close < bb_middle:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)
        
        # 计算加权平均置信度
        if confidence_factors:
            return np.mean(confidence_factors)
        else:
            return 0.5
    
    def _calculate_momentum_score(self, indicators: Dict) -> float:
        """计算动量得分 (0-1)"""
        scores = []
        
        # ROC得分
        roc = indicators['roc'][-1]
        if not pd.isna(roc):
            roc_score = min(abs(roc) / 10.0, 1.0)  # 10%为满分
            scores.append(roc_score)
        
        # 动量得分
        momentum = indicators['momentum'][-1]
        if not pd.isna(momentum):
            mom_score = min(abs(momentum) / (indicators['momentum'][-20:].std() * 2), 1.0)
            scores.append(mom_score)
        
        # MACD得分
        macd = indicators['macd'][-1]
        if not pd.isna(macd):
            macd_score = min(abs(macd) / (indicators['macd'][-20:].std() * 2), 1.0)
            scores.append(macd_score)
        
        return np.mean(scores) if scores else 0.5
    
    def _check_volume_support(self, data: pd.DataFrame, direction: TrendDirection) -> bool:
        """检查成交量是否支撑趋势"""
        if len(data) < self.volume_ma_period:
            return False
        
        current_volume = data['volume'].iloc[-1]
        avg_volume = data['volume'].rolling(self.volume_ma_period).mean().iloc[-1]
        
        # 成交量放大且与趋势方向一致
        volume_surge = current_volume > avg_volume * self.volume_surge_threshold
        
        if direction == TrendDirection.SIDEWAYS:
            return not volume_surge  # 横盘时成交量应该较低
        else:
            return volume_surge  # 趋势时成交量应该放大
    
    def _assess_breakout_strength(self, data: pd.DataFrame, direction: TrendDirection) -> float:
        """评估突破强度 (0-1)"""
        if len(data) < self.breakout_lookback:
            return 0.5
        
        recent_data = data.tail(self.breakout_lookback)
        current_price = data['close'].iloc[-1]
        
        if direction == TrendDirection.UP:
            resistance = recent_data['high'].max()
            if current_price > resistance:
                breakout_pct = (current_price - resistance) / resistance
                return min(breakout_pct / self.breakout_threshold, 1.0)
        elif direction == TrendDirection.DOWN:
            support = recent_data['low'].min()
            if current_price < support:
                breakout_pct = (support - current_price) / support
                return min(breakout_pct / self.breakout_threshold, 1.0)
        
        return 0.0
    
    def _check_volatility_expansion(self, indicators: Dict) -> bool:
        """检查波动率是否扩张"""
        if len(indicators['atr']) < self.atr_lookback:
            return False
        
        current_atr = indicators['atr'][-1]
        avg_atr = np.mean(indicators['atr'][-self.atr_lookback:-1])
        
        return current_atr > avg_atr * self.atr_expansion_threshold
    
    def _estimate_trend_age(self, data: pd.DataFrame, indicators: Dict, 
                          direction: TrendDirection) -> int:
        """估算趋势年龄（多少根K线）"""
        if direction == TrendDirection.SIDEWAYS:
            return 0
        
        # 简化版：计算价格连续朝一个方向移动的K线数
        closes = data['close'].values
        age = 0
        
        for i in range(len(closes) - 1, 0, -1):
            if direction == TrendDirection.UP:
                if closes[i] > closes[i-1]:
                    age += 1
                else:
                    break
            else:  # DOWN
                if closes[i] < closes[i-1]:
                    age += 1
                else:
                    break
        
        return min(age, 100)  # 最大100根K线
    
    def _estimate_trend_duration(self, strength: TrendStrength, momentum_score: float,
                               volume_support: bool, breakout_strength: float) -> int:
        """估算趋势预期持续时间"""
        base_duration = {
            TrendStrength.WEAK: 5,
            TrendStrength.MODERATE: 10,
            TrendStrength.STRONG: 20,
            TrendStrength.VERY_STRONG: 40,
            TrendStrength.EXTREME: 80
        }
        
        duration = base_duration[strength]
        
        # 根据其他因子调整
        if momentum_score > 0.7:
            duration *= 1.5
        if volume_support:
            duration *= 1.3
        if breakout_strength > 0.5:
            duration *= 1.4
        
        return int(duration)
    
    def _create_default_trend_info(self) -> TrendInfo:
        """创建默认趋势信息"""
        return TrendInfo(
            direction=TrendDirection.SIDEWAYS,
            strength=TrendStrength.WEAK,
            confidence=0.5,
            momentum_score=0.5,
            volume_support=False,
            breakout_strength=0.0,
            volatility_expansion=False,
            trend_age=0,
            expected_duration=5
        )
    
    def should_extend_profit_target(self, trend_info: TrendInfo, 
                                  current_profit_pct: float) -> bool:
        """判断是否应该延长止盈目标"""
        # 强趋势且利润还不够大时，延长止盈
        if (trend_info.is_strong_trend() and 
            current_profit_pct < 5.0 and  # 利润小于5%
            trend_info.momentum_score > 0.6):
            return True
        
        # 极强趋势时，即使利润较大也可以继续持有
        if (trend_info.strength == TrendStrength.EXTREME and
            trend_info.confidence > 0.8 and
            current_profit_pct < 10.0):  # 利润小于10%
            return True
        
        return False
    
    def calculate_dynamic_profit_target(self, trend_info: TrendInfo, 
                                      entry_price: float, direction: str) -> float:
        """计算动态止盈目标"""
        base_target_pct = 2.0  # 基础2%止盈
        
        # 根据趋势强度调整
        strength_multiplier = {
            TrendStrength.WEAK: 1.0,
            TrendStrength.MODERATE: 1.5,
            TrendStrength.STRONG: 2.5,
            TrendStrength.VERY_STRONG: 4.0,
            TrendStrength.EXTREME: 6.0
        }
        
        target_pct = base_target_pct * strength_multiplier[trend_info.strength]
        
        # 根据置信度调整
        target_pct *= trend_info.confidence
        
        # 根据动量调整
        target_pct *= (0.5 + trend_info.momentum_score)
        
        # 突破强度加成
        if trend_info.breakout_strength > 0.3:
            target_pct *= (1 + trend_info.breakout_strength)
        
        # 计算目标价格
        if direction == 'buy':
            return entry_price * (1 + target_pct / 100)
        else:
            return entry_price * (1 - target_pct / 100)
    
    def get_trailing_stop_distance(self, trend_info: TrendInfo) -> float:
        """获取追踪止损距离（百分比）"""
        base_distance = 1.0  # 基础1%
        
        # 强趋势时放宽止损距离
        if trend_info.strength.value >= 3:
            base_distance *= 1.5
        
        # 高波动时放宽止损距离
        if trend_info.volatility_expansion:
            base_distance *= 1.3
        
        return base_distance