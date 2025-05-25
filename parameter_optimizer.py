#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参数优化器
自动寻找最优参数组合
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from itertools import product
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self, config_file: str = 'enhanced_config.json'):
        self.config_file = config_file
        self.load_config()
        self.optimization_results = []
    
    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"❌ 配置文件 {self.config_file} 不存在，使用默认配置")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "pinbar_strategy": {
                "min_shadow_body_ratio": 1.8,
                "max_body_ratio": 0.4,
                "min_candle_size": 0.002,
                "trend_period": 20,
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "bb_period": 20,
                "volume_threshold": 1.2,
                "sr_lookback": 50,
                "level_proximity": 0.001,
                "min_signal_score": 4
            },
            "参数优化范围": {
                "min_shadow_body_ratio": {"min": 1.5, "max": 3.0, "step": 0.2},
                "max_body_ratio": {"min": 0.2, "max": 0.5, "step": 0.05},
                "rsi_oversold": {"min": 20, "max": 35, "step": 5},
                "rsi_overbought": {"min": 65, "max": 80, "step": 5},
                "min_signal_score": {"min": 3, "max": 5, "step": 1},
                "volume_threshold": {"min": 1.0, "max": 2.0, "step": 0.2}
            }
        }
    
    def generate_parameter_combinations(self, optimization_type: str = 'grid') -> List[Dict[str, Any]]:
        """生成参数组合"""
        if optimization_type == 'grid':
            return self._generate_grid_combinations()
        elif optimization_type == 'random':
            return self._generate_random_combinations()
        elif optimization_type == 'preset':
            return self._generate_preset_combinations()
        else:
            raise ValueError(f"不支持的优化类型: {optimization_type}")
    
    def _generate_grid_combinations(self) -> List[Dict[str, Any]]:
        """生成网格搜索参数组合"""
        optimization_ranges = self.config.get("参数优化范围", {})
        base_config = self.config.get("pinbar_strategy", {})
        
        # 生成参数范围
        param_ranges = {}
        for param_name, param_config in optimization_ranges.items():
            min_val = param_config.get('min', base_config.get(param_name, 1))
            max_val = param_config.get('max', base_config.get(param_name, 2))
            step = param_config.get('step', 0.1)
            
            if isinstance(min_val, int) and isinstance(max_val, int):
                param_ranges[param_name] = list(range(int(min_val), int(max_val) + 1, int(step)))
            else:
                values = []
                current = min_val
                while current <= max_val:
                    values.append(round(current, 3))
                    current += step
                param_ranges[param_name] = values
        
        # 限制组合数量（避免过多组合）
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        if total_combinations > 1000:
            print(f"⚠️  参数组合数量过多 ({total_combinations})，将进行随机采样")
            return self._generate_random_combinations(sample_size=500)
        
        # 生成所有组合
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        
        combinations = []
        for values in product(*param_values):
            config = base_config.copy()
            for i, param_name in enumerate(param_names):
                config[param_name] = values[i]
            combinations.append(config)
        
        print(f"✅ 生成了 {len(combinations)} 个参数组合")
        return combinations
    
    def _generate_random_combinations(self, sample_size: int = 200) -> List[Dict[str, Any]]:
        """生成随机参数组合"""
        optimization_ranges = self.config.get("参数优化范围", {})
        base_config = self.config.get("pinbar_strategy", {})
        
        combinations = []
        for _ in range(sample_size):
            config = base_config.copy()
            
            for param_name, param_config in optimization_ranges.items():
                min_val = param_config.get('min', base_config.get(param_name, 1))
                max_val = param_config.get('max', base_config.get(param_name, 2))
                
                if isinstance(min_val, int) and isinstance(max_val, int):
                    config[param_name] = np.random.randint(min_val, max_val + 1)
                else:
                    config[param_name] = round(np.random.uniform(min_val, max_val), 3)
            
            combinations.append(config)
        
        print(f"✅ 生成了 {len(combinations)} 个随机参数组合")
        return combinations
    
    def _generate_preset_combinations(self) -> List[Dict[str, Any]]:
        """生成预设参数组合"""
        preset_configs = self.config.get("预设配置", {})
        base_config = self.config.get("pinbar_strategy", {})
        
        combinations = []
        for preset_name, preset_params in preset_configs.items():
            config = base_config.copy()
            config.update(preset_params)
            config['preset_name'] = preset_name
            combinations.append(config)
        
        print(f"✅ 生成了 {len(combinations)} 个预设参数组合")
        return combinations
    
    def optimize_parameters(self, data: pd.DataFrame, optimization_type: str = 'grid',
                          max_workers: int = None) -> Dict[str, Any]:
        """优化参数"""
        print(f"\n🔧 开始参数优化 - {optimization_type} 搜索")
        print("=" * 60)
        
        # 生成参数组合
        param_combinations = self.generate_parameter_combinations(optimization_type)
        
        if not param_combinations:
            print("❌ 没有生成任何参数组合")
            return {}
        
        # 设置进程数
        if max_workers is None:
            max_workers = min(mp.cpu_count() - 1, len(param_combinations), 4)
        
        print(f"📊 参数组合数量: {len(param_combinations)}")
        print(f"👥 并行进程数: {max_workers}")
        print(f"📈 数据长度: {len(data)} 根K线")
        
        # 开始优化
        start_time = time.time()
        optimization_results = []
        
        if max_workers == 1:
            # 单进程模式
            for i, params in enumerate(param_combinations):
                result = self._test_single_parameter_set(data, params, i)
                if result:
                    optimization_results.append(result)
                
                if (i + 1) % 10 == 0:
                    print(f"📈 进度: {i + 1}/{len(param_combinations)} ({(i + 1)/len(param_combinations)*100:.1f}%)")
        else:
            # 多进程模式
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                future_to_params = {}
                for i, params in enumerate(param_combinations):
                    future = executor.submit(self._test_single_parameter_set, data, params, i)
                    future_to_params[future] = params
                
                # 收集结果
                completed = 0
                for future in as_completed(future_to_params):
                    completed += 1
                    try:
                        result = future.result()
                        if result:
                            optimization_results.append(result)
                    except Exception as e:
                        print(f"❌ 参数测试失败: {e}")
                    
                    if completed % 10 == 0:
                        print(f"📈 进度: {completed}/{len(param_combinations)} ({completed/len(param_combinations)*100:.1f}%)")
        
        # 处理结果
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n⏱️  优化完成，总耗时: {total_time:.1f} 秒")
        print(f"✅ 有效结果数量: {len(optimization_results)}")
        
        if not optimization_results:
            print("❌ 没有找到有效的参数组合")
            return {}
        
        # 分析结果
        return self._analyze_optimization_results(optimization_results)
    
    def _test_single_parameter_set(self, data: pd.DataFrame, params: Dict[str, Any], 
                                  index: int) -> Optional[Dict[str, Any]]:
        """测试单个参数集合"""
        try:
            from enhanced_signal_generator import EnhancedPinbarDetector
            
            # 创建检测器
            detector = EnhancedPinbarDetector(params)
            
            # 检测信号
            signals = detector.detect_pinbar_patterns(data.copy())
            
            if len(signals) == 0:
                return None
            
            # 模拟交易计算收益
            total_return, win_rate, profit_factor, max_drawdown, total_trades = self._simulate_trading(signals, data)
            
            # 计算综合评分
            score = self._calculate_score(total_return, win_rate, profit_factor, max_drawdown, total_trades)
            
            return {
                'index': index,
                'params': params,
                'total_return': total_return,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'total_trades': total_trades,
                'avg_signals_per_month': len(signals) / (len(data) / 720) if len(data) > 720 else len(signals),
                'score': score
            }
            
        except Exception as e:
            print(f"❌ 参数测试失败 #{index}: {e}")
            return None
    
    def _simulate_trading(self, signals: List, data: pd.DataFrame) -> Tuple[float, float, float, float, int]:
        """模拟交易"""
        if not signals:
            return 0.0, 0.0, 0.0, 0.0, 0
        
        initial_capital = 10000
        current_capital = initial_capital
        peak_capital = initial_capital
        max_drawdown = 0.0
        
        winning_trades = 0
        losing_trades = 0
        total_profit = 0.0
        total_loss = 0.0
        
        for signal in signals:
            # 模拟交易执行
            entry_price = signal.entry_price
            stop_loss = signal.stop_loss
            take_profit = signal.take_profit_1  # 使用第一个止盈目标
            
            # 风险管理
            risk_amount = current_capital * 0.02  # 2%风险
            position_size = risk_amount / abs(entry_price - stop_loss) if abs(entry_price - stop_loss) > 0 else 0
            
            if position_size <= 0:
                continue
            
            # 模拟结果（简化版）
            success_probability = min(signal.confidence_score, 0.8)  # 最高80%胜率
            
            if np.random.random() < success_probability:
                # 盈利交易
                profit = position_size * abs(take_profit - entry_price)
                current_capital += profit
                winning_trades += 1
                total_profit += profit
            else:
                # 亏损交易
                loss = position_size * abs(entry_price - stop_loss)
                current_capital -= loss
                losing_trades += 1
                total_loss += loss
            
            # 更新最大回撤
            peak_capital = max(peak_capital, current_capital)
            drawdown = (peak_capital - current_capital) / peak_capital
            max_drawdown = max(max_drawdown, drawdown)
        
        # 计算统计指标
        total_trades = winning_trades + losing_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        total_return = (current_capital - initial_capital) / initial_capital * 100
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        return total_return, win_rate, profit_factor, max_drawdown * 100, total_trades
    
    def _calculate_score(self, total_return: float, win_rate: float, profit_factor: float, 
                        max_drawdown: float, total_trades: int) -> float:
        """计算综合评分"""
        # 基础分数
        score = 0.0
        
        # 总收益权重 (40%)
        return_score = min(total_return / 100, 2.0) * 40  # 100%收益得满分
        score += return_score
        
        # 胜率权重 (20%)
        win_rate_score = win_rate * 20
        score += win_rate_score
        
        # 盈亏比权重 (20%)
        pf_score = min(profit_factor / 2.0, 1.0) * 20  # 盈亏比2得满分
        score += pf_score
        
        # 最大回撤惩罚 (15%)
        dd_penalty = max(0, 15 - max_drawdown)  # 回撤越大扣分越多
        score += dd_penalty
        
        # 交易频率适中奖励 (5%)
        if 10 <= total_trades <= 100:  # 适中的交易频率
            score += 5
        elif total_trades > 100:
            score += max(0, 5 - (total_trades - 100) * 0.01)  # 过多交易小幅扣分
        
        return round(score, 2)
    
    def _analyze_optimization_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析优化结果"""
        if not results:
            return {}
        
        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        self.optimization_results = results
        
        # 最佳结果
        best_result = results[0]
        
        # 统计分析
        scores = [r['score'] for r in results]
        returns = [r['total_return'] for r in results]
        win_rates = [r['win_rate'] for r in results]
        
        analysis = {
            'best_params': best_result['params'],
            'best_result': best_result,
            'top_10_results': results[:10],
            'statistics': {
                'total_tested': len(results),
                'best_score': best_result['score'],
                'avg_score': np.mean(scores),
                'best_return': max(returns),
                'avg_return': np.mean(returns),
                'best_win_rate': max(win_rates),
                'avg_win_rate': np.mean(win_rates)
            }
        }
        
        return analysis
    
    def print_optimization_results(self, analysis: Dict[str, Any]):
        """打印优化结果"""
        if not analysis:
            print("❌ 没有优化结果可显示")
            return
        
        print("\n" + "=" * 60)
        print("🏆 参数优化结果汇总")
        print("=" * 60)
        
        # 统计信息
        stats = analysis['statistics']
        print(f"📊 测试参数组合数: {stats['total_tested']}")
        print(f"🏆 最佳综合评分: {stats['best_score']:.2f}")
        print(f"📈 最佳收益率: {stats['best_return']:.2f}%")
        print(f"🎯 最佳胜率: {stats['best_win_rate']:.2f}%")
        
        print(f"\n📊 平均表现:")
        print(f"   平均评分: {stats['avg_score']:.2f}")
        print(f"   平均收益: {stats['avg_return']:.2f}%")
        print(f"   平均胜率: {stats['avg_win_rate']:.2f}%")
        
        # 最佳参数
        best_result = analysis['best_result']
        print(f"\n🏆 最佳参数组合:")
        print(f"   综合评分: {best_result['score']:.2f}")
        print(f"   总收益率: {best_result['total_return']:.2f}%")
        print(f"   胜率: {best_result['win_rate']:.2f}%")
        print(f"   盈亏比: {best_result['profit_factor']:.2f}")
        print(f"   最大回撤: {best_result['max_drawdown']:.2f}%")
        print(f"   交易次数: {best_result['total_trades']}")
        
        print(f"\n⚙️  最佳参数详情:")
        best_params = best_result['params']
        for key, value in best_params.items():
            if key != 'preset_name':
                print(f"   {key}: {value}")
        
        # 前5名对比
        print(f"\n📊 前5名参数组合对比:")
        print(f"{'排名':<4} {'评分':<8} {'收益%':<8} {'胜率%':<8} {'盈亏比':<8} {'回撤%':<8} {'交易数':<8}")
        print("-" * 60)
        
        for i, result in enumerate(analysis['top_10_results'][:5], 1):
            print(f"{i:<4} {result['score']:<8.2f} {result['total_return']:<8.2f} "
                  f"{result['win_rate']*100:<8.1f} {result['profit_factor']:<8.2f} "
                  f"{result['max_drawdown']:<8.2f} {result['total_trades']:<8}")
    
    def save_optimization_results(self, analysis: Dict[str, Any], filename: str = None):
        """保存优化结果"""
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"optimization_results_{timestamp}.json"
        
        try:
            # 转换numpy类型为Python原生类型
            def convert_numpy(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                return obj
            
            # 递归转换所有numpy类型
            def deep_convert(obj):
                if isinstance(obj, dict):
                    return {k: deep_convert(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [deep_convert(v) for v in obj]
                else:
                    return convert_numpy(obj)
            
            converted_analysis = deep_convert(analysis)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(converted_analysis, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 优化结果已保存到: {filename}")
            
        except Exception as e:
            print(f"❌ 保存优化结果失败: {e}")
    
    def apply_best_params(self, analysis: Dict[str, Any]):
        """应用最佳参数到配置文件"""
        if not analysis or 'best_params' not in analysis:
            print("❌ 没有最佳参数可应用")
            return
        
        best_params = analysis['best_params']
        
        # 更新配置
        self.config['pinbar_strategy'].update(best_params)
        
        # 保存到文件
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 最佳参数已应用到配置文件: {self.config_file}")
            print(f"🏆 最佳评分: {analysis['best_result']['score']:.2f}")
            
        except Exception as e:
            print(f"❌ 保存配置文件失败: {e}")

# 使用示例
if __name__ == "__main__":
    print("参数优化器已加载")
    print("功能包括:")
    print("✅ 网格搜索优化")
    print("✅ 随机搜索优化") 
    print("✅ 预设配置测试")
    print("✅ 多进程并行计算")
    print("✅ 综合评分系统")
    print("✅ 自动应用最佳参数")