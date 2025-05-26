"""
盘整带缓存系统 - 模块初始化文件

这个模块实现了基于盘整带理论的智能止损系统，旨在解决传统Pinbar策略的两大核心问题：
1. 过早止盈错过大行情
2. 容易被洗盘震出

核心设计理念：
- 双重止损体系：盘整带止损（主） + 传统止损（保底）
- 流动性猎杀检测：识别大资金的洗盘行为
- 抗干扰持仓：基于盘整区间边界的智能止损

系统组件：
- ConsolidationDetector: 盘整带识别器
- BreakoutAnalyzer: 突破分析器
- RangeCacheManager: 区间缓存管理器
- DynamicStopController: 动态止损控制器
- LiquidityHunterDetector: 流动性猎杀检测器

Author: Pinbar Strategy Team
Date: 2024-12
Version: 1.0
"""

from .consolidation_detector import ConsolidationDetector, ConsolidationRange
from .breakout_analyzer import BreakoutAnalyzer, BreakoutSignal, BreakoutType
from .range_cache_manager import RangeCacheManager, CachedRange
from .dynamic_stop_controller import DynamicStopController, StopLossType, StopLossLevel
from .liquidity_hunter_detector import LiquidityHunterDetector, HuntingSignal, LiquidityZone

# 版本信息
__version__ = "1.0.0"
__author__ = "Pinbar Strategy Team"
__description__ = "盘整带缓存系统 - 智能抗洗盘止损解决方案"

# 导出的主要类
__all__ = [
    # 核心检测器
    'ConsolidationDetector',
    'BreakoutAnalyzer', 
    'RangeCacheManager',
    'DynamicStopController',
    'LiquidityHunterDetector',
    
    # 数据结构
    'ConsolidationRange',
    'BreakoutSignal',
    'BreakoutType',
    'CachedRange',
    'StopLossType',
    'StopLossLevel',
    'HuntingSignal',
    'LiquidityZone',
    
    # 系统集成类
    'ConsolidationCacheSystem'
]

class ConsolidationCacheSystem:
    """
    盘整带缓存系统主控制器
    
    集成所有子模块，提供统一的接口供外部调用
    """
    
    def __init__(self, config=None):
        """
        初始化盘整带缓存系统
        
        Args:
            config: 系统配置参数
        """
        # 默认配置
        self.config = config or self._get_default_config()
        
        # 初始化各子模块
        self.consolidation_detector = ConsolidationDetector(self.config.get('consolidation', {}))
        self.breakout_analyzer = BreakoutAnalyzer(self.config.get('breakout', {}))
        self.range_cache_manager = RangeCacheManager(self.config.get('cache', {}))
        self.dynamic_stop_controller = DynamicStopController(self.config.get('stop_loss', {}))
        self.liquidity_hunter_detector = LiquidityHunterDetector(self.config.get('liquidity', {}))
        
        # 系统状态
        self.is_initialized = True
        self.active_ranges = {}  # 活跃的盘整区间
        self.system_stats = self._init_stats()
    
    def _get_default_config(self):
        """获取默认系统配置"""
        return {
            'consolidation': {
                'min_bars': 10,           # 最小盘整K线数
                'max_bars': 100,          # 最大盘整K线数
                'range_tolerance': 0.02,  # 盘整区间容忍度 (2%)
                'volume_confirm': True,   # 是否需要成交量确认
            },
            'breakout': {
                'min_volume_ratio': 1.5,  # 最小成交量放大倍数
                'price_threshold': 0.005, # 价格突破阈值 (0.5%)
                'confirm_bars': 2,        # 突破确认K线数
                'false_breakout_check': True,  # 是否检查假突破
            },
            'cache': {
                'max_cached_ranges': 50,  # 最大缓存区间数
                'cache_expiry_days': 30,  # 缓存过期天数
                'auto_cleanup': True,     # 自动清理过期缓存
            },
            'stop_loss': {
                'use_range_stop': True,   # 使用盘整带止损
                'use_traditional_stop': True,  # 使用传统止损
                'range_stop_buffer': 0.001,    # 盘整带止损缓冲 (0.1%)
                'max_stop_loss': 0.05,         # 最大止损比例 (5%)
            },
            'liquidity': {
                'detection_enabled': True,     # 启用流动性猎杀检测
                'volume_spike_threshold': 2.0, # 成交量异常阈值
                'price_rejection_threshold': 0.01,  # 价格拒绝阈值 (1%)
            }
        }
    
    def _init_stats(self):
        """初始化系统统计信息"""
        return {
            'ranges_detected': 0,
            'breakouts_analyzed': 0,
            'successful_holds': 0,
            'false_breakouts_caught': 0,
            'liquidity_hunts_detected': 0,
            'system_uptime': 0,
        }
    
    def analyze_consolidation_breakout(self, price_data, current_price=None):
        """
        分析盘整突破情况
        
        Args:
            price_data: 价格数据 (DataFrame)
            current_price: 当前价格
            
        Returns:
            dict: 分析结果
        """
        try:
            # 1. 检测盘整区间
            consolidation_range = self.consolidation_detector.detect_consolidation(price_data)
            
            if not consolidation_range:
                return {'status': 'no_consolidation', 'range': None}
            
            # 2. 分析突破
            breakout_signal = self.breakout_analyzer.analyze_breakout(
                price_data, consolidation_range, current_price
            )
            
            if not breakout_signal or not breakout_signal.is_valid:
                return {'status': 'no_breakout', 'range': consolidation_range}
            
            # 3. 缓存区间
            cached_range = self.range_cache_manager.cache_range(
                consolidation_range, breakout_signal
            )
            
            # 4. 生成止损建议
            stop_levels = self.dynamic_stop_controller.calculate_stop_levels(
                cached_range, breakout_signal, current_price
            )
            
            # 5. 检测流动性猎杀
            hunting_signal = self.liquidity_hunter_detector.detect_hunting(
                price_data, cached_range, breakout_signal
            )
            
            # 更新统计
            self.system_stats['ranges_detected'] += 1
            self.system_stats['breakouts_analyzed'] += 1
            
            return {
                'status': 'breakout_detected',
                'range': consolidation_range,
                'cached_range': cached_range,
                'breakout': breakout_signal,
                'stop_levels': stop_levels,
                'hunting_signal': hunting_signal,
                'system_stats': self.system_stats.copy()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'range': None
            }
    
    def should_exit_by_range(self, cached_range_id, current_price):
        """
        基于盘整带判断是否应该退出
        
        Args:
            cached_range_id: 缓存区间ID
            current_price: 当前价格
            
        Returns:
            dict: 退出建议
        """
        try:
            # 获取缓存的区间
            cached_range = self.range_cache_manager.get_cached_range(cached_range_id)
            if not cached_range:
                return {'should_exit': False, 'reason': 'range_not_found'}
            
            # 使用动态止损控制器判断
            exit_signal = self.dynamic_stop_controller.should_exit(
                cached_range, current_price
            )
            
            if exit_signal['should_exit']:
                # 更新统计
                if exit_signal['exit_type'] == 'range_return':
                    self.system_stats['successful_holds'] += 1
            
            return exit_signal
            
        except Exception as e:
            return {
                'should_exit': True,  # 出错时保守退出
                'reason': 'error',
                'error': str(e)
            }
    
    def get_system_status(self):
        """获取系统状态"""
        return {
            'initialized': self.is_initialized,
            'active_ranges_count': len(self.active_ranges),
            'stats': self.system_stats.copy(),
            'config': self.config
        }
    
    def cleanup_expired_ranges(self):
        """清理过期的缓存区间"""
        return self.range_cache_manager.cleanup_expired()
    
    def reset_system(self):
        """重置系统状态"""
        self.active_ranges.clear()
        self.system_stats = self._init_stats()
        self.range_cache_manager.clear_cache()
        return True


