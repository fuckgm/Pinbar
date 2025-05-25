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
# Pinbar策略思维导图 - 放宽条件版

## 一、策略核心逻辑
1. Pinbar形态识别
   - 下影线/实体比例 > pinbar_shadow_ratio (降为1.8) -> 看涨Pinbar
   - 上影线/实体比例 > pinbar_shadow_ratio (降为1.8) -> 看跌Pinbar
   - 实体/K线总高度 < pinbar_body_ratio (提高到0.4) -> 更宽松的实体要求

2. 可选多重指标确认 (通过参数开关控制)
   - RSI指标 (可选)
     - RSI < rsi_oversold (默认35) -> 支持看涨信号 (放宽RSI超卖标准)
     - RSI > rsi_overbought (默认65) -> 支持看跌信号 (放宽RSI超买标准)
   - 布林带位置 (可选)
     - 价格接近下轨 -> 支持看涨信号 (放宽接近标准，80%而非原来的95%)
     - 价格接近上轨 -> 支持看跌信号 (放宽接近标准，120%而非原来的105%)
   - 均线趋势 (基础条件，保留)
     - 价格低于慢速SMA -> 下跌趋势，寻找看涨Pinbar
     - 价格高于慢速SMA -> 上涨趋势，寻找看跌Pinbar

3. 放宽开仓条件
   - 只需满足Pinbar形态 + 趋势条件 + 任一附加指标(如启用)
   - 不再要求同时满足所有指标条件

# Pinbar策略回测系统 (优化升级版)

## 一、主要改进

基于您的反馈，我们对Pinbar策略回测系统进行了全面优化：

1. **修复可视化问题**：
   - 总览界面现在正确显示完整K线图及指标
   - 交易明细中加入清晰的开平仓箭头标记
   - 调整为显示开仓前10根至平仓后10根K线，更加聚焦

2. **增加移动止损功能**：
   - 在交易盈利达到设定阈值后自动激活移动止损
   - 有效解决"涨了很多也不止盈，最后亏损出局"的问题

3. **增加趋势过滤功能**：
   - 使用长周期均线判断整体趋势方向
   - 只在趋势明确时进行交易，提高成功率

4. **全新参数优化功能**：
   - 自动测试多种参数组合
   - 找出最优参数并生成详细的优化报告
   - 支持按盈利能力、胜率等多维度排序

## 二、新增运行模式

系统现在提供两种运行模式：

### 1. 单次回测模式
- 使用自定义参数进行单次回测
- 可以灵活调整各项指标和参数
- 适合手动探索不同参数的效果

### 2. 参数优化模式
- 自动测试多组预设参数组合
- 找出盈利能力最强的参数组合
- 使用最优参数进行最终回测
- 生成完整的优化结果报表

## 三、使用指南

### 运行程序

1. 确保安装了所有所需依赖：
   ```
   pip install backtrader pandas python-binance plotly numpy
   ```

2. 准备API密钥文件(key.json)：
   ```json
   {
       "api_key": "您的币安API密钥",
       "api_secret": "您的币安API密钥"
   }
   ```

3. 运行主程序：
   ```
   python pinbar_strategy.py
   ```

4. 选择运行模式：
   - 模式1: 单次回测(自定义参数)
   - 模式2: 参数优化(自动寻找最佳参数)


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

