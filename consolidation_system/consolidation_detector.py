"""
盘整带识别器 - ConsolidationDetector

识别价格数据中的盘整区间，为后续的突破分析和止损策略提供基础。

核心功能：
1. 自动识别盘整区间的上下边界
2. 评估盘整的有效性和强度
3. 检测盘整的时间长度和稳定性
4. 提供多种盘整模式的识别
5. 支持成交量确认机制

算法特点：
- 基于价格波动范围的统计分析
- 动态调整识别参数
- 考虑加密货币市场的高波动特性
- 抗噪声干扰设计

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

# 设置日志
logger = logging.getLogger(__name__)


class ConsolidationType(Enum):
    """盘整类型枚举"""
    HORIZONTAL = "horizontal"      # 水平盘整
    ASCENDING = "ascending"        # 上升楔形
    DESCENDING = "descending"      # 下降楔形
    TRIANGLE = "triangle"          # 三角形整理
    RECTANGLE = "rectangle"        # 矩形整理
    FLAG = "flag"                  # 旗形整理
    PENNANT = "pennant"           # 三角旗


class ConsolidationStrength(Enum):
    """盘整强度等级"""
    WEAK = 1       # 弱盘整
    MODERATE = 2   # 中等盘整
    STRONG = 3     # 强盘整
    VERY_STRONG = 4  # 极强盘整


@dataclass
class ConsolidationRange:
    """
    盘整区间数据结构
    
    包含盘整区间的所有关键信息，用于后续的突破分析和止损计算
    """
    # 基本信息
    symbol: str                    # 交易对符号
    start_time: datetime          # 盘整开始时间
    end_time: datetime            # 盘整结束时间
    duration_bars: int            # 持续K线数
    
    # 价格边界
    upper_boundary: float         # 上边界
    lower_boundary: float         # 下边界
    range_size: float            # 区间大小
    range_percentage: float      # 区间百分比
    
    # 统计信息
    avg_price: float             # 平均价格
    median_price: float          # 中位数价格
    price_std: float            # 价格标准差
    
    # 成交量信息
    avg_volume: float           # 平均成交量
    volume_std: float          # 成交量标准差
    volume_trend: float        # 成交量趋势 (-1到1)
    
    # 质量评估
    consolidation_type: ConsolidationType   # 盘整类型
    strength: ConsolidationStrength         # 盘整强度
    quality_score: float                    # 质量评分 (0-100)
    confidence: float                       # 置信度 (0-1)
    
    # 技术特征
    support_tests: int          # 支撑测试次数
    resistance_tests: int       # 阻力测试次数
    false_breakouts: int        # 假突破次数
    volume_spikes: int          # 成交量异常次数
    
    # 元数据
    created_at: datetime        # 创建时间
    updated_at: datetime        # 更新时间
    
    def __post_init__(self):
        """后处理初始化"""
        # 计算派生指标
        if self.upper_boundary and self.lower_boundary:
            self.range_size = self.upper_boundary - self.lower_boundary
            if self.avg_price > 0:
                self.range_percentage = (self.range_size / self.avg_price) * 100
    
    def is_valid(self) -> bool:
        """检查盘整区间是否有效"""
        return (
            self.upper_boundary > self.lower_boundary and
            self.duration_bars >= 5 and
            self.quality_score >= 30 and
            self.confidence >= 0.5
        )
    
    def contains_price(self, price: float, buffer: float = 0.0) -> bool:
        """检查价格是否在盘整区间内"""
        buffer_amount = self.range_size * buffer
        return (self.lower_boundary - buffer_amount <= price <= 
                self.upper_boundary + buffer_amount)
    
    def distance_to_boundary(self, price: float) -> Dict[str, float]:
        """计算价格到边界的距离"""
        return {
            'to_upper': abs(price - self.upper_boundary),
            'to_lower': abs(price - self.lower_boundary),
            'to_upper_pct': abs(price - self.upper_boundary) / self.avg_price * 100,
            'to_lower_pct': abs(price - self.lower_boundary) / self.avg_price * 100
        }
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'symbol': self.symbol,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_bars': self.duration_bars,
            'upper_boundary': self.upper_boundary,
            'lower_boundary': self.lower_boundary,
            'range_size': self.range_size,
            'range_percentage': self.range_percentage,
            'avg_price': self.avg_price,
            'consolidation_type': self.consolidation_type.value if self.consolidation_type else None,
            'strength': self.strength.value if self.strength else None,
            'quality_score': self.quality_score,
            'confidence': self.confidence,
            'support_tests': self.support_tests,
            'resistance_tests': self.resistance_tests,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ConsolidationDetector:
    """
    盘整带识别器
    
    使用多种技术分析方法识别价格数据中的盘整区间
    """
    
    def __init__(self, config: Dict = None):
        """
        初始化盘整带识别器
        
        Args:
            config: 配置参数
        """
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 识别参数
        self.min_bars = self.config.get('min_bars', 10)
        self.max_bars = self.config.get('max_bars', 100)
        self.range_tolerance = self.config.get('range_tolerance', 0.02)
        self.volume_confirm = self.config.get('volume_confirm', True)
        self.min_quality_score = self.config.get('min_quality_score', 30)
        
        # 统计信息
        self.detection_stats = {
            'total_detections': 0,
            'valid_detections': 0,
            'invalid_detections': 0,
            'avg_quality_score': 0.0
        }
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'min_bars': 10,
            'max_bars': 100,
            'range_tolerance': 0.02,
            'volume_confirm': True,
            'min_quality_score': 30,
            'support_resistance_buffer': 0.005,
            'volume_spike_threshold': 1.5,
            'false_breakout_threshold': 0.01
        }
    
    def detect_consolidation(self, 
                           price_data: pd.DataFrame, 
                           symbol: str = "UNKNOWN") -> Optional[ConsolidationRange]:
        """
        检测盘整区间
        
        Args:
            price_data: 价格数据，必须包含 ['open', 'high', 'low', 'close', 'volume']
            symbol: 交易对符号
            
        Returns:
            ConsolidationRange: 检测到的盘整区间，如果没有则返回None
        """
        try:
            if len(price_data) < self.min_bars:
                self.logger.warning(f"数据长度不足，需要至少{self.min_bars}条数据")
                return None
            
            # 确保数据格式正确
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in price_data.columns for col in required_columns):
                self.logger.error(f"数据缺少必需列: {required_columns}")
                return None
            
            # 取最近的数据进行分析
            data = price_data.tail(self.max_bars).copy()
            
            # 1. 基础盘整检测
            consolidation_info = self._detect_basic_consolidation(data)
            if not consolidation_info:
                return None
            
            # 2. 计算详细统计信息
            stats = self._calculate_statistics(data, consolidation_info)
            
            # 3. 识别盘整类型
            consolidation_type = self._identify_consolidation_type(data, consolidation_info)
            
            # 4. 评估盘整强度
            strength = self._assess_consolidation_strength(data, consolidation_info, stats)
            
            # 5. 计算质量评分
            quality_score = self._calculate_quality_score(data, consolidation_info, stats)
            
            # 6. 计算置信度
            confidence = self._calculate_confidence(data, consolidation_info, stats)
            
            # 7. 分析支撑阻力测试
            support_resistance = self._analyze_support_resistance_tests(data, consolidation_info)
            
            # 创建盘整区间对象
            consolidation_range = ConsolidationRange(
                symbol=symbol,
                start_time=data.index[consolidation_info['start_idx']] if hasattr(data.index[0], 'to_pydatetime') else datetime.now() - timedelta(days=len(data)),
                end_time=data.index[consolidation_info['end_idx']] if hasattr(data.index[0], 'to_pydatetime') else datetime.now(),
                duration_bars=consolidation_info['duration'],
                
                upper_boundary=consolidation_info['upper_boundary'],
                lower_boundary=consolidation_info['lower_boundary'],
                range_size=consolidation_info['upper_boundary'] - consolidation_info['lower_boundary'],
                range_percentage=((consolidation_info['upper_boundary'] - consolidation_info['lower_boundary']) / stats['avg_price']) * 100,
                
                avg_price=stats['avg_price'],
                median_price=stats['median_price'],
                price_std=stats['price_std'],
                
                avg_volume=stats['avg_volume'],
                volume_std=stats['volume_std'],
                volume_trend=stats['volume_trend'],
                
                consolidation_type=consolidation_type,
                strength=strength,
                quality_score=quality_score,
                confidence=confidence,
                
                support_tests=support_resistance['support_tests'],
                resistance_tests=support_resistance['resistance_tests'],
                false_breakouts=support_resistance['false_breakouts'],
                volume_spikes=support_resistance['volume_spikes'],
                
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # 更新统计信息
            self.detection_stats['total_detections'] += 1
            if consolidation_range.is_valid():
                self.detection_stats['valid_detections'] += 1
            else:
                self.detection_stats['invalid_detections'] += 1
            
            self._update_avg_quality_score(quality_score)
            
            self.logger.info(f"检测到盘整区间: {symbol}, 质量评分: {quality_score:.1f}, 置信度: {confidence:.2f}")
            return consolidation_range
            
        except Exception as e:
            self.logger.error(f"盘整检测失败: {str(e)}")
            return None
    
    def _detect_basic_consolidation(self, data: pd.DataFrame) -> Optional[Dict]:
        """检测基础盘整模式"""
        try:
            # 使用滑动窗口寻找最佳盘整区间
            best_consolidation = None
            best_score = 0
            
            for window_size in range(self.min_bars, min(len(data), self.max_bars) + 1):
                # 计算滑动窗口中的盘整指标
                for start_idx in range(len(data) - window_size + 1):
                    end_idx = start_idx + window_size - 1
                    window_data = data.iloc[start_idx:end_idx + 1]
                    
                    # 计算价格范围
                    high_prices = window_data['high']
                    low_prices = window_data['low']
                    close_prices = window_data['close']
                    
                    upper_boundary = high_prices.max()
                    lower_boundary = low_prices.min()
                    avg_price = close_prices.mean()
                    
                    # 检查是否符合盘整条件
                    range_size = upper_boundary - lower_boundary
                    range_ratio = range_size / avg_price
                    
                    if range_ratio > self.range_tolerance * 3:  # 范围太大，不是盘整
                        continue
                    
                    # 计算价格在区间内的稳定性
                    prices_in_range = 0
                    total_bars = len(window_data)
                    
                    for _, bar in window_data.iterrows():
                        if (lower_boundary <= bar['low'] and 
                            bar['high'] <= upper_boundary):
                            prices_in_range += 1
                        elif (bar['low'] <= upper_boundary and 
                              bar['high'] >= lower_boundary):
                            prices_in_range += 0.5  # 部分在区间内
                    
                    stability_ratio = prices_in_range / total_bars
                    
                    # 评分系统
                    score = (
                        stability_ratio * 40 +           # 稳定性权重40%
                        (1 - range_ratio / self.range_tolerance) * 30 +  # 区间紧密度权重30%
                        min(window_size / self.max_bars, 1.0) * 20 +     # 持续时间权重20%
                        self._volume_consistency_score(window_data) * 10  # 成交量一致性权重10%
                    )
                    
                    if score > best_score and stability_ratio >= 0.7:
                        best_score = score
                        best_consolidation = {
                            'start_idx': start_idx,
                            'end_idx': end_idx,
                            'duration': window_size,
                            'upper_boundary': upper_boundary,
                            'lower_boundary': lower_boundary,
                            'stability_ratio': stability_ratio,
                            'range_ratio': range_ratio,
                            'score': score
                        }
            
            return best_consolidation
            
        except Exception as e:
            self.logger.error(f"基础盘整检测失败: {str(e)}")
            return None
    
    def _volume_consistency_score(self, data: pd.DataFrame) -> float:
        """计算成交量一致性评分"""
        try:
            if not self.volume_confirm or len(data) < 3:
                return 0.5  # 默认中等评分
            
            volumes = data['volume']
            avg_volume = volumes.mean()
            volume_std = volumes.std()
            
            if avg_volume == 0:
                return 0.0
            
            # 计算变异系数 (CV)
            cv = volume_std / avg_volume
            
            # CV越小，一致性越好
            consistency_score = max(0, 1.0 - cv)
            return min(consistency_score, 1.0)
            
        except Exception:
            return 0.5
    
    def _calculate_statistics(self, data: pd.DataFrame, consolidation_info: Dict) -> Dict:
        """计算统计信息"""
        try:
            start_idx = consolidation_info['start_idx']
            end_idx = consolidation_info['end_idx']
            window_data = data.iloc[start_idx:end_idx + 1]
            
            close_prices = window_data['close']
            volumes = window_data['volume']
            
            # 价格统计
            avg_price = close_prices.mean()
            median_price = close_prices.median()
            price_std = close_prices.std()
            
            # 成交量统计
            avg_volume = volumes.mean()
            volume_std = volumes.std()
            
            # 成交量趋势（线性回归斜率）
            volume_trend = 0.0
            if len(volumes) > 2:
                x = np.arange(len(volumes))
                z = np.polyfit(x, volumes, 1)
                volume_trend = z[0] / avg_volume  # 标准化斜率
            
            return {
                'avg_price': avg_price,
                'median_price': median_price,
                'price_std': price_std,
                'avg_volume': avg_volume,
                'volume_std': volume_std,
                'volume_trend': volume_trend
            }
            
        except Exception as e:
            self.logger.error(f"统计计算失败: {str(e)}")
            return {}
    
    def _identify_consolidation_type(self, data: pd.DataFrame, consolidation_info: Dict) -> ConsolidationType:
        """识别盘整类型"""
        try:
            start_idx = consolidation_info['start_idx']
            end_idx = consolidation_info['end_idx']
            window_data = data.iloc[start_idx:end_idx + 1]
            
            highs = window_data['high']
            lows = window_data['low']
            
            # 计算上下轨趋势
            x = np.arange(len(highs))
            
            # 上轨趋势
            upper_trend = 0
            if len(highs) > 2:
                upper_coef = np.polyfit(x, highs, 1)
                upper_trend = upper_coef[0]
            
            # 下轨趋势  
            lower_trend = 0
            if len(lows) > 2:
                lower_coef = np.polyfit(x, lows, 1)
                lower_trend = lower_coef[0]
            
            # 根据趋势判断类型
            trend_threshold = consolidation_info['upper_boundary'] * 0.001  # 0.1%
            
            if abs(upper_trend) < trend_threshold and abs(lower_trend) < trend_threshold:
                return ConsolidationType.HORIZONTAL
            elif upper_trend > trend_threshold and lower_trend > trend_threshold:
                return ConsolidationType.ASCENDING
            elif upper_trend < -trend_threshold and lower_trend < -trend_threshold:
                return ConsolidationType.DESCENDING
            elif upper_trend < -trend_threshold and lower_trend > trend_threshold:
                return ConsolidationType.TRIANGLE
            else:
                return ConsolidationType.RECTANGLE
            
        except Exception:
            return ConsolidationType.HORIZONTAL
    
    def _assess_consolidation_strength(self, data: pd.DataFrame, 
                                     consolidation_info: Dict, 
                                     stats: Dict) -> ConsolidationStrength:
        """评估盘整强度"""
        try:
            # 因素1: 持续时间 (权重30%)
            duration_score = min(consolidation_info['duration'] / self.max_bars, 1.0)
            
            # 因素2: 价格稳定性 (权重40%)
            stability_score = consolidation_info['stability_ratio']
            
            # 因素3: 成交量一致性 (权重20%)
            volume_score = self._volume_consistency_score(
                data.iloc[consolidation_info['start_idx']:consolidation_info['end_idx'] + 1]
            )
            
            # 因素4: 区间紧密度 (权重10%)
            range_score = max(0, 1 - consolidation_info['range_ratio'] / self.range_tolerance)
            
            # 综合评分
            total_score = (
                duration_score * 30 +
                stability_score * 40 +
                volume_score * 20 +
                range_score * 10
            )
            
            # 转换为强度等级
            if total_score >= 80:
                return ConsolidationStrength.VERY_STRONG
            elif total_score >= 65:
                return ConsolidationStrength.STRONG
            elif total_score >= 45:
                return ConsolidationStrength.MODERATE
            else:
                return ConsolidationStrength.WEAK
                
        except Exception:
            return ConsolidationStrength.WEAK
    
    def _calculate_quality_score(self, data: pd.DataFrame, 
                               consolidation_info: Dict, 
                               stats: Dict) -> float:
        """计算质量评分 (0-100)"""
        try:
            # 基础评分
            base_score = consolidation_info.get('score', 0)
            
            # 调整因子
            adjustments = 0
            
            # 1. 持续时间调整
            if consolidation_info['duration'] >= 20:
                adjustments += 10
            elif consolidation_info['duration'] >= 15:
                adjustments += 5
            
            # 2. 稳定性调整
            if consolidation_info['stability_ratio'] >= 0.9:
                adjustments += 15
            elif consolidation_info['stability_ratio'] >= 0.8:
                adjustments += 10
            
            # 3. 成交量确认调整
            if self.volume_confirm:
                volume_score = self._volume_consistency_score(
                    data.iloc[consolidation_info['start_idx']:consolidation_info['end_idx'] + 1]
                )
                if volume_score >= 0.7:
                    adjustments += 8
                elif volume_score >= 0.5:
                    adjustments += 4
            
            # 4. 区间紧密度调整
            if consolidation_info['range_ratio'] <= self.range_tolerance * 0.5:
                adjustments += 10
            elif consolidation_info['range_ratio'] <= self.range_tolerance:
                adjustments += 5
            
            final_score = min(base_score + adjustments, 100)
            return max(final_score, 0)
            
        except Exception:
            return 0.0
    
    def _calculate_confidence(self, data: pd.DataFrame, 
                            consolidation_info: Dict, 
                            stats: Dict) -> float:
        """计算置信度 (0-1)"""
        try:
            confidence_factors = []
            
            # 1. 数据充足性
            data_adequacy = min(len(data) / (self.min_bars * 2), 1.0)
            confidence_factors.append(data_adequacy * 0.2)
            
            # 2. 稳定性置信度
            stability_confidence = consolidation_info['stability_ratio']
            confidence_factors.append(stability_confidence * 0.4)
            
            # 3. 持续时间置信度
            duration_confidence = min(consolidation_info['duration'] / 30, 1.0)
            confidence_factors.append(duration_confidence * 0.2)
            
            # 4. 成交量置信度
            volume_confidence = self._volume_consistency_score(
                data.iloc[consolidation_info['start_idx']:consolidation_info['end_idx'] + 1]
            )
            confidence_factors.append(volume_confidence * 0.2)
            
            total_confidence = sum(confidence_factors)
            return min(max(total_confidence, 0.0), 1.0)
            
        except Exception:
            return 0.5
    
    def _analyze_support_resistance_tests(self, data: pd.DataFrame, 
                                        consolidation_info: Dict) -> Dict:
        """分析支撑阻力测试次数"""
        try:
            start_idx = consolidation_info['start_idx']
            end_idx = consolidation_info['end_idx']
            window_data = data.iloc[start_idx:end_idx + 1]
            
            upper_boundary = consolidation_info['upper_boundary']
            lower_boundary = consolidation_info['lower_boundary']
            
            buffer = (upper_boundary - lower_boundary) * self.config.get('support_resistance_buffer', 0.005)
            
            support_tests = 0
            resistance_tests = 0
            false_breakouts = 0
            volume_spikes = 0
            
            avg_volume = window_data['volume'].mean()
            volume_threshold = avg_volume * self.config.get('volume_spike_threshold', 1.5)
            
            for _, bar in window_data.iterrows():
                # 支撑测试
                if bar['low'] <= lower_boundary + buffer:
                    support_tests += 1
                    # 假突破检测
                    if bar['close'] < lower_boundary - buffer:
                        false_breakouts += 1
                
                # 阻力测试
                if bar['high'] >= upper_boundary - buffer:
                    resistance_tests += 1
                    # 假突破检测
                    if bar['close'] > upper_boundary + buffer:
                        false_breakouts += 1
                
                # 成交量异常
                if bar['volume'] > volume_threshold:
                    volume_spikes += 1
            
            return {
                'support_tests': support_tests,
                'resistance_tests': resistance_tests,
                'false_breakouts': false_breakouts,
                'volume_spikes': volume_spikes
            }
            
        except Exception:
            return {
                'support_tests': 0,
                'resistance_tests': 0,
                'false_breakouts': 0,
                'volume_spikes': 0
            }
    
    def _update_avg_quality_score(self, new_score: float):
        """更新平均质量评分"""
        total = self.detection_stats['total_detections']
        if total == 1:
            self.detection_stats['avg_quality_score'] = new_score
        else:
            current_avg = self.detection_stats['avg_quality_score']
            self.detection_stats['avg_quality_score'] = (
                (current_avg * (total - 1) + new_score) / total
            )
    
    def get_detection_stats(self) -> Dict:
        """获取检测统计信息"""
        return self.detection_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.detection_stats = {
            'total_detections': 0,
            'valid_detections': 0,
            'invalid_detections': 0,
            'avg_quality_score': 0.0
        }
    
    def validate_consolidation(self, consolidation_range: ConsolidationRange) -> Dict:
        """验证盘整区间的有效性"""
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'errors': []
        }
        
        try:
            # 基本验证
            if not consolidation_range.upper_boundary > consolidation_range.lower_boundary:
                validation_result['errors'].append("上边界必须大于下边界")
                validation_result['is_valid'] = False
            
            if consolidation_range.duration_bars < self.min_bars:
                validation_result['errors'].append(f"持续时间过短，最少需要{self.min_bars}根K线")
                validation_result['is_valid'] = False
            
            if consolidation_range.quality_score < self.min_quality_score:
                validation_result['warnings'].append(f"质量评分偏低: {consolidation_range.quality_score}")
            
            if consolidation_range.confidence < 0.5:
                validation_result['warnings'].append(f"置信度偏低: {consolidation_range.confidence}")
            
            if consolidation_range.range_percentage > 5.0:
                validation_result['warnings'].append(f"价格区间过大: {consolidation_range.range_percentage:.2f}%")
            
        except Exception as e:
            validation_result['errors'].append(f"验证过程出错: {str(e)}")
            validation_result['is_valid'] = False
        
        return validation_result