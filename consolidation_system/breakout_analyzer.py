"""
突破分析器 - BreakoutAnalyzer

分析价格突破盘整区间的有效性，区分真假突破，为交易决策提供关键信号。

核心功能：
1. 检测价格突破盘整区间的有效性
2. 区分真突破和假突破
3. 分析突破的强度和可持续性
4. 提供成交量和动量确认
5. 生成详细的突破信号

分析维度：
- 价格突破幅度和持续性
- 成交量放大确认
- 动量指标确认
- 市场结构分析
- 时间确认机制

Author: Pinbar Strategy Team  
Date: 2024-12
Version: 1.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from .consolidation_detector import ConsolidationRange

# 设置日志
logger = logging.getLogger(__name__)


class BreakoutDirection(Enum):
    """突破方向枚举"""
    UP = "up"          # 向上突破
    DOWN = "down"      # 向下突破
    NONE = "none"      # 无突破


class BreakoutType(Enum):
    """突破类型枚举"""
    GENUINE = "genuine"           # 真突破
    FALSE = "false"               # 假突破
    POTENTIAL = "potential"       # 潜在突破
    INVALID = "invalid"           # 无效突破


class BreakoutStrength(Enum):
    """突破强度枚举"""
    WEAK = 1         # 弱突破
    MODERATE = 2     # 中等突破
    STRONG = 3       # 强突破
    EXPLOSIVE = 4    # 爆发性突破


class ConfirmationType(Enum):
    """确认类型枚举"""
    PRICE_ONLY = "price_only"           # 仅价格确认
    VOLUME_CONFIRMED = "volume_confirmed"  # 成交量确认
    MOMENTUM_CONFIRMED = "momentum_confirmed"  # 动量确认
    FULL_CONFIRMED = "full_confirmed"      # 全面确认


@dataclass
class BreakoutSignal:
    """
    突破信号数据结构
    
    包含突破分析的所有关键信息
    """
    # 基本信息
    symbol: str                      # 交易对符号
    breakout_time: datetime          # 突破时间
    direction: BreakoutDirection     # 突破方向
    breakout_type: BreakoutType      # 突破类型
    strength: BreakoutStrength       # 突破强度
    
    # 价格信息
    breakout_price: float           # 突破价格
    target_boundary: float          # 目标边界价格
    breakout_distance: float        # 突破距离
    breakout_percentage: float      # 突破百分比
    
    # 确认信息
    confirmation_type: ConfirmationType  # 确认类型
    confirm_bars: int               # 确认K线数
    volume_ratio: float            # 成交量比率
    momentum_score: float          # 动量评分
    
    # 质量评估
    quality_score: float           # 质量评分 (0-100)
    confidence: float              # 置信度 (0-1)
    risk_level: int               # 风险等级 (1-5)
    
    # 技术指标
    avg_volume_ratio: float        # 平均成交量比率
    price_acceleration: float      # 价格加速度
    volatility_expansion: float    # 波动率扩张
    
    # 预测信息
    success_probability: float     # 成功概率
    target_distance: float         # 目标距离
    expected_duration: int         # 预期持续时间
    
    # 风险控制
    stop_loss_suggestion: float    # 止损建议价位
    invalidation_level: float      # 失效价位
    
    # 元数据
    is_valid: bool                # 是否有效
    created_at: datetime          # 创建时间
    
    def __post_init__(self):
        """后处理初始化"""
        # 计算派生指标
        if self.breakout_price and self.target_boundary:
            self.breakout_distance = abs(self.breakout_price - self.target_boundary)
            if self.target_boundary > 0:
                self.breakout_percentage = (self.breakout_distance / self.target_boundary) * 100
    
    def is_confirmed_breakout(self) -> bool:
        """检查是否为确认的突破"""
        return (
            self.is_valid and
            self.breakout_type in [BreakoutType.GENUINE, BreakoutType.POTENTIAL] and
            self.confirmation_type != ConfirmationType.PRICE_ONLY and
            self.quality_score >= 50 and
            self.confidence >= 0.6
        )
    
    def get_signal_strength_score(self) -> float:
        """获取信号强度综合评分"""
        strength_weights = {
            BreakoutStrength.WEAK: 25,
            BreakoutStrength.MODERATE: 50,
            BreakoutStrength.STRONG: 75,
            BreakoutStrength.EXPLOSIVE: 100
        }
        
        strength_score = strength_weights.get(self.strength, 0)
        
        # 结合其他因素
        volume_score = min(self.volume_ratio / 2.0, 1.0) * 100
        momentum_score = self.momentum_score
        confidence_score = self.confidence * 100
        
        # 加权平均
        final_score = (
            strength_score * 0.3 +
            volume_score * 0.25 +
            momentum_score * 0.25 +
            confidence_score * 0.2
        )
        
        return min(final_score, 100)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'symbol': self.symbol,
            'breakout_time': self.breakout_time.isoformat() if self.breakout_time else None,
            'direction': self.direction.value,
            'breakout_type': self.breakout_type.value,
            'strength': self.strength.value,
            'breakout_price': self.breakout_price,
            'breakout_percentage': self.breakout_percentage,
            'confirmation_type': self.confirmation_type.value,
            'volume_ratio': self.volume_ratio,
            'quality_score': self.quality_score,
            'confidence': self.confidence,
            'success_probability': self.success_probability,
            'is_valid': self.is_valid,
            'signal_strength_score': self.get_signal_strength_score()
        }


class BreakoutAnalyzer:
    """
    突破分析器
    
    分析价格突破盘整区间的有效性和质量
    """
    
    def __init__(self, config: Dict = None):
        """
        初始化突破分析器
        
        Args:
            config: 配置参数
        """
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 分析参数
        self.min_volume_ratio = self.config.get('min_volume_ratio', 1.3)
        self.price_threshold = self.config.get('price_threshold', 0.005)
        self.confirm_bars = self.config.get('confirm_bars', 2)
        self.false_breakout_check = self.config.get('false_breakout_check', True)
        
        # 统计信息
        self.analysis_stats = {
            'total_analyses': 0,
            'genuine_breakouts': 0,
            'false_breakouts': 0,
            'avg_success_rate': 0.0
        }
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'min_volume_ratio': 1.3,
            'price_threshold': 0.005,
            'confirm_bars': 2,
            'false_breakout_check': True,
            'momentum_period': 14,
            'volatility_period': 20,
            'volume_ma_period': 20,
            'min_quality_score': 40,
            'explosive_volume_threshold': 3.0,
            'strong_momentum_threshold': 0.7
        }
    
    def analyze_breakout(self,
                        price_data: pd.DataFrame,
                        consolidation_range: ConsolidationRange,
                        current_price: float = None) -> Optional[BreakoutSignal]:
        """
        分析突破信号
        
        Args:
            price_data: 价格数据
            consolidation_range: 盘整区间
            current_price: 当前价格
            
        Returns:
            BreakoutSignal: 突破信号，如果没有则返回None
        """
        try:
            if not consolidation_range or not consolidation_range.is_valid():
                self.logger.warning("盘整区间无效或不存在")
                return None
            
            # 获取最新数据进行分析
            if len(price_data) < self.confirm_bars + 1:
                self.logger.warning("数据不足以进行突破分析")
                return None
            
            # 确定当前价格
            if current_price is None:
                current_price = price_data['close'].iloc[-1]
            
            # 1. 检测突破方向
            breakout_direction = self._detect_breakout_direction(
                current_price, consolidation_range
            )
            
            if breakout_direction == BreakoutDirection.NONE:
                return None
            
            # 2. 分析突破有效性
            breakout_validity = self._analyze_breakout_validity(
                price_data, consolidation_range, breakout_direction, current_price
            )
            
            # 3. 计算突破强度
            breakout_strength = self._calculate_breakout_strength(
                price_data, consolidation_range, breakout_validity
            )
            
            # 4. 获取确认信息
            confirmation_info = self._get_confirmation_info(
                price_data, consolidation_range, breakout_validity
            )
            
            # 5. 评估质量和置信度
            quality_assessment = self._assess_breakout_quality(
                price_data, consolidation_range, breakout_validity, confirmation_info
            )
            
            # 6. 计算预测信息
            prediction_info = self._calculate_prediction_metrics(
                price_data, consolidation_range, breakout_validity, quality_assessment
            )
            
            # 7. 生成风险控制建议
            risk_control = self._generate_risk_control_suggestions(
                consolidation_range, breakout_validity, current_price
            )
            
            # 创建突破信号
            breakout_signal = BreakoutSignal(
                symbol=consolidation_range.symbol,
                breakout_time=datetime.now(),
                direction=breakout_direction,
                breakout_type=breakout_validity['type'],
                strength=breakout_strength,
                
                breakout_price=current_price,
                target_boundary=breakout_validity['target_boundary'],
                breakout_distance=breakout_validity['distance'],
                breakout_percentage=breakout_validity['percentage'],
                
                confirmation_type=confirmation_info['type'],
                confirm_bars=confirmation_info['bars'],
                volume_ratio=confirmation_info['volume_ratio'],
                momentum_score=confirmation_info['momentum_score'],
                
                quality_score=quality_assessment['quality_score'],
                confidence=quality_assessment['confidence'],
                risk_level=quality_assessment['risk_level'],
                
                avg_volume_ratio=confirmation_info['avg_volume_ratio'],
                price_acceleration=confirmation_info['price_acceleration'],
                volatility_expansion=confirmation_info['volatility_expansion'],
                
                success_probability=prediction_info['success_probability'],
                target_distance=prediction_info['target_distance'],
                expected_duration=prediction_info['expected_duration'],
                
                stop_loss_suggestion=risk_control['stop_loss'],
                invalidation_level=risk_control['invalidation_level'],
                
                is_valid=quality_assessment['is_valid'],
                created_at=datetime.now()
            )
            
            # 更新统计信息
            self._update_analysis_stats(breakout_signal)
            
            self.logger.info(f"突破分析完成: {breakout_signal.symbol}, "
                           f"方向: {breakout_signal.direction.value}, "
                           f"强度: {breakout_signal.strength.value}, "
                           f"质量: {breakout_signal.quality_score:.1f}")
            
            return breakout_signal
            
        except Exception as e:
            self.logger.error(f"突破分析失败: {str(e)}")
            return None
    
    def _detect_breakout_direction(self, 
                                 current_price: float, 
                                 consolidation_range: ConsolidationRange) -> BreakoutDirection:
        """检测突破方向"""
        try:
            upper_threshold = consolidation_range.upper_boundary * (1 + self.price_threshold)
            lower_threshold = consolidation_range.lower_boundary * (1 - self.price_threshold)
            
            if current_price > upper_threshold:
                return BreakoutDirection.UP
            elif current_price < lower_threshold:
                return BreakoutDirection.DOWN
            else:
                return BreakoutDirection.NONE
                
        except Exception:
            return BreakoutDirection.NONE
    
    def _analyze_breakout_validity(self,
                                 price_data: pd.DataFrame,
                                 consolidation_range: ConsolidationRange,
                                 direction: BreakoutDirection,
                                 current_price: float) -> Dict:
        """分析突破有效性"""
        try:
            # 获取目标边界
            if direction == BreakoutDirection.UP:
                target_boundary = consolidation_range.upper_boundary
            else:
                target_boundary = consolidation_range.lower_boundary
            
            # 计算突破距离和百分比
            distance = abs(current_price - target_boundary)
            percentage = (distance / target_boundary) * 100
            
            # 检查突破的持续性
            recent_data = price_data.tail(self.confirm_bars + 1)
            sustained_breakout = True
            
            for _, bar in recent_data.iterrows():
                if direction == BreakoutDirection.UP:
                    if bar['close'] <= consolidation_range.upper_boundary:
                        sustained_breakout = False
                        break
                else:
                    if bar['close'] >= consolidation_range.lower_boundary:
                        sustained_breakout = False
                        break
            
            # 判断突破类型
            if not sustained_breakout:
                breakout_type = BreakoutType.FALSE
            elif percentage >= self.price_threshold * 100:
                if self._check_volume_confirmation(price_data, recent_data):
                    breakout_type = BreakoutType.GENUINE
                else:
                    breakout_type = BreakoutType.POTENTIAL
            else:
                breakout_type = BreakoutType.POTENTIAL
            
            return {
                'type': breakout_type,
                'target_boundary': target_boundary,
                'distance': distance,
                'percentage': percentage,
                'sustained': sustained_breakout,
                'bars_confirmed': len(recent_data)
            }
            
        except Exception as e:
            self.logger.error(f"突破有效性分析失败: {str(e)}")
            return {
                'type': BreakoutType.INVALID,
                'target_boundary': 0,
                'distance': 0,
                'percentage': 0,
                'sustained': False,
                'bars_confirmed': 0
            }
    
    def _check_volume_confirmation(self, 
                                 price_data: pd.DataFrame, 
                                 recent_data: pd.DataFrame) -> bool:
        """检查成交量确认"""
        try:
            # 计算平均成交量
            volume_ma_period = self.config.get('volume_ma_period', 20)
            historical_data = price_data.tail(volume_ma_period + len(recent_data))
            avg_volume = historical_data['volume'].head(volume_ma_period).mean()
            
            # 检查最近几根K线的成交量
            recent_avg_volume = recent_data['volume'].mean()
            volume_ratio = recent_avg_volume / avg_volume if avg_volume > 0 else 0
            
            return volume_ratio >= self.min_volume_ratio
            
        except Exception:
            return False
    
    def _calculate_breakout_strength(self,
                                   price_data: pd.DataFrame,
                                   consolidation_range: ConsolidationRange,
                                   breakout_validity: Dict) -> BreakoutStrength:
        """计算突破强度"""
        try:
            # 基于多个因素计算强度
            factors = []
            
            # 1. 价格突破幅度
            percentage = breakout_validity['percentage']
            if percentage >= 2.0:
                factors.append(4)  # 爆发性
            elif percentage >= 1.0:
                factors.append(3)  # 强
            elif percentage >= 0.5:
                factors.append(2)  # 中等
            else:
                factors.append(1)  # 弱
            
            # 2. 成交量放大
            recent_data = price_data.tail(self.confirm_bars + 1)
            volume_ma_period = self.config.get('volume_ma_period', 20)
            avg_volume = price_data['volume'].tail(volume_ma_period).mean()
            current_volume = recent_data['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio >= self.config.get('explosive_volume_threshold', 3.0):
                factors.append(4)
            elif volume_ratio >= 2.0:
                factors.append(3)
            elif volume_ratio >= self.min_volume_ratio:
                factors.append(2)
            else:
                factors.append(1)
            
            # 3. 动量强度
            momentum_score = self._calculate_momentum_score(price_data)
            if momentum_score >= 0.8:
                factors.append(4)
            elif momentum_score >= 0.6:
                factors.append(3)
            elif momentum_score >= 0.4:
                factors.append(2)
            else:
                factors.append(1)
            
            # 4. 盘整质量
            quality_score = consolidation_range.quality_score
            if quality_score >= 80:
                factors.append(4)
            elif quality_score >= 60:
                factors.append(3)
            elif quality_score >= 40:
                factors.append(2)
            else:
                factors.append(1)
            
            # 计算平均强度
            avg_strength = sum(factors) / len(factors)
            
            if avg_strength >= 3.5:
                return BreakoutStrength.EXPLOSIVE
            elif avg_strength >= 2.5:
                return BreakoutStrength.STRONG
            elif avg_strength >= 1.5:
                return BreakoutStrength.MODERATE
            else:
                return BreakoutStrength.WEAK
                
        except Exception:
            return BreakoutStrength.WEAK
    
    def _calculate_momentum_score(self, price_data: pd.DataFrame) -> float:
        """计算动量评分"""
        try:
            period = self.config.get('momentum_period', 14)
            if len(price_data) < period:
                return 0.5
            
            recent_data = price_data.tail(period)
            
            # RSI计算
            delta = recent_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # 价格动量
            price_momentum = (recent_data['close'].iloc[-1] / recent_data['close'].iloc[0] - 1) * 100
            
            # MACD动量
            exp1 = recent_data['close'].ewm(span=12).mean()
            exp2 = recent_data['close'].ewm(span=26).mean()
            macd = exp1 - exp2
            macd_signal = macd.ewm(span=9).mean()
            macd_histogram = macd - macd_signal
            macd_momentum = macd_histogram.iloc[-1]
            
            # 综合动量评分
            momentum_factors = []
            
            # RSI评分
            if current_rsi > 70 or current_rsi < 30:
                momentum_factors.append(0.8)
            elif current_rsi > 60 or current_rsi < 40:
                momentum_factors.append(0.6)
            else:
                momentum_factors.append(0.4)
            
            # 价格动量评分
            if abs(price_momentum) > 5:
                momentum_factors.append(0.9)
            elif abs(price_momentum) > 2:
                momentum_factors.append(0.7)
            else:
                momentum_factors.append(0.4)
            
            # MACD评分
            if abs(macd_momentum) > 0.01:
                momentum_factors.append(0.8)
            elif abs(macd_momentum) > 0.005:
                momentum_factors.append(0.6)
            else:
                momentum_factors.append(0.4)
            
            return sum(momentum_factors) / len(momentum_factors)
            
        except Exception:
            return 0.5
    
    def _get_confirmation_info(self,
                             price_data: pd.DataFrame,
                             consolidation_range: ConsolidationRange,
                             breakout_validity: Dict) -> Dict:
        """获取确认信息"""
        try:
            recent_data = price_data.tail(self.confirm_bars + 5)
            
            # 成交量确认
            volume_ma_period = self.config.get('volume_ma_period', 20)
            avg_volume = price_data['volume'].tail(volume_ma_period).mean()
            recent_volume = recent_data['volume'].tail(self.confirm_bars).mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
            avg_volume_ratio = recent_data['volume'].mean() / avg_volume if avg_volume > 0 else 1
            
            # 动量确认
            momentum_score = self._calculate_momentum_score(price_data)
            
            # 价格加速度
            closes = recent_data['close']
            if len(closes) >= 3:
                price_acceleration = (closes.iloc[-1] - closes.iloc[-2]) - (closes.iloc[-2] - closes.iloc[-3])
            else:
                price_acceleration = 0
            
            # 波动率扩张
            volatility_period = self.config.get('volatility_period', 20)
            historical_volatility = price_data['close'].tail(volatility_period).pct_change().std()
            recent_volatility = recent_data['close'].pct_change().std()
            volatility_expansion = recent_volatility / historical_volatility if historical_volatility > 0 else 1
            
            # 确认类型
            if (volume_ratio >= self.min_volume_ratio and 
                momentum_score >= self.config.get('strong_momentum_threshold', 0.7)):
                confirmation_type = ConfirmationType.FULL_CONFIRMED
            elif volume_ratio >= self.min_volume_ratio:
                confirmation_type = ConfirmationType.VOLUME_CONFIRMED
            elif momentum_score >= 0.6:
                confirmation_type = ConfirmationType.MOMENTUM_CONFIRMED
            else:
                confirmation_type = ConfirmationType.PRICE_ONLY
            
            return {
                'type': confirmation_type,
                'bars': breakout_validity['bars_confirmed'],
                'volume_ratio': volume_ratio,
                'avg_volume_ratio': avg_volume_ratio,
                'momentum_score': momentum_score,
                'price_acceleration': price_acceleration,
                'volatility_expansion': volatility_expansion
            }
            
        except Exception:
            return {
                'type': ConfirmationType.PRICE_ONLY,
                'bars': 0,
                'volume_ratio': 1.0,
                'avg_volume_ratio': 1.0,
                'momentum_score': 0.5,
                'price_acceleration': 0.0,
                'volatility_expansion': 1.0
            }
    
    def _assess_breakout_quality(self,
                               price_data: pd.DataFrame,
                               consolidation_range: ConsolidationRange,
                               breakout_validity: Dict,
                               confirmation_info: Dict) -> Dict:
        """评估突破质量"""
        try:
            quality_factors = []
            
            # 1. 突破类型评分
            type_scores = {
                BreakoutType.GENUINE: 90,
                BreakoutType.POTENTIAL: 70,
                BreakoutType.FALSE: 20,
                BreakoutType.INVALID: 0
            }
            quality_factors.append(type_scores.get(breakout_validity['type'], 0))
            
            # 2. 盘整质量评分
            quality_factors.append(consolidation_range.quality_score)
            
            # 3. 确认质量评分
            confirmation_scores = {
                ConfirmationType.FULL_CONFIRMED: 90,
                ConfirmationType.VOLUME_CONFIRMED: 75,
                ConfirmationType.MOMENTUM_CONFIRMED: 60,
                ConfirmationType.PRICE_ONLY: 30
            }
            quality_factors.append(confirmation_scores.get(confirmation_info['type'], 30))
            
            # 4. 持续性评分
            if breakout_validity['sustained']:
                quality_factors.append(80)
            else:
                quality_factors.append(30)
            
            # 5. 突破幅度评分
            percentage = breakout_validity['percentage']
            if percentage >= 2.0:
                quality_factors.append(90)
            elif percentage >= 1.0:
                quality_factors.append(75)
            elif percentage >= 0.5:
                quality_factors.append(60)
            else:
                quality_factors.append(40)
            
            # 计算综合质量评分
            quality_score = sum(quality_factors) / len(quality_factors)
            
            # 计算置信度
            confidence = min(quality_score / 100, 1.0)
            
            # 风险等级 (1-5, 5为最高风险)
            if quality_score >= 80:
                risk_level = 1
            elif quality_score >= 60:
                risk_level = 2
            elif quality_score >= 40:
                risk_level = 3
            elif quality_score >= 20:
                risk_level = 4
            else:
                risk_level = 5
            
            # 有效性判断
            is_valid = (
                quality_score >= self.config.get('min_quality_score', 40) and
                breakout_validity['type'] != BreakoutType.INVALID and
                confidence >= 0.3
            )
            
            return {
                'quality_score': quality_score,
                'confidence': confidence,
                'risk_level': risk_level,
                'is_valid': is_valid
            }
            
        except Exception:
            return {
                'quality_score': 0.0,
                'confidence': 0.0,
                'risk_level': 5,
                'is_valid': False
            }
    
    def _calculate_prediction_metrics(self,
                                    price_data: pd.DataFrame,
                                    consolidation_range: ConsolidationRange,
                                    breakout_validity: Dict,
                                    quality_assessment: Dict) -> Dict:
        """计算预测指标"""
        try:
            # 成功概率基于质量评分和历史统计
            base_probability = quality_assessment['quality_score'] / 100
            
            # 根据盘整时间调整
            duration_factor = min(consolidation_range.duration_bars / 30, 1.2)
            success_probability = min(base_probability * duration_factor, 0.95)
            
            # 目标距离计算（基于盘整区间大小）
            range_size = consolidation_range.range_size
            if breakout_validity['type'] == BreakoutType.GENUINE:
                target_distance = range_size * 2.0  # 强突破目标距离是区间的2倍
            elif breakout_validity['type'] == BreakoutType.POTENTIAL:
                target_distance = range_size * 1.5  # 潜在突破目标距离是区间的1.5倍
            else:
                target_distance = range_size * 0.5  # 弱突破目标距离是区间的0.5倍
            
            # 预期持续时间（以K线数计算）
            base_duration = consolidation_range.duration_bars * 0.5
            strength_multiplier = {
                BreakoutStrength.WEAK: 0.5,
                BreakoutStrength.MODERATE: 1.0,
                BreakoutStrength.STRONG: 1.5,
                BreakoutStrength.EXPLOSIVE: 2.0
            }
            
            # 这里我们需要从某个地方获取strength，由于在当前函数中还没有，我们用质量评分来估算
            if quality_assessment['quality_score'] >= 80:
                multiplier = 2.0
            elif quality_assessment['quality_score'] >= 60:
                multiplier = 1.5
            elif quality_assessment['quality_score'] >= 40:
                multiplier = 1.0
            else:
                multiplier = 0.5
            
            expected_duration = int(base_duration * multiplier)
            
            return {
                'success_probability': success_probability,
                'target_distance': target_distance,
                'expected_duration': max(expected_duration, 1)
            }
            
        except Exception:
            return {
                'success_probability': 0.5,
                'target_distance': 0.0,
                'expected_duration': 1
            }
    
    def _generate_risk_control_suggestions(self,
                                         consolidation_range: ConsolidationRange,
                                         breakout_validity: Dict,
                                         current_price: float) -> Dict:
        """生成风险控制建议"""
        try:
            # 止损建议：盘整区间的另一边界
            if breakout_validity['target_boundary'] == consolidation_range.upper_boundary:
                # 向上突破，止损设在下边界
                stop_loss = consolidation_range.lower_boundary * 0.999  # 稍微留一点缓冲
                invalidation_level = consolidation_range.lower_boundary
            else:
                # 向下突破，止损设在上边界
                stop_loss = consolidation_range.upper_boundary * 1.001  # 稍微留一点缓冲
                invalidation_level = consolidation_range.upper_boundary
            
            return {
                'stop_loss': stop_loss,
                'invalidation_level': invalidation_level
            }
            
        except Exception:
            return {
                'stop_loss': current_price * 0.95,  # 默认5%止损
                'invalidation_level': current_price * 0.95
            }
    
    def _update_analysis_stats(self, breakout_signal: BreakoutSignal):
        """更新分析统计信息"""
        try:
            self.analysis_stats['total_analyses'] += 1
            
            if breakout_signal.breakout_type == BreakoutType.GENUINE:
                self.analysis_stats['genuine_breakouts'] += 1
            elif breakout_signal.breakout_type == BreakoutType.FALSE:
                self.analysis_stats['false_breakouts'] += 1
            
            # 更新平均成功率
            if self.analysis_stats['total_analyses'] > 0:
                success_rate = (self.analysis_stats['genuine_breakouts'] / 
                              self.analysis_stats['total_analyses'])
                self.analysis_stats['avg_success_rate'] = success_rate
                
        except Exception as e:
            self.logger.error(f"统计更新失败: {str(e)}")
    
    def get_analysis_stats(self) -> Dict:
        """获取分析统计信息"""
        return self.analysis_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.analysis_stats = {
            'total_analyses': 0,
            'genuine_breakouts': 0,
            'false_breakouts': 0,
            'avg_success_rate': 0.0
        }
    
    def validate_breakout_signal(self, breakout_signal: BreakoutSignal) -> Dict:
        """验证突破信号的有效性"""
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'errors': []
        }
        
        try:
            # 基本验证
            if not breakout_signal.is_valid:
                validation_result['errors'].append("信号标记为无效")
                validation_result['is_valid'] = False
            
            if breakout_signal.breakout_type == BreakoutType.INVALID:
                validation_result['errors'].append("突破类型无效")
                validation_result['is_valid'] = False
            
            if breakout_signal.quality_score < self.config.get('min_quality_score', 40):
                validation_result['warnings'].append(f"质量评分偏低: {breakout_signal.quality_score}")
            
            if breakout_signal.confidence < 0.5:
                validation_result['warnings'].append(f"置信度偏低: {breakout_signal.confidence}")
            
            if breakout_signal.volume_ratio < self.min_volume_ratio:
                validation_result['warnings'].append(f"成交量确认不足: {breakout_signal.volume_ratio}")
            
            if breakout_signal.risk_level >= 4:
                validation_result['warnings'].append(f"风险等级较高: {breakout_signal.risk_level}")
            
        except Exception as e:
            validation_result['errors'].append(f"验证过程出错: {str(e)}")
            validation_result['is_valid'] = False
        
        return validation_result