# 获取历史K线数据
def get_historical_data(symbol: str = 'BTCUSDT', interval: str = '15m', start_date: str = '2024-01-01', end_date: str = '2025-05-21'):
    start_timestamp = int(datetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_timestamp = int(datetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
    klines = client.get_historical_klines(symbol, interval, start_timestamp, end_timestamp)
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    # 计算技术指标
    df = calculate_indicators(df)
    return df

# 计算技术指标
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

# 增强版Pinbar策略（放宽条件版）
# 在EnhancedPinbarFuturesStrategy类中添加移动止损功能和趋势筛选

class EnhancedPinbarFuturesStrategy(bt.Strategy):
    params = (
        ('fast_period', 8),  # 快线周期
        ('slow_period', 16),  # 慢线周期
        ('pinbar_shadow_ratio', 1.8),  # 影线/实体比率
        ('pinbar_body_ratio', 0.4),  # 实体/总范围比率
        ('leverage', 20),  # 杠杆倍数
        ('risk_per_trade', 0.01),  # 每笔交易风险比例
        ('stop_loss_pct', 0.01),  # 止损百分比
        ('take_profit_pct', 0.025),  # 止盈百分比，增加到2.5倍止损
        ('max_position_size', 0.5),  # 最大仓位比例
        ('stop_loss_type', 'fixed'),  # 止损方式：'fixed'（固定比例）、'pinbar'（Pinbar高低点）或'atr'（ATR动态）
        ('use_rsi', True),  # 是否使用RSI过滤信号
        ('use_bb_confirmation', True),  # 是否使用布林带确认
        ('rsi_oversold', 35),  # RSI超卖线
        ('rsi_overbought', 65),  # RSI超买线
        ('bb_threshold', 0.2),  # 布林带阈值
        ('atr_stop_multiplier', 2.0),  # ATR止损倍数
        ('min_trend_strength', 0.001),  # 最小趋势强度
        ('use_trailing_stop', True),  # 启用移动止损
        ('trail_percent', 0.5),  # 移动止损距离，为原止损距离的50%
        ('trail_activation_pct', 0.01),  # 移动止损激活的盈利比例 (1%)
        ('use_trend_filter', True),  # 启用趋势过滤
        ('trend_period', 30),  # 趋势判断周期
    )

    def __init__(self):
        # 初始化指标和变量
        self.fast_sma = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.slow_sma = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.trend_sma = bt.indicators.SMA(self.data.close, period=self.params.trend_period)  # 长周期均线用于判断趋势
        
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

    def log_trade(self, is_open: bool, price: float, size: float, direction: str, index: int = None, exit_reason: str = ""):
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

            # 止盈止损价格计算
            if self.params.stop_loss_type == 'fixed':
                # 固定比例止损
                self.stop_loss_price = price * (1 - self.params.stop_loss_pct) if direction == 'buy' else price * (1 + self.params.stop_loss_pct)
            elif self.params.stop_loss_type == 'pinbar':
                # Pinbar高低点止损
                self.stop_loss_price = self.entry_low if direction == 'buy' else self.entry_high
            elif self.params.stop_loss_type == 'atr':
                # ATR动态止损
                atr_value = self.data.atr[0] if hasattr(self.data, 'atr') else 0
                atr_stop = atr_value * self.params.atr_stop_multiplier
                self.stop_loss_price = price - atr_stop if direction == 'buy' else price + atr_stop

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

            # 记录交易
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
                '手续费': fee
            })
        else:
            # 平仓记录
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
        """Pinbar形态检测，放宽条件版"""
        if len(self.data) < max(self.params.fast_period, self.params.slow_period):
            return False, None

        body = abs(self.data.close[0] - self.data.open[0])
        upper_shadow = self.data.high[0] - max(self.data.open[0], self.data.close[0])
        lower_shadow = min(self.data.open[0], self.data.close[0]) - self.data.low[0]
        total_range = self.data.high[0] - self.data.low[0]

        if body == 0 or total_range == 0:
            return False, None

        # 看涨Pinbar：下影线长，实体小，收盘价高于开盘价
        is_bullish_pin = (lower_shadow > self.params.pinbar_shadow_ratio * body and 
                         upper_shadow < 0.7 * body and  # 放宽上影线要求
                         body < self.params.pinbar_body_ratio * total_range and 
                         self.data.close[0] > self.data.open[0])
        
        # 看跌Pinbar：上影线长，实体小，收盘价低于开盘价
        is_bearish_pin = (upper_shadow > self.params.pinbar_shadow_ratio * body and 
                         lower_shadow < 0.7 * body and  # 放宽下影线要求
                         body < self.params.pinbar_body_ratio * total_range and 
                         self.data.close[0] < self.data.open[0])

        # 基础趋势判断
        sma = self.slow_sma[0] if len(self.slow_sma) > 0 else self.data.close.get(size=self.params.slow_period).mean()
        trend_diff_pct = abs(self.data.close[0] - sma) / sma  # 计算趋势强度
        
        is_uptrend = self.data.close[0] > sma and trend_diff_pct >= self.params.min_trend_strength
        is_downtrend = self.data.close[0] < sma and trend_diff_pct >= self.params.min_trend_strength

        # 加强趋势判断 - 使用长期均线
        if self.params.use_trend_filter and len(self.trend_sma) > 0:
            # 只有当价格方向与趋势一致时才开仓
            # 多头：价格和短期SMA都在长期SMA上方
            long_trend_ok = self.data.close[0] > self.trend_sma[0] and self.slow_sma[0] > self.trend_sma[0]
            # 空头：价格和短期SMA都在长期SMA下方
            short_trend_ok = self.data.close[0] < self.trend_sma[0] and self.slow_sma[0] < self.trend_sma[0]
        else:
            long_trend_ok = True
            short_trend_ok = True

        # 附加指标确认（可选）
        indicator_signals = []
        
        # RSI指标确认（可选）
        if self.params.use_rsi:
            rsi_value = self.data.rsi[0] if hasattr(self.data, 'rsi') else 50
            rsi_bull_signal = rsi_value < self.params.rsi_oversold
            rsi_bear_signal = rsi_value > self.params.rsi_overbought
            indicator_signals.append((rsi_bull_signal, rsi_bear_signal))
        
        # 布林带确认（可选）
        if self.params.use_bb_confirmation:
            bb_upper = self.data.bb_upper[0] if hasattr(self.data, 'bb_upper') else float('inf')
            bb_lower = self.data.bb_lower[0] if hasattr(self.data, 'bb_lower') else 0
            # 放宽靠近布林带的判断标准
            near_upper_band = self.data.close[0] > bb_upper * (1 - self.params.bb_threshold)
            near_lower_band = self.data.close[0] < bb_lower * (1 + self.params.bb_threshold)
            indicator_signals.append((near_lower_band, near_upper_band))
        
        # 如果没有启用任何附加指标，添加一个默认为True的信号
        if not indicator_signals:
            indicator_signals.append((True, True))
        
        # 检查是否有任一附加指标给出信号
        has_bull_signal = any(signal[0] for signal in indicator_signals)
        has_bear_signal = any(signal[1] for signal in indicator_signals)

        # 看涨Pinbar：下跌趋势中，任一附加指标支持，趋势过滤通过
        if is_bullish_pin and is_downtrend and has_bull_signal and long_trend_ok:
            return True, 'buy'
        # 看跌Pinbar：上升趋势中，任一附加指标支持，趋势过滤通过
        elif is_bearish_pin and is_uptrend and has_bear_signal and short_trend_ok:
            return True, 'sell'
        return False, None

    def next(self):
        # 数据不足时跳过
        if len(self.data) <= max(self.params.fast_period, self.params.slow_period, self.params.trend_period):
            return
        
        # 当前价格
        current_price = self.data.close[0]
        
        # 如果有持仓，检查止盈止损和移动止损条件
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
                max_risk_amount = cash * self.params.risk_per_trade
                leveraged_cash = cash * self.params.leverage
                
                if signal == 'buy':
                    # 做多开仓
                    risk_amount = min(max_risk_amount, leveraged_cash * self.params.max_position_size)
                    position_size = (risk_amount / current_price) * self.params.leverage
                    self.buy(size=position_size)
                    self.position_size = position_size
                    self.log_trade(True, current_price, position_size, 'buy')
                elif signal == 'sell':
                    # 做空开仓
                    risk_amount = min(max_risk_amount, leveraged_cash * self.params.max_position_size)
                    position_size = (risk_amount / current_price) * self.params.leverage
                    self.sell(size=position_size)
                    self.position_size = -position_size
                    self.log_trade(True, current_price, position_size, 'sell')

    def stop(self):
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
        
        # 输出交易记录和统计信息
        print(f'初始账户余额: {self.initial_cash:.2f} USDT')
        print(f'最终账户余额: {final_value:.2f} USDT')
        print(f'净盈亏金额: {profit_amount:.2f} USDT')
        print(f'净盈亏百分比: {profit_percentage:.2f}%')
        print(f'总手续费 (USDT): {self.total_fees:.2f}')
        print(f'总交易次数: {total_trades}')
        print(f'胜率: {win_rate:.2f}%')
        print(f'盈亏比: {profit_loss_ratio:.2f}')
        print(f'最大回撤: {self.max_drawdown * 100:.2f}%')
        # 生成并打印统计报告
        report = self.generate_txt_report()
        print(report)

        print("\n交易记录:")
        for trade in self.trades:
            print(f"交易ID: {trade['trade_id']}")
            print(f"开仓时间: {trade['开仓时间']}")
            print(f"开仓价格: {trade['开仓价格']}")
            print(f"杠杆倍数: {trade['杠杆倍数']}")
            print(f"开仓总价值(USDT): {trade['开仓总价值(USDT)']:.2f}")
            print(f"占用保证金: {trade['占用保证金']:.2f}")
            print(f"剩余保证金: {trade['剩余保证金']:.2f}")
            print(f"方向: {'做多' if trade['方向'] == 'buy' else '做空'}")
            print(f"止损价格: {trade['止损价格']:.2f}")
            print(f"止盈价格: {trade['止盈价格']:.2f}")
            print(f"手续费 (USDT): {trade['手续费']:.2f}")
            if '平仓时间' in trade:
                print(f"平仓时间: {trade['平仓时间']}")
                print(f"平仓价格: {trade['平仓价格']}")
                print(f"平仓原因: {trade.get('平仓原因', '未知')}")
                print(f"收益金额(USDT): {trade['收益金额(USDT)']:.2f}")
                print(f"收益率(%): {trade['收益率(%)']:.2f}%")
            print("-" * 50)

