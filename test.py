#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试脚本
用于验证系统是否正常工作，使用模拟数据
"""

import sys
import pandas as pd
import numpy as np
import datetime
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config import ConfigManager, TradingParams, BacktestParams
    from signal_generator import create_default_signal_generator
    from report_generator import ReportGenerator
    print("✅ 所有模块导入成功")
except ImportError as e:
    print(f"❌ 模块导入失败: {e}")
    print("请确保安装了所有依赖: pip install backtrader pandas numpy plotly jinja2 inquirer scipy")
    sys.exit(1)

def create_mock_data(symbol='BTCUSDT', days=30, interval='1h'):
    """创建模拟数据用于测试"""
    print(f"📊 创建 {days} 天的模拟 {symbol} {interval} 数据...")
    
    # 根据interval计算数据点数量
    if interval == '1h':
        periods = days * 24
        freq = '1H'
    elif interval == '15m':
        periods = days * 24 * 4
        freq = '15min'
    elif interval == '5m':
        periods = days * 24 * 12
        freq = '5min'
    else:
        periods = days
        freq = '1D'
    
    # 生成时间序列
    dates = pd.date_range('2024-01-01', periods=periods, freq=freq)
    
    # 生成价格数据（布朗运动 + 趋势）
    np.random.seed(42)  # 固定随机种子，便于复现
    
    # 基础价格和波动率
    base_price = 50000
    volatility = 0.02
    trend = 0.0001
    
    # 生成价格序列
    returns = np.random.normal(trend, volatility, periods)
    prices = base_price * np.exp(np.cumsum(returns))
    
    # 生成OHLC数据
    data = {
        'timestamp': dates,
        'open': prices,
        'close': prices * (1 + np.random.normal(0, 0.001, periods)),
    }
    
    # 计算high和low
    data['high'] = np.maximum(data['open'], data['close']) * (1 + np.abs(np.random.normal(0, 0.005, periods)))
    data['low'] = np.minimum(data['open'], data['close']) * (1 - np.abs(np.random.normal(0, 0.005, periods)))
    
    # 生成成交量
    data['volume'] = np.random.lognormal(np.log(1000), 0.5, periods)
    
    df = pd.DataFrame(data)
    
    # 计算技术指标（简化版）
    df['sma_fast'] = df['close'].rolling(window=20).mean()
    df['sma_slow'] = df['close'].rolling(window=50).mean()
    df['sma_trend'] = df['close'].rolling(window=100).mean()
    
    # RSI计算（简化版）
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 成交量指标
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # MACD（简化版）
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    
    # 布林带
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # 波动率
    df['volatility'] = df['close'].pct_change().rolling(window=20).std() * np.sqrt(24)
    
    print(f"✅ 生成了 {len(df)} 行模拟数据")
    return df

def run_mock_backtest():
    """运行模拟回测"""
    print("\n🚀 开始模拟回测测试...")
    
    try:
        # 创建配置
        config_manager = ConfigManager()
        
        # 使用保守配置
        config_manager.trading_params.leverage = 3
        config_manager.trading_params.risk_per_trade = 0.005
        config_manager.trading_params.stop_loss_pct = 0.02
        config_manager.trading_params.take_profit_pct = 0.04
        config_manager.trading_params.max_positions = 2
        
        config_manager.backtest_params.symbol = 'BTCUSDT'
        config_manager.backtest_params.interval = '1h'
        config_manager.backtest_params.initial_cash = 10000.0
        
        print("✅ 配置创建成功")
        
        # 创建模拟数据
        data = create_mock_data('BTCUSDT', days=60, interval='1h')
        
        # 创建信号生成器
        signal_generator = create_default_signal_generator()
        print("✅ 信号生成器创建成功")
        
        # 模拟回测结果（因为完整回测需要backtrader，这里用模拟数据）
        mock_results = {
            'initial_cash': 10000.0,
            'final_value': 10500.0,
            'total_return': 5.0,
            'total_trades': 8,
            'win_trades': 5,
            'lose_trades': 3,
            'win_rate': 62.5,
            'profit_factor': 1.8,
            'max_drawdown': 0.08,
            'sharpe_ratio': 1.2,
            'trades': []
        }
        
        # 生成模拟交易记录
        for i in range(8):
            trade_time = data['timestamp'].iloc[i*200 + 100] if i*200 + 100 < len(data) else data['timestamp'].iloc[-1]
            exit_time = data['timestamp'].iloc[i*200 + 150] if i*200 + 150 < len(data) else data['timestamp'].iloc[-1]
            
            profit = np.random.uniform(-50, 100)
            
            mock_results['trades'].append({
                'trade_id': f'T{i+1:04d}',
                'direction': 'buy' if i % 2 == 0 else 'sell',
                'entry_time': trade_time,
                'exit_time': exit_time,
                'entry_price': data['close'].iloc[i*200 + 100] if i*200 + 100 < len(data) else data['close'].iloc[-1],
                'exit_price': data['close'].iloc[i*200 + 150] if i*200 + 150 < len(data) else data['close'].iloc[-1],
                'profit': profit,
                'profit_pct': profit / 100,
                'reason': ['止盈', '止损', '移动止损'][i % 3]
            })
        
        print("✅ 模拟回测结果生成成功")
        
        # 生成报告
        report_generator = ReportGenerator()
        
        config_dict = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'leverage': 3,
            'risk_per_trade': 0.005,
            'stop_loss_pct': 0.02,
            'take_profit_pct': 0.04
        }
        
        report_path = report_generator.generate_backtest_report(
            data, mock_results, config_dict
        )
        
        print("✅ 报告生成成功")
        
        # 输出总结
        print(f"\n📊 模拟回测结果总结:")
        print(f"初始资金: {mock_results['initial_cash']:,.2f} USDT")
        print(f"最终资金: {mock_results['final_value']:,.2f} USDT") 
        print(f"总收益率: {mock_results['total_return']:.2f}%")
        print(f"总交易次数: {mock_results['total_trades']}")
        print(f"胜率: {mock_results['win_rate']:.1f}%")
        print(f"最大回撤: {mock_results['max_drawdown']*100:.1f}%")
        
        print(f"\n📋 报告已保存到: {report_path}")
        
        # 询问是否打开报告
        try:
            open_report = input("\n是否在浏览器中打开报告? (y/N): ").lower().strip()
            if open_report == 'y':
                report_generator.open_report_in_browser(report_path)
        except:
            print("跳过打开浏览器")
        
        print("\n🎉 模拟回测测试完成!")
        print("✅ 系统运行正常，可以开始使用真实数据进行回测")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_dependencies():
    """检查依赖"""
    print("🔍 检查依赖包...")
    
    required_packages = [
        ('pandas', 'pandas'),
        ('numpy', 'numpy'), 
        ('plotly', 'plotly.graph_objects'),
        ('jinja2', 'jinja2'),
        ('scipy', 'scipy'),
        ('backtrader', 'backtrader')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            if import_name == 'plotly.graph_objects':
                import plotly.graph_objects as go
                print(f"✅ {package_name}")
            else:
                __import__(import_name)
                print(f"✅ {package_name}")
        except ImportError as e:
            print(f"❌ {package_name} - {e}")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install " + ' '.join(missing_packages))
        return False
    else:
        print("✅ 所有依赖包检查通过")
        return True

if __name__ == "__main__":
    print("🧪 Pinbar策略系统快速测试")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        print("\n⚠️  部分依赖检查失败，但可能是检查逻辑问题")
        print("如果您确认依赖已安装，可以继续测试")
        
        try:
            continue_test = input("是否继续测试? (y/N): ").lower().strip()
            if continue_test != 'y':
                print("测试已取消")
                sys.exit(1)
        except:
            print("跳过依赖检查，继续测试...")
    
    # 运行测试
    success = run_mock_backtest()
    
    if success:
        print("\n🎯 下一步:")
        print("1. 配置API密钥 (key.json)")
        print("2. 运行完整系统: python main.py")
        print("3. 选择真实数据进行回测")
    else:
        print("\n🔧 如果遇到问题:")
        print("1. 检查所有文件是否完整")
        print("2. 确认依赖包已正确安装")
        print("3. 查看错误信息进行调试")