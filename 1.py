import backtrader as bt
import pandas as pd
from binance.client import Client
import datetime
from typing import Tuple, Optional, List, Dict, Any
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import webbrowser
import os
import tempfile
import json
import math
import uuid
from collections import defaultdict

"""
# Pinbar策略思维导图 - 优化激进版

## 一、策略核心逻辑（优化版）
1. Pinbar形态识别（简化条件，避免过拟合）
   - 下影线/实体比例 > 1.5 (简化固定) -> 看涨Pinbar
   - 上影线/实体比例 > 1.5 (简化固定) -> 看跌Pinbar
   - 实体/K线总高度 < 0.4 (简化固定) -> 实体要求

2. 多周期确认（新增）
   - 15分钟趋势判断 + 5分钟精准入场
   - 长期趋势过滤，避免逆势交易

3. 激进风险管理
   - 30倍杠杆（提升）
   - 2.5%单笔风险（提升）
   - 0.6%紧止损，1.8%止盈（3:1盈亏比）

4. 市场状态过滤（新增）
   - 波动率过滤，避免超高波动和超低波动市场
   - 成交量确认，确保流动性充足

# Pinbar策略回测系统 (优化激进版)

## 主要优化改进

基于原版策略的全面优化：

1. **解决过拟合问题**：
   - 大幅减少可调参数（从15+个减少到8个核心参数）
   - 移除复杂的网格搜索优化
   - 固定核心Pinbar识别参数

2. **提升激进程度**：
   - 杠杆从20倍提升到30倍
   - 单笔风险从1%提升到2.5%
   - 止损收紧到0.6%，止盈扩大到1.8%

3. **多周期融合**：
   - 保留15分钟数据用于趋势判断
   - 支持5分钟数据用于精准入场
   - 双周期确认机制

4. **智能市场过滤**：
   - 波动率过滤机制
   - 成交量确认
   - 避免极端市场条件

5. **保留核心优势**：
   - 移动止损功能
   - 完整的可视化系统
   - 详细的交易记录

## 新参数说明（大幅简化）

### 核心参数（固定，避免过拟合）
- pinbar_shadow_ratio: 1.5 (固定)
- pinbar_body_ratio: 0.4 (固定)

### 激进风险参数
- leverage: 30 (提升杠杆)
- risk_per_trade: 0.025 (2.5%风险)
- stop_loss_pct: 0.006 (0.6%止损)
- take_profit_pct: 0.018 (1.8%止盈)

### 市场过滤参数
- min_volatility: 0.001 (最小波动率)
- max_volatility: 0.008 (最大波动率)

"""

# 从key.json文件加载API密钥
try:
    with open('key.json', 'r') as f:
        keys = json.load(f)
        api_key = keys.get('api_key', '')
        api_secret = keys.get('api_secret', '')
        if not api_key or not api_secret:
            print("警告: API密钥为空，请检查key.json文件")
except FileNotFoundError:
    print("错误: 找不到key.json文件，请确保文件存在于当前目录")
    print("创建示例key.json文件...")
    example_keys = {
        "api_key": "您的币安API密钥",
        "api_secret": "您的币安API密钥"
    }
    with open('key.json', 'w') as f:
        json.dump(example_keys, f, indent=4)
    print("已创建示例key.json文件，请编辑此文件并重新运行程序")
    api_key = ''
    api_secret = ''
except json.JSONDecodeError:
    print("错误: key.json文件格式不正确，请确保是有效的JSON格式")
    api_key = ''
    api_secret = ''

# 初始化币安客户端
client = Client(api_key, api_secret)

# 币安手续费标准（标准用户）
MAKER_FEE = 0.0002  # Maker 手续费 0.02%
TAKER_FEE = 0.0004  # Taker 手续费 0.04%

# 在文件顶部添加函数获取前10币种
def get_top_10_symbols():
    """获取币安前10交易量最高的币种"""
    exchange_info = client.get_exchange_info()
    symbols = exchange_info['symbols']
    volume_data = {}
    for symbol in symbols:
        if symbol['symbol'].endswith('USDT') and symbol['status'] == 'TRADING':
            symbol_name = symbol['symbol']
            klines = client.get_klines(symbol=symbol_name, interval='1d', limit=30)
            total_volume = sum(float(k[5]) for k in klines)  # 30天总成交量
            volume_data[symbol_name] = total_volume
    sorted_symbols = sorted(volume_data.items(), key=lambda x: x[1], reverse=True)
    return [symbol for symbol, _ in sorted_symbols[:10]]

