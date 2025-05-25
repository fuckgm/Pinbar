#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pinbar策略主程序 - 主入口文件
拆分后的核心主程序，负责程序启动和主菜单
"""

import sys
import signal
from typing import Dict, Any, List, Optional, Tuple

# 导入拆分后的模块
from menu_handlers import (
    quick_backtest_with_trend,    # 新增：趋势跟踪版快速回测
    custom_backtest,
    multi_symbol_backtest,
    parameter_optimization,
    ab_test_strategies,           # 新增：A/B测试
    adaptive_parameter_tuning,    # 新增：自适应参数调优
    multi_timeframe_analysis,     # 新增：多周期分析
    ml_trend_optimization,        # 新增：ML优化
    batch_training_optimization   # 新增：批量训练优化
)
from data_utils import (
    get_local_data_summary, 
    load_local_data, 
    interactive_select_local_data
)
from utils import (
    signal_handler,
    safe_list_input,
    safe_confirm,
    safe_text_input
)

# 导入基础模块
from config import ConfigManager, TradingParams, BacktestParams
from data_manager import DataManager
from report_generator import ReportGenerator

def main():
    """主程序入口"""
    print("=" * 60)
    print("🎯 模块化Pinbar策略回测系统 - 趋势跟踪版")
    print("=" * 60)
    print("✨ 系统特色:")
    print("   🧠 智能信号生成器 - 多重确认机制")
    print("   📊 动态杠杆管理 - 根据市场条件自动调节")
    print("   🎯 强化趋势确认 - 确保信号符合趋势方向")
    print("   📈 信号质量评分 - 多维度评估信号强度")
    print("   🔧 智能参数优化 - 自动寻找最优参数组合")
    print("   📊 增强回测报告 - 包含信号质量统计")
    print("   🎯 多币种同时回测 - 批量测试多个币种")
    print("   🔄 模块化架构 - 便于维护和扩展")
    print("   📈 趋势跟踪系统 - 捕获大趋势利润")
    print("   🆚 A/B测试对比 - 策略性能对比分析")
    print("   🤖 机器学习优化 - AI驱动的策略改进")
    print("   🎯 批量训练系统 - 基于历史数据的智能优化")
    print("💡 提示: 使用 Ctrl+C 或 ESC 键可以返回上层菜单")
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    
    # 初始化管理器
    config_manager = ConfigManager()
    data_manager = DataManager()
    report_generator = ReportGenerator()
    
    # 主菜单循环
    while True:
        print("\n📋 主菜单:")
        choices = [
            '🚀 快速回测 (趋势跟踪版)',
            '⚙️  配置参数后回测 (增强版)',
            '🎯 多币种同时回测',
            '🔧 智能参数优化',
            '🆚 A/B测试 (原版vs趋势版)',
            '📊 自适应参数调优',
            '📈 多周期趋势确认',
            '🤖 ML趋势识别优化',
            '🎯 批量训练数据优化',
            '⬇️  数据下载器',
            '📁 查看本地数据',
            '❌ 退出程序'
        ]
        
        choice = safe_list_input("请选择操作 (ESC返回)", choices=choices)
        if choice is None:
            print("👋 程序退出")
            return
        
        try:
            if choice == choices[0]:  # 快速回测 (趋势跟踪版)
                quick_backtest_with_trend(config_manager, data_manager, report_generator)

            elif choice == choices[1]:  # 配置参数后回测
                custom_backtest(config_manager, data_manager, report_generator)

            elif choice == choices[2]:  # 多币种同时回测
                multi_symbol_backtest(config_manager, data_manager, report_generator)

            elif choice == choices[3]:  # 参数优化
                parameter_optimization(config_manager, data_manager)

            elif choice == choices[4]:  # A/B测试
                ab_test_strategies(config_manager, data_manager, report_generator)

            elif choice == choices[5]:  # 自适应参数调优
                adaptive_parameter_tuning(config_manager, data_manager)

            elif choice == choices[6]:  # 多周期趋势确认
                multi_timeframe_analysis(config_manager, data_manager, report_generator)

            elif choice == choices[7]:  # ML趋势识别优化
                ml_trend_optimization(config_manager, data_manager)

            elif choice == choices[8]:  # 批量训练数据优化
                batch_training_optimization(config_manager, data_manager)

            elif choice == choices[9]:  # 数据下载器
                print("\n🚀 启动数据下载器...")
                try:
                    from data_downloader import CryptoDataDownloader
                    downloader = CryptoDataDownloader()
                    downloader.interactive_download()
                except ImportError:
                    print("❌ 数据下载器模块未找到")
                    print("   请确保 data_downloader.py 文件存在")
                except Exception as e:
                    print(f"❌ 数据下载器启动失败: {e}")

            elif choice == choices[10]:  # 查看本地数据
                view_local_data()

            elif choice == choices[11]:  # 退出
                print("👋 感谢使用Pinbar策略回测系统!")
                break
                
        except KeyboardInterrupt:
            print("\n🔙 返回主菜单")
            continue
        except Exception as e:
            print(f"\n❌ 操作执行失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 询问是否继续
            continue_choice = safe_confirm("是否继续使用程序?", default=True)
            if not continue_choice:
                break

def view_local_data():
    """查看本地数据摘要"""
    print("\n📁 本地数据管理")
    
    local_data = get_local_data_summary()
    if not local_data:
        print("❌ 未找到本地数据")
        print("💡 建议:")
        print("   1. 使用数据下载器下载数据")
        print("   2. 确保数据文件存放在 data/ 目录下")
        print("   3. 数据文件格式为 CSV 或 PKL")
        return
    
    print(f"\n📊 本地数据摘要 (共 {len(local_data)} 个币种):")
    print("=" * 80)
    print(f"{'币种':<15} {'时间周期':<30} {'文件数量':<10}")
    print("-" * 80)
    
    total_files = 0
    for symbol, intervals in sorted(local_data.items()):
        intervals_str = ', '.join(intervals[:5])  # 只显示前5个
        if len(intervals) > 5:
            intervals_str += f'... (+{len(intervals)-5}个)'
        
        print(f"{symbol:<15} {intervals_str:<30} {len(intervals):<10}")
        total_files += len(intervals)
    
    print("-" * 80)
    print(f"总计: {len(local_data)} 个币种, {total_files} 个数据文件")
    
    # 数据质量检查选项
    check_quality = safe_confirm("\n🔍 是否检查数据质量?", default=False)
    if check_quality:
        check_data_quality(local_data)

def check_data_quality(local_data: Dict[str, List[str]]):
    """检查本地数据质量"""
    print("\n🔍 数据质量检查中...")
    
    quality_report = []
    
    for symbol in list(local_data.keys())[:5]:  # 只检查前5个币种
        for interval in local_data[symbol][:2]:  # 每个币种只检查前2个周期
            try:
                data = load_local_data(symbol, interval)
                if data is not None:
                    # 检查数据完整性
                    missing_data = data.isnull().sum().sum()
                    duplicate_data = data.duplicated().sum()
                    data_range = f"{data['timestamp'].min()} ~ {data['timestamp'].max()}" if 'timestamp' in data.columns else "未知"
                    
                    quality_info = {
                        'symbol': symbol,
                        'interval': interval,
                        'rows': len(data),
                        'missing': missing_data,
                        'duplicates': duplicate_data,
                        'range': data_range,
                        'status': '✅' if missing_data == 0 and duplicate_data == 0 else '⚠️'
                    }
                    quality_report.append(quality_info)
                    
            except Exception as e:
                quality_report.append({
                    'symbol': symbol,
                    'interval': interval,
                    'rows': 0,
                    'missing': 0,
                    'duplicates': 0,
                    'range': '错误',
                    'status': '❌',
                    'error': str(e)
                })
    
    # 显示质量报告
    if quality_report:
        print(f"\n📋 数据质量报告:")
        print("=" * 100)
        print(f"{'状态':<4} {'币种':<12} {'周期':<8} {'数据量':<8} {'缺失':<6} {'重复':<6} {'时间范围':<30}")
        print("-" * 100)
        
        for info in quality_report:
            print(f"{info['status']:<4} {info['symbol']:<12} {info['interval']:<8} "
                  f"{info['rows']:<8} {info['missing']:<6} {info['duplicates']:<6} "
                  f"{info['range']:<30}")
            
            if 'error' in info:
                print(f"     错误: {info['error']}")
        
        print("-" * 100)
        
        # 统计摘要
        total_checked = len(quality_report)
        good_quality = len([r for r in quality_report if r['status'] == '✅'])
        warning_quality = len([r for r in quality_report if r['status'] == '⚠️'])
        error_quality = len([r for r in quality_report if r['status'] == '❌'])
        
        print(f"质量摘要: ✅ {good_quality} | ⚠️ {warning_quality} | ❌ {error_quality} (共 {total_checked} 个)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 如果问题持续，请检查:")
        print("   1. 所有依赖模块是否已安装")
        print("   2. 配置文件是否正确")
        print("   3. 数据文件是否完整")