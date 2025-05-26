"""
盘整带缓存系统优化测试版

增加参数调优、详细调试信息和多策略对比功能

Author: Pinbar Strategy Team
Date: 2024-12
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
from typing import Optional, Dict, List, Any

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入项目模块
from data_utils import interactive_select_local_data, load_local_data, validate_data_quality, print_data_quality_report
from consolidation_system import (
    ConsolidationCacheSystem,
    create_consolidation_system,
    ConsolidationConfig
)

def create_optimized_configs() -> Dict[str, Dict]:
    """创建不同的优化配置"""
    
    # 基础配置（当前默认）
    base_config = {
        'consolidation': {
            'min_bars': 10,
            'max_bars': 100,
            'range_tolerance': 0.015,  # BTC默认1.5%
            'volume_confirm': True,
        },
        'breakout': {
            'min_volume_ratio': 1.2,
            'price_threshold': 0.005,
            'confirm_bars': 2,
        },
        'stop_loss': {
            'range_stop_buffer': 0.0005,
            'max_stop_loss': 0.05,
        }
    }
    
    # 宽松配置（更容易检测到信号）
    relaxed_config = {
        'consolidation': {
            'min_bars': 8,           # 降低最小K线数
            'max_bars': 120,
            'range_tolerance': 0.025, # 提高到2.5%
            'volume_confirm': False,   # 关闭成交量确认
        },
        'breakout': {
            'min_volume_ratio': 1.1,  # 降低成交量要求
            'price_threshold': 0.003,  # 降低突破阈值
            'confirm_bars': 1,         # 减少确认K线
        },
        'stop_loss': {
            'range_stop_buffer': 0.001,
            'max_stop_loss': 0.08,     # 放宽最大止损
        }
    }
    
    # 严格配置（高质量信号）
    strict_config = {
        'consolidation': {
            'min_bars': 15,          # 提高最小K线数
            'max_bars': 80,
            'range_tolerance': 0.01,  # 降低到1%
            'volume_confirm': True,
        },
        'breakout': {
            'min_volume_ratio': 1.5,  # 提高成交量要求
            'price_threshold': 0.008,  # 提高突破阈值
            'confirm_bars': 3,         # 增加确认K线
        },
        'stop_loss': {
            'range_stop_buffer': 0.0003,
            'max_stop_loss': 0.03,     # 收紧最大止损
        }
    }
    
    # 激进配置（寻找更多机会）
    aggressive_config = {
        'consolidation': {
            'min_bars': 6,           # 大幅降低
            'max_bars': 150,
            'range_tolerance': 0.035, # 大幅提高到3.5%
            'volume_confirm': False,
        },
        'breakout': {
            'min_volume_ratio': 1.0,  # 不要求成交量放大
            'price_threshold': 0.002,  # 很小的突破即可
            'confirm_bars': 1,
        },
        'stop_loss': {
            'range_stop_buffer': 0.002,
            'max_stop_loss': 0.10,     # 非常宽松
        }
    }
    
    return {
        'base': base_config,
        'relaxed': relaxed_config,
        'strict': strict_config,
        'aggressive': aggressive_config
    }

def analyze_data_characteristics(df: pd.DataFrame, symbol: str, interval: str) -> Dict:
    """分析数据特征，为参数调优提供依据"""
    
    print(f"\n🔍 分析 {symbol} {interval} 数据特征...")
    
    characteristics = {}
    
    try:
        # 基本统计
        characteristics['basic_stats'] = {
            'total_bars': len(df),
            'price_range': {
                'min': df['low'].min(),
                'max': df['high'].max(),
                'avg': df['close'].mean()
            },
            'time_span_days': (df['timestamp'].max() - df['timestamp'].min()).days if 'timestamp' in df.columns else 0
        }
        
        # 波动率分析
        df_copy = df.copy()
        df_copy['price_change'] = df_copy['close'].pct_change()
        df_copy['abs_change'] = df_copy['price_change'].abs()
        
        characteristics['volatility'] = {
            'avg_change': df_copy['abs_change'].mean(),
            'std_change': df_copy['price_change'].std(),
            'max_single_move': df_copy['abs_change'].max(),
            'volatility_percentiles': {
                '50%': df_copy['abs_change'].quantile(0.5),
                '75%': df_copy['abs_change'].quantile(0.75),
                '90%': df_copy['abs_change'].quantile(0.9),
                '95%': df_copy['abs_change'].quantile(0.95)
            }
        }
        
        # 成交量分析
        characteristics['volume'] = {
            'avg_volume': df['volume'].mean(),
            'volume_std': df['volume'].std(),
            'volume_cv': df['volume'].std() / df['volume'].mean() if df['volume'].mean() > 0 else 0,
            'volume_spikes': len(df[df['volume'] > df['volume'].mean() * 2])
        }
        
        # 趋势性分析
        window_size = min(50, len(df) // 4)
        df_copy['sma'] = df_copy['close'].rolling(window=window_size).mean()
        df_copy['trend'] = (df_copy['close'] - df_copy['sma']) / df_copy['sma']
        
        characteristics['trend'] = {
            'trending_periods': len(df_copy[df_copy['trend'].abs() > 0.02]),
            'sideways_periods': len(df_copy[df_copy['trend'].abs() <= 0.02]),
            'trend_ratio': len(df_copy[df_copy['trend'].abs() > 0.02]) / len(df_copy)
        }
        
        # 盘整潜力分析
        range_sizes = []
        for i in range(0, len(df) - 20, 10):  # 每10根K线检查一次
            window = df.iloc[i:i+20]
            if len(window) == 20:
                range_size = (window['high'].max() - window['low'].min()) / window['close'].mean()
                range_sizes.append(range_size)
        
        characteristics['consolidation_potential'] = {
            'avg_range_size': np.mean(range_sizes) if range_sizes else 0,
            'small_ranges_count': len([r for r in range_sizes if r < 0.02]),
            'medium_ranges_count': len([r for r in range_sizes if 0.02 <= r < 0.05]),
            'large_ranges_count': len([r for r in range_sizes if r >= 0.05])
        }
        
        # 打印分析结果
        print(f"   📊 基本信息:")
        print(f"     总K线数: {characteristics['basic_stats']['total_bars']}")
        print(f"     价格范围: {characteristics['basic_stats']['price_range']['min']:.2f} - {characteristics['basic_stats']['price_range']['max']:.2f}")
        print(f"     时间跨度: {characteristics['basic_stats']['time_span_days']} 天")
        
        print(f"   📈 波动率特征:")
        print(f"     平均变动: {characteristics['volatility']['avg_change']*100:.3f}%")
        print(f"     标准差: {characteristics['volatility']['std_change']*100:.3f}%")
        print(f"     最大单次变动: {characteristics['volatility']['max_single_move']*100:.2f}%")
        
        print(f"   📊 成交量特征:")
        print(f"     变异系数: {characteristics['volume']['volume_cv']:.2f}")
        print(f"     成交量激增次数: {characteristics['volume']['volume_spikes']}")
        
        print(f"   📈 市场特征:")
        print(f"     趋势性比例: {characteristics['trend']['trend_ratio']*100:.1f}%")
        print(f"     横盘比例: {(1-characteristics['trend']['trend_ratio'])*100:.1f}%")
        
        print(f"   🔄 盘整潜力:")
        print(f"     平均区间大小: {characteristics['consolidation_potential']['avg_range_size']*100:.2f}%")
        print(f"     小区间(<2%): {characteristics['consolidation_potential']['small_ranges_count']}")
        print(f"     中区间(2-5%): {characteristics['consolidation_potential']['medium_ranges_count']}")
        print(f"     大区间(>5%): {characteristics['consolidation_potential']['large_ranges_count']}")
        
        return characteristics
        
    except Exception as e:
        print(f"   ❌ 数据特征分析失败: {str(e)}")
        return characteristics

def suggest_optimal_config(characteristics: Dict, symbol: str) -> Dict:
    """基于数据特征建议最优配置"""
    
    print(f"\n💡 为 {symbol} 生成自适应配置...")
    
    try:
        # 基于波动率调整
        avg_volatility = characteristics.get('volatility', {}).get('avg_change', 0.01)
        
        # 基于盘整潜力调整
        avg_range_size = characteristics.get('consolidation_potential', {}).get('avg_range_size', 0.02)
        small_ranges = characteristics.get('consolidation_potential', {}).get('small_ranges_count', 0)
        total_windows = small_ranges + characteristics.get('consolidation_potential', {}).get('medium_ranges_count', 0) + characteristics.get('consolidation_potential', {}).get('large_ranges_count', 0)
        
        # 基于趋势性调整
        trend_ratio = characteristics.get('trend', {}).get('trend_ratio', 0.5)
        
        # 自适应参数计算
        if avg_volatility > 0.02:  # 高波动
            range_tolerance = min(avg_range_size * 1.5, 0.04)
            min_volume_ratio = 1.0  # 高波动时降低成交量要求
            price_threshold = avg_volatility * 0.5
        elif avg_volatility < 0.005:  # 低波动
            range_tolerance = max(avg_range_size * 0.8, 0.01)
            min_volume_ratio = 1.3  # 低波动时提高成交量要求
            price_threshold = 0.003
        else:  # 中等波动
            range_tolerance = avg_range_size * 1.2
            min_volume_ratio = 1.1
            price_threshold = avg_volatility * 0.7
        
        # 基于趋势性调整最小K线数
        if trend_ratio > 0.7:  # 强趋势市场
            min_bars = 6  # 趋势市场中盘整时间较短
        else:  # 震荡市场
            min_bars = 12  # 震荡市场中盘整时间较长
        
        # 基于数据量调整最大K线数
        total_bars = characteristics.get('basic_stats', {}).get('total_bars', 200)
        max_bars = min(total_bars // 3, 150)  # 不超过总数据的1/3
        
        adaptive_config = {
            'consolidation': {
                'min_bars': min_bars,
                'max_bars': max_bars,
                'range_tolerance': range_tolerance,
                'volume_confirm': avg_volatility < 0.015,  # 低波动时要求成交量确认
            },
            'breakout': {
                'min_volume_ratio': min_volume_ratio,
                'price_threshold': price_threshold,
                'confirm_bars': 2 if avg_volatility > 0.015 else 1,
            },
            'stop_loss': {
                'range_stop_buffer': max(avg_volatility * 0.1, 0.0003),
                'max_stop_loss': min(avg_volatility * 4, 0.08),
            }
        }
        
        print(f"   🎯 自适应参数:")
        print(f"     盘整容忍度: {range_tolerance*100:.2f}%")
        print(f"     最小K线数: {min_bars}")
        print(f"     成交量比率: {min_volume_ratio:.1f}")
        print(f"     价格阈值: {price_threshold*100:.3f}%")
        print(f"     成交量确认: {'是' if adaptive_config['consolidation']['volume_confirm'] else '否'}")
        
        return adaptive_config
        
    except Exception as e:
        print(f"   ❌ 配置生成失败: {str(e)}")
        # 返回默认配置
        return create_optimized_configs()['base']

def test_with_multiple_configs(df: pd.DataFrame, symbol: str, interval: str) -> Dict:
    """使用多种配置进行对比测试"""
    
    print(f"\n🔬 多配置对比测试开始...")
    
    # 获取数据特征
    characteristics = analyze_data_characteristics(df, symbol, interval)
    
    # 获取所有配置
    configs = create_optimized_configs()
    
    # 添加自适应配置
    configs['adaptive'] = suggest_optimal_config(characteristics, symbol)
    
    # 准备测试数据
    total_len = len(df)
    analysis_data = df.iloc[:int(total_len * 0.7)]
    test_data = df.iloc[int(total_len * 0.6):]
    
    results = {}
    
    for config_name, config in configs.items():
        print(f"\n{'='*50}")
        print(f"🧪 测试配置: {config_name.upper()}")
        print(f"{'='*50}")
        
        try:
            # 创建系统
            system = ConsolidationCacheSystem(config)
            
            # 执行分析
            consolidation_result = system.analyze_consolidation_breakout(
                price_data=analysis_data,
                current_price=test_data['close'].iloc[0] if len(test_data) > 0 else analysis_data['close'].iloc[-1]
            )
            
            # 记录结果
            config_result = {
                'config_name': config_name,
                'config': config,
                'status': consolidation_result['status'],
                'consolidation_detected': False,
                'breakout_detected': False,
                'quality_scores': {},
                'performance': {}
            }
            
            if consolidation_result['status'] == 'breakout_detected':
                consolidation_range = consolidation_result['range']
                breakout_signal = consolidation_result['breakout']
                cached_range = consolidation_result['cached_range']
                
                config_result.update({
                    'consolidation_detected': True,
                    'breakout_detected': True,
                    'quality_scores': {
                        'consolidation_quality': consolidation_range.quality_score,
                        'consolidation_confidence': consolidation_range.confidence,
                        'breakout_quality': breakout_signal.quality_score,
                        'breakout_confidence': breakout_signal.confidence,
                        'success_probability': breakout_signal.success_probability
                    },
                    'range_info': {
                        'upper_boundary': consolidation_range.upper_boundary,
                        'lower_boundary': consolidation_range.lower_boundary,
                        'range_size': consolidation_range.range_size,
                        'range_percentage': consolidation_range.range_percentage,
                        'duration_bars': consolidation_range.duration_bars
                    },
                    'breakout_info': {
                        'direction': breakout_signal.direction.value,
                        'type': breakout_signal.breakout_type.value,
                        'strength': breakout_signal.strength.value,
                        'price': breakout_signal.breakout_price,
                        'volume_ratio': breakout_signal.volume_ratio
                    }
                })
                
                # 测试后续表现
                if len(test_data) > 10:
                    performance = test_config_performance(system, cached_range, test_data, consolidation_range)
                    config_result['performance'] = performance
                
                # 显示关键信息
                print(f"   ✅ 检测到突破!")
                print(f"     盘整质量: {consolidation_range.quality_score:.1f}/100")
                print(f"     突破质量: {breakout_signal.quality_score:.1f}/100")
                print(f"     突破方向: {breakout_signal.direction.value}")
                print(f"     突破强度: {breakout_signal.strength.value}")
                print(f"     区间大小: {consolidation_range.range_percentage:.2f}%")
                print(f"     成功概率: {breakout_signal.success_probability:.2f}")
                
                if config_result['performance']:
                    perf = config_result['performance']
                    print(f"     测试表现: 最大盈利{perf['max_profit']:+.2f}%, 最大回撤{perf['max_drawdown']:+.2f}%")
                
            elif consolidation_result['status'] == 'no_breakout':
                print(f"   📊 检测到盘整，但无突破")
                config_result['consolidation_detected'] = True
                if consolidation_result['range']:
                    consolidation_range = consolidation_result['range']
                    config_result['quality_scores'] = {
                        'consolidation_quality': consolidation_range.quality_score,
                        'consolidation_confidence': consolidation_range.confidence
                    }
                    print(f"     盘整质量: {consolidation_range.quality_score:.1f}/100")
            else:
                print(f"   ❌ 未检测到有效信号")
            
            results[config_name] = config_result
            
        except Exception as e:
            print(f"   ❌ 配置 {config_name} 测试失败: {str(e)}")
            results[config_name] = {
                'config_name': config_name,
                'status': 'error',
                'error': str(e)
            }
    
    return results

def test_config_performance(system, cached_range, test_data: pd.DataFrame, consolidation_range) -> Dict:
    """测试配置的实际性能"""
    
    try:
        entry_price = test_data['close'].iloc[0]
        max_profit = 0
        max_drawdown = 0
        final_profit = 0
        stop_triggered = False
        bars_held = 0
        
        for i, (_, row) in enumerate(test_data.iterrows()):
            current_price = row['close']
            profit_pct = (current_price - entry_price) / entry_price * 100
            
            max_profit = max(max_profit, profit_pct)
            max_drawdown = min(max_drawdown, profit_pct)
            
            # 检查止损
            exit_signal = system.should_exit_by_range(cached_range.cache_id, current_price)
            if exit_signal.get('should_exit'):
                stop_triggered = True
                final_profit = profit_pct
                bars_held = i + 1
                break
        
        if not stop_triggered:
            final_profit = (test_data['close'].iloc[-1] - entry_price) / entry_price * 100
            bars_held = len(test_data)
        
        # 计算目标达成情况
        target_profit = consolidation_range.range_percentage  # 以区间大小为目标
        target_achieved = max_profit >= target_profit
        
        return {
            'max_profit': max_profit,
            'max_drawdown': max_drawdown,
            'final_profit': final_profit,
            'bars_held': bars_held,
            'stop_triggered': stop_triggered,
            'target_achieved': target_achieved,
            'risk_reward_ratio': max_profit / abs(max_drawdown) if max_drawdown < 0 else float('inf')
        }
        
    except Exception as e:
        print(f"     性能测试失败: {str(e)}")
        return {}

def generate_comparison_report(results: Dict) -> None:
    """生成对比报告"""
    
    print(f"\n" + "🎉"*20)
    print("🎉 多配置对比测试完成!")
    print("🎉"*20)
    
    # 统计各配置表现
    summary = {}
    for config_name, result in results.items():
        if result.get('status') == 'error':
            continue
        
        summary[config_name] = {
            'consolidation_detected': result.get('consolidation_detected', False),
            'breakout_detected': result.get('breakout_detected', False),
            'avg_quality': 0,
            'performance_score': 0
        }
        
        # 计算平均质量分数
        quality_scores = result.get('quality_scores', {})
        if quality_scores:
            scores = [score for score in quality_scores.values() if isinstance(score, (int, float))]
            summary[config_name]['avg_quality'] = np.mean(scores) if scores else 0
        
        # 计算性能分数
        performance = result.get('performance', {})
        if performance:
            perf_score = 0
            if performance.get('target_achieved'):
                perf_score += 50
            perf_score += min(performance.get('max_profit', 0) * 2, 30)  # 最多30分
            perf_score += max(20 - abs(performance.get('max_drawdown', 0)), 0)  # 回撤越小分数越高
            summary[config_name]['performance_score'] = perf_score
    
    # 显示对比表格
    print(f"\n📊 配置对比表:")
    print("-" * 80)
    print(f"{'配置':<12} {'盘整检测':<8} {'突破检测':<8} {'平均质量':<10} {'性能分数':<10} {'推荐度':<8}")
    print("-" * 80)
    
    # 按性能分数排序
    sorted_configs = sorted(summary.items(), key=lambda x: x[1]['performance_score'], reverse=True)
    
    for config_name, stats in sorted_configs:
        consolidation = "✅" if stats['consolidation_detected'] else "❌"
        breakout = "✅" if stats['breakout_detected'] else "❌"
        quality = f"{stats['avg_quality']:.1f}"
        performance = f"{stats['performance_score']:.1f}"
        
        # 推荐度评级
        if stats['performance_score'] >= 70:
            recommendation = "🌟🌟🌟"
        elif stats['performance_score'] >= 50:
            recommendation = "🌟🌟"
        elif stats['performance_score'] >= 30:
            recommendation = "🌟"
        else:
            recommendation = "❌"
        
        print(f"{config_name:<12} {consolidation:<8} {breakout:<8} {quality:<10} {performance:<10} {recommendation:<8}")
    
    # 详细分析最佳配置
    if sorted_configs:
        best_config_name, best_stats = sorted_configs[0]
        best_result = results[best_config_name]
        
        print(f"\n🏆 最佳配置: {best_config_name.upper()}")
        print("-" * 40)
        
        if best_result.get('breakout_detected'):
            range_info = best_result.get('range_info', {})
            breakout_info = best_result.get('breakout_info', {})
            performance = best_result.get('performance', {})
            
            print(f"盘整区间: {range_info.get('lower_boundary', 0):.2f} - {range_info.get('upper_boundary', 0):.2f}")
            print(f"区间大小: {range_info.get('range_percentage', 0):.2f}%")
            print(f"突破方向: {breakout_info.get('direction', 'N/A')}")
            print(f"突破强度: {breakout_info.get('strength', 'N/A')}")
            
            if performance:
                print(f"最大盈利: {performance.get('max_profit', 0):+.2f}%")
                print(f"最大回撤: {performance.get('max_drawdown', 0):+.2f}%")
                print(f"持仓周期: {performance.get('bars_held', 0)} 根K线")
                print(f"目标达成: {'是' if performance.get('target_achieved') else '否'}")
        
        # 显示最佳配置的参数
        best_config = best_result.get('config', {})
        print(f"\n🔧 最佳配置参数:")
        for category, params in best_config.items():
            print(f"  {category}:")
            for key, value in params.items():
                print(f"    {key}: {value}")
    
    # 总结建议
    print(f"\n💡 优化建议:")
    successful_configs = [name for name, stats in summary.items() if stats['breakout_detected']]
    
    if len(successful_configs) > 1:
        print("   ✅ 多个配置成功检测到信号，系统具备良好的适应性")
        print("   🎯 建议根据实际交易环境选择合适的配置")
    elif len(successful_configs) == 1:
        print(f"   🎯 {successful_configs[0]} 配置表现最佳，建议优先使用")
        print("   📊 可尝试在此基础上微调参数")
    else:
        print("   ⚠️ 所有配置都未检测到有效信号")
        print("   🔧 建议：")
        print("     1. 尝试更宽松的参数设置")
        print("     2. 使用更长时间范围的数据")
        print("     3. 选择波动率更高的币种或时间周期")

def run_optimized_test():
    """运行优化版测试"""
    
    print("🎯 盘整带缓存系统 - 优化版真实数据测试")
    print("=" * 60)
    
    # 1. 加载真实数据
    df, symbol, interval = load_real_market_data()
    if df is None:
        return
    
    print(f"\n📊 数据概览:")
    print(f"   币种: {symbol}")
    print(f"   周期: {interval}")
    print(f"   数据量: {len(df)} 条")
    if 'timestamp' in df.columns:
        print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"   价格范围: {df['low'].min():.2f} - {df['high'].max():.2f}")
    
    # 2. 多配置对比测试
    results = test_with_multiple_configs(df, symbol, interval)
    
    # 3. 生成对比报告
    generate_comparison_report(results)
    
    return results

def load_real_market_data():
    """加载真实市场数据"""
    print("🎯 选择测试数据")
    print("=" * 30)
    
    # 交互式选择本地数据
    symbol, interval = interactive_select_local_data()
    
    if symbol is None or interval is None:
        print("❌ 未选择有效数据")
        return None, None, None
    
    # 加载选定的数据
    print(f"\n📊 加载数据: {symbol} {interval}")
    df = load_local_data(symbol, interval)
    
    if df is None:
        print("❌ 数据加载失败")
        return None, None, None
    
    # 验证数据质量
    quality_report = validate_data_quality(df, symbol, interval)
    print_data_quality_report(quality_report)
    
    if quality_report['score'] < 60:
        print(f"⚠️ 数据质量较差 ({quality_report['score']:.0f}/100)")
        if input("是否继续测试？(y/N): ").lower() != 'y':
            return None, None, None
    
    return df, symbol, interval

def main():
    """主程序入口"""
    
    print("🎯 盘整带缓存系统 - 优化版测试工具")
    print("=" * 60)
    print("✨ 多配置对比 + 自适应参数调优 + 详细分析")
    print("=" * 60)
    
    try:
        print("\n📋 测试选项:")
        print("1. 🔬 多配置对比测试 (推荐)")
        print("2. 🧪 单配置快速测试")
        print("3. ❌ 退出")
        
        choice = input("\n请选择测试模式 (1-3): ").strip()
        
        if choice == '1':
            run_optimized_test()
        elif choice == '2':
            # 保留原来的单配置测试逻辑
            df, symbol, interval = load_real_market_data()
            if df is not None:
                system = create_consolidation_system(symbol)
                total_len = len(df)
                analysis_data = df.iloc[:int(total_len * 0.8)]
                test_data = df.iloc[int(total_len * 0.7):]
                
                consolidation_result = system.analyze_consolidation_breakout(
                    price_data=analysis_data,
                    current_price=test_data['close'].iloc[0] if len(test_data) > 0 else analysis_data['close'].iloc[-1]
                )
                print(f"\n结果: {consolidation_result['status']}")
        elif choice == '3':
            print("👋 测试退出")
        else:
            print("❌ 无效选择")
    
    except KeyboardInterrupt:
        print("\n👋 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()