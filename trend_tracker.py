#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
趋势跟踪模块 - 解决过早止盈问题
识别强势趋势并动态调整止盈策略

版本: v2.0 - 修复版
修复日期: 2024年12月
主要修复:
1. 增强趋势识别的准确性
2. 优化趋势强度判断逻辑
3. 添加波动率扩张检测
4. 完善趋势持续时间预测
5. 新增趋势逆转检测辅助功能

核心功能:
- 多维度趋势方向识别 (均线+DI+价格位置)
- 5级趋势强度评估 (WEAK/MODERATE/STRONG/VERY_STRONG/EXTREME)
- 动态置信度计算 (0-1评分)
- 成交量支撑验证
- 突破强度评估
- 波动率扩张检测
- 趋势年龄和持续期预测
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

class TrendStrength(Enum):
    """
    趋势强度等级枚举
    
    用于量化趋势的强弱程度，影响后续的交易决策:
    - WEAK(1): 弱趋势，谨慎交易
    - MODERATE(2): 中等趋势，正常交易
    - STRONG(3): 强趋势，可加大仓位
    - VERY_STRONG(4): 极强趋势，可延长持仓
    - EXTREME(5): 极端趋势，最大化利润
    """
    WEAK = 1          # 弱趋势 (ADX < 20)
    MODERATE = 2      # 中等趋势 (ADX 20-30)
    STRONG = 3        # 强趋势 (ADX 30-40)
    VERY_STRONG = 4   # 极强趋势 (ADX 40-60)
    EXTREME = 5       # 极端趋势 (ADX > 60)

class TrendDirection(Enum):
    """
    趋势方向枚举
    
    基于多重技术指标确认的趋势方向:
    - UP: 上升趋势，偏向做多
    - DOWN: 下降趋势，偏向做空  
    - SIDEWAYS: 横盘整理，等待突破
    """
    UP = "up"         # 上升趋势
    DOWN = "down"     # 下降趋势
    SIDEWAYS = "sideways"  # 横盘趋势

@dataclass
class TrendInfo:
    """
    趋势信息数据类
    
    包含完整的趋势分析结果，供策略决策使用:
    - 基础信息: 方向、强度、置信度
    - 动量信息: 动量得分、成交量支撑
    - 技术信息: 突破强度、波动率状态
    - 时间信息: 趋势年龄、预期持续期
    """
    direction: TrendDirection      # 趋势方向
    strength: TrendStrength        # 趋势强度
    confidence: float              # 趋势置信度 (0-1)
    momentum_score: float          # 动量得分 (0-1)
    volume_support: bool           # 成交量是否支撑趋势
    breakout_strength: float       # 突破强度 (0-1)
    volatility_expansion: bool     # 是否出现波动率扩张
    trend_age: int                 # 趋势年龄 (K线数)
    expected_duration: int         # 预期持续时间 (K线数)
    
    def is_strong_trend(self) -> bool:
        """
        判断是否为强趋势
        
        强趋势定义:
        - 趋势强度 >= 3 (STRONG级别以上)
        - 置信度 >= 0.7 (70%以上)
        
        Returns:
            bool: True表示强趋势，False表示弱趋势
        """
        return self.strength.value >= 3 and self.confidence >= 0.7
    
    def should_hold_position(self) -> bool:
        """
        判断是否应该继续持仓
        
        持仓条件:
        - 趋势强度 >= 3 (STRONG级别以上)
        - 置信度 >= 0.6 (60%以上)
        - 动量得分 >= 0.5 (50%以上)
        
        用于趋势跟踪系统决定是否延长止盈目标
        
        Returns:
            bool: True表示应该持仓，False表示可以平仓
        """
        return (self.strength.value >= 3 and 
                self.confidence >= 0.6 and
                self.momentum_score >= 0.5)

