#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
币种数据批量下载器 - 优化版
支持下载币安所有历史数据，自动分批处理
"""

import os
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import inquirer
from binance.client import Client
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pickle

class CryptoDataDownloader:
    """加密货币数据下载器 - 优化版"""
    
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        
        # 数据存储路径
        self.data_dir = "data"
        self.cache_dir = os.path.join(self.data_dir, "cache")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 加载API密钥
        if not api_key or not api_secret:
            self._load_api_keys()
        
        # 初始化币安客户端
        if self.api_key and self.api_secret:
            try:
                self.client = Client(self.api_key, self.api_secret)
                print("✅ 币安API连接成功")
            except Exception as e:
                print(f"❌ 币安API连接失败: {e}")
                return
        else:
            print("❌ 未设置API密钥")
            return
        
        # 支持的时间周期
        self.intervals = {
            '1m': '1分钟',
            '5m': '5分钟', 
            '15m': '15分钟',
            '30m': '30分钟',
            '1h': '1小时',
            '2h': '2小时',
            '4h': '4小时',
            '6h': '6小时',
            '8h': '8小时',
            '12h': '12小时',
            '1d': '1天',
            '3d': '3天',
            '1w': '1周'
        }
        
        # 每个周期的毫秒数（用于计算数据点）
        self.interval_ms = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '6h': 6 * 60 * 60 * 1000,
            '8h': 8 * 60 * 60 * 1000,
            '12h': 12 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
            '3d': 3 * 24 * 60 * 60 * 1000,
            '1w': 7 * 24 * 60 * 60 * 1000
        }
        
        # 下载统计
        self.download_stats = {
            'total_symbols': 0,
            'total_intervals': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_data_points': 0,
            'start_time': None,
            'end_time': None
        }
    
    def _load_api_keys(self):
        """加载API密钥"""
        try:
            with open('key.json', 'r') as f:
                keys = json.load(f)
                self.api_key = keys.get('api_key', '')
                self.api_secret = keys.get('api_secret', '')
        except FileNotFoundError:
            print("❌ 找不到key.json文件")
        except json.JSONDecodeError:
            print("❌ key.json文件格式错误")
    
    def get_top_symbols(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取交易量最高的币种"""
        if not self.client:
            return []
        
        try:
            print("📊 获取币安交易对信息...")
            
            # 获取24小时ticker数据
            tickers = self.client.get_ticker()
            
            # 过滤USDT交易对并按交易量排序
            usdt_pairs = []
            for ticker in tickers:
                symbol = ticker['symbol']
                if (symbol.endswith('USDT') and 
                    not any(x in symbol for x in ['UP', 'DOWN', 'BULL', 'BEAR', 'LEVERAGED'])):
                    try:
                        volume_usdt = float(ticker['quoteVolume'])
                        price = float(ticker['lastPrice'])
                        price_change_pct = float(ticker['priceChangePercent'])
                        
                        usdt_pairs.append({
                            'symbol': symbol,
                            'volume_usdt': volume_usdt,
                            'price': price,
                            'price_change_pct': price_change_pct,
                            'count': int(ticker['count'])  # 交易次数
                        })
                    except:
                        continue
            
            # 按交易量排序
            usdt_pairs.sort(key=lambda x: x['volume_usdt'], reverse=True)
            
            print(f"✅ 获取到 {len(usdt_pairs)} 个USDT交易对")
            return usdt_pairs[:limit]
            
        except Exception as e:
            print(f"❌ 获取交易对失败: {e}")
            return []
    
    def download_symbol_data_batch(self, symbol: str, interval: str, 
                                 start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """批量下载单个币种的数据（支持下载所有历史数据）"""
        try:
            print(f"📊 批量下载 {symbol} {interval} 数据: {start_date} ~ {end_date}")
            
            # 转换时间戳
            start_timestamp = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_timestamp = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
            
            # 计算总时间跨度
            time_span = end_timestamp - start_timestamp
            interval_duration = self.interval_ms[interval]
            
            # 估算总数据点数
            estimated_points = time_span // interval_duration
            print(f"📈 预计数据点数: {estimated_points:,}")
            
            # 分批下载数据
            all_klines = []
            batch_size = 1000  # 每批最多1000条
            current_start = start_timestamp
            
            while current_start < end_timestamp:
                try:
                    # 获取一批数据
                    klines = self.client.get_historical_klines(
                        symbol, interval, current_start, end_timestamp, limit=batch_size
                    )
                    
                    if not klines:
                        break
                    
                    all_klines.extend(klines)
                    
                    # 更新下一批的开始时间
                    last_timestamp = klines[-1][0]
                    current_start = last_timestamp + interval_duration
                    
                    # 显示进度
                    progress = min((current_start - start_timestamp) / time_span * 100, 100)
                    print(f"📊 {symbol} {interval} 下载进度: {progress:.1f}% ({len(all_klines)} 条)")
                    
                    # 避免请求过于频繁
                    time.sleep(0.2)
                    
                except Exception as e:
                    print(f"❌ 批次下载失败: {e}")
                    break
            
            if not all_klines:
                print(f"❌ {symbol} {interval} 无数据")
                return None
            
            # 转换为DataFrame
            df = pd.DataFrame(all_klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            
            # 数据类型转换
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 
                             'quote_asset_volume', 'number_of_trades']
            df[numeric_columns] = df[numeric_columns].astype(float)
            
            # 删除重复数据
            df.drop_duplicates(subset=['timestamp'], inplace=True)
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)
            
            print(f"✅ {symbol} {interval} 下载完成: {len(df)} 条数据")
            return df
            
        except Exception as e:
            print(f"❌ {symbol} {interval} 下载失败: {e}")
            return None
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        if df.empty:
            return df
        
        try:
            # 移动平均线
            df['sma_5'] = df['close'].rolling(window=5).mean()
            df['sma_10'] = df['close'].rolling(window=10).mean()
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['sma_100'] = df['close'].rolling(window=100).mean()
            df['sma_200'] = df['close'].rolling(window=200).mean()
            
            # EMA指标
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            # RSI指标
            df['rsi'] = self._calculate_rsi(df['close'], 14)
            
            # MACD指标
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']
            
            # 布林带
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            # ATR指标
            df['atr'] = self._calculate_atr(df['high'], df['low'], df['close'])
            
            # 成交量指标
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            # 波动率
            df['volatility'] = self._calculate_volatility(df['close'])
            
            # 价格变化
            df['price_change'] = df['close'].pct_change()
            df['price_change_abs'] = df['price_change'].abs()
            
            return df
            
        except Exception as e:
            print(f"❌ 技术指标计算失败: {e}")
            return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, 
                      close: pd.Series, period: int = 14) -> pd.Series:
        """计算ATR指标"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def _calculate_volatility(self, prices: pd.Series, period: int = 20) -> pd.Series:
        """计算波动率"""
        returns = np.log(prices / prices.shift())
        volatility = returns.rolling(window=period).std() * np.sqrt(24)
        return volatility
    
    def save_data(self, df: pd.DataFrame, symbol: str, interval: str):
        """保存数据到文件"""
        try:
            # 创建目录结构
            symbol_dir = os.path.join(self.data_dir, symbol)
            os.makedirs(symbol_dir, exist_ok=True)
            
            # 保存为CSV
            csv_file = os.path.join(symbol_dir, f"{symbol}_{interval}.csv")
            df.to_csv(csv_file, index=False)
            
            # 保存为pickle (更快的加载)
            pkl_file = os.path.join(symbol_dir, f"{symbol}_{interval}.pkl")
            df.to_pickle(pkl_file)
            
            # 保存基本信息
            info = {
                'symbol': symbol,
                'interval': interval,
                'data_points': len(df),
                'start_date': df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S'),
                'download_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_size_mb': round(os.path.getsize(csv_file) / 1024 / 1024, 2)
            }
            
            info_file = os.path.join(symbol_dir, f"{symbol}_{interval}_info.json")
            with open(info_file, 'w') as f:
                json.dump(info, f, indent=2)
            
            print(f"💾 {symbol} {interval} 数据已保存")
            
        except Exception as e:
            print(f"❌ 保存数据失败: {e}")
    
    def download_batch(self, symbols: List[str], intervals: List[str], 
                      start_date: str, end_date: str, max_workers: int = 3):
        """批量下载数据（优化版）"""
        self.download_stats['start_time'] = datetime.now()
        self.download_stats['total_symbols'] = len(symbols)
        self.download_stats['total_intervals'] = len(intervals)
        
        total_tasks = len(symbols) * len(intervals)
        completed_tasks = 0
        
        print(f"🚀 开始批量下载...")
        print(f"📊 币种数量: {len(symbols)}")
        print(f"⏱️  时间周期: {len(intervals)}")
        print(f"📅 时间范围: {start_date} ~ {end_date}")
        print(f"🔄 总任务数: {total_tasks}")
        print(f"👥 并发数: {max_workers}")
        print("-" * 60)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_task = {}
            for symbol in symbols:
                for interval in intervals:
                    future = executor.submit(
                        self._download_and_save_single,
                        symbol, interval, start_date, end_date
                    )
                    future_to_task[future] = (symbol, interval)
            
            # 处理完成的任务
            for future in as_completed(future_to_task):
                symbol, interval = future_to_task[future]
                completed_tasks += 1
                
                try:
                    success, data_points = future.result()
                    if success:
                        self.download_stats['successful_downloads'] += 1
                        self.download_stats['total_data_points'] += data_points
                    else:
                        self.download_stats['failed_downloads'] += 1
                        
                except Exception as e:
                    print(f"❌ {symbol} {interval} 任务执行失败: {e}")
                    self.download_stats['failed_downloads'] += 1
                
                # 显示进度
                progress = completed_tasks / total_tasks * 100
                print(f"📈 进度: {completed_tasks}/{total_tasks} ({progress:.1f}%) - "
                      f"成功: {self.download_stats['successful_downloads']} "
                      f"失败: {self.download_stats['failed_downloads']}")
                
                # 添加延时避免API限制
                time.sleep(0.1)
        
        self.download_stats['end_time'] = datetime.now()
        self._print_download_summary()
    
    def _download_and_save_single(self, symbol: str, interval: str, 
                                 start_date: str, end_date: str) -> tuple:
        """下载并保存单个任务（支持批量下载）"""
        try:
            # 使用批量下载方法
            df = self.download_symbol_data_batch(symbol, interval, start_date, end_date)
            if df is not None:
                # 计算技术指标
                df = self.calculate_technical_indicators(df)
                
                # 保存数据
                self.save_data(df, symbol, interval)
                
                return True, len(df)
            else:
                return False, 0
                
        except Exception as e:
            print(f"❌ {symbol} {interval} 处理失败: {e}")
            return False, 0
    
    def _print_download_summary(self):
        """打印下载汇总"""
        stats = self.download_stats
        duration = stats['end_time'] - stats['start_time']
        
        print("\n" + "=" * 60)
        print("📊 下载完成汇总")
        print("=" * 60)
        print(f"⏱️  总耗时: {duration}")
        print(f"📊 币种数量: {stats['total_symbols']}")
        print(f"⏱️  时间周期: {stats['total_intervals']}")
        print(f"✅ 成功下载: {stats['successful_downloads']}")
        print(f"❌ 失败下载: {stats['failed_downloads']}")
        print(f"📈 总数据点: {stats['total_data_points']:,}")
        print(f"📊 成功率: {stats['successful_downloads']/(stats['successful_downloads']+stats['failed_downloads'])*100:.1f}%")
        
        # 计算数据存储大小
        total_size = 0
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.csv'):
                    total_size += os.path.getsize(os.path.join(root, file))
        
        print(f"💾 存储大小: {total_size/1024/1024:.1f} MB")
        print("=" * 60)
    
    def interactive_download(self):
        """交互式下载（支持更多历史数据选项）"""
        if not self.client:
            print("❌ API客户端未初始化，无法下载数据")
            return
        
        print("\n🎯 币种数据批量下载器")
        print("=" * 50)
        
        # 获取币种列表
        print("📊 正在获取币种列表...")
        all_symbols = self.get_top_symbols(100)
        
        if not all_symbols:
            print("❌ 获取币种列表失败")
            return
        
        # 选择币种
        symbol_choices = []
        for i, sym_info in enumerate(all_symbols[:50]):
            volume_m = sym_info['volume_usdt'] / 1_000_000
            price_change = sym_info['price_change_pct']
            symbol_choices.append((
                f"{sym_info['symbol']:<12} 📊{volume_m:8.1f}M  📈{price_change:+6.2f}%",
                sym_info['symbol']
            ))
        
        # 添加快捷选项
        symbol_choices.extend([
            ("📊 前10大币种", "top10"),
            ("📊 前20大币种", "top20"),
            ("📊 前30大币种", "top30"),
            ("🎯 全部50币种", "all50")
        ])
        
        try:
            selected_symbols = inquirer.checkbox(
                "选择要下载的币种 (多选)",
                choices=symbol_choices
            )
        except KeyboardInterrupt:
            print("\n操作取消")
            return
        
        # 处理快捷选项
        if "top10" in selected_symbols:
            selected_symbols = [s['symbol'] for s in all_symbols[:10]]
        elif "top20" in selected_symbols:
            selected_symbols = [s['symbol'] for s in all_symbols[:20]]
        elif "top30" in selected_symbols:
            selected_symbols = [s['symbol'] for s in all_symbols[:30]]
        elif "all50" in selected_symbols:
            selected_symbols = [s['symbol'] for s in all_symbols[:50]]
        else:
            # 过滤掉快捷选项
            selected_symbols = [s for s in selected_symbols if s not in ["top10", "top20", "top30", "all50"]]
        
        if not selected_symbols:
            print("❌ 未选择任何币种")
            return
        
        # 选择时间周期
        interval_choices = [(f"{desc} ({interval})", interval) 
                          for interval, desc in self.intervals.items()]
        interval_choices.extend([
            ("⚡ 短周期组合 (1m,5m,15m,1h)", "short"),
            ("📊 标准组合 (15m,1h,4h,1d)", "standard"),
            ("📈 长周期组合 (1h,4h,1d,1w)", "long"),
            ("🎯 全部周期", "all")
        ])
        
        try:
            selected_intervals = inquirer.checkbox(
                "选择时间周期 (多选)",
                choices=interval_choices
            )
        except KeyboardInterrupt:
            print("\n操作取消")
            return
        
        # 处理周期快捷选项
        if "short" in selected_intervals:
            selected_intervals = ['1m', '5m', '15m', '1h']
        elif "standard" in selected_intervals:
            selected_intervals = ['15m', '1h', '4h', '1d']
        elif "long" in selected_intervals:
            selected_intervals = ['1h', '4h', '1d', '1w']
        elif "all" in selected_intervals:
            selected_intervals = list(self.intervals.keys())
        else:
            # 过滤掉快捷选项
            selected_intervals = [s for s in selected_intervals 
                                if s not in ["short", "standard", "long", "all"]]
        
        if not selected_intervals:
            print("❌ 未选择任何时间周期")
            return
        
        # 选择时间范围（支持更多选项）
        time_range_choices = [
            ("🗓️  最近1周", "1week"),
            ("🗓️  最近1个月", "1month"),
            ("🗓️  最近3个月", "3months"),
            ("🗓️  最近6个月", "6months"),
            ("🗓️  最近1年", "1year"),
            ("🗓️  最近2年", "2years"),
            ("🗓️  最近3年", "3years"),
            ("🗓️  全部历史数据（从币种上线开始）", "all"),
            ("📅 自定义时间", "custom")
        ]
        
        try:
            time_range = inquirer.list_input(
                "选择时间范围",
                choices=time_range_choices
            )
        except KeyboardInterrupt:
            print("\n操作取消")
            return
        
        # 计算时间范围
        end_date = datetime.now()
        if time_range == "1week":
            start_date = end_date - timedelta(days=7)
        elif time_range == "1month":
            start_date = end_date - timedelta(days=30)
        elif time_range == "3months":
            start_date = end_date - timedelta(days=90)
        elif time_range == "6months":
            start_date = end_date - timedelta(days=180)
        elif time_range == "1year":
            start_date = end_date - timedelta(days=365)
        elif time_range == "2years":
            start_date = end_date - timedelta(days=730)
        elif time_range == "3years":
            start_date = end_date - timedelta(days=1095)
        elif time_range == "all":
            # 币安最早的数据大约从2017年开始
            start_date = datetime(2017, 1, 1)
        else:  # custom
            try:
                start_str = inquirer.text(
                    "输入开始日期 (YYYY-MM-DD)",
                    default="2024-01-01"
                )
                end_str = inquirer.text(
                    "输入结束日期 (YYYY-MM-DD)",
                    default=end_date.strftime('%Y-%m-%d')
                )
                start_date = datetime.strptime(start_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_str, '%Y-%m-%d')
            except:
                print("❌ 日期格式错误")
                return
        
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # 估算数据量和时间
        days_span = (end_date - start_date).days
        estimated_points_per_symbol = {
            '1m': days_span * 24 * 60,
            '5m': days_span * 24 * 12,
            '15m': days_span * 24 * 4,
            '30m': days_span * 24 * 2,
            '1h': days_span * 24,
            '2h': days_span * 12,
            '4h': days_span * 6,
            '6h': days_span * 4,
            '8h': days_span * 3,
            '12h': days_span * 2,
            '1d': days_span,
            '3d': days_span // 3,
            '1w': days_span // 7
        }
        
        total_estimated_points = 0
        for interval in selected_intervals:
            total_estimated_points += estimated_points_per_symbol.get(interval, 0) * len(selected_symbols)
        
        # 确认下载
        total_tasks = len(selected_symbols) * len(selected_intervals)
        estimated_time = total_tasks * 3  # 估计每个任务3秒
        
        print(f"\n📋 下载确认:")
        print(f"  币种数量: {len(selected_symbols)}")
        print(f"  时间周期: {len(selected_intervals)}")
        print(f"  时间范围: {start_date_str} ~ {end_date_str} ({days_span}天)")
        print(f"  总任务数: {total_tasks}")
        print(f"  预计数据点: {total_estimated_points:,}")
        print(f"  预计耗时: {estimated_time//60}分{estimated_time%60}秒")
        
        # 对于大量数据给出警告
        if total_estimated_points > 1000000:
            print(f"\n⚠️  警告: 数据量较大（超过100万条），下载可能需要较长时间")
            print(f"💡 建议: 可以分批下载或减少币种/周期数量")
        
        try:
            if not inquirer.confirm("确认开始下载？"):
                print("下载取消")
                return
        except KeyboardInterrupt:
            print("\n操作取消")
            return
        
        # 开始下载
        self.download_batch(
            symbols=selected_symbols,
            intervals=selected_intervals,
            start_date=start_date_str,
            end_date=end_date_str,
            max_workers=3
        )
    
    def get_downloaded_data_summary(self) -> Dict[str, Any]:
        """获取已下载数据摘要"""
        summary = {
            'total_symbols': 0,
            'total_files': 0,
            'total_size_mb': 0,
            'symbols': {}
        }
        
        if not os.path.exists(self.data_dir):
            return summary
        
        for symbol_dir in os.listdir(self.data_dir):
            symbol_path = os.path.join(self.data_dir, symbol_dir)
            if os.path.isdir(symbol_path) and symbol_dir != 'cache':
                summary['total_symbols'] += 1
                summary['symbols'][symbol_dir] = {
                    'intervals': [],
                    'files': 0,
                    'size_mb': 0,
                    'data_points': 0,
                    'date_ranges': {}
                }
                
                for file in os.listdir(symbol_path):
                    if file.endswith('.csv'):
                        file_path = os.path.join(symbol_path, file)
                        file_size = os.path.getsize(file_path) / 1024 / 1024
                        
                        summary['total_files'] += 1
                        summary['total_size_mb'] += file_size
                        summary['symbols'][symbol_dir]['files'] += 1
                        summary['symbols'][symbol_dir]['size_mb'] += file_size
                        
                        # 提取时间周期
                        interval = file.replace(f"{symbol_dir}_", "").replace(".csv", "")
                        summary['symbols'][symbol_dir]['intervals'].append(interval)
                        
                        # 读取info文件获取数据范围
                        info_file = file_path.replace('.csv', '_info.json')
                        if os.path.exists(info_file):
                            try:
                                with open(info_file, 'r') as f:
                                    info = json.load(f)
                                    summary['symbols'][symbol_dir]['data_points'] += info.get('data_points', 0)
                                    summary['symbols'][symbol_dir]['date_ranges'][interval] = {
                                        'start': info.get('start_date', ''),
                                        'end': info.get('end_date', ''),
                                        'points': info.get('data_points', 0)
                                    }
                            except:
                                pass
        
        return summary


def main():
    """主程序"""
    print("🎯 币种数据批量下载器 - 优化版")
    print("=" * 60)
    print("✨ 新功能：支持下载所有历史数据")
    print("=" * 60)
    
    # 创建下载器
    downloader = CryptoDataDownloader()
    
    # 主菜单
    while True:
        print("\n📋 功能菜单:")
        choices = [
            '📊 查看可用币种列表',
            '⬇️  交互式批量下载（支持全部历史数据）',
            '📁 查看已下载数据详情',
            '🗑️  清理缓存数据',
            '❌ 退出程序'
        ]
        
        try:
            choice = inquirer.list_input("请选择功能", choices=choices)
        except KeyboardInterrupt:
            print("\n👋 程序退出")
            break
        
        if choice == choices[0]:  # 查看币种列表
            symbols = downloader.get_top_symbols(50)
            if symbols:
                print(f"\n📊 前50大交易量币种:")
                print("-" * 80)
                print(f"{'排名':<4} {'币种':<12} {'价格':<12} {'24h涨跌':<10} {'交易量(M)':<12} {'交易次数':<10}")
                print("-" * 80)
                for i, sym in enumerate(symbols, 1):
                    volume_m = sym['volume_usdt'] / 1_000_000
                    print(f"{i:<4} {sym['symbol']:<12} {sym['price']:<12.4f} "
                          f"{sym['price_change_pct']:+8.2f}% {volume_m:<12.1f} {sym['count']:<10}")
            
        elif choice == choices[1]:  # 交互式下载
            downloader.interactive_download()
            
        elif choice == choices[2]:  # 查看已下载数据
            summary = downloader.get_downloaded_data_summary()
            print(f"\n📁 已下载数据摘要:")
            print(f"  总币种数: {summary['total_symbols']}")
            print(f"  总文件数: {summary['total_files']}")
            print(f"  总大小: {summary['total_size_mb']:.1f} MB")
            
            if summary['symbols']:
                print(f"\n📊 分币种统计:")
                for symbol, info in list(summary['symbols'].items())[:10]:
                    print(f"\n{symbol}:")
                    print(f"  文件数: {info['files']}")
                    print(f"  大小: {info['size_mb']:.1f} MB")
                    print(f"  数据点: {info['data_points']:,}")
                    
                    if info['date_ranges']:
                        print("  时间周期:")
                        for interval, range_info in info['date_ranges'].items():
                            print(f"    {interval}: {range_info['start']} ~ {range_info['end']} ({range_info['points']:,}条)")
                
                if len(summary['symbols']) > 10:
                    print(f"\n... 还有 {len(summary['symbols']) - 10} 个币种")
            
        elif choice == choices[3]:  # 清理缓存
            if os.path.exists(downloader.cache_dir):
                cache_files = os.listdir(downloader.cache_dir)
                if cache_files:
                    try:
                        if inquirer.confirm(f"确认清理 {len(cache_files)} 个缓存文件？"):
                            for file in cache_files:
                                os.remove(os.path.join(downloader.cache_dir, file))
                            print("✅ 缓存清理完成")
                    except KeyboardInterrupt:
                        print("操作取消")
                else:
                    print("📁 缓存目录为空")
            
        elif choice == choices[4]:  # 退出
            print("👋 程序退出")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()