def generate_txt_report(self) -> str:
    """生成文本格式的统计报告"""
    report = ["=== Pinbar策略回测统计报告 ===\n"]
    report.append(f"报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} JST\n")
    report.append(f"初始账户余额: {self.initial_cash:.2f} USDT\n")
    report.append(f"最终账户余额: {self.broker.getvalue():.2f} USDT\n")
    report.append(f"净盈亏金额: {(self.broker.getvalue() - self.initial_cash):.2f} USDT\n")
    report.append(f"净盈亏百分比: {((self.broker.getvalue() - self.initial_cash) / self.initial_cash * 100):.2f}%\n")
    report.append(f"总手续费: {self.total_fees:.2f} USDT\n")
    report.append(f"总交易次数: {len(self.trades)}\n")
    report.append(f"盈利交易次数: {self.win_trades}\n")
    report.append(f"亏损交易次数: {self.lose_trades}\n")
    win_rate = (self.win_trades / len(self.trades) * 100) if len(self.trades) > 0 else 0
    report.append(f"胜率: {win_rate:.2f}%\n")
    avg_profit = self.total_profit / self.win_trades if self.win_trades > 0 else 0
    avg_loss = self.total_loss / self.lose_trades if self.lose_trades > 0 else 0
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
    report.append(f"盈亏比: {profit_loss_ratio:.2f}\n")
    report.append(f"最大回撤: {self.max_drawdown * 100:.2f}%\n")
    report.append("\n=== 交易明细 ===\n")
    for trade in self.trades:
        report.append(f"交易ID: {trade['trade_id']}")
        report.append(f"方向: {'做多' if trade['方向'] == 'buy' else '做空'}")
        report.append(f"开仓时间: {trade['开仓时间']}")
        report.append(f"开仓价格: {trade['开仓价格']:.2f}")
        report.append(f"平仓时间: {trade.get('平仓时间', '未平仓')}")
        report.append(f"平仓价格: {trade.get('平仓价格', '-'):2f}")
        report.append(f"平仓原因: {trade.get('平仓原因', '未平仓')}")
        report.append(f"收益金额: {trade.get('收益金额(USDT)', 0):.2f} USDT")
        report.append(f"收益率: {trade.get('收益率(%)', 0):.2f}%")
        report.append("-" * 50)
    return "\n".join(report)

