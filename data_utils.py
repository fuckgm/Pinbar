#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据处理工具模块
负责本地数据的加载、管理和交互式选择
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from utils import safe_list_input, safe_text_input

def get_local_data_summary() -> Dict[str, List[str]]:
    """获取本地已下载数据摘要"""
    data_dir = "data"
    local_data = {}
    
    if not os.path.exists(data_dir):
        print(f"📁 数据目录不存在: {data_dir}")
        return local_data
    
    try:
        for symbol_dir in os.listdir(data_dir):
            symbol_path = os.path.join(data_dir, symbol_dir)
            
            # 跳过非目录文件和缓存目录
            if not os.path.isdir(symbol_path) or symbol_dir == 'cache':
                continue
            
            intervals = []
            try:
                for file in os.listdir(symbol_path):
                    if file.endswith('.csv') or file.endswith('.pkl'):
                        # 提取时间周期信息
                        # 文件名格式: SYMBOL_INTERVAL.csv 或 SYMBOL_INTERVAL.pkl
                        interval = file.replace(f"{symbol_dir}_", "").replace(".csv", "").replace(".pkl", "")
                        if interval and interval not in intervals:
                            intervals.append(interval)
                
                if intervals:
                    local_data[symbol_dir] = sorted(intervals, key=lambda x: _sort_interval_key(x))
                    
            except Exception as e:
                print(f"⚠️ 读取 {symbol_dir} 目录失败: {e}")
                continue
    
    except Exception as e:
        print(f"❌ 读取数据目录失败: {e}")
        return {}
    
    return local_data

def _sort_interval_key(interval: str) -> int:
    """间隔排序键函数"""
    # 将时间间隔转换为分钟数用于排序
    interval_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
        '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
        '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200
    }
    return interval_minutes.get(interval, 99999)

def load_local_data(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """加载本地数据"""
    data_dir = "data"
    symbol_path = os.path.join(data_dir, symbol)
    
    if not os.path.exists(symbol_path):
        print(f"❌ 币种目录不存在: {symbol_path}")
        return None
    
    # 尝试加载PKL文件（优先）和CSV文件
    pkl_file = os.path.join(symbol_path, f"{symbol}_{interval}.pkl")
    csv_file = os.path.join(symbol_path, f"{symbol}_{interval}.csv")
    
    try:
        df = None
        
        # 优先加载PKL文件（更快）
        if os.path.exists(pkl_file):
            print(f"📁 加载本地数据: {symbol} {interval} (pickle格式)")
            df = pd.read_pickle(pkl_file)
            
        elif os.path.exists(csv_file):
            print(f"📁 加载本地数据: {symbol} {interval} (csv格式)")
            df = pd.read_csv(csv_file)
            
            # 确保时间戳列存在并正确格式化
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            elif 'datetime' in df.columns:
                df['timestamp'] = pd.to_datetime(df['datetime'])
                df.drop('datetime', axis=1, inplace=True)
            else:
                print("⚠️ 未找到时间戳列，尝试从索引创建")
                if df.index.name == 'datetime' or isinstance(df.index, pd.DatetimeIndex):
                    df.reset_index(inplace=True)
                    df.rename(columns={'index': 'timestamp'}, inplace=True)
                    
        else:
            print(f"❌ 未找到数据文件: {symbol} {interval}")
            print(f"   查找路径: {pkl_file} 或 {csv_file}")
            return None
        
        if df is None:
            print(f"❌ 数据加载失败: {symbol} {interval}")
            return None
        
        # 数据验证和清理
        original_len = len(df)
        
        # 检查必要列
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ 数据缺少必要列: {missing_columns}")
            return None
        
        # 数据清理
        # 1. 删除包含NaN的行
        df = df.dropna(subset=required_columns)
        
        # 2. 删除异常数据（价格为0或负数）
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            df = df[df[col] > 0]
        
        # 3. 检查OHLC逻辑
        df = df[(df['high'] >= df['low']) & 
                (df['high'] >= df['open']) & 
                (df['high'] >= df['close']) & 
                (df['low'] <= df['open']) & 
                (df['low'] <= df['close'])]
        
        # 4. 删除重复时间戳
        if 'timestamp' in df.columns:
            df = df.drop_duplicates(subset=['timestamp'], keep='first')
            df = df.sort_values('timestamp').reset_index(drop=True)
        
        cleaned_len = len(df)
        
        if cleaned_len < original_len:
            removed = original_len - cleaned_len
            print(f"⚠️ 数据清理: 移除 {removed} 条异常记录")
        
        # 检查数据量
        if cleaned_len < 100:
            print(f"❌ 数据不足: 仅有 {cleaned_len} 条记录，至少需要100条")
            return None
        
        print(f"✅ 成功加载 {cleaned_len} 条数据")
        
        # 显示数据范围信息
        if 'timestamp' in df.columns:
            start_time = df['timestamp'].min()
            end_time = df['timestamp'].max()
            print(f"   时间范围: {start_time} ~ {end_time}")
            
            # 检查数据连续性
            time_gaps = _check_data_continuity(df, interval)
            if time_gaps > 0:
                print(f"   数据间隙: {time_gaps} 处")
        
        return df
        
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def _check_data_continuity(df: pd.DataFrame, interval: str) -> int:
    """检查数据连续性"""
    if len(df) < 2 or 'timestamp' not in df.columns:
        return 0
    
    # 计算预期的时间间隔（分钟）
    interval_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
        '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
        '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200
    }
    
    expected_minutes = interval_minutes.get(interval, 60)
    expected_delta = pd.Timedelta(minutes=expected_minutes)
    
    # 计算时间差
    time_diffs = df['timestamp'].diff()[1:]
    
    # 允许的误差范围（10%）
    tolerance = expected_delta * 0.1
    min_expected = expected_delta - tolerance
    max_expected = expected_delta + tolerance
    
    # 计算间隙数量
    gaps = sum((time_diffs < min_expected) | (time_diffs > max_expected))
    
    return gaps