# 系统配置常量
class ConsolidationConfig:
    """盘整带系统配置常量"""
    
    # 盘整检测参数
    MIN_CONSOLIDATION_BARS = 8
    MAX_CONSOLIDATION_BARS = 120
    DEFAULT_RANGE_TOLERANCE = 0.02
    
    # 突破确认参数
    MIN_BREAKOUT_VOLUME_RATIO = 1.3
    DEFAULT_PRICE_THRESHOLD = 0.005
    BREAKOUT_CONFIRM_BARS = 2
    
    # 止损参数
    RANGE_STOP_BUFFER = 0.001
    MAX_STOP_LOSS_RATIO = 0.08
    EMERGENCY_STOP_RATIO = 0.12
    
    # 流动性检测参数
    VOLUME_SPIKE_THRESHOLD = 2.0
    PRICE_REJECTION_THRESHOLD = 0.015
    
    # 缓存管理参数
    MAX_CACHE_SIZE = 100
    CACHE_EXPIRY_HOURS = 24 * 7  # 7天


# 快速工厂函数
def create_consolidation_system(symbol=None, config=None):
    """
    快速创建盘整带缓存系统实例
    
    Args:
        symbol: 交易对符号 (如 'BTCUSDT')
        config: 自定义配置
        
    Returns:
        ConsolidationCacheSystem: 系统实例
    """
    # 根据币种调整配置
    if symbol and config is None:
        config = _get_symbol_specific_config(symbol)
    
    return ConsolidationCacheSystem(config)


def _get_symbol_specific_config(symbol):
    """获取币种特定的配置"""
    # 基础配置
    base_config = ConsolidationCacheSystem()._get_default_config()
    
    # 根据币种调整参数
    if symbol.startswith('BTC'):
        # BTC参数调整
        base_config['consolidation']['range_tolerance'] = 0.015
        base_config['breakout']['min_volume_ratio'] = 1.2
    elif symbol.startswith('ETH'):
        # ETH参数调整
        base_config['consolidation']['range_tolerance'] = 0.018
        base_config['breakout']['min_volume_ratio'] = 1.3
    elif symbol in ['BNBUSDT', 'ADAUSDT', 'SOLUSDT']:
        # 主流山寨币参数
        base_config['consolidation']['range_tolerance'] = 0.025
        base_config['breakout']['min_volume_ratio'] = 1.5
    else:
        # 其他币种使用更保守参数
        base_config['consolidation']['range_tolerance'] = 0.03
        base_config['breakout']['min_volume_ratio'] = 1.8
    
    return base_config