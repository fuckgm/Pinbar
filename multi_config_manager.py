#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多配置管理器 - 支持加载和对比多个配置文件
添加到config.py或作为独立模块使用
"""

import json
import os
import glob
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import inquirer

@dataclass
class ConfigResult:
    """配置回测结果"""
    config_name: str
    config_path: str
    strategy_name: str
    description: str
    risk_level: str
    backtest_result: Dict[str, Any]
    performance_score: float

class MultiConfigManager:
    """多配置文件管理器"""
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = config_dir
        self.available_configs = {}
        self.loaded_configs = {}
        self.comparison_results = []
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 扫描可用配置
        self.scan_available_configs()
    
    def scan_available_configs(self):
        """扫描可用的配置文件"""
        # 扫描配置目录中的JSON文件
        config_files = glob.glob(os.path.join(self.config_dir, "*.json"))
        
        # 也扫描根目录的配置文件
        root_configs = glob.glob("*_config.json")
        config_files.extend(root_configs)
        
        # 添加默认配置
        if os.path.exists("strategy_config.json"):
            config_files.append("strategy_config.json")
        
        self.available_configs = {}
        
        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 提取配置信息
                config_name = os.path.basename(config_file).replace('.json', '')
                strategy_name = config_data.get('strategy_name', config_name)
                description = config_data.get('description', '无描述')
                risk_level = config_data.get('risk_level', '未知')
                
                self.available_configs[config_name] = {
                    'path': config_file,
                    'strategy_name': strategy_name,
                    'description': description,
                    'risk_level': risk_level,
                    'config_data': config_data
                }
                
                print(f"✅ 发现配置: {strategy_name}")
                
            except Exception as e:
                print(f"❌ 加载配置失败 {config_file}: {e}")
        
        print(f"📋 总共发现 {len(self.available_configs)} 个配置文件")
    
    def list_available_configs(self) -> Dict[str, Dict[str, Any]]:
        """列出所有可用配置"""
        return self.available_configs
    
    def load_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """加载指定配置"""
        if config_name in self.available_configs:
            config_info = self.available_configs[config_name]
            self.loaded_configs[config_name] = config_info['config_data']
            return config_info['config_data']
        else:
            print(f"❌ 配置不存在: {config_name}")
            return None
    
    def interactive_config_selection(self) -> List[str]:
        """交互式选择配置进行对比"""
        if not self.available_configs:
            print("❌ 没有发现可用的配置文件")
            return []
        
        print("\n🎯 可用的策略配置:")
        print("=" * 60)
        
        # 显示配置选项
        config_choices = []
        for config_name, config_info in self.available_configs.items():
            strategy_name = config_info['strategy_name']
            description = config_info['description']
            risk_level = config_info['risk_level']
            
            choice_text = f"{strategy_name} ({risk_level}风险) - {description}"
            config_choices.append((choice_text, config_name))
        
        # 添加特殊选项
        config_choices.extend([
            ("🔄 全部配置对比测试", "all"),
            ("📊 推荐配置组合", "recommended"),
            ("🎯 高收益配置", "high_yield"),
            ("🛡️ 低风险配置", "low_risk")
        ])
        
        try:
            selected = inquirer.checkbox(
                "选择要对比的配置 (多选)",
                choices=config_choices
            )
            
            # 处理特殊选项
            if "all" in selected:
                return list(self.available_configs.keys())
            elif "recommended" in selected:
                return self.get_recommended_configs()
            elif "high_yield" in selected:
                return self.get_high_yield_configs()
            elif "low_risk" in selected:
                return self.get_low_risk_configs()
            else:
                return selected
                
        except KeyboardInterrupt:
            print("\n操作取消")
            return []
    
    def get_recommended_configs(self) -> List[str]:
        """获取推荐配置组合"""
        recommended = []
        for config_name, config_info in self.available_configs.items():
            strategy_name = config_info['strategy_name']
            if any(keyword in strategy_name.lower() for keyword in 
                   ['激进短线', '趋势跟踪', '改进保守']):
                recommended.append(config_name)
        
        return recommended[:3]  # 限制为3个
    
    def get_high_yield_configs(self) -> List[str]:
        """获取高收益配置"""
        high_yield = []
        for config_name, config_info in self.available_configs.items():
            strategy_name = config_info['strategy_name']
            if any(keyword in strategy_name.lower() for keyword in 
                   ['激进', '突破', '动量']):
                high_yield.append(config_name)
        
        return high_yield
    
    def get_low_risk_configs(self) -> List[str]:
        """获取低风险配置"""
        low_risk = []
        for config_name, config_info in self.available_configs.items():
            risk_level = config_info['risk_level']
            if risk_level in ['低', '中']:
                low_risk.append(config_name)
        
        return low_risk
    
    def calculate_performance_score(self, result: Dict[str, Any]) -> float:
        """计算性能综合得分"""
        try:
            total_return = result.get('total_return', 0)
            win_rate = result.get('win_rate', 0)
            max_drawdown = result.get('max_drawdown', 100)
            profit_factor = result.get('profit_factor', 0)
            sharpe_ratio = result.get('sharpe_ratio', 0)
            total_trades = result.get('total_trades', 0)
            
            # 权重设置
            weights = {
                'return': 0.3,
                'win_rate': 0.2,
                'drawdown': 0.2,
                'profit_factor': 0.15,
                'sharpe': 0.1,
                'trades': 0.05
            }
            
            # 标准化指标 (0-100分)
            return_score = min(100, max(0, total_return * 2))  # 50%收益=100分
            win_rate_score = min(100, win_rate * 1.5)  # 67%胜率=100分
            drawdown_score = max(0, 100 - max_drawdown * 4)  # 25%回撤=0分
            pf_score = min(100, profit_factor * 30)  # 3.33盈亏比=100分
            sharpe_score = min(100, max(0, sharpe_ratio * 40))  # 2.5夏普=100分
            trades_score = min(100, total_trades * 2)  # 50笔交易=100分
            
            # 计算加权得分
            final_score = (
                return_score * weights['return'] +
                win_rate_score * weights['win_rate'] +
                drawdown_score * weights['drawdown'] +
                pf_score * weights['profit_factor'] +
                sharpe_score * weights['sharpe'] +
                trades_score * weights['trades']
            )
            
            return round(final_score, 2)
            
        except Exception as e:
            print(f"计算得分失败: {e}")
            return 0.0
    
    def add_comparison_result(self, config_name: str, backtest_result: Dict[str, Any]):
        """添加对比结果"""
        if config_name not in self.available_configs:
            print(f"警告: 配置 {config_name} 不存在")
            return
        
        config_info = self.available_configs[config_name]
        performance_score = self.calculate_performance_score(backtest_result)
        
        result = ConfigResult(
            config_name=config_name,
            config_path=config_info['path'],
            strategy_name=config_info['strategy_name'],
            description=config_info['description'],
            risk_level=config_info['risk_level'],
            backtest_result=backtest_result,
            performance_score=performance_score
        )
        
        self.comparison_results.append(result)
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """获取对比汇总"""
        if not self.comparison_results:
            return {}
        
        # 按得分排序
        sorted_results = sorted(self.comparison_results, 
                              key=lambda x: x.performance_score, reverse=True)
        
        # 找出各项最佳
        best_return = max(self.comparison_results, 
                         key=lambda x: x.backtest_result.get('total_return', 0))
        best_winrate = max(self.comparison_results, 
                          key=lambda x: x.backtest_result.get('win_rate', 0))
        best_risk = min(self.comparison_results, 
                       key=lambda x: x.backtest_result.get('max_drawdown', 100))
        best_sharpe = max(self.comparison_results, 
                         key=lambda x: x.backtest_result.get('sharpe_ratio', 0))
        
        return {
            'total_configs': len(self.comparison_results),
            'best_overall': sorted_results[0],
            'worst_overall': sorted_results[-1],
            'best_return': best_return,
            'best_winrate': best_winrate,
            'best_risk': best_risk,
            'best_sharpe': best_sharpe,
            'all_results': sorted_results,
            'average_return': sum(r.backtest_result.get('total_return', 0) 
                                for r in self.comparison_results) / len(self.comparison_results),
            'average_score': sum(r.performance_score for r in self.comparison_results) / len(self.comparison_results)
        }
    
    def print_comparison_summary(self):
        """打印对比汇总"""
        summary = self.get_comparison_summary()
        
        if not summary:
            print("❌ 没有对比结果")
            return
        
        print("\n" + "=" * 80)
        print("📊 多配置对比测试结果汇总")
        print("=" * 80)
        
        print(f"🔢 测试配置数量: {summary['total_configs']}")
        print(f"📈 平均收益率: {summary['average_return']:.2f}%")
        print(f"🏆 平均综合得分: {summary['average_score']:.1f}/100")
        
        print(f"\n🥇 最佳综合表现:")
        best = summary['best_overall']
        result = best.backtest_result
        print(f"   策略: {best.strategy_name}")
        print(f"   收益率: {result.get('total_return', 0):.2f}%")
        print(f"   胜率: {result.get('win_rate', 0):.1f}%")
        print(f"   最大回撤: {result.get('max_drawdown', 0):.2f}%")
        print(f"   综合得分: {best.performance_score:.1f}/100")
        
        print(f"\n🎯 各项最佳表现:")
        print(f"   💰 最高收益: {summary['best_return'].strategy_name} "
              f"({summary['best_return'].backtest_result.get('total_return', 0):.2f}%)")
        print(f"   🎯 最高胜率: {summary['best_winrate'].strategy_name} "
              f"({summary['best_winrate'].backtest_result.get('win_rate', 0):.1f}%)")
        print(f"   🛡️  最低回撤: {summary['best_risk'].strategy_name} "
              f"({summary['best_risk'].backtest_result.get('max_drawdown', 0):.2f}%)")
        print(f"   📊 最高夏普: {summary['best_sharpe'].strategy_name} "
              f"({summary['best_sharpe'].backtest_result.get('sharpe_ratio', 0):.3f})")
        
        print(f"\n📋 详细排名:")
        for i, result in enumerate(summary['all_results'], 1):
            backtest = result.backtest_result
            print(f"   {i:2d}. {result.strategy_name:<20} "
                  f"收益:{backtest.get('total_return', 0):6.2f}% "
                  f"胜率:{backtest.get('win_rate', 0):5.1f}% "
                  f"回撤:{backtest.get('max_drawdown', 0):5.2f}% "
                  f"得分:{result.performance_score:5.1f}")
    
    def export_comparison_results(self, filename: str = None):
        """导出对比结果"""
        if not self.comparison_results:
            print("❌ 没有对比结果可导出")
            return
        
        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"config_comparison_{timestamp}.json"
        
        # 准备导出数据
        export_data = {
            'comparison_time': str(datetime.now()),
            'total_configs': len(self.comparison_results),
            'summary': self.get_comparison_summary(),
            'detailed_results': []
        }
        
        for result in self.comparison_results:
            export_data['detailed_results'].append({
                'config_name': result.config_name,
                'config_path': result.config_path,
                'strategy_name': result.strategy_name,
                'description': result.description,
                'risk_level': result.risk_level,
                'performance_score': result.performance_score,
                'backtest_result': result.backtest_result
            })
        
        # 保存文件
        os.makedirs('comparison_results', exist_ok=True)
        filepath = os.path.join('comparison_results', filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ 对比结果已导出到: {filepath}")
        return filepath

# 在config.py中添加的方法
def enhanced_config_manager_methods():
    """在ConfigManager类中添加的方法"""
    
    def load_multiple_configs_for_comparison(self, config_names: List[str] = None) -> List[Dict[str, Any]]:
        """加载多个配置用于对比"""
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
    
    def run_multi_config_comparison(self, data_manager, strategy_runner):
        """运行多配置对比测试"""
        multi_manager = MultiConfigManager()
        
        # 选择配置
        config_names = multi_manager.interactive_config_selection()
        if not config_names:
            return None
        
        print(f"\n🚀 开始对比测试 {len(config_names)} 个配置...")
        
        # 逐个运行回测
        for i, config_name in enumerate(config_names, 1):
            print(f"\n📊 测试配置 {i}/{len(config_names)}: {config_name}")
            
            # 加载配置
            config_data = multi_manager.load_config(config_name)
            if not config_data:
                continue
            
            try:
                # 应用配置到当前管理器
                self.apply_config_data(config_data)
                
                # 获取数据
                symbol = self.backtest_params.symbol
                data = data_manager.get_historical_data(
                    symbol=symbol,
                    interval=self.backtest_params.interval,
                    start_date=self.backtest_params.start_date,
                    end_date=self.backtest_params.end_date
                )
                
                if data is None:
                    print(f"❌ {config_name} 数据获取失败")
                    continue
                
                # 运行策略
                result = strategy_runner(data, self.trading_params, self.backtest_params)
                
                # 添加结果
                multi_manager.add_comparison_result(config_name, result)
                
                print(f"✅ {config_name} 测试完成 - 收益率: {result.get('total_return', 0):.2f}%")
                
            except Exception as e:
                print(f"❌ {config_name} 测试失败: {e}")
                continue
        
        # 显示汇总结果
        multi_manager.print_comparison_summary()
        
        # 导出结果
        if inquirer.confirm("是否导出对比结果?", default=True):
            multi_manager.export_comparison_results()
        
        return multi_manager
    
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

# 使用示例
if __name__ == "__main__":
    # 测试多配置管理器
    manager = MultiConfigManager()
    
    # 列出可用配置
    configs = manager.list_available_configs()
    print(f"发现 {len(configs)} 个配置")
    
    # 交互式选择
    selected = manager.interactive_config_selection()
    print(f"选择了: {selected}")
    
    # 模拟添加结果
    for config_name in selected[:2]:
        # 模拟回测结果
        mock_result = {
            'total_return': 5.5,
            'win_rate': 65.0,
            'max_drawdown': 12.0,
            'profit_factor': 1.8,
            'sharpe_ratio': 1.2,
            'total_trades': 25
        }
        manager.add_comparison_result(config_name, mock_result)
    
    # 显示汇总
    manager.print_comparison_summary()

