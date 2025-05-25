#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版报告生成器 - 使用外部模板文件版本
改用静态HTML模板文件，便于维护和管理
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from typing import Dict, List, Any, Optional
import datetime
import os
import tempfile
import webbrowser
from jinja2 import Template, FileSystemLoader, Environment
import json
import base64
from io import BytesIO

# 导入拆分的模块
from report_data_processor import ReportDataProcessor
from report_chart_generator import ReportChartGenerator

class EnhancedReportGenerator:
    """增强版报告生成器 - 使用外部模板文件版本"""
    
    def __init__(self):
        self.template_dir = 'templates'
        os.makedirs(self.template_dir, exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        # 设置Jinja2环境，使用文件系统加载器
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True
        )
        
        # 初始化子模块
        self.data_processor = ReportDataProcessor()
        self.chart_generator = ReportChartGenerator()
        
        # 确保模板文件存在
        self._ensure_template_files()
    
    def _ensure_template_files(self):
        """确保所有必需的模板文件存在"""
        required_templates = {
            'enhanced_backtest_report.html': '增强版回测报告模板',
            'multi_symbol_report.html': '多币种报告模板',
            'ab_test_report.html': 'A/B测试报告模板'
        }
        
        missing_templates = []
        for template_name, description in required_templates.items():
            template_path = os.path.join(self.template_dir, template_name)
            if not os.path.exists(template_path):
                missing_templates.append(f"{template_name} ({description})")
        
        if missing_templates:
            print(f"❌ 缺少以下模板文件，请将对应的HTML模板文件放到 {self.template_dir} 目录下：")
            for template in missing_templates:
                print(f"   - {template}")
            print("\n📋 模板文件应包含：")
            print("   1. enhanced_backtest_report.html - 增强版回测报告模板")
            print("   2. multi_symbol_report.html - 多币种报告模板")
            print("   3. ab_test_report.html - A/B测试报告模板")
            return False
        
        print(f"✅ 所有模板文件已就绪，位于: {self.template_dir}")
        return True
    
    def generate_enhanced_backtest_report(self, data: pd.DataFrame, strategy_results: Dict[str, Any],
                                        config: Dict[str, Any], output_file: str = None) -> str:
        """生成增强版回测报告 - 使用外部模板"""
        print("生成增强版回测报告（使用外部模板文件）...")
        
        # 准备增强数据
        report_data = self.data_processor.prepare_enhanced_backtest_data(data, strategy_results, config)
        
        # 添加K线数据到报告数据中
        report_data['kline_data'] = data
        
        # 生成增强图表
        charts = self.chart_generator.create_enhanced_backtest_charts(data, strategy_results)
        
        # 使用外部模板生成HTML报告
        html_content = self._render_template_with_data(
            'enhanced_backtest_report.html',
            report_data, 
            charts
        )
        
        # 保存文件
        if output_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"enhanced_backtest_report_{timestamp}.html"
        
        filepath = os.path.join('reports', output_file)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ 增强版回测报告已保存: {filepath}")
        return filepath

    def generate_multi_symbol_report(self, multi_results: Dict[str, Dict], 
                                   config: Dict[str, Any], output_file: str = None) -> str:
        """生成多币种回测报告 - 使用外部模板"""
        print("生成多币种回测报告（使用外部模板文件）...")
        
        # 准备多币种数据
        report_data = self.data_processor.prepare_multi_symbol_data(multi_results, config)
        
        # 生成多币种图表
        charts = self.chart_generator.create_multi_symbol_charts(multi_results)
        
        # 使用外部模板生成HTML报告
        try:
            template = self.jinja_env.get_template('multi_symbol_report.html')
            html_content = template.render(
                data=report_data,
                charts=charts,
                report_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        except Exception as e:
            print(f"❌ 模板渲染失败: {e}")
            print("请确保 multi_symbol_report.html 模板文件存在且格式正确")
            return None
        
        # 保存文件
        if output_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"multi_symbol_report_{timestamp}.html"
        
        filepath = os.path.join('reports', output_file)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ 多币种回测报告已保存: {filepath}")
        return filepath

    def generate_ab_test_report(self, comparison_data: Dict[str, Any], 
                          data: pd.DataFrame, output_file: str = None) -> str:
        """生成A/B测试对比报告 - 使用外部模板"""
        print("生成A/B测试对比报告（使用外部模板文件）...")
        
        # 提取对比数据
        original_results = comparison_data['original_strategy']
        trend_results = comparison_data['trend_strategy']
        symbol = comparison_data['symbol']
        interval = comparison_data['interval']
        test_type = comparison_data.get('test_type', 'ab_test')
        
        # 计算改进幅度
        def calculate_improvement(original_val, trend_val):
            if original_val == 0:
                return "N/A" if trend_val == 0 else "+∞"
            return f"{((trend_val - original_val) / original_val) * 100:+.1f}%"
        
        # 准备对比指标
        comparison_metrics = [
            {
                'metric': '总收益率',
                'original': f"{original_results['total_return']:.2f}%",
                'trend': f"{trend_results['total_return']:.2f}%",
                'improvement': calculate_improvement(original_results['total_return'], trend_results['total_return']),
                'better': trend_results['total_return'] > original_results['total_return']
            },
            {
                'metric': '总交易数',
                'original': str(original_results['total_trades']),
                'trend': str(trend_results['total_trades']),
                'improvement': calculate_improvement(original_results['total_trades'], trend_results['total_trades']),
                'better': trend_results['total_trades'] > original_results['total_trades']
            },
            {
                'metric': '胜率',
                'original': f"{original_results['win_rate']:.1f}%",
                'trend': f"{trend_results['win_rate']:.1f}%",
                'improvement': calculate_improvement(original_results['win_rate'], trend_results['win_rate']),
                'better': trend_results['win_rate'] > original_results['win_rate']
            },
            {
                'metric': '盈亏比',
                'original': f"{original_results.get('profit_factor', 0):.2f}",
                'trend': f"{trend_results.get('profit_factor', 0):.2f}",
                'improvement': calculate_improvement(original_results.get('profit_factor', 0), trend_results.get('profit_factor', 0)),
                'better': trend_results.get('profit_factor', 0) > original_results.get('profit_factor', 0)
            },
            {
                'metric': '最大回撤',
                'original': f"{original_results['max_drawdown']*100:.2f}%",
                'trend': f"{trend_results['max_drawdown']*100:.2f}%",
                'improvement': calculate_improvement(original_results['max_drawdown']*100, trend_results['max_drawdown']*100),
                'better': trend_results['max_drawdown'] < original_results['max_drawdown']  # 回撤越小越好
            },
            {
                'metric': '夏普比率',
                'original': f"{original_results.get('sharpe_ratio', 0):.3f}",
                'trend': f"{trend_results.get('sharpe_ratio', 0):.3f}",
                'improvement': calculate_improvement(original_results.get('sharpe_ratio', 0), trend_results.get('sharpe_ratio', 0)),
                'better': trend_results.get('sharpe_ratio', 0) > original_results.get('sharpe_ratio', 0)
            }
        ]
        
        # 计算总体评分
        better_count = sum(1 for m in comparison_metrics if m['better'])
        total_metrics = len(comparison_metrics)
        improvement_score = (better_count / total_metrics) * 100
        
        # 生成结论
        if improvement_score >= 70:
            conclusion = "🎉 趋势跟踪版策略显著优于原版策略！"
            conclusion_class = "excellent"
        elif improvement_score >= 50:
            conclusion = "✅ 趋势跟踪版策略整体表现更好"
            conclusion_class = "good"
        elif improvement_score >= 30:
            conclusion = "⚖️ 两种策略各有优劣，建议进一步优化"
            conclusion_class = "neutral"
        else:
            conclusion = "⚠️ 原版策略在此数据集上表现更好"
            conclusion_class = "poor"
        
        # 使用外部模板生成HTML报告
        try:
            template = self.jinja_env.get_template('ab_test_report.html')
            html_content = template.render(
                symbol=symbol,
                interval=interval,
                original_results=original_results,
                trend_results=trend_results,
                comparison_metrics=comparison_metrics,
                improvement_score=improvement_score,
                conclusion=conclusion,
                conclusion_class=conclusion_class,
                report_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        except Exception as e:
            print(f"❌ A/B测试模板渲染失败: {e}")
            print("请确保 ab_test_report.html 模板文件存在且格式正确")
            return None
        
        # 保存文件
        if output_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"ab_test_report_{symbol}_{interval}_{timestamp}.html"
        
        filepath = os.path.join('reports', output_file)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ A/B测试对比报告已保存: {filepath}")
        return filepath

    def _render_template_with_data(self, template_name: str, report_data: Dict[str, Any], 
                                 charts: Dict[str, str]) -> str:
        """使用外部模板渲染报告 - 增强版回测报告专用"""
        
        # 处理交易数据的JSON序列化
        trades_for_json = []
        for trade in report_data['trades']:
            trade_json = trade.copy()
            # 转换datetime对象为字符串
            if 'entry_time' in trade_json and trade_json['entry_time']:
                if hasattr(trade_json['entry_time'], 'strftime'):
                    trade_json['entry_time'] = trade_json['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(trade_json['entry_time'], str):
                    pass  # 已经是字符串
            if 'exit_time' in trade_json and trade_json['exit_time']:
                if hasattr(trade_json['exit_time'], 'strftime'):
                    trade_json['exit_time'] = trade_json['exit_time'].strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(trade_json['exit_time'], str):
                    pass  # 已经是字符串
            
            # 确保所有必要字段存在
            trade_json.setdefault('profit', 0)
            trade_json.setdefault('profit_pct', 0)
            trade_json.setdefault('entry_price', 0)
            trade_json.setdefault('exit_price', 0)
            trade_json.setdefault('size', 0)
            trade_json.setdefault('leverage', 1)
            trade_json.setdefault('signal_type', 'unknown')
            trade_json.setdefault('signal_strength', 0)
            trade_json.setdefault('reason', '未知')
            # 新增：成本相关字段
            trade_json.setdefault('commission_costs', 0)
            trade_json.setdefault('funding_costs', 0)
            trade_json.setdefault('slippage_costs', 0)
            trade_json.setdefault('total_costs', 0)
            trade_json.setdefault('required_margin', 0)
            trade_json.setdefault('margin_ratio', 0)
            trade_json.setdefault('position_value', 0)
            trade_json.setdefault('gross_profit', 0)
            
            trades_for_json.append(trade_json)
        
        # 准备K线数据用于交易详情显示
        kline_data_for_js = []
        if 'kline_data' in report_data and 'timestamp' in report_data['kline_data'].columns:
            kline_df = report_data['kline_data']
            for i in range(len(kline_df)):
                kline_data_for_js.append({
                    'timestamp': kline_df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(kline_df['open'].iloc[i]),
                    'high': float(kline_df['high'].iloc[i]),
                    'low': float(kline_df['low'].iloc[i]),
                    'close': float(kline_df['close'].iloc[i]),
                    'volume': float(kline_df['volume'].iloc[i])
                })
        
        # 使用外部模板渲染
        try:
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(
                data=report_data,
                charts=charts,
                trades_json=json.dumps(trades_for_json, ensure_ascii=False),
                kline_json=json.dumps(kline_data_for_js, ensure_ascii=False) if kline_data_for_js else '[]',
                report_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            return html_content
        except Exception as e:
            print(f"❌ 模板 {template_name} 渲染失败: {e}")
            print("请确保模板文件存在且格式正确")
            raise
    
    def open_report_in_browser(self, filepath: str):
        """在浏览器中打开报告"""
        try:
            abs_path = os.path.abspath(filepath)
            webbrowser.open(f'file://{abs_path}', new=2)
            print(f"✅ 报告已在浏览器中打开: {filepath}")
        except Exception as e:
            print(f"❌ 打开浏览器失败: {e}")

    def get_template_info(self):
        """获取模板信息"""
        template_info = {
            'template_dir': self.template_dir,
            'available_templates': [],
            'missing_templates': []
        }
        
        required_templates = [
            'enhanced_backtest_report.html',
            'multi_symbol_report.html', 
            'ab_test_report.html'
        ]
        
        for template_name in required_templates:
            template_path = os.path.join(self.template_dir, template_name)
            if os.path.exists(template_path):
                template_info['available_templates'].append(template_name)
            else:
                template_info['missing_templates'].append(template_name)
        
        return template_info

    def create_template_directory_structure(self):
        """创建模板目录结构"""
        print("📁 创建模板目录结构...")
        
        # 确保模板目录存在
        os.makedirs(self.template_dir, exist_ok=True)
        
        # 创建说明文件
        readme_content = """# 报告模板文件说明

## 📋 模板文件列表

### 1. enhanced_backtest_report.html
- **用途**: 增强版单币种回测报告
- **特色**: 包含详细成本分析、保证金分析、交易明细表格
- **数据绑定**: data, charts, trades_json, kline_json, report_time

### 2. multi_symbol_report.html  
- **用途**: 多币种对比回测报告
- **特色**: 币种排名、收益率对比、风险收益散点图
- **数据绑定**: data, charts, report_time

### 3. ab_test_report.html
- **用途**: A/B测试对比报告  
- **特色**: 策略VS布局、详细指标对比、改进建议
- **数据绑定**: symbol, interval, original_results, trend_results, comparison_metrics, improvement_score, conclusion, conclusion_class, report_time

## 🎯 使用方法

1. 将对应的HTML模板文件放置到此目录下
2. 模板使用Jinja2语法，支持变量插值、条件判断、循环等
3. 图表数据通过 {{ charts.chart_name|safe }} 方式插入
4. 交易数据通过 {{ trades_json|safe }} 方式传递给JavaScript

## 🔧 维护提示

- 修改模板后立即生效，无需重启程序
- 建议保留模板文件的备份
- 样式修改在<style>标签内进行
- JavaScript交互代码在<script>标签内实现

生成时间: """ + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        readme_path = os.path.join(self.template_dir, 'README.md')
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"✅ 模板目录结构已创建: {self.template_dir}")
        print(f"📖 说明文档已生成: {readme_path}")
        
        return self.template_dir

if __name__ == "__main__":
    print("增强版报告生成器 - 使用外部模板文件版本")
    print("主要改进:")
    print("1. ✅ 使用外部HTML模板文件，便于维护和定制")
    print("2. ✅ 支持Jinja2模板语法，更灵活的数据绑定")
    print("3. ✅ 模板文件分离，代码更清晰")
    print("4. ✅ 模板热更新，修改后立即生效")
    print("5. ✅ 自动检查模板文件完整性")
    
    # 创建实例并检查模板
    generator = EnhancedReportGenerator()
    template_info = generator.get_template_info()
    
    print(f"\n📁 模板目录: {template_info['template_dir']}")
    print(f"✅ 可用模板: {len(template_info['available_templates'])} 个")
    print(f"❌ 缺失模板: {len(template_info['missing_templates'])} 个")
    
    if template_info['missing_templates']:
        print("\n⚠️ 请将以下模板文件放到模板目录:")
        for template in template_info['missing_templates']:
            print(f"   - {template}")
        
        # 创建目录结构
        generator.create_template_directory_structure()
    else:
        print("\n🎉 所有模板文件已就绪，可以开始生成报告！")