# 生成HTML报告
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

# 参数优化功能代码

def optimize_parameters(data, initial_cash=20000.0):
    """
    使用网格搜索优化策略参数
    """
    # 定义参数网格
    param_grid = {
        'pinbar_shadow_ratio': [1.5, 1.8, 2.0, 2.2],  # 影线/实体比率
        'pinbar_body_ratio': [0.3, 0.35, 0.4, 0.45],  # 实体/总范围比率
        'stop_loss_pct': [0.008, 0.01, 0.012, 0.015],  # 止损百分比
        'take_profit_factor': [2.0, 2.5, 3.0],  # 止盈系数 (相对于止损)
        'trail_activation_pct': [0.005, 0.01, 0.015],  # 移动止损激活阈值
        'trail_percent': [0.3, 0.5, 0.7],  # 移动止损距离系数
        'use_rsi': [True, False],  # 是否使用RSI
        'use_bb': [True, False],  # 是否使用布林带
        'use_trend_filter': [True, False],  # 是否使用趋势过滤
        'use_trailing_stop': [True, False],  # 是否使用移动止损
    }
    
    # 固定参数
    fixed_params = {
        'stop_loss_type': 'fixed',  # 止损类型
        'risk_per_trade': 0.01,     # 每笔交易风险
        'trend_period': 30,         # 趋势周期
        'rsi_oversold': 35,         # RSI超卖线
        'rsi_overbought': 65,       # RSI超买线
    }
    
    # 创建所有参数组合
    param_combinations = []
    
    # 为了减少计算量，我们只选择一些关键参数的组合
    # 这是一种优化方法，您可以根据需要调整参数组合
    for shadow_ratio in param_grid['pinbar_shadow_ratio']:
        for body_ratio in param_grid['pinbar_body_ratio']:
            for stop_loss in param_grid['stop_loss_pct']:
                # 选择一些关键组合，而不是所有组合
                key_combinations = [
                    {
                        'pinbar_shadow_ratio': shadow_ratio,
                        'pinbar_body_ratio': body_ratio,
                        'stop_loss_pct': stop_loss,
                        'take_profit_pct': stop_loss * 2.5,
                        'use_rsi': True,
                        'use_bb_confirmation': True,
                        'use_trend_filter': True,
                        'use_trailing_stop': True,
                        'trail_activation_pct': 0.01,
                        'trail_percent': 0.5
                    },
                    {
                        'pinbar_shadow_ratio': shadow_ratio,
                        'pinbar_body_ratio': body_ratio,
                        'stop_loss_pct': stop_loss,
                        'take_profit_pct': stop_loss * 2.5,
                        'use_rsi': False,
                        'use_bb_confirmation': False,
                        'use_trend_filter': True,
                        'use_trailing_stop': True,
                        'trail_activation_pct': 0.01,
                        'trail_percent': 0.5
                    },
                    {
                        'pinbar_shadow_ratio': shadow_ratio,
                        'pinbar_body_ratio': body_ratio,
                        'stop_loss_pct': stop_loss,
                        'take_profit_pct': stop_loss * 2.0,
                        'use_rsi': True,
                        'use_bb_confirmation': True,
                        'use_trend_filter': True,
                        'use_trailing_stop': False,
                        'trail_activation_pct': 0.01,
                        'trail_percent': 0.5
                    }
                ]
                param_combinations.extend(key_combinations)
    
    # 避免测试太多组合，造成计算量过大
    if len(param_combinations) > 50:
        print(f"参数组合过多 ({len(param_combinations)}), 随机选择50组进行测试...")
        import random
        random.shuffle(param_combinations)
        param_combinations = param_combinations[:50]
    
    print(f"将测试 {len(param_combinations)} 组参数组合...")
    
    # 存储结果
    results = []
    
    # 循环测试每组参数
    for i, params in enumerate(param_combinations):
        print(f"测试参数组合 {i+1}/{len(param_combinations)}: {params}")
        
        # 合并固定参数
        params.update(fixed_params)
        
        # 创建Backtrader环境
        cerebro = bt.Cerebro()
        data_feed = CustomDataFeed(dataname=data)
        cerebro.adddata(data_feed)
        
        # 添加策略
        cerebro.addstrategy(EnhancedPinbarFuturesStrategy, **params)
        
        # 设置初始资金
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=0.00075)
        
        # 运行回测
        print(f"初始账户余额: {cerebro.broker.getvalue():.2f} USDT")
        strategies = cerebro.run()
        final_value = cerebro.broker.getvalue()
        profit = final_value - initial_cash
        profit_pct = (profit / initial_cash) * 100
        
        # 获取策略实例
        strategy = strategies[0]
        
        # 计算其他指标
        total_trades = strategy.win_trades + strategy.lose_trades
        win_rate = (strategy.win_trades / total_trades) * 100 if total_trades > 0 else 0
        avg_profit = strategy.total_profit / strategy.win_trades if strategy.win_trades > 0 else 0
        avg_loss = strategy.total_loss / strategy.lose_trades if strategy.lose_trades > 0 else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        max_drawdown = strategy.max_drawdown * 100
        
        print(f"最终账户余额: {final_value:.2f} USDT")
        print(f"净盈亏: {profit:.2f} USDT ({profit_pct:.2f}%)")
        print(f"总交易次数: {total_trades}, 胜率: {win_rate:.2f}%, 盈亏比: {profit_loss_ratio:.2f}")
        print(f"最大回撤: {max_drawdown:.2f}%")
        print("-" * 50)
        
        # 记录结果
        results.append({
            'params': params,
            'final_value': final_value,
            'profit': profit,
            'profit_pct': profit_pct,
            'total_trades': total_trades,
            'win_trades': strategy.win_trades,
            'lose_trades': strategy.lose_trades,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'max_drawdown': max_drawdown
        })
    
    # 按利润排序结果
    results.sort(key=lambda x: x['profit'], reverse=True)
    
    # 输出最佳结果
    print("\n===== 参数优化结果 =====")
    print(f"共测试了 {len(results)} 组参数")
    print("\n最佳参数组合 (按利润排序):")
    
    for i, result in enumerate(results[:5]):
        params = result['params']
        print(f"\n第 {i+1} 名参数组合:")
        print(f"  影线/实体比率: {params['pinbar_shadow_ratio']}")
        print(f"  实体/总范围比率: {params['pinbar_body_ratio']}")
        print(f"  止损百分比: {params['stop_loss_pct']}")
        print(f"  止盈百分比: {params['take_profit_pct']}")
        print(f"  使用RSI: {params['use_rsi']}")
        print(f"  使用布林带: {params['use_bb_confirmation']}")
        print(f"  使用趋势过滤: {params['use_trend_filter']}")
        print(f"  使用移动止损: {params['use_trailing_stop']}")
        if params['use_trailing_stop']:
            print(f"  移动止损激活阈值: {params['trail_activation_pct']}")
            print(f"  移动止损距离系数: {params['trail_percent']}")
        
        print(f"  净盈亏: {result['profit']:.2f} USDT ({result['profit_pct']:.2f}%)")
        print(f"  总交易次数: {result['total_trades']}")
        print(f"  胜率: {result['win_rate']:.2f}%")
        print(f"  盈亏比: {result['profit_loss_ratio']:.2f}")
        print(f"  最大回撤: {result['max_drawdown']:.2f}%")
    
    # 生成HTML格式的结果表格
    html_results = generate_optimization_html(results)
    
    # 返回最佳参数和HTML结果
    return results[0]['params'] if results else None, html_results