def interactive_select_local_data() -> Tuple[Optional[str], Optional[str]]:
    """交互式选择本地数据"""
    print("\n📁 本地数据选择器")
    print("=" * 50)
    
    local_data = get_local_data_summary()
    
    if not local_data:
        print("❌ 未找到本地数据")
        print("\n💡 解决方案:")
        print("   1. 使用数据下载器下载数据")
        print("   2. 确保数据文件存放在正确位置:")
        print("      - 目录结构: data/SYMBOL/SYMBOL_INTERVAL.csv")
        print("      - 示例: data/BTCUSDT/BTCUSDT_1h.csv")
        print("   3. 检查文件权限和格式")
        return None, None
    
    print(f"📊 发现 {len(local_data)} 个币种的本地数据")
    
    # 创建币种选择列表
    symbol_choices = []
    for symbol, intervals in local_data.items():
        # 显示前3个时间周期，如果更多则显示省略号
        interval_preview = ', '.join(intervals[:3])
        if len(intervals) > 3:
            interval_preview += f'... (共{len(intervals)}个)'
        
        symbol_choices.append((f"{symbol:<12} [{interval_preview}]", symbol))
    
    # 按币种名称排序
    symbol_choices.sort(key=lambda x: x[1])
    
    # 选择币种
    selected_symbol = safe_list_input("选择币种", choices=symbol_choices)
    if selected_symbol is None:
        return None, None
    
    # 选择时间周期
    available_intervals = local_data[selected_symbol]
    
    print(f"\n📊 {selected_symbol} 可用时间周期:")
    interval_choices = []
    
    for interval in available_intervals:
        # 尝试获取该时间周期的数据信息
        try:
            data = load_local_data(selected_symbol, interval)
            if data is not None:
                data_info = f"({len(data)} 条记录)"
                if 'timestamp' in data.columns:
                    start_time = data['timestamp'].min().strftime('%Y-%m-%d')
                    end_time = data['timestamp'].max().strftime('%Y-%m-%d')
                    data_info += f" [{start_time} ~ {end_time}]"
                
                interval_choices.append((f"{interval:<8} {data_info}", interval))
            else:
                interval_choices.append((f"{interval:<8} (数据异常)", interval))
        except:
            interval_choices.append((f"{interval:<8} (读取失败)", interval))
    
    if not interval_choices:
        print(f"❌ {selected_symbol} 没有可用的时间周期数据")
        return None, None
    
    selected_interval = safe_list_input(f"选择 {selected_symbol} 的时间周期", choices=interval_choices)
    if selected_interval is None:
        return None, None
    
    print(f"✅ 已选择: {selected_symbol} - {selected_interval}")
    return selected_symbol, selected_interval

