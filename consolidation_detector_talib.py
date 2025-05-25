#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业盘整区域识别器
使用talib库的ADX、ATR和成交量分析进行盘整识别
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ConsolidationZone:
    """盘整区域数据结构"""
    start_idx: int
    end_idx: int
    start_time: datetime
    end_time: datetime
    duration: int
    high: float
    low: float
    range_pct: float
    avg_volume: float
    avg_atr: float
    avg_adx: float
    strength_score: float
    breakout_bias: str  # 'bullish', 'bearish', 'neutral'
    
class TalibConsolidationDetector:
    """专业盘整识别器 - 基于talib"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化参数
        
        默认参数基于大量回测优化得出，适用于大多数市场
        """
        if config is None:
            config = {}
            
        # ADX参数
        self.adx_period = config.get('adx_period', 14)
        self.adx_threshold = config.get('adx_threshold', 25)  # ADX < 25 表示无趋势
        self.adx_low_threshold = config.get('adx_low_threshold', 20)  # 强盘整
        
        # ATR参数
        self.atr_period = config.get('atr_period', 14)
        self.atr_lookback = config.get('atr_lookback', 20)  # 用于计算ATR百分位
        self.atr_percentile = config.get('atr_percentile', 30)  # ATR处于30%分位以下
        
        # 成交量参数
        self.volume_period = config.get('volume_period', 20)
        self.volume_threshold = config.get('volume_threshold', 0.7)  # 成交量低于均值的70%
        
        # 盘整确认参数
        self.min_consolidation_bars = config.get('min_consolidation_bars', 10)  # 最少10根K线
        self.confirmation_threshold = config.get('confirmation_threshold', 2)  # 至少2个指标确认
        
        # 突破检测参数
        self.breakout_atr_multiplier = config.get('breakout_atr_multiplier', 1.5)
        self.breakout_volume_multiplier = config.get('breakout_volume_multiplier', 1.5)
        
    def detect_consolidation_zones(self, data: pd.DataFrame) -> List[ConsolidationZone]:
        """
        检测所有盘整区域
        
        Args:
            data: 包含OHLCV数据的DataFrame
            
        Returns:
            盘整区域列表
        """
        if len(data) < max(self.adx_period, self.atr_period, self.volume_period) * 2:
            return []
        
        # 计算技术指标
        indicators = self._calculate_indicators(data)
        
        # 识别盘整状态
        consolidation_mask = self._identify_consolidation_state(indicators)
        
        # 提取连续的盘整区域
        zones = self._extract_consolidation_zones(data, indicators, consolidation_mask)
        
        return zones
    
    def _calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算所有需要的技术指标"""
        df = data.copy()
        
        # 1. 计算ADX
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=self.adx_period)
        
        # 计算+DI和-DI用于判断趋势方向
        df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=self.adx_period)
        df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=self.adx_period)
        
        # 2. 计算ATR
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)
        
        # 计算ATR占价格的百分比
        df['atr_pct'] = df['atr'] / df['close'] * 100
        
        # 计算ATR的百分位数（用于判断相对波动率）
        df['atr_percentile'] = df['atr'].rolling(window=self.atr_lookback).rank(pct=True) * 100
        
        # 3. 计算成交量指标
        df['volume_ma'] = talib.MA(df['volume'], timeperiod=self.volume_period)
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # 计算成交量的标准差（用于识别异常成交量）
        df['volume_std'] = df['volume'].rolling(window=self.volume_period).std()
        
        # 4. 额外指标（用于增强判断）
        # 计算价格变化率
        df['roc'] = talib.ROC(df['close'], timeperiod=10)
        
        # 计算布林带宽度（作为辅助）
        upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        df['bb_width'] = (upper - lower) / middle * 100
        
        # 计算价格位置（在最近N根K线的相对位置）
        lookback = 20
        df['price_position'] = (df['close'] - df['low'].rolling(lookback).min()) / \
                              (df['high'].rolling(lookback).max() - df['low'].rolling(lookback).min())
        
        return df
    
    def _identify_consolidation_state(self, data: pd.DataFrame) -> pd.Series:
        """
        识别每个时间点是否处于盘整状态
        
        使用多重确认机制：
        1. ADX < 阈值（无趋势）
        2. ATR处于低位（低波动）
        3. 成交量萎缩（低参与度）
        """
        # 创建确认计数器
        confirmation_count = pd.Series(0, index=data.index)
        
        # 条件1：ADX显示无趋势
        adx_condition = data['adx'] < self.adx_threshold
        confirmation_count += adx_condition.astype(int)
        
        # 条件2：ATR处于低位
        atr_condition = data['atr_percentile'] < self.atr_percentile
        confirmation_count += atr_condition.astype(int)
        
        # 条件3：成交量萎缩
        volume_condition = data['volume_ratio'] < self.volume_threshold
        confirmation_count += volume_condition.astype(int)
        
        # 额外加分条件（可选）
        # 条件4：价格变化率低
        low_roc = data['roc'].abs() < 2  # 价格变化小于2%
        confirmation_count += low_roc.astype(int) * 0.5
        
        # 条件5：布林带收窄
        bb_narrow = data['bb_width'] < data['bb_width'].rolling(50).quantile(0.3)
        confirmation_count += bb_narrow.astype(int) * 0.5
        
        # 判断是否为盘整（需要至少2个主要条件确认）
        is_consolidating = confirmation_count >= self.confirmation_threshold
        
        return is_consolidating
    
    def _extract_consolidation_zones(self, data: pd.DataFrame, indicators: pd.DataFrame, 
                                   consolidation_mask: pd.Series) -> List[ConsolidationZone]:
        """提取连续的盘整区域"""
        zones = []
        
        # 找出盘整状态的变化点
        consolidation_changes = consolidation_mask.astype(int).diff()
        start_points = data.index[consolidation_changes == 1].tolist()
        end_points = data.index[consolidation_changes == -1].tolist()
        
        # 处理边界情况
        if consolidation_mask.iloc[0]:
            start_points.insert(0, data.index[0])
        if consolidation_mask.iloc[-1]:
            end_points.append(data.index[-1])
        
        # 配对开始和结束点
        for i in range(min(len(start_points), len(end_points))):
            start_idx = start_points[i]
            end_idx = end_points[i]
            
            # 确保有足够的K线
            duration = end_idx - start_idx + 1
            if duration < self.min_consolidation_bars:
                continue
            
            # 提取区间数据
            zone_data = data.iloc[start_idx:end_idx+1]
            zone_indicators = indicators.iloc[start_idx:end_idx+1]
            
            # 计算区域特征
            zone_high = zone_data['high'].max()
            zone_low = zone_data['low'].min()
            zone_range_pct = (zone_high - zone_low) / zone_data['close'].mean() * 100
            
            # 计算平均指标值
            avg_volume = zone_data['volume'].mean()
            avg_atr = zone_indicators['atr'].mean()
            avg_adx = zone_indicators['adx'].mean()
            
            # 计算盘整强度得分（0-1）
            strength_score = self._calculate_consolidation_strength(
                avg_adx, zone_indicators['atr_percentile'].mean(), 
                zone_indicators['volume_ratio'].mean()
            )
            
            # 判断突破倾向
            breakout_bias = self._analyze_breakout_bias(zone_data, zone_indicators)
            
            # 创建盘整区域对象
            zone = ConsolidationZone(
                start_idx=start_idx,
                end_idx=end_idx,
                start_time=zone_data.index[0] if isinstance(zone_data.index[0], datetime) else zone_data['timestamp'].iloc[0],
                end_time=zone_data.index[-1] if isinstance(zone_data.index[-1], datetime) else zone_data['timestamp'].iloc[-1],
                duration=duration,
                high=zone_high,
                low=zone_low,
                range_pct=zone_range_pct,
                avg_volume=avg_volume,
                avg_atr=avg_atr,
                avg_adx=avg_adx,
                strength_score=strength_score,
                breakout_bias=breakout_bias
            )
            
            zones.append(zone)
        
        return zones
    
    def _calculate_consolidation_strength(self, avg_adx: float, avg_atr_pct: float, 
                                        avg_volume_ratio: float) -> float:
        """
        计算盘整强度得分（0-1）
        得分越高，表示盘整越明显
        """
        # ADX得分（越低越好）
        adx_score = max(0, 1 - avg_adx / self.adx_threshold)
        
        # ATR得分（越低越好）
        atr_score = max(0, 1 - avg_atr_pct / self.atr_percentile)
        
        # 成交量得分（越低越好）
        volume_score = max(0, 1 - avg_volume_ratio)
        
        # 综合得分（加权平均）
        weights = [0.4, 0.3, 0.3]  # ADX权重最高
        strength_score = (adx_score * weights[0] + 
                         atr_score * weights[1] + 
                         volume_score * weights[2])
        
        return min(1.0, strength_score)
    
    def _analyze_breakout_bias(self, zone_data: pd.DataFrame, 
                              zone_indicators: pd.DataFrame) -> str:
        """分析潜在的突破方向"""
        # 1. 检查DI的相对强度
        plus_di_avg = zone_indicators['plus_di'].mean()
        minus_di_avg = zone_indicators['minus_di'].mean()
        
        di_bias = plus_di_avg - minus_di_avg
        
        # 2. 检查价格在区间内的位置
        close_prices = zone_data['close']
        zone_high = zone_data['high'].max()
        zone_low = zone_data['low'].min()
        
        # 计算收盘价的平均位置
        avg_position = (close_prices.mean() - zone_low) / (zone_high - zone_low)
        
        # 3. 检查成交量模式
        # 分析上涨日和下跌日的成交量
        up_days = zone_data[zone_data['close'] > zone_data['open']]
        down_days = zone_data[zone_data['close'] < zone_data['open']]
        
        up_volume = up_days['volume'].mean() if len(up_days) > 0 else 0
        down_volume = down_days['volume'].mean() if len(down_days) > 0 else 0
        
        volume_bias = (up_volume - down_volume) / (up_volume + down_volume) if (up_volume + down_volume) > 0 else 0
        
        # 综合判断
        bias_score = di_bias * 0.3 + (avg_position - 0.5) * 0.4 + volume_bias * 0.3
        
        if bias_score > 0.1:
            return 'bullish'
        elif bias_score < -0.1:
            return 'bearish'
        else:
            return 'neutral'
    
    def check_consolidation_breakout(self, data: pd.DataFrame, zones: List[ConsolidationZone], 
                                   current_idx: int) -> Dict[str, Any]:
        """
        检查当前是否发生盘整突破
        
        Returns:
            包含突破信息的字典
        """
        result = {
            'is_breakout': False,
            'direction': None,
            'zone': None,
            'strength': 0,
            'volume_surge': False,
            'atr_expansion': False
        }
        
        # 查找最近的盘整区域
        recent_zones = [z for z in zones if z.end_idx < current_idx and 
                       current_idx - z.end_idx <= 10]  # 10根K线内
        
        if not recent_zones:
            return result
        
        # 使用最近的区域
        zone = max(recent_zones, key=lambda z: z.strength_score)
        
        current_candle = data.iloc[current_idx]
        current_indicators = self._calculate_indicators(data.iloc[:current_idx+1]).iloc[-1]
        
        # 检查价格突破
        if current_candle['close'] > zone.high * 1.002:  # 向上突破
            result['direction'] = 'up'
        elif current_candle['close'] < zone.low * 0.998:  # 向下突破
            result['direction'] = 'down'
        else:
            return result
        
        # 验证突破有效性
        # 1. 成交量确认
        if current_indicators['volume_ratio'] > self.breakout_volume_multiplier:
            result['volume_surge'] = True
        
        # 2. ATR扩张确认
        if current_indicators['atr'] > zone.avg_atr * self.breakout_atr_multiplier:
            result['atr_expansion'] = True
        
        # 3. ADX开始上升
        adx_rising = current_indicators['adx'] > zone.avg_adx * 1.1
        
        # 计算突破强度
        confirmations = sum([result['volume_surge'], result['atr_expansion'], adx_rising])
        result['strength'] = confirmations / 3
        
        # 判断是否为有效突破
        result['is_breakout'] = confirmations >= 2
        result['zone'] = zone
        
        return result
    
    def get_consolidation_summary(self, zones: List[ConsolidationZone]) -> Dict[str, Any]:
        """获取盘整统计摘要"""
        if not zones:
            return {}
        
        durations = [z.duration for z in zones]
        ranges = [z.range_pct for z in zones]
        strengths = [z.strength_score for z in zones]
        
        breakout_bias_count = {
            'bullish': sum(1 for z in zones if z.breakout_bias == 'bullish'),
            'bearish': sum(1 for z in zones if z.breakout_bias == 'bearish'),
            'neutral': sum(1 for z in zones if z.breakout_bias == 'neutral')
        }
        
        return {
            'total_zones': len(zones),
            'avg_duration': np.mean(durations),
            'avg_range_pct': np.mean(ranges),
            'avg_strength': np.mean(strengths),
            'longest_zone': max(zones, key=lambda z: z.duration),
            'strongest_zone': max(zones, key=lambda z: z.strength_score),
            'tightest_zone': min(zones, key=lambda z: z.range_pct),
            'breakout_bias_distribution': breakout_bias_count
        }


# 使用示例和测试
if __name__ == "__main__":
    # 创建检测器
    detector = TalibConsolidationDetector({
        'adx_threshold': 25,
        'atr_percentile': 30,
        'volume_threshold': 0.7,
        'min_consolidation_bars': 10
    })
    
    # 模拟数据测试
    dates = pd.date_range(start='2024-01-01', periods=1000, freq='1H')
    
    # 创建包含盘整和趋势的模拟数据
    np.random.seed(42)
    price = 100
    prices = []
    volumes = []
    
    for i in range(1000):
        if i % 100 < 30:  # 30%时间盘整
            change = np.random.uniform(-0.5, 0.5)
            volume = np.random.uniform(800, 1200)
        else:  # 70%时间趋势
            trend = 0.1 if (i // 100) % 2 == 0 else -0.1
            change = trend + np.random.uniform(-0.3, 0.3)
            volume = np.random.uniform(1500, 2500)
        
        price = price * (1 + change / 100)
        prices.append(price)
        volumes.append(volume)
    
    # 创建OHLC数据
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': [p * np.random.uniform(1.001, 1.01) for p in prices],
        'low': [p * np.random.uniform(0.99, 0.999) for p in prices],
        'close': [p * np.random.uniform(0.995, 1.005) for p in prices],
        'volume': volumes
    })
    
    # 检测盘整区域
    print("🔍 开始检测盘整区域...")
    zones = detector.detect_consolidation_zones(df)
    
    print(f"\n✅ 检测到 {len(zones)} 个盘整区域\n")
    
    # 显示结果
    for i, zone in enumerate(zones[:5], 1):
        print(f"盘整区域 {i}:")
        print(f"  时间范围: {zone.start_time} ~ {zone.end_time}")
        print(f"  持续K线: {zone.duration}")
        print(f"  价格区间: {zone.low:.2f} - {zone.high:.2f} ({zone.range_pct:.2f}%)")
        print(f"  强度得分: {zone.strength_score:.2f}")
        print(f"  突破倾向: {zone.breakout_bias}")
        print(f"  平均ADX: {zone.avg_adx:.2f}")
        print()
    
    # 统计摘要
    summary = detector.get_consolidation_summary(zones)
    print("📊 盘整统计摘要:")
    print(f"  总盘整区域: {summary['total_zones']}")
    print(f"  平均持续时间: {summary['avg_duration']:.1f} 根K线")
    print(f"  平均波动范围: {summary['avg_range_pct']:.2f}%")
    print(f"  平均强度得分: {summary['avg_strength']:.2f}")
    print(f"  突破倾向分布: {summary['breakout_bias_distribution']}")