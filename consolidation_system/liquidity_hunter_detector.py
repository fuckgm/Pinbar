"""
流动性猎杀检测器 - LiquidityHunterDetector

检测大资金的流动性猎杀行为，识别洗盘和止损猎杀模式。

核心功能：
1. 识别流动性聚集区域
2. 检测大资金的洗盘行为
3. 预测止损猎杀区域
4. 分析成交量和价格异常
5. 提供反向操作建议

检测原理：
- 大资金需要流动性来建仓/平仓
- 散户止损单集中在明显的技术位
- 突破后的快速回撤往往是洗盘
- 异常成交量配合价格拒绝是猎杀信号

应用价值：
- 减少被洗盘震出的概率
- 识别假突破和真突破
- 提供更智能的持仓决策
- 优化入场和出场时机

Author: Pinbar Strategy Team
Date: 2024-12
Version: 1.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from .consolidation_detector import ConsolidationRange
from .breakout_analyzer import BreakoutSignal, BreakoutDirection
from .range_cache_manager import CachedRange

# 设置日志
logger = logging.getLogger(__name__)


class HuntingType(Enum):
    """猎杀类型枚举"""
    STOP_HUNT = "stop_hunt"           # 止损猎杀
    LIQUIDITY_GRAB = "liquidity_grab"  # 流动性抓取
    FAKE_BREAKOUT = "fake_breakout"   # 假突破
    WASHOUT = "washout"               # 洗盘
    SQUEEZE = "squeeze"               # 挤压


class LiquidityZoneType(Enum):
    """流动性区域类型枚举"""
    SUPPORT_CLUSTER = "support_cluster"        # 支撑聚集区
    RESISTANCE_CLUSTER = "resistance_cluster"  # 阻力聚集区
    STOP_LOSS_CLUSTER = "stop_loss_cluster"   # 止损聚集区
    PSYCHOLOGICAL_LEVEL = "psychological_level" # 心理价位
    TECHNICAL_LEVEL = "technical_level"        # 技术位


class HuntingStrength(Enum):
    """猎杀强度枚举"""
    WEAK = 1         # 弱猎杀
    MODERATE = 2     # 中等猎杀
    STRONG = 3       # 强猎杀
    EXTREME = 4      # 极端猎杀


@dataclass
class LiquidityZone:
    """
    流动性区域数据结构
    
    标识价格中的流动性聚集区域
    """
    # 基本信息
    zone_type: LiquidityZoneType = LiquidityZoneType.SUPPORT_CLUSTER    # 区域类型
    price_level: float = 0.0              # 价格水平
    price_range: Tuple[float, float] = (0.0, 0.0) # 价格范围 (下限, 上限)
    strength: float = 50.0                 # 强度评分 (0-100)
    
    # 统计信息
    touch_count: int = 0               # 触碰次数
    volume_concentration: float = 0.0    # 成交量集中度
    rejection_count: int = 0           # 拒绝次数
    penetration_count: int = 0         # 穿透次数
    
    # 时间信息
    first_touch: datetime = field(default_factory=datetime.now)          # 首次触碰时间
    last_touch: datetime = field(default_factory=datetime.now)           # 最后触碰时间
    formation_period: int = 1          # 形成周期(K线数)
    
    # 预测信息
    hunt_probability: float = 0.5        # 被猎杀概率
    target_distance: float = 0.0         # 猎杀目标距离
    expected_reaction: str = "unknown"         # 预期反应
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)          # 创建时间
    confidence: float = 0.5             # 置信度
    notes: str = ""                    # 备注
    
    def is_active(self) -> bool:
        """检查区域是否活跃"""
        time_since_last_touch = datetime.now() - self.last_touch
        return time_since_last_touch.total_seconds() < 24 * 3600  # 24小时内有触碰
    
    def get_zone_info(self) -> Dict:
        """获取区域信息摘要"""
        return {
            'type': self.zone_type.value,
            'price_level': self.price_level,
            'strength': self.strength,
            'touch_count': self.touch_count,
            'rejection_count': self.rejection_count,
            'hunt_probability': self.hunt_probability,
            'is_active': self.is_active(),
            'confidence': self.confidence
        }


@dataclass
class HuntingSignal:
    """
    猎杀信号数据结构
    
    检测到的流动性猎杀行为信号
    """
    # 基本信息
    hunting_type: HuntingType = HuntingType.STOP_HUNT      # 猎杀类型
    strength: HuntingStrength = HuntingStrength.WEAK      # 猎杀强度
    target_zone: Optional[LiquidityZone] = None           # 目标区域
    
    # 价格信息
    hunt_price: float = 0.0             # 猎杀价格
    reversal_price: float = 0.0         # 反转价格
    distance_hunted: float = 0.0        # 猎杀距离
    
    # 成交量信息
    volume_spike: float = 1.0           # 成交量激增倍数
    volume_profile: Dict = field(default_factory=dict)          # 成交量分布
    absorption_detected: bool = False     # 是否检测到吸筹
    
    # 时间信息
    hunt_start_time: datetime = field(default_factory=datetime.now)     # 猎杀开始时间
    hunt_duration: timedelta = field(default_factory=lambda: timedelta(minutes=5))      # 猎杀持续时间
    reversal_time: Optional[datetime] = None  # 反转时间
    
    # 确认信息
    is_confirmed: bool = False           # 是否确认
    confirmation_signals: List[str] = field(default_factory=list) # 确认信号列表
    false_signal_risk: float = 0.5     # 误判风险
    
    # 操作建议
    recommended_action: str = "观察"       # 推荐行动
    hold_suggestion: bool = False        # 是否建议持有
    entry_opportunity: bool = False      # 是否为入场机会
    
    # 质量评估
    signal_quality: float = 0.0        # 信号质量 (0-100)
    confidence: float = 0.0           # 置信度 (0-1)
    
    # 元数据
    detected_at: datetime = field(default_factory=datetime.now)        # 检测时间
    
    def is_valid_hunting_signal(self) -> bool:
        """检查是否为有效的猎杀信号"""
        return (
            self.is_confirmed and
            self.signal_quality >= 50 and
            self.confidence >= 0.6 and
            self.false_signal_risk <= 0.4
        )
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'hunting_type': self.hunting_type.value,
            'strength': self.strength.value,
            'hunt_price': self.hunt_price,
            'volume_spike': self.volume_spike,
            'hunt_duration_minutes': self.hunt_duration.total_seconds() / 60,
            'is_confirmed': self.is_confirmed,
            'recommended_action': self.recommended_action,
            'signal_quality': self.signal_quality,
            'confidence': self.confidence,
            'target_zone_info': self.target_zone.get_zone_info()
        }


class LiquidityHunterDetector:
    """
    流动性猎杀检测器
    
    检测和分析大资金的流动性猎杀行为
    """
    
    def __init__(self, config: Dict = None):
        """
        初始化流动性猎杀检测器
        
        Args:
            config: 配置参数
        """
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 检测参数
        self.detection_enabled = self.config.get('detection_enabled', True)
        self.volume_spike_threshold = self.config.get('volume_spike_threshold', 2.0)
        self.price_rejection_threshold = self.config.get('price_rejection_threshold', 0.01)
        self.min_hunt_distance = self.config.get('min_hunt_distance', 0.005)
        
        # 流动性区域缓存
        self.liquidity_zones: Dict[str, List[LiquidityZone]] = {}  # symbol -> zones
        self.hunting_signals: List[HuntingSignal] = []
        
        # 统计信息
        self.detection_stats = {
            'total_hunts_detected': 0,
            'confirmed_hunts': 0,
            'false_signals': 0,
            'successful_predictions': 0,
            'avg_hunt_accuracy': 0.0,
            'zones_identified': 0
        }
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            # 基本检测参数
            'detection_enabled': True,
            'volume_spike_threshold': 2.0,      # 成交量激增阈值
            'price_rejection_threshold': 0.015, # 价格拒绝阈值 1.5%
            'min_hunt_distance': 0.005,         # 最小猎杀距离 0.5%
            
            # 流动性区域参数
            'zone_strength_threshold': 30,      # 区域强度阈值
            'zone_touch_min': 2,                # 最小触碰次数
            'zone_formation_period': 20,        # 区域形成周期
            'zone_expiry_hours': 24 * 7,        # 区域过期时间(7天)
            
            # 猎杀检测参数
            'hunt_confirmation_bars': 3,        # 猎杀确认K线数
            'reversal_confirmation_time': 15,   # 反转确认时间(分钟)
            'absorption_volume_ratio': 3.0,     # 吸筹成交量比率
            
            # 心理价位参数
            'psychological_levels': [
                50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 25000, 30000, 50000
            ],
            'round_number_sensitivity': 100,    # 整数敏感度
            
            # 质量控制参数
            'min_signal_quality': 50,          # 最小信号质量
            'max_false_signal_risk': 0.4,      # 最大误判风险
            'confirmation_weight': 0.7,        # 确认权重
        }
    
    def detect_hunting(self,
                      price_data: pd.DataFrame,
                      cached_range: CachedRange,
                      breakout_signal: BreakoutSignal) -> Optional[HuntingSignal]:
        """
        检测流动性猎杀
        
        Args:
            price_data: 价格数据
            cached_range: 缓存区间
            breakout_signal: 突破信号
            
        Returns:
            HuntingSignal: 猎杀信号，如果没有则返回None
        """
        try:
            if not self.detection_enabled:
                return None
            
            if len(price_data) < 20:  # 数据不足
                return None
            
            symbol = cached_range.symbol
            
            # 1. 更新流动性区域
            self._update_liquidity_zones(symbol, price_data, cached_range)
            
            # 2. 检测当前是否有猎杀行为
            hunting_signal = self._detect_current_hunting(
                price_data, cached_range, breakout_signal
            )
            
            if hunting_signal:
                # 3. 验证和确认信号
                hunting_signal = self._validate_hunting_signal(
                    hunting_signal, price_data, cached_range
                )
                
                if hunting_signal and hunting_signal.is_valid_hunting_signal():
                    # 4. 记录信号
                    self.hunting_signals.append(hunting_signal)
                    self._update_detection_stats(hunting_signal)
                    
                    self.logger.info(f"检测到流动性猎杀: {symbol}, "
                                   f"类型: {hunting_signal.hunting_type.value}, "
                                   f"强度: {hunting_signal.strength.value}, "
                                   f"质量: {hunting_signal.signal_quality:.1f}")
                    
                    return hunting_signal
            
            return None
            
        except Exception as e:
            self.logger.error(f"流动性猎杀检测失败: {str(e)}")
            return None
    
    def _update_liquidity_zones(self,
                              symbol: str,
                              price_data: pd.DataFrame,
                              cached_range: CachedRange):
        """更新流动性区域"""
        try:
            if symbol not in self.liquidity_zones:
                self.liquidity_zones[symbol] = []
            
            # 1. 检测支撑阻力聚集区
            sr_zones = self._detect_support_resistance_clusters(price_data)
            
            # 2. 检测止损聚集区
            stop_zones = self._detect_stop_loss_clusters(price_data, cached_range)
            
            # 3. 检测心理价位
            psychological_zones = self._detect_psychological_levels(price_data)
            
            # 4. 检测技术位聚集
            technical_zones = self._detect_technical_levels(price_data)
            
            # 合并所有区域
            new_zones = sr_zones + stop_zones + psychological_zones + technical_zones
            
            # 更新现有区域或添加新区域
            for new_zone in new_zones:
                existing_zone = self._find_existing_zone(symbol, new_zone)
                if existing_zone:
                    self._update_existing_zone(existing_zone, new_zone)
                else:
                    self.liquidity_zones[symbol].append(new_zone)
                    self.detection_stats['zones_identified'] += 1
            
            # 清理过期区域
            self._cleanup_expired_zones(symbol)
            
        except Exception as e:
            self.logger.error(f"更新流动性区域失败: {str(e)}")
    
    def _detect_support_resistance_clusters(self, price_data: pd.DataFrame) -> List[LiquidityZone]:
        """检测支撑阻力聚集区"""
        try:
            zones = []
            lookback = min(50, len(price_data))
            recent_data = price_data.tail(lookback)
            
            # 找到局部高点和低点
            highs = []
            lows = []
            
            for i in range(2, len(recent_data) - 2):
                current = recent_data.iloc[i]
                prev2 = recent_data.iloc[i-2]
                prev1 = recent_data.iloc[i-1]
                next1 = recent_data.iloc[i+1]
                next2 = recent_data.iloc[i+2]
                
                # 局部高点
                if (current['high'] > prev2['high'] and 
                    current['high'] > prev1['high'] and
                    current['high'] > next1['high'] and 
                    current['high'] > next2['high']):
                    highs.append({
                        'price': current['high'],
                        'time': current.name,
                        'volume': current['volume']
                    })
                
                # 局部低点
                if (current['low'] < prev2['low'] and 
                    current['low'] < prev1['low'] and
                    current['low'] < next1['low'] and 
                    current['low'] < next2['low']):
                    lows.append({
                        'price': current['low'],
                        'time': current.name,
                        'volume': current['volume']
                    })
            
            # 聚类分析 - 找到价格聚集区
            def cluster_levels(levels, tolerance=0.01):
                if not levels:
                    return []
                
                clusters = []
                sorted_levels = sorted(levels, key=lambda x: x['price'])
                
                current_cluster = [sorted_levels[0]]
                
                for level in sorted_levels[1:]:
                    if abs(level['price'] - current_cluster[-1]['price']) / current_cluster[-1]['price'] <= tolerance:
                        current_cluster.append(level)
                    else:
                        if len(current_cluster) >= 2:  # 至少2个点才形成聚集
                            clusters.append(current_cluster)
                        current_cluster = [level]
                
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                
                return clusters
            
            # 处理阻力聚集区
            resistance_clusters = cluster_levels(highs)
            for cluster in resistance_clusters:
                avg_price = np.mean([level['price'] for level in cluster])
                price_range = (
                    min(level['price'] for level in cluster),
                    max(level['price'] for level in cluster)
                )
                touch_count = len(cluster)
                avg_volume = np.mean([level['volume'] for level in cluster])
                
                zone = LiquidityZone(
                    zone_type=LiquidityZoneType.RESISTANCE_CLUSTER,
                    price_level=avg_price,
                    price_range=price_range,
                    strength=min(touch_count * 20, 100),
                    touch_count=touch_count,
                    volume_concentration=avg_volume,
                    rejection_count=0,
                    penetration_count=0,
                    first_touch=cluster[0]['time'],
                    last_touch=cluster[-1]['time'],
                    formation_period=len(cluster),
                    hunt_probability=min(touch_count / 10, 0.8),
                    target_distance=0.002,  # 0.2%
                    expected_reaction="rejection",
                    created_at=datetime.now(),
                    confidence=min(touch_count / 5, 1.0),
                    notes=f"阻力聚集区，{touch_count}次触碰"
                )
                zones.append(zone)
            
            # 处理支撑聚集区
            support_clusters = cluster_levels(lows)
            for cluster in support_clusters:
                avg_price = np.mean([level['price'] for level in cluster])
                price_range = (
                    min(level['price'] for level in cluster),
                    max(level['price'] for level in cluster)
                )
                touch_count = len(cluster)
                avg_volume = np.mean([level['volume'] for level in cluster])
                
                zone = LiquidityZone(
                    zone_type=LiquidityZoneType.SUPPORT_CLUSTER,
                    price_level=avg_price,
                    price_range=price_range,
                    strength=min(touch_count * 20, 100),
                    touch_count=touch_count,
                    volume_concentration=avg_volume,
                    rejection_count=0,
                    penetration_count=0,
                    first_touch=cluster[0]['time'],
                    last_touch=cluster[-1]['time'],
                    formation_period=len(cluster),
                    hunt_probability=min(touch_count / 10, 0.8),
                    target_distance=0.002,
                    expected_reaction="bounce",
                    created_at=datetime.now(),
                    confidence=min(touch_count / 5, 1.0),
                    notes=f"支撑聚集区，{touch_count}次触碰"
                )
                zones.append(zone)
            
            return zones
            
        except Exception as e:
            self.logger.error(f"检测支撑阻力聚集失败: {str(e)}")
            return []
    
    def _detect_stop_loss_clusters(self, 
                                 price_data: pd.DataFrame, 
                                 cached_range: CachedRange) -> List[LiquidityZone]:
        """检测止损聚集区"""
        try:
            zones = []
            consolidation = cached_range.consolidation_range
            
            # 盘整区间边界是明显的止损聚集区
            # 上边界上方 - 空头止损聚集
            upper_stop_zone = LiquidityZone(
                zone_type=LiquidityZoneType.STOP_LOSS_CLUSTER,
                price_level=consolidation.upper_boundary * 1.005,  # 稍微高于边界
                price_range=(
                    consolidation.upper_boundary * 1.001,
                    consolidation.upper_boundary * 1.01
                ),
                strength=70,  # 较高强度
                touch_count=0,
                volume_concentration=0,
                rejection_count=0,
                penetration_count=0,
                first_touch=datetime.now(),
                last_touch=datetime.now(),
                formation_period=1,
                hunt_probability=0.7,  # 高猎杀概率
                target_distance=0.01,   # 1%猎杀距离
                expected_reaction="hunt_and_reverse",
                created_at=datetime.now(),
                confidence=0.8,
                notes="盘整上边界止损聚集区"
            )
            zones.append(upper_stop_zone)
            
            # 下边界下方 - 多头止损聚集
            lower_stop_zone = LiquidityZone(
                zone_type=LiquidityZoneType.STOP_LOSS_CLUSTER,
                price_level=consolidation.lower_boundary * 0.995,  # 稍微低于边界
                price_range=(
                    consolidation.lower_boundary * 0.99,
                    consolidation.lower_boundary * 0.999
                ),
                strength=70,
                touch_count=0,
                volume_concentration=0,
                rejection_count=0,
                penetration_count=0,
                first_touch=datetime.now(),
                last_touch=datetime.now(),
                formation_period=1,
                hunt_probability=0.7,
                target_distance=0.01,
                expected_reaction="hunt_and_reverse",
                created_at=datetime.now(),
                confidence=0.8,
                notes="盘整下边界止损聚集区"
            )
            zones.append(lower_stop_zone)
            
            return zones
            
        except Exception as e:
            self.logger.error(f"检测止损聚集区失败: {str(e)}")
            return []
    
    def _detect_psychological_levels(self, price_data: pd.DataFrame) -> List[LiquidityZone]:
        """检测心理价位"""
        try:
            zones = []
            current_price = price_data['close'].iloc[-1]
            
            # 获取配置的心理价位
            psychological_levels = self.config.get('psychological_levels', [])
            round_sensitivity = self.config.get('round_number_sensitivity', 100)
            
            # 检查整数价位
            for level in psychological_levels:
                if abs(current_price - level) / current_price <= 0.1:  # 当前价格10%范围内
                    zone = LiquidityZone(
                        zone_type=LiquidityZoneType.PSYCHOLOGICAL_LEVEL,
                        price_level=level,
                        price_range=(level * 0.999, level * 1.001),
                        strength=60,
                        touch_count=1,
                        volume_concentration=0,
                        rejection_count=0,
                        penetration_count=0,
                        first_touch=datetime.now(),
                        last_touch=datetime.now(),
                        formation_period=1,
                        hunt_probability=0.6,
                        target_distance=0.005,
                        expected_reaction="temporary_pause",
                        created_at=datetime.now(),
                        confidence=0.7,
                        notes=f"心理价位 {level}"
                    )
                    zones.append(zone)
            
            # 检查当前价格附近的整数位
            current_rounded = round(current_price / round_sensitivity) * round_sensitivity
            if abs(current_price - current_rounded) / current_price <= 0.02:  # 2%范围内
                zone = LiquidityZone(
                    zone_type=LiquidityZoneType.PSYCHOLOGICAL_LEVEL,
                    price_level=current_rounded,
                    price_range=(current_rounded * 0.998, current_rounded * 1.002),
                    strength=50,
                    touch_count=1,
                    volume_concentration=0,
                    rejection_count=0,
                    penetration_count=0,
                    first_touch=datetime.now(),
                    last_touch=datetime.now(),
                    formation_period=1,
                    hunt_probability=0.5,
                    target_distance=0.003,
                    expected_reaction="minor_reaction",
                    created_at=datetime.now(),
                    confidence=0.6,
                    notes=f"整数价位 {current_rounded}"
                )
                zones.append(zone)
            
            return zones
            
        except Exception as e:
            self.logger.error(f"检测心理价位失败: {str(e)}")
            return []
    
    def _detect_technical_levels(self, price_data: pd.DataFrame) -> List[LiquidityZone]:
        """检测技术位聚集"""
        try:
            zones = []
            
            if len(price_data) < 20:
                return zones
            
            # 移动平均线
            ma_periods = [20, 50, 200]
            for period in ma_periods:
                if len(price_data) >= period:
                    ma_value = price_data['close'].tail(period).mean()
                    
                    zone = LiquidityZone(
                        zone_type=LiquidityZoneType.TECHNICAL_LEVEL,
                        price_level=ma_value,
                        price_range=(ma_value * 0.999, ma_value * 1.001),
                        strength=40,
                        touch_count=1,
                        volume_concentration=0,
                        rejection_count=0,
                        penetration_count=0,
                        first_touch=datetime.now(),
                        last_touch=datetime.now(),
                        formation_period=period,
                        hunt_probability=0.4,
                        target_distance=0.002,
                        expected_reaction="test_and_continue",
                        created_at=datetime.now(),
                        confidence=0.5,
                        notes=f"MA{period} 技术位"
                    )
                    zones.append(zone)
            
            return zones
            
        except Exception as e:
            self.logger.error(f"检测技术位失败: {str(e)}")
            return []
    
    def _detect_current_hunting(self,
                              price_data: pd.DataFrame,
                              cached_range: CachedRange,
                              breakout_signal: BreakoutSignal) -> Optional[HuntingSignal]:
        """检测当前的猎杀行为"""
        try:
            recent_data = price_data.tail(10)  # 最近10根K线
            if len(recent_data) < 5:
                return None
            
            current_price = recent_data['close'].iloc[-1]
            consolidation = cached_range.consolidation_range
            
            # 1. 检测止损猎杀
            stop_hunt = self._detect_stop_hunt(recent_data, consolidation, breakout_signal)
            if stop_hunt:
                return stop_hunt
            
            # 2. 检测假突破
            fake_breakout = self._detect_fake_breakout(recent_data, consolidation, breakout_signal)
            if fake_breakout:
                return fake_breakout
            
            # 3. 检测洗盘
            washout = self._detect_washout(recent_data, consolidation, breakout_signal)
            if washout:
                return washout
            
            # 4. 检测流动性抓取
            liquidity_grab = self._detect_liquidity_grab(recent_data, consolidation)
            if liquidity_grab:
                return liquidity_grab
            
            return None
            
        except Exception as e:
            self.logger.error(f"检测当前猎杀失败: {str(e)}")
            return None
    
    def _detect_stop_hunt(self,
                         recent_data: pd.DataFrame,
                         consolidation: ConsolidationRange,
                         breakout_signal: BreakoutSignal) -> Optional[HuntingSignal]:
        """检测止损猎杀"""
        try:
            # 查找价格快速穿越边界后迅速回撤的模式
            if breakout_signal.direction == BreakoutDirection.UP:
                # 向上突破后的止损猎杀
                target_boundary = consolidation.upper_boundary
                hunt_threshold = target_boundary * 1.01  # 1%以上为猎杀
                
                for i in range(len(recent_data)):
                    bar = recent_data.iloc[i]
                    
                    # 检查是否突破到猎杀区域
                    if bar['high'] > hunt_threshold:
                        # 检查是否快速回撤
                        subsequent_bars = recent_data.iloc[i+1:]
                        if len(subsequent_bars) > 0:
                            min_close_after = subsequent_bars['close'].min()
                            if min_close_after < target_boundary:
                                # 发现止损猎杀模式
                                return self._create_hunting_signal(
                                    HuntingType.STOP_HUNT,
                                    bar['high'],
                                    min_close_after,
                                    recent_data,
                                    consolidation
                                )
            else:
                # 向下突破后的止损猎杀
                target_boundary = consolidation.lower_boundary
                hunt_threshold = target_boundary * 0.99  # 1%以下为猎杀
                
                for i in range(len(recent_data)):
                    bar = recent_data.iloc[i]
                    
                    if bar['low'] < hunt_threshold:
                        subsequent_bars = recent_data.iloc[i+1:]
                        if len(subsequent_bars) > 0:
                            max_close_after = subsequent_bars['close'].max()
                            if max_close_after > target_boundary:
                                return self._create_hunting_signal(
                                    HuntingType.STOP_HUNT,
                                    bar['low'],
                                    max_close_after,
                                    recent_data,
                                    consolidation
                                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"检测止损猎杀失败: {str(e)}")
            return None
    
    def _detect_fake_breakout(self,
                            recent_data: pd.DataFrame,
                            consolidation: ConsolidationRange,
                            breakout_signal: BreakoutSignal) -> Optional[HuntingSignal]:
        """检测假突破"""
        try:
            # 假突破特征：突破后无法维持，快速回到区间内
            current_price = recent_data['close'].iloc[-1]
            
            # 检查是否已经回到盘整区间内
            if consolidation.contains_price(current_price, 0.001):
                # 突破后又回到区间内，可能是假突破
                if breakout_signal.breakout_percentage > 0.5:  # 有明显突破距离
                    return self._create_hunting_signal(
                        HuntingType.FAKE_BREAKOUT,
                        breakout_signal.breakout_price,
                        current_price,
                        recent_data,
                        consolidation
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"检测假突破失败: {str(e)}")
            return None
    
    def _detect_washout(self,
                       recent_data: pd.DataFrame,
                       consolidation: ConsolidationRange,
                       breakout_signal: BreakoutSignal) -> Optional[HuntingSignal]:
        """检测洗盘"""
        try:
            # 洗盘特征：突破后的快速但浅层回撤，配合成交量减少
            if len(recent_data) < 3:
                return None
            
            # 计算回撤幅度
            if breakout_signal.direction == BreakoutDirection.UP:
                high_price = recent_data['high'].max()
                current_price = recent_data['close'].iloc[-1]
                retracement = (high_price - current_price) / high_price
                
                # 10-30%的回撤可能是洗盘
                if 0.1 <= retracement <= 0.3:
                    # 检查成交量是否递减（洗盘特征）
                    volume_trend = self._calculate_volume_trend(recent_data)
                    if volume_trend < 0:  # 成交量递减
                        return self._create_hunting_signal(
                            HuntingType.WASHOUT,
                            high_price,
                            current_price,
                            recent_data,
                            consolidation
                        )
            else:
                low_price = recent_data['low'].min()
                current_price = recent_data['close'].iloc[-1]
                retracement = (current_price - low_price) / low_price
                
                if 0.1 <= retracement <= 0.3:
                    volume_trend = self._calculate_volume_trend(recent_data)
                    if volume_trend < 0:
                        return self._create_hunting_signal(
                            HuntingType.WASHOUT,
                            low_price,
                            current_price,
                            recent_data,
                            consolidation
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"检测洗盘失败: {str(e)}")
            return None
    
    def _detect_liquidity_grab(self,
                             recent_data: pd.DataFrame,
                             consolidation: ConsolidationRange) -> Optional[HuntingSignal]:
        """检测流动性抓取"""
        try:
            # 流动性抓取特征：异常高成交量配合价格快速回撤
            avg_volume = recent_data['volume'].mean()
            max_volume = recent_data['volume'].max()
            
            # 成交量激增
            if max_volume > avg_volume * self.volume_spike_threshold:
                # 找到成交量最大的K线
                max_volume_idx = recent_data['volume'].idxmax()
                max_volume_bar = recent_data.loc[max_volume_idx]
                
                # 检查该K线是否有长上影或长下影（快速回撤特征）
                body_size = abs(max_volume_bar['close'] - max_volume_bar['open'])
                upper_shadow = max_volume_bar['high'] - max(max_volume_bar['open'], max_volume_bar['close'])
                lower_shadow = min(max_volume_bar['open'], max_volume_bar['close']) - max_volume_bar['low']
                
                total_range = max_volume_bar['high'] - max_volume_bar['low']
                
                # 上影线或下影线占总范围的40%以上
                if (upper_shadow / total_range > 0.4 or lower_shadow / total_range > 0.4):
                    hunt_price = max_volume_bar['high'] if upper_shadow > lower_shadow else max_volume_bar['low']
                    reversal_price = max_volume_bar['close']
                    
                    return self._create_hunting_signal(
                        HuntingType.LIQUIDITY_GRAB,
                        hunt_price,
                        reversal_price,
                        recent_data,
                        consolidation
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"检测流动性抓取失败: {str(e)}")
            return None
    
    def _calculate_volume_trend(self, data: pd.DataFrame) -> float:
        """计算成交量趋势"""
        try:
            if len(data) < 3:
                return 0.0
            
            volumes = data['volume'].values
            x = np.arange(len(volumes))
            
            # 线性回归计算趋势
            slope = np.polyfit(x, volumes, 1)[0]
            avg_volume = np.mean(volumes)
            
            # 标准化斜率
            return slope / avg_volume if avg_volume > 0 else 0.0
            
        except Exception:
            return 0.0
    
    def _create_hunting_signal(self,
                             hunting_type: HuntingType,
                             hunt_price: float,
                             reversal_price: float,
                             recent_data: pd.DataFrame,
                             consolidation: ConsolidationRange) -> HuntingSignal:
        """创建猎杀信号"""
        try:
            # 计算基本信息
            distance_hunted = abs(hunt_price - reversal_price)
            hunt_percentage = distance_hunted / hunt_price * 100
            
            # 计算成交量信息
            avg_volume = recent_data['volume'].mean()
            max_volume = recent_data['volume'].max()
            volume_spike = max_volume / avg_volume if avg_volume > 0 else 1.0
            
            # 评估强度
            if hunt_percentage >= 2.0 and volume_spike >= 3.0:
                strength = HuntingStrength.EXTREME
            elif hunt_percentage >= 1.0 and volume_spike >= 2.0:
                strength = HuntingStrength.STRONG
            elif hunt_percentage >= 0.5 or volume_spike >= 1.5:
                strength = HuntingStrength.MODERATE
            else:
                strength = HuntingStrength.WEAK
            
            # 创建目标区域
            target_zone = LiquidityZone(
                zone_type=LiquidityZoneType.STOP_LOSS_CLUSTER,
                price_level=hunt_price,
                price_range=(hunt_price * 0.999, hunt_price * 1.001),
                strength=70.0,
                touch_count=1,
                volume_concentration=max_volume,
                rejection_count=1,
                penetration_count=0,
                hunt_probability=0.8,
                target_distance=distance_hunted,
                expected_reaction="reversal",
                confidence=0.8,
                notes=f"{hunting_type.value}目标区域"
            )
            
            # 确认信号
            confirmation_signals = []
            if volume_spike >= 2.0:
                confirmation_signals.append("异常成交量")
            if hunt_percentage >= 1.0:
                confirmation_signals.append("显著价格移动")
            if len(confirmation_signals) >= 1:
                confirmation_signals.append("快速反转")
            
            # 操作建议
            if hunting_type in [HuntingType.WASHOUT, HuntingType.FAKE_BREAKOUT]:
                recommended_action = "继续持有，这是洗盘"
                hold_suggestion = True
                entry_opportunity = False
            elif hunting_type == HuntingType.STOP_HUNT:
                recommended_action = "考虑加仓或重新入场"
                hold_suggestion = True
                entry_opportunity = True
            else:
                recommended_action = "保持观察"
                hold_suggestion = False
                entry_opportunity = False
            
            # 质量评估
            signal_quality = min(
                hunt_percentage * 20 +
                volume_spike * 20 +
                len(confirmation_signals) * 20,
                100
            )
            
            confidence = min(
                signal_quality / 100 * 0.6 +
                (1 if volume_spike >= 2.0 else 0) * 0.3 +
                (1 if hunt_percentage >= 1.0 else 0) * 0.1,
                1.0
            )
            
            return HuntingSignal(
                hunting_type=hunting_type,
                strength=strength,
                target_zone=target_zone,
                hunt_price=hunt_price,
                reversal_price=reversal_price,
                distance_hunted=distance_hunted,
                volume_spike=volume_spike,
                volume_profile={'max': max_volume, 'avg': avg_volume},
                absorption_detected=volume_spike >= 3.0,
                hunt_start_time=datetime.now() - timedelta(minutes=5),
                hunt_duration=timedelta(minutes=5),
                reversal_time=datetime.now(),
                is_confirmed=len(confirmation_signals) >= 2,
                confirmation_signals=confirmation_signals,
                false_signal_risk=max(0, 0.5 - confidence),
                recommended_action=recommended_action,
                hold_suggestion=hold_suggestion,
                entry_opportunity=entry_opportunity,
                signal_quality=signal_quality,
                confidence=confidence
            )
            
        except Exception as e:
            self.logger.error(f"创建猎杀信号失败: {str(e)}")
            return None
    
    def _validate_hunting_signal(self,
                               hunting_signal: HuntingSignal,
                               price_data: pd.DataFrame,
                               cached_range: CachedRange) -> Optional[HuntingSignal]:
        """验证猎杀信号"""
        try:
            # 基本验证
            if hunting_signal.signal_quality < self.config.get('min_signal_quality', 50):
                return None
            
            if hunting_signal.false_signal_risk > self.config.get('max_false_signal_risk', 0.4):
                return None
            
            # 距离验证
            if hunting_signal.distance_hunted < cached_range.consolidation_range.range_size * 0.1:
                # 猎杀距离太小，可能不是真正的猎杀
                hunting_signal.confidence *= 0.7
                hunting_signal.signal_quality *= 0.8
            
            # 时间验证
            if hunting_signal.hunt_duration.total_seconds() > 3600:  # 超过1小时
                # 时间太长，可能不是快速猎杀
                hunting_signal.confidence *= 0.8
            
            # 成交量验证
            if hunting_signal.volume_spike < 1.5:
                # 成交量增长不明显
                hunting_signal.confidence *= 0.6
                hunting_signal.is_confirmed = False
            
            # 重新评估是否有效
            if not hunting_signal.is_valid_hunting_signal():
                return None
            
            return hunting_signal
            
        except Exception as e:
            self.logger.error(f"验证猎杀信号失败: {str(e)}")
            return None
    
    def _find_existing_zone(self, symbol: str, new_zone: LiquidityZone) -> Optional[LiquidityZone]:
        """查找现有的相似区域"""
        try:
            existing_zones = self.liquidity_zones.get(symbol, [])
            
            for zone in existing_zones:
                # 检查价格是否接近
                price_diff = abs(zone.price_level - new_zone.price_level) / zone.price_level
                if price_diff <= 0.01 and zone.zone_type == new_zone.zone_type:  # 1%范围内
                    return zone
            
            return None
            
        except Exception:
            return None
    
    def _update_existing_zone(self, existing_zone: LiquidityZone, new_zone: LiquidityZone):
        """更新现有区域"""
        try:
            # 更新触碰次数
            existing_zone.touch_count += 1
            existing_zone.last_touch = datetime.now()
            
            # 更新强度
            existing_zone.strength = min(existing_zone.strength + 10, 100)
            
            # 更新猎杀概率
            existing_zone.hunt_probability = min(existing_zone.touch_count / 10, 0.9)
            
            # 更新置信度
            existing_zone.confidence = min(existing_zone.confidence + 0.1, 1.0)
            
        except Exception as e:
            self.logger.error(f"更新现有区域失败: {str(e)}")
    
    def _cleanup_expired_zones(self, symbol: str):
        """清理过期区域"""
        try:
            if symbol not in self.liquidity_zones:
                return
            
            expiry_time = datetime.now() - timedelta(hours=self.config.get('zone_expiry_hours', 24 * 7))
            
            valid_zones = [
                zone for zone in self.liquidity_zones[symbol]
                if zone.created_at > expiry_time and zone.confidence > 0.3
            ]
            
            removed_count = len(self.liquidity_zones[symbol]) - len(valid_zones)
            self.liquidity_zones[symbol] = valid_zones
            
            if removed_count > 0:
                self.logger.debug(f"清理过期流动性区域: {symbol}, 移除{removed_count}个")
                
        except Exception as e:
            self.logger.error(f"清理过期区域失败: {str(e)}")
    
    def _update_detection_stats(self, hunting_signal: HuntingSignal):
        """更新检测统计"""
        try:
            self.detection_stats['total_hunts_detected'] += 1
            
            if hunting_signal.is_confirmed:
                self.detection_stats['confirmed_hunts'] += 1
            
            if hunting_signal.false_signal_risk > 0.5:
                self.detection_stats['false_signals'] += 1
            
            # 更新平均准确率
            total_signals = self.detection_stats['total_hunts_detected']
            if total_signals > 0:
                accuracy = (self.detection_stats['confirmed_hunts'] - 
                          self.detection_stats['false_signals']) / total_signals
                self.detection_stats['avg_hunt_accuracy'] = max(accuracy, 0.0)
                
        except Exception as e:
            self.logger.error(f"更新检测统计失败: {str(e)}")
    
    def get_liquidity_zones(self, symbol: str) -> List[LiquidityZone]:
        """获取指定币种的流动性区域"""
        return self.liquidity_zones.get(symbol, [])
    
    def get_recent_hunting_signals(self, hours: int = 24) -> List[HuntingSignal]:
        """获取最近的猎杀信号"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return [
                signal for signal in self.hunting_signals
                if signal.detected_at > cutoff_time
            ]
        except Exception:
            return []
    
    def get_detection_statistics(self) -> Dict:
        """获取检测统计信息"""
        return self.detection_stats.copy()
    
    def reset_detector(self):
        """重置检测器"""
        try:
            self.liquidity_zones.clear()
            self.hunting_signals.clear()
            self.detection_stats = {
                'total_hunts_detected': 0,
                'confirmed_hunts': 0,
                'false_signals': 0,
                'successful_predictions': 0,
                'avg_hunt_accuracy': 0.0,
                'zones_identified': 0
            }
            self.logger.info("流动性猎杀检测器已重置")
        except Exception as e:
            self.logger.error(f"重置检测器失败: {str(e)}")
    
    def export_zones_data(self, symbol: str = None) -> Dict:
        """导出区域数据"""
        try:
            if symbol:
                zones_data = {symbol: [zone.get_zone_info() for zone in self.get_liquidity_zones(symbol)]}
            else:
                zones_data = {}
                for sym, zones in self.liquidity_zones.items():
                    zones_data[sym] = [zone.get_zone_info() for zone in zones]
            
            return {
                'export_time': datetime.now().isoformat(),
                'zones_data': zones_data,
                'statistics': self.get_detection_statistics()
            }
            
        except Exception as e:
            self.logger.error(f"导出区域数据失败: {str(e)}")
            return {}