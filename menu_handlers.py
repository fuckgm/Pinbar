#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
菜单处理函数模块
负责处理各种菜单选项的具体逻辑
"""

from typing import Dict, List, Any, Optional, Tuple
from config import ConfigManager, TradingParams, BacktestParams
from data_manager import DataManager
from report_generator import ReportGenerator
from enhanced_report_generator import EnhancedReportGenerator
from parameter_optimizer import ParameterOptimizer
from data_utils import get_local_data_summary, load_local_data, interactive_select_local_data
from pinbar_strategy import run_enhanced_backtest
from utils import safe_list_input, safe_confirm, safe_text_input
def deep_clean_for_json(data, path="root"):
    """递归清理所有numpy类型，使数据可JSON序列化"""
    import numpy as np
    import pandas as pd
    
    problematic_items = []
    
    if isinstance(data, dict):
        cleaned_dict = {}
        for key, value in data.items():
            current_path = f"{path}.{key}"
            cleaned_value, problems = deep_clean_for_json(value, current_path)
            cleaned_dict[key] = cleaned_value
            problematic_items.extend(problems)
        return cleaned_dict, problematic_items
        
    elif isinstance(data, (list, tuple)):
        cleaned_list = []
        for i, item in enumerate(data):
            current_path = f"{path}[{i}]"
            cleaned_item, problems = deep_clean_for_json(item, current_path)
            cleaned_list.append(cleaned_item)
            problematic_items.extend(problems)
        return cleaned_list, problematic_items
        
    else:
        # 处理单个值
        original_type = type(data).__name__
        
        if isinstance(data, np.bool_):
            problematic_items.append(f"{path}: numpy.bool_ -> bool")
            return bool(data), problematic_items
        elif isinstance(data, (np.int8, np.int16, np.int32, np.int64)):
            problematic_items.append(f"{path}: {original_type} -> int")
            return int(data), problematic_items
        elif isinstance(data, (np.float16, np.float32, np.float64)):
            problematic_items.append(f"{path}: {original_type} -> float")
            return float(data), problematic_items
        elif isinstance(data, np.ndarray):
            if data.size == 1:
                return data.item(), problematic_items
            else:
                return data.tolist(), problematic_items
        elif hasattr(data, 'item'):  # 其他numpy标量
            return data.item(), problematic_items
        elif pd.isna(data):
            return None, problematic_items
        else:
            return data, problematic_items

def clean_data_before_report(results, config_dict):
    """在生成报告前彻底清理数据"""
    # print(f"\n🔍 深度清理JSON序列化问题...")
    
    # 清理results
    cleaned_results, result_problems = deep_clean_for_json(results, "results")
    
    # 清理config_dict  
    cleaned_config, config_problems = deep_clean_for_json(config_dict, "config_dict")
    
    return cleaned_results, cleaned_config
def quick_backtest(config_manager: ConfigManager, data_manager: DataManager, 
                  report_generator: ReportGenerator):
    """快速回测 - 增强版"""
    print("\n🚀 快速回测模式（增强版）")
    print("=" * 50)
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 选择增强功能
    use_dynamic_leverage = safe_confirm("🎯 是否使用动态杠杆管理?", default=True)
    if use_dynamic_leverage:
        print("✅ 启用动态杠杆管理 - 根据信号质量和市场波动自动调节杠杆")
    
    trading_params = config_manager.trading_params
    backtest_params = config_manager.backtest_params
    
    # 获取数据
    if data_source == 'local':
        symbol, interval = interactive_select_local_data()
        if not symbol or not interval:
            print("❌ 未选择有效数据")
            return
        
        backtest_params.symbol = symbol
        backtest_params.interval = interval
        data = load_local_data(symbol, interval)
        if data is None:
            print("❌ 数据加载失败")
            return
    else:
        # 在线数据 - 智能币种选择
        symbol = _select_online_symbol(data_manager, backtest_params)
        if not symbol:
            return
        
        # 选择时间周期
        interval = _select_time_interval(backtest_params)
        if not interval:
            return
        
        backtest_params.symbol = symbol
        backtest_params.interval = interval
        
        print(f"📊 获取 {backtest_params.symbol} {backtest_params.interval} 数据...")
        data = data_manager.get_historical_data(
            symbol=backtest_params.symbol,
            interval=backtest_params.interval,
            start_date=backtest_params.start_date,
            end_date=backtest_params.end_date
        )
        
        if data is None or len(data) < 100:
            print("❌ 数据获取失败或数据不足")
            return
    
    # 显示数据信息
    _display_data_info(data, backtest_params)
    
    # 运行增强版回测
    print(f"\n🚀 开始回测...")
    print(f"💡 使用放宽版信号执行条件，提高交易频率")
    
    results = run_enhanced_backtest(
        data=data, 
        trading_params=trading_params, 
        backtest_params=backtest_params,
        use_dynamic_leverage=use_dynamic_leverage
    )
    
    # 生成报告配置
    config_dict = _prepare_report_config(
        backtest_params, trading_params, data_source, use_dynamic_leverage, results
    )
    
    # 生成增强版报告
    _generate_and_open_report(data, results, config_dict)
    
    print("🔙 返回主菜单")

def custom_backtest(config_manager: ConfigManager, data_manager: DataManager,
                   report_generator: ReportGenerator):
    """自定义配置回测 - 增强版"""
    print("\n⚙️ 自定义配置回测（增强版）")
    print("=" * 50)
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 交互式配置参数
    print("\n🔧 开始参数配置...")
    config_manager.interactive_config()
    
    # 显示当前配置
    print("\n📋 当前配置摘要:")
    config_manager.print_current_config()
    
    # 选择增强功能
    use_dynamic_leverage = safe_confirm("🎯 是否使用动态杠杆管理?", default=True)
    
    # 验证配置
    if not config_manager.validate_config():
        print("⚠️ 配置验证发现问题")
        continue_anyway = safe_confirm("是否继续执行回测?", default=False)
        if not continue_anyway:
            return
    
    # 保存配置选项
    save_config = safe_confirm("💾 是否保存当前配置为默认配置？", default=True)
    if save_config:
        try:
            config_manager.save_config()
            print("✅ 配置已保存")
        except Exception as e:
            print(f"⚠️ 配置保存失败: {e}")
    
    # 获取数据
    if data_source == 'local':
        symbol, interval = interactive_select_local_data()
        if not symbol or not interval:
            print("❌ 未选择有效数据")
            return
        
        config_manager.backtest_params.symbol = symbol
        config_manager.backtest_params.interval = interval
        data = load_local_data(symbol, interval)
        if data is None:
            print("❌ 数据加载失败")
            return
    else:
        symbol = config_manager.backtest_params.symbol
        print(f"📊 获取 {symbol} 数据...")
        
        data = data_manager.get_historical_data(
            symbol=symbol,
            interval=config_manager.backtest_params.interval,
            start_date=config_manager.backtest_params.start_date,
            end_date=config_manager.backtest_params.end_date
        )
        
        if data is None or len(data) < 100:
            print("❌ 数据获取失败或数据不足")
            return
    
    # 显示数据信息
    _display_data_info(data, config_manager.backtest_params)
    
    # 最终确认
    final_confirm = safe_confirm("🚀 确认开始回测?", default=True)
    if not final_confirm:
        print("❌ 回测已取消")
        return
    
    # 运行增强版回测
    results = run_enhanced_backtest(
        data=data, 
        trading_params=config_manager.trading_params, 
        backtest_params=config_manager.backtest_params,
        use_dynamic_leverage=use_dynamic_leverage
    )
    
    # 生成报告配置
    config_dict = config_manager.trading_params.__dict__.copy()
    config_dict.update(config_manager.backtest_params.__dict__)
    config_dict['data_source'] = data_source
    config_dict['use_dynamic_leverage'] = use_dynamic_leverage
    config_dict.update(_extract_signal_quality_info(results))
    
    # 生成增强版报告
    _generate_and_open_report(data, results, config_dict)
    
    print("🔙 返回主菜单")

def multi_symbol_backtest(config_manager: ConfigManager, data_manager: DataManager, 
                         report_generator: ReportGenerator):
    """多币种同时回测"""
    print("\n🎯 多币种同时回测模式")
    print("=" * 50)
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 选择币种
    symbols_to_test = _select_multiple_symbols(data_source, data_manager)
    if not symbols_to_test:
        print("❌ 未选择任何币种")
        return
    
    # 选择时间周期
    if data_source == 'local':
        selected_interval = _select_interval_for_local_symbols(symbols_to_test)
    else:
        selected_interval = config_manager.backtest_params.interval
    
    if not selected_interval:
        print("❌ 未选择时间周期")
        return
    
    # 选择增强功能
    use_dynamic_leverage = safe_confirm("🎯 是否使用动态杠杆管理?", default=True)
    
    # 显示回测计划
    print(f"\n📊 多币种回测计划:")
    print(f"   币种数量: {len(symbols_to_test)}")
    print(f"   时间周期: {selected_interval}")
    print(f"   动态杠杆: {'启用' if use_dynamic_leverage else '禁用'}")
    print(f"   每币种初始资金: {config_manager.backtest_params.initial_cash:,.0f} USDT")
    print(f"   预计总投入: {config_manager.backtest_params.initial_cash * len(symbols_to_test):,.0f} USDT")
    
    # 最终确认
    final_confirm = safe_confirm("🚀 确认开始多币种回测?", default=True)
    if not final_confirm:
        print("❌ 回测已取消")
        return
    
    # 执行多币种回测
    multi_results = _execute_multi_symbol_backtest(
        symbols_to_test, selected_interval, data_source, 
        config_manager, data_manager, use_dynamic_leverage
    )
    
    if not multi_results:
        print("❌ 所有币种回测均失败")
        return
    
    # 显示汇总结果
    _display_multi_symbol_summary(multi_results, config_manager.backtest_params.initial_cash)
    
    # 生成多币种报告
    _generate_multi_symbol_report(multi_results, config_manager, data_source, use_dynamic_leverage)
    
    print("🔙 返回主菜单")

def parameter_optimization(config_manager: ConfigManager, data_manager: DataManager):
    """参数优化功能"""
    print("\n🔧 智能参数优化模式")
    print("=" * 50)
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 选择优化类型
    optimization_choices = [
        ('🎯 网格搜索 (全面但耗时)', 'grid'),
        ('🎲 随机搜索 (快速采样)', 'random'),
        ('📋 预设配置测试', 'preset'),
        ('🧠 智能优化 (贝叶斯)', 'bayesian')
    ]
    
    optimization_type = safe_list_input("选择优化方式", choices=optimization_choices)
    if optimization_type is None:
        return
    
    # 获取数据
    if data_source == 'local':
        symbol, interval = interactive_select_local_data()
        if not symbol or not interval:
            print("❌ 未选择有效数据")
            return
        
        data = load_local_data(symbol, interval)
        if data is None:
            print("❌ 数据加载失败")
            return
    else:
        # 在线数据
        symbol = config_manager.backtest_params.symbol
        print(f"📊 获取 {symbol} 数据...")
        
        data = data_manager.get_historical_data(
            symbol=symbol,
            interval=config_manager.backtest_params.interval,
            start_date=config_manager.backtest_params.start_date,
            end_date=config_manager.backtest_params.end_date
        )
        
        if data is None or len(data) < 100:
            print("❌ 数据获取失败或数据不足")
            return
    
    # 设置优化参数
    optimization_config = _configure_optimization(optimization_type)
    if not optimization_config:
        return
    
    print(f"\n🚀 开始智能参数优化...")
    print(f"📊 优化方式: {optimization_type}")
    print(f"📈 数据长度: {len(data)} 条")
    print(f"⚡ 并行进程: {optimization_config.get('max_workers', 4)}")
    print(f"🎯 测试组合: {optimization_config.get('max_iterations', 100)}")
    
    # 执行优化
    try:
        optimizer = ParameterOptimizer()
        optimization_results = optimizer.optimize_parameters(
            data=data,
            optimization_type=optimization_type,
            **optimization_config
        )
        
        if optimization_results:
            # 显示结果
            print("\n📊 优化结果:")
            optimizer.print_optimization_results(optimization_results)
            
            # 询问是否应用最佳参数
            apply_best = safe_confirm("🎯 是否应用最佳参数到配置文件?", default=True)
            if apply_best:
                optimizer.apply_best_params(optimization_results)
                print("✅ 最佳参数已应用到配置")
            
            # 询问是否保存结果
            save_results = safe_confirm("💾 是否保存优化结果?", default=True)
            if save_results:
                saved_path = optimizer.save_optimization_results(optimization_results)
                print(f"✅ 优化结果已保存: {saved_path}")
                
            # 询问是否生成优化报告
            generate_report = safe_confirm("📊 是否生成优化报告?", default=True)
            if generate_report:
                try:
                    from report_generator import ReportGenerator
                    report_gen = ReportGenerator()
                    report_path = report_gen.generate_optimization_report(
                        optimization_results, 
                        optimizer.get_parameter_space(),
                        f"optimization_report_{symbol}_{interval}.html"
                    )
                    
                    # 询问是否打开报告
                    open_report = safe_confirm("🌐 是否在浏览器中打开报告?", default=True)
                    if open_report:
                        report_gen.open_report_in_browser(report_path)
                        
                except Exception as e:
                    print(f"❌ 报告生成失败: {e}")
                    
        else:
            print("❌ 参数优化失败，未找到有效结果")
            print("💡 建议:")
            print("   1. 检查数据质量和数量")
            print("   2. 调整优化参数范围")
            print("   3. 尝试其他优化方法")
            
    except Exception as e:
        print(f"❌ 参数优化过程出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 提供错误恢复建议
        print("\n🔧 错误排查建议:")
        print("   1. 检查内存使用情况")
        print("   2. 减少并行进程数量")
        print("   3. 缩小参数搜索范围")
        print("   4. 检查数据格式是否正确")

# 辅助函数

def _select_online_symbol(data_manager: DataManager, backtest_params: BacktestParams) -> Optional[str]:
    """选择在线币种"""
    try:
        print("📊 获取热门币种列表...")
        all_symbols = data_manager.get_top_symbols(20)
        
        if not all_symbols:
            print("⚠️ 获取币种列表失败，使用默认列表")
            all_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT', 
                          'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT']
        
        # 创建选择列表（显示前10个热门币种）
        symbol_choices = []
        for i, symbol in enumerate(all_symbols[:10], 1):
            symbol_choices.append((f"{i:2d}. {symbol}", symbol))
        
        # 选择币种
        selected_symbol = safe_list_input("选择交易对", choices=symbol_choices)
        return selected_symbol
        
    except Exception as e:
        print(f"❌ 获取币种列表失败: {e}")
        print("使用默认币种BTCUSDT")
        return 'BTCUSDT'

def _select_time_interval(backtest_params: BacktestParams) -> Optional[str]:
    """选择时间周期"""
    interval_choices = [
        ('1分钟 (1m) - 高频交易', '1m'),
        ('5分钟 (5m) - 短线交易', '5m'),
        ('15分钟 (15m) - 日内交易', '15m'),
        ('30分钟 (30m) - 日内波段', '30m'),
        ('1小时 (1h) - 中短线', '1h'),
        ('4小时 (4h) - 中线交易', '4h'),
        ('1天 (1d) - 长线交易', '1d')
    ]
    
    selected_interval = safe_list_input("选择时间周期", choices=interval_choices)
    return selected_interval if selected_interval else '1h'  # 默认1小时

def _display_data_info(data, backtest_params):
    """显示数据信息"""
    print(f"\n📊 数据信息:")
    print(f"  币种: {backtest_params.symbol}")
    print(f"  周期: {backtest_params.interval}")
    print(f"  数据量: {len(data):,} 条")
    
    if 'timestamp' in data.columns:
        start_time = data['timestamp'].min().strftime('%Y-%m-%d %H:%M')
        end_time = data['timestamp'].max().strftime('%Y-%m-%d %H:%M')
        duration = (data['timestamp'].max() - data['timestamp'].min()).days
        print(f"  时间范围: {start_time} ~ {end_time} ({duration} 天)")
    
    # 简单的数据质量检查
    missing_data = data.isnull().sum().sum()
    if missing_data > 0:
        print(f"  ⚠️ 缺失数据: {missing_data} 个字段")
    else:
        print(f"  ✅ 数据完整性良好")

def _prepare_report_config(backtest_params, trading_params, data_source, use_dynamic_leverage, results):
    """准备报告配置"""
    config_dict = {
        'symbol': backtest_params.symbol,
        'interval': backtest_params.interval,
        'leverage': trading_params.leverage,
        'risk_per_trade': trading_params.risk_per_trade,
        'stop_loss_pct': trading_params.stop_loss_pct,
        'take_profit_pct': trading_params.take_profit_pct,
        'data_source': data_source,
        'use_dynamic_leverage': use_dynamic_leverage,
    }
    
    # 添加信号质量信息
    config_dict.update(_extract_signal_quality_info(results))
    
    return config_dict

def _extract_signal_quality_info(results):
    """提取信号质量信息"""
    return {
        'signal_execution_rate': results.get('signal_stats', {}).get('signal_execution_rate', 0),
        'avg_signal_strength': results.get('avg_signal_strength', 0),
        'avg_confidence_score': results.get('avg_confidence_score', 0),
        'trend_alignment_rate': results.get('trend_alignment_rate', 0),
        'total_signals': results.get('signal_stats', {}).get('total_signals', 0),
        'high_quality_signals': results.get('signal_stats', {}).get('high_quality_signals', 0)
    }

def _generate_and_open_report(data, results, config_dict):
    """生成并打开报告"""
    print("\n📊 生成增强版回测报告...")
    try:
        enhanced_generator = EnhancedReportGenerator()
        report_path = enhanced_generator.generate_enhanced_backtest_report(data, results, config_dict)
        
        print("🚀 自动在浏览器中打开报告...")
        enhanced_generator.open_report_in_browser(report_path)
        
    except Exception as e:
        print(f"❌ 增强版报告生成失败: {e}")
        print("🔄 尝试生成标准报告...")
        try:
            from report_generator import ReportGenerator
            report_gen = ReportGenerator()
            report_path = report_gen.generate_backtest_report(data, results, config_dict)
            
            auto_open = safe_confirm("是否在浏览器中打开标准报告?", default=True)
            if auto_open:
                report_gen.open_report_in_browser(report_path)
                
        except Exception as e2:
            print(f"❌ 标准报告也生成失败: {e2}")

def _select_multiple_symbols(data_source, data_manager):
    """选择多个币种"""
    symbols_to_test = []
    
    if data_source == 'local':
        local_data = get_local_data_summary()
        if not local_data:
            print("❌ 未找到本地数据")
            return []
        
        print(f"\n📁 发现 {len(local_data)} 个币种的本地数据")
        
        # 批量选择或预设组合
        selection_choices = [
            ('🎯 热门币种组合 (BTC, ETH, BNB等)', 'popular'),
            ('📊 主流币种组合 (包含DeFi币种)', 'major'),
            ('🔧 自定义选择币种', 'custom'),
            ('📈 全部本地币种', 'all')
        ]
        
        selection_type = safe_list_input("选择币种方式", choices=selection_choices)
        if selection_type is None:
            return []
        
        if selection_type == 'popular':
            popular_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT']
            symbols_to_test = [s for s in popular_symbols if s in local_data]
        elif selection_type == 'major':
            major_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'DOTUSDT', 
                           'AVAXUSDT', 'MATICUSDT', 'LINKUSDT', 'UNIUSDT', 'LTCUSDT']
            symbols_to_test = [s for s in major_symbols if s in local_data]
        elif selection_type == 'all':
            symbols_to_test = list(local_data.keys())
        else:
            symbols_to_test = _custom_select_symbols(local_data)
            
    else:
        # 在线数据
        try:
            all_symbols = data_manager.get_top_symbols(20)
            
            preset_choices = [
                ('🎯 前5大币种', all_symbols[:5]),
                ('📊 前10大币种', all_symbols[:10]),
                ('🔧 自定义选择', 'custom')
            ]
            
            preset_choice = safe_list_input("选择币种组合", choices=[(desc, symbols) for desc, symbols in preset_choices])
            if preset_choice is None:
                return []
            
            if preset_choice == 'custom':
                symbols_to_test = _custom_select_online_symbols(all_symbols)
            else:
                symbols_to_test = preset_choice
                
        except Exception as e:
            print(f"❌ 获取币种列表失败: {e}")
            return []
    
    return symbols_to_test

def _custom_select_symbols(local_data):
    """自定义选择本地币种"""
    selected_symbols = []
    
    print("\n📋 可选币种:")
    symbol_list = list(local_data.keys())
    for i, symbol in enumerate(symbol_list, 1):
        intervals = ', '.join(local_data[symbol][:3])
        if len(local_data[symbol]) > 3:
            intervals += f'... (+{len(local_data[symbol])-3}个)'
        print(f"{i:2d}. {symbol:<12} [{intervals}]")
    
    while True:
        symbol_input = safe_text_input("输入币种编号(用逗号分隔,如:1,2,3)或直接回车结束", default="")
        if not symbol_input:
            break
        
        try:
            indices = [int(x.strip()) for x in symbol_input.split(',')]
            for idx in indices:
                if 1 <= idx <= len(symbol_list):
                    symbol = symbol_list[idx-1]
                    if symbol not in selected_symbols:
                        selected_symbols.append(symbol)
            
            if selected_symbols:
                print(f"✅ 已选择: {', '.join(selected_symbols)}")
                break
        except:
            print("❌ 输入格式错误，请重新输入")
    
    return selected_symbols

def _custom_select_online_symbols(all_symbols):
    """自定义选择在线币种"""
    symbols_to_test = []
    
    print("\n📋 可选币种 (按交易量排序):")
    for i, symbol in enumerate(all_symbols, 1):
        print(f"{i:2d}. {symbol}")
    
    symbol_input = safe_text_input("输入币种编号(用逗号分隔,如:1,2,3)", default="1,2,3")
    if not symbol_input:
        return []
    
    try:
        indices = [int(x.strip()) for x in symbol_input.split(',')]
        for idx in indices:
            if 1 <= idx <= len(all_symbols):
                symbols_to_test.append(all_symbols[idx-1])
    except:
        print("❌ 输入格式错误")
        return []
    
    return symbols_to_test

def _select_interval_for_local_symbols(symbols_to_test):
    """为本地币种选择时间周期"""
    local_data = get_local_data_summary()
    
    # 找到所有币种共同的时间周期
    available_intervals = set(local_data[symbols_to_test[0]])
    for symbol in symbols_to_test[1:]:
        available_intervals = available_intervals.intersection(set(local_data[symbol]))
    
    if not available_intervals:
        print("❌ 选择的币种没有共同的时间周期")
        return None
    
    interval_choices = [(interval, interval) for interval in sorted(available_intervals)]
    selected_interval = safe_list_input("选择时间周期", choices=interval_choices)
    
    return selected_interval

def _execute_multi_symbol_backtest(symbols_to_test, selected_interval, data_source, 
                                  config_manager, data_manager, use_dynamic_leverage):
    """执行多币种回测"""
    multi_results = {}
    total_initial_cash = 0
    total_final_value = 0
    
    for i, symbol in enumerate(symbols_to_test, 1):
        print(f"\n[{i}/{len(symbols_to_test)}] 📊 回测 {symbol}...")
        
        # 获取数据
        if data_source == 'local':
            data = load_local_data(symbol, selected_interval)
        else:
            data = data_manager.get_historical_data(
                symbol=symbol,
                interval=selected_interval,
                start_date=config_manager.backtest_params.start_date,
                end_date=config_manager.backtest_params.end_date
            )
        
        if data is None or len(data) < 100:
            print(f"❌ {symbol} 数据不足，跳过")
            continue
        
        # 创建该币种的回测参数
        from config import BacktestParams
        symbol_backtest_params = BacktestParams(
            symbol=symbol,
            interval=selected_interval,
            initial_cash=config_manager.backtest_params.initial_cash,
            commission=config_manager.backtest_params.commission,
            start_date=config_manager.backtest_params.start_date,
            end_date=config_manager.backtest_params.end_date
        )
        
        # 运行回测
        try:
            results = run_enhanced_backtest(
                data=data,
                trading_params=config_manager.trading_params,
                backtest_params=symbol_backtest_params,
                use_dynamic_leverage=use_dynamic_leverage
            )
            
            multi_results[symbol] = {
                'results': results,
                'data': data,
                'symbol': symbol,
                'interval': selected_interval
            }
            
            total_initial_cash += results['initial_cash']
            total_final_value += results['final_value']
            
            # 显示简要结果
            print(f"✅ {symbol}: {results['total_return']:+.2f}% | "
                  f"交易: {results['total_trades']} | "
                  f"胜率: {results['win_rate']:.1f}% | "
                  f"信号: {results.get('signal_stats', {}).get('executed_signals', 0)}")
            
        except Exception as e:
            print(f"❌ {symbol} 回测失败: {e}")
            continue
    
    return multi_results

def _display_multi_symbol_summary(multi_results, initial_cash_per_symbol):
    """显示多币种回测汇总"""
    total_initial_cash = initial_cash_per_symbol * len(multi_results)
    total_final_value = sum(result['results']['final_value'] for result in multi_results.values())
    total_return = (total_final_value - total_initial_cash) / total_initial_cash * 100 if total_initial_cash > 0 else 0
    
    print(f"\n🎯 多币种回测汇总:")
    print(f"📊 成功回测币种: {len(multi_results)}")
    print(f"💰 总投入资金: {total_initial_cash:,.0f} USDT")
    print(f"💰 总最终价值: {total_final_value:,.0f} USDT")
    print(f"📈 总体收益率: {total_return:+.2f}%")
    
    # 按收益率排序显示
    sorted_results = sorted(multi_results.items(), key=lambda x: x[1]['results']['total_return'], reverse=True)
    
    print(f"\n📊 各币种表现排行:")
    print(f"{'排名':<4} {'币种':<12} {'收益率':<10} {'交易数':<8} {'胜率':<8} {'信号数':<8} {'最大回撤':<10}")
    print("-" * 80)
    
    for rank, (symbol, data) in enumerate(sorted_results, 1):
        results = data['results']
        signal_count = results.get('signal_stats', {}).get('executed_signals', 0)
        
        print(f"{rank:<4} {symbol:<12} {results['total_return']:>+8.2f}% {results['total_trades']:>6} "
              f"{results['win_rate']:>6.1f}% {signal_count:>6} {results['max_drawdown']*100:>8.2f}%")

def _generate_multi_symbol_report(multi_results, config_manager, data_source, use_dynamic_leverage):
    """生成多币种报告"""
    print("\n📊 生成多币种回测报告...")
    try:
        enhanced_generator = EnhancedReportGenerator()
        
        # 计算总体统计
        total_initial_cash = sum(result['results']['initial_cash'] for result in multi_results.values())
        total_final_value = sum(result['results']['final_value'] for result in multi_results.values())
        total_return = (total_final_value - total_initial_cash) / total_initial_cash * 100 if total_initial_cash > 0 else 0
        
        report_config = {
            'data_source': data_source,
            'use_dynamic_leverage': use_dynamic_leverage,
            'total_initial_cash': total_initial_cash,
            'total_final_value': total_final_value,
            'total_return': total_return,
            'config': config_manager.trading_params.__dict__
        }
        
        report_path = enhanced_generator.generate_multi_symbol_report(multi_results, report_config)
        
        print("🚀 自动在浏览器中打开报告...")
        enhanced_generator.open_report_in_browser(report_path)
        
    except Exception as e:
        print(f"❌ 多币种报告生成失败: {e}")
        import traceback
        traceback.print_exc()

def _configure_optimization(optimization_type):
    """配置优化参数"""
    config = {}
    
    if optimization_type == 'grid':
        max_workers = safe_text_input("并行进程数 (默认4)", default="4")
        try:
            config['max_workers'] = int(max_workers)
        except:
            config['max_workers'] = 4
            
    elif optimization_type == 'random':
        max_iterations = safe_text_input("随机测试次数 (默认100)", default="100")
        try:
            config['max_iterations'] = int(max_iterations)
        except:
            config['max_iterations'] = 100
            
    elif optimization_type == 'bayesian':
        max_iterations = safe_text_input("优化迭代次数 (默认50)", default="50")
        try:
            config['max_iterations'] = int(max_iterations)
        except:
            config['max_iterations'] = 50
    
    # 通用配置
    config['max_workers'] = config.get('max_workers', 2)
    
    return config
# ============================================================================
# 添加到 menu_handlers.py 文件末尾的新函数
# ============================================================================

def quick_backtest_with_trend(config_manager: ConfigManager, data_manager: DataManager, 
                             report_generator: ReportGenerator):
    """快速回测 - 趋势跟踪版"""
    print("\n🚀 快速回测 - 趋势跟踪版")
    print("=" * 50)
    
    # 选择数据源（参考原有函数）
    data_source_choices = [
        ('📁 使用本地下载数据', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 选择增强功能
    use_dynamic_leverage = safe_confirm("🎯 是否使用动态杠杆管理?", default=True)
    if use_dynamic_leverage:
        print("✅ 启用动态杠杆管理 - 根据信号质量和市场波动自动调节杠杆")
    
    # 获取数据
    if data_source == 'local':
        selected_data = interactive_select_local_data()
        if not selected_data:
            print("❌ 未选择有效数据")
            return
        
        symbol, interval = selected_data
        data = load_local_data(symbol, interval)
        if data is None:
            print("❌ 数据加载失败")
            return
    else:
        # 在线数据 - 智能币种选择
        symbol = _select_online_symbol(data_manager, config_manager.backtest_params)
        if not symbol:
            return
        
        # 选择时间周期
        interval = _select_time_interval(config_manager.backtest_params)
        if not interval:
            return
        
        print(f"📊 获取 {symbol} {interval} 数据...")
        data = data_manager.get_historical_data(
            symbol=symbol,
            interval=interval,
            start_date=config_manager.backtest_params.start_date,
            end_date=config_manager.backtest_params.end_date
        )
        
        if data is None or len(data) < 100:
            print("❌ 数据获取失败或数据不足")
            return
    
    # 显示数据信息
    _display_data_info(data, type('BacktestParams', (), {'symbol': symbol, 'interval': interval})())
    
    # 使用默认配置
    trading_params = TradingParams(
        risk_per_trade=0.02,
        leverage=10,
        max_positions=3
    )
    
    from config import BacktestParams
    backtest_params = BacktestParams(
        symbol=symbol,
        interval=interval,
        initial_cash=10000,
        commission=0.0005
    )
    
    print("\n🎯 启动趋势跟踪版回测...")
    print("   - 启用趋势跟踪系统")
    print("   - 启用动态杠杆管理" if use_dynamic_leverage else "   - 使用固定杠杆")
    print("   - 启用智能部分平仓")
    
    # 运行趋势跟踪版回测
    results = run_enhanced_backtest(
        data=data,
        trading_params=trading_params,
        backtest_params=backtest_params,
        detector_config=None,  # 使用默认放宽配置
        use_dynamic_leverage=use_dynamic_leverage
    )
    
    # 显示结果
    print(f"\n📈 回测结果:")
    print(f"   总收益率: {results['total_return']:.2f}%")
    print(f"   总交易数: {results['total_trades']}")
    print(f"   胜率: {results['win_rate']:.1f}%")
    print(f"   盈亏比: {results.get('profit_factor', 0):.2f}")
    print(f"   最大回撤: {results['max_drawdown']*100:.2f}%")
    print(f"   趋势跟踪交易: {results.get('trend_tracking_trades', 0)}笔")
    print(f"   平均最大浮盈: {results.get('avg_max_profit_seen', 0):.2f}%")
    
    # 准备报告配置（参考原有函数）
    config_dict = _prepare_report_config(
        backtest_params, trading_params, data_source, use_dynamic_leverage, results
    )
    # config_dict['strategy_type'] = 'trend_tracking'
    # 彻底清理数据
    cleaned_results, cleaned_config = clean_data_before_report(results, config_dict)

    # 生成增强版报告（使用原有的报告生成函数）
    # _generate_and_open_report(data, results, config_dict)
    _generate_and_open_report(data, cleaned_results, cleaned_config)

def ab_test_strategies(config_manager: ConfigManager, data_manager: DataManager, 
                      report_generator: ReportGenerator):
    """A/B测试：对比原策略和趋势跟踪策略"""
    print("\n🆚 A/B测试 - 策略对比分析")
    print("=" * 50)
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 获取数据
    if data_source == 'local':
        selected_data = interactive_select_local_data()
        if not selected_data:
            print("❌ 未选择有效数据")
            return
        
        symbol, interval = selected_data
        data = load_local_data(symbol, interval)
        if data is None:
            print("❌ 数据加载失败")
            return
    else:
        # 在线数据
        symbol = _select_online_symbol(data_manager, config_manager.backtest_params)
        if not symbol:
            return
        
        interval = _select_time_interval(config_manager.backtest_params)
        if not interval:
            return
        
        print(f"📊 获取 {symbol} {interval} 数据...")
        data = data_manager.get_historical_data(
            symbol=symbol,
            interval=interval,
            start_date=config_manager.backtest_params.start_date,
            end_date=config_manager.backtest_params.end_date
        )
        
        if data is None or len(data) < 100:
            print("❌ 数据获取失败或数据不足")
            return
    
    print(f"📊 开始A/B测试: {symbol} {interval}")
    print(f"   数据量: {len(data)} 条")
    
    # 统一参数
    trading_params = TradingParams(
        risk_per_trade=0.02,
        leverage=10,
        max_positions=3
    )
    
    from config import BacktestParams
    backtest_params = BacktestParams(
        symbol=symbol,
        interval=interval,
        initial_cash=10000,
        commission=0.0005
    )
    
    print("\n🔄 正在运行原版策略...")
    # 原版策略（严格参数）
    original_config = {
        'min_shadow_body_ratio': 3.0,
        'max_body_ratio': 0.20,
        'min_signal_score': 4,
        'require_confirmation': True
    }
    
    original_results = run_enhanced_backtest(
        data=data,
        trading_params=trading_params,
        backtest_params=backtest_params,
        detector_config=original_config,
        use_dynamic_leverage=False  # 原版不使用动态杠杆
    )
    
    print("\n🔄 正在运行趋势跟踪版策略...")
    # 趋势跟踪版（使用默认放宽配置）
    trend_results = run_enhanced_backtest(
        data=data,
        trading_params=trading_params,
        backtest_params=backtest_params,
        detector_config=None,  # 使用放宽配置
        use_dynamic_leverage=True
    )
    
    # 对比分析
    print("\n" + "="*60)
    print("📊 A/B测试结果对比")
    print("="*60)
    
    metrics = [
        ('总收益率', 'total_return', '%'),
        ('总交易数', 'total_trades', '笔'),
        ('胜率', 'win_rate', '%'),
        ('盈亏比', 'profit_factor', ''),
        ('最大回撤', 'max_drawdown', '%'),
    ]
    
    print(f"{'指标':<15} {'原版策略':<15} {'趋势跟踪版':<15} {'改进幅度':<15}")
    print("-" * 60)
    
    for metric_name, metric_key, unit in metrics:
        original_val = original_results.get(metric_key, 0)
        trend_val = trend_results.get(metric_key, 0)
        
        if metric_key == 'max_drawdown':
            original_val *= 100
            trend_val *= 100
        
        if original_val != 0:
            improvement = ((trend_val - original_val) / original_val) * 100
            improvement_str = f"{improvement:+.1f}%"
        else:
            improvement_str = "N/A"
        
        print(f"{metric_name:<15} {original_val:<15.2f}{unit:<3} {trend_val:<15.2f}{unit:<3} {improvement_str:<15}")
    
    # 特殊指标
    print("\n📈 趋势跟踪特有指标:")
    print(f"   趋势跟踪交易数: {trend_results.get('trend_tracking_trades', 0)}笔")
    print(f"   平均最大浮盈: {trend_results.get('avg_max_profit_seen', 0):.2f}%")
    
    # 结论
    if trend_results['total_return'] > original_results['total_return']:
        print("\n✅ 趋势跟踪版策略表现更优！")
    else:
        print("\n⚠️  原版策略在此数据集上表现更好，建议进一步调优")
    
    # 生成A/B对比报告
    generate_comparison_report = safe_confirm("\n📊 是否生成A/B对比报告?", default=True)
    if generate_comparison_report:
        try:
            _generate_ab_test_report(original_results, trend_results, symbol, interval, data)
        except Exception as e:
            print(f"❌ A/B对比报告生成失败: {e}")

def adaptive_parameter_tuning(config_manager: ConfigManager, data_manager: DataManager):
    """自适应参数调优"""
    print("\n📊 自适应参数调优")
    print("=" * 50)
    print("   基于市场特征自动优化策略参数")
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 获取数据
    if data_source == 'local':
        selected_data = interactive_select_local_data()
        if not selected_data:
            print("❌ 未选择有效数据")
            return
        
        symbol, interval = selected_data
        data = load_local_data(symbol, interval)
        if data is None:
            print("❌ 数据加载失败")
            return
    else:
        # 在线数据
        symbol = _select_online_symbol(data_manager, config_manager.backtest_params)
        if not symbol:
            return
        
        interval = _select_time_interval(config_manager.backtest_params)
        if not interval:
            return
        
        print(f"📊 获取 {symbol} {interval} 数据...")
        data = data_manager.get_historical_data(
            symbol=symbol,
            interval=interval,
            start_date=config_manager.backtest_params.start_date,
            end_date=config_manager.backtest_params.end_date
        )
        
        if data is None or len(data) < 100:
            print("❌ 数据获取失败或数据不足")
            return
    
    print(f"📊 开始参数调优: {symbol} {interval}")
    
    # 市场特征分析
    try:
        from adaptive_parameter_system import AdaptiveParameterSystem
        
        adaptive_system = AdaptiveParameterSystem()
        market_features = adaptive_system.analyze_market_characteristics(data)
        
        print("\n📈 市场特征分析:")
        print(f"   平均波动率: {market_features.volatility:.2f}%")
        print(f"   趋势强度: {market_features.trend_strength:.2f}")
        print(f"   市场类型: {market_features.market_type.value}")
        
        # 基于市场特征调整参数
        optimized_params = adaptive_system.get_optimized_parameters(market_features)
        
        print("\n🔧 优化后参数:")
        for param, value in optimized_params.items():
            print(f"   {param}: {value}")
        
        # 测试优化参数
        trading_params = TradingParams(
            risk_per_trade=0.02,
            leverage=10,
            max_positions=3
        )
        
        from config import BacktestParams
        backtest_params = BacktestParams(
            symbol=symbol,
            interval=interval,
            initial_cash=10000,
            commission=0.0005
        )
        
        print("\n🔄 测试优化参数...")
        results = run_enhanced_backtest(
            data=data,
            trading_params=trading_params,
            backtest_params=backtest_params,
            detector_config=optimized_params,
            use_dynamic_leverage=True
        )
        
        print(f"\n📈 优化后回测结果:")
        print(f"   总收益率: {results['total_return']:.2f}%")
        print(f"   总交易数: {results['total_trades']}")
        print(f"   胜率: {results['win_rate']:.1f}%")
        
        # 生成优化报告
        report = adaptive_system.generate_optimization_report(market_features, optimized_params)
        print(report)
        
        # 保存优化参数选项
        save_params = safe_confirm("\n💾 是否保存优化后的参数?", default=True)
        if save_params:
            import json
            import os
            
            save_dir = "optimization_results"
            os.makedirs(save_dir, exist_ok=True)
            
            save_data = {
                'symbol': symbol,
                'interval': interval,
                'market_features': {
                    'volatility': market_features.volatility,
                    'trend_strength': market_features.trend_strength,
                    'market_type': market_features.market_type.value
                },
                'optimized_params': optimized_params,
                'results': {
                    'total_return': results['total_return'],
                    'total_trades': results['total_trades'],
                    'win_rate': results['win_rate']
                }
            }
            
            filename = f"adaptive_params_{symbol}_{interval}.json"
            filepath = os.path.join(save_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 参数已保存: {filepath}")
        
    except ImportError:
        print("❌ 自适应参数系统模块未找到")
        print("   请确保 adaptive_parameter_system.py 文件存在")
    except Exception as e:
        print(f"❌ 参数调优失败: {e}")

def multi_timeframe_analysis(config_manager: ConfigManager, data_manager: DataManager, 
                           report_generator: ReportGenerator):
    """多周期趋势确认分析"""
    print("\n📈 多周期趋势确认分析")
    print("=" * 50)
    print("   结合多个时间周期进行趋势确认")
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据 (推荐)', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 获取主要数据
    if data_source == 'local':
        selected_data = interactive_select_local_data()
        if not selected_data:
            print("❌ 未选择有效数据")
            return
        
        symbol, primary_interval = selected_data
    else:
        # 在线数据
        symbol = _select_online_symbol(data_manager, config_manager.backtest_params)
        if not symbol:
            return
        
        primary_interval = _select_time_interval(config_manager.backtest_params)
        if not primary_interval:
            return
    
    # 定义周期层级
    timeframes = {
        '1m': ['5m', '15m', '1h'],
        '5m': ['15m', '1h', '4h'],
        '15m': ['1h', '4h', '1d'],
        '1h': ['4h', '1d', '1w'],
        '4h': ['1d', '1w', '1M'],
        '1d': ['1w', '1M']
    }
    
    higher_timeframes = timeframes.get(primary_interval, ['1h', '4h', '1d'])
    
    print(f"📊 主周期: {symbol} {primary_interval}")
    print(f"📊 高级周期: {', '.join(higher_timeframes)}")
    
    # 加载多周期数据
    all_data = {}
    
    if data_source == 'local':
        # 本地数据加载
        all_data[primary_interval] = load_local_data(symbol, primary_interval)
        
        for tf in higher_timeframes:
            data = load_local_data(symbol, tf)
            if data is not None:
                all_data[tf] = data
                print(f"✅ 加载本地 {tf} 数据: {len(data)} 条")
            else:
                print(f"❌ 未找到本地 {tf} 数据")
    else:
        # 在线数据加载
        print(f"📊 获取在线多周期数据...")
        all_timeframes = [primary_interval] + higher_timeframes
        
        for tf in all_timeframes:
            try:
                data = data_manager.get_historical_data(
                    symbol=symbol,
                    interval=tf,
                    start_date=config_manager.backtest_params.start_date,
                    end_date=config_manager.backtest_params.end_date
                )
                if data is not None and len(data) >= 50:  # 至少50条数据
                    all_data[tf] = data
                    print(f"✅ 获取在线 {tf} 数据: {len(data)} 条")
                else:
                    print(f"❌ {tf} 数据不足")
            except Exception as e:
                print(f"❌ 获取 {tf} 数据失败: {e}")
    
    if len(all_data) < 2:
        print("❌ 多周期数据不足，无法进行分析")
        return
    
    try:
        from multi_timeframe_system import MultiTimeframeAnalyzer
        
        analyzer = MultiTimeframeAnalyzer()
        analysis = analyzer.analyze_multiple_timeframes(all_data, primary_interval)
        
        # 生成并显示报告
        report = analyzer.generate_analysis_report(analysis)
        print(report)
        
        # 保存分析结果选项
        save_analysis = safe_confirm("\n💾 是否保存多周期分析结果?", default=True)
        if save_analysis:
            import json
            import os
            from datetime import datetime
            
            save_dir = "multi_timeframe_analysis"
            os.makedirs(save_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mtf_analysis_{symbol}_{primary_interval}_{timestamp}.json"
            filepath = os.path.join(save_dir, filename)
            
            # 准备保存数据
            save_data = {
                'symbol': symbol,
                'primary_interval': primary_interval,
                'analysis_timestamp': timestamp,
                'timeframes_analyzed': list(all_data.keys()),
                'analysis_results': analysis  # 这里需要确保analysis是可序列化的
            }
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
                print(f"✅ 分析结果已保存: {filepath}")
            except Exception as e:
                print(f"❌ 保存失败: {e}")
        
    except ImportError:
        print("❌ 多周期分析系统模块未找到")
        print("   请确保 multi_timeframe_system.py 文件存在")
    except Exception as e:
        print(f"❌ 多周期分析失败: {e}")

def ml_trend_optimization(config_manager: ConfigManager, data_manager: DataManager):
    """机器学习趋势识别优化"""
    print("\n🤖 机器学习趋势识别优化")
    print("=" * 50)
    print("   使用机器学习改进趋势识别准确率")
    
    # 选择数据源
    data_source_choices = [
        ('📁 使用本地下载数据 (推荐)', 'local'),
        ('🌐 在线获取数据', 'online')
    ]
    
    data_source = safe_list_input("选择数据源", choices=data_source_choices)
    if data_source is None:
        return
    
    # 获取数据
    if data_source == 'local':
        selected_data = interactive_select_local_data()
        if not selected_data:
            print("❌ 未选择有效数据")
            return
        
        symbol, interval = selected_data
        data = load_local_data(symbol, interval)
        if data is None:
            print("❌ 数据加载失败")
            return
    else:
        # 在线数据
        symbol = _select_online_symbol(data_manager, config_manager.backtest_params)
        if not symbol:
            return
        
        interval = _select_time_interval(config_manager.backtest_params)
        if not interval:
            return
        
        print(f"📊 获取 {symbol} {interval} 数据...")
        data = data_manager.get_historical_data(
            symbol=symbol,
            interval=interval,
            start_date=config_manager.backtest_params.start_date,
            end_date=config_manager.backtest_params.end_date
        )
        
        if data is None or len(data) < 1000:  # ML需要更多数据
            print("❌ 数据获取失败或数据不足 (ML训练建议至少1000条数据)")
            return
    
    print(f"📊 准备训练数据: {symbol} {interval} ({len(data)} 条)")
    
    try:
        from ml_trend_optimizer import MLTrendOptimizer
        
        ml_optimizer = MLTrendOptimizer()
        
        # 特征工程
        print("\n🔧 特征工程...")
        features = ml_optimizer.extract_comprehensive_features(data)
        print(f"   提取特征数: {features.shape[1]}")
        
        # 标签生成
        print("\n🏷️  生成标签...")
        labels = ml_optimizer.generate_labels(data, horizon=10)
        print(f"   标签数量: {len(labels)}")
        
        # 对齐特征和标签
        min_length = min(len(features), len(labels))
        features = features.iloc[:min_length]
        labels = labels.iloc[:min_length]
        
        print(f"\n📊 最终数据集:")
        print(f"   样本数: {len(features)}")
        print(f"   特征数: {features.shape[1]}")
        
        # 检查数据充足性
        if len(features) < 1000:
            print("⚠️  数据量较少，ML模型效果可能有限")
            continue_choice = safe_confirm("是否继续训练?", default=True)
            if not continue_choice:
                return
        
        # 模型训练
        print("\n🎯 训练模型...")
        model_package = ml_optimizer.train_ensemble_model(features, labels)
        
        # 保存模型
        save_option = safe_confirm("\n💾 是否保存训练好的模型?", default=True)
        if save_option:
            model_path = f"models/trend_model_{symbol}_{interval}.pkl"
            import os
            os.makedirs("models", exist_ok=True)
            ml_optimizer.save_model(model_package, model_path)
            print(f"✅ 模型已保存: {model_path}")
        
        # 测试参数优化
        print("\n🔧 测试ML参数优化...")
        optimized_params = ml_optimizer.optimize_parameters_with_ml(data, model_package)
        
        print("\n📊 ML优化后参数:")
        for param, value in optimized_params.items():
            print(f"   {param}: {value}")
        
        # 保存优化结果
        save_results = safe_confirm("\n💾 是否保存ML优化结果?", default=True)
        if save_results:
            import json
            import os
            from datetime import datetime
            
            save_dir = "ml_optimization_results"
            os.makedirs(save_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ml_optimization_{symbol}_{interval}_{timestamp}.json"
            filepath = os.path.join(save_dir, filename)
            
            save_data = {
                'symbol': symbol,
                'interval': interval,
                'timestamp': timestamp,
                'features_count': features.shape[1],
                'samples_count': len(features),
                'model_metrics': model_package.get('metrics', {}),
                'optimized_params': optimized_params
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ ML优化结果已保存: {filepath}")
        
    except ImportError:
        print("❌ 机器学习模块未安装")
        print("   请运行: pip install scikit-learn joblib")
    except Exception as e:
        print(f"❌ ML优化失败: {e}")
        import traceback
        traceback.print_exc()

def batch_training_optimization(config_manager: ConfigManager, data_manager: DataManager):
    """批量训练数据优化"""
    print("\n🎯 批量训练数据优化")
    print("=" * 50)
    print("   使用历史交易记录训练模型，优化策略参数")
    
    try:
        from batch_training_system import BatchTrainingSystem, BatchTrainingConfig
        from trade_record_collector import TradeRecordCollector
        
        # 初始化系统
        collector = TradeRecordCollector()
        batch_system = BatchTrainingSystem()
        
        # 选择数据源
        data_source_choices = [
            '📁 从现有记录文件加载',
            '📄 从CSV文件导入',
            '🔄 从回测结果收集',
            '📝 创建示例数据',
            '❌ 返回'
        ]
        
        source_choice = safe_list_input("选择数据源:", choices=data_source_choices)
        if source_choice is None or source_choice == data_source_choices[-1]:
            return
        
        trade_records = []
        
        if source_choice == data_source_choices[0]:  # 从现有文件加载
            trade_records = collector.load_records()
            
        elif source_choice == data_source_choices[1]:  # 从CSV导入
            csv_file = safe_text_input("请输入CSV文件路径:")
            if csv_file:
                trade_records = collector.collect_from_csv(csv_file)
                
        elif source_choice == data_source_choices[2]:  # 从回测结果收集
            print("⚠️  此功能需要先运行回测生成交易记录")
            print("   建议先使用其他功能进行回测，然后收集结果")
            return
            
        elif source_choice == data_source_choices[3]:  # 创建示例数据
            trade_records = collector.create_sample_records()
            save_sample = safe_confirm("是否保存示例数据?", default=True)
            if save_sample:
                collector.save_records(trade_records, append=False)
        
        if not trade_records:
            print("❌ 没有可用的交易记录")
            return
        
        # 分析现有记录
        print(f"\n📊 分析 {len(trade_records)} 条交易记录...")
        analysis = collector.analyze_records(trade_records)
        
        # 增强记录（添加市场环境数据）
        enhance_choice = safe_confirm("是否增强记录（添加市场环境数据）?", default=True)
        if enhance_choice:
            trade_records = collector.enhance_records_with_market_data(trade_records)
        
        # 准备批量训练数据
        print("\n🔧 准备批量训练数据...")
        batch_data = batch_system.prepare_batch_training_data(trade_records)
        
        if not batch_data:
            print("❌ 批量数据准备失败")
            return
        
        # 训练模型
        print("\n🎯 开始批量模型训练...")
        training_results = batch_system.train_batch_models(batch_data)
        
        # 显示训练结果
        print(f"\n📊 训练完成:")
        for model_name, metrics in training_results['metrics'].items():
            print(f"   {model_name}:")
            print(f"     训练得分: {metrics['train_score']:.3f}")
            print(f"     测试得分: {metrics['test_score']:.3f}")
        
        # 保存模型
        save_choice = safe_confirm("是否保存训练好的模型?", default=True)
        if save_choice:
            model_path = batch_system.save_batch_models()
            print(f"✅ 模型已保存: {model_path}")
        
        # 策略参数优化
        optimize_choice = safe_confirm("是否进行策略参数优化?", default=True)
        if optimize_choice:
            # 选择币种进行优化
            symbols = list(set(record.symbol for record in trade_records))
            if len(symbols) == 1:
                symbol = symbols[0]
            else:
                symbol = safe_list_input("选择要优化的币种:", choices=symbols)
                if not symbol:
                    return
            
            # 选择时间周期
            intervals = list(set(record.interval for record in trade_records if record.symbol == symbol))
            if len(intervals) == 1:
                interval = intervals[0]
            else:
                interval = safe_list_input("选择时间周期:", choices=intervals)
                if not interval:
                    return
            
            # 当前参数（使用默认参数）
            current_params = {
                'min_shadow_body_ratio': 2.0,
                'max_body_ratio': 0.30,
                'min_signal_score': 3,
                'volume_threshold': 1.2,
                'trend_profit_extension': False,
                'max_trend_profit_pct': 8.0
            }
            
            # 执行优化
            optimized_params = batch_system.optimize_strategy_parameters(
                symbol, interval, current_params
            )
            
            # 生成优化报告
            predictions = batch_system._predict_with_ensemble({})  # 使用空特征进行示例预测
            report = batch_system.generate_optimization_report(
                symbol, predictions, current_params, optimized_params
            )
            print(report)
        
    except ImportError as e:
        print(f"❌ 批量训练模块未找到: {e}")
        print("   请确保 batch_training_system.py 和 trade_record_collector.py 文件存在")
    except Exception as e:
        print(f"❌ 批量训练失败: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# 辅助函数
# ============================================================================

def _generate_ab_test_report(original_results: Dict, trend_results: Dict, 
                           symbol: str, interval: str, data):
    """生成A/B测试对比报告"""
    try:
        enhanced_generator = EnhancedReportGenerator()
        
        # 准备A/B测试数据
        comparison_data = {
            'original_strategy': original_results,
            'trend_strategy': trend_results,
            'symbol': symbol,
            'interval': interval,
            'test_type': 'ab_test'
        }
        
        # 生成对比报告
        report_path = enhanced_generator.generate_ab_test_report(comparison_data, data)
        
        print("🚀 自动在浏览器中打开A/B对比报告...")
        enhanced_generator.open_report_in_browser(report_path)
        
    except Exception as e:
        print(f"❌ A/B对比报告生成失败: {e}")
        # 如果增强报告失败，生成简单的文本报告
        _generate_simple_ab_report(original_results, trend_results, symbol, interval)

def _generate_simple_ab_report(original_results: Dict, trend_results: Dict, 
                             symbol: str, interval: str):
    """生成简单的A/B测试文本报告"""
    try:
        import os
        from datetime import datetime
        
        # 创建报告目录
        report_dir = "reports"
        os.makedirs(report_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ab_test_report_{symbol}_{interval}_{timestamp}.txt"
        filepath = os.path.join(report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"A/B测试对比报告\n")
            f.write(f"=" * 50 + "\n")
            f.write(f"币种: {symbol}\n")
            f.write(f"周期: {interval}\n")
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"原版策略结果:\n")
            f.write(f"  总收益率: {original_results['total_return']:.2f}%\n")
            f.write(f"  总交易数: {original_results['total_trades']}\n")
            f.write(f"  胜率: {original_results['win_rate']:.1f}%\n")
            f.write(f"  最大回撤: {original_results['max_drawdown']*100:.2f}%\n\n")
            
            f.write(f"趋势跟踪版结果:\n")
            f.write(f"  总收益率: {trend_results['total_return']:.2f}%\n")
            f.write(f"  总交易数: {trend_results['total_trades']}\n")
            f.write(f"  胜率: {trend_results['win_rate']:.1f}%\n")
            f.write(f"  最大回撤: {trend_results['max_drawdown']*100:.2f}%\n")
            f.write(f"  趋势跟踪交易: {trend_results.get('trend_tracking_trades', 0)}笔\n")
            
            # 计算改进幅度
            return_improvement = ((trend_results['total_return'] - original_results['total_return']) / 
                                original_results['total_return']) * 100 if original_results['total_return'] != 0 else 0
            
            f.write(f"\n改进幅度:\n")
            f.write(f"  收益率改进: {return_improvement:+.1f}%\n")
        
        print(f"✅ 简单A/B报告已保存: {filepath}")
        
    except Exception as e:
        print(f"❌ 简单报告生成也失败: {e}")