def generate_optimization_html(results):
    """生成参数优化的HTML表格"""
    
    # 创建HTML表格
    html = """
    <div class="optimization-results">
        <h2>参数优化结果</h2>
        <table class="results-table">
            <thead>
                <tr>
                    <th>排名</th>
                    <th>影线/实体比率</th>
                    <th>实体/总范围比率</th>
                    <th>止损%</th>
                    <th>止盈%</th>
                    <th>使用RSI</th>
                    <th>使用布林带</th>
                    <th>使用趋势过滤</th>
                    <th>使用移动止损</th>
                    <th>净盈亏</th>
                    <th>交易次数</th>
                    <th>胜率</th>
                    <th>盈亏比</th>
                    <th>最大回撤</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # 添加每行数据
    for i, result in enumerate(results):
        params = result['params']
        profit_class = "profit" if result['profit'] > 0 else "loss"
        
        html += f"""
                <tr>
                    <td>{i+1}</td>
                    <td>{params['pinbar_shadow_ratio']}</td>
                    <td>{params['pinbar_body_ratio']}</td>
                    <td>{params['stop_loss_pct']:.3f}</td>
                    <td>{params['take_profit_pct']:.3f}</td>
                    <td>{'是' if params['use_rsi'] else '否'}</td>
                    <td>{'是' if params['use_bb_confirmation'] else '否'}</td>
                    <td>{'是' if params['use_trend_filter'] else '否'}</td>
                    <td>{'是' if params['use_trailing_stop'] else '否'}</td>
                    <td class="{profit_class}">{result['profit']:.2f} ({result['profit_pct']:.2f}%)</td>
                    <td>{result['total_trades']}</td>
                    <td>{result['win_rate']:.2f}%</td>
                    <td>{result['profit_loss_ratio']:.2f}</td>
                    <td>{result['max_drawdown']:.2f}%</td>
                </tr>
        """
    
    # 关闭表格
    html += """
            </tbody>
        </table>
    </div>
    <style>
        .optimization-results {
            margin-top: 30px;
            overflow-x: auto;
        }
        .results-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        .results-table th, .results-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }
        .results-table th {
            background-color: #f2f2f2;
            position: sticky;
            top: 0;
        }
        .results-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .results-table tr:hover {
            background-color: #f0f0f0;
        }
        .profit {
            color: #e74c3c;
            font-weight: bold;
        }
        .loss {
            color: #2ecc71;
            font-weight: bold;
        }
    </style>
    """
    
    return html

def generate_html_report_with_optimization(data, strategy_instance, optimization_results=None):
    """
    生成包含参数优化结果的HTML报告
    """
    # 首先生成正常的回测报告
    report_file = generate_html_report(data, strategy_instance)
    
    # 如果没有优化结果，直接返回标准报告
    if optimization_results is None:
        return report_file
    
    # 读取原始HTML文件
    with open(report_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 在Tab导航中添加"参数优化"选项卡
    tab_html = """
                    <button class="tablinks" onclick="openTab(event, 'optimization')">参数优化</button>
    """
    html_content = html_content.replace('<button class="tablinks" onclick="openTab(event, \'trades\')">交易明细</button>', 
                                        '<button class="tablinks" onclick="openTab(event, \'trades\')">交易明细</button>\n' + tab_html)
    
    # 添加参数优化选项卡内容
    optimization_tab = f"""
                <div id="optimization" class="tabcontent">
                    <h2>参数优化结果</h2>
                    {optimization_results}
                </div>
    """
    html_content = html_content.replace('<div id="trades" class="tabcontent">', 
                                        optimization_tab + '\n<div id="trades" class="tabcontent">')
    
    # 写入修改后的HTML文件
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return report_file


# 主程序
if __name__ == '__main__':
    print("====== Pinbar策略回测系统 (改进版) ======")
    print("特点:")
    print("1. 移动止损功能: 当盈利达到一定比例时自动保护利润")
    print("2. 趋势过滤: 使用长周期均线过滤伪信号")
    print("3. 优化的可视化: 清晰的开平仓标记和精简的K线显示")
    print("4. 多种止损方式: 固定比例/Pinbar高低点/ATR动态止损")
    print("5. 参数优化: 自动寻找最佳参数组合")
    
    # 获取前10币种
    print("\n正在获取前10交易量最高的币种...")
    top_symbols = get_top_10_symbols()
    print(f"前10币种: {top_symbols}")
    
    for symbol in top_symbols:
        print(f"\n开始处理币种: {symbol}")
        
        # 获取数据
        print(f"正在获取 {symbol} 的历史数据...")
        data = get_historical_data(symbol=symbol, start_date='2024-01-01', end_date='2025-05-21')
        if len(data) < 50:  # 确保有足够数据
            print(f"警告: {symbol} 数据不足，跳过")
            continue
        data.reset_index(drop=True, inplace=True)
        
        # 拆分训练集和测试集
        train_size = int(len(data) * 0.8)
        train_data = data.iloc[:train_size].copy()
        test_data = data.iloc[train_size:].copy()
        
        # 参数优化（使用训练集）
        print(f"\n开始为 {symbol} 进行参数优化...")
        optimal_params, optimization_html = optimize_parameters(train_data)
        
        if optimal_params:
            print(f"\n使用最优参数为 {symbol} 进行最终回测...")
            
            # 设置Backtrader环境
            cerebro = bt.Cerebro()
            data_feed = CustomDataFeed(dataname=test_data)  # 使用测试集验证
            cerebro.adddata(data_feed)
            
            # 添加策略，使用优化后的参数
            cerebro.addstrategy(EnhancedPinbarFuturesStrategy, **optimal_params)
            
            # 设置初始资金
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
            
            # 生成HTML报告（包含优化结果）
            print(f"\n正在为 {symbol} 生成回测报告...")
            report_file = generate_html_report_with_optimization(test_data, strategy_instance, optimization_html)
            report_file_new = report_file.replace('.html', f'_{symbol}.html')  # 为每个币种生成独立报告
            os.rename(report_file, report_file_new)  # 重命名文件
            print(f"报告已保存到: {report_file_new}")
            print(f"正在打开浏览器显示 {symbol} 的报告...")
            webbrowser.open('file://' + report_file_new, new=2)
        else:
            print(f"参数优化失败，未找到 {symbol} 的有效参数组合")

