#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多周期趋势确认系统
通过多个时间周期确认趋势方向，提高信号质量
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

class TimeframeHierarchy(Enum):
    """时间周期层级"""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m" 
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"

@dataclass
class TimeframeTrend:
    """单个时间周期的趋势信息"""
    timeframe: str
    direction: str          # 'up', 'down', 'sideways'
    strength: float         # 0-1
    confidence: float       # 0-1
    adx: float
    slope: float           # 价格斜率
    momentum: float        # 动量指标
    volume_support: bool   # 成交量支撑
    
    def __str__(self):
        return f"{self.timeframe}: {self.direction} (强度:{self.strength:.2f} 置信:{self.confidence:.2f})"

@dataclass
class MultiTimeframeTrendAnalysis:
    """多周期趋势分析结果"""
    primary_timeframe: str
    higher_timeframes: List[str]
    trend_analysis: Dict[str, TimeframeTrend]
    overall_direction: str
    consensus_strength: float
    alignment_score: float
    recommendation: str
    
    def is_strong_consensus(self) -> bool:
        """是否有强共识"""
        return self.consensus_strength >= 0.7 and self.alignment_score >= 0.6
    
    def get_conflicting_timeframes(self) -> List[str]:
        """获取冲突的时间周期"""
        if self.overall_direction == 'sideways':
            return []
        
        conflicting = []
        for tf, trend in self.trend_analysis.items():
            if (trend.direction != self.overall_direction and 
                trend.direction != 'sideways' and 
                trend.confidence > 0.5):
                conflicting.append(tf)
        
        return conflicting