class TrendTracker:
    """
    趋势跟踪器主类
    
    核心功能:
    1. 多维度趋势识别: 结合均线、DI指标、价格位置
    2. 趋势强度量化: 基于ADX指标的5级评估
    3. 置信度计算: 综合多个因子的加权评分
    4. 动量分析: ROC、Momentum、MACD综合评估
    5. 成交量确认: 验证趋势的成交量支撑
    6. 突破检测: 识别关键位突破的强度
    7. 波动率监控: 检测波动率扩张信号
    8. 时间预测: 估算趋势年龄和持续期
    
    使用场景:
    - 趋势跟踪策略的核心引擎
    - 动态止盈目标调整
    - 仓位管理决策支持
    - 风险控制参考
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化趋势跟踪器
        
        Args:
            config: 配置参数字典，包含所有技术指标参数
        """
        config = config or {}
        
        # === 趋势识别参数 ===
        # 用于多重均线确认趋势方向
        self.fast_ma_period = config.get('fast_ma_period', 8)      # 快速均线周期
        self.slow_ma_period = config.get('slow_ma_period', 21)     # 慢速均线周期  
        self.trend_ma_period = config.get('trend_ma_period', 50)   # 趋势均线周期
        
        # === 动量指标参数 ===
        # 用于评估趋势的动量强度
        self.roc_period = config.get('roc_period', 10)             # ROC变化率周期
        self.momentum_period = config.get('momentum_period', 14)   # 动量指标周期
        self.adx_period = config.get('adx_period', 14)             # ADX趋势强度周期
        self.atr_period = config.get('atr_period', 14)             # ATR波动率周期
        
        # === 趋势强度阈值 ===
        # ADX指标的分级阈值，用于量化趋势强度
        self.weak_adx = config.get('weak_adx', 20)                 # 弱趋势阈值
        self.moderate_adx = config.get('moderate_adx', 30)         # 中等趋势阈值
        self.strong_adx = config.get('strong_adx', 40)             # 强趋势阈值
        self.extreme_adx = config.get('extreme_adx', 60)           # 极端趋势阈值
        
        # === 成交量确认参数 ===
        # 用于验证趋势的成交量支撑
        self.volume_ma_period = config.get('volume_ma_period', 20) # 成交量均线周期
        self.volume_surge_threshold = config.get('volume_surge_threshold', 1.5)  # 成交量放大阈值
        
        # === 突破强度参数 ===
        # 用于评估关键位突破的有效性
        self.breakout_lookback = config.get('breakout_lookback', 20)    # 突破检测回看期
        self.breakout_threshold = config.get('breakout_threshold', 0.02)  # 有效突破阈值(2%)
        
        # === 波动率扩张参数 ===
        # 用于检测市场波动率的变化
        self.atr_expansion_threshold = config.get('atr_expansion_threshold', 1.3)  # ATR扩张阈值
        self.atr_lookback = config.get('atr_lookback', 10)          # ATR对比回看期
        
        print(f"✅ 趋势跟踪器初始化完成:")
        print(f"   - 均线周期: 快{self.fast_ma_period}/慢{self.slow_ma_period}/趋势{self.trend_ma_period}")
        print(f"   - ADX阈值: 弱{self.weak_adx}/中{self.moderate_adx}/强{self.strong_adx}/极{self.extreme_adx}")
        print(f"   - 成交量放大阈值: {self.volume_surge_threshold}x")
        print(f"   - 突破确认阈值: {self.breakout_threshold*100:.1f}%")
        
    def analyze_trend(self, data: pd.DataFrame) -> TrendInfo:
        """
        综合分析当前趋势状态
        
        分析流程:
        1. 数据充足性检查
        2. 计算全部技术指标
        3. 识别趋势方向 (多重确认)
        4. 评估趋势强度 (ADX为主)
        5. 计算趋势置信度 (加权平均)
        6. 分析动量状态 (ROC/MOM/MACD)
        7. 验证成交量支撑
        8. 评估突破强度
        9. 检测波动率扩张
        10. 估算趋势年龄和持续期
        
        Args:
            data: 包含OHLCV的历史数据DataFrame
            
        Returns:
            TrendInfo: 完整的趋势分析结果
        """
        # 1. 数据充足性检查
        min_bars_required = max(self.slow_ma_period, self.trend_ma_period) + 10
        if len(data) < min_bars_required:
            print(f"⚠️ 数据不足: 需要{min_bars_required}根K线，实际{len(data)}根")
            return self._create_default_trend_info()
        
        # 2. 计算技术指标
        try:
            indicators = self._calculate_trend_indicators(data)
        except Exception as e:
            print(f"❌ 技术指标计算失败: {e}")
            return self._create_default_trend_info()
        
        # 3. 趋势方向识别 (多重确认机制)
        direction = self._identify_trend_direction(data, indicators)
        
        # 4. 趋势强度评估 (基于ADX)
        strength = self._assess_trend_strength(indicators)
        
        # 5. 趋势置信度计算 (综合评分)
        confidence = self._calculate_trend_confidence(data, indicators, direction)
        
        # 6. 动量得分 (多指标综合)
        momentum_score = self._calculate_momentum_score(indicators)
        
        # 7. 成交量支撑检查
        volume_support = self._check_volume_support(data, direction)
        
        # 8. 突破强度评估
        breakout_strength = self._assess_breakout_strength(data, direction)
        
        # 9. 波动率扩张检查
        volatility_expansion = self._check_volatility_expansion(indicators)
        
        # 10. 趋势年龄估算
        trend_age = self._estimate_trend_age(data, indicators, direction)
        
        # 11. 预期持续时间
        expected_duration = self._estimate_trend_duration(
            strength, momentum_score, volume_support, breakout_strength
        )
        
        # 构建趋势信息对象
        trend_info = TrendInfo(
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
        
        # 输出分析结果 (调试信息)
        print(f"📈 趋势分析完成:")
        print(f"   方向: {direction.value} | 强度: {strength.name}({strength.value})")
        print(f"   置信度: {confidence:.2f} | 动量: {momentum_score:.2f}")
        print(f"   成交量支撑: {'是' if volume_support else '否'} | 突破强度: {breakout_strength:.2f}")
        print(f"   波动率扩张: {'是' if volatility_expansion else '否'} | 趋势年龄: {trend_age}K线")
        
        return trend_info
    
    def _calculate_trend_indicators(self, data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        计算趋势相关技术指标
        
        计算的指标包括:
        - 移动平均线: EMA快速/慢速, SMA趋势线
        - 趋势强度: ADX, +DI, -DI
        - 动量指标: ROC, Momentum, MACD
        - 波动率: ATR, 布林带
        - 成交量: SMA, OBV
        
        Args:
            data: OHLCV数据
            
        Returns:
            Dict: 指标名称到数组的映射
        """
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        volume = data['volume'].values
        
        indicators = {
            # === 移动平均线系统 ===
            'ema_fast': talib.EMA(close, timeperiod=self.fast_ma_period),     # 快速EMA
            'ema_slow': talib.EMA(close, timeperiod=self.slow_ma_period),     # 慢速EMA
            'sma_trend': talib.SMA(close, timeperiod=self.trend_ma_period),   # 趋势SMA
            
            # === 趋势强度指标 ===
            'adx': talib.ADX(high, low, close, timeperiod=self.adx_period),           # 平均趋向指数
            'plus_di': talib.PLUS_DI(high, low, close, timeperiod=self.adx_period),  # 正向指标
            'minus_di': talib.MINUS_DI(high, low, close, timeperiod=self.adx_period), # 负向指标
            
            # === 动量指标系统 ===
            'roc': talib.ROC(close, timeperiod=self.roc_period),                      # 变化率
            'momentum': talib.MOM(close, timeperiod=self.momentum_period),            # 动量指标
            'macd': talib.MACD(close)[0],  # MACD线 (只要主线，不要信号线)
            
            # === 波动率指标 ===
            'atr': talib.ATR(high, low, close, timeperiod=self.atr_period),          # 真实波动幅度
            'bbands_upper': talib.BBANDS(close)[0],   # 布林带上轨
            'bbands_lower': talib.BBANDS(close)[2],   # 布林带下轨
            
            # === 成交量指标 ===
            'volume_sma': talib.SMA(volume.astype(float), timeperiod=self.volume_ma_period),  # 成交量均线
            'obv': talib.OBV(close, volume.astype(float))     # 能量潮指标
        }
        
        return indicators
    
    def _identify_trend_direction(self, data: pd.DataFrame, indicators: Dict) -> TrendDirection:
        """
        识别趋势方向 - 多重确认机制
        
        确认方法:
        1. 均线排列: 快线 vs 慢线 vs 趋势线的相对位置
        2. 价格位置: 当前价格与趋势线的关系
        3. DI指标: +DI与-DI的强弱对比
        
        投票机制: 3个方法各给出一票，多数决定最终方向
        
        Args:
            data: 价格数据
            indicators: 计算好的技术指标
            
        Returns:
            TrendDirection: 趋势方向枚举值
        """
        current_price = data['close'].iloc[-1]
        ema_fast = indicators['ema_fast'][-1]
        ema_slow = indicators['ema_slow'][-1]
        sma_trend = indicators['sma_trend'][-1]
        
        # 投票系统: 收集各方法的方向判断
        direction_votes = []
        
        # === 投票1: 均线排列 ===
        if ema_fast > ema_slow > sma_trend:
            direction_votes.append('up')
            print(f"   均线排列: 上升 (快{ema_fast:.4f} > 慢{ema_slow:.4f} > 趋势{sma_trend:.4f})")
        elif ema_fast < ema_slow < sma_trend:
            direction_votes.append('down')
            print(f"   均线排列: 下降 (快{ema_fast:.4f} < 慢{ema_slow:.4f} < 趋势{sma_trend:.4f})")
        else:
            direction_votes.append('sideways')
            print(f"   均线排列: 混乱")
        
        # === 投票2: 价格与趋势线关系 ===
        price_trend_ratio = current_price / sma_trend
        if price_trend_ratio > 1.01:  # 高于趋势线1%
            direction_votes.append('up')
            print(f"   价格位置: 上升 (价格{current_price:.4f} > 趋势线{sma_trend:.4f}, 比例{price_trend_ratio:.3f})")
        elif price_trend_ratio < 0.99:  # 低于趋势线1%
            direction_votes.append('down')
            print(f"   价格位置: 下降 (价格{current_price:.4f} < 趋势线{sma_trend:.4f}, 比例{price_trend_ratio:.3f})")
        else:
            direction_votes.append('sideways')
            print(f"   价格位置: 中性")
        
        # === 投票3: DI指标确认 ===
        plus_di = indicators['plus_di'][-1]
        minus_di = indicators['minus_di'][-1]
        
        if not (pd.isna(plus_di) or pd.isna(minus_di)):
            di_ratio = plus_di / minus_di if minus_di > 0 else 2.0
            if di_ratio > 1.1:  # +DI显著强于-DI
                direction_votes.append('up')
                print(f"   DI指标: 上升 (+DI{plus_di:.1f} > -DI{minus_di:.1f}, 比例{di_ratio:.2f})")
            elif di_ratio < 0.9:  # -DI显著强于+DI
                direction_votes.append('down')
                print(f"   DI指标: 下降 (+DI{plus_di:.1f} < -DI{minus_di:.1f}, 比例{di_ratio:.2f})")
            else:
                direction_votes.append('sideways')
                print(f"   DI指标: 平衡")
        else:
            direction_votes.append('sideways')
            print(f"   DI指标: 数据不足")
        
        # === 投票统计 ===
        up_votes = direction_votes.count('up')
        down_votes = direction_votes.count('down')
        sideways_votes = direction_votes.count('sideways')
        
        print(f"   方向投票: 上升{up_votes}票, 下降{down_votes}票, 横盘{sideways_votes}票")
        
        # 多数决定方向
        if up_votes >= 2:
            return TrendDirection.UP
        elif down_votes >= 2:
            return TrendDirection.DOWN
        else:
            return TrendDirection.SIDEWAYS
    
    def _assess_trend_strength(self, indicators: Dict) -> TrendStrength:
        """
        评估趋势强度 - 基于ADX指标
        
        ADX (Average Directional Index) 是衡量趋势强度的经典指标:
        - ADX > 60: 极端趋势 (EXTREME)
        - ADX 40-60: 极强趋势 (VERY_STRONG)  
        - ADX 30-40: 强趋势 (STRONG)
        - ADX 20-30: 中等趋势 (MODERATE)
        - ADX < 20: 弱趋势 (WEAK)
        
        Args:
            indicators: 包含ADX值的指标字典
            
        Returns:
            TrendStrength: 趋势强度枚举值
        """
        adx = indicators['adx'][-1]
        
        # 处理NaN值
        if pd.isna(adx):
            print(f"   ADX数据不足，默认为弱趋势")
            return TrendStrength.WEAK
        
        # 根据ADX值分级
        if adx >= self.extreme_adx:
            strength = TrendStrength.EXTREME
        elif adx >= self.strong_adx:
            strength = TrendStrength.VERY_STRONG
        elif adx >= self.moderate_adx:
            strength = TrendStrength.STRONG
        elif adx >= self.weak_adx:
            strength = TrendStrength.MODERATE
        else:
            strength = TrendStrength.WEAK
        
        print(f"   ADX强度: {adx:.1f} -> {strength.name}")
        return strength
    
    def _calculate_trend_confidence(self, data: pd.DataFrame, 
                                  indicators: Dict, direction: TrendDirection) -> float:
        """
        计算趋势置信度 - 多因子加权评分
        
        置信度因子:
        1. ADX强度因子 (权重30%): ADX值标准化
        2. 均线一致性因子 (权重30%): 均线排列的完美程度
        3. 动量一致性因子 (权重25%): 动量指标与方向的一致性
        4. 价格位置因子 (权重15%): 价格在布林带中的位置
        
        Args:
            data: 价格数据
            indicators: 技术指标
            direction: 趋势方向
            
        Returns:
            float: 置信度评分 (0-1)
        """
        confidence_factors = []
        factor_weights = []
        
        # === 因子1: ADX强度因子 (权重30%) ===
        adx = indicators['adx'][-1]
        if not pd.isna(adx):
            # ADX标准化: 以极端阈值为满分
            adx_factor = min(adx / self.extreme_adx, 1.0)
            confidence_factors.append(adx_factor)
            factor_weights.append(0.30)
            print(f"   置信度-ADX: {adx_factor:.2f} (ADX={adx:.1f})")
        
        # === 因子2: 均线一致性因子 (权重30%) ===
        ema_fast = indicators['ema_fast'][-1]
        ema_slow = indicators['ema_slow'][-1]
        sma_trend = indicators['sma_trend'][-1]
        
        if direction == TrendDirection.UP:
            # 上升趋势: 快>慢>趋势 = 完美(1.0), 快>慢 = 良好(0.7), 其他 = 差(0.3)
            if ema_fast > ema_slow > sma_trend:
                ma_factor = 1.0
                print(f"   置信度-均线: 1.0 (完美上升排列)")
            elif ema_fast > ema_slow:
                ma_factor = 0.7
                print(f"   置信度-均线: 0.7 (部分上升排列)")
            else:
                ma_factor = 0.3
                print(f"   置信度-均线: 0.3 (混乱排列)")
        elif direction == TrendDirection.DOWN:
            # 下降趋势: 快<慢<趋势 = 完美(1.0), 快<慢 = 良好(0.7), 其他 = 差(0.3)
            if ema_fast < ema_slow < sma_trend:
                ma_factor = 1.0
                print(f"   置信度-均线: 1.0 (完美下降排列)")
            elif ema_fast < ema_slow:
                ma_factor = 0.7
                print(f"   置信度-均线: 0.7 (部分下降排列)")
            else:
                ma_factor = 0.3
                print(f"   置信度-均线: 0.3 (混乱排列)")
        else:
            # 横盘趋势: 均线纠缠是正常的
            ma_factor = 0.5
            print(f"   置信度-均线: 0.5 (横盘状态)")
        
        confidence_factors.append(ma_factor)
        factor_weights.append(0.30)
        
        # === 因子3: 动量一致性因子 (权重25%) ===
        roc = indicators['roc'][-1]
        momentum = indicators['momentum'][-1]
        
        momentum_factor = 0.5  # 默认中性
        
        if not (pd.isna(roc) or pd.isna(momentum)):
            if direction == TrendDirection.UP:
                # 上升趋势: ROC>0 且 Momentum>0
                if roc > 0 and momentum > 0:
                    momentum_factor = 0.8
                    print(f"   置信度-动量: 0.8 (动量支持上升)")
                else:
                    momentum_factor = 0.4
                    print(f"   置信度-动量: 0.4 (动量不支持)")
            elif direction == TrendDirection.DOWN:
                # 下降趋势: ROC<0 且 Momentum<0
                if roc < 0 and momentum < 0:
                    momentum_factor = 0.8
                    print(f"   置信度-动量: 0.8 (动量支持下降)")
                else:
                    momentum_factor = 0.4
                    print(f"   置信度-动量: 0.4 (动量不支持)")
            else:
                # 横盘趋势: 动量应该较弱
                if abs(roc) < 1 and abs(momentum) < 10:
                    momentum_factor = 0.7
                    print(f"   置信度-动量: 0.7 (动量支持横盘)")
        
        confidence_factors.append(momentum_factor)
        factor_weights.append(0.25)
        
        # === 因子4: 价格位置因子 (权重15%) ===
        current_price = data['close'].iloc[-1]
        bb_upper = indicators['bbands_upper'][-1]
        bb_lower = indicators['bbands_lower'][-1]
        
        if not (pd.isna(bb_upper) or pd.isna(bb_lower)):
            bb_middle = (bb_upper + bb_lower) / 2
            
            if direction == TrendDirection.UP:
                # 上升趋势: 价格在布林带上半部分更有说服力
                if current_price > bb_middle:
                    position_factor = 0.7
                    print(f"   置信度-位置: 0.7 (价格位于布林带上半部)")
                else:
                    position_factor = 0.5
                    print(f"   置信度-位置: 0.5 (价格位于布林带下半部)")
            elif direction == TrendDirection.DOWN:
                # 下降趋势: 价格在布林带下半部分更有说服力
                if current_price < bb_middle:
                    position_factor = 0.7
                    print(f"   置信度-位置: 0.7 (价格位于布林带下半部)")
                else:
                    position_factor = 0.5
                    print(f"   置信度-位置: 0.5 (价格位于布林带上半部)")
            else:
                # 横盘趋势: 价格在中轨附近最好
                distance_to_middle = abs(current_price - bb_middle) / (bb_upper - bb_lower)
                if distance_to_middle < 0.3:  # 距离中轨30%内
                    position_factor = 0.8
                    print(f"   置信度-位置: 0.8 (价格接近布林带中轨)")
                else:
                    position_factor = 0.4
                    print(f"   置信度-位置: 0.4 (价格偏离布林带中轨)")
            
            confidence_factors.append(position_factor)
            factor_weights.append(0.15)
        
        # === 计算加权平均置信度 ===
        if confidence_factors and factor_weights:
            # 加权平均
            weighted_sum = sum(f * w for f, w in zip(confidence_factors, factor_weights))
            total_weight = sum(factor_weights)
            final_confidence = weighted_sum / total_weight
        else:
            # 没有有效因子时返回中性置信度
            final_confidence = 0.5
        
        print(f"   最终置信度: {final_confidence:.2f}")
        return final_confidence
    
    def _calculate_momentum_score(self, indicators: Dict) -> float:
        """
        计算动量得分 - 多指标标准化综合
        
        动量指标:
        1. ROC (变化率): 衡量价格变化速度
        2. Momentum: 衡量价格动量强度  
        3. MACD: 衡量趋势变化动量
        
        每个指标标准化到0-1范围，然后平均
        
        Args:
            indicators: 技术指标字典
            
        Returns:
            float: 动量得分 (0-1)
        """
        momentum_scores = []
        
        # === ROC得分 ===
        roc = indicators['roc'][-1]
        if not pd.isna(roc):
            # ROC标准化: 10%变化率为满分
            roc_score = min(abs(roc) / 10.0, 1.0)
            momentum_scores.append(roc_score)
            print(f"   动量-ROC: {roc_score:.2f} (ROC={roc:.2f}%)")
        
        # === Momentum得分 ===
        momentum = indicators['momentum'][-1]
        if not pd.isna(momentum) and len(indicators['momentum']) >= 20:
            # 基于最近20期的标准差标准化
            momentum_std = np.std(indicators['momentum'][-20:])
            if momentum_std > 0:
                mom_score = min(abs(momentum) / (momentum_std * 2), 1.0)
                momentum_scores.append(mom_score)
                print(f"   动量-MOM: {mom_score:.2f} (MOM={momentum:.2f})")
        
        # === MACD得分 ===
        macd = indicators['macd'][-1]
        if not pd.isna(macd) and len(indicators['macd']) >= 20:
            # 基于最近20期的标准差标准化
            macd_std = np.std(indicators['macd'][-20:])
            if macd_std > 0:
                macd_score = min(abs(macd) / (macd_std * 2), 1.0)
                momentum_scores.append(macd_score)
                print(f"   动量-MACD: {macd_score:.2f} (MACD={macd:.4f})")
        
        # 计算平均动量得分
        if momentum_scores:
            final_score = np.mean(momentum_scores)
        else:
            final_score = 0.5  # 数据不足时返回中性
        
        print(f"   最终动量得分: {final_score:.2f}")
        return final_score
    
    def _check_volume_support(self, data: pd.DataFrame, direction: TrendDirection) -> bool:
        """
        检查成交量是否支撑趋势
        
        成交量确认原理:
        - 趋势行情: 成交量应该放大 (表明参与度高)
        - 横盘行情: 成交量应该萎缩 (表明观望情绪)
        
        Args:
            data: 包含成交量的价格数据
            direction: 趋势方向
            
        Returns:
            bool: True表示成交量支撑趋势，False表示不支撑
        """
        if len(data) < self.volume_ma_period:
            print(f"   成交量: 数据不足")
            return False
        
        current_volume = data['volume'].iloc[-1]
        avg_volume = data['volume'].rolling(self.volume_ma_period).mean().iloc[-1]
        
        if avg_volume <= 0:
            print(f"   成交量: 平均成交量为0")
            return False
        
        volume_ratio = current_volume / avg_volume
        
        if direction == TrendDirection.SIDEWAYS:
            # 横盘时期待成交量萎缩
            volume_support = volume_ratio < self.volume_surge_threshold
            print(f"   成交量: 横盘期 {volume_ratio:.2f}x {'✓萎缩' if volume_support else '✗放大'}")
        else:
            # 趋势时期待成交量放大
            volume_support = volume_ratio >= self.volume_surge_threshold
            print(f"   成交量: 趋势期 {volume_ratio:.2f}x {'✓放大' if volume_support else '✗萎缩'}")
        
        return volume_support
    
    def _assess_breakout_strength(self, data: pd.DataFrame, direction: TrendDirection) -> float:
        """
        评估突破强度 - 关键位突破的有效性
        
        突破强度计算:
        1. 确定关键位: 最近N期的最高/最低点
        2. 计算突破幅度: (当前价-关键位)/关键位
        3. 标准化: 以阈值百分比为满分
        
        Args:
            data: 价格数据
            direction: 趋势方向
            
        Returns:
            float: 突破强度 (0-1)
        """
        if len(data) < self.breakout_lookback:
            print(f"   突破强度: 数据不足 -> 0.0")
            return 0.0
        
        recent_data = data.tail(self.breakout_lookback)
        current_price = data['close'].iloc[-1]
        
        if direction == TrendDirection.UP:
            # 上升趋势: 检查是否突破近期阻力位
            resistance = recent_data['high'].max()
            if current_price > resistance:
                breakout_pct = (current_price - resistance) / resistance
                strength = min(breakout_pct / self.breakout_threshold, 1.0)
                print(f"   突破强度: 上破阻力 {resistance:.4f} -> {strength:.2f} ({breakout_pct*100:.1f}%)")
                return strength
            else:
                print(f"   突破强度: 未突破阻力 {resistance:.4f} -> 0.0")
                return 0.0
                
        elif direction == TrendDirection.DOWN:
            # 下降趋势: 检查是否跌破近期支撑位
            support = recent_data['low'].min()
            if current_price < support:
                breakout_pct = (support - current_price) / support
                strength = min(breakout_pct / self.breakout_threshold, 1.0)
                print(f"   突破强度: 下破支撑 {support:.4f} -> {strength:.2f} ({breakout_pct*100:.1f}%)")
                return strength
            else:
                print(f"   突破强度: 未跌破支撑 {support:.4f} -> 0.0")
                return 0.0
        else:
            # 横盘趋势: 没有突破概念
            print(f"   突破强度: 横盘无突破 -> 0.0")
            return 0.0
    
    def _check_volatility_expansion(self, indicators: Dict) -> bool:
        """
        检查波动率是否扩张
        
        波动率扩张判断:
        - 当前ATR vs 历史ATR平均值
        - 扩张表明市场活跃度增加，趋势可能加速
        
        Args:
            indicators: 包含ATR的技术指标
            
        Returns:
            bool: True表示波动率扩张，False表示正常或收缩
        """
        if len(indicators['atr']) < self.atr_lookback + 1:
            print(f"   波动率: 数据不足 -> False")
            return False
        
        current_atr = indicators['atr'][-1]
        # 排除当前值，计算历史平均
        historical_atr = np.mean(indicators['atr'][-self.atr_lookback-1:-1])
        
        if historical_atr <= 0:
            print(f"   波动率: 历史ATR为0 -> False")
            return False
        
        atr_ratio = current_atr / historical_atr
        expansion = atr_ratio > self.atr_expansion_threshold
        
        print(f"   波动率: {atr_ratio:.2f}x {'✓扩张' if expansion else '✗正常'} (阈值{self.atr_expansion_threshold}x)")
        return expansion
    
    def _estimate_trend_age(self, data: pd.DataFrame, indicators: Dict, 
                          direction: TrendDirection) -> int:
        """
        估算趋势年龄 - 趋势持续的K线数量
        
        简化算法:
        - 从最新K线向前回溯
        - 统计价格连续朝同一方向移动的K线数
        - 上升趋势: 连续收盘价上涨
        - 下降趋势: 连续收盘价下跌
        
        Args:
            data: 价格数据
            indicators: 技术指标 (暂未使用)
            direction: 趋势方向
            
        Returns:
            int: 趋势年龄 (K线数，最大100)
        """
        if direction == TrendDirection.SIDEWAYS:
            print(f"   趋势年龄: 横盘无年龄 -> 0")
            return 0
        
        closes = data['close'].values
        age = 0
        
        # 从最新向前回溯，计算连续同向K线数
        for i in range(len(closes) - 1, 0, -1):
            current_close = closes[i]
            previous_close = closes[i-1]
            
            if direction == TrendDirection.UP:
                if current_close > previous_close:
                    age += 1
                else:
                    break
            else:  # DOWN
                if current_close < previous_close:
                    age += 1
                else:
                    break
        
        # 限制最大年龄，避免异常值
        age = min(age, 100)
        print(f"   趋势年龄: {age}根K线")
        return age
    
    def _estimate_trend_duration(self, strength: TrendStrength, momentum_score: float,
                               volume_support: bool, breakout_strength: float) -> int:
        """
        估算趋势预期持续时间
        
        基础持续期 (根据强度):
        - WEAK: 5根K线
        - MODERATE: 10根K线  
        - STRONG: 20根K线
        - VERY_STRONG: 40根K线
        - EXTREME: 80根K线
        
        调整因子:
        - 强动量: +50%
        - 成交量支撑: +30%
        - 强突破: +40%
        
        Args:
            strength: 趋势强度
            momentum_score: 动量得分
            volume_support: 成交量支撑
            breakout_strength: 突破强度
            
        Returns:
            int: 预期持续时间 (K线数)
        """
        # 基础持续时间
        base_duration = {
            TrendStrength.WEAK: 5,
            TrendStrength.MODERATE: 10,
            TrendStrength.STRONG: 20,
            TrendStrength.VERY_STRONG: 40,
            TrendStrength.EXTREME: 80
        }
        
        duration = base_duration[strength]
        
        # 动量调整: 强动量延长持续期
        if momentum_score > 0.7:
            duration *= 1.5
            print(f"   持续期调整: 强动量 +50%")
        
        # 成交量调整: 成交量支撑延长持续期
        if volume_support:
            duration *= 1.3
            print(f"   持续期调整: 成交量支撑 +30%")
        
        # 突破调整: 强突破延长持续期
        if breakout_strength > 0.5:
            duration *= 1.4
            print(f"   持续期调整: 强突破 +40%")
        
        final_duration = int(duration)
        print(f"   预期持续: {final_duration}根K线")
        return final_duration
    
    def _create_default_trend_info(self) -> TrendInfo:
        """
        创建默认趋势信息 - 数据不足时使用
        
        Returns:
            TrendInfo: 中性/保守的趋势信息
        """
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
    
    # ===== 趋势跟踪决策方法 =====
    def should_extend_profit_target(self, trend_info: TrendInfo, current_profit_pct: float) -> bool:
        """判断是否应该延长止盈目标 - 激进版"""
        if not trend_info:
            return False
        
        # 🔥 激进的延长条件
        min_profit_for_extension = 0.3  # 从1.0%降低到0.3%
        min_trend_strength = 2          # 从3降低到2
        min_confidence = 0.4            # 从0.6降低到0.4
        
        # 基础条件检查 - 放宽要求
        if (current_profit_pct >= min_profit_for_extension and 
            trend_info.strength.value >= min_trend_strength and 
            trend_info.confidence >= min_confidence):
            
            print(f"✅ 延长止盈: 利润{current_profit_pct:.1f}% 趋势{trend_info.strength.value} 置信{trend_info.confidence:.2f}")
            return True
        
        print(f"✗ 不延长止盈: 利润{current_profit_pct:.1f}% 趋势{trend_info.strength.value} 置信{trend_info.confidence:.2f}")
        return False
    
    def should_extend_profit_target_原版(self, trend_info: TrendInfo, 
                                  current_profit_pct: float) -> bool:
        """
        判断是否应该延长止盈目标
        
        延长条件:
        1. 强趋势 + 利润未达到5% + 动量充足
        2. 极强趋势 + 高置信度 + 利润未达到10%
        
        Args:
            trend_info: 当前趋势信息
            current_profit_pct: 当前利润百分比
            
        Returns:
            bool: True表示应该延长止盈，False表示正常止盈
        """
        # 条件1: 强趋势且利润还不够大时，延长止盈
        if (trend_info.is_strong_trend() and 
            current_profit_pct < 5.0 and  # 利润小于5%
            trend_info.momentum_score > 0.6):
            print(f"✓ 延长止盈: 强趋势 + 利润{current_profit_pct:.1f}% < 5% + 动量{trend_info.momentum_score:.2f}")
            return True
        
        # 条件2: 极强趋势时，即使利润较大也可以继续持有
        if (trend_info.strength == TrendStrength.EXTREME and
            trend_info.confidence > 0.8 and
            current_profit_pct < 10.0):  # 利润小于10%
            print(f"✓ 延长止盈: 极强趋势 + 高置信度{trend_info.confidence:.2f} + 利润{current_profit_pct:.1f}% < 10%")
            return True
        
        print(f"✗ 不延长止盈: 趋势强度{trend_info.strength.name} 利润{current_profit_pct:.1f}%")
        return False
    def calculate_dynamic_profit_target(self, trend_info: TrendInfo, entry_price: float, direction: str) -> float:
        """计算动态止盈目标 - 激进版"""
        if not trend_info:
            return entry_price * (1.02 if direction == 'buy' else 0.98)
        
        # 🔥 激进的盈亏比目标
        base_targets = {
            TrendStrength.WEAK: 0.02,        # 从0.015提高到0.02
            TrendStrength.MODERATE: 0.035,   # 从0.025提高到0.035  
            TrendStrength.STRONG: 0.06,      # 从0.04提高到0.06 ⭐关键
            TrendStrength.VERY_STRONG: 0.10, # 从0.08提高到0.10
            TrendStrength.EXTREME: 0.15      # 从0.12提高到0.15
        }
        
        target_pct = base_targets.get(trend_info.strength, 0.02)
        
        # 置信度加成 - 更激进
        confidence_boost = min(0.05, trend_info.confidence * 0.08)  # 从0.05提高到0.08
        final_target_pct = target_pct + confidence_boost
        
        if direction == 'buy':
            return entry_price * (1 + final_target_pct)
        else:
            return entry_price * (1 - final_target_pct)
            
    def calculate_dynamic_profit_target_原版(self, trend_info: TrendInfo, 
                                      entry_price: float, direction: str) -> float:
        """
        计算动态止盈目标
        
        计算逻辑:
        1. 基础目标: 2%
        2. 强度倍数: 根据趋势强度调整 (1x-6x)
        3. 置信度调整: 乘以置信度
        4. 动量调整: 乘以(0.5+动量得分)
        5. 突破加成: 突破强度额外加成
        
        Args:
            trend_info: 趋势信息
            entry_price: 入场价格
            direction: 交易方向 ('buy' or 'sell')
            
        Returns:
            float: 动态止盈目标价格
        """
        base_target_pct = 2.0  # 基础2%止盈
        
        # === 趋势强度倍数 ===
        strength_multiplier = {
            TrendStrength.WEAK: 1.0,
            TrendStrength.MODERATE: 1.5,
            TrendStrength.STRONG: 2.5,
            TrendStrength.VERY_STRONG: 4.0,
            TrendStrength.EXTREME: 6.0
        }
        
        target_pct = base_target_pct * strength_multiplier[trend_info.strength]
        print(f"   基础目标: {base_target_pct}% × 强度倍数{strength_multiplier[trend_info.strength]} = {target_pct}%")
        
        # === 置信度调整 ===
        target_pct *= trend_info.confidence
        print(f"   置信度调整: × {trend_info.confidence:.2f} = {target_pct:.1f}%")
        
        # === 动量调整 ===
        momentum_factor = 0.5 + trend_info.momentum_score
        target_pct *= momentum_factor
        print(f"   动量调整: × {momentum_factor:.2f} = {target_pct:.1f}%")
        
        # === 突破强度加成 ===
        if trend_info.breakout_strength > 0.3:
            breakout_bonus = 1 + trend_info.breakout_strength
            target_pct *= breakout_bonus
            print(f"   突破加成: × {breakout_bonus:.2f} = {target_pct:.1f}%")
        
        # === 计算目标价格 ===
        if direction == 'buy':
            target_price = entry_price * (1 + target_pct / 100)
        else:
            target_price = entry_price * (1 - target_pct / 100)
        
        print(f"   最终目标: {target_price:.4f} (利润{target_pct:.1f}%)")
        return target_price
    
    def get_trailing_stop_distance(self, trend_info: TrendInfo) -> float:
        """
        获取追踪止损距离 - 基于趋势特征动态调整
        
        基础距离: 1%
        调整因子:
        - 强趋势: +50% (给更多空间)
        - 高波动: +30% (适应波动)
        
        Args:
            trend_info: 趋势信息
            
        Returns:
            float: 追踪止损距离百分比
        """
        base_distance = 1.0  # 基础1%
        
        # 强趋势时放宽止损距离，避免被震出
        if trend_info.strength.value >= 3:
            base_distance *= 1.5
            print(f"   止损调整: 强趋势 +50%")
        
        # 高波动时放宽止损距离，适应波动
        if trend_info.volatility_expansion:
            base_distance *= 1.3
            print(f"   止损调整: 高波动 +30%")
        
        print(f"   追踪止损距离: {base_distance:.1f}%")
        return base_distance