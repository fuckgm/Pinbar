"""
动态止损控制器 - DynamicStopController

实现基于盘整带的双重止损系统，解决传统止损过于敏感的问题。

核心功能：
1. 双重止损机制：盘整带止损（主）+ 传统止损（保底）
2. 动态调整止损位置
3. 抗洗盘智能判断
4. 多种止损策略组合
5. 风险梯度管理

止损优先级：
- 盘整带止损：价格回到盘整区间内触发（抗洗盘）
- 传统止损：固定比例/金额止损（风险控制）
- 时间止损：持仓时间过长触发（避免无谓等待）
- 紧急止损：极端情况下的强制止损（保护资金）

Author: Pinbar Strategy Team
Date: 2024-12
Version: 1.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import logging

from .consolidation_detector import ConsolidationRange
from .breakout_analyzer import BreakoutSignal, BreakoutDirection
from .range_cache_manager import CachedRange

# 设置日志
logger = logging.getLogger(__name__)


class StopLossType(Enum):
    """止损类型枚举"""
    RANGE_BOUNDARY = "range_boundary"    # 盘整带边界止损
    FIXED_PERCENTAGE = "fixed_percentage"  # 固定比例止损
    TRAILING = "trailing"                # 跟踪止损
    TIME_BASED = "time_based"           # 时间止损
    VOLATILITY_BASED = "volatility_based"  # 波动率止损
    EMERGENCY = "emergency"             # 紧急止损


class StopLossLevel(Enum):
    """止损等级枚举"""
    PRIMARY = "primary"       # 主要止损（盘整带）
    SECONDARY = "secondary"   # 次要止损（传统）
    EMERGENCY = "emergency"   # 紧急止损
    OVERRIDE = "override"     # 强制覆盖


class ExitReason(Enum):
    """退出原因枚举"""
    RANGE_RETURN = "range_return"           # 回到盘整区间
    FIXED_STOP_HIT = "fixed_stop_hit"       # 触发固定止损
    TRAILING_STOP_HIT = "trailing_stop_hit"  # 触发跟踪止损
    TIME_STOP_HIT = "time_stop_hit"         # 时间止损
    EMERGENCY_STOP = "emergency_stop"       # 紧急止损
    MANUAL_EXIT = "manual_exit"             # 手动退出
    PROFIT_TARGET = "profit_target"         # 止盈目标


@dataclass
class StopLossLevel:
    """止损水平数据结构"""
    level_type: StopLossType    # 止损类型
    price: float               # 止损价格
    distance: float            # 距离当前价格
    distance_pct: float        # 距离百分比
    priority: int              # 优先级 (1-5, 1最高)
    is_active: bool           # 是否激活
    created_at: datetime      # 创建时间
    description: str          # 描述


@dataclass
class ExitSignal:
    """退出信号数据结构"""
    should_exit: bool         # 是否应该退出
    exit_reason: ExitReason   # 退出原因
    triggered_stop: Optional[StopLossLevel]  # 触发的止损
    exit_price: float         # 建议退出价格
    urgency: int             # 紧急程度 (1-5)
    confidence: float        # 置信度 (0-1)
    additional_info: Dict    # 额外信息
    timestamp: datetime      # 时间戳


class DynamicStopController:
    """
    动态止损控制器
    
    管理多层止损机制，提供智能退出决策
    """
    
    def __init__(self, config: Dict = None):
        """
        初始化动态止损控制器
        
        Args:
            config: 配置参数
        """
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 止损参数
        self.use_range_stop = self.config.get('use_range_stop', True)
        self.use_traditional_stop = self.config.get('use_traditional_stop', True)
        self.range_stop_buffer = self.config.get('range_stop_buffer', 0.001)
        self.max_stop_loss = self.config.get('max_stop_loss', 0.05)
        self.time_stop_hours = self.config.get('time_stop_hours', 24 * 7)  # 7天
        
        # 活跃止损追踪
        self.active_stops: Dict[str, List[StopLossLevel]] = {}  # cache_id -> stops
        self.stop_history: List[ExitSignal] = []
        
        # 统计信息
        self.stop_stats = {
            'total_stops_created': 0,
            'range_stops_triggered': 0,
            'fixed_stops_triggered': 0,
            'time_stops_triggered': 0,
            'emergency_stops_triggered': 0,
            'false_triggers': 0,
            'avg_holding_time': 0.0
        }
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            # 基本止损设置
            'use_range_stop': True,
            'use_traditional_stop': True,
            'range_stop_buffer': 0.001,      # 0.1%缓冲
            'max_stop_loss': 0.05,           # 最大5%止损
            
            # 时间止损
            'time_stop_hours': 24 * 7,       # 7天时间止损
            'max_holding_days': 30,          # 最大持仓天数
            
            # 跟踪止损
            'trailing_stop_distance': 0.02,  # 2%跟踪距离
            'trailing_activation_profit': 0.01,  # 1%利润后激活跟踪
            
            # 波动率止损
            'volatility_multiplier': 2.0,    # 波动率倍数
            'volatility_period': 20,         # 波动率计算周期
            
            # 紧急止损
            'emergency_stop_threshold': 0.08,  # 8%紧急止损
            'max_daily_loss': 0.03,           # 单日最大亏损3%
            
            # 优先级权重
            'priority_weights': {
                'range_boundary': 0.4,
                'fixed_percentage': 0.3,
                'trailing': 0.2,
                'time_based': 0.1
            }
        }
    
    def calculate_stop_levels(self,
                            cached_range: CachedRange,
                            breakout_signal: BreakoutSignal,
                            current_price: float,
                            entry_price: Optional[float] = None) -> Dict[str, StopLossLevel]:
        """
        计算止损水平
        
        Args:
            cached_range: 缓存的区间
            breakout_signal: 突破信号
            current_price: 当前价格
            entry_price: 入场价格
            
        Returns:
            Dict[str, StopLossLevel]: 止损水平字典
        """
        try:
            if entry_price is None:
                entry_price = breakout_signal.breakout_price
            
            stop_levels = {}
            
            # 1. 盘整带边界止损（主要止损）
            if self.use_range_stop:
                range_stop = self._calculate_range_boundary_stop(
                    cached_range, breakout_signal, current_price, entry_price
                )
                if range_stop:
                    stop_levels['range_boundary'] = range_stop
            
            # 2. 固定比例止损（保底止损）
            if self.use_traditional_stop:
                fixed_stop = self._calculate_fixed_percentage_stop(
                    breakout_signal, current_price, entry_price
                )
                if fixed_stop:
                    stop_levels['fixed_percentage'] = fixed_stop
            
            # 3. 跟踪止损
            trailing_stop = self._calculate_trailing_stop(
                breakout_signal, current_price, entry_price
            )
            if trailing_stop:
                stop_levels['trailing'] = trailing_stop
            
            # 4. 时间止损
            time_stop = self._calculate_time_based_stop(
                cached_range, current_price
            )
            if time_stop:
                stop_levels['time_based'] = time_stop
            
            # 5. 波动率止损
            volatility_stop = self._calculate_volatility_based_stop(
                breakout_signal, current_price, entry_price
            )
            if volatility_stop:
                stop_levels['volatility_based'] = volatility_stop
            
            # 6. 紧急止损
            emergency_stop = self._calculate_emergency_stop(
                current_price, entry_price
            )
            if emergency_stop:
                stop_levels['emergency'] = emergency_stop
            
            # 缓存止损水平
            self.active_stops[cached_range.cache_id] = list(stop_levels.values())
            self.stop_stats['total_stops_created'] += len(stop_levels)
            
            self.logger.info(f"计算止损水平完成，共{len(stop_levels)}个止损点")
            return stop_levels
            
        except Exception as e:
            self.logger.error(f"计算止损水平失败: {str(e)}")
            return {}
    
    def _calculate_range_boundary_stop(self,
                                     cached_range: CachedRange,
                                     breakout_signal: BreakoutSignal,
                                     current_price: float,
                                     entry_price: float) -> Optional[StopLossLevel]:
        """计算盘整带边界止损"""
        try:
            consolidation = cached_range.consolidation_range
            
            # 根据突破方向确定止损边界
            if breakout_signal.direction == BreakoutDirection.UP:
                # 向上突破，止损设在下边界
                stop_price = consolidation.lower_boundary * (1 - self.range_stop_buffer)
                boundary_name = "下边界"
            else:
                # 向下突破，止损设在上边界
                stop_price = consolidation.upper_boundary * (1 + self.range_stop_buffer)
                boundary_name = "上边界"
            
            distance = abs(current_price - stop_price)
            distance_pct = (distance / current_price) * 100
            
            # 检查止损距离是否合理
            if distance_pct > self.max_stop_loss * 100:
                self.logger.warning(f"盘整带止损距离过大: {distance_pct:.2f}%，使用最大止损")
                if breakout_signal.direction == BreakoutDirection.UP:
                    stop_price = current_price * (1 - self.max_stop_loss)
                else:
                    stop_price = current_price * (1 + self.max_stop_loss)
                distance = abs(current_price - stop_price)
                distance_pct = (distance / current_price) * 100
            
            return StopLossLevel(
                level_type=StopLossType.RANGE_BOUNDARY,
                price=stop_price,
                distance=distance,
                distance_pct=distance_pct,
                priority=1,  # 最高优先级
                is_active=True,
                created_at=datetime.now(),
                description=f"盘整带{boundary_name}止损，缓冲{self.range_stop_buffer*100:.1f}%"
            )
            
        except Exception as e:
            self.logger.error(f"计算盘整带止损失败: {str(e)}")
            return None
    
    def _calculate_fixed_percentage_stop(self,
                                       breakout_signal: BreakoutSignal,
                                       current_price: float,
                                       entry_price: float) -> Optional[StopLossLevel]:
        """计算固定比例止损"""
        try:
            # 基于风险等级调整止损比例
            base_stop_pct = self.max_stop_loss
            
            # 根据突破质量调整
            quality_factor = breakout_signal.quality_score / 100
            adjusted_stop_pct = base_stop_pct * (1.5 - quality_factor * 0.5)  # 质量越高，止损越宽松
            
            # 根据突破方向设置止损
            if breakout_signal.direction == BreakoutDirection.UP:
                stop_price = entry_price * (1 - adjusted_stop_pct)
            else:
                stop_price = entry_price * (1 + adjusted_stop_pct)
            
            distance = abs(current_price - stop_price)
            distance_pct = (distance / current_price) * 100
            
            return StopLossLevel(
                level_type=StopLossType.FIXED_PERCENTAGE,
                price=stop_price,
                distance=distance,
                distance_pct=distance_pct,
                priority=2,  # 次高优先级
                is_active=True,
                created_at=datetime.now(),
                description=f"固定比例止损 {adjusted_stop_pct*100:.1f}%"
            )
            
        except Exception as e:
            self.logger.error(f"计算固定比例止损失败: {str(e)}")
            return None
    
    def _calculate_trailing_stop(self,
                               breakout_signal: BreakoutSignal,
                               current_price: float,
                               entry_price: float) -> Optional[StopLossLevel]:
        """计算跟踪止损"""
        try:
            # 检查是否已达到激活利润
            if breakout_signal.direction == BreakoutDirection.UP:
                profit_pct = (current_price - entry_price) / entry_price
                if profit_pct >= self.config.get('trailing_activation_profit', 0.01):
                    stop_price = current_price * (1 - self.config.get('trailing_stop_distance', 0.02))
                else:
                    return None  # 利润不足，不激活跟踪止损
            else:
                profit_pct = (entry_price - current_price) / entry_price
                if profit_pct >= self.config.get('trailing_activation_profit', 0.01):
                    stop_price = current_price * (1 + self.config.get('trailing_stop_distance', 0.02))
                else:
                    return None
            
            distance = abs(current_price - stop_price)
            distance_pct = (distance / current_price) * 100
            
            return StopLossLevel(
                level_type=StopLossType.TRAILING,
                price=stop_price,
                distance=distance,
                distance_pct=distance_pct,
                priority=3,
                is_active=profit_pct >= self.config.get('trailing_activation_profit', 0.01),
                created_at=datetime.now(),
                description=f"跟踪止损，距离{self.config.get('trailing_stop_distance', 0.02)*100:.1f}%"
            )
            
        except Exception as e:
            self.logger.error(f"计算跟踪止损失败: {str(e)}")
            return None
    
    def _calculate_time_based_stop(self,
                                 cached_range: CachedRange,
                                 current_price: float) -> Optional[StopLossLevel]:
        """计算时间止损"""
        try:
            # 检查持仓时间
            holding_time = datetime.now() - cached_range.cached_at
            max_holding = timedelta(hours=self.time_stop_hours)
            
            if holding_time >= max_holding:
                # 时间止损触发，使用当前价格
                return StopLossLevel(
                    level_type=StopLossType.TIME_BASED,
                    price=current_price,
                    distance=0,
                    distance_pct=0,
                    priority=4,
                    is_active=True,
                    created_at=datetime.now(),
                    description=f"时间止损，持仓超过{self.time_stop_hours}小时"
                )
            else:
                # 时间止损待触发
                remaining_time = max_holding - holding_time
                return StopLossLevel(
                    level_type=StopLossType.TIME_BASED,
                    price=current_price,
                    distance=0,
                    distance_pct=0,
                    priority=4,
                    is_active=False,
                    created_at=datetime.now(),
                    description=f"时间止损，剩余{remaining_time.total_seconds()/3600:.1f}小时"
                )
            
        except Exception as e:
            self.logger.error(f"计算时间止损失败: {str(e)}")
            return None
    
    def _calculate_volatility_based_stop(self,
                                       breakout_signal: BreakoutSignal,
                                       current_price: float,
                                       entry_price: float) -> Optional[StopLossLevel]:
        """计算波动率止损"""
        try:
            # 这里需要价格数据来计算波动率，简化处理
            # 实际项目中应该传入价格数据
            
            # 使用默认波动率估算
            estimated_volatility = 0.02  # 假设2%日波动率
            volatility_multiplier = self.config.get('volatility_multiplier', 2.0)
            
            stop_distance = estimated_volatility * volatility_multiplier
            
            if breakout_signal.direction == BreakoutDirection.UP:
                stop_price = current_price * (1 - stop_distance)
            else:
                stop_price = current_price * (1 + stop_distance)
            
            distance = abs(current_price - stop_price)
            distance_pct = stop_distance * 100
            
            return StopLossLevel(
                level_type=StopLossType.VOLATILITY_BASED,
                price=stop_price,
                distance=distance,
                distance_pct=distance_pct,
                priority=3,
                is_active=True,
                created_at=datetime.now(),
                description=f"波动率止损，{volatility_multiplier}倍ATR"
            )
            
        except Exception as e:
            self.logger.error(f"计算波动率止损失败: {str(e)}")
            return None
    
    def _calculate_emergency_stop(self,
                                current_price: float,
                                entry_price: float) -> Optional[StopLossLevel]:
        """计算紧急止损"""
        try:
            emergency_threshold = self.config.get('emergency_stop_threshold', 0.08)
            
            # 计算当前亏损
            loss_pct = abs(current_price - entry_price) / entry_price
            
            if loss_pct >= emergency_threshold:
                return StopLossLevel(
                    level_type=StopLossType.EMERGENCY,
                    price=current_price,
                    distance=0,
                    distance_pct=0,
                    priority=0,  # 最高优先级
                    is_active=True,
                    created_at=datetime.now(),
                    description=f"紧急止损，亏损{loss_pct*100:.1f}%"
                )
            else:
                # 设置紧急止损线
                if current_price > entry_price:
                    stop_price = entry_price * (1 - emergency_threshold)
                else:
                    stop_price = entry_price * (1 + emergency_threshold)
                
                distance = abs(current_price - stop_price)
                distance_pct = (distance / current_price) * 100
                
                return StopLossLevel(
                    level_type=StopLossType.EMERGENCY,
                    price=stop_price,
                    distance=distance,
                    distance_pct=distance_pct,
                    priority=0,
                    is_active=False,
                    created_at=datetime.now(),
                    description=f"紧急止损线，{emergency_threshold*100:.1f}%"
                )
            
        except Exception as e:
            self.logger.error(f"计算紧急止损失败: {str(e)}")
            return None
    
    def should_exit(self,
                   cached_range: CachedRange,
                   current_price: float,
                   current_time: Optional[datetime] = None) -> ExitSignal:
        """
        判断是否应该退出
        
        Args:
            cached_range: 缓存区间
            current_price: 当前价格
            current_time: 当前时间
            
        Returns:
            ExitSignal: 退出信号
        """
        try:
            if current_time is None:
                current_time = datetime.now()
            
            # 获取止损水平
            stop_levels = self.active_stops.get(cached_range.cache_id, [])
            if not stop_levels:
                # 如果没有缓存的止损，重新计算
                breakout_signal = cached_range.breakout_signal
                stop_levels_dict = self.calculate_stop_levels(
                    cached_range, breakout_signal, current_price
                )
                stop_levels = list(stop_levels_dict.values())
            
            # 按优先级排序
            stop_levels.sort(key=lambda x: x.priority)
            
            # 检查各种止损条件
            exit_signals = []
            
            # 1. 检查盘整带止损（最重要）
            range_exit = self._check_range_boundary_exit(cached_range, current_price)
            if range_exit:
                exit_signals.append(range_exit)
            
            # 2. 检查其他止损
            for stop_level in stop_levels:
                if not stop_level.is_active:
                    continue
                
                exit_signal = self._check_stop_level_triggered(
                    stop_level, current_price, cached_range
                )
                if exit_signal and exit_signal.should_exit:
                    exit_signals.append(exit_signal)
            
            # 3. 检查时间止损
            time_exit = self._check_time_based_exit(cached_range, current_time)
            if time_exit:
                exit_signals.append(time_exit)
            
            # 选择最高优先级的退出信号
            if exit_signals:
                # 按紧急程度和优先级排序
                exit_signals.sort(key=lambda x: (x.urgency, -x.confidence), reverse=True)
                final_exit = exit_signals[0]
                
                # 记录退出信号
                self.stop_history.append(final_exit)
                self._update_stop_stats(final_exit)
                
                return final_exit
            else:
                # 无退出信号
                return ExitSignal(
                    should_exit=False,
                    exit_reason=ExitReason.RANGE_RETURN,  # 默认原因
                    triggered_stop=None,
                    exit_price=current_price,
                    urgency=0,
                    confidence=0.0,
                    additional_info={'active_stops': len(stop_levels)},
                    timestamp=current_time
                )
                
        except Exception as e:
            self.logger.error(f"退出判断失败: {str(e)}")
            # 出错时保守退出
            return ExitSignal(
                should_exit=True,
                exit_reason=ExitReason.EMERGENCY_STOP,
                triggered_stop=None,
                exit_price=current_price,
                urgency=5,
                confidence=1.0,
                additional_info={'error': str(e)},
                timestamp=current_time or datetime.now()
            )
    
    def _check_range_boundary_exit(self,
                                 cached_range: CachedRange,
                                 current_price: float) -> Optional[ExitSignal]:
        """检查盘整带边界退出"""
        try:
            if not self.use_range_stop:
                return None
            
            consolidation = cached_range.consolidation_range
            breakout_signal = cached_range.breakout_signal
            
            # 检查价格是否回到盘整区间内
            buffer = consolidation.range_size * self.range_stop_buffer
            
            if breakout_signal.direction == BreakoutDirection.UP:
                # 向上突破后，检查是否跌破下边界
                trigger_price = consolidation.lower_boundary + buffer
                if current_price <= trigger_price:
                    return ExitSignal(
                        should_exit=True,
                        exit_reason=ExitReason.RANGE_RETURN,
                        triggered_stop=None,
                        exit_price=current_price,
                        urgency=3,
                        confidence=0.8,
                        additional_info={
                            'boundary_type': 'lower',
                            'boundary_price': consolidation.lower_boundary,
                            'trigger_price': trigger_price,
                            'penetration': trigger_price - current_price
                        },
                        timestamp=datetime.now()
                    )
            else:
                # 向下突破后，检查是否升破上边界
                trigger_price = consolidation.upper_boundary - buffer
                if current_price >= trigger_price:
                    return ExitSignal(
                        should_exit=True,
                        exit_reason=ExitReason.RANGE_RETURN,
                        triggered_stop=None,
                        exit_price=current_price,
                        urgency=3,
                        confidence=0.8,
                        additional_info={
                            'boundary_type': 'upper',
                            'boundary_price': consolidation.upper_boundary,
                            'trigger_price': trigger_price,
                            'penetration': current_price - trigger_price
                        },
                        timestamp=datetime.now()
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"检查盘整带退出失败: {str(e)}")
            return None
    
    def _check_stop_level_triggered(self,
                                  stop_level: StopLossLevel,
                                  current_price: float,
                                  cached_range: CachedRange) -> Optional[ExitSignal]:
        """检查止损水平是否触发"""
        try:
            breakout_signal = cached_range.breakout_signal
            triggered = False
            
            # 根据突破方向和止损类型判断触发条件
            if breakout_signal.direction == BreakoutDirection.UP:
                # 向上突破，检查下行止损
                triggered = current_price <= stop_level.price
            else:
                # 向下突破，检查上行止损
                triggered = current_price >= stop_level.price
            
            if triggered:
                # 确定退出原因
                reason_map = {
                    StopLossType.RANGE_BOUNDARY: ExitReason.RANGE_RETURN,
                    StopLossType.FIXED_PERCENTAGE: ExitReason.FIXED_STOP_HIT,
                    StopLossType.TRAILING: ExitReason.TRAILING_STOP_HIT,
                    StopLossType.TIME_BASED: ExitReason.TIME_STOP_HIT,
                    StopLossType.EMERGENCY: ExitReason.EMERGENCY_STOP,
                    StopLossType.VOLATILITY_BASED: ExitReason.FIXED_STOP_HIT
                }
                
                exit_reason = reason_map.get(stop_level.level_type, ExitReason.FIXED_STOP_HIT)
                
                # 计算紧急程度
                urgency = 5 - stop_level.priority  # 优先级越高，紧急程度越高
                if stop_level.level_type == StopLossType.EMERGENCY:
                    urgency = 5
                
                return ExitSignal(
                    should_exit=True,
                    exit_reason=exit_reason,
                    triggered_stop=stop_level,
                    exit_price=current_price,
                    urgency=urgency,
                    confidence=0.9,
                    additional_info={
                        'stop_type': stop_level.level_type.value,
                        'stop_price': stop_level.price,
                        'penetration': abs(current_price - stop_level.price),
                        'stop_description': stop_level.description
                    },
                    timestamp=datetime.now()
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"检查止损触发失败: {str(e)}")
            return None
    
    def _check_time_based_exit(self,
                             cached_range: CachedRange,
                             current_time: datetime) -> Optional[ExitSignal]:
        """检查时间止损"""
        try:
            holding_time = current_time - cached_range.cached_at
            max_holding = timedelta(hours=self.time_stop_hours)
            
            if holding_time >= max_holding:
                return ExitSignal(
                    should_exit=True,
                    exit_reason=ExitReason.TIME_STOP_HIT,
                    triggered_stop=None,
                    exit_price=0,  # 需要外部提供当前价格
                    urgency=2,
                    confidence=0.7,
                    additional_info={
                        'holding_hours': holding_time.total_seconds() / 3600,
                        'max_holding_hours': self.time_stop_hours,
                        'overtime_hours': (holding_time - max_holding).total_seconds() / 3600
                    },
                    timestamp=current_time
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"检查时间止损失败: {str(e)}")
            return None
    
    def _update_stop_stats(self, exit_signal: ExitSignal):
        """更新止损统计"""
        try:
            # 根据退出原因更新统计
            if exit_signal.exit_reason == ExitReason.RANGE_RETURN:
                self.stop_stats['range_stops_triggered'] += 1
            elif exit_signal.exit_reason == ExitReason.FIXED_STOP_HIT:
                self.stop_stats['fixed_stops_triggered'] += 1
            elif exit_signal.exit_reason == ExitReason.TIME_STOP_HIT:
                self.stop_stats['time_stops_triggered'] += 1
            elif exit_signal.exit_reason == ExitReason.EMERGENCY_STOP:
                self.stop_stats['emergency_stops_triggered'] += 1
            
            # 检查是否为误触发（可以通过后续价格走势验证）
            if exit_signal.confidence < 0.5:
                self.stop_stats['false_triggers'] += 1
                
        except Exception as e:
            self.logger.error(f"更新止损统计失败: {str(e)}")
    
    def update_trailing_stop(self,
                           cache_id: str,
                           current_price: float,
                           breakout_direction: BreakoutDirection):
        """更新跟踪止损"""
        try:
            stop_levels = self.active_stops.get(cache_id, [])
            
            for stop_level in stop_levels:
                if stop_level.level_type == StopLossType.TRAILING and stop_level.is_active:
                    trailing_distance = self.config.get('trailing_stop_distance', 0.02)
                    
                    # 计算新的跟踪止损价格
                    if breakout_direction == BreakoutDirection.UP:
                        new_stop_price = current_price * (1 - trailing_distance)
                        # 只向上调整止损（更有利的方向）
                        if new_stop_price > stop_level.price:
                            stop_level.price = new_stop_price
                            stop_level.distance = current_price - new_stop_price
                            stop_level.distance_pct = (stop_level.distance / current_price) * 100
                            self.logger.debug(f"跟踪止损上调至: {new_stop_price:.6f}")
                    else:
                        new_stop_price = current_price * (1 + trailing_distance)
                        # 只向下调整止损（更有利的方向）
                        if new_stop_price < stop_level.price:
                            stop_level.price = new_stop_price
                            stop_level.distance = new_stop_price - current_price
                            stop_level.distance_pct = (stop_level.distance / current_price) * 100
                            self.logger.debug(f"跟踪止损下调至: {new_stop_price:.6f}")
                    
                    break
                    
        except Exception as e:
            self.logger.error(f"更新跟踪止损失败: {str(e)}")
    
    def get_stop_summary(self, cache_id: str) -> Dict:
        """获取止损摘要"""
        try:
            stop_levels = self.active_stops.get(cache_id, [])
            
            summary = {
                'total_stops': len(stop_levels),
                'active_stops': sum(1 for stop in stop_levels if stop.is_active),
                'stops_by_type': {},
                'nearest_stop': None,
                'most_critical_stop': None
            }
            
            if not stop_levels:
                return summary
            
            # 按类型统计
            for stop in stop_levels:
                stop_type = stop.level_type.value
                if stop_type not in summary['stops_by_type']:
                    summary['stops_by_type'][stop_type] = {
                        'count': 0,
                        'active': 0,
                        'prices': []
                    }
                
                summary['stops_by_type'][stop_type]['count'] += 1
                summary['stops_by_type'][stop_type]['prices'].append(stop.price)
                
                if stop.is_active:
                    summary['stops_by_type'][stop_type]['active'] += 1
            
            # 找到最近的止损
            active_stops = [stop for stop in stop_levels if stop.is_active]
            if active_stops:
                nearest_stop = min(active_stops, key=lambda x: x.distance)
                summary['nearest_stop'] = {
                    'type': nearest_stop.level_type.value,
                    'price': nearest_stop.price,
                    'distance': nearest_stop.distance,
                    'distance_pct': nearest_stop.distance_pct
                }
                
                # 找到最关键的止损（优先级最高）
                most_critical = min(active_stops, key=lambda x: x.priority)
                summary['most_critical_stop'] = {
                    'type': most_critical.level_type.value,
                    'price': most_critical.price,
                    'priority': most_critical.priority,
                    'description': most_critical.description
                }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"获取止损摘要失败: {str(e)}")
            return {}
    
    def get_controller_stats(self) -> Dict:
        """获取控制器统计信息"""
        try:
            stats = self.stop_stats.copy()
            
            # 计算总触发次数
            total_triggers = (
                stats['range_stops_triggered'] +
                stats['fixed_stops_triggered'] +
                stats['time_stops_triggered'] +
                stats['emergency_stops_triggered']
            )
            
            # 计算各类型触发比例
            if total_triggers > 0:
                stats['range_stop_ratio'] = stats['range_stops_triggered'] / total_triggers
                stats['fixed_stop_ratio'] = stats['fixed_stops_triggered'] / total_triggers
                stats['time_stop_ratio'] = stats['time_stops_triggered'] / total_triggers
                stats['emergency_stop_ratio'] = stats['emergency_stops_triggered'] / total_triggers
                stats['false_trigger_ratio'] = stats['false_triggers'] / total_triggers
            else:
                stats.update({
                    'range_stop_ratio': 0.0,
                    'fixed_stop_ratio': 0.0,
                    'time_stop_ratio': 0.0,
                    'emergency_stop_ratio': 0.0,
                    'false_trigger_ratio': 0.0
                })
            
            # 添加当前状态
            stats['active_positions'] = len(self.active_stops)
            stats['total_exit_signals'] = len(self.stop_history)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取控制器统计失败: {str(e)}")
            return {}
    
    def reset_stats(self):
        """重置统计信息"""
        self.stop_stats = {
            'total_stops_created': 0,
            'range_stops_triggered': 0,
            'fixed_stops_triggered': 0,
            'time_stops_triggered': 0,
            'emergency_stops_triggered': 0,
            'false_triggers': 0,
            'avg_holding_time': 0.0
        }
        self.stop_history.clear()
        self.logger.info("止损控制器统计已重置")
    
    def cleanup_inactive_stops(self):
        """清理非活跃的止损"""
        try:
            cleaned_count = 0
            cache_ids_to_remove = []
            
            for cache_id, stop_levels in self.active_stops.items():
                # 过滤掉非活跃的止损
                active_stops = [stop for stop in stop_levels if stop.is_active]
                
                if not active_stops:
                    cache_ids_to_remove.append(cache_id)
                    cleaned_count += 1
                else:
                    self.active_stops[cache_id] = active_stops
            
            # 移除空的缓存条目
            for cache_id in cache_ids_to_remove:
                del self.active_stops[cache_id]
            
            if cleaned_count > 0:
                self.logger.info(f"清理非活跃止损: {cleaned_count} 个")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"清理非活跃止损失败: {str(e)}")
            return 0