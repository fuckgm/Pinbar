#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应参数系统
根据市场特征自动调整策略参数
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

class MarketType(Enum):
    """市场类型"""
    HIGH_VOL_TRENDING = "高波动趋势"
    HIGH_VOL_RANGING = "高波动震荡"  
    MED_VOL_TRENDING = "中波动趋势"
    MED_VOL_RANGING = "中波动震荡"
    LOW_VOL_TRENDING = "低波动趋势"
    LOW_VOL_RANGING = "低波动震荡"

@dataclass
class MarketCharacteristics:
    """市场特征"""
    volatility: float           # 波动率 (%)
    trend_strength: float       # 趋势强度 (0-1)
    trend_consistency: float    # 趋势一致性 (0-1)
    volume_profile: float       # 成交量特征 (0-1)
    price_efficiency: float     # 价格效率 (0-1)
    market_type: MarketType
    
    def __str__(self):
        return f"波动率:{self.volatility:.1f}% 趋势强度:{self.trend_strength:.2f} 类型:{self.market_type.value}"

class AdaptiveParameterSystem:
    """自适应参数系统"""
    
    def __init__(self):
        # 基础参数模板
        self.base_templates = {
            MarketType.HIGH_VOL_TRENDING: {
                'min_shadow_body_ratio': 1.5,    # 降低要求，增加信号
                'max_body_ratio': 0.35,
                'min_signal_score': 2,
                'volume_threshold': 0.8,          # 放宽成交量要求
                'adx_threshold': 15,
                'rsi_oversold': 35,
                'rsi_overbought': 65,
                'trend_profit_extension': True,
                'max_trend_profit_pct': 20.0,     # 高目标
                'trailing_stop_buffer': 2.0       # 宽止损
            },
            
            MarketType.HIGH_VOL_RANGING: {
                'min_shadow_body_ratio': 2.5,    # 提高要求
                'max_body_ratio': 0.25,
                'min_signal_score': 4,
                'volume_threshold': 1.5,          # 要求成交量确认
                'adx_threshold': 25,
                'rsi_oversold': 25,               # 更严格的超买超卖
                'rsi_overbought': 75,
                'trend_profit_extension': False,
                'max_trend_profit_pct': 5.0,      # 低目标
                'trailing_stop_buffer': 1.0       # 紧止损
            },
            
            MarketType.MED_VOL_TRENDING: {
                'min_shadow_body_ratio': 2.0,
                'max_body_ratio': 0.30,
                'min_signal_score': 3,
                'volume_threshold': 1.0,
                'adx_threshold': 20,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'trend_profit_extension': True,
                'max_trend_profit_pct': 15.0,
                'trailing_stop_buffer': 1.5
            },
            
            MarketType.MED_VOL_RANGING: {
                'min_shadow_body_ratio': 2.3,
                'max_body_ratio': 0.28,
                'min_signal_score': 3,
                'volume_threshold': 1.2,
                'adx_threshold': 22,
                'rsi_oversold': 28,
                'rsi_overbought': 72,
                'trend_profit_extension': False,
                'max_trend_profit_pct': 8.0,
                'trailing_stop_buffer': 1.2
            },
            
            MarketType.LOW_VOL_TRENDING: {
                'min_shadow_body_ratio': 1.8,
                'max_body_ratio': 0.32,
                'min_signal_score': 2,
                'volume_threshold': 0.9,
                'adx_threshold': 18,
                'rsi_oversold': 32,
                'rsi_overbought': 68,
                'trend_profit_extension': True,
                'max_trend_profit_pct': 12.0,
                'trailing_stop_buffer': 1.8
            },
            
            MarketType.LOW_VOL_RANGING: {
                'min_shadow_body_ratio': 2.8,
                'max_body_ratio': 0.22,
                'min_signal_score': 4,
                'volume_threshold': 1.3,
                'adx_threshold': 28,
                'rsi_oversold': 20,
                'rsi_overbought': 80,
                'trend_profit_extension': False,
                'max_trend_profit_pct': 6.0,
                'trailing_stop_buffer': 1.0
            }
        }
    
    def analyze_market_characteristics(self, data: pd.DataFrame, 
                                     lookback_period: int = 200) -> MarketCharacteristics:
        """分析市场特征"""
        
        # 确保数据充足
        if len(data) < lookback_period:
            lookback_period = len(data)
        
        recent_data = data.tail(lookback_period)
        
        # 1. 计算波动率
        volatility = self._calculate_volatility(recent_data)
        
        # 2. 计算趋势强度
        trend_strength = self._calculate_trend_strength(recent_data)
        
        # 3. 计算趋势一致性
        trend_consistency = self._calculate_trend_consistency(recent_data)
        
        # 4. 分析成交量特征
        volume_profile = self._analyze_volume_profile(recent_data)
        
        # 5. 计算价格效率
        price_efficiency = self._calculate_price_efficiency(recent_data)
        
        # 6. 确定市场类型
        market_type = self._determine_market_type(volatility, trend_strength)
        
        return MarketCharacteristics(
            volatility=volatility,
            trend_strength=trend_strength,
            trend_consistency=trend_consistency,
            volume_profile=volume_profile,
            price_efficiency=price_efficiency,
            market_type=market_type
        )
    
    def _calculate_volatility(self, data: pd.DataFrame) -> float:
        """计算年化波动率"""
        returns = data['close'].pct_change().dropna()
        daily_vol = returns.std()
        
        # 根据时间周期调整
        if len(data) > 0:
            # 假设数据是日线，转换为年化
            annualized_vol = daily_vol * np.sqrt(365) * 100
        else:
            annualized_vol = 0
        
        return min(annualized_vol, 200)  # 限制最大值
    
    def _calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """计算趋势强度 (0-1)"""
        if len(data) < 20:
            return 0.5
        
        # 使用ADX
        adx = talib.ADX(data['high'], data['low'], data['close'], timeperiod=14)
        avg_adx = np.nanmean(adx[-20:])  # 最近20期平均
        
        # 标准化到0-1
        normalized_adx = min(avg_adx / 60, 1.0) if not np.isnan(avg_adx) else 0.5
        
        # 使用线性回归斜率确认
        prices = data['close'].values[-50:]  # 最近50个价格
        if len(prices) >= 10:
            x = np.arange(len(prices))
            slope = np.polyfit(x, prices, 1)[0]
            trend_direction_strength = abs(slope) / np.mean(prices)
            trend_direction_strength = min(trend_direction_strength * 100, 1.0)
        else:
            trend_direction_strength = 0
        
        # 综合评分
        return (normalized_adx * 0.7 + trend_direction_strength * 0.3)
    
    def _calculate_trend_consistency(self, data: pd.DataFrame) -> float:
        """计算趋势一致性"""
        if len(data) < 20:
            return 0.5
        
        # 计算不同周期的移动平均线
        sma_10 = talib.SMA(data['close'], 10)
        sma_20 = talib.SMA(data['close'], 20)
        sma_50 = talib.SMA(data['close'], 50) if len(data) >= 50 else sma_20
        
        # 检查均线排列的一致性
        recent_periods = min(20, len(data))
        consistent_periods = 0
        
        for i in range(-recent_periods, 0):
            if (sma_10.iloc[i] > sma_20.iloc[i] > sma_50.iloc[i] or
                sma_10.iloc[i] < sma_20.iloc[i] < sma_50.iloc[i]):
                consistent_periods += 1
        
        return consistent_periods / recent_periods
    
    def _analyze_volume_profile(self, data: pd.DataFrame) -> float:
        """分析成交量特征"""
        if 'volume' not in data.columns or len(data) < 20:
            return 0.5
        
        # 计算成交量的变异系数
        volume_mean = data['volume'].mean()
        volume_std = data['volume'].std()
        
        if volume_mean > 0:
            cv = volume_std / volume_mean  # 变异系数
            # 标准化：变异系数越小，成交量越稳定
            volume_stability = max(0, 1 - cv)
        else:
            volume_stability = 0.5
        
        # 成交量趋势
        volume_sma = talib.SMA(data['volume'], 20)
        recent_volume_trend = (data['volume'].iloc[-1] / volume_sma.iloc[-1] 
                              if not pd.isna(volume_sma.iloc[-1]) and volume_sma.iloc[-1] > 0 
                              else 1.0)
        
        # 综合评分
        return min((volume_stability * 0.6 + min(recent_volume_trend, 2.0) / 2.0 * 0.4), 1.0)
    
    def _calculate_price_efficiency(self, data: pd.DataFrame) -> float:
        """计算价格效率（价格走势的直线性）"""
        if len(data) < 20:
            return 0.5
        
        prices = data['close'].values[-20:]  # 最近20个价格
        
        # 计算实际价格路径长度
        actual_distance = np.sum(np.abs(np.diff(prices)))
        
        # 计算直线距离
        straight_distance = abs(prices[-1] - prices[0])
        
        # 效率 = 直线距离 / 实际距离
        if actual_distance > 0:
            efficiency = straight_distance / actual_distance
        else:
            efficiency = 1.0
        
        return min(efficiency, 1.0)
    
    def _determine_market_type(self, volatility: float, trend_strength: float) -> MarketType:
        """确定市场类型"""
        
        # 波动率分类
        if volatility > 60:
            vol_category = "HIGH"
        elif volatility > 30:
            vol_category = "MED"
        else:
            vol_category = "LOW"
        
        # 趋势强度分类
        if trend_strength > 0.6:
            trend_category = "TRENDING"
        else:
            trend_category = "RANGING"
        
        # 组合确定类型
        type_mapping = {
            ("HIGH", "TRENDING"): MarketType.HIGH_VOL_TRENDING,
            ("HIGH", "RANGING"): MarketType.HIGH_VOL_RANGING,
            ("MED", "TRENDING"): MarketType.MED_VOL_TRENDING,
            ("MED", "RANGING"): MarketType.MED_VOL_RANGING,
            ("LOW", "TRENDING"): MarketType.LOW_VOL_TRENDING,
            ("LOW", "RANGING"): MarketType.LOW_VOL_RANGING,
        }
        
        return type_mapping.get((vol_category, trend_category), MarketType.MED_VOL_RANGING)
    
    def get_optimized_parameters(self, market_characteristics: MarketCharacteristics) -> Dict[str, Any]:
        """获取优化后的参数"""
        
        base_params = self.base_templates[market_characteristics.market_type].copy()
        
        # 根据具体特征微调参数
        
        # 1. 根据趋势一致性调整
        if market_characteristics.trend_consistency > 0.8:
            base_params['min_signal_score'] = max(1, base_params['min_signal_score'] - 1)
            base_params['trend_profit_extension'] = True
        elif market_characteristics.trend_consistency < 0.3:
            base_params['min_signal_score'] += 1
            base_params['trend_profit_extension'] = False
        
        # 2. 根据成交量特征调整
        if market_characteristics.volume_profile > 0.7:
            base_params['volume_threshold'] *= 0.9  # 降低成交量要求
        elif market_characteristics.volume_profile < 0.3:
            base_params['volume_threshold'] *= 1.2  # 提高成交量要求
        
        # 3. 根据价格效率调整
        if market_characteristics.price_efficiency > 0.7:
            # 高效率市场，可以放宽一些要求
            base_params['min_shadow_body_ratio'] *= 0.9
            base_params['max_body_ratio'] *= 1.1
        elif market_characteristics.price_efficiency < 0.3:
            # 低效率市场，提高要求
            base_params['min_shadow_body_ratio'] *= 1.1
            base_params['max_body_ratio'] *= 0.9
        
        # 4. 限制参数范围
        base_params['min_shadow_body_ratio'] = max(1.0, min(5.0, base_params['min_shadow_body_ratio']))
        base_params['max_body_ratio'] = max(0.15, min(0.5, base_params['max_body_ratio']))
        base_params['min_signal_score'] = max(1, min(5, base_params['min_signal_score']))
        base_params['volume_threshold'] = max(0.5, min(2.0, base_params['volume_threshold']))
        
        return base_params
    
    def generate_optimization_report(self, market_characteristics: MarketCharacteristics, 
                                   optimized_params: Dict[str, Any]) -> str:
        """生成优化报告"""
        
        report = f"""
📊 市场特征分析报告
{'='*50}
市场类型: {market_characteristics.market_type.value}
波动率: {market_characteristics.volatility:.1f}%
趋势强度: {market_characteristics.trend_strength:.3f}
趋势一致性: {market_characteristics.trend_consistency:.3f}
成交量特征: {market_characteristics.volume_profile:.3f}
价格效率: {market_characteristics.price_efficiency:.3f}

🔧 优化后参数
{'='*50}
Pinbar检测参数:
  - 影线/实体比例: {optimized_params['min_shadow_body_ratio']:.1f}
  - 最大实体比例: {optimized_params['max_body_ratio']:.2f}
  - 最低信号评分: {optimized_params['min_signal_score']}

技术指标参数:
  - 成交量阈值: {optimized_params['volume_threshold']:.1f}
  - ADX阈值: {optimized_params['adx_threshold']}
  - RSI超卖线: {optimized_params['rsi_oversold']}
  - RSI超买线: {optimized_params['rsi_overbought']}

止盈策略参数:
  - 启用趋势延长: {optimized_params['trend_profit_extension']}
  - 最大趋势利润: {optimized_params['max_trend_profit_pct']:.1f}%
  - 追踪止损缓冲: {optimized_params['trailing_stop_buffer']:.1f}%

💡 优化建议
{'='*50}
"""
        
        if market_characteristics.market_type in [MarketType.HIGH_VOL_TRENDING, MarketType.MED_VOL_TRENDING, MarketType.LOW_VOL_TRENDING]:
            report += "- 当前为趋势市场，建议使用趋势跟踪策略\n"
            report += "- 可以适当放宽信号要求，增加交易频率\n"
            report += "- 建议启用动态止盈，捕获更大利润\n"
        else:
            report += "- 当前为震荡市场，建议提高信号质量要求\n" 
            report += "- 使用较紧的止盈止损，快进快出\n"
            report += "- 避免长时间持仓，防止被套\n"
        
        if market_characteristics.volatility > 50:
            report += "- 高波动环境，注意控制仓位大小\n"
            report += "- 适当放宽止损空间，避免被震出\n"
        
        return report

# 使用示例
if __name__ == "__main__":
    # 创建自适应参数系统
    adaptive_system = AdaptiveParameterSystem()
    
    # 示例：分析市场特征（需要真实数据）
    # market_chars = adaptive_system.analyze_market_characteristics(data)
    # optimized_params = adaptive_system.get_optimized_parameters(market_chars)
    # report = adaptive_system.generate_optimization_report(market_chars, optimized_params)
    # print(report)
    
    print("🔧 自适应参数系统已就绪")
    print("   支持6种市场类型的参数自动优化")
    print("   可根据波动率、趋势强度、成交量等特征调整参数")