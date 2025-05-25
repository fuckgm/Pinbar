#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版动态杠杆管理器 - 修复低杠杆问题
根据资金规模和信号质量动态调整杠杆和仓位
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
import json
import os
from datetime import datetime, timedelta

class OptimizedLeverageManager:
    """优化版动态杠杆管理器"""
    
    def __init__(self):
        # 优化后的币种分类和杠杆 - 整体提升杠杆水平
        self.coin_categories = {
            'btc': {
                'symbols': ['BTCUSDT'],
                'base_leverage': 50,  # 从15提升到25
                'max_leverage': 100,   # 从25提升到50
                'volatility_factor': 0.8,  # 降低波动率惩罚
                'liquidity_score': 10
            },
            'eth': {
                'symbols': ['ETHUSDT'],
                'base_leverage': 20,  # 从12提升到20
                'max_leverage': 100,   # 从20提升到40
                'volatility_factor': 0.85,
                'liquidity_score': 9
            },
            'major_alts': {
                'symbols': ['BNBUSDT', 'ADAUSDT', 'DOTUSDT', 'SOLUSDT', 'AVAXUSDT', 
                           'MATICUSDT', 'LINKUSDT', 'UNIUSDT', 'LTCUSDT', 'BCHUSDT'],
                'base_leverage': 40,  # 从10提升到18
                'max_leverage': 75,   # 从15提升到35
                'volatility_factor': 0.9,
                'liquidity_score': 8
            },
            'popular_alts': {
                'symbols': ['XRPUSDT', 'DOGEUSDT', 'SHIBUSDT', 'TRXUSDT', 'ETCUSDT',
                           'XLMUSDT', 'VETUSDT', 'FILUSDT', 'SANDUSDT', 'MANAUSDT'],
                'base_leverage': 35,  # 从8提升到15
                'max_leverage': 60,   # 从12提升到30
                'volatility_factor': 0.95,
                'liquidity_score': 7
            },
            'mid_caps': {
                'symbols': ['NEARUSDT', 'ATOMUSDT', 'FTMUSDT', 'HBARUSDT', 'AAVEUSDT',
                           'COMPUSDT', 'MKRUSDT', 'SUSHIUSDT', 'SNXUSDT', 'CRVUSDT'],
                'base_leverage': 30,  # 从6提升到12
                'max_leverage': 50,   # 从10提升到25
                'volatility_factor': 1.0,
                'liquidity_score': 6
            },
            'small_caps': {
                'symbols': [],
                'base_leverage': 25,  # 从4提升到10
                'max_leverage': 40,   # 从8提升到20
                'volatility_factor': 1.1,
                'liquidity_score': 5
            }
        }
        
        # 优化波动率阈值 - 降低波动率惩罚
        self.volatility_thresholds = {
            'very_low': 0.03,     # 提升阈值
            'low': 0.05,         # 提升阈值
            'normal': 0.08,      # 提升阈值
            'high': 0.12,         # 提升阈值
            'very_high': 0.18,    # 提升阈值
            'extreme': float('inf')
        }
        
        # 资金规模调整因子 - 新增
        self.capital_factors = {
            'small': {'threshold': 1000, 'leverage_boost': 1.5, 'position_boost': 1.3},    # <1000U
            'medium': {'threshold': 10000, 'leverage_boost': 1.2, 'position_boost': 1.1},  # 1000-10000U
            'large': {'threshold': 50000, 'leverage_boost': 1.0, 'position_boost': 1.0},   # 10000-50000U
            'huge': {'threshold': float('inf'), 'leverage_boost': 0.8, 'position_boost': 0.9}  # >50000U
        }
        
        # 优化市场状态影响因子 - 提升整体水平
        self.market_conditions = {
            'bull_strong': 1.5,     # 从1.2提升
            'bull_normal': 1.3,     # 从1.1提升
            'sideways': 1.1,        # 保持不变
            'bear_normal': 1.0,     # 从0.8提升
            'bear_strong': 0.8,     # 从0.6提升
            'panic': 0.6            # 从0.4提升
        }
        
        # 信号质量影响因子 - 新增
        self.signal_quality_factors = {
            'confidence': {
                'excellent': 1.5,    # >0.8置信度
                'good': 1.3,        # 0.6-0.8置信度
                'fair': 1.1,         # 0.4-0.6置信度
                'poor': 0.9          # <0.4置信度
            },
            'strength': {
                'very_strong': 1.4,  # 5分
                'strong': 1.2,        # 4分
                'moderate': 1.0,      # 3分
                'weak': 0.8          # 1-2分
            },
            'trend_alignment': {
                'aligned': 1.3,       # 趋势对齐
                'not_aligned': 1.0    # 不对齐
            }
        }
        
        # 最小杠杆保证 - 新增
        self.min_leverage_guarantee = {
            'btc': 30,
            'eth': 20,
            'major_alts': 20,
            'popular_alts': 18,
            'mid_caps': 15,
            'small_caps': 12
        }
    
    def get_capital_factor(self, total_capital: float) -> Dict[str, float]:
        """根据资金规模获取调整因子"""
        for level, config in self.capital_factors.items():
            if total_capital < config['threshold']:
                return {
                    'leverage_boost': config['leverage_boost'],
                    'position_boost': config['position_boost'],
                    'level': level
                }
        
        # 默认返回大资金配置
        return {
            'leverage_boost': self.capital_factors['huge']['leverage_boost'],
            'position_boost': self.capital_factors['huge']['position_boost'],
            'level': 'huge'
        }
    
    def get_coin_category(self, symbol: str) -> str:
        """获取币种分类"""
        symbol = symbol.upper()
        
        for category, info in self.coin_categories.items():
            if symbol in info['symbols']:
                return category
        
        return 'small_caps'
    
    def calculate_signal_quality_factor(self, signal_info: Dict[str, Any]) -> float:
        """计算信号质量调整因子"""
        total_factor = 1.0
        
        # 置信度因子
        confidence = signal_info.get('confidence_score', 0.5)
        if confidence >= 0.8:
            total_factor *= self.signal_quality_factors['confidence']['excellent']
        elif confidence >= 0.6:
            total_factor *= self.signal_quality_factors['confidence']['good']
        elif confidence >= 0.4:
            total_factor *= self.signal_quality_factors['confidence']['fair']
        else:
            total_factor *= self.signal_quality_factors['confidence']['poor']
        
        # 信号强度因子
        strength = signal_info.get('signal_strength', 3)
        if strength >= 5:
            total_factor *= self.signal_quality_factors['strength']['very_strong']
        elif strength >= 4:
            total_factor *= self.signal_quality_factors['strength']['strong']
        elif strength >= 3:
            total_factor *= self.signal_quality_factors['strength']['moderate']
        else:
            total_factor *= self.signal_quality_factors['strength']['weak']
        
        # 趋势对齐因子
        trend_aligned = signal_info.get('trend_alignment', False)
        if trend_aligned:
            total_factor *= self.signal_quality_factors['trend_alignment']['aligned']
        else:
            total_factor *= self.signal_quality_factors['trend_alignment']['not_aligned']
        
        return total_factor
    
    def calculate_volatility_factor(self, data: pd.DataFrame, period: int = 20) -> float:
        """优化版波动率因子计算"""
        if len(data) < period:
            return 1.2  # 数据不足时不惩罚
        
        returns = data['close'].pct_change().dropna()
        if len(returns) < period:
            return 1.2
        
        recent_returns = returns[-period:]
        volatility = recent_returns.std() * np.sqrt(24)
        
        # 优化版波动率调整 - 降低惩罚力度
        if volatility <= self.volatility_thresholds['very_low']:
            return 1.3  # 降低奖励
        elif volatility <= self.volatility_thresholds['low']:
            return 1.2
        elif volatility <= self.volatility_thresholds['normal']:
            return 1.1
        elif volatility <= self.volatility_thresholds['high']:
            return 1.0  # 降低惩罚
        elif volatility <= self.volatility_thresholds['very_high']:
            return 0.95
        else:
            return 0.9  # 降低极端惩罚
    
    def calculate_optimized_leverage(self, symbol: str, data: pd.DataFrame, 
                                   total_capital: float, signal_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """计算优化版动态杠杆"""
        
        # 获取币种基础信息
        category = self.get_coin_category(symbol)
        coin_info = self.coin_categories[category]
        base_leverage = coin_info['base_leverage']
        max_leverage = coin_info['max_leverage']
        
        # 资金规模调整
        capital_factor = self.get_capital_factor(total_capital)
        
        # 信号质量调整
        signal_quality_factor = 1.0
        if signal_info:
            signal_quality_factor = self.calculate_signal_quality_factor(signal_info)
        
        # 市场条件调整
        market_condition = self.get_market_condition(data)
        market_factor = self.market_conditions[market_condition]
        
        # 波动率调整
        volatility_factor = self.calculate_volatility_factor(data)
        
        # 趋势强度调整
        trend_factor = self.calculate_trend_factor(data)
        
        # 时间因子
        time_factor = self.get_time_factor()
        
        # 综合调整因子 - 重新权重分配
        total_factor = (
            capital_factor['leverage_boost'] * 0.25 +      # 资金规模权重25%
            signal_quality_factor * 0.20 +                # 信号质量权重20%
            market_factor * 0.20 +                         # 市场状态权重20%
            volatility_factor * 0.15 +                     # 波动率权重15%
            trend_factor * 0.15 +                          # 趋势权重15%
            time_factor * 0.05                             # 时间权重5%
        )
        
        # 计算最终杠杆
        calculated_leverage = base_leverage * total_factor
        
        # 应用最小杠杆保证
        min_leverage = self.min_leverage_guarantee[category]
        
        # 最终杠杆确定
        final_leverage = max(min_leverage, min(max_leverage, int(calculated_leverage)))
        
        return {
            'symbol': symbol,
            'category': category,
            'base_leverage': base_leverage,
            'calculated_leverage': calculated_leverage,
            'final_leverage': final_leverage,
            'max_leverage': max_leverage,
            'min_leverage': min_leverage,
            'capital_level': capital_factor['level'],
            'factors': {
                'capital_factor': capital_factor['leverage_boost'],
                'signal_quality_factor': signal_quality_factor,
                'market_factor': market_factor,
                'volatility_factor': volatility_factor,
                'trend_factor': trend_factor,
                'time_factor': time_factor,
                'total_factor': total_factor
            },
            'market_condition': market_condition,
            'recommendation': self._generate_optimized_recommendation(symbol, final_leverage, total_factor, capital_factor['level'])
        }
    def calculate_dynamic_leverage(self, symbol: str, data: pd.DataFrame, 
                             current_price: float, **kwargs) -> Dict[str, Any]:
        """兼容性方法 - 调用优化版杠杆计算"""
        # 从kwargs中提取total_capital，如果没有则使用默认值
        total_capital = kwargs.get('total_capital', 20000)
        signal_info = kwargs.get('signal_info', None)
        
        result = self.calculate_optimized_leverage(symbol, data, total_capital, signal_info)
        return result
    
    def calculate_position_size(self, symbol: str, total_capital: float, 
                              signal_info: Dict[str, Any], leverage: int) -> Dict[str, Any]:
        """计算优化版仓位大小"""
        
        # 基础仓位配置
        base_position_ratio = 0.02  # 基础2%风险
        
        # 资金规模调整
        capital_factor = self.get_capital_factor(total_capital)
        
        # 信号质量调整仓位
        signal_quality_factor = self.calculate_signal_quality_factor(signal_info) if signal_info else 1.0
        
        # 杠杆调整仓位 - 高杠杆适当降低仓位
        leverage_position_factor = 1.0
        if leverage >= 20:
            leverage_position_factor = 0.8
        elif leverage >= 15:
            leverage_position_factor = 0.9
        elif leverage >= 10:
            leverage_position_factor = 1.0
        else:
            leverage_position_factor = 1.2  # 低杠杆增加仓位
        
        # 计算单笔仓位金额
        adjusted_position_ratio = (
            base_position_ratio * 
            capital_factor['position_boost'] * 
            signal_quality_factor * 
            leverage_position_factor
        )
        
        # 限制单笔仓位不超过资金的5%
        adjusted_position_ratio = min(adjusted_position_ratio, 0.05)
        
        # 计算具体金额
        position_amount = total_capital * adjusted_position_ratio
        
        # 最小开仓金额调整
        min_position = max(200, total_capital * 0.01)  # 最小200U或1%资金
        max_position = total_capital * 0.05  # 最大5%资金
        
        final_position_amount = max(min_position, min(max_position, position_amount))
        
        return {
            'position_amount': final_position_amount,
            'position_ratio': final_position_amount / total_capital,
            'leverage': leverage,
            'margin_required': final_position_amount / leverage,
            'factors': {
                'base_ratio': base_position_ratio,
                'capital_boost': capital_factor['position_boost'],
                'signal_quality_boost': signal_quality_factor,
                'leverage_adjustment': leverage_position_factor,
                'final_ratio': adjusted_position_ratio
            },
            'capital_level': capital_factor['level']
        }
    
    def calculate_max_total_exposure(self, total_capital: float) -> float:
        """计算最大总敞口 - 不超过70%资金"""
        return min(total_capital * 0.7, total_capital)
    
    def get_market_condition(self, data: pd.DataFrame) -> str:
        """判断市场状态 - 优化版"""
        if len(data) < 30:
            return 'sideways'
        
        # 多重时间框架分析
        short_return = (data['close'].iloc[-1] - data['close'].iloc[-7]) / data['close'].iloc[-7]  # 7天
        medium_return = (data['close'].iloc[-1] - data['close'].iloc[-30]) / data['close'].iloc[-30]  # 30天
        
        # 波动率分析
        returns = data['close'].pct_change().dropna()
        volatility = returns[-30:].std() * np.sqrt(30)
        
        # 趋势强度
        sma_20 = data['close'][-20:].mean()
        sma_50 = data['close'][-50:].mean() if len(data) >= 50 else sma_20
        trend_strength = abs(sma_20 - sma_50) / sma_50
        
        # 激进的判断标准（更容易判定为牛市）
        if short_return > 0.08 and medium_return > 0.1:
            return 'bull_strong'
        elif short_return > 0.02 or medium_return > 0.03:
            return 'bull_normal'
        elif short_return < -0.15 and medium_return < -0.2 and volatility > 0.8:
            return 'panic'
        elif short_return < -0.08 and medium_return < -0.1:
            return 'bear_strong'
        elif short_return < -0.03 or medium_return < -0.05:
            return 'bear_normal'
        else:
            return 'sideways'
    
    def calculate_trend_factor(self, data: pd.DataFrame) -> float:
        """优化版趋势因子"""
        if len(data) < 50:
            return 1.2
        
        # 多重均线分析
        sma_10 = data['close'][-10:].mean()
        sma_20 = data['close'][-20:].mean()
        sma_50 = data['close'][-50:].mean()
        current_price = data['close'].iloc[-1]
        
        # 趋势一致性
        trend_alignment = 0
        if sma_10 > sma_20 > sma_50:  # 上升趋势
            trend_alignment = 1
        elif sma_10 < sma_20 < sma_50:  # 下降趋势
            trend_alignment = 1
        
        # 趋势强度
        trend_strength = abs(current_price - sma_50) / sma_50
        
        # 激进的趋势因子
        if trend_alignment and trend_strength > 0.05:
            return 1.4
        elif trend_alignment and trend_strength > 0.03:
            return 1.3
        elif trend_strength > 0.02:
            return 1.2
        else:
            return 1.1  # 最低也给1.1
    
    def get_time_factor(self) -> float:
        """时间因子 - 优化版"""
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()
        
        # 周末也给予正常交易
        if weekday >= 5:
            return 1.0  
        
        # 各时段都适合交易
        if 0 <= hour < 8:
            return 1.0  
        elif 8 <= hour < 16:
            return 1.1  # 活跃时段加成
        else:
            return 1.05  # 从1.1降低
    
    def _generate_optimized_recommendation(self, symbol: str, leverage: int, 
                                         total_factor: float, capital_level: str) -> str:
        """生成优化建议"""
        recommendations = []
        
       # 杠杆建议
        if leverage >= 50:
            recommendations.append("超高杠杆，仓位控制很重要")
        elif leverage >= 30:
            recommendations.append("高杠杆交易，注意风险")
        elif leverage >= 20:
            recommendations.append("中高杠杆，可积极操作")
        else:
            recommendations.append("杠杆偏低，可考虑提高")
        
        # 资金规模建议
        if capital_level == 'small':
            recommendations.append("小资金可用高杠杆放大收益")
        elif capital_level == 'large':
            recommendations.append("大资金建议分散持仓")
        
        # 市场状态建议
        if total_factor > 1.2:
            recommendations.append("市场条件良好，可积极交易")
        elif total_factor < 0.8:
            recommendations.append("市场波动较大，谨慎操作")
        
        return " | ".join(recommendations)

DynamicLeverageManager = OptimizedLeverageManager

# 使用示例
if __name__ == "__main__":
    print("🎯 优化版动态杠杆管理器测试")
    print("=" * 50)
    
    manager = OptimizedLeverageManager()
    
    # 模拟不同资金规模测试
    test_capitals = [500, 5000, 25000, 100000]  # 不同资金规模
    # 模拟不同场景
    test_scenarios = [
        {'symbol': 'BTCUSDT', 'capital': 5000, 'confidence': 0.5, 'strength': 3, 'aligned': True},
        {'symbol': 'BTCUSDT', 'capital': 5000, 'confidence': 0.8, 'strength': 5, 'aligned': True},
        {'symbol': 'ETHUSDT', 'capital': 10000, 'confidence': 0.6, 'strength': 4, 'aligned': False},
        {'symbol': 'DOGEUSDT', 'capital': 2000, 'confidence': 0.7, 'strength': 4, 'aligned': True},
    ]

    print("场景测试结果：")
    print("-" * 80)
    print(f"{'币种':<10} {'资金':<8} {'置信度':<8} {'强度':<6} {'趋势':<6} {'杠杆':<6} {'建议':<30}")
    print("-" * 80)
    
    for scenario in test_scenarios:
        # 创建模拟数据
        dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
        prices = np.random.lognormal(np.log(50000 if 'BTC' in scenario['symbol'] else 3000), 0.02, 100)
        volumes = np.random.lognormal(10, 0.5, 100)
        
        data = pd.DataFrame({
            'timestamp': dates,
            'close': prices,
            'volume': volumes
        })
        
        # 创建信号信息
        signal_info = {
            'confidence_score': scenario['confidence'],
            'signal_strength': scenario['strength'],
            'trend_alignment': scenario['aligned']
        }
        
        # 计算杠杆
        result = manager.calculate_optimized_leverage(
            scenario['symbol'], 
            data, 
            scenario['capital'], 
            signal_info
        )
        
        # 显示结果
        print(f"{scenario['symbol']:<10} "
              f"{scenario['capital']:<8} "
              f"{scenario['confidence']:<8.1f} "
              f"{scenario['strength']:<6} "
              f"{'对齐' if scenario['aligned'] else '不对齐':<6} "
              f"{result['final_leverage']:<6}x "
              f"{result['recommendation'][:30]:<30}")
    print(f"\n✅ 优化要点:")
    print("1. 整体提升杠杆水平，最低保证5倍")
    print("2. 根据资金规模调整：小资金高杠杆，大资金低杠杆")
    print("3. 信号质量影响杠杆和仓位大小")
    print("4. 最小开仓200U，最大不超过总资金5%")
    print("5. 降低波动率惩罚，提升开仓频率")