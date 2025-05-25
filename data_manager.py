#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据管理模块
负责数据获取、处理和技术指标计算
"""

import pandas as pd
import numpy as np
from binance.client import Client
import datetime
import json
import os
from typing import Optional, List, Dict, Any
import backtrader as bt

class DataManager:
    """数据管理器"""
    
    def __init__(self, api_key: str = "", api_secret: str = ""):
        """初始化数据管理器"""
        self.client = None
        self.api_key = api_key
        self.api_secret = api_secret
        
        # 尝试加载API密钥
        if not api_key or not api_secret:
            self._load_api_keys()
        
        # 初始化币安客户端
        if self.api_key and self.api_secret:
            try:
                self.client = Client(self.api_key, self.api_secret)
                print("✅ 币安API连接成功")
            except Exception as e:
                print(f"❌ 币安API连接失败: {e}")
        else:
            print("⚠️  未设置API密钥，将使用离线模式")
    
    def _load_api_keys(self) -> None:
        """从key.json文件加载API密钥"""
        try:
            with open('key.json', 'r') as f:
                keys = json.load(f)
                self.api_key = keys.get('api_key', '')
                self.api_secret = keys.get('api_secret', '')
                
                if not self.api_key or not self.api_secret:
                    print("警告: API密钥为空，请检查key.json文件")
        except FileNotFoundError:
            print("错误: 找不到key.json文件，创建示例文件...")
            self._create_sample_key_file()
        except json.JSONDecodeError:
            print("错误: key.json文件格式不正确")
    
    def _create_sample_key_file(self) -> None:
        """创建示例key.json文件"""
        example_keys = {
            "api_key": "您的币安API密钥",
            "api_secret": "您的币安API密钥"
        }
        with open('key.json', 'w') as f:
            json.dump(example_keys, f, indent=4)
        print("已创建示例key.json文件，请编辑此文件并重新运行程序")
    
    def get_top_symbols(self, limit: int = 20) -> List[str]:
        """获取交易量最高的币种"""
        if not self.client:
            # 返回常见币种作为备选
            return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT', 
                   'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LUNAUSDT']
        
        try:
            # 获取24小时ticker数据
            tickers = self.client.get_ticker()
            
            # 过滤USDT交易对并按交易量排序
            usdt_pairs = []
            for ticker in tickers:
                symbol = ticker['symbol']
                if symbol.endswith('USDT') and not any(x in symbol for x in ['UP', 'DOWN', 'BULL', 'BEAR']):
                    try:
                        volume = float(ticker['quoteVolume'])
                        usdt_pairs.append((symbol, volume))
                    except:
                        continue
            
            # 按交易量排序
            usdt_pairs.sort(key=lambda x: x[1], reverse=True)
            
            # 返回前N个币种
            top_symbols = [pair[0] for pair in usdt_pairs[:limit]]
            print(f"✅ 获取到前{limit}个交易量最高的币种")
            return top_symbols
            
        except Exception as e:
            print(f"❌ 获取币种列表失败: {e}")
            return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    def get_historical_data(self, symbol: str, interval: str, 
                          start_date: str, end_date: str, 
                          limit: int = 1500) -> Optional[pd.DataFrame]:
        """
        获取历史K线数据
        
        Args:
            symbol: 交易对符号
            interval: 时间间隔 ('1m', '5m', '15m', '1h', '4h', '1d')
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            limit: 最大获取数量
        """
        if not self.client:
            print("❌ API客户端未初始化")
            return None
        
        try:
            print(f"📊 获取 {symbol} {interval} 数据: {start_date} ~ {end_date}")
            
            # 转换时间戳
            start_timestamp = int(datetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_timestamp = int(datetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
            
            # 获取K线数据
            klines = self.client.get_historical_klines(
                symbol, interval, start_timestamp, end_timestamp, limit=limit
            )
            
            if not klines:
                print(f"❌ 未获取到 {symbol} 的数据")
                return None
            
            # 转换为DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            
            # 数据类型转换
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 
                             'quote_asset_volume', 'number_of_trades']
            df[numeric_columns] = df[numeric_columns].astype(float)
            
            # 计算技术指标
            df = self.calculate_indicators(df, interval)
            
            print(f"✅ 成功获取 {len(df)} 条数据")
            return df
            
        except Exception as e:
            print(f"❌ 获取历史数据失败: {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame, interval: str = '1h') -> pd.DataFrame:
        """
        计算技术指标
        根据不同时间周期调整参数
        """
        if df.empty:
            return df
        
        try:
            # 根据时间周期调整参数
            if interval in ['1m', '5m']:
                # 短周期参数
                fast_period, slow_period, rsi_period = 5, 10, 14
                bb_period = 12
            elif interval in ['15m', '1h']:
                # 中周期参数
                fast_period, slow_period, rsi_period = 20, 50, 14
                bb_period = 20
            else:
                # 长周期参数
                fast_period, slow_period, rsi_period = 10, 25, 14
                bb_period = 20
            
            # 移动平均线
            df['sma_fast'] = df['close'].rolling(window=fast_period).mean()
            df['sma_slow'] = df['close'].rolling(window=slow_period).mean()
            df['sma_trend'] = df['close'].rolling(window=100).mean()
            
            # RSI指标
            df['rsi'] = self._calculate_rsi(df['close'], rsi_period)
            
            # ATR指标
            df['atr'] = self._calculate_atr(df['high'], df['low'], df['close'])
            
            # 布林带
            df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
            bb_std = df['close'].rolling(window=bb_period).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            # MACD指标
            df = self._calculate_macd(df)
            
            # 成交量指标
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            # 波动率
            df['volatility'] = self._calculate_volatility(df['close'])
            
            print("✅ 技术指标计算完成")
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
    
    def _calculate_macd(self, df: pd.DataFrame, 
                       fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算MACD指标"""
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=signal).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        return df
    
    def _calculate_volatility(self, prices: pd.Series, period: int = 20) -> pd.Series:
        """计算波动率"""
        returns = np.log(prices / prices.shift())
        volatility = returns.rolling(window=period).std() * np.sqrt(24)  # 日化波动率
        return volatility
    
    def save_data(self, df: pd.DataFrame, filename: str) -> None:
        """保存数据到文件"""
        try:
            # 创建数据目录
            os.makedirs('data', exist_ok=True)
            
            filepath = os.path.join('data', filename)
            df.to_csv(filepath, index=False)
            print(f"✅ 数据已保存到 {filepath}")
        except Exception as e:
            print(f"❌ 保存数据失败: {e}")
    
    def load_data(self, filename: str) -> Optional[pd.DataFrame]:
        """从文件加载数据"""
        try:
            filepath = os.path.join('data', filename)
            if os.path.exists(filepath):
                df = pd.read_csv(filepath)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                print(f"✅ 数据已从 {filepath} 加载")
                return df
            else:
                print(f"❌ 文件不存在: {filepath}")
                return None
        except Exception as e:
            print(f"❌ 加载数据失败: {e}")
            return None
    
    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取数据摘要"""
        if df.empty:
            return {}
        
        summary = {
            'total_rows': len(df),
            'date_range': {
                'start': df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S'),
                'end': df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')
            },
            'price_range': {
                'min': df['low'].min(),
                'max': df['high'].max(),
                'first': df['open'].iloc[0],
                'last': df['close'].iloc[-1]
            },
            'volume': {
                'total': df['volume'].sum(),
                'average': df['volume'].mean(),
                'max': df['volume'].max()
            },
            'missing_data': df.isnull().sum().to_dict()
        }
        
        return summary
    
    def validate_data(self, df: pd.DataFrame) -> List[str]:
        """验证数据质量"""
        issues = []
        
        if df.empty:
            issues.append("数据为空")
            return issues
        
        # 检查必要列
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            issues.append(f"缺少必要列: {missing_columns}")
        
        # 检查数据完整性
        if df.isnull().any().any():
            null_counts = df.isnull().sum()
            null_columns = null_counts[null_counts > 0].to_dict()
            issues.append(f"存在空值: {null_columns}")
        
        # 检查价格逻辑
        invalid_ohlc = df[(df['high'] < df['low']) | 
                         (df['high'] < df['open']) | 
                         (df['high'] < df['close']) |
                         (df['low'] > df['open']) | 
                         (df['low'] > df['close'])]
        if not invalid_ohlc.empty:
            issues.append(f"发现 {len(invalid_ohlc)} 条价格逻辑错误的数据")
        
        # 检查时间序列
        if not df['timestamp'].is_monotonic_increasing:
            issues.append("时间序列不是递增的")
        
        return issues

class CustomDataFeed(bt.feeds.PandasData):
    """自定义Backtrader数据源"""
    params = (
        ('datetime', 'timestamp'),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', -1),
        # 自定义技术指标
        ('rsi', -1),
        ('atr', -1),
        ('bb_upper', -1),
        ('bb_lower', -1),
        ('bb_middle', -1),
        ('sma_fast', -1),
        ('sma_slow', -1),
        ('sma_trend', -1),
        ('macd', -1),
        ('macd_signal', -1),
        ('volume_sma', -1),
        ('volatility', -1),
    )

# 全局数据管理器实例
data_manager = DataManager()

def get_data_manager() -> DataManager:
    """获取全局数据管理器"""
    return data_manager

if __name__ == "__main__":
    # 测试数据管理器
    dm = DataManager()
    
    # 获取币种列表
    symbols = dm.get_top_symbols(10)
    print(f"前10币种: {symbols}")
    
    # 获取历史数据
    if symbols:
        df = dm.get_historical_data(
            symbol=symbols[0],
            interval='1h',
            start_date='2024-01-01',
            end_date='2024-02-01'
        )
        
        if df is not None:
            # 数据摘要
            summary = dm.get_data_summary(df)
            print("数据摘要:", summary)
            
            # 数据验证
            issues = dm.validate_data(df)
            if issues:
                print("数据问题:", issues)
            else:
                print("✅ 数据验证通过")
            
            # 保存数据
            dm.save_data(df, f"{symbols[0]}_1h_test.csv")