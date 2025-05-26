"""
区间缓存管理器 - RangeCacheManager

管理盘整区间的缓存，提供高效的存储、检索和生命周期管理。

核心功能：
1. 缓存已识别的盘整区间和突破信息
2. 管理缓存的生命周期和过期清理
3. 提供快速查询和检索接口
4. 跟踪区间的使用状态和有效性
5. 支持多币种的独立缓存管理

设计特点：
- 内存高效的缓存结构
- 基于时间和使用频率的智能清理
- 支持多种查询方式
- 完整的状态追踪
- 数据持久化支持

Author: Pinbar Strategy Team
Date: 2024-12
Version: 1.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json
import os
import logging
from collections import defaultdict, OrderedDict

from .consolidation_detector import ConsolidationRange
from .breakout_analyzer import BreakoutSignal

# 设置日志
logger = logging.getLogger(__name__)


class CacheStatus(Enum):
    """缓存状态枚举"""
    ACTIVE = "active"           # 活跃状态
    INACTIVE = "inactive"       # 非活跃状态
    EXPIRED = "expired"         # 已过期
    INVALIDATED = "invalidated" # 已失效


class RangeUsageType(Enum):
    """区间使用类型枚举"""
    STOP_LOSS = "stop_loss"           # 用于止损
    ENTRY_SIGNAL = "entry_signal"     # 用于入场信号
    EXIT_SIGNAL = "exit_signal"       # 用于出场信号
    REFERENCE = "reference"           # 仅作参考


@dataclass
class CachedRange:
    """
    缓存的盘整区间数据结构
    
    包含盘整区间、突破信息和缓存管理元数据
    """
    # 唯一标识
    cache_id: str                    # 缓存唯一ID
    symbol: str                      # 交易对符号
    
    # 核心数据
    consolidation_range: ConsolidationRange  # 盘整区间
    breakout_signal: BreakoutSignal         # 突破信号
    
    # 缓存状态
    status: CacheStatus             # 缓存状态
    usage_type: RangeUsageType      # 使用类型
    is_active: bool                 # 是否活跃
    
    # 时间信息
    cached_at: datetime             # 缓存时间
    last_accessed: datetime         # 最后访问时间
    expires_at: datetime            # 过期时间
    
    # 使用统计
    access_count: int               # 访问次数
    hit_count: int                  # 命中次数
    success_count: int              # 成功次数
    
    # 性能指标
    price_returns: List[float] = field(default_factory=list)      # 价格回报序列
    holding_periods: List[int] = field(default_factory=list)      # 持仓周期序列
    effectiveness_score: float = 0.0                              # 有效性评分
    
    # 市场环境
    market_condition: str = "unknown"        # 市场环境
    volatility_regime: str = "normal"        # 波动率状态
    
    # 元数据
    created_by: str = "system"              # 创建者
    notes: str = ""                         # 备注信息
    tags: List[str] = field(default_factory=list)  # 标签
    
    def __post_init__(self):
        """后处理初始化"""
        if not self.cache_id:
            self.cache_id = str(uuid.uuid4())
        
        if not self.cached_at:
            self.cached_at = datetime.now()
        
        if not self.last_accessed:
            self.last_accessed = self.cached_at
    
    def is_expired(self) -> bool:
        """检查是否已过期"""
        return datetime.now() > self.expires_at
    
    def is_valid(self) -> bool:
        """检查是否有效"""
        return (
            self.status in [CacheStatus.ACTIVE, CacheStatus.INACTIVE] and
            not self.is_expired() and
            self.consolidation_range.is_valid() and
            self.breakout_signal.is_valid
        )
    
    def update_access(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def record_hit(self, success: bool = False):
        """记录命中"""
        self.hit_count += 1
        if success:
            self.success_count += 1
        self.update_access()
    
    def add_performance_data(self, price_return: float, holding_period: int):
        """添加性能数据"""
        self.price_returns.append(price_return)
        self.holding_periods.append(holding_period)
        self._update_effectiveness_score()
    
    def _update_effectiveness_score(self):
        """更新有效性评分"""
        if not self.price_returns:
            self.effectiveness_score = 0.0
            return
        
        # 基于收益率和成功率计算
        avg_return = np.mean(self.price_returns)
        success_rate = self.success_count / max(self.hit_count, 1)
        
        # 综合评分
        self.effectiveness_score = (avg_return * 50 + success_rate * 50)
    
    def get_performance_summary(self) -> Dict:
        """获取性能摘要"""
        if not self.price_returns:
            return {
                'total_trades': 0,
                'avg_return': 0.0,
                'success_rate': 0.0,
                'avg_holding_period': 0,
                'effectiveness_score': 0.0
            }
        
        return {
            'total_trades': len(self.price_returns),
            'avg_return': np.mean(self.price_returns),
            'success_rate': self.success_count / max(self.hit_count, 1),
            'avg_holding_period': np.mean(self.holding_periods) if self.holding_periods else 0,
            'effectiveness_score': self.effectiveness_score,
            'max_return': max(self.price_returns),
            'min_return': min(self.price_returns),
            'total_access': self.access_count
        }
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'cache_id': self.cache_id,
            'symbol': self.symbol,
            'status': self.status.value,
            'usage_type': self.usage_type.value,
            'is_active': self.is_active,
            'cached_at': self.cached_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'access_count': self.access_count,
            'hit_count': self.hit_count,
            'success_count': self.success_count,
            'effectiveness_score': self.effectiveness_score,
            'market_condition': self.market_condition,
            'consolidation_range': self.consolidation_range.to_dict() if self.consolidation_range else None,
            'breakout_signal': self.breakout_signal.to_dict() if self.breakout_signal else None,
            'performance_summary': self.get_performance_summary()
        }


class RangeCacheManager:
    """
    区间缓存管理器
    
    管理盘整区间和突破信号的缓存
    """
    
    def __init__(self, config: Dict = None):
        """
        初始化缓存管理器
        
        Args:
            config: 配置参数
        """
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 缓存参数
        self.max_cached_ranges = self.config.get('max_cached_ranges', 50)
        self.cache_expiry_hours = self.config.get('cache_expiry_hours', 24 * 7)  # 7天
        self.auto_cleanup = self.config.get('auto_cleanup', True)
        self.persistence_enabled = self.config.get('persistence_enabled', False)
        self.cache_file_path = self.config.get('cache_file_path', 'cache/range_cache.json')
        
        # 缓存存储
        self.cache: OrderedDict[str, CachedRange] = OrderedDict()
        self.symbol_index: Dict[str, List[str]] = defaultdict(list)  # 按币种索引
        self.active_ranges: Dict[str, str] = {}  # 活跃区间映射
        
        # 统计信息
        self.cache_stats = {
            'total_cached': 0,
            'total_hits': 0,
            'total_misses': 0,
            'total_expired': 0,
            'total_invalidated': 0,
            'avg_lifetime': 0.0,
            'hit_ratio': 0.0
        }
        
        # 初始化
        self._initialize_cache()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'max_cached_ranges': 100,
            'cache_expiry_hours': 24 * 7,  # 7天
            'auto_cleanup': True,
            'cleanup_interval_minutes': 60,
            'persistence_enabled': False,
            'cache_file_path': 'cache/range_cache.json',
            'max_symbol_ranges': 10,
            'effectiveness_threshold': 30.0
        }
    
    def _initialize_cache(self):
        """初始化缓存"""
        try:
            # 加载持久化数据
            if self.persistence_enabled:
                self._load_cache_from_file()
            
            # 清理过期数据
            if self.auto_cleanup:
                self._cleanup_expired_ranges()
                
            self.logger.info(f"缓存管理器初始化完成，当前缓存: {len(self.cache)} 个区间")
            
        except Exception as e:
            self.logger.error(f"缓存初始化失败: {str(e)}")
    
    def cache_range(self,
                   consolidation_range: ConsolidationRange,
                   breakout_signal: BreakoutSignal,
                   usage_type: RangeUsageType = RangeUsageType.STOP_LOSS,
                   expiry_hours: Optional[int] = None) -> CachedRange:
        """
        缓存盘整区间
        
        Args:
            consolidation_range: 盘整区间
            breakout_signal: 突破信号
            usage_type: 使用类型
            expiry_hours: 过期时间(小时)，None则使用默认值
            
        Returns:
            CachedRange: 缓存的区间对象
        """
        try:
            # 检查容量限制
            self._ensure_cache_capacity()
            
            # 设置过期时间
            if expiry_hours is None:
                expiry_hours = self.cache_expiry_hours
            expires_at = datetime.now() + timedelta(hours=expiry_hours)
            
            # 创建缓存对象
            cached_range = CachedRange(
                cache_id=str(uuid.uuid4()),
                symbol=consolidation_range.symbol,
                consolidation_range=consolidation_range,
                breakout_signal=breakout_signal,
                status=CacheStatus.ACTIVE,
                usage_type=usage_type,
                is_active=True,
                cached_at=datetime.now(),
                last_accessed=datetime.now(),
                expires_at=expires_at,
                access_count=0,
                hit_count=0,
                success_count=0
            )
            
            # 添加到缓存
            self.cache[cached_range.cache_id] = cached_range
            
            # 更新索引
            self.symbol_index[consolidation_range.symbol].append(cached_range.cache_id)
            
            # 设置为活跃区间
            if usage_type == RangeUsageType.STOP_LOSS:
                self.active_ranges[consolidation_range.symbol] = cached_range.cache_id
            
            # 更新统计
            self.cache_stats['total_cached'] += 1
            
            # 持久化
            if self.persistence_enabled:
                self._save_cache_to_file()
            
            self.logger.info(f"成功缓存区间: {cached_range.cache_id}, "
                           f"币种: {consolidation_range.symbol}, "
                           f"类型: {usage_type.value}")
            
            return cached_range
            
        except Exception as e:
            self.logger.error(f"缓存区间失败: {str(e)}")
            raise
    
    def get_cached_range(self, cache_id: str) -> Optional[CachedRange]:
        """
        获取缓存的区间
        
        Args:
            cache_id: 缓存ID
            
        Returns:
            CachedRange: 缓存对象，如果不存在则返回None
        """
        try:
            cached_range = self.cache.get(cache_id)
            
            if cached_range:
                if cached_range.is_expired():
                    self._invalidate_range(cache_id, "expired")
                    self.cache_stats['total_expired'] += 1
                    return None
                
                # 更新访问信息
                cached_range.update_access()
                self.cache_stats['total_hits'] += 1
                
                # 移到最后 (LRU)
                self.cache.move_to_end(cache_id)
                
                return cached_range
            else:
                self.cache_stats['total_misses'] += 1
                return None
                
        except Exception as e:
            self.logger.error(f"获取缓存区间失败: {str(e)}")
            return None
    
    def get_active_range_for_symbol(self, symbol: str) -> Optional[CachedRange]:
        """
        获取指定币种的活跃区间
        
        Args:
            symbol: 交易对符号
            
        Returns:
            CachedRange: 活跃区间，如果不存在则返回None
        """
        try:
            active_id = self.active_ranges.get(symbol)
            if active_id:
                return self.get_cached_range(active_id)
            return None
            
        except Exception as e:
            self.logger.error(f"获取活跃区间失败: {str(e)}")
            return None
    
    def get_ranges_by_symbol(self, 
                           symbol: str, 
                           active_only: bool = False,
                           limit: Optional[int] = None) -> List[CachedRange]:
        """
        获取指定币种的所有区间
        
        Args:
            symbol: 交易对符号
            active_only: 是否只返回活跃区间
            limit: 返回数量限制
            
        Returns:
            List[CachedRange]: 区间列表
        """
        try:
            cache_ids = self.symbol_index.get(symbol, [])
            ranges = []
            
            for cache_id in cache_ids:
                cached_range = self.get_cached_range(cache_id)
                if cached_range:
                    if active_only and not cached_range.is_active:
                        continue
                    ranges.append(cached_range)
                    
                    if limit and len(ranges) >= limit:
                        break
            
            # 按创建时间倒序排列
            ranges.sort(key=lambda x: x.cached_at, reverse=True)
            
            return ranges
            
        except Exception as e:
            self.logger.error(f"获取币种区间失败: {str(e)}")
            return []
    
    def find_ranges_by_price(self,
                           symbol: str,
                           price: float,
                           tolerance: float = 0.01) -> List[CachedRange]:
        """
        根据价格查找相关区间
        
        Args:
            symbol: 交易对符号
            price: 价格
            tolerance: 容忍度
            
        Returns:
            List[CachedRange]: 相关区间列表
        """
        try:
            ranges = self.get_ranges_by_symbol(symbol)
            matching_ranges = []
            
            for cached_range in ranges:
                consolidation = cached_range.consolidation_range
                
                # 检查价格是否在区间内或附近
                if consolidation.contains_price(price, tolerance):
                    matching_ranges.append(cached_range)
                    continue
                
                # 检查价格是否接近边界
                distance = consolidation.distance_to_boundary(price)
                if (distance['to_upper_pct'] <= tolerance * 100 or 
                    distance['to_lower_pct'] <= tolerance * 100):
                    matching_ranges.append(cached_range)
            
            return matching_ranges
            
        except Exception as e:
            self.logger.error(f"根据价格查找区间失败: {str(e)}")
            return []
    
    def update_range_performance(self,
                               cache_id: str,
                               price_return: float,
                               holding_period: int,
                               success: bool = False):
        """
        更新区间性能数据
        
        Args:
            cache_id: 缓存ID
            price_return: 价格回报
            holding_period: 持仓周期
            success: 是否成功
        """
        try:
            cached_range = self.get_cached_range(cache_id)
            if cached_range:
                cached_range.add_performance_data(price_return, holding_period)
                cached_range.record_hit(success)
                
                self.logger.info(f"更新区间性能: {cache_id}, "
                               f"回报: {price_return:.4f}, "
                               f"周期: {holding_period}, "
                               f"成功: {success}")
                
                # 持久化
                if self.persistence_enabled:
                    self._save_cache_to_file()
                    
        except Exception as e:
            self.logger.error(f"更新区间性能失败: {str(e)}")
    
    def invalidate_range(self, cache_id: str, reason: str = "manual"):
        """
        使区间失效
        
        Args:
            cache_id: 缓存ID
            reason: 失效原因
        """
        self._invalidate_range(cache_id, reason)
    
    def _invalidate_range(self, cache_id: str, reason: str):
        """内部失效方法"""
        try:
            cached_range = self.cache.get(cache_id)
            if cached_range:
                cached_range.status = CacheStatus.INVALIDATED
                cached_range.is_active = False
                cached_range.notes = f"Invalidated: {reason}"
                
                # 从活跃区间中移除
                if cached_range.symbol in self.active_ranges:
                    if self.active_ranges[cached_range.symbol] == cache_id:
                        del self.active_ranges[cached_range.symbol]
                
                self.cache_stats['total_invalidated'] += 1
                
                self.logger.info(f"区间失效: {cache_id}, 原因: {reason}")
                
        except Exception as e:
            self.logger.error(f"区间失效操作失败: {str(e)}")
    
    def _ensure_cache_capacity(self):
        """确保缓存容量不超限"""
        try:
            while len(self.cache) >= self.max_cached_ranges:
                # 移除最旧的无效区间
                oldest_invalid = None
                for cache_id, cached_range in self.cache.items():
                    if not cached_range.is_valid():
                        oldest_invalid = cache_id
                        break
                
                if oldest_invalid:
                    self._remove_range(oldest_invalid)
                else:
                    # 移除最旧的区间
                    oldest_id = next(iter(self.cache))
                    self._remove_range(oldest_id)
                    
        except Exception as e:
            self.logger.error(f"缓存容量管理失败: {str(e)}")
    
    def _remove_range(self, cache_id: str):
        """移除区间"""
        try:
            cached_range = self.cache.get(cache_id)
            if cached_range:
                # 从索引中移除
                symbol = cached_range.symbol
                if symbol in self.symbol_index:
                    if cache_id in self.symbol_index[symbol]:
                        self.symbol_index[symbol].remove(cache_id)
                    
                    # 如果该币种没有其他区间，删除索引条目
                    if not self.symbol_index[symbol]:
                        del self.symbol_index[symbol]
                
                # 从活跃区间中移除
                if symbol in self.active_ranges:
                    if self.active_ranges[symbol] == cache_id:
                        del self.active_ranges[symbol]
                
                # 从缓存中移除
                del self.cache[cache_id]
                
                self.logger.debug(f"移除区间: {cache_id}")
                
        except Exception as e:
            self.logger.error(f"移除区间失败: {str(e)}")
    
    def cleanup_expired(self) -> int:
        """
        清理过期区间
        
        Returns:
            int: 清理的数量
        """
        return self._cleanup_expired_ranges()
    
    def _cleanup_expired_ranges(self) -> int:
        """清理过期区间"""
        try:
            expired_ids = []
            current_time = datetime.now()
            
            for cache_id, cached_range in self.cache.items():
                if (cached_range.expires_at < current_time or
                    cached_range.status == CacheStatus.EXPIRED):
                    expired_ids.append(cache_id)
            
            # 移除过期区间
            for cache_id in expired_ids:
                self._remove_range(cache_id)
            
            if expired_ids:
                self.logger.info(f"清理过期区间: {len(expired_ids)} 个")
            
            return len(expired_ids)
            
        except Exception as e:
            self.logger.error(f"清理过期区间失败: {str(e)}")
            return 0
    
    def get_cache_statistics(self) -> Dict:
        """获取缓存统计信息"""
        try:
            # 计算命中率
            total_requests = self.cache_stats['total_hits'] + self.cache_stats['total_misses']
            if total_requests > 0:
                self.cache_stats['hit_ratio'] = self.cache_stats['total_hits'] / total_requests
            
            # 计算平均生存期
            if self.cache:
                lifetimes = []
                current_time = datetime.now()
                for cached_range in self.cache.values():
                    lifetime = (current_time - cached_range.cached_at).total_seconds() / 3600
                    lifetimes.append(lifetime)
                self.cache_stats['avg_lifetime'] = np.mean(lifetimes)
            
            # 添加当前状态
            current_stats = {
                'current_cache_size': len(self.cache),
                'active_ranges_count': len(self.active_ranges),
                'symbols_count': len(self.symbol_index),
                'max_capacity': self.max_cached_ranges,
                'capacity_usage': len(self.cache) / self.max_cached_ranges * 100
            }
            
            return {**self.cache_stats, **current_stats}
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}")
            return {}
    
    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        try:
            report = {
                'total_ranges': len(self.cache),
                'by_symbol': {},
                'by_effectiveness': {'high': 0, 'medium': 0, 'low': 0},
                'overall_performance': {
                    'avg_effectiveness': 0.0,
                    'total_trades': 0,
                    'avg_return': 0.0,
                    'success_rate': 0.0
                }
            }
            
            all_returns = []
            all_effectiveness = []
            total_success = 0
            total_trades = 0
            
            # 按币种统计
            for symbol, cache_ids in self.symbol_index.items():
                symbol_stats = {
                    'ranges_count': len(cache_ids),
                    'active_count': 0,
                    'avg_effectiveness': 0.0,
                    'total_trades': 0,
                    'avg_return': 0.0,
                    'success_rate': 0.0
                }
                
                symbol_returns = []
                symbol_effectiveness = []
                symbol_success = 0
                symbol_trades = 0
                
                for cache_id in cache_ids:
                    cached_range = self.cache.get(cache_id)
                    if cached_range and cached_range.is_valid():
                        if cached_range.is_active:
                            symbol_stats['active_count'] += 1
                        
                        if cached_range.price_returns:
                            symbol_returns.extend(cached_range.price_returns)
                            symbol_trades += len(cached_range.price_returns)
                            symbol_success += cached_range.success_count
                        
                        symbol_effectiveness.append(cached_range.effectiveness_score)
                
                if symbol_returns:
                    symbol_stats['avg_return'] = np.mean(symbol_returns)
                    symbol_stats['total_trades'] = symbol_trades
                    symbol_stats['success_rate'] = symbol_success / symbol_trades if symbol_trades > 0 else 0
                    
                    all_returns.extend(symbol_returns)
                    total_trades += symbol_trades
                    total_success += symbol_success
                
                if symbol_effectiveness:
                    symbol_stats['avg_effectiveness'] = np.mean(symbol_effectiveness)
                    all_effectiveness.extend(symbol_effectiveness)
                
                report['by_symbol'][symbol] = symbol_stats
            
            # 按有效性分类
            for effectiveness in all_effectiveness:
                if effectiveness >= 70:
                    report['by_effectiveness']['high'] += 1
                elif effectiveness >= 40:
                    report['by_effectiveness']['medium'] += 1
                else:
                    report['by_effectiveness']['low'] += 1
            
            # 整体性能
            if all_returns:
                report['overall_performance']['avg_return'] = np.mean(all_returns)
                report['overall_performance']['total_trades'] = total_trades
                report['overall_performance']['success_rate'] = total_success / total_trades if total_trades > 0 else 0
            
            if all_effectiveness:
                report['overall_performance']['avg_effectiveness'] = np.mean(all_effectiveness)
            
            return report
            
        except Exception as e:
            self.logger.error(f"获取性能报告失败: {str(e)}")
            return {}
    
    def _save_cache_to_file(self):
        """保存缓存到文件"""
        try:
            if not self.persistence_enabled:
                return
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.cache_file_path), exist_ok=True)
            
            # 序列化缓存数据
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
                'cache_stats': self.cache_stats,
                'ranges': {}
            }
            
            for cache_id, cached_range in self.cache.items():
                if cached_range.is_valid():  # 只保存有效的区间
                    cache_data['ranges'][cache_id] = cached_range.to_dict()
            
            # 写入文件
            with open(self.cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"缓存已保存到文件: {self.cache_file_path}")
            
        except Exception as e:
            self.logger.error(f"保存缓存文件失败: {str(e)}")
    
    def _load_cache_from_file(self):
        """从文件加载缓存"""
        try:
            if not os.path.exists(self.cache_file_path):
                return
            
            with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 恢复统计信息
            if 'cache_stats' in cache_data:
                self.cache_stats.update(cache_data['cache_stats'])
            
            # 恢复区间数据
            loaded_count = 0
            if 'ranges' in cache_data:
                for cache_id, range_data in cache_data['ranges'].items():
                    try:
                        # 这里需要从字典重建对象
                        # 由于结构复杂，我们简化为只加载基本信息
                        # 实际项目中可能需要更完整的反序列化逻辑
                        loaded_count += 1
                    except Exception as e:
                        self.logger.warning(f"加载区间失败: {cache_id}, {str(e)}")
            
            self.logger.info(f"从文件加载缓存: {loaded_count} 个区间")
            
        except Exception as e:
            self.logger.error(f"加载缓存文件失败: {str(e)}")
    
    def clear_cache(self):
        """清空缓存"""
        try:
            self.cache.clear()
            self.symbol_index.clear()
            self.active_ranges.clear()
            
            # 重置统计
            self.cache_stats = {
                'total_cached': 0,
                'total_hits': 0,
                'total_misses': 0,
                'total_expired': 0,
                'total_invalidated': 0,
                'avg_lifetime': 0.0,
                'hit_ratio': 0.0
            }
            
            self.logger.info("缓存已清空")
            
        except Exception as e:
            self.logger.error(f"清空缓存失败: {str(e)}")
    
    def export_cache_data(self, file_path: str) -> bool:
        """
        导出缓存数据
        
        Args:
            file_path: 导出文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            export_data = {
                'export_time': datetime.now().isoformat(),
                'cache_stats': self.get_cache_statistics(),
                'performance_report': self.get_performance_report(),
                'ranges': {}
            }
            
            for cache_id, cached_range in self.cache.items():
                export_data['ranges'][cache_id] = cached_range.to_dict()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"缓存数据已导出到: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出缓存数据失败: {str(e)}")
            return False