#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
用于管理策略参数、用户输入和配置文件
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import inquirer

@dataclass
class TradingParams:
    """交易参数配置类"""
    # 风险管理参数
    leverage: int = 5
    risk_per_trade: float = 0.005
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_positions: int = 3
    
    # Pinbar识别参数
    pinbar_shadow_ratio: float = 2.0
    pinbar_body_ratio: float = 0.3
    min_candle_size: float = 0.001
    
    # 趋势过滤参数
    sma_fast: int = 20
    sma_slow: int = 50
    sma_trend: int = 100
    trend_strength: float = 0.01
    
    # 市场状态过滤
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    volatility_lookback: int = 20
    min_volatility: float = 0.01
    max_volatility: float = 0.06
    
    # 时间过滤
    avoid_weekend: bool = True
    trading_hours_start: int = 8
    trading_hours_end: int = 22
    
    # 移动止损
    use_trailing_stop: bool = True
    trail_activation_pct: float = 0.015
    trail_percent: float = 0.6

@dataclass
class BacktestParams:
    """回测参数配置类"""
    symbol: str = 'BTCUSDT'
    interval: str = '1h'
    start_date: str = '2024-01-01'
    end_date: str = '2025-05-21'
    initial_cash: float = 20000.0
    commission: float = 0.00075

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = 'strategy_config.json'):
        self.config_file = config_file
        self.trading_params = TradingParams()
        self.backtest_params = BacktestParams()
        
        # 新增配置项
        self.signal_config = {}
        self.optimization_config = {}
        self.report_config = {}
     # 在config.py的ConfigManager类中添加

    def load_multiple_configs_for_comparison(self, config_names: List[str] = None) -> List[Dict[str, Any]]:
        """加载多个配置用于对比"""
        from multi_config_manager import MultiConfigManager
        
        multi_manager = MultiConfigManager()
        
        if config_names is None:
            config_names = multi_manager.interactive_config_selection()
        
        if not config_names:
            return []
        
        loaded_configs = []
        for config_name in config_names:
            config_data = multi_manager.load_config(config_name)
            if config_data:
                config_data['_config_name'] = config_name
                config_data['_strategy_name'] = multi_manager.available_configs[config_name]['strategy_name']
                loaded_configs.append(config_data)
        
        return loaded_configs

    def apply_config_data(self, config_data: Dict[str, Any]):
        """应用配置数据到当前管理器"""
        # 应用交易参数
        if 'trading_params' in config_data:
            for key, value in config_data['trading_params'].items():
                if hasattr(self.trading_params, key):
                    setattr(self.trading_params, key, value)
        
        # 应用回测参数
        if 'backtest_params' in config_data:
            for key, value in config_data['backtest_params'].items():
                if hasattr(self.backtest_params, key):
                    setattr(self.backtest_params, key, value)
        
        # 应用信号配置
        if 'signal_config' in config_data:
            self.signal_config = config_data['signal_config']

    def get_available_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有可用配置"""
        from multi_config_manager import MultiConfigManager
        multi_manager = MultiConfigManager()
        return multi_manager.list_available_configs()  
        
    def load_config(self, config_file: str = None) -> None:
        """从文件加载配置"""
        if config_file:
            self.config_file = config_file
        
        # 尝试加载多个可能的配置文件
        config_files_to_try = [
            self.config_file,
            'strategy_config.json',
            'example_config.json'
        ]
        
        config_loaded = False
        for config_path in config_files_to_try:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    
                    # 加载交易参数
                    if 'trading_params' in config_data:
                        for key, value in config_data['trading_params'].items():
                            if hasattr(self.trading_params, key):
                                setattr(self.trading_params, key, value)
                    
                    # 加载回测参数
                    if 'backtest_params' in config_data:
                        for key, value in config_data['backtest_params'].items():
                            if hasattr(self.backtest_params, key):
                                setattr(self.backtest_params, key, value)
                    
                    # 加载信号配置
                    if 'signal_config' in config_data:
                        self.signal_config = config_data['signal_config']
                    
                    # 加载优化配置
                    if 'optimization_config' in config_data:
                        self.optimization_config = config_data['optimization_config']
                    
                    # 加载报告配置
                    if 'report_config' in config_data:
                        self.report_config = config_data['report_config']
                                
                    print(f"✅ 配置已从 {config_path} 加载")
                    config_loaded = True
                    break
                except Exception as e:
                    print(f"❌ 加载配置文件 {config_path} 失败: {e}")
                    continue
        
        if not config_loaded:
            print(f"📄 未找到配置文件，将使用默认配置")
            print("💡 提示: 您可以将 example_config.json 重命名为 strategy_config.json 来使用示例配置")
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            config_data = {
                'trading_params': asdict(self.trading_params),
                'backtest_params': asdict(self.backtest_params)
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            print(f"✅ 配置已保存到 {self.config_file}")
        except Exception as e:
            print(f"❌ 保存配置文件失败: {e}")
    
    def interactive_config(self) -> None:
        """交互式配置参数"""
        print("\n=== 策略参数配置 ===")
        
        # 选择配置模式
        config_mode = inquirer.list_input(
            "请选择配置模式",
            choices=[
                ('快速配置 (推荐)', 'quick'),
                ('详细配置', 'detailed'),
                ('从文件加载', 'load'),
                ('使用默认配置', 'default')
            ]
        )
        
        if config_mode == 'load':
            self.load_config()
            return
        elif config_mode == 'default':
            print("✅ 使用默认配置")
            return
        elif config_mode == 'quick':
            self._quick_config()
        else:
            self._detailed_config()
    
    def _quick_config(self) -> None:
        """快速配置模式"""
        print("\n--- 快速配置模式 ---")
        
        # 选择策略风格
        strategy_style = inquirer.list_input(
            "选择策略风格",
            choices=[
                ('极度保守 (推荐新手)', 'conservative'),
                ('稳健均衡', 'moderate'),
                ('相对激进', 'aggressive')
            ]
        )
        
        # 根据风格设置预设参数
        if strategy_style == 'conservative':
            self.trading_params.leverage = 2
            self.trading_params.risk_per_trade = 0.002
            self.trading_params.stop_loss_pct = 0.05
            self.trading_params.take_profit_pct = 0.1
        elif strategy_style == 'moderate':
            self.trading_params.leverage = 5
            self.trading_params.risk_per_trade = 0.005
            self.trading_params.stop_loss_pct = 0.02
            self.trading_params.take_profit_pct = 0.04
        else:  # aggressive
            self.trading_params.leverage = 10
            self.trading_params.risk_per_trade = 0.01
            self.trading_params.stop_loss_pct = 0.015
            self.trading_params.take_profit_pct = 0.03
        
        # 选择交易周期
        self.backtest_params.interval = inquirer.list_input(
            "选择交易周期",
            choices=['15m', '1h', '4h', '1d']
        )
        
        # 选择交易对
        self.backtest_params.symbol = inquirer.text(
            "输入交易对 (如 BTCUSDT)",
            default='BTCUSDT'
        )
        
        print(f"✅ 快速配置完成 - {strategy_style} 风格")
    
    def _detailed_config(self) -> None:
        """详细配置模式"""
        print("\n--- 详细配置模式 ---")
        
        # 风险管理参数
        self.trading_params.leverage = inquirer.text(
            "杠杆倍数 (1-20)",
            default=str(self.trading_params.leverage),
            validate=lambda _, x: 1 <= int(x) <= 20
        )
        self.trading_params.leverage = int(self.trading_params.leverage)
        
        self.trading_params.risk_per_trade = float(inquirer.text(
            "单笔风险比例 (0.001-0.02)",
            default=str(self.trading_params.risk_per_trade),
            validate=lambda _, x: 0.001 <= float(x) <= 0.02
        ))
        
        self.trading_params.stop_loss_pct = float(inquirer.text(
            "止损比例 (0.005-0.1)",
            default=str(self.trading_params.stop_loss_pct),
            validate=lambda _, x: 0.005 <= float(x) <= 0.1
        ))
        
        # Pinbar参数
        self.trading_params.pinbar_shadow_ratio = float(inquirer.text(
            "Pinbar影线比例 (1.0-5.0)",
            default=str(self.trading_params.pinbar_shadow_ratio),
            validate=lambda _, x: 1.0 <= float(x) <= 5.0
        ))
        
        # 其他参数...
        print("✅ 详细配置完成")
    
    def get_preset_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取预设配置"""
        return {
            'conservative': {
                'name': '极度保守',
                'trading_params': {
                    'leverage': 2,
                    'risk_per_trade': 0.002,
                    'stop_loss_pct': 0.05,
                    'take_profit_pct': 0.1,
                    'max_positions': 1
                },
                'description': '最低风险，适合新手验证策略'
            },
            'moderate': {
                'name': '稳健均衡',
                'trading_params': {
                    'leverage': 5,
                    'risk_per_trade': 0.005,
                    'stop_loss_pct': 0.02,
                    'take_profit_pct': 0.04,
                    'max_positions': 3
                },
                'description': '中等风险，平衡收益和安全'
            },
            'aggressive': {
                'name': '相对激进',
                'trading_params': {
                    'leverage': 10,
                    'risk_per_trade': 0.01,
                    'stop_loss_pct': 0.015,
                    'take_profit_pct': 0.03,
                    'max_positions': 5
                },
                'description': '较高风险，追求更高收益'
            }
        }
    
    def apply_preset(self, preset_name: str) -> None:
        """应用预设配置"""
        presets = self.get_preset_configs()
        if preset_name in presets:
            preset = presets[preset_name]
            for key, value in preset['trading_params'].items():
                if hasattr(self.trading_params, key):
                    setattr(self.trading_params, key, value)
            print(f"✅ 已应用 {preset['name']} 预设配置")
        else:
            print(f"❌ 未找到预设配置: {preset_name}")
    
    def print_current_config(self) -> None:
        """打印当前配置"""
        print("\n=== 当前策略配置 ===")
        
        print("📊 交易参数:")
        print(f"  杠杆倍数: {self.trading_params.leverage}")
        print(f"  单笔风险: {self.trading_params.risk_per_trade * 100:.2f}%")
        print(f"  止损比例: {self.trading_params.stop_loss_pct * 100:.2f}%")
        print(f"  止盈比例: {self.trading_params.take_profit_pct * 100:.2f}%")
        print(f"  最大持仓: {self.trading_params.max_positions}")
        
        print("\n📈 Pinbar参数:")
        print(f"  影线比例: {self.trading_params.pinbar_shadow_ratio}")
        print(f"  实体比例: {self.trading_params.pinbar_body_ratio}")
        
        print("\n📅 回测参数:")
        print(f"  交易对: {self.backtest_params.symbol}")
        print(f"  时间周期: {self.backtest_params.interval}")
        print(f"  回测期间: {self.backtest_params.start_date} ~ {self.backtest_params.end_date}")
        print(f"  初始资金: {self.backtest_params.initial_cash:,.2f} USDT")
    
    def validate_config(self) -> bool:
        """验证配置的合理性"""
        errors = []
        
        # 验证风险参数
        if self.trading_params.leverage > 20:
            errors.append("杠杆倍数过高，建议不超过20倍")
        
        if self.trading_params.risk_per_trade > 0.02:
            errors.append("单笔风险过高，建议不超过2%")
        
        if self.trading_params.stop_loss_pct < 0.005:
            errors.append("止损过紧，建议不小于0.5%")
        
        # 验证逻辑关系
        if self.trading_params.take_profit_pct <= self.trading_params.stop_loss_pct:
            errors.append("止盈应该大于止损")
        
        if errors:
            print("\n⚠️  配置验证发现问题:")
            for error in errors:
                print(f"  - {error}")
            return False
        else:
            print("✅ 配置验证通过")
            return True

# 全局配置实例
config_manager = ConfigManager()

def get_config() -> ConfigManager:
    """获取全局配置管理器"""
    return config_manager

if __name__ == "__main__":
    # 测试配置管理器
    cm = ConfigManager()
    cm.interactive_config()
    cm.print_current_config()
    cm.validate_config()
    cm.save_config()