def validate_data_quality(df: pd.DataFrame, symbol: str, interval: str) -> Dict[str, Any]:
    """验证数据质量"""
    quality_report = {
        'symbol': symbol,
        'interval': interval,
        'total_rows': len(df),
        'issues': [],
        'warnings': [],
        'score': 100  # 满分100
    }
    
    # 检查必要列
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        quality_report['issues'].append(f"缺少必要列: {missing_columns}")
        quality_report['score'] -= 30
    
    if quality_report['score'] <= 0:  # 如果缺少必要列，直接返回
        return quality_report
    
    # 检查空值
    null_counts = df[required_columns].isnull().sum()
    total_nulls = null_counts.sum()
    
    if total_nulls > 0:
        null_percentage = (total_nulls / (len(df) * len(required_columns))) * 100
        quality_report['warnings'].append(f"空值: {total_nulls} 个 ({null_percentage:.1f}%)")
        quality_report['score'] -= min(20, null_percentage)
    
    # 检查OHLC逻辑错误
    ohlc_errors = 0
    if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        # High应该是最高价
        ohlc_errors += len(df[(df['high'] < df['open']) | (df['high'] < df['close']) | (df['high'] < df['low'])])
        # Low应该是最低价
        ohlc_errors += len(df[(df['low'] > df['open']) | (df['low'] > df['close']) | (df['low'] > df['high'])])
    
    if ohlc_errors > 0:
        error_percentage = (ohlc_errors / len(df)) * 100
        quality_report['issues'].append(f"OHLC逻辑错误: {ohlc_errors} 条 ({error_percentage:.1f}%)")
        quality_report['score'] -= min(25, error_percentage * 2)
    
    # 检查异常价格（0或负数）
    price_columns = ['open', 'high', 'low', 'close']
    zero_prices = 0
    for col in price_columns:
        if col in df.columns:
            zero_prices += len(df[df[col] <= 0])
    
    if zero_prices > 0:
        zero_percentage = (zero_prices / (len(df) * len(price_columns))) * 100
        quality_report['issues'].append(f"异常价格(≤0): {zero_prices} 个 ({zero_percentage:.1f}%)")
        quality_report['score'] -= min(15, zero_percentage)
    
    # 检查数据连续性（如果有时间戳）
    if 'timestamp' in df.columns:
        gaps = _check_data_continuity(df, interval)
        if gaps > len(df) * 0.05:  # 超过5%的间隙
            gap_percentage = (gaps / len(df)) * 100
            quality_report['warnings'].append(f"数据间隙: {gaps} 处 ({gap_percentage:.1f}%)")
            quality_report['score'] -= min(10, gap_percentage)
    
    # 检查重复数据
    if 'timestamp' in df.columns:
        duplicates = df.duplicated(subset=['timestamp']).sum()
        if duplicates > 0:
            dup_percentage = (duplicates / len(df)) * 100
            quality_report['warnings'].append(f"重复时间戳: {duplicates} 条 ({dup_percentage:.1f}%)")
            quality_report['score'] -= min(10, dup_percentage)
    
    # 确保得分不低于0
    quality_report['score'] = max(0, quality_report['score'])
    
    return quality_report

def print_data_quality_report(quality_report: Dict[str, Any]):
    """打印数据质量报告"""
    symbol = quality_report['symbol']
    interval = quality_report['interval']
    score = quality_report['score']
    
    print(f"\n📊 数据质量报告: {symbol} {interval}")
    print("=" * 50)
    print(f"总记录数: {quality_report['total_rows']:,}")
    print(f"质量得分: {score:.0f}/100", end="")
    
    # 根据得分显示等级
    if score >= 90:
        print(" 🟢 优秀")
    elif score >= 75:
        print(" 🟡 良好")
    elif score >= 60:
        print(" 🟠 一般")
    else:
        print(" 🔴 较差")
    
    # 显示问题
    if quality_report['issues']:
        print("\n❌ 严重问题:")
        for issue in quality_report['issues']:
            print(f"   • {issue}")
    
    # 显示警告
    if quality_report['warnings']:
        print("\n⚠️ 警告:")
        for warning in quality_report['warnings']:
            print(f"   • {warning}")
    
    if not quality_report['issues'] and not quality_report['warnings']:
        print("\n✅ 数据质量良好，未发现问题")
    
    # 建议
    if score < 75:
        print("\n💡 改进建议:")
        if score < 60:
            print("   • 考虑重新下载数据")
        print("   • 使用数据清理功能")
        print("   • 检查数据源质量")

def get_data_statistics(df: pd.DataFrame) -> Dict[str, Any]:
    """获取数据统计信息"""
    stats = {
        'total_records': len(df),
        'date_range': {},
        'price_stats': {},
        'volume_stats': {},
        'data_quality': {}
    }
    
    # 时间范围
    if 'timestamp' in df.columns:
        stats['date_range'] = {
            'start': df['timestamp'].min(),
            'end': df['timestamp'].max(),
            'duration_days': (df['timestamp'].max() - df['timestamp'].min()).days
        }
    
    # 价格统计