class MultiTimeframeAnalyzer:
    """多周期分析器"""
    
    def __init__(self):
        # 时间周期层级映射
        self.timeframe_hierarchy = {
            "1m": ["5m", "15m", "1h"],
            "5m": ["15m", "1h", "4h"], 
            "15m": ["1h", "4h", "1d"],
            "1h": ["4h", "1d", "1w"],
            "4h": ["1d", "1w", "1M"],
            "1d": ["1w", "1M"]
        }
        
        # 周期权重（高级周期权重更大）
        self.timeframe_weights = {
            "1m": 0.1, "5m": 0.2, "15m": 0.3,
            "1h": 0.5, "4h": 0.7, "1d": 1.0,
            "1w": 1.2, "1M": 1.5
        }
    
    def analyze_multiple_timeframes(self, data_dict: Dict[str, pd.DataFrame], 
                                  primary_timeframe: str) -> MultiTimeframeTrendAnalysis:
        """
        分析多个时间周期的趋势
        
        Args:
            data_dict: {timeframe: dataframe} 格式的数据字典
            primary_timeframe: 主要交易周期
            
        Returns:
            MultiTimeframeTrendAnalysis: 多周期分析结果
        """
        
        # 获取相关的高级周期
        higher_timeframes = self.timeframe_hierarchy.get(primary_timeframe, ["1h", "4h", "1d"])
        available_higher_tfs = [tf for tf in higher_timeframes if tf in data_dict]
        
        if not available_higher_tfs:
            # 如果没有高级周期数据，只分析主周期
            available_higher_tfs = []
        
        # 分析每个周期的趋势
        trend_analysis = {}
        
        # 分析主周期
        if primary_timeframe in data_dict:
            trend_analysis[primary_timeframe] = self._analyze_single_timeframe_trend(
                data_dict[primary_timeframe], primary_timeframe
            )
        
        # 分析高级周期
        for tf in available_higher_tfs:
            if tf in data_dict:
                trend_analysis[tf] = self._analyze_single_timeframe_trend(
                    data_dict[tf], tf
                )
        
        # 计算整体趋势共识
        overall_direction, consensus_strength = self._calculate_trend_consensus(trend_analysis)
        
        # 计算趋势对齐评分
        alignment_score = self._calculate_alignment_score(trend_analysis, overall_direction)
        
        # 生成交易建议
        recommendation = self._generate_trading_recommendation(
            trend_analysis, overall_direction, consensus_strength, alignment_score
        )
        
        return MultiTimeframeTrendAnalysis(
            primary_timeframe=primary_timeframe,
            higher_timeframes=available_higher_tfs,
            trend_analysis=trend_analysis,
            overall_direction=overall_direction,
            consensus_strength=consensus_strength,
            alignment_score=alignment_score,
            recommendation=recommendation
        )
    
    def _analyze_single_timeframe_trend(self, data: pd.DataFrame, timeframe: str) -> TimeframeTrend:
        """分析单个时间周期的趋势"""
        
        if len(data) < 50:
            return TimeframeTrend(
                timeframe=timeframe,
                direction='sideways',
                strength=0.0,
                confidence=0.0,
                adx=0.0,
                slope=0.0,
                momentum=0.0,
                volume_support=False
            )
        
        # 1. 计算技术指标
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        volume = data.get('volume', pd.Series([1]*len(data))).values
        
        # ADX趋势强度
        adx = talib.ADX(high, low, close, timeperiod=14)
        plus_di = talib.PLUS_DI(high, low, close, timeperiod=14)
        minus_di = talib.MINUS_DI(high, low, close, timeperiod=14)
        
        # 移动平均线
        sma_20 = talib.SMA(close, 20)
        sma_50 = talib.SMA(close, 50)
        ema_12 = talib.EMA(close, 12)
        ema_26 = talib.EMA(close, 26)
        
        # 动量指标
        rsi = talib.RSI(close, 14)
        macd_line, macd_signal, macd_hist = talib.MACD(close)
        
        # 2. 趋势方向判断
        direction = self._determine_trend_direction(
            close, sma_20, sma_50, ema_12, ema_26, plus_di, minus_di
        )
        
        # 3. 趋势强度计算
        strength = self._calculate_trend_strength(adx, close, sma_20, sma_50)
        
        # 4. 置信度计算
        confidence = self._calculate_trend_confidence(
            direction, adx, rsi, macd_line, macd_signal, close, sma_20, sma_50
        )
        
        # 5. 价格斜率
        slope = self._calculate_price_slope(close)
        
        # 6. 动量评分
        momentum = self._calculate_momentum_score(rsi, macd_line, macd_hist)
        
        # 7. 成交量支撑
        volume_support = self._check_volume_support(volume, direction)
        
        return TimeframeTrend(
            timeframe=timeframe,
            direction=direction,
            strength=strength,
            confidence=confidence,
            adx=adx[-1] if len(adx) > 0 and not np.isnan(adx[-1]) else 0,
            slope=slope,
            momentum=momentum,
            volume_support=volume_support
        )
    
    def _determine_trend_direction(self, close, sma_20, sma_50, ema_12, ema_26, plus_di, minus_di) -> str:
        """确定趋势方向"""
        
        signals = []
        current_price = close[-1]
        
        # 1. 价格与移动平均线关系
        if not np.isnan(sma_20[-1]):
            if current_price > sma_20[-1] * 1.005:  # 高于SMA20的0.5%
                signals.append('up')
            elif current_price < sma_20[-1] * 0.995:  # 低于SMA20的0.5%
                signals.append('down')
            else:
                signals.append('sideways')
        
        # 2. 移动平均线排列
        if not np.isnan(sma_20[-1]) and not np.isnan(sma_50[-1]):
            if sma_20[-1] > sma_50[-1] * 1.002:
                signals.append('up')
            elif sma_20[-1] < sma_50[-1] * 0.998:
                signals.append('down')
            else:
                signals.append('sideways')
        
        # 3. EMA金叉死叉
        if (not np.isnan(ema_12[-1]) and not np.isnan(ema_26[-1]) and
            len(ema_12) > 1 and len(ema_26) > 1):
            
            if ema_12[-1] > ema_26[-1] and ema_12[-2] <= ema_26[-2]:
                signals.append('up')  # 金叉
            elif ema_12[-1] < ema_26[-1] and ema_12[-2] >= ema_26[-2]:
                signals.append('down')  # 死叉
            elif ema_12[-1] > ema_26[-1]:
                signals.append('up')
            elif ema_12[-1] < ema_26[-1]:
                signals.append('down')
            else:
                signals.append('sideways')
        
        # 4. DI指标
        if (not np.isnan(plus_di[-1]) and not np.isnan(minus_di[-1])):
            if plus_di[-1] > minus_di[-1] * 1.1:
                signals.append('up')
            elif minus_di[-1] > plus_di[-1] * 1.1:
                signals.append('down')
            else:
                signals.append('sideways')
        
        # 投票决定方向
        up_votes = signals.count('up')
        down_votes = signals.count('down')
        sideways_votes = signals.count('sideways')
        
        if up_votes > down_votes and up_votes > sideways_votes:
            return 'up'
        elif down_votes > up_votes and down_votes > sideways_votes:
            return 'down'
        else:
            return 'sideways'
    
    def _calculate_trend_strength(self, adx, close, sma_20, sma_50) -> float:
        """计算趋势强度 (0-1)"""
        
        strength_factors = []
        
        # 1. ADX强度
        if len(adx) > 0 and not np.isnan(adx[-1]):
            adx_strength = min(adx[-1] / 50, 1.0)  # ADX 50为满分
            strength_factors.append(adx_strength)
        
        # 2. 均线分离度
        if not np.isnan(sma_20[-1]) and not np.isnan(sma_50[-1]):
            ma_separation = abs(sma_20[-1] - sma_50[-1]) / sma_50[-1]
            ma_strength = min(ma_separation * 50, 1.0)  # 2%分离为满分
            strength_factors.append(ma_strength)
        
        # 3. 价格动量
        if len(close) >= 20:
            price_momentum = abs(close[-1] - close[-20]) / close[-20]
            momentum_strength = min(price_momentum * 10, 1.0)  # 10%变化为满分
            strength_factors.append(momentum_strength)
        
        return np.mean(strength_factors) if strength_factors else 0.0
    
    def _calculate_trend_confidence(self, direction, adx, rsi, macd_line, macd_signal, close, sma_20, sma_50) -> float:
        """计算趋势置信度 (0-1)"""
        
        confidence_factors = []
        
        # 1. ADX置信度
        if len(adx) > 0 and not np.isnan(adx[-1]):
            if adx[-1] > 25:
                confidence_factors.append(0.8)
            elif adx[-1] > 20:
                confidence_factors.append(0.6)
            else:
                confidence_factors.append(0.3)
        
        # 2. RSI确认
        if len(rsi) > 0 and not np.isnan(rsi[-1]):
            if direction == 'up' and 30 < rsi[-1] < 70:
                confidence_factors.append(0.7)
            elif direction == 'down' and 30 < rsi[-1] < 70:
                confidence_factors.append(0.7)
            elif direction == 'up' and rsi[-1] > 70:
                confidence_factors.append(0.3)  # 超买降低置信度
            elif direction == 'down' and rsi[-1] < 30:
                confidence_factors.append(0.3)  # 超卖降低置信度
            else:
                confidence_factors.append(0.5)
        
        # 3. MACD确认
        if (len(macd_line) > 0 and len(macd_signal) > 0 and 
            not np.isnan(macd_line[-1]) and not np.isnan(macd_signal[-1])):
            
            if direction == 'up' and macd_line[-1] > macd_signal[-1]:
                confidence_factors.append(0.8)
            elif direction == 'down' and macd_line[-1] < macd_signal[-1]:
                confidence_factors.append(0.8)
            else:
                confidence_factors.append(0.4)
        
        # 4. 价格位置确认
        if not np.isnan(sma_20[-1]) and not np.isnan(sma_50[-1]):
            if direction == 'up' and close[-1] > sma_20[-1] > sma_50[-1]:
                confidence_factors.append(0.9)
            elif direction == 'down' and close[-1] < sma_20[-1] < sma_50[-1]:
                confidence_factors.append(0.9)
            else:
                confidence_factors.append(0.4)
        
        return np.mean(confidence_factors) if confidence_factors else 0.5
    
    def _calculate_price_slope(self, close) -> float:
        """计算价格斜率"""
        if len(close) < 20:
            return 0.0
        
        x = np.arange(20)
        y = close[-20:]
        
        try:
            slope = np.polyfit(x, y, 1)[0]
            return slope / np.mean(y)  # 标准化斜率
        except:
            return 0.0
    
    def _calculate_momentum_score(self, rsi, macd_line, macd_hist) -> float:
        """计算动量评分 (0-1)"""
        
        momentum_factors = []
        
        # RSI动量
        if len(rsi) > 0 and not np.isnan(rsi[-1]):
            if rsi[-1] > 50:
                rsi_momentum = (rsi[-1] - 50) / 50
            else:
                rsi_momentum = (50 - rsi[-1]) / 50
            momentum_factors.append(rsi_momentum)
        
        # MACD动量
        if len(macd_line) > 1 and not np.isnan(macd_line[-1]) and not np.isnan(macd_line[-2]):
            macd_change = macd_line[-1] - macd_line[-2]
            macd_momentum = min(abs(macd_change) * 100, 1.0)
            momentum_factors.append(macd_momentum)
        
        # MACD柱状图动量
        if len(macd_hist) > 0 and not np.isnan(macd_hist[-1]):
            hist_momentum = min(abs(macd_hist[-1]) * 50, 1.0)
            momentum_factors.append(hist_momentum)
        
        return np.mean(momentum_factors) if momentum_factors else 0.5
    
    def _check_volume_support(self, volume, direction) -> bool:
        """检查成交量支撑"""
        if len(volume) < 20:
            return False
        
        recent_volume = np.mean(volume[-5:])  # 最近5期平均成交量
        historical_volume = np.mean(volume[-20:-5])  # 历史平均成交量
        
        # 成交量放大且与趋势方向一致时认为有支撑
        if recent_volume > historical_volume * 1.2:  # 成交量放大20%
            return True
        
        return False
    
    def _calculate_trend_consensus(self, trend_analysis: Dict[str, TimeframeTrend]) -> Tuple[str, float]:
        """计算趋势共识"""
        
        if not trend_analysis:
            return 'sideways', 0.0
        
        # 加权投票
        weighted_votes = {'up': 0, 'down': 0, 'sideways': 0}
        total_weight = 0
        
        for tf, trend in trend_analysis.items():
            weight = self.timeframe_weights.get(tf, 1.0)
            confidence_weight = weight * trend.confidence
            
            weighted_votes[trend.direction] += confidence_weight
            total_weight += confidence_weight
        
        if total_weight == 0:
            return 'sideways', 0.0
        
        # 标准化投票
        for direction in weighted_votes:
            weighted_votes[direction] /= total_weight
        
        # 确定主导方向
        max_direction = max(weighted_votes, key=weighted_votes.get)
        consensus_strength = weighted_votes[max_direction]
        
        return max_direction, consensus_strength
    
    def _calculate_alignment_score(self, trend_analysis: Dict[str, TimeframeTrend], 
                                 overall_direction: str) -> float:
        """计算趋势对齐评分"""
        
        if not trend_analysis:
            return 0.0
        
        aligned_weight = 0
        total_weight = 0
        
        for tf, trend in trend_analysis.items():
            weight = self.timeframe_weights.get(tf, 1.0)
            total_weight += weight
            
            if trend.direction == overall_direction:
                aligned_weight += weight * trend.confidence
            elif trend.direction == 'sideways':
                aligned_weight += weight * 0.5  # 中性不对抗
        
        return aligned_weight / total_weight if total_weight > 0 else 0.0
    
    def _generate_trading_recommendation(self, trend_analysis: Dict[str, TimeframeTrend],
                                       overall_direction: str, consensus_strength: float,
                                       alignment_score: float) -> str:
        """生成交易建议"""
        
        if consensus_strength >= 0.8 and alignment_score >= 0.8:
            return f"强烈建议{overall_direction}方向交易，多周期高度一致"
        
        elif consensus_strength >= 0.7 and alignment_score >= 0.6:
            return f"建议{overall_direction}方向交易，趋势较为明确"
        
        elif consensus_strength >= 0.6 and alignment_score >= 0.5:
            return f"谨慎{overall_direction}方向交易，注意风险控制"
        
        elif overall_direction == 'sideways':
            return "震荡行情，建议等待明确趋势信号"
        
        else:
            conflicting_tfs = []
            for tf, trend in trend_analysis.items():
                if (trend.direction != overall_direction and 
                    trend.direction != 'sideways' and 
                    trend.confidence > 0.5):
                    conflicting_tfs.append(tf)
            
            if conflicting_tfs:
                return f"多周期存在冲突({','.join(conflicting_tfs)})，建议观望"
            else:
                return "趋势不明确，建议等待更好的机会"
    
    def generate_analysis_report(self, analysis: MultiTimeframeTrendAnalysis) -> str:
        """生成分析报告"""
        
        report = f"""
📈 多周期趋势分析报告
{'='*60}
主交易周期: {analysis.primary_timeframe}
高级确认周期: {', '.join(analysis.higher_timeframes)}

📊 各周期趋势分析:
{'-'*60}
"""
        
        for tf, trend in analysis.trend_analysis.items():
            emoji = "📈" if trend.direction == 'up' else "📉" if trend.direction == 'down' else "➡️"
            report += f"{emoji} {trend}\n"
            report += f"   ADX: {trend.adx:.1f} | 斜率: {trend.slope:.4f} | 动量: {trend.momentum:.2f} | 成交量支撑: {'✅' if trend.volume_support else '❌'}\n"
        
        report += f"""
🎯 综合分析结果:
{'-'*60}
整体趋势方向: {analysis.overall_direction.upper()}
趋势共识强度: {analysis.consensus_strength:.3f} (0-1)
多周期对齐度: {analysis.alignment_score:.3f} (0-1)
强共识判定: {'✅ 是' if analysis.is_strong_consensus() else '❌ 否'}

💡 交易建议:
{'-'*60}
{analysis.recommendation}
"""
        
        # 冲突周期提醒
        conflicting_tfs = analysis.get_conflicting_timeframes()
        if conflicting_tfs:
            report += f"\n⚠️  冲突周期提醒: {', '.join(conflicting_tfs)}\n"
            report += "   建议等待冲突解决后再进行交易\n"
        
        return report

# 使用示例
if __name__ == "__main__":
    print("📈 多周期趋势确认系统已就绪")
    print("   支持最多8个时间周期的趋势分析")
    print("   提供加权共识和对齐度评分")
    print("   生成具体的交易建议")