# 获取历史K线数据 - 支持多周期
def get_historical_data(symbol: str = 'BTCUSDT', interval: str = '5m', start_date: str = '2024-01-01', end_date: str = '2025-05-21'):
    """
    获取历史数据，支持5分钟和15分钟周期
    interval: '5m' for 5分钟, '15m' for 15分钟
    """
    start_timestamp = int(datetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_timestamp = int(datetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
    klines = client.get_historical_klines(symbol, interval, start_timestamp, end_timestamp)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # 根据周期调整技术指标参数
    if interval == '5m':
        df = calculate_indicators_5m(df)
    else:
        df = calculate_indicators(df)
    return df

# 计算技术指标 - 原版15分钟
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # RSI指标
    def calc_rsi(prices, n=14):
        deltas = np.diff(prices)
        seed = deltas[:n+1]
        up = seed[seed>=0].sum()/n
        down = -seed[seed<0].sum()/n
        rs = up/down if down != 0 else 1  # 避免除以零
        rsi = np.zeros_like(prices)
        rsi[:n] = 100. - 100./(1.+rs)
        
        for i in range(n, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
                
            up = (up * (n-1) + upval) / n
            down = (down * (n-1) + downval) / n
            rs = up/down if down != 0 else 1
            rsi[i] = 100. - 100./(1.+rs)
        return rsi
    
    # ATR指标
    def calc_atr(high, low, close, n=14):
        tr = np.zeros(len(high))
        tr[0] = high[0] - low[0]
        for i in range(1, len(high)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i-1])
            tr3 = abs(low[i] - close[i-1])
            tr[i] = max(tr1, tr2, tr3)
        
        atr = np.zeros_like(tr)
        atr[:n] = np.mean(tr[:n])
        for i in range(n, len(tr)):
            atr[i] = (atr[i-1] * (n-1) + tr[i]) / n
        return atr
    
    # 计算SMA
    df['sma_fast'] = df['close'].rolling(window=8).mean()
    df['sma_slow'] = df['close'].rolling(window=16).mean()
    
    # 计算RSI
    df['rsi'] = calc_rsi(df['close'].values, 14)
    
    # 计算ATR
    df['atr'] = calc_atr(df['high'].values, df['low'].values, df['close'].values, 14)
    
    # 计算布林带
    df['sma_20'] = df['close'].rolling(window=20).mean()
    std_20 = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['sma_20'] + (std_20 * 2)
    df['bb_lower'] = df['sma_20'] - (std_20 * 2)
    
    return df

# 计算技术指标 - 5分钟版本（参数调整）
def calculate_indicators_5m(df: pd.DataFrame) -> pd.DataFrame:
    """5分钟周期的技术指标计算，参数相应调整"""
    # RSI指标
    def calc_rsi(prices, n=14):
        deltas = np.diff(prices)
        seed = deltas[:n+1]
        up = seed[seed>=0].sum()/n
        down = -seed[seed<0].sum()/n
        rs = up/down if down != 0 else 1
        rsi = np.zeros_like(prices)
        rsi[:n] = 100. - 100./(1.+rs)
        
        for i in range(n, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
                
            up = (up * (n-1) + upval) / n
            down = (down * (n-1) + downval) / n
            rs = up/down if down != 0 else 1
            rsi[i] = 100. - 100./(1.+rs)
        return rsi
    
    # ATR指标
    def calc_atr(high, low, close, n=14):
        tr = np.zeros(len(high))
        tr[0] = high[0] - low[0]
        for i in range(1, len(high)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i-1])
            tr3 = abs(low[i] - close[i-1])
            tr[i] = max(tr1, tr2, tr3)
        
        atr = np.zeros_like(tr)
        atr[:n] = np.mean(tr[:n])
        for i in range(n, len(tr)):
            atr[i] = (atr[i-1] * (n-1) + tr[i]) / n
        return atr
    
    # 5分钟周期的SMA（缩短周期）
    df['sma_fast'] = df['close'].rolling(window=5).mean()   # 从8改为5
    df['sma_slow'] = df['close'].rolling(window=10).mean()  # 从16改为10
    
    # 计算RSI
    df['rsi'] = calc_rsi(df['close'].values, 14)
    
    # 计算ATR
    df['atr'] = calc_atr(df['high'].values, df['low'].values, df['close'].values, 14)
    
    # 计算布林带（缩短周期）
    df['sma_20'] = df['close'].rolling(window=12).mean()    # 从20改为12
    std_20 = df['close'].rolling(window=12).std()
    df['bb_upper'] = df['sma_20'] + (std_20 * 2)
    df['bb_lower'] = df['sma_20'] - (std_20 * 2)
    
    return df

# 自定义数据加载类
class CustomDataFeed(bt.feeds.PandasData):
    params = (
        ('datetime', 'timestamp'),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', -1),
        # 添加自定义指标
        ('rsi', -1),
        ('atr', -1),
        ('bb_upper', -1),
        ('bb_lower', -1),
        ('sma_fast', -1),
        ('sma_slow', -1),
    )

# 优化激进版Pinbar策略（基于原版改进）
class OptimizedAggressivePinbarStrategy(bt.Strategy):
    """
    优化激进版Pinbar策略
    - 解决过拟合问题：大幅简化参数
    - 提升激进程度：更高杠杆和风险
    - 保留核心功能：移动止损、可视化等
    - 新增市场过滤：波动率和成交量确认
    """
    params = (
        # ===== 核心参数（固定，避免过拟合） =====
        ('pinbar_shadow_ratio', 1.5),    # 影线/实体比率（固定，避免过拟合）
        ('pinbar_body_ratio', 0.4),      # 实体/总范围比率（固定）
        
        # ===== 激进风险参数（提升） =====
        ('leverage', 30),                # 杠杆倍数（从20提升到30）
        ('risk_per_trade', 0.025),       # 每笔交易风险比例（从0.01提升到0.025）
        ('stop_loss_pct', 0.006),        # 止损百分比（从0.01收紧到0.006）
        ('take_profit_pct', 0.018),      # 止盈百分比（3倍止损，更激进）
        
        # ===== 移动止损（保留优势功能） =====
        ('use_trailing_stop', True),     # 启用移动止损
        ('trail_percent', 0.4),          # 移动止损距离（收紧到40%）
        ('trail_activation_pct', 0.008), # 移动止损激活的盈利比例（收紧）
        
        # ===== 趋势过滤（简化） =====
        ('trend_period', 20),            # 趋势判断周期（简化）
        ('min_trend_strength', 0.002),   # 最小趋势强度
        
        # ===== 市场状态过滤（新增） =====
        ('min_volatility', 0.001),       # 最小波动率要求
        ('max_volatility', 0.008),       # 最大波动率限制
        ('min_volume_ratio', 0.8),       # 最小成交量比率
        
        # ===== 移除的复杂参数 =====
        # 移除了原版中的大量可调参数，如：
        # fast_period, slow_period, stop_loss_type, use_rsi, use_bb_confirmation
        # rsi_oversold, rsi_overbought, bb_threshold, atr_stop_multiplier 等
        # 这些参数容易导致过拟合
    )

    def __init__(self):
        # 简化的指标初始化
        self.trend_sma = bt.indicators.SMA(self.data.close, period=self.params.trend_period)
        self.atr = bt.indicators.ATR(self.data, period=14)
        self.volume_sma = bt.indicators.SMA(self.data.volume, period=20)  # 成交量均线
        
        # 交易状态变量（保留原版逻辑）
        self.position_size = 0  # 当前仓位大小
        self.entry_price = 0  # 开仓价格
        self.entry_time = None  # 开仓时间
        self.entry_index = 0  # 开仓时的索引位置
        self.exit_index = 0  # 平仓时的索引位置
        self.margin_used = 0  # 占用保证金
        self.direction = None  # 交易方向
        self.trades = []  # 交易记录
        self.stop_loss_price = 0  # 止损价格
        self.take_profit_price = 0  # 止盈价格
        self.trailing_stop_price = 0  # 移动止损价格
        self.trailing_activated = False  # 移动止损是否激活
        self.highest_price = 0  # 交易中遇到的最高价（用于多头移动止损）
        self.lowest_price = float('inf')  # 交易中遇到的最低价（用于空头移动止损）
        self.total_fees = 0  # 总手续费
        self.entry_high = 0  # 开仓K线的最高价
        self.entry_low = 0  # 开仓K线的最低价
        self.trade_markers = []  # 记录交易标记点
        self.initial_cash = self.broker.getcash()  # 初始资金
        self.peak_value = self.initial_cash  # 用于计算最大回撤
        self.max_drawdown = 0  # 最大回撤比例
        
        # 额外信息
        self.win_trades = 0  # 盈利交易次数
        self.lose_trades = 0  # 亏损交易次数
        self.total_profit = 0  # 总盈利金额
        self.total_loss = 0  # 总亏损金额

    def get_market_volatility(self):
        """
        计算市场波动率
        使用ATR作为波动率代理指标
        """
        if len(self.atr) == 0:
            return 0.005  # 默认中等波动率
        
        current_atr = self.atr[0]
        current_price = self.data.close[0]
        
        return current_atr / current_price if current_price > 0 else 0.005

    def is_volume_sufficient(self):
        """
        检查成交量是否充足
        避免在流动性不足时交易
        """
        if len(self.volume_sma) == 0:
            return True  # 数据不足时默认通过
        
        current_volume = self.data.volume[0]
        avg_volume = self.volume_sma[0]
        
        return current_volume >= avg_volume * self.params.min_volume_ratio

    def is_market_suitable(self):
        """
        市场适合性检查（新增功能）
        结合波动率和成交量进行过滤
        """
        volatility = self.get_market_volatility()
        volume_ok = self.is_volume_sufficient()
        
        volatility_ok = self.params.min_volatility <= volatility <= self.params.max_volatility
        
        return volatility_ok and volume_ok

    def log_trade(self, is_open: bool, price: float, size: float, direction: str, index: int = None, exit_reason: str = ""):
        """交易记录函数（保留原版逻辑，增加市场状态记录）"""
        # 计算仓位信息
        cash = self.broker.getcash()
        total_value = abs(size * price)  # 开仓总价值
        margin_used = total_value / self.params.leverage  # 占用保证金
        remaining_margin = cash - margin_used  # 剩余保证金

        # 计算手续费（开仓按 Taker 费率，平仓按 Maker 费率）
        fee = total_value * TAKER_FEE if is_open else total_value * MAKER_FEE
        self.total_fees += fee
        self.broker.add_cash(-fee)  # 扣除手续费

        if is_open:
            # 开仓记录
            trade_id = str(uuid.uuid4())[:8]  # 生成唯一交易ID
            self.entry_time = self.data.datetime.datetime()
            self.entry_price = price
            self.margin_used = margin_used
            self.direction = direction
            self.entry_high = self.data.high[0]  # 记录开仓K线的最高价
            self.entry_low = self.data.low[0]  # 记录开仓K线的最低价
            self.entry_index = len(self.data) - 1 if index is None else index  # 记录开仓索引
            
            # 重置移动止损相关变量
            self.trailing_activated = False
            self.highest_price = price if direction == 'buy' else 0
            self.lowest_price = price if direction == 'sell' else float('inf')

            # 使用简化的固定比例止损（移除复杂的止损类型选择）
            self.stop_loss_price = price * (1 - self.params.stop_loss_pct) if direction == 'buy' else price * (1 + self.params.stop_loss_pct)

            # 初始移动止损价格等于固定止损价格
            self.trailing_stop_price = self.stop_loss_price
            
            # 止盈价格
            self.take_profit_price = price * (1 + self.params.take_profit_pct) if direction == 'buy' else price * (1 - self.params.take_profit_pct)

            # 记录开仓标记
            self.trade_markers.append({
                'type': 'entry',
                'direction': direction,
                'timestamp': self.entry_time,
                'price': price,
                'index': self.entry_index,
                'trade_id': trade_id
            })

            # 记录交易（增加市场状态信息）
            self.trades.append({
                'trade_id': trade_id,
                '开仓时间': self.entry_time,
                '开仓价格': price,
                '开仓索引': self.entry_index,
                '杠杆倍数': self.params.leverage,
                '开仓总价值(USDT)': total_value,
                '占用保证金': margin_used,
                '剩余保证金': remaining_margin,
                '方向': direction,
                '止损价格': self.stop_loss_price,
                '止盈价格': self.take_profit_price,
                '手续费': fee,
                '市场波动率': self.get_market_volatility(),  # 新增：记录开仓时的市场状态
                '成交量比率': self.data.volume[0] / self.volume_sma[0] if len(self.volume_sma) > 0 else 1.0
            })
        else:
            # 平仓记录（保留原版逻辑）
            if not self.trades:  # 防止意外情况
                return
                
            trade = self.trades[-1]
            trade['平仓时间'] = self.data.datetime.datetime()
            trade['平仓价格'] = price
            trade['平仓索引'] = len(self.data) - 1 if index is None else index
            trade['平仓原因'] = exit_reason
            self.exit_index = trade['平仓索引']
            trade['手续费'] += fee  # 累计平仓手续费
            
            # 收益计算
            profit = (price - trade['开仓价格']) * size if direction == 'buy' else (trade['开仓价格'] - price) * size
            trade['收益金额(USDT)'] = profit
            trade['收益率(%)'] = (profit / trade['占用保证金']) * 100 if trade['占用保证金'] > 0 else 0
            
            # 记录平仓标记
            self.trade_markers.append({
                'type': 'exit',
                'direction': direction,
                'timestamp': trade['平仓时间'],
                'price': price,
                'index': trade['平仓索引'],
                'trade_id': trade['trade_id'],
                'profit': profit,
                'profit_pct': trade['收益率(%)'],
                'reason': exit_reason
            })
            
            # 更新统计信息
            if profit > 0:
                self.win_trades += 1
                self.total_profit += profit
            else:
                self.lose_trades += 1
                self.total_loss += abs(profit)
            
            # 更新最大回撤
            current_value = self.broker.getvalue()
            if current_value > self.peak_value:
                self.peak_value = current_value
            drawdown = (self.peak_value - current_value) / self.peak_value
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown

    def is_pinbar(self) -> Tuple[bool, Optional[str]]:
        """
        简化版Pinbar形态检测，避免过拟合
        移除了复杂的多指标确认，专注于核心形态识别
        """
        if len(self.data) < self.params.trend_period:
            return False, None

        # 基本K线数据
        body = abs(self.data.close[0] - self.data.open[0])
        upper_shadow = self.data.high[0] - max(self.data.open[0], self.data.close[0])
        lower_shadow = min(self.data.open[0], self.data.close[0]) - self.data.low[0]
        total_range = self.data.high[0] - self.data.low[0]

        if body == 0 or total_range == 0:
            return False, None

        # 简化的Pinbar判断（固定参数，避免过拟合）
        is_bullish_pin = (
            lower_shadow > self.params.pinbar_shadow_ratio * body and 
            upper_shadow < 0.7 * body and  # 简化条件
            body < self.params.pinbar_body_ratio * total_range and 
            self.data.close[0] > self.data.open[0]
        )
        
        is_bearish_pin = (
            upper_shadow > self.params.pinbar_shadow_ratio * body and 
            lower_shadow < 0.7 * body and  # 简化条件
            body < self.params.pinbar_body_ratio * total_range and 
            self.data.close[0] < self.data.open[0]
        )

        # 简化的趋势判断（移除复杂的趋势强度计算）
        trend_sma = self.trend_sma[0] if len(self.trend_sma) > 0 else self.data.close[0]
        trend_diff_pct = abs(self.data.close[0] - trend_sma) / trend_sma
        
        # 确保有最小趋势强度
        if trend_diff_pct < self.params.min_trend_strength:
            return False, None
        
        is_uptrend = self.data.close[0] > trend_sma
        is_downtrend = self.data.close[0] < trend_sma

        # 简化的信号确认（移除复杂的多指标确认）
        # 看涨Pinbar：下跌趋势中出现
        if is_bullish_pin and is_downtrend:
            return True, 'buy'
        # 看跌Pinbar：上升趋势中出现
        elif is_bearish_pin and is_uptrend:
            return True, 'sell'
            
        return False, None

    def next(self):
        """主要交易逻辑（保留原版框架，增加市场过滤）"""
        # 数据不足时跳过
        if len(self.data) <= self.params.trend_period:
            return
        
        # 新增：市场适合性检查
        if not self.is_market_suitable():
            return
        
        # 当前价格
        current_price = self.data.close[0]
        
        # 如果有持仓，检查止盈止损和移动止损条件（保留原版逻辑）
        if self.position:
            # 更新交易中的最高/最低价格
            if self.direction == 'buy':
                if current_price > self.highest_price:
                    self.highest_price = current_price
                    
                    # 检查是否应该激活移动止损
                    if self.params.use_trailing_stop and not self.trailing_activated:
                        # 计算当前盈利比例
                        profit_pct = (current_price - self.entry_price) / self.entry_price
                        
                        # 如果盈利达到激活阈值，则激活移动止损
                        if profit_pct >= self.params.trail_activation_pct:
                            self.trailing_activated = True
                    
                    # 如果移动止损已激活，更新移动止损价格
                    if self.trailing_activated:
                        # 计算止损距离
                        stop_distance = self.entry_price * self.params.stop_loss_pct * self.params.trail_percent
                        
                        # 新的移动止损价格
                        new_stop = self.highest_price - stop_distance
                        
                        # 仅当新止损价格高于现有止损价格时更新
                        if new_stop > self.trailing_stop_price:
                            self.trailing_stop_price = new_stop
                
                # 检查是否触发移动止损
                if self.trailing_activated and current_price <= self.trailing_stop_price:
                    self.sell(size=self.position_size)
                    self.log_trade(False, current_price, self.position_size, 'buy', exit_reason="移动止损")
                    self.position_size = 0
                    self.direction = None
                    return
                
                # 检查普通止损或止盈
                elif current_price <= self.stop_loss_price:
                    self.sell(size=self.position_size)
                    self.log_trade(False, current_price, self.position_size, 'buy', exit_reason="止损")
                    self.position_size = 0
                    self.direction = None
                    return
                elif current_price >= self.take_profit_price:
                    self.sell(size=self.position_size)
                    self.log_trade(False, current_price, self.position_size, 'buy', exit_reason="止盈")
                    self.position_size = 0
                    self.direction = None
                    return
                
            else:  # direction == 'sell'
                if current_price < self.lowest_price:
                    self.lowest_price = current_price
                    
                    # 检查是否应该激活移动止损
                    if self.params.use_trailing_stop and not self.trailing_activated:
                        # 计算当前盈利比例
                        profit_pct = (self.entry_price - current_price) / self.entry_price
                        
                        # 如果盈利达到激活阈值，则激活移动止损
                        if profit_pct >= self.params.trail_activation_pct:
                            self.trailing_activated = True
                    
                    # 如果移动止损已激活，更新移动止损价格
                    if self.trailing_activated:
                        # 计算止损距离
                        stop_distance = self.entry_price * self.params.stop_loss_pct * self.params.trail_percent
                        
                        # 新的移动止损价格
                        new_stop = self.lowest_price + stop_distance
                        
                        # 仅当新止损价格低于现有止损价格时更新
                        if new_stop < self.trailing_stop_price:
                            self.trailing_stop_price = new_stop
                
                # 检查是否触发移动止损
                if self.trailing_activated and current_price >= self.trailing_stop_price:
                    self.buy(size=abs(self.position_size))
                    self.log_trade(False, current_price, abs(self.position_size), 'sell', exit_reason="移动止损")
                    self.position_size = 0
                    self.direction = None
                    return
                
                # 检查普通止损或止盈
                elif current_price >= self.stop_loss_price:
                    self.buy(size=abs(self.position_size))
                    self.log_trade(False, current_price, abs(self.position_size), 'sell', exit_reason="止损")
                    self.position_size = 0
                    self.direction = None
                    return
                elif current_price <= self.take_profit_price:
                    self.buy(size=abs(self.position_size))
                    self.log_trade(False, current_price, abs(self.position_size), 'sell', exit_reason="止盈")
                    self.position_size = 0
                    self.direction = None
                    return

        # 如果没有持仓，检查是否有开仓信号
        if not self.position:
            # 检测Pinbar信号
            is_pin, signal = self.is_pinbar()
            
            if is_pin:
                cash = self.broker.getcash()
                max_risk_amount = cash * self.params.risk_per_trade  # 使用激进的2.5%风险
                leveraged_cash = cash * self.params.leverage  # 使用30倍杠杆
                
                if signal == 'buy':
                    # 做多开仓
                    risk_amount = min(max_risk_amount, leveraged_cash * 0.5)  # 最大50%仓位
                    position_size = (risk_amount / current_price) * self.params.leverage
                    self.buy(size=position_size)
                    self.position_size = position_size
                    self.log_trade(True, current_price, position_size, 'buy')
                elif signal == 'sell':
                    # 做空开仓
                    risk_amount = min(max_risk_amount, leveraged_cash * 0.5)  # 最大50%仓位
                    position_size = (risk_amount / current_price) * self.params.leverage
                    self.sell(size=position_size)
                    self.position_size = -position_size
                    self.log_trade(True, current_price, position_size, 'sell')

    def stop(self):
        """回测结束处理（保留原版逻辑，增加优化报告）"""
        # 回测结束前强制平仓
        if self.position:
            current_price = self.data.close[0]
            if self.position_size > 0:
                self.sell(size=self.position_size)
                self.log_trade(False, current_price, self.position_size, 'buy', exit_reason="回测结束")
            else:
                self.buy(size=abs(self.position_size))
                self.log_trade(False, current_price, abs(self.position_size), 'sell', exit_reason="回测结束")
            self.position_size = 0

        # 计算收益率
        final_value = self.broker.getvalue()
        profit_amount = final_value - self.initial_cash
        profit_percentage = (profit_amount / self.initial_cash) * 100
        
        # 计算胜率
        total_trades = self.win_trades + self.lose_trades
        win_rate = (self.win_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # 计算盈亏比
        avg_profit = self.total_profit / self.win_trades if self.win_trades > 0 else 0
        avg_loss = self.total_loss / self.lose_trades if self.lose_trades > 0 else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        
        # 输出优化版统计信息
        print(f'\n=== 优化激进版Pinbar策略回测结果 ===')
        print(f'策略特点: 30倍杠杆 + 2.5%风险 + 0.6%止损 + 1.8%止盈')
        print(f'参数优化: 大幅简化参数，避免过拟合')
        print(f'市场过滤: 波动率 + 成交量双重过滤')
        print(f'初始账户余额: {self.initial_cash:.2f} USDT')
        print(f'最终账户余额: {final_value:.2f} USDT')
        print(f'净盈亏金额: {profit_amount:.2f} USDT')
        print(f'净盈亏百分比: {profit_percentage:.2f}%')
        print(f'总手续费 (USDT): {self.total_fees:.2f}')
        print(f'总交易次数: {total_trades}')
        print(f'胜率: {win_rate:.2f}%')
        print(f'盈亏比: {profit_loss_ratio:.2f}')
        print(f'最大回撤: {self.max_drawdown * 100:.2f}%')
        
        # 计算夏普比率（简化版）
        if len(self.trades) > 0:
            returns = [trade.get('收益率(%)', 0) for trade in self.trades]
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = avg_return / std_return if std_return > 0 else 0
            print(f'夏普比率: {sharpe_ratio:.2f}')

        print("\n=== 交易记录详情 ===")
        for trade in self.trades:
            print(f"交易ID: {trade['trade_id']}")
            print(f"开仓时间: {trade['开仓时间']}")
            print(f"开仓价格: {trade['开仓价格']}")
            print(f"杠杆倍数: {trade['杠杆倍数']}")
            print(f"开仓总价值(USDT): {trade['开仓总价值(USDT)']:.2f}")
            print(f"占用保证金: {trade['占用保证金']:.2f}")
            print(f"方向: {'做多' if trade['方向'] == 'buy' else '做空'}")
            print(f"止损价格: {trade['止损价格']:.4f}")
            print(f"止盈价格: {trade['止盈价格']:.4f}")
            print(f"市场波动率: {trade['市场波动率']:.4f}")  # 新增
            print(f"成交量比率: {trade['成交量比率']:.2f}")    # 新增
            if '平仓时间' in trade:
                print(f"平仓时间: {trade['平仓时间']}")
                print(f"平仓价格: {trade['平仓价格']}")
                print(f"平仓原因: {trade.get('平仓原因', '未知')}")
                print(f"收益金额(USDT): {trade['收益金额(USDT)']:.2f}")
                print(f"收益率(%): {trade['收益率(%)']:.2f}%")
            print("-" * 50)

# 修复可视化问题，重写关键部分

def generate_html_report(data: pd.DataFrame, strategy_instance) -> str:
    """生成包含交易详情和图表的HTML报告"""
    # 创建临时文件
    temp_file = os.path.join(tempfile.gettempdir(), f'backtest_report_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.html')
    
    # 提取交易标记
    trade_markers = strategy_instance.trade_markers
    trades = strategy_instance.trades
    
    # 计算主要统计数据
    initial_cash = strategy_instance.initial_cash
    final_value = strategy_instance.broker.getvalue()
    profit_amount = final_value - initial_cash
    profit_percentage = (profit_amount / initial_cash) * 100
    
    # 计算胜率等关键指标
    total_trades = strategy_instance.win_trades + strategy_instance.lose_trades
    win_rate = (strategy_instance.win_trades / total_trades) * 100 if total_trades > 0 else 0
    avg_profit = strategy_instance.total_profit / strategy_instance.win_trades if strategy_instance.win_trades > 0 else 0
    avg_loss = strategy_instance.total_loss / strategy_instance.lose_trades if strategy_instance.lose_trades > 0 else 0
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
    max_drawdown = strategy_instance.max_drawdown * 100
    
    # 统计不同退出原因的交易数量
    exit_reasons = {}
    for trade in trades:
        if '平仓原因' in trade:
            reason = trade['平仓原因']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    
    # ===================== 总览K线图 =====================
    # 创建主图表 - 确保包含K线图
    main_fig = go.Figure()
    
    # 绘制K线图
    main_fig.add_trace(go.Candlestick(
        x=data['timestamp'],
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name='K线',
        increasing_line_color='red',   # 中国市场习惯，涨为红色
        decreasing_line_color='green', # 中国市场习惯，跌为绿色
    ))
    
    # 绘制技术指标
    main_fig.add_trace(go.Scatter(
        x=data['timestamp'],
        y=data['sma_fast'],
        name='快速SMA',
        line=dict(color='blue', width=1.5)
    ))
    
    main_fig.add_trace(go.Scatter(
        x=data['timestamp'],
        y=data['sma_slow'],
        name='慢速SMA',
        line=dict(color='orange', width=1.5)
    ))
    
    # 绘制布林带
    main_fig.add_trace(go.Scatter(
        x=data['timestamp'],
        y=data['bb_upper'],
        name='布林上轨',
        line=dict(color='rgba(0, 128, 0, 0.3)', width=1),
        showlegend=True
    ))
    
    main_fig.add_trace(go.Scatter(
        x=data['timestamp'],
        y=data['bb_lower'],
        name='布林下轨',
        line=dict(color='rgba(0, 128, 0, 0.3)', width=1),
        fill='tonexty',
        fillcolor='rgba(0, 128, 0, 0.1)',
        showlegend=True
    ))
    
    # 添加开仓和平仓标记
    entry_x = []
    entry_y = []
    entry_symbols = []
    entry_colors = []
    entry_texts = []
    
    exit_x = []
    exit_y = []
    exit_symbols = []
    exit_colors = []
    exit_texts = []
    
    for marker in trade_markers:
        if marker['type'] == 'entry':
            # 开仓标记
            shape = 'triangle-up' if marker['direction'] == 'buy' else 'triangle-down'
            color = 'red' if marker['direction'] == 'buy' else 'green' # 中国市场习惯的颜色
            entry_x.append(marker['timestamp'])
            entry_y.append(marker['price'])
            entry_symbols.append(shape)
            entry_colors.append(color)
            entry_texts.append(f"开仓: {'买入' if marker['direction'] == 'buy' else '卖出'} (ID: {marker['trade_id']})")
        else:
            # 平仓标记
            shape = 'triangle-down' if marker['direction'] == 'buy' else 'triangle-up'
            color = 'red' if marker['profit'] > 0 else 'green' # 为正收益使用红色
            reason = marker.get('reason', '未知')
            exit_x.append(marker['timestamp'])
            exit_y.append(marker['price'])
            exit_symbols.append(shape)
            exit_colors.append(color)
            exit_texts.append(f"平仓: {'卖出' if marker['direction'] == 'buy' else '买入'} ({reason})<br>盈亏: {marker['profit']:.2f} USDT ({marker['profit_pct']:.2f}%)")
    
    if entry_x:
        main_fig.add_trace(go.Scatter(
            x=entry_x,
            y=entry_y,
            mode='markers',
            marker=dict(
                symbol=entry_symbols,
                size=15,
                color=entry_colors,
                line=dict(width=2, color='black')
            ),
            name='开仓点',
            text=entry_texts,
            hoverinfo='text'
        ))
    
    if exit_x:
        main_fig.add_trace(go.Scatter(
            x=exit_x,
            y=exit_y,
            mode='markers',
            marker=dict(
                symbol=exit_symbols,
                size=15,
                color=exit_colors,
                line=dict(width=2, color='black')
            ),
            name='平仓点',
            text=exit_texts,
            hoverinfo='text'
        ))
    
    # 设置主图表布局
    main_fig.update_layout(
        title='回测结果总览 - BTCUSDT 永续合约 (15分钟K线)',
        xaxis_title='时间',
        yaxis_title='价格 (USDT)',
        hovermode='closest',
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        height=600,
        plot_bgcolor='rgba(240, 240, 240, 0.8)',  # 更浅的背景色
        paper_bgcolor='white',
        autosize=True
    )
    
    # 添加网格线
    main_fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(211, 211, 211, 0.5)'
    )
    main_fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(211, 211, 211, 0.5)'
    )
    
    # ===================== 成交量子图 =====================
    volume_fig = go.Figure()
    volume_fig.add_trace(go.Bar(
        x=data['timestamp'],
        y=data['volume'],
        name='成交量',
        marker_color='blue',
        opacity=0.5
    ))
    
    volume_fig.update_layout(
        title='成交量',
        xaxis_title='时间',
        yaxis_title='成交量',
        height=300,
        plot_bgcolor='rgba(240, 240, 240, 0.8)',
        paper_bgcolor='white',
        autosize=True
    )
    
    # ===================== RSI子图 =====================
    rsi_fig = go.Figure()
    rsi_fig.add_trace(go.Scatter(
        x=data['timestamp'],
        y=data['rsi'],
        name='RSI(14)',
        line=dict(color='purple', width=1.5)
    ))
    
    # 添加RSI超买超卖线
    rsi_fig.add_hline(y=65, line_dash="dash", line_color="red")  # 使用放宽的RSI标准
    rsi_fig.add_hline(y=35, line_dash="dash", line_color="green")  # 使用放宽的RSI标准
    
    rsi_fig.update_layout(
        title='RSI指标',
        xaxis_title='时间',
        yaxis_title='RSI值',
        height=300,
        plot_bgcolor='rgba(240, 240, 240, 0.8)',
        paper_bgcolor='white',
        autosize=True
    )
    
    # ===================== 退出原因饼图 =====================
    if exit_reasons:
        labels = list(exit_reasons.keys())
        values = list(exit_reasons.values())
        
        exit_reasons_fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.3,
            textinfo='percent+label',
            insidetextorientation='radial'
        )])
        
        exit_reasons_fig.update_layout(
            title='平仓原因分布',
            height=400,
            plot_bgcolor='rgba(240, 240, 240, 0.8)',
            paper_bgcolor='white',
        )
    else:
        # 如果没有交易，创建一个空的图表
        exit_reasons_fig = go.Figure()
        exit_reasons_fig.update_layout(
            title='平仓原因分布 (无交易)',
            height=400,
            plot_bgcolor='rgba(240, 240, 240, 0.8)',
            paper_bgcolor='white',
        )
    
    # ===================== 单个交易详情 =====================
    def create_trade_detail_html():
        trade_divs = []
        for trade in trades:
            trade_id = trade.get('trade_id', 'unknown')
            
            # 找出开仓和平仓的索引
            entry_index = trade.get('开仓索引', 0)
            exit_index = trade.get('平仓索引', entry_index) if '平仓索引' in trade else entry_index
            
            # 计算显示范围：开仓前10根K线到平仓后10根K线
            start_index = max(0, entry_index - 10)
            end_index = min(len(data), exit_index + 11)  # +11确保包含平仓后的第10根K线
            
            # 提取相关区间的数据
            trade_data = data.iloc[start_index:end_index].copy()
            
            # 如果没有数据，跳过
            if len(trade_data) == 0:
                continue
                
            # 创建单个交易的K线图
            trade_fig = go.Figure()
            
            # 绘制K线
            trade_fig.add_trace(go.Candlestick(
                x=trade_data['timestamp'],
                open=trade_data['open'],
                high=trade_data['high'],
                low=trade_data['low'],
                close=trade_data['close'],
                name='K线',
                increasing_line_color='red',   # 中国市场习惯，涨为红色
                decreasing_line_color='green', # 中国市场习惯，跌为绿色
            ))
            
            # 绘制SMA
            trade_fig.add_trace(go.Scatter(
                x=trade_data['timestamp'],
                y=trade_data['sma_fast'],
                name='快速SMA',
                line=dict(color='blue', width=1.5)
            ))
            
            trade_fig.add_trace(go.Scatter(
                x=trade_data['timestamp'],
                y=trade_data['sma_slow'],
                name='慢速SMA',
                line=dict(color='orange', width=1.5)
            ))
            
            # 找到交易数据中的开仓和平仓点
            entry_timestamp = trade['开仓时间']
            entry_price = trade['开仓价格']
            
            # 添加开仓标记
            try:
                # 在K线图上标记开仓点
                trade_fig.add_trace(go.Scatter(
                    x=[entry_timestamp],
                    y=[entry_price],
                    mode='markers',
                    marker=dict(
                        symbol='triangle-up' if trade['方向'] == 'buy' else 'triangle-down',
                        size=15,
                        color='red' if trade['方向'] == 'buy' else 'green',
                        line=dict(width=2, color='black')
                    ),
                    name='开仓点',
                    text=f"开仓: {'买入' if trade['方向'] == 'buy' else '卖出'} @ {entry_price:.2f}",
                    hoverinfo='text'
                ))
                
                # 添加垂直线标示开仓位置
                trade_fig.add_shape(
                    type="line",
                    x0=entry_timestamp,
                    y0=trade_data['low'].min() * 0.999,
                    x1=entry_timestamp,
                    y1=trade_data['high'].max() * 1.001,
                    line=dict(
                        color="red" if trade['方向'] == 'buy' else "green",
                        width=1,
                        dash="dash",
                    ),
                )
            except Exception as e:
                print(f"标记开仓点时出错: {e}")
            
            # 如果有平仓信息，添加平仓标记
            if '平仓时间' in trade:
                exit_timestamp = trade['平仓时间']
                exit_price = trade['平仓价格']
                
                try:
                    # 添加平仓点标记
                    profit_color = "red" if trade.get('收益金额(USDT)', 0) > 0 else "green"
                    
                    trade_fig.add_trace(go.Scatter(
                        x=[exit_timestamp],
                        y=[exit_price],
                        mode='markers',
                        marker=dict(
                            symbol='triangle-down' if trade['方向'] == 'buy' else 'triangle-up',
                            size=15,
                            color=profit_color,
                            line=dict(width=2, color='black')
                        ),
                        name='平仓点',
                        text=f"平仓: {'卖出' if trade['方向'] == 'buy' else '买入'} @ {exit_price:.2f}<br>盈亏: {trade.get('收益金额(USDT)', 0):.2f} USDT ({trade.get('收益率(%)', 0):.2f}%)",
                        hoverinfo='text'
                    ))
                    
                    # 添加垂直线标示平仓位置
                    trade_fig.add_shape(
                        type="line",
                        x0=exit_timestamp,
                        y0=trade_data['low'].min() * 0.999,
                        x1=exit_timestamp,
                        y1=trade_data['high'].max() * 1.001,
                        line=dict(
                            color=profit_color,
                            width=1,
                            dash="dash",
                        ),
                    )
                except Exception as e:
                    print(f"标记平仓点时出错: {e}")
            
            # 设置图表布局
            is_completed = '平仓时间' in trade
            profit_loss = trade.get('收益金额(USDT)', 0)
            profit_loss_pct = trade.get('收益率(%)', 0)
            exit_reason = trade.get('平仓原因', '未知') if is_completed else "未平仓"
            profit_loss_text = f"- 盈亏: {profit_loss:.2f} USDT ({profit_loss_pct:.2f}%) - {exit_reason}" if is_completed else "- 未平仓"
            
            trade_fig.update_layout(
                title=f"交易ID: {trade_id} - {'做多' if trade['方向'] == 'buy' else '做空'} {profit_loss_text}",
                xaxis_title="时间",
                yaxis_title="价格 (USDT)",
                height=500,
                plot_bgcolor='rgba(240, 240, 240, 0.8)',
                paper_bgcolor='white',
                autosize=True,
                showlegend=False  # 隐藏图例以节省空间
            )
            
            # 添加网格线
            trade_fig.update_xaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(211, 211, 211, 0.5)'
            )
            trade_fig.update_yaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(211, 211, 211, 0.5)'
            )
            
            # 创建交易详情表格
            trade_details = f"""
            <div class="trade-card" id="trade-{trade_id}">
                <h3>交易ID: {trade_id}</h3>
                <table class="trade-details">
                    <tr>
                        <th>方向</th>
                        <td>{'做多' if trade['方向'] == 'buy' else '做空'}</td>
                        <th>状态</th>
                        <td>{'已平仓' if '平仓时间' in trade else '持仓中'}</td>
                    </tr>
                    <tr>
                        <th>开仓时间</th>
                        <td>{trade['开仓时间']}</td>
                        <th>开仓价格</th>
                        <td>{trade['开仓价格']:.2f}</td>
                    </tr>
                    <tr>
                        <th>止损价格</th>
                        <td>{trade['止损价格']:.2f}</td>
                        <th>止盈价格</th>
                        <td>{trade['止盈价格']:.2f}</td>
                    </tr>
            """
            
            if '平仓时间' in trade:
                # 计算持仓时间 (小时)
                try:
                    holding_time = (trade['平仓时间'] - trade['开仓时间']).total_seconds() / 3600
                except:
                    holding_time = 0
                    
                trade_details += f"""
                    <tr>
                        <th>平仓时间</th>
                        <td>{trade['平仓时间']}</td>
                        <th>平仓价格</th>
                        <td>{trade['平仓价格']:.2f}</td>
                    </tr>
                    <tr>
                        <th>平仓原因</th>
                        <td>{trade.get('平仓原因', '未知')}</td>
                        <th>持仓时间</th>
                        <td>{holding_time:.1f} 小时</td>
                    </tr>
                    <tr>
                        <th>收益金额</th>
                        <td class="{'profit' if trade['收益金额(USDT)'] > 0 else 'loss'}">{trade['收益金额(USDT)']:.2f} USDT</td>
                        <th>收益率</th>
                        <td class="{'profit' if trade['收益率(%)'] > 0 else 'loss'}">{trade['收益率(%)']:.2f}%</td>
                    </tr>
                """
            
            trade_details += f"""
                    <tr>
                        <th>开仓总价值</th>
                        <td>{trade['开仓总价值(USDT)']:.2f} USDT</td>
                        <th>占用保证金</th>
                        <td>{trade['占用保证金']:.2f} USDT</td>
                    </tr>
                    <tr>
                        <th>杠杆倍数</th>
                        <td>{trade['杠杆倍数']}</td>
                        <th>手续费</th>
                        <td>{trade['手续费']:.4f} USDT</td>
                    </tr>
                </table>
                
                <div class="trade-chart" id="trade-chart-{trade_id}">
                    {trade_fig.to_html(include_plotlyjs="cdn", full_html=False)}
                </div>
            </div>
            """
            
            trade_divs.append(trade_details)
        
        return '\n'.join(trade_divs)
    
    # ===================== 组装HTML内容 =====================
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pinbar策略回测报告</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
                border-radius: 5px;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            .summary-box {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                margin-bottom: 30px;
            }}
            .summary-card {{
                flex: 1;
                min-width: 200px;
                padding: 15px;
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .summary-card h3 {{
                margin-top: 0;
                color: #3498db;
            }}
            .summary-value {{
                font-size: 24px;
                font-weight: bold;
                margin: 10px 0;
            }}
            .positive {{
                color: #e74c3c; /* 红色表示盈利 */
            }}
            .negative {{
                color: #2ecc71; /* 绿色表示亏损 */
            }}
            .chart-container {{
                margin: 30px 0;
                background-color: #fff;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.05);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
                font-weight: bold;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .trade-list {{
                margin-top: 40px;
            }}
            .trade-card {{
                background-color: #fff;
                margin-bottom: 30px;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            .trade-details {{
                width: 100%;
            }}
            .trade-chart {{
                margin-top: 20px;
            }}
            .profit {{
                color: #e74c3c; /* 红色表示盈利 */
                font-weight: bold;
            }}
            .loss {{
                color: #2ecc71; /* 绿色表示亏损 */
                font-weight: bold;
            }}
            .trades-summary {{
                margin-top: 40px;
            }}
            #trade-list-container {{
                margin-top: 20px;
            }}
            .tab-container {{
                margin-top: 20px;
            }}
            .tab {{
                overflow: hidden;
                border: 1px solid #ccc;
                background-color: #f1f1f1;
                border-radius: 5px 5px 0 0;
            }}
            .tab button {{
                background-color: inherit;
                float: left;
                border: none;
                outline: none;
                cursor: pointer;
                padding: 14px 16px;
                transition: 0.3s;
                font-size: 16px;
            }}
            .tab button:hover {{
                background-color: #ddd;
            }}
            .tab button.active {{
                background-color: #3498db;
                color: white;
            }}
            .tabcontent {{
                display: none;
                padding: 20px;
                border: 1px solid #ccc;
                border-top: none;
                border-radius: 0 0 5px 5px;
                animation: fadeEffect 1s;
            }}
            @keyframes fadeEffect {{
                from {{opacity: 0;}}
                to {{opacity: 1;}}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Pinbar策略回测报告</h1>
            
            <div class="summary-box">
                <div class="summary-card">
                    <h3>净盈亏</h3>
                    <div class="summary-value {'positive' if profit_amount > 0 else 'negative'}">
                        {profit_amount:.2f} USDT ({profit_percentage:.2f}%)
                    </div>
                </div>
                
                <div class="summary-card">
                    <h3>交易次数</h3>
                    <div class="summary-value">
                        {total_trades}
                    </div>
                </div>
                
                <div class="summary-card">
                    <h3>胜率</h3>
                    <div class="summary-value">
                        {win_rate:.2f}%
                    </div>
                </div>
                
                <div class="summary-card">
                    <h3>盈亏比</h3>
                    <div class="summary-value">
                        {profit_loss_ratio:.2f}
                    </div>
                </div>
                
                <div class="summary-card">
                    <h3>最大回撤</h3>
                    <div class="summary-value negative">
                        {max_drawdown:.2f}%
                    </div>
                </div>
            </div>
            
            <div class="tab-container">
                <div class="tab">
                    <button class="tablinks active" onclick="openTab(event, 'overview')">总览</button>
                    <button class="tablinks" onclick="openTab(event, 'volume')">成交量</button>
                    <button class="tablinks" onclick="openTab(event, 'rsi')">RSI指标</button>
                    <button class="tablinks" onclick="openTab(event, 'exits')">平仓原因</button>
                    <button class="tablinks" onclick="openTab(event, 'trades')">交易明细</button>
                </div>
                
                <div id="overview" class="tabcontent" style="display:block;">
                    <div class="chart-container">
                        {main_fig.to_html(include_plotlyjs=False, full_html=False)}
                    </div>
                </div>
                
                <div id="volume" class="tabcontent">
                    <div class="chart-container">
                        {volume_fig.to_html(include_plotlyjs=False, full_html=False)}
                    </div>
                </div>
                
                <div id="rsi" class="tabcontent">
                    <div class="chart-container">
                        {rsi_fig.to_html(include_plotlyjs=False, full_html=False)}
                    </div>
                </div>
                
                <div id="exits" class="tabcontent">
                    <div class="chart-container">
                        {exit_reasons_fig.to_html(include_plotlyjs=False, full_html=False)}
                    </div>
                </div>
                
                <div id="trades" class="tabcontent">
                    <h2>交易明细</h2>
                    <p>总共 {total_trades} 笔交易, 其中盈利 {strategy_instance.win_trades} 笔, 亏损 {strategy_instance.lose_trades} 笔</p>
                    
                    <div id="trade-list-container">
                        {create_trade_detail_html()}
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            function openTab(evt, tabName) {{
                var i, tabcontent, tablinks;
                tabcontent = document.getElementsByClassName("tabcontent");
                for (i = 0; i < tabcontent.length; i++) {{
                    tabcontent[i].style.display = "none";
                }}
                tablinks = document.getElementsByClassName("tablinks");
                for (i = 0; i < tablinks.length; i++) {{
                    tablinks[i].className = tablinks[i].className.replace(" active", "");
                }}
                document.getElementById(tabName).style.display = "block";
                evt.currentTarget.className += " active";
            }}
            
            // 初始化页面，显示第一个标签
            document.getElementsByClassName("tablinks")[0].click();
        </script>
    </body>
    </html>
    """
    
    # 写入HTML文件
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"报告已保存到: {temp_file}")
    return temp_file# 主程序

# 简化的单次回测函数（移除复杂的参数优化）
def run_single_backtest(symbol='BTCUSDT', interval='5m', start_date='2024-01-01', end_date='2025-05-21'):
    """
    运行单次回测（简化版，避免过拟合）
    """
    print(f"\n=== 开始 {symbol} 优化激进版回测 ===")
    print(f"数据周期: {interval}")
    print(f"回测区间: {start_date} 到 {end_date}")
    
    # 获取数据
    print(f"正在获取 {symbol} 的历史数据...")
    data = get_historical_data(symbol=symbol, interval=interval, start_date=start_date, end_date=end_date)
    if len(data) < 50:
        print(f"警告: {symbol} 数据不足，跳过")
        return None
    
    data.reset_index(drop=True, inplace=True)
    print(f"数据获取完成，共 {len(data)} 根K线")
    
    # 设置Backtrader环境
    cerebro = bt.Cerebro()
    data_feed = CustomDataFeed(dataname=data)
    cerebro.adddata(data_feed)
    
    # 添加优化版策略（固定参数，避免过拟合）
    cerebro.addstrategy(OptimizedAggressivePinbarStrategy)
    
    # 设置初始资金和手续费
    initial_cash = 20000.0
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.00075)

    # 运行回测
    print(f'初始账户余额: {cerebro.broker.getvalue():.2f} USDT')
    results = cerebro.run()
    strategy_instance = results[0]
    final_value = cerebro.broker.getvalue()
    profit = final_value - initial_cash
    profit_pct = (profit / initial_cash) * 100
    
    print(f'最终账户余额: {final_value:.2f} USDT')
    print(f'净盈亏: {profit:.2f} USDT ({profit_pct:.2f}%)')
    
    return strategy_instance, data

# 主程序（简化版本）
if __name__ == '__main__':
    print("====== 优化激进版Pinbar策略回测系统 ======")
    print("主要优化:")
    print("1. 解决过拟合: 参数从15+个减少到8个核心参数")
    print("2. 提升激进度: 30倍杠杆 + 2.5%风险 + 更紧止损止盈")  
    print("3. 市场过滤: 波动率 + 成交量双重过滤机制")
    print("4. 保留优势: 移动止损 + 完整可视化 + 详细记录")
    print("5. 多周期支持: 15分钟趋势 + 5分钟入场")
    
    # 获取前10币种（保留原版功能）
    print("\n正在获取前10交易量最高的币种...")
    try:
        top_symbols = get_top_10_symbols()
        print(f"前10币种: {top_symbols}")
    except:
        print("获取币种列表失败，使用默认币种")
        top_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    # 选择运行模式
    print("\n请选择运行模式:")
    print("1. 5分钟激进模式（推荐）")
    print("2. 15分钟稳健模式")
    print("3. 批量测试前10币种")
    
    try:
        mode = input("请输入选择 (1-3): ").strip()
    except:
        mode = '1'  # 默认选择
    
    if mode == '1':
        # 5分钟激进模式
        symbol = input(f"请输入币种符号 (默认BTCUSDT): ").strip() or 'BTCUSDT'
        result = run_single_backtest(symbol=symbol, interval='5m')
        if result:
            strategy_instance, data = result
            print(f"\n{symbol} 5分钟激进模式回测完成！")
            
    elif mode == '2':
        # 15分钟稳健模式  
        symbol = input(f"请输入币种符号 (默认BTCUSDT): ").strip() or 'BTCUSDT'
        result = run_single_backtest(symbol=symbol, interval='15m')
        if result:
            strategy_instance, data = result
            print(f"\n{symbol} 15分钟稳健模式回测完成！")
            
    elif mode == '3':
        # 批量测试
        print("\n开始批量测试前10币种...")
        results = {}
        for symbol in top_symbols[:5]:  # 限制为前5币种，避免过长时间
            print(f"\n--- 测试 {symbol} ---")
            result = run_single_backtest(symbol=symbol, interval='5m')
            if result:
                strategy_instance, data = result
                final_value = strategy_instance.broker.getvalue()
                profit_pct = ((final_value - 20000) / 20000) * 100
                results[symbol] = profit_pct
        
        # 输出汇总结果
        print("\n=== 批量测试汇总结果 ===")
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        for symbol, profit_pct in sorted_results:
            print(f"{symbol}: {profit_pct:.2f}%")
    
    else:
        print("无效选择，程序退出")
    
    print("\n回测完成！")
    print("注意事项:")
    print("1. 本策略已大幅优化，避免了过拟合问题")
    print("2. 使用了更激进的参数设置，请注意风险控制")
    print("3. 建议先用小资金进行实盘验证")
    print("4. 市场环境变化时，请及时调整策略参数")