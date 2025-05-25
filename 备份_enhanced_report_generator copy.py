#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版报告生成器 - 成本分析版
增加详细的交易成本分析显示（手续费、资金费率、滑点、保证金占用）
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
from jinja2 import Template
import json
import base64
from io import BytesIO

# 导入拆分的模块
from report_data_processor import ReportDataProcessor
from report_chart_generator import ReportChartGenerator

class EnhancedReportGenerator:
    """增强版报告生成器 - 成本分析版"""
    
    def __init__(self):
        self.template_dir = 'templates'
        os.makedirs(self.template_dir, exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        # 初始化子模块
        self.data_processor = ReportDataProcessor()
        self.chart_generator = ReportChartGenerator()
    
    def generate_enhanced_backtest_report(self, data: pd.DataFrame, strategy_results: Dict[str, Any],
                                        config: Dict[str, Any], output_file: str = None) -> str:
        """生成增强版回测报告 - 包含成本分析"""
        print("生成增强版回测报告（包含详细成本分析）...")
        
        # 准备增强数据
        report_data = self.data_processor.prepare_enhanced_backtest_data(data, strategy_results, config)
        
        # 添加K线数据到报告数据中
        report_data['kline_data'] = data
        
        # 生成增强图表
        charts = self.chart_generator.create_enhanced_backtest_charts(data, strategy_results)
        
        # 生成HTML报告
        html_content = self._generate_enhanced_backtest_html(report_data, charts)
        
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
        """生成多币种回测报告"""
        print("生成多币种回测报告...")
        
        # 准备多币种数据
        report_data = self.data_processor.prepare_multi_symbol_data(multi_results, config)
        
        # 生成多币种图表
        charts = self.chart_generator.create_multi_symbol_charts(multi_results)
        
        # 生成HTML报告
        html_content = self._generate_multi_symbol_html(report_data, charts)
        
        # 保存文件
        if output_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"multi_symbol_report_{timestamp}.html"
        
        filepath = os.path.join('reports', output_file)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ 多币种回测报告已保存: {filepath}")
        return filepath

        
    def _generate_enhanced_backtest_html(self, data: Dict[str, Any], 
                                charts: Dict[str, str]) -> str:
        """生成增强版回测HTML报告 - 包含详细成本分析"""
        
        # 处理交易数据的JSON序列化
        trades_for_json = []
        for trade in data['trades']:
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
        if 'kline_data' in data and 'timestamp' in data['kline_data'].columns:
            kline_df = data['kline_data']
            for i in range(len(kline_df)):
                kline_data_for_js.append({
                    'timestamp': kline_df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(kline_df['open'].iloc[i]),
                    'high': float(kline_df['high'].iloc[i]),
                    'low': float(kline_df['low'].iloc[i]),
                    'close': float(kline_df['close'].iloc[i]),
                    'volume': float(kline_df['volume'].iloc[i])
                })
        
        template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pinbar策略回测报告 - 详细成本分析</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background: #f5f5f5;
                color: #333;
            }
            .container { 
                max-width: 1400px; 
                margin: 0 auto; 
                background: white; 
                padding: 20px; 
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            h1, h2 { 
                color: #333;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
                margin-top: 30px;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            .info-row {
                text-align: center;
                color: #666;
                margin: 5px 0;
            }
            
            /* === 成本分析样式 === */
            .cost-summary {
                background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
                border: 1px solid #f39c12;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 4px 15px rgba(243, 156, 18, 0.2);
            }
            
            .cost-summary h3 {
                color: #d68910;
                margin-top: 0;
                border: none;
                font-size: 18px;
            }
            
            .cost-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            
            .cost-item {
                background: rgba(255, 255, 255, 0.8);
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #f39c12;
            }
            
            .cost-value {
                font-size: 20px;
                font-weight: bold;
                color: #d68910;
                margin-bottom: 5px;
            }
            
            .cost-label {
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
            }
            
            /* === 保证金分析样式（修改为网格格式） === */
            .margin-summary {
                background: linear-gradient(135deg, #e3f2fd 0%, #90caf9 100%);
                border: 1px solid #2196f3;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 4px 15px rgba(33, 150, 243, 0.2);
            }
            
            .margin-summary h3 {
                color: #1976d2;
                margin-top: 0;
                border: none;
                font-size: 18px;
            }
            
            /* 保证金网格样式 */
            .margin-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            
            .margin-item {
                background: rgba(255, 255, 255, 0.8);
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #2196f3;
            }
            
            .margin-value {
                font-size: 20px;
                font-weight: bold;
                color: #1976d2;
                margin-bottom: 5px;
            }
            
            .margin-label {
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
            }
            
            .margin-detail {
                font-size: 10px;
                color: #1976d2;
                line-height: 1.2;
                margin-top: 5px;
            }
            
            /* 简化摘要网格样式 */
            .summary-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            
            .summary-item {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #4CAF50;
            }
            
            .summary-value {
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            
            .summary-label {
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
            }
            
            /* 颜色样式 */
            .positive { color: #4CAF50; }
            .negative { color: #f44336; }
            .warning { color: #ff9800; }
            
            /* 交易表格样式 - 增强版 */
            .trades-table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-size: 12px;
            }
            .trades-table th {
                background: #4CAF50;
                color: white;
                padding: 8px 4px;
                text-align: center;
                font-weight: normal;
                font-size: 11px;
            }
            .trades-table td {
                padding: 6px 4px;
                text-align: center;
                border-bottom: 1px solid #eee;
                font-size: 11px;
            }
            .trades-table tr {
                cursor: pointer;
                transition: background-color 0.3s;
            }
            
            .trades-table tr:hover {
                background-color: #e3f2fd;
            }
            
            /* 成本明细样式 */
            .cost-detail {
                font-size: 10px;
                color: #666;
                line-height: 1.2;
            }
            
            /* 翻页控件样式 */
            .pagination {
                text-align: center;
                margin: 20px 0;
            }
            .pagination button {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 8px 15px;
                margin: 0 5px;
                cursor: pointer;
                border-radius: 3px;
                font-size: 14px;
            }
            .pagination button:hover {
                background: #45a049;
            }
            .pagination button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            .pagination .page-info {
                display: inline-block;
                margin: 0 20px;
                color: #666;
            }
            .pagination select {
                padding: 5px;
                margin: 0 5px;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            
            /* 图表容器 */
            .chart-container {
                margin: 30px 0;
                padding: 20px;
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
            }
            
            /* 标签页 */
            .tabs {
                display: flex;
                margin-bottom: 20px;
                border-bottom: 2px solid #e0e0e0;
            }
            .tab {
                padding: 10px 20px;
                cursor: pointer;
                border-bottom: 3px solid transparent;
                transition: all 0.3s;
            }
            .tab:hover {
                background: #f5f5f5;
            }
            .tab.active {
                border-bottom-color: #4CAF50;
                color: #4CAF50;
            }
            .tab-content {
                display: none;
            }
            .tab-content.active {
                display: block;
            }
            
            /* 交易详情弹窗 */
            .trade-modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
            }
            
            .trade-modal-content {
                background-color: white;
                margin: 2% auto;
                padding: 30px;
                border-radius: 15px;
                width: 90%;
                max-width: 1200px;
                max-height: 90%;
                overflow-y: auto;
            }
            
            .close {
                color: #aaa;
                float: right;
                font-size: 28px;
                font-weight: bold;
                cursor: pointer;
            }
            
            .close:hover {
                color: #000;
            }
            
            /* K线图容器 */
            .kline-chart-container {
                width: 100%;
                height: 500px;
                margin-top: 20px;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            .trade-detail-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
                margin-bottom: 20px;
            }
            
            .trade-detail-item {
                padding: 10px;
                background: #f8f9fa;
                border-radius: 5px;
            }
            
            .trade-detail-item strong {
                color: #333;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- 头部 -->
            <div class="header">
                <h1>📊 Pinbar策略回测报告 - 详细成本分析</h1>
                <div class="info-row">生成时间: {{ report_time }}</div>
                <div class="info-row">交易对: {{ data.data_info.symbol }} | 周期: {{ data.data_info.interval }}</div>
                <div class="info-row">时间范围: {{ data.data_info.start_date }} ~ {{ data.data_info.end_date }}</div>
                
                <!-- === 累计成本统计显示 === -->
                {% if data.cost_analysis %}
                <div class="info-row" style="font-size: 16px; font-weight: bold; color: #d68910; margin-top: 15px;">
                    📊 累计交易成本总览: 手续费 {{ "{:.2f}".format(data.cost_analysis.total_commission) }} USDT | 
                    资金费率 {{ "{:.2f}".format(data.cost_analysis.total_funding) }} USDT | 
                    总成本 {{ "{:.2f}".format(data.cost_analysis.total_costs) }} USDT
                    (占收益 {{ "{:.1f}".format(data.cost_analysis.cost_to_profit_ratio) }}%)
                </div>
                {% endif %}
            </div>
            
            <!-- === 详细成本分析区域 === -->
            {% if data.cost_analysis %}
            <div class="cost-summary">
                <h3>💰 交易成本详细分析</h3>
                <div class="cost-grid">
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_commission) }} USDT</div>
                        <div class="cost-label">累计总手续费</div>
                        <div class="cost-detail">平均: {{ "{:.2f}".format(data.cost_analysis.avg_commission_per_trade) }} USDT/笔</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_funding) }} USDT</div>
                        <div class="cost-label">累计资金费率</div>
                        <div class="cost-detail">平均: {{ "{:.2f}".format(data.cost_analysis.avg_funding_per_trade) }} USDT/笔</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_slippage) }} USDT</div>
                        <div class="cost-label">累计滑点成本</div>
                        <div class="cost-detail">平均: {{ "{:.2f}".format(data.cost_analysis.avg_slippage_per_trade) }} USDT/笔</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_costs) }} USDT</div>
                        <div class="cost-label">累计总成本</div>
                        <div class="cost-detail">占收益: {{ "{:.1f}".format(data.cost_analysis.cost_to_profit_ratio) }}%</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.1f}".format(data.cost_analysis.commission_percentage) }}%</div>
                        <div class="cost-label">手续费占比</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.1f}".format(data.cost_analysis.funding_percentage) }}%</div>
                        <div class="cost-label">资金费率占比</div>
                    </div>
                </div>
            </div>
            {% endif %}
            
            <!-- === 保证金使用分析区域（修改为网格格式） === -->
            {% if data.margin_analysis and data.margin_analysis.valid_margin_trades_count > 0 %}
            <div class="margin-summary">
                <h3>📈 保证金使用分析</h3>
                <!-- 数据质量提示 -->
                {% if data.margin_analysis.invalid_margin_count > 0 %}
                <div style="background: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #ffc107;">
                    ⚠️ 发现 {{ data.margin_analysis.invalid_margin_count }} 笔交易的保证金数据异常，已排除统计
                </div>
                {% endif %}
                
                <div class="margin-grid">
                    <div class="margin-item">
                        <div class="margin-value">{{ "{:.1f}".format(data.margin_analysis.avg_margin_ratio) }}%</div>
                        <div class="margin-label">平均保证金占用</div>
                        <div class="margin-detail">
                            范围: {{ "{:.1f}".format(data.margin_analysis.min_margin_ratio) }}% - 
                                {{ "{:.1f}".format(data.margin_analysis.max_margin_ratio) }}%
                        </div>
                    </div>
                    <div class="margin-item">
                        <div class="margin-value">{{ "{:.1f}".format(data.margin_analysis.avg_leverage) }}x</div>
                        <div class="margin-label">平均杠杆</div>
                        <div class="margin-detail">最高: {{ "{:.1f}".format(data.margin_analysis.max_leverage) }}x</div>
                    </div>
                    <div class="margin-item">
                        <div class="margin-value">{{ "{:,.0f}".format(data.margin_analysis.total_position_value) }}</div>
                        <div class="margin-label">总仓位价值 (USDT)</div>
                        <div class="margin-detail">保证金: {{ "{:,.0f}".format(data.margin_analysis.total_margin_used) }} USDT</div>
                    </div>
                    <div class="margin-item">
                        <div class="margin-value">{{ "{:.1f}".format(data.margin_analysis.margin_efficiency) }}</div>
                        <div class="margin-label">保证金效率</div>
                        <div class="margin-detail">仓位/保证金比率</div>
                    </div>
                    <div class="margin-item">
                        <div class="margin-value" style="font-size: 16px;">
                            盈利: {{ "{:.1f}".format(data.margin_analysis.avg_margin_profitable_trades) }}%<br>
                            亏损: {{ "{:.1f}".format(data.margin_analysis.avg_margin_losing_trades) }}%
                        </div>
                        <div class="margin-label">交易类型保证金对比</div>
                    </div>
                    <div class="margin-item">
                        <div class="margin-value" style="font-size: 14px; color: #666;">
                            有效数据: {{ data.margin_analysis.valid_margin_trades_count }}/{{ data.trades|length }}<br>
                            数据完整度: {{ "{:.1f}".format(data.margin_analysis.valid_margin_trades_ratio) }}%
                        </div>
                        <div class="margin-label">数据质量统计</div>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="margin-summary">
                <h3>📈 保证金使用分析</h3>
                <div style="text-align: center; padding: 30px; color: #666; background: #f8f9fa; border-radius: 8px;">
                    {% if data.trades|length == 0 %}
                        📝 暂无交易记录
                    {% else %}
                        ⚠️ 保证金数据异常，无法生成统计<br>
                        <small>共 {{ data.trades|length }} 笔交易，但保证金数据全部无效</small>
                    {% endif %}
                </div>
            </div>
            {% endif %}
            
            <!-- 核心指标摘要 - 简化为网格（3行显示） -->
            <h2>回测结果摘要</h2>
            
            <!-- 第一行：核心收益指标 -->
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value">{{ "{:,.0f}".format(data.summary.initial_cash) }} USDT</div>
                    <div class="summary-label">初始资金</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ "{:,.0f}".format(data.summary.final_value) }} USDT</div>
                    <div class="summary-label">最终资金</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value {{ 'positive' if data.summary.total_return > 0 else 'negative' }}">
                        {{ "{:.2f}".format(data.summary.total_return) }}%
                    </div>
                    <div class="summary-label">总收益率</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ data.summary.total_trades }}</div>
                    <div class="summary-label">总交易次数</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value {{ 'positive' if data.summary.win_rate > 50 else 'negative' }}">
                        {{ "{:.1f}".format(data.summary.win_rate) }}%
                    </div>
                    <div class="summary-label">胜率</div>
                </div>
            </div>
            
            <!-- 第二行：风险指标 -->
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value {{ 'positive' if data.summary.profit_factor > 1 else 'negative' }}">
                        {{ "{:.2f}".format(data.summary.profit_factor) }}
                    </div>
                    <div class="summary-label">盈亏比</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value negative">{{ "{:.2f}".format(data.summary.max_drawdown) }}%</div>
                    <div class="summary-label">最大回撤</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ "{:.3f}".format(data.summary.sharpe_ratio) }}</div>
                    <div class="summary-label">夏普比率</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ "{:.1f}".format(data.summary.avg_holding_time) }} 小时</div>
                    <div class="summary-label">平均持仓时间</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ data.summary.max_consecutive_wins }} / {{ data.summary.max_consecutive_losses }}</div>
                    <div class="summary-label">最大连续盈利/亏损</div>
                </div>
            </div>
            
            <!-- 第三行：信号质量统计 -->
            {% if data.signal_quality_stats %}
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value">{{ data.signal_quality_stats.total_signals }}</div>
                    <div class="summary-label">总检测信号数</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ data.signal_quality_stats.executed_signals }}</div>
                    <div class="summary-label">执行信号数</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ "{:.1f}".format(data.signal_quality_stats.execution_rate) }}%</div>
                    <div class="summary-label">信号执行率</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value {{ 'positive' if data.signal_quality_stats.signal_success_rate > 60 else 'negative' }}">
                        {{ "{:.1f}".format(data.signal_quality_stats.signal_success_rate) }}%
                    </div>
                    <div class="summary-label">信号成功率</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{{ "{:.1f}".format(data.signal_quality_stats.avg_signal_strength) }}/5</div>
                    <div class="summary-label">平均信号强度</div>
                </div>
            </div>
            {% endif %}
            
            <!-- 图表展示 -->
            <div class="tabs">
                <div class="tab active" onclick="showTab('enhanced_price')">价格走势图</div>
                {% if 'pnl_analysis' in charts %}<div class="tab" onclick="showTab('pnl_analysis')">收益分析</div>{% endif %}
            </div>
            
            <div id="enhanced_price" class="tab-content active chart-container">
                {{ charts.enhanced_price|safe }}
            </div>
            
            {% if 'pnl_analysis' in charts %}
            <div id="pnl_analysis" class="tab-content chart-container">
                {{ charts.pnl_analysis|safe }}
            </div>
            {% endif %}
            
            <!-- === 交易明细表格 - 增加成本列 === -->
            <h2>📊 交易记录明细 (共 {{ data.trades|length }} 条) - 含详细成本分析</h2>
            
            <!-- 翻页控件（顶部） -->
            <div class="pagination">
                <button onclick="firstPage()">首页</button>
                <button onclick="prevPage()">上一页</button>
                <span class="page-info">
                    第 <span id="currentPage">1</span> 页 / 共 <span id="totalPages">1</span> 页
                </span>
                <button onclick="nextPage()">下一页</button>
                <button onclick="lastPage()">末页</button>
                <span style="margin-left: 20px;">
                    跳转到: <input type="number" id="gotoPage" min="1" style="width: 60px; padding: 5px;" onkeypress="if(event.key=='Enter') gotoPage()">
                    <button onclick="gotoPage()">跳转</button>
                </span>
                <span style="margin-left: 20px;">
                    每页显示: 
                    <select id="pageSize" onchange="changePageSize()">
                        <option value="50">50条</option>
                        <option value="100" selected>100条</option>
                        <option value="200">200条</option>
                        <option value="500">500条</option>
                    </select>
                </span>
            </div>
            
            <table class="trades-table" id="tradesTable">
                <thead>
                    <tr>
                        <th>序号</th>
                        <th>方向</th>
                        <th>开仓时间</th>
                        <th>开仓价格</th>
                        <th>平仓时间</th>
                        <th>平仓价格</th>
                        <th>仓位大小</th>
                        <th>杠杆</th>
                        <th>保证金占用</th>
                        <th>手续费明细</th>
                        <th>资金费率</th>
                        <th>滑点成本</th>
                        <th>毛利润</th>
                        <th>净收益</th>
                        <th>收益率</th>
                        <th>信号强度</th>
                        <th>平仓原因</th>
                    </tr>
                </thead>
                <tbody id="tradesTableBody">
                    <!-- 动态填充 -->
                </tbody>
            </table>
            
            <!-- 添加交易详情弹窗 -->
            <div id="tradeModal" class="trade-modal">
                <div class="trade-modal-content">
                    <span class="close" onclick="closeTradeDetail()">&times;</span>
                    <h2>交易详情</h2>
                    <div id="tradeDetailContent"></div>
                    <div id="klineChart" class="kline-chart-container"></div>
                </div>
            </div>
            
            <!-- 翻页控件（底部） -->
            <div class="pagination">
                <button onclick="firstPage()">首页</button>
                <button onclick="prevPage()">上一页</button>
                <span class="page-info">
                    第 <span id="currentPage2">1</span> 页 / 共 <span id="totalPages2">1</span> 页
                </span>
                <button onclick="nextPage()">下一页</button>
                <button onclick="lastPage()">末页</button>
            </div>
        </div>
        
        <script>
            // 交易数据和K线数据
            const allTrades = {{ trades_json|safe }};
            const klineData = {{ kline_json|safe }};
            let currentPage = 1;
            let pageSize = 100;
            let totalPages = Math.ceil(allTrades.length / pageSize);
            
            console.log('交易数据加载:', allTrades.length, '条记录');
            console.log('K线数据加载:', klineData.length, '条记录');
            
            // 初始化
            updatePagination();
            renderTrades();
            
            function renderTrades() {
                const tbody = document.getElementById('tradesTableBody');
                tbody.innerHTML = '';
                
                if (!allTrades || allTrades.length === 0) {
                    const row = tbody.insertRow();
                    const cell = row.insertCell(0);
                    cell.colSpan = 17;  // 更新列数
                    cell.textContent = '暂无交易记录';
                    cell.style.textAlign = 'center';
                    cell.style.padding = '20px';
                    cell.style.color = '#999';
                    return;
                }
                
                const start = (currentPage - 1) * pageSize;
                const end = Math.min(start + pageSize, allTrades.length);
                
                console.log(`渲染交易记录 ${start + 1} - ${end} / ${allTrades.length}`);
                
                for (let i = start; i < end; i++) {
                    const trade = allTrades[i];
                    const row = tbody.insertRow();
                    
                    // 添加点击事件
                    row.onclick = function() { showTradeDetail(i); };
                    row.style.cursor = 'pointer';
                    
                    // 序号
                    row.insertCell(0).textContent = i + 1;
                    
                    // 方向
                    const directionCell = row.insertCell(1);
                    if (trade.direction === 'buy') {
                        directionCell.innerHTML = '<span style="color: green;">做多</span>';
                    } else {
                        directionCell.innerHTML = '<span style="color: red;">做空</span>';
                    }
                    
                    // 开仓时间
                    const entryTimeCell = row.insertCell(2);
                    entryTimeCell.textContent = trade.entry_time ? trade.entry_time.substring(0, 16) : '-';
                    entryTimeCell.style.fontSize = '10px';
                    
                    // 开仓价格
                    row.insertCell(3).textContent = trade.entry_price ? trade.entry_price.toFixed(4) : '-';
                    
                    // 平仓时间
                    const exitTimeCell = row.insertCell(4);
                    exitTimeCell.textContent = trade.exit_time ? trade.exit_time.substring(0, 16) : '-';
                    exitTimeCell.style.fontSize = '10px';
                    
                    // 平仓价格
                    row.insertCell(5).textContent = trade.exit_price ? trade.exit_price.toFixed(4) : '-';
                    
                    // 仓位大小
                    row.insertCell(6).textContent = trade.size ? trade.size.toFixed(4) : '-';
                    
                    // 杠杆
                    row.insertCell(7).textContent = (trade.leverage || 1) + 'x';
                    
                    // === 保证金占用 ===
                    const marginCell = row.insertCell(8);
                    const marginAmount = trade.required_margin || 0;
                    const marginRatio = trade.margin_ratio || 0;
                    marginCell.innerHTML = `
                        <div>${marginAmount.toFixed(0)} USDT</div>
                        <div class="margin-detail">${marginRatio.toFixed(1)}%</div>
                    `;
                    
                    // === 手续费明细 ===
                    const commissionCell = row.insertCell(9);
                    const commission = trade.commission_costs || 0;
                    commissionCell.innerHTML = `
                        <div style="color: #d68910; font-weight: bold;">${commission.toFixed(2)} USDT</div>
                        <div class="cost-detail">开仓+平仓手续费</div>
                    `;
                    
                    // === 资金费率 ===
                    const fundingCell = row.insertCell(10);
                    const funding = trade.funding_costs || 0;
                    fundingCell.innerHTML = `
                        <div style="color: #e67e22; font-weight: bold;">${funding.toFixed(2)} USDT</div>
                        <div class="cost-detail">持仓期间累计</div>
                    `;
                    
                    // === 滑点成本 ===
                    const slippageCell = row.insertCell(11);
                    const slippage = trade.slippage_costs || 0;
                    slippageCell.innerHTML = `
                        <div style="color: #8e44ad; font-weight: bold;">${slippage.toFixed(2)} USDT</div>
                        <div class="cost-detail">买卖滑点</div>
                    `;
                    
                    // === 毛利润 ===
                    const grossProfitCell = row.insertCell(12);
                    const grossProfit = trade.gross_profit || 0;
                    grossProfitCell.textContent = grossProfit.toFixed(2);
                    grossProfitCell.className = grossProfit >= 0 ? 'positive' : 'negative';
                    
                    // 净收益
                    const profitCell = row.insertCell(13);
                    const profit = trade.profit || 0;
                    profitCell.textContent = profit.toFixed(2);
                    profitCell.className = profit >= 0 ? 'positive' : 'negative';
                    profitCell.style.fontWeight = 'bold';
                    
                    // 收益率
                    const profitPctCell = row.insertCell(14);
                    const profitPct = trade.profit_pct || 0;
                    profitPctCell.textContent = profitPct.toFixed(2) + '%';
                    profitPctCell.className = profitPct >= 0 ? 'positive' : 'negative';
                    
                    // 信号强度
                    const strengthCell = row.insertCell(15);
                    const strength = trade.signal_strength || 0;
                    strengthCell.textContent = strength + '/5';
                    if (strength >= 4) {
                        strengthCell.style.color = 'green';
                    } else if (strength >= 2) {
                        strengthCell.style.color = 'orange';
                    } else {
                        strengthCell.style.color = 'red';
                    }
                    
                    // 平仓原因
                    row.insertCell(16).textContent = trade.reason || '未知';
                }
            }
            
            function showTradeDetail(tradeIndex) {
                const trade = allTrades[tradeIndex];
                if (!trade) return;
                
                const modal = document.getElementById('tradeModal');
                const content = document.getElementById('tradeDetailContent');
                
                // 格式化详细信息 - 增强版包含成本分析
                content.innerHTML = `
                    <h3>交易 #${tradeIndex + 1} - 详细成本分析</h3>
                    <div class="trade-detail-grid">
                        <div class="trade-detail-item">
                            <h4>基础信息</h4>
                            <p><strong>方向:</strong> ${trade.direction === 'buy' ? '🟢 做多' : '🔴 做空'}</p>
                            <p><strong>开仓时间:</strong> ${trade.entry_time || '-'}</p>
                            <p><strong>开仓价格:</strong> ${trade.entry_price ? trade.entry_price.toFixed(4) : '-'}</p>
                            <p><strong>平仓时间:</strong> ${trade.exit_time || '-'}</p>
                            <p><strong>平仓价格:</strong> ${trade.exit_price ? trade.exit_price.toFixed(4) : '-'}</p>
                            <p><strong>仓位大小:</strong> ${trade.size ? trade.size.toFixed(4) : '-'}</p>
                        </div>
                        <div class="trade-detail-item">
                            <h4>保证金信息</h4>
                            <p><strong>杠杆倍数:</strong> ${trade.leverage || 1}x</p>
                            <p><strong>仓位价值:</strong> ${(trade.position_value || 0).toFixed(2)} USDT</p>
                            <p><strong>保证金占用:</strong> ${(trade.required_margin || 0).toFixed(2)} USDT</p>
                            <p><strong>保证金比例:</strong> ${(trade.margin_ratio || 0).toFixed(1)}%</p>
                            <p><strong>保证金回报:</strong> ${(trade.return_on_margin || 0).toFixed(1)}%</p>
                        </div>
                    </div>
                    <div class="trade-detail-grid">
                        <div class="trade-detail-item">
                            <h4>成本明细</h4>
                            <p><strong>手续费:</strong> ${(trade.commission_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>资金费率:</strong> ${(trade.funding_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>滑点成本:</strong> ${(trade.slippage_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>总成本:</strong> ${(trade.total_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>成本比例:</strong> ${(trade.cost_ratio || 0).toFixed(1)}%</p>
                        </div>
                        <div class="trade-detail-item">
                            <h4>收益分析</h4>
                            <p><strong>毛利润:</strong> ${(trade.gross_profit || 0).toFixed(2)} USDT</p>
                            <p><strong>净利润:</strong> ${(trade.profit || 0).toFixed(2)} USDT</p>
                            <p><strong>收益率:</strong> ${(trade.profit_pct || 0).toFixed(2)}%</p>
                            <p><strong>平仓原因:</strong> ${trade.reason || '-'}</p>
                        </div>
                    </div>
                    <div class="trade-detail-grid">
                        <div class="trade-detail-item">
                            <h4>信号信息</h4>
                            <p><strong>信号类型:</strong> ${trade.signal_type === 'hammer' ? '🔨 锤形线' : trade.signal_type === 'shooting_star' ? '⭐ 射击线' : trade.signal_type || '-'}</p>
                            <p><strong>信号强度:</strong> ${trade.signal_strength || '-'}/5</p>
                            <p><strong>置信度:</strong> ${trade.confidence_score ? trade.confidence_score.toFixed(2) : '-'}</p>
                            <p><strong>趋势对齐:</strong> ${trade.trend_alignment ? '✅ 是' : '❌ 否'}</p>
                        </div>
                        <div class="trade-detail-item">
                            <h4>效率指标</h4>
                            <p><strong>成本效率:</strong> ${((trade.total_costs || 0) / Math.abs(trade.gross_profit || 1) * 100).toFixed(1)}%</p>
                            <p><strong>时间效率:</strong> ${((trade.profit || 0) / Math.max(1, (new Date(trade.exit_time) - new Date(trade.entry_time)) / (1000 * 3600)) * 24).toFixed(2)} USDT/天</p>
                        </div>
                    </div>
                    <h4>📊 交易区间K线图</h4>
                `;
                
                // 生成K线图
                generateTradeKlineChart(trade);
                
                modal.style.display = 'block';
            }
            
            function generateTradeKlineChart(trade) {
                if (!klineData || klineData.length === 0) {
                    document.getElementById('klineChart').innerHTML = '<p style="text-align: center; padding: 50px;">暂无K线数据</p>';
                    return;
                }
                
                try {
                    // 找到开仓和平仓时间对应的K线索引
                    const entryTime = new Date(trade.entry_time);
                    const exitTime = new Date(trade.exit_time);
                    
                    let entryIndex = -1;
                    let exitIndex = -1;
                    
                    // 查找最接近的K线
                    for (let i = 0; i < klineData.length; i++) {
                        const klineTime = new Date(klineData[i].timestamp);
                        if (entryIndex === -1 && klineTime >= entryTime) {
                            entryIndex = i;
                        }
                        if (klineTime >= exitTime) {
                            exitIndex = i;
                            break;
                        }
                    }
                    
                    if (entryIndex === -1 || exitIndex === -1) {
                        document.getElementById('klineChart').innerHTML = '<p style="text-align: center; padding: 50px;">无法找到对应的K线数据</p>';
                        return;
                    }
                    
                    // 获取前30根和后30根K线
                    const startIndex = Math.max(0, entryIndex - 30);
                    const endIndex = Math.min(klineData.length - 1, exitIndex + 30);
                    
                    const chartData = klineData.slice(startIndex, endIndex + 1);
                    
                    // 准备Plotly数据
                    const x = chartData.map(d => d.timestamp);
                    const open = chartData.map(d => d.open);
                    const high = chartData.map(d => d.high);
                    const low = chartData.map(d => d.low);
                    const close = chartData.map(d => d.close);
                    const volume = chartData.map(d => d.volume);
                    
                    // 创建K线图
                    const traces = [
                        {
                            x: x,
                            open: open,
                            high: high,
                            low: low,
                            close: close,
                            type: 'candlestick',
                            name: 'K线',
                            increasing: {line: {color: '#26a69a'}},
                            decreasing: {line: {color: '#ef5350'}}
                        }
                    ];
                    
                    // 添加开仓和平仓标记
                    if (entryIndex >= startIndex && entryIndex <= endIndex) {
                        traces.push({
                            x: [trade.entry_time],
                            y: [trade.entry_price],
                            mode: 'markers',
                            marker: {
                                color: trade.direction === 'buy' ? 'green' : 'red',
                                size: 15,
                                symbol: trade.direction === 'buy' ? 'triangle-up' : 'triangle-down'
                            },
                            name: '开仓点',
                            showlegend: true
                        });
                    }
                    
                    if (exitIndex >= startIndex && exitIndex <= endIndex) {
                        traces.push({
                            x: [trade.exit_time],
                            y: [trade.exit_price],
                            mode: 'markers',
                            marker: {
                                color: trade.direction === 'buy' ? 'lightgreen' : 'lightcoral',
                                size: 15,
                                symbol: trade.direction === 'buy' ? 'triangle-down' : 'triangle-up'
                            },
                            name: '平仓点',
                            showlegend: true
                        });
                    }
                    
                    // 添加止损线
                    if (trade.stop_loss) {
                        traces.push({
                            x: [x[0], x[x.length-1]],
                            y: [trade.stop_loss, trade.stop_loss],
                            mode: 'lines',
                            line: {
                                color: 'red',
                                width: 1,
                                dash: 'dash'
                            },
                            name: '止损线',
                            showlegend: true
                        });
                    }
                    
                    // 添加止盈线
                    if (trade.take_profit_1) {
                        traces.push({
                            x: [x[0], x[x.length-1]],
                            y: [trade.take_profit_1, trade.take_profit_1],
                            mode: 'lines',
                            line: {
                                color: 'green',
                                width: 1,
                                dash: 'dot'
                            },
                            name: '止盈1',
                            showlegend: true
                        });
                    }
                    
                    const layout = {
                        title: `交易区间K线图 (${trade.direction === 'buy' ? '做多' : '做空'}) - 成本: ${(trade.total_costs || 0).toFixed(2)} USDT`,
                        xaxis: {
                            title: '时间',
                            rangeslider: {visible: false}
                        },
                        yaxis: {
                            title: '价格'
                        },
                        showlegend: true,
                        height: 450
                    };
                    
                    Plotly.newPlot('klineChart', traces, layout);
                    
                } catch (error) {
                    console.error('生成K线图失败:', error);
                    document.getElementById('klineChart').innerHTML = '<p style="text-align: center; padding: 50px;">K线图生成失败</p>';
                }
            }
            
            function closeTradeDetail() {
                document.getElementById('tradeModal').style.display = 'none';
            }
            
            // 点击弹窗外部关闭
            window.onclick = function(event) {
                const modal = document.getElementById('tradeModal');
                if (event.target === modal) {
                    modal.style.display = 'none';
                }
            }
            
            // ESC键关闭弹窗
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Escape') {
                    closeTradeDetail();
                }
            });
            
            // 翻页函数
            function updatePagination() {
                totalPages = Math.ceil(Math.max(1, allTrades.length) / pageSize);
                document.getElementById('currentPage').textContent = currentPage;
                document.getElementById('currentPage2').textContent = currentPage;
                document.getElementById('totalPages').textContent = totalPages;
                document.getElementById('totalPages2').textContent = totalPages;
                
                // 更新按钮状态
                const prevButtons = document.querySelectorAll('.pagination button:nth-child(2)');
                const nextButtons = document.querySelectorAll('.pagination button:nth-child(4)');
                
                prevButtons.forEach(btn => btn.disabled = currentPage <= 1);
                nextButtons.forEach(btn => btn.disabled = currentPage >= totalPages);
            }
            
            function firstPage() {
                currentPage = 1;
                updatePagination();
                renderTrades();
            }
            
            function lastPage() {
                currentPage = totalPages;
                updatePagination();
                renderTrades();
            }
            
            function prevPage() {
                if (currentPage > 1) {
                    currentPage--;
                    updatePagination();
                    renderTrades();
                }
            }
            
            function nextPage() {
                if (currentPage < totalPages) {
                    currentPage++;
                    updatePagination();
                    renderTrades();
                }
            }
            
            function gotoPage() {
                const input = document.getElementById('gotoPage');
                const page = parseInt(input.value);
                if (page >= 1 && page <= totalPages) {
                    currentPage = page;
                    updatePagination();
                    renderTrades();
                    input.value = '';
                } else {
                    alert(`请输入有效的页码 (1-${totalPages})`);
                }
            }
            
            function changePageSize() {
                pageSize = parseInt(document.getElementById('pageSize').value);
                currentPage = 1;
                updatePagination();
                renderTrades();
            }
            
            function showTab(tabName) {
                // 隐藏所有标签页内容
                const contents = document.querySelectorAll('.tab-content');
                contents.forEach(content => content.classList.remove('active'));
                
                // 移除所有标签的active类
                const tabs = document.querySelectorAll('.tab');
                tabs.forEach(tab => tab.classList.remove('active'));
                
                // 显示选中的标签页
                document.getElementById(tabName).classList.add('active');
                event.target.classList.add('active');
            }
        </script>
    </body>
    </html>
        """
        
        template = Template(template_str)
        return template.render(
            data=data,
            charts=charts,
            trades_json=json.dumps(trades_for_json, ensure_ascii=False),
            kline_json=json.dumps(kline_data_for_js, ensure_ascii=False) if kline_data_for_js else '[]',
            report_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    def _generate_enhanced_backtest_html_back20250525(self, data: Dict[str, Any], 
                                    charts: Dict[str, str]) -> str:
        """生成增强版回测HTML报告 - 包含详细成本分析"""
        
        # 处理交易数据的JSON序列化
        trades_for_json = []
        for trade in data['trades']:
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
        if 'kline_data' in data and 'timestamp' in data['kline_data'].columns:
            kline_df = data['kline_data']
            for i in range(len(kline_df)):
                kline_data_for_js.append({
                    'timestamp': kline_df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(kline_df['open'].iloc[i]),
                    'high': float(kline_df['high'].iloc[i]),
                    'low': float(kline_df['low'].iloc[i]),
                    'close': float(kline_df['close'].iloc[i]),
                    'volume': float(kline_df['volume'].iloc[i])
                })
        
        template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pinbar策略回测报告 - 详细成本分析</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background: #f5f5f5;
                color: #333;
            }
            .container { 
                max-width: 1400px; 
                margin: 0 auto; 
                background: white; 
                padding: 20px; 
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            h1, h2 { 
                color: #333;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
                margin-top: 30px;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            .info-row {
                text-align: center;
                color: #666;
                margin: 5px 0;
            }
            
            /* === 新增：成本分析样式 === */
            .cost-summary {
                background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
                border: 1px solid #f39c12;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 4px 15px rgba(243, 156, 18, 0.2);
            }
            
            .cost-summary h3 {
                color: #d68910;
                margin-top: 0;
                border: none;
                font-size: 18px;
            }
            
            .cost-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            
            .cost-item {
                background: rgba(255, 255, 255, 0.8);
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #f39c12;
            }
            
            .cost-value {
                font-size: 20px;
                font-weight: bold;
                color: #d68910;
                margin-bottom: 5px;
            }
            
            .cost-label {
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
            }
            
            /* === 新增：保证金分析样式 === */
            .margin-summary {
                background: linear-gradient(135deg, #e3f2fd 0%, #90caf9 100%);
                border: 1px solid #2196f3;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 4px 15px rgba(33, 150, 243, 0.2);
            }
            
            .margin-summary h3 {
                color: #1976d2;
                margin-top: 0;
                border: none;
                font-size: 18px;
            }
            
            /* 简化的摘要表格样式 */
            .summary-table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            .summary-table td {
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }
            .summary-table td:first-child {
                font-weight: bold;
                width: 40%;
                color: #666;
            }
            .summary-table td:last-child {
                text-align: right;
            }
            
            /* 颜色样式 */
            .positive { color: #4CAF50; }
            .negative { color: #f44336; }
            .warning { color: #ff9800; }
            
            /* 交易表格样式 - 增强版 */
            .trades-table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-size: 12px;
            }
            .trades-table th {
                background: #4CAF50;
                color: white;
                padding: 8px 4px;
                text-align: center;
                font-weight: normal;
                font-size: 11px;
            }
            .trades-table td {
                padding: 6px 4px;
                text-align: center;
                border-bottom: 1px solid #eee;
                font-size: 11px;
            }
            .trades-table tr {
                cursor: pointer;
                transition: background-color 0.3s;
            }
            
            .trades-table tr:hover {
                background-color: #e3f2fd;
            }
            
            /* 成本明细样式 */
            .cost-detail {
                font-size: 10px;
                color: #666;
                line-height: 1.2;
            }
            
            .margin-detail {
                font-size: 10px;
                color: #1976d2;
                line-height: 1.2;
            }
            
            /* 翻页控件样式 */
            .pagination {
                text-align: center;
                margin: 20px 0;
            }
            .pagination button {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 8px 15px;
                margin: 0 5px;
                cursor: pointer;
                border-radius: 3px;
                font-size: 14px;
            }
            .pagination button:hover {
                background: #45a049;
            }
            .pagination button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            .pagination .page-info {
                display: inline-block;
                margin: 0 20px;
                color: #666;
            }
            .pagination select {
                padding: 5px;
                margin: 0 5px;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            
            /* 策略配置样式 */
            .config-table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            .config-table td {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            .config-table td:first-child {
                font-weight: bold;
                color: #666;
                width: 30%;
            }
            
            /* 图表容器 */
            .chart-container {
                margin: 30px 0;
                padding: 20px;
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
            }
            
            /* 标签页 */
            .tabs {
                display: flex;
                margin-bottom: 20px;
                border-bottom: 2px solid #e0e0e0;
            }
            .tab {
                padding: 10px 20px;
                cursor: pointer;
                border-bottom: 3px solid transparent;
                transition: all 0.3s;
            }
            .tab:hover {
                background: #f5f5f5;
            }
            .tab.active {
                border-bottom-color: #4CAF50;
                color: #4CAF50;
            }
            .tab-content {
                display: none;
            }
            .tab-content.active {
                display: block;
            }
            
            /* 交易详情弹窗 */
            .trade-modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
            }
            
            .trade-modal-content {
                background-color: white;
                margin: 2% auto;
                padding: 30px;
                border-radius: 15px;
                width: 90%;
                max-width: 1200px;
                max-height: 90%;
                overflow-y: auto;
            }
            
            .close {
                color: #aaa;
                float: right;
                font-size: 28px;
                font-weight: bold;
                cursor: pointer;
            }
            
            .close:hover {
                color: #000;
            }
            
            /* K线图容器 */
            .kline-chart-container {
                width: 100%;
                height: 500px;
                margin-top: 20px;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            .trade-detail-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
                margin-bottom: 20px;
            }
            
            .trade-detail-item {
                padding: 10px;
                background: #f8f9fa;
                border-radius: 5px;
            }
            
            .trade-detail-item strong {
                color: #333;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- 头部 -->
            <div class="header">
                <h1>📊 Pinbar策略回测报告 - 详细成本分析</h1>
                <div class="info-row">生成时间: {{ report_time }}</div>
                <div class="info-row">交易对: {{ data.data_info.symbol }} | 周期: {{ data.data_info.interval }}</div>
                <div class="info-row">时间范围: {{ data.data_info.start_date }} ~ {{ data.data_info.end_date }}</div>
                
                <!-- === 新增：累计成本统计显示 === -->
                {% if data.cost_analysis %}
                <div class="info-row" style="font-size: 16px; font-weight: bold; color: #d68910; margin-top: 15px;">
                    📊 累计交易成本总览: 手续费 {{ "{:.2f}".format(data.cost_analysis.total_commission or 0) }} USDT | 
                    资金费率 {{ "{:.2f}".format(data.cost_analysis.total_funding) }} USDT | 
                    总成本 {{ "{:.2f}".format(data.cost_analysis.total_costs) }} USDT
                    (占收益 {{ "{:.1f}".format(data.cost_analysis.cost_to_profit_ratio) }}%)
                </div>
                {% endif %}
            </div>
            
            <!-- === 新增：详细成本分析区域 === -->
            {% if data.cost_analysis %}
            <div class="cost-summary">
                <h3>💰 交易成本详细分析</h3>
                <div class="cost-grid">
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_commission or 0) }} USDT</div>
                        <div class="cost-label">累计总手续费</div>
                        <div class="cost-detail">平均: {{ "{:.2f}".format(data.cost_analysis.avg_commission_per_trade) }} USDT/笔</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_funding) }} USDT</div>
                        <div class="cost-label">累计资金费率</div>
                        <div class="cost-detail">平均: {{ "{:.2f}".format(data.cost_analysis.avg_funding_per_trade) }} USDT/笔</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_slippage) }} USDT</div>
                        <div class="cost-label">累计滑点成本</div>
                        <div class="cost-detail">平均: {{ "{:.2f}".format(data.cost_analysis.avg_slippage_per_trade) }} USDT/笔</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.2f}".format(data.cost_analysis.total_costs) }} USDT</div>
                        <div class="cost-label">累计总成本</div>
                        <div class="cost-detail">占收益: {{ "{:.1f}".format(data.cost_analysis.cost_to_profit_ratio) }}%</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.1f}".format(data.cost_analysis.commission_percentage) }}%</div>
                        <div class="cost-label">手续费占比</div>
                    </div>
                    <div class="cost-item">
                        <div class="cost-value">{{ "{:.1f}".format(data.cost_analysis.funding_percentage) }}%</div>
                        <div class="cost-label">资金费率占比</div>
                    </div>
                </div>
            </div>
            {% endif %}
            
            <!-- === 新增：保证金使用分析区域 === -->
            {% if data.margin_analysis and data.margin_analysis.valid_margin_trades_count > 0 %}
            <div class="margin-summary">
                <h3>📈 保证金使用分析</h3>
                <!-- 数据质量提示 -->
            {% if data.margin_analysis.invalid_margin_count > 0 %}
            <div style="background: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #ffc107;">
                ⚠️ 发现 {{ data.margin_analysis.invalid_margin_count }} 笔交易的保证金数据异常，已排除统计
            </div>
            {% endif %}
            
            <div class="cost-breakdown">
                <div class="cost-item">
                    <div style="font-size: 18px; font-weight: bold; color: #17a2b8;">
                        {{ "{:.1f}".format(data.margin_analysis.avg_margin_ratio) }}%
                    </div>
                    <div>平均保证金占用</div>
                    <div class="margin-detail">
                        范围: {{ "{:.1f}".format(data.margin_analysis.min_margin_ratio) }}% - 
                            {{ "{:.1f}".format(data.margin_analysis.max_margin_ratio) }}%
                    </div>
                </div>
                <div class="cost-item">
                    <div style="font-size: 18px; font-weight: bold; color: #28a745;">
                        {{ "{:.1f}".format(data.margin_analysis.avg_leverage) }}x
                    </div>
                    <div>平均杠杆</div>
                    <div class="margin-detail">最高: {{ "{:.1f}".format(data.margin_analysis.max_leverage) }}x</div>
                </div>
                <div class="cost-item">
                    <div style="font-size: 18px; font-weight: bold; color: #6610f2;">
                        {{ "{:,.0f}".format(data.margin_analysis.total_position_value) }}
                    </div>
                    <div>总仓位价值 (USDT)</div>
                    <div class="margin-detail">保证金: {{ "{:,.0f}".format(data.margin_analysis.total_margin_used) }} USDT</div>
                </div>
                <div class="cost-item">
                    <div style="font-size: 18px; font-weight: bold; color: #e83e8c;">
                        {{ "{:.1f}".format(data.margin_analysis.margin_efficiency) }}
                    </div>
                    <div>保证金效率</div>
                    <div class="margin-detail">仓位/保证金比率</div>
                </div>
                <div class="cost-item">
                    <div style="font-size: 16px; font-weight: bold; color: #17a2b8;">
                        盈利: {{ "{:.1f}".format(data.margin_analysis.avg_margin_profitable_trades) }}%<br>
                        亏损: {{ "{:.1f}".format(data.margin_analysis.avg_margin_losing_trades) }}%
                    </div>
                    <div>交易类型保证金对比</div>
                </div>
                <div class="cost-item">
                    <div style="font-size: 14px; color: #666;">
                        有效数据: {{ data.margin_analysis.valid_margin_trades_count }}/{{ data.trades|length }}<br>
                        数据完整度: {{ "{:.1f}".format(data.margin_analysis.valid_margin_trades_ratio) }}%
                    </div>
                    <div>数据质量统计</div>
                </div>
            </div>
        </div>
        {% else %}
        <div class="margin-analysis">
            <h3>📈 保证金使用分析</h3>
            <div style="text-align: center; padding: 30px; color: #666; background: #f8f9fa; border-radius: 8px;">
                {% if data.trades|length == 0 %}
                    📝 暂无交易记录
                {% else %}
                    ⚠️ 保证金数据异常，无法生成统计<br>
                    <small>共 {{ data.trades|length }} 笔交易，但保证金数据全部无效</small>
                {% endif %}
            </div>
        </div>
        {% endif %}
            
            <!-- 核心指标摘要 - 简化为表格 -->
            <h2>回测结果摘要</h2>
            <table class="summary-table">
                <tr>
                    <td>初始资金</td>
                    <td>{{ "{:,.0f}".format(data.summary.initial_cash) }} USDT</td>
                </tr>
                <tr>
                    <td>最终资金</td>
                    <td>{{ "{:,.0f}".format(data.summary.final_value) }} USDT</td>
                </tr>
                <tr>
                    <td>总收益率</td>
                    <td class="{{ 'positive' if data.summary.total_return > 0 else 'negative' }}">
                        {{ "{:.2f}".format(data.summary.total_return) }}%
                    </td>
                </tr>
                <tr>
                    <td>总交易次数</td>
                    <td>{{ data.summary.total_trades }}</td>
                </tr>
                <tr>
                    <td>胜率</td>
                    <td class="{{ 'positive' if data.summary.win_rate > 50 else 'negative' }}">
                        {{ "{:.2f}".format(data.summary.win_rate) }}%
                    </td>
                </tr>
                <tr>
                    <td>盈亏比</td>
                    <td class="{{ 'positive' if data.summary.profit_factor > 1 else 'negative' }}">
                        {{ "{:.2f}".format(data.summary.profit_factor) }}
                    </td>
                </tr>
                <tr>
                    <td>最大回撤</td>
                    <td class="negative">{{ "{:.2f}".format(data.summary.max_drawdown) }}%</td>
                </tr>
                <tr>
                    <td>夏普比率</td>
                    <td>{{ "{:.3f}".format(data.summary.sharpe_ratio) }}</td>
                </tr>
                <tr>
                    <td>平均持仓时间</td>
                    <td>{{ "{:.1f}".format(data.summary.avg_holding_time) }} 小时</td>
                </tr>
                <tr>
                    <td>最大连续盈利</td>
                    <td>{{ data.summary.max_consecutive_wins }} 次</td>
                </tr>
                <tr>
                    <td>最大连续亏损</td>
                    <td>{{ data.summary.max_consecutive_losses }} 次</td>
                </tr>
            </table>
            
            <!-- 信号质量统计 - 简化为表格 -->
            {% if data.signal_quality_stats %}
            <h2>信号质量统计</h2>
            <table class="summary-table">
                <tr>
                    <td>总检测信号数</td>
                    <td>{{ data.signal_quality_stats.total_signals }}</td>
                </tr>
                <tr>
                    <td>执行信号数</td>
                    <td>{{ data.signal_quality_stats.executed_signals }}</td>
                </tr>
                <tr>
                    <td>信号执行率</td>
                    <td>{{ "{:.1f}".format(data.signal_quality_stats.execution_rate) }}%</td>
                </tr>
                <tr>
                    <td>信号成功率</td>
                    <td class="{{ 'positive' if data.signal_quality_stats.signal_success_rate > 60 else 'negative' }}">
                        {{ "{:.1f}".format(data.signal_quality_stats.signal_success_rate) }}%
                    </td>
                </tr>
                <tr>
                    <td>趋势对齐信号数</td>
                    <td>{{ data.signal_quality_stats.trend_aligned_signals }}</td>
                </tr>
                <tr>
                    <td>高质量信号数</td>
                    <td>{{ data.signal_quality_stats.high_quality_signals }}</td>
                </tr>
                <tr>
                    <td>平均信号强度</td>
                    <td>{{ "{:.1f}".format(data.signal_quality_stats.avg_signal_strength) }}/5</td>
                </tr>
                <tr>
                    <td>平均置信度</td>
                    <td>{{ "{:.2f}".format(data.signal_quality_stats.avg_confidence_score) }}</td>
                </tr>
            </table>
            {% endif %}
            
            <!-- 图表展示 -->
            <div class="tabs">
                <div class="tab active" onclick="showTab('enhanced_price')">价格走势图</div>
                {% if 'pnl_analysis' in charts %}<div class="tab" onclick="showTab('pnl_analysis')">收益分析</div>{% endif %}
            </div>
            
            <div id="enhanced_price" class="tab-content active chart-container">
                {{ charts.enhanced_price|safe }}
            </div>
            
            {% if 'pnl_analysis' in charts %}
            <div id="pnl_analysis" class="tab-content chart-container">
                {{ charts.pnl_analysis|safe }}
            </div>
            {% endif %}
            
            <!-- === 修改：交易明细表格 - 增加成本列 === -->
            <h2>📊 交易记录明细 (共 {{ data.trades|length }} 条) - 含详细成本分析</h2>
            
            <!-- 翻页控件（顶部） -->
            <div class="pagination">
                <button onclick="firstPage()">首页</button>
                <button onclick="prevPage()">上一页</button>
                <span class="page-info">
                    第 <span id="currentPage">1</span> 页 / 共 <span id="totalPages">1</span> 页
                </span>
                <button onclick="nextPage()">下一页</button>
                <button onclick="lastPage()">末页</button>
                <span style="margin-left: 20px;">
                    跳转到: <input type="number" id="gotoPage" min="1" style="width: 60px; padding: 5px;" onkeypress="if(event.key=='Enter') gotoPage()">
                    <button onclick="gotoPage()">跳转</button>
                </span>
                <span style="margin-left: 20px;">
                    每页显示: 
                    <select id="pageSize" onchange="changePageSize()">
                        <option value="50">50条</option>
                        <option value="100" selected>100条</option>
                        <option value="200">200条</option>
                        <option value="500">500条</option>
                    </select>
                </span>
            </div>
            
            <table class="trades-table" id="tradesTable">
                <thead>
                    <tr>
                        <th>序号</th>
                        <th>方向</th>
                        <th>开仓时间</th>
                        <th>开仓价格</th>
                        <th>平仓时间</th>
                        <th>平仓价格</th>
                        <th>仓位大小</th>
                        <th>杠杆</th>
                        <th>保证金占用</th>
                        <th>手续费明细</th>
                        <th>资金费率</th>
                        <th>滑点成本</th>
                        <th>毛利润</th>
                        <th>净收益</th>
                        <th>收益率</th>
                        <th>信号强度</th>
                        <th>平仓原因</th>
                    </tr>
                </thead>
                <tbody id="tradesTableBody">
                    <!-- 动态填充 -->
                </tbody>
            </table>
            
            <!-- 添加交易详情弹窗 -->
            <div id="tradeModal" class="trade-modal">
                <div class="trade-modal-content">
                    <span class="close" onclick="closeTradeDetail()">&times;</span>
                    <h2>交易详情</h2>
                    <div id="tradeDetailContent"></div>
                    <div id="klineChart" class="kline-chart-container"></div>
                </div>
            </div>
            
            <!-- 翻页控件（底部） -->
            <div class="pagination">
                <button onclick="firstPage()">首页</button>
                <button onclick="prevPage()">上一页</button>
                <span class="page-info">
                    第 <span id="currentPage2">1</span> 页 / 共 <span id="totalPages2">1</span> 页
                </span>
                <button onclick="nextPage()">下一页</button>
                <button onclick="lastPage()">末页</button>
            </div>
            
            <!-- 策略配置信息 - 简化为表格 -->
            <h2>策略配置</h2>
            <table class="config-table">
                <tr>
                    <td>交易对</td>
                    <td>{{ data.config.symbol }}</td>
                </tr>
                <tr>
                    <td>时间周期</td>
                    <td>{{ data.config.interval }}</td>
                </tr>
                <tr>
                    <td>杠杆</td>
                    <td>{{ data.config.leverage }}x</td>
                </tr>
                <tr>
                    <td>单笔风险</td>
                    <td>{{ data.config.risk_per_trade * 100 }}%</td>
                </tr>
                <tr>
                    <td>止损比例</td>
                    <td>{{ data.config.stop_loss_pct * 100 }}%</td>
                </tr>
                <tr>
                    <td>止盈比例</td>
                    <td>{{ data.config.take_profit_pct * 100 }}%</td>
                </tr>
                <tr>
                    <td>数据来源</td>
                    <td>{{ data.config.data_source }}</td>
                </tr>
                <tr>
                    <td>动态杠杆</td>
                    <td>{{ '是' if data.config.use_dynamic_leverage else '否' }}</td>
                </tr>
            </table>
        </div>
        
        <script>
            // 交易数据和K线数据
            const allTrades = {{ trades_json|safe }};
            const klineData = {{ kline_json|safe }};
            let currentPage = 1;
            let pageSize = 100;
            let totalPages = Math.ceil(allTrades.length / pageSize);
            
            console.log('交易数据加载:', allTrades.length, '条记录');
            console.log('K线数据加载:', klineData.length, '条记录');
            
            // 初始化
            updatePagination();
            renderTrades();
            
            function renderTrades() {
                const tbody = document.getElementById('tradesTableBody');
                tbody.innerHTML = '';
                
                if (!allTrades || allTrades.length === 0) {
                    const row = tbody.insertRow();
                    const cell = row.insertCell(0);
                    cell.colSpan = 17;  // 更新列数
                    cell.textContent = '暂无交易记录';
                    cell.style.textAlign = 'center';
                    cell.style.padding = '20px';
                    cell.style.color = '#999';
                    return;
                }
                
                const start = (currentPage - 1) * pageSize;
                const end = Math.min(start + pageSize, allTrades.length);
                
                console.log(`渲染交易记录 ${start + 1} - ${end} / ${allTrades.length}`);
                
                for (let i = start; i < end; i++) {
                    const trade = allTrades[i];
                    const row = tbody.insertRow();
                    
                    // 添加点击事件
                    row.onclick = function() { showTradeDetail(i); };
                    row.style.cursor = 'pointer';
                    
                    // 序号
                    row.insertCell(0).textContent = i + 1;
                    
                    // 方向
                    const directionCell = row.insertCell(1);
                    if (trade.direction === 'buy') {
                        directionCell.innerHTML = '<span style="color: green;">做多</span>';
                    } else {
                        directionCell.innerHTML = '<span style="color: red;">做空</span>';
                    }
                    
                    // 开仓时间
                    const entryTimeCell = row.insertCell(2);
                    entryTimeCell.textContent = trade.entry_time ? trade.entry_time.substring(0, 16) : '-';
                    entryTimeCell.style.fontSize = '10px';
                    
                    // 开仓价格
                    row.insertCell(3).textContent = trade.entry_price ? trade.entry_price.toFixed(4) : '-';
                    
                    // 平仓时间
                    const exitTimeCell = row.insertCell(4);
                    exitTimeCell.textContent = trade.exit_time ? trade.exit_time.substring(0, 16) : '-';
                    exitTimeCell.style.fontSize = '10px';
                    
                    // 平仓价格
                    row.insertCell(5).textContent = trade.exit_price ? trade.exit_price.toFixed(4) : '-';
                    
                    // 仓位大小
                    row.insertCell(6).textContent = trade.size ? trade.size.toFixed(4) : '-';
                    
                    // 杠杆
                    row.insertCell(7).textContent = (trade.leverage || 1) + 'x';
                    
                    // === 新增：保证金占用 ===
                    const marginCell = row.insertCell(8);
                    const marginAmount = trade.required_margin || 0;
                    const marginRatio = trade.margin_ratio || 0;
                    marginCell.innerHTML = `
                        <div>${marginAmount.toFixed(0)} USDT</div>
                        <div class="margin-detail">${marginRatio.toFixed(1)}%</div>
                    `;
                    
                    // === 新增：手续费明细 ===
                    const commissionCell = row.insertCell(9);
                    const commission = trade.commission_costs || 0;
                    commissionCell.innerHTML = `
                        <div style="color: #d68910; font-weight: bold;">${commission.toFixed(2)} USDT</div>
                        <div class="cost-detail">开仓+平仓手续费</div>
                    `;
                    
                    // === 新增：资金费率 ===
                    const fundingCell = row.insertCell(10);
                    const funding = trade.funding_costs || 0;
                    fundingCell.innerHTML = `
                        <div style="color: #e67e22; font-weight: bold;">${funding.toFixed(2)} USDT</div>
                        <div class="cost-detail">持仓期间累计</div>
                    `;
                    
                    // === 新增：滑点成本 ===
                    const slippageCell = row.insertCell(11);
                    const slippage = trade.slippage_costs || 0;
                    slippageCell.innerHTML = `
                        <div style="color: #8e44ad; font-weight: bold;">${slippage.toFixed(2)} USDT</div>
                        <div class="cost-detail">买卖滑点</div>
                    `;
                    
                    // === 新增：毛利润 ===
                    const grossProfitCell = row.insertCell(12);
                    const grossProfit = trade.gross_profit || 0;
                    grossProfitCell.textContent = grossProfit.toFixed(2);
                    grossProfitCell.className = grossProfit >= 0 ? 'positive' : 'negative';
                    
                    // 净收益
                    const profitCell = row.insertCell(13);
                    const profit = trade.profit || 0;
                    profitCell.textContent = profit.toFixed(2);
                    profitCell.className = profit >= 0 ? 'positive' : 'negative';
                    profitCell.style.fontWeight = 'bold';
                    
                    // 收益率
                    const profitPctCell = row.insertCell(14);
                    const profitPct = trade.profit_pct || 0;
                    profitPctCell.textContent = profitPct.toFixed(2) + '%';
                    profitPctCell.className = profitPct >= 0 ? 'positive' : 'negative';
                    
                    // 信号强度
                    const strengthCell = row.insertCell(15);
                    const strength = trade.signal_strength || 0;
                    strengthCell.textContent = strength + '/5';
                    if (strength >= 4) {
                        strengthCell.style.color = 'green';
                    } else if (strength >= 2) {
                        strengthCell.style.color = 'orange';
                    } else {
                        strengthCell.style.color = 'red';
                    }
                    
                    // 平仓原因
                    row.insertCell(16).textContent = trade.reason || '未知';
                }
            }
            
            function showTradeDetail(tradeIndex) {
                const trade = allTrades[tradeIndex];
                if (!trade) return;
                
                const modal = document.getElementById('tradeModal');
                const content = document.getElementById('tradeDetailContent');
                
                // 格式化详细信息 - 增强版包含成本分析
                content.innerHTML = `
                    <h3>交易 #${tradeIndex + 1} - 详细成本分析</h3>
                    <div class="trade-detail-grid">
                        <div class="trade-detail-item">
                            <h4>基础信息</h4>
                            <p><strong>方向:</strong> ${trade.direction === 'buy' ? '🟢 做多' : '🔴 做空'}</p>
                            <p><strong>开仓时间:</strong> ${trade.entry_time || '-'}</p>
                            <p><strong>开仓价格:</strong> ${trade.entry_price ? trade.entry_price.toFixed(4) : '-'}</p>
                            <p><strong>平仓时间:</strong> ${trade.exit_time || '-'}</p>
                            <p><strong>平仓价格:</strong> ${trade.exit_price ? trade.exit_price.toFixed(4) : '-'}</p>
                            <p><strong>仓位大小:</strong> ${trade.size ? trade.size.toFixed(4) : '-'}</p>
                        </div>
                        <div class="trade-detail-item">
                            <h4>保证金信息</h4>
                            <p><strong>杠杆倍数:</strong> ${trade.leverage || 1}x</p>
                            <p><strong>仓位价值:</strong> ${(trade.position_value || 0).toFixed(2)} USDT</p>
                            <p><strong>保证金占用:</strong> ${(trade.required_margin || 0).toFixed(2)} USDT</p>
                            <p><strong>保证金比例:</strong> ${(trade.margin_ratio || 0).toFixed(1)}%</p>
                            <p><strong>保证金回报:</strong> ${(trade.return_on_margin || 0).toFixed(1)}%</p>
                        </div>
                    </div>
                    <div class="trade-detail-grid">
                        <div class="trade-detail-item">
                            <h4>成本明细</h4>
                            <p><strong>手续费:</strong> ${(trade.commission_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>资金费率:</strong> ${(trade.funding_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>滑点成本:</strong> ${(trade.slippage_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>总成本:</strong> ${(trade.total_costs || 0).toFixed(2)} USDT</p>
                            <p><strong>成本比例:</strong> ${(trade.cost_ratio || 0).toFixed(1)}%</p>
                        </div>
                        <div class="trade-detail-item">
                            <h4>收益分析</h4>
                            <p><strong>毛利润:</strong> ${(trade.gross_profit || 0).toFixed(2)} USDT</p>
                            <p><strong>净利润:</strong> ${(trade.profit || 0).toFixed(2)} USDT</p>
                            <p><strong>收益率:</strong> ${(trade.profit_pct || 0).toFixed(2)}%</p>
                            <p><strong>平仓原因:</strong> ${trade.reason || '-'}</p>
                        </div>
                    </div>
                    <div class="trade-detail-grid">
                        <div class="trade-detail-item">
                            <h4>信号信息</h4>
                            <p><strong>信号类型:</strong> ${trade.signal_type === 'hammer' ? '🔨 锤形线' : trade.signal_type === 'shooting_star' ? '⭐ 射击线' : trade.signal_type || '-'}</p>
                            <p><strong>信号强度:</strong> ${trade.signal_strength || '-'}/5</p>
                            <p><strong>置信度:</strong> ${trade.confidence_score ? trade.confidence_score.toFixed(2) : '-'}</p>
                            <p><strong>趋势对齐:</strong> ${trade.trend_alignment ? '✅ 是' : '❌ 否'}</p>
                        </div>
                        <div class="trade-detail-item">
                            <h4>效率指标</h4>
                            <p><strong>成本效率:</strong> ${((trade.total_costs || 0) / Math.abs(trade.gross_profit || 1) * 100).toFixed(1)}%</p>
                            <p><strong>时间效率:</strong> ${((trade.profit || 0) / Math.max(1, (new Date(trade.exit_time) - new Date(trade.entry_time)) / (1000 * 3600)) * 24).toFixed(2)} USDT/天</p>
                        </div>
                    </div>
                    <h4>📊 交易区间K线图</h4>
                `;
                
                // 生成K线图
                generateTradeKlineChart(trade);
                
                modal.style.display = 'block';
            }
            
            function generateTradeKlineChart(trade) {
                if (!klineData || klineData.length === 0) {
                    document.getElementById('klineChart').innerHTML = '<p style="text-align: center; padding: 50px;">暂无K线数据</p>';
                    return;
                }
                
                try {
                    // 找到开仓和平仓时间对应的K线索引
                    const entryTime = new Date(trade.entry_time);
                    const exitTime = new Date(trade.exit_time);
                    
                    let entryIndex = -1;
                    let exitIndex = -1;
                    
                    // 查找最接近的K线
                    for (let i = 0; i < klineData.length; i++) {
                        const klineTime = new Date(klineData[i].timestamp);
                        if (entryIndex === -1 && klineTime >= entryTime) {
                            entryIndex = i;
                        }
                        if (klineTime >= exitTime) {
                            exitIndex = i;
                            break;
                        }
                    }
                    
                    if (entryIndex === -1 || exitIndex === -1) {
                        document.getElementById('klineChart').innerHTML = '<p style="text-align: center; padding: 50px;">无法找到对应的K线数据</p>';
                        return;
                    }
                    
                    // 获取前30根和后30根K线
                    const startIndex = Math.max(0, entryIndex - 30);
                    const endIndex = Math.min(klineData.length - 1, exitIndex + 30);
                    
                    const chartData = klineData.slice(startIndex, endIndex + 1);
                    
                    // 准备Plotly数据
                    const x = chartData.map(d => d.timestamp);
                    const open = chartData.map(d => d.open);
                    const high = chartData.map(d => d.high);
                    const low = chartData.map(d => d.low);
                    const close = chartData.map(d => d.close);
                    const volume = chartData.map(d => d.volume);
                    
                    // 创建K线图
                    const traces = [
                        {
                            x: x,
                            open: open,
                            high: high,
                            low: low,
                            close: close,
                            type: 'candlestick',
                            name: 'K线',
                            increasing: {line: {color: '#26a69a'}},
                            decreasing: {line: {color: '#ef5350'}}
                        }
                    ];
                    
                    // 添加开仓和平仓标记
                    if (entryIndex >= startIndex && entryIndex <= endIndex) {
                        traces.push({
                            x: [trade.entry_time],
                            y: [trade.entry_price],
                            mode: 'markers',
                            marker: {
                                color: trade.direction === 'buy' ? 'green' : 'red',
                                size: 15,
                                symbol: trade.direction === 'buy' ? 'triangle-up' : 'triangle-down'
                            },
                            name: '开仓点',
                            showlegend: true
                        });
                    }
                    
                    if (exitIndex >= startIndex && exitIndex <= endIndex) {
                        traces.push({
                            x: [trade.exit_time],
                            y: [trade.exit_price],
                            mode: 'markers',
                            marker: {
                                color: trade.direction === 'buy' ? 'lightgreen' : 'lightcoral',
                                size: 15,
                                symbol: trade.direction === 'buy' ? 'triangle-down' : 'triangle-up'
                            },
                            name: '平仓点',
                            showlegend: true
                        });
                    }
                    
                    // 添加止损线
                    if (trade.stop_loss) {
                        traces.push({
                            x: [x[0], x[x.length-1]],
                            y: [trade.stop_loss, trade.stop_loss],
                            mode: 'lines',
                            line: {
                                color: 'red',
                                width: 1,
                                dash: 'dash'
                            },
                            name: '止损线',
                            showlegend: true
                        });
                    }
                    
                    // 添加止盈线
                    if (trade.take_profit_1) {
                        traces.push({
                            x: [x[0], x[x.length-1]],
                            y: [trade.take_profit_1, trade.take_profit_1],
                            mode: 'lines',
                            line: {
                                color: 'green',
                                width: 1,
                                dash: 'dot'
                            },
                            name: '止盈1',
                            showlegend: true
                        });
                    }
                    
                    const layout = {
                        title: `交易区间K线图 (${trade.direction === 'buy' ? '做多' : '做空'}) - 成本: ${(trade.total_costs || 0).toFixed(2)} USDT`,
                        xaxis: {
                            title: '时间',
                            rangeslider: {visible: false}
                        },
                        yaxis: {
                            title: '价格'
                        },
                        showlegend: true,
                        height: 450
                    };
                    
                    Plotly.newPlot('klineChart', traces, layout);
                    
                } catch (error) {
                    console.error('生成K线图失败:', error);
                    document.getElementById('klineChart').innerHTML = '<p style="text-align: center; padding: 50px;">K线图生成失败</p>';
                }
            }
            
            function closeTradeDetail() {
                document.getElementById('tradeModal').style.display = 'none';
            }
            
            // 点击弹窗外部关闭
            window.onclick = function(event) {
                const modal = document.getElementById('tradeModal');
                if (event.target === modal) {
                    modal.style.display = 'none';
                }
            }
            
            // ESC键关闭弹窗
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Escape') {
                    closeTradeDetail();
                }
            });
            
            // 翻页函数
            function updatePagination() {
                totalPages = Math.ceil(Math.max(1, allTrades.length) / pageSize);
                document.getElementById('currentPage').textContent = currentPage;
                document.getElementById('currentPage2').textContent = currentPage;
                document.getElementById('totalPages').textContent = totalPages;
                document.getElementById('totalPages2').textContent = totalPages;
                
                // 更新按钮状态
                const prevButtons = document.querySelectorAll('.pagination button:nth-child(2)');
                const nextButtons = document.querySelectorAll('.pagination button:nth-child(4)');
                
                prevButtons.forEach(btn => btn.disabled = currentPage <= 1);
                nextButtons.forEach(btn => btn.disabled = currentPage >= totalPages);
            }
            
            function firstPage() {
                currentPage = 1;
                updatePagination();
                renderTrades();
            }
            
            function lastPage() {
                currentPage = totalPages;
                updatePagination();
                renderTrades();
            }
            
            function prevPage() {
                if (currentPage > 1) {
                    currentPage--;
                    updatePagination();
                    renderTrades();
                }
            }
            
            function nextPage() {
                if (currentPage < totalPages) {
                    currentPage++;
                    updatePagination();
                    renderTrades();
                }
            }
            
            function gotoPage() {
                const input = document.getElementById('gotoPage');
                const page = parseInt(input.value);
                if (page >= 1 && page <= totalPages) {
                    currentPage = page;
                    updatePagination();
                    renderTrades();
                    input.value = '';
                } else {
                    alert(`请输入有效的页码 (1-${totalPages})`);
                }
            }
            
            function changePageSize() {
                pageSize = parseInt(document.getElementById('pageSize').value);
                currentPage = 1;
                updatePagination();
                renderTrades();
            }
            
            function showTab(tabName) {
                // 隐藏所有标签页内容
                const contents = document.querySelectorAll('.tab-content');
                contents.forEach(content => content.classList.remove('active'));
                
                // 移除所有标签的active类
                const tabs = document.querySelectorAll('.tab');
                tabs.forEach(tab => tab.classList.remove('active'));
                
                // 显示选中的标签页
                document.getElementById(tabName).classList.add('active');
                event.target.classList.add('active');
            }
        </script>
    </body>
    </html>
        """
        
        template = Template(template_str)
        return template.render(
            data=data,
            charts=charts,
            trades_json=json.dumps(trades_for_json, ensure_ascii=False),
            kline_json=json.dumps(kline_data_for_js, ensure_ascii=False) if kline_data_for_js else '[]',
            report_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def _generate_multi_symbol_html(self, data: Dict[str, Any], 
                                  charts: Dict[str, str]) -> str:
        """生成多币种HTML报告"""
        
        template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>多币种Pinbar策略回测报告</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                color: #333;
            }
            
            .container { 
                max-width: 1400px; 
                margin: 0 auto; 
                background: white; 
                padding: 30px; 
                border-radius: 15px; 
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }
            
            .header { 
                text-align: center; 
                margin-bottom: 40px;
                background: #2c3e50;
                color: white;
                padding: 40px 30px;
                border-radius: 15px;
                margin: -30px -30px 40px -30px;
            }
            
            .header h1 {
                margin: 0;
                font-size: 2.5em;
                font-weight: 300;
                text-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }
            
            /* 汇总指标网格 */
            .summary {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }
            
            .metric-card {
                background: linear-gradient(135deg, #fff 0%, #f8f9fa 100%);
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                border-left: 5px solid #3498db;
                transition: transform 0.3s ease;
            }
            
            .metric-card:hover {
                transform: translateY(-5px);
            }
            
            .metric-value {
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 8px;
            }
            
            .metric-label {
                color: #666;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            
            .positive { color: #27ae60; }
            .negative { color: #e74c3c; }
            .neutral { color: #7f8c8d; }
            
            /* 币种表格 */
            .symbols-table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            
            .symbols-table th {
                background: #2c3e50;
                color: white;
                padding: 15px 10px;
                text-align: center;
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .symbols-table td {
                padding: 12px 8px;
                text-align: center;
                border-bottom: 1px solid #eee;
                font-size: 13px;
            }
            
            .symbols-table tr:hover {
                background-color: #f8f9fa;
            }
            
            /* 图表容器 */
            .chart-container {
                margin: 40px 0;
                padding: 30px;
                background: white;
                border-radius: 15px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            
            .chart-title {
                font-size: 1.5em;
                font-weight: bold;
                text-align: center;
                margin-bottom: 25px;
                color: #2c3e50;
            }
            
            /* 标签页 */
            .tabs {
                display: flex;
                margin-bottom: 20px;
                border-bottom: 2px solid #e9ecef;
                overflow-x: auto;
            }
            
            .tab {
                padding: 12px 25px;
                cursor: pointer;
                border-bottom: 3px solid transparent;
                white-space: nowrap;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            
            .tab:hover {
                background: #f8f9fa;
            }
            
            .tab.active {
                border-bottom-color: #3498db;
                background: #f8f9fa;
                color: #3498db;
            }
            
            .tab-content {
                display: none;
            }
            
            .tab-content.active {
                display: block;
            }
            
            /* 排名标识 */
            .rank-1 { background: #f39c12; color: white; padding: 2px 6px; border-radius: 12px; }
            .rank-2 { background: #95a5a6; color: white; padding: 2px 6px; border-radius: 12px; }
            .rank-3 { background: #cd853f; color: white; padding: 2px 6px; border-radius: 12px; }
            
            /* 信号质量标识 */
            .signal-excellent { color: #27ae60; font-weight: bold; }
            .signal-good { color: #f39c12; font-weight: bold; }
            .signal-poor { color: #e74c3c; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- 头部 -->
            <div class="header">
                <h1>🎯 多币种Pinbar策略回测报告</h1>
                <p>生成时间: {{ report_time }}</p>
                <p>回测币种: {{ data.summary.total_symbols }} 个</p>
            </div>
            
            <!-- 汇总指标 -->
            <div class="summary">
                <div class="metric-card">
                    <div class="metric-value {{ 'positive' if data.summary.total_return > 0 else 'negative' }}">
                        {{ "{:.2f}".format(data.summary.total_return) }}%
                    </div>
                    <div class="metric-label">总体收益率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ data.summary.total_symbols }}</div>
                    <div class="metric-label">回测币种数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ data.summary.total_trades }}</div>
                    <div class="metric-label">总交易次数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ data.summary.total_signals }}</div>
                    <div class="metric-label">总信号数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ "{:.1f}".format(data.summary.avg_win_rate) }}%</div>
                    <div class="metric-label">平均胜率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ "{:.1f}".format(data.summary.avg_signal_execution_rate) }}%</div>
                    <div class="metric-label">平均信号执行率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value {{ 'positive' if data.summary.best_return > 0 else 'negative' }}">
                        {{ data.summary.best_symbol }}: {{ "{:.2f}".format(data.summary.best_return) }}%
                    </div>
                    <div class="metric-label">最佳表现</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ "{:.1f}".format(data.summary.avg_signal_success_rate) }}%</div>
                    <div class="metric-label">平均信号成功率</div>
                </div>
            </div>
            
            <!-- 图表展示 -->
            <div class="tabs">
                <div class="tab active" onclick="showTab('returns_comparison')">收益率对比</div>
                <div class="tab" onclick="showTab('risk_return_scatter')">风险收益分析</div>
                {% if 'signal_quality' in charts %}<div class="tab" onclick="showTab('signal_quality')">信号质量分析</div>{% endif %}
            </div>
            
            <div id="returns_comparison" class="tab-content active chart-container">
                <div class="chart-title">📊 各币种收益率对比</div>
                {{ charts.returns_comparison|safe }}
            </div>
            
            <div id="risk_return_scatter" class="tab-content chart-container">
                <div class="chart-title">📈 风险收益散点图</div>
                {{ charts.risk_return_scatter|safe }}
            </div>
            
            {% if 'signal_quality' in charts %}
            <div id="signal_quality" class="tab-content chart-container">
                <div class="chart-title">🎯 信号质量分析</div>
                {{ charts.signal_quality|safe }}
            </div>
            {% endif %}
            
            <!-- 币种详细表格 -->
            <div class="chart-container">
                <h2>📊 各币种详细表现</h2>
                <table class="symbols-table">
                    <thead>
                        <tr>
                            <th>排名</th>
                            <th>币种</th>
                            <th>收益率</th>
                            <th>交易次数</th>
                            <th>胜率</th>
                            <th>盈亏比</th>
                            <th>最大回撤</th>
                            <th>夏普比率</th>
                            <th>总信号数</th>
                            <th>执行信号数</th>
                            <th>信号执行率</th>
                            <th>信号成功率</th>
                            <th>平均信号强度</th>
                            <th>平均置信度</th>
                            <th>趋势对齐率</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for symbol in data.symbol_stats %}
                        <tr>
                            <td>
                                {% if loop.index == 1 %}
                                    <span class="rank-1">🥇</span>
                                {% elif loop.index == 2 %}
                                    <span class="rank-2">🥈</span>
                                {% elif loop.index == 3 %}
                                    <span class="rank-3">🥉</span>
                                {% else %}
                                    {{ loop.index }}
                                {% endif %}
                            </td>
                            <td><strong>{{ symbol.symbol }}</strong></td>
                            <td>
                                {% if symbol.total_return > 0 %}
                                    <span class="positive">+{{ "{:.2f}".format(symbol.total_return) }}%</span>
                                {% else %}
                                    <span class="negative">{{ "{:.2f}".format(symbol.total_return) }}%</span>
                                {% endif %}
                            </td>
                            <td>{{ symbol.total_trades }}</td>
                            <td>{{ "{:.1f}".format(symbol.win_rate) }}%</td>
                            <td>{{ "{:.2f}".format(symbol.profit_factor) }}</td>
                            <td>{{ "{:.2f}".format(symbol.max_drawdown) }}%</td>
                            <td>{{ "{:.3f}".format(symbol.sharpe_ratio) }}</td>
                            <td>{{ symbol.total_signals }}</td>
                            <td>{{ symbol.executed_signals }}</td>
                            <td>{{ "{:.1f}".format(symbol.signal_execution_rate) }}%</td>
                            <td>
                                {% set success_rate = symbol.signal_success_rate %}
                                {% if success_rate >= 70 %}
                                    <span class="signal-excellent">{{ "{:.1f}".format(success_rate) }}%</span>
                                {% elif success_rate >= 50 %}
                                    <span class="signal-good">{{ "{:.1f}".format(success_rate) }}%</span>
                                {% else %}
                                    <span class="signal-poor">{{ "{:.1f}".format(success_rate) }}%</span>
                                {% endif %}
                            </td>
                            <td>{{ "{:.1f}".format(symbol.avg_signal_strength) }}</td>
                            <td>{{ "{:.2f}".format(symbol.avg_confidence_score) }}</td>
                            <td>{{ "{:.1f}".format(symbol.trend_alignment_rate) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <!-- 策略配置信息 -->
            <div class="chart-container">
                <h2>⚙️ 策略配置</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                    {% for key, value in data.config.items() %}
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db;">
                        <strong>{{ key }}:</strong> {{ value }}
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <script>
            function showTab(tabName) {
                // 隐藏所有标签页内容
                const contents = document.querySelectorAll('.tab-content');
                contents.forEach(content => content.classList.remove('active'));
                
                // 移除所有标签的active类
                const tabs = document.querySelectorAll('.tab');
                tabs.forEach(tab => tab.classList.remove('active'));
                
                // 显示选中的标签页
                document.getElementById(tabName).classList.add('active');
                event.target.classList.add('active');
            }
        </script>
    </body>
    </html>
        """
        
        template = Template(template_str)
        return template.render(
            data=data,
            charts=charts,
            report_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

    def generate_ab_test_report(self, comparison_data: Dict[str, Any], 
                          data: pd.DataFrame, output_file: str = None) -> str:
        """生成A/B测试对比报告"""
        print("生成A/B测试对比报告...")
        
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
        
        # 生成HTML报告
        html_content = self._generate_ab_test_html(
            comparison_metrics, original_results, trend_results,
            symbol, interval, improvement_score, conclusion, conclusion_class
        )
        
        # 保存文件
        if output_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"ab_test_report_{symbol}_{interval}_{timestamp}.html"
        
        filepath = os.path.join('reports', output_file)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ A/B测试对比报告已保存: {filepath}")
        return filepath

    def _generate_ab_test_html(self, comparison_metrics: List[Dict], 
                            original_results: Dict, trend_results: Dict,
                            symbol: str, interval: str, improvement_score: float,
                            conclusion: str, conclusion_class: str) -> str:
        """生成A/B测试HTML报告"""
        
        template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>A/B测试对比报告 - {{symbol}} {{interval}}</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                min-height: 100vh;
            }
            
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white; 
                padding: 30px; 
                border-radius: 20px; 
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            
            .header { 
                text-align: center; 
                margin-bottom: 40px;
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: white;
                padding: 40px 30px;
                border-radius: 15px;
                margin: -30px -30px 40px -30px;
            }
            
            .header h1 {
                margin: 0;
                font-size: 2.5em;
                font-weight: 300;
                text-shadow: 0 2px 10px rgba(0,0,0,0.5);
            }
            
            .test-info {
                font-size: 1.1em;
                margin-top: 15px;
                opacity: 0.9;
            }
            
            /* 对比卡片 */
            .vs-container {
                display: grid;
                grid-template-columns: 1fr auto 1fr;
                gap: 30px;
                margin: 40px 0;
                align-items: center;
            }
            
            .strategy-card {
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border-radius: 15px;
                padding: 30px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }
            
            .strategy-card:hover {
                transform: translateY(-5px);
            }
            
            .strategy-card.winner {
                background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
                border: 2px solid #28a745;
            }
            
            .strategy-title {
                font-size: 1.5em;
                font-weight: bold;
                margin-bottom: 20px;
                color: #2c3e50;
            }
            
            .strategy-badge {
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.9em;
                font-weight: bold;
                margin-bottom: 15px;
            }
            
            .original-badge {
                background: #6c757d;
                color: white;
            }
            
            .trend-badge {
                background: #007bff;
                color: white;
            }
            
            .winner-badge {
                background: #28a745;
                color: white;
            }
            
            .vs-divider {
                font-size: 3em;
                font-weight: bold;
                color: #6c757d;
                text-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }
            
            /* 对比表格 */
            .comparison-table {
                width: 100%;
                border-collapse: collapse;
                margin: 30px 0;
                background: white;
                border-radius: 15px;
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            
            .comparison-table th {
                background: linear-gradient(135deg, #495057 0%, #6c757d 100%);
                color: white;
                padding: 20px 15px;
                text-align: center;
                font-weight: 600;
                font-size: 1.1em;
            }
            
            .comparison-table td {
                padding: 15px;
                text-align: center;
                border-bottom: 1px solid #dee2e6;
                font-size: 1em;
            }
            
            .comparison-table tr:hover {
                background-color: #f8f9fa;
            }
            
            .metric-name {
                font-weight: bold;
                color: #495057;
                text-align: left !important;
            }
            
            .improvement-positive {
                color: #28a745;
                font-weight: bold;
            }
            
            .improvement-negative {
                color: #dc3545;
                font-weight: bold;
            }
            
            .improvement-neutral {
                color: #6c757d;
            }
            
            /* 结论区域 */
            .conclusion {
                background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
                border-radius: 15px;
                padding: 30px;
                margin: 40px 0;
                text-align: center;
                box-shadow: 0 10px 30px rgba(33, 150, 243, 0.2);
            }
            
            .conclusion.excellent {
                background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
                border-left: 5px solid #28a745;
            }
            
            .conclusion.good {
                background: linear-gradient(135deg, #cce7ff 0%, #b3d9ff 100%);
                border-left: 5px solid #007bff;
            }
            
            .conclusion.neutral {
                background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
                border-left: 5px solid #ffc107;
            }
            
            .conclusion.poor {
                background: linear-gradient(135deg, #f8d7da 0%, #f1aeb5 100%);
                border-left: 5px solid #dc3545;
            }
            
            .conclusion h2 {
                margin-top: 0;
                font-size: 1.8em;
                margin-bottom: 15px;
            }
            
            .improvement-score {
                font-size: 3em;
                font-weight: bold;
                margin: 20px 0;
                text-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }
            
            /* 详细对比图表 */
            .chart-container {
                margin: 40px 0;
                padding: 30px;
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            
            .chart-title {
                font-size: 1.5em;
                font-weight: bold;
                text-align: center;
                margin-bottom: 25px;
                color: #2c3e50;
            }
            
            /* 特殊指标展示 */
            .special-metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }
            
            .metric-card {
                background: linear-gradient(135deg, #fff 0%, #f8f9fa 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                border-left: 4px solid #007bff;
            }
            
            .metric-value {
                font-size: 1.8em;
                font-weight: bold;
                margin-bottom: 8px;
            }
            
            .metric-label {
                color: #666;
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            
            /* 响应式设计 */
            @media (max-width: 768px) {
                .vs-container {
                    grid-template-columns: 1fr;
                    gap: 20px;
                }
                
                .vs-divider {
                    transform: rotate(90deg);
                    font-size: 2em;
                }
                
                .comparison-table {
                    font-size: 0.8em;
                }
                
                .comparison-table th,
                .comparison-table td {
                    padding: 10px 5px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- 头部 -->
            <div class="header">
                <h1>🆚 A/B测试对比报告</h1>
                <div class="test-info">
                    交易对: {{symbol}} | 周期: {{interval}} | 生成时间: {{report_time}}
                </div>
            </div>
            
            <!-- 策略对比卡片 -->
            <div class="vs-container">
                <div class="strategy-card">
                    <div class="strategy-badge original-badge">原版策略</div>
                    <div class="strategy-title">经典Pinbar策略</div>
                    <div class="metric-card">
                        <div class="metric-value">{{original_results.total_return | round(2)}}%</div>
                        <div class="metric-label">总收益率</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{original_results.total_trades}}</div>
                        <div class="metric-label">交易次数</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{original_results.win_rate | round(1)}}%</div>
                        <div class="metric-label">胜率</div>
                    </div>
                </div>
                
                <div class="vs-divider">VS</div>
                
                <div class="strategy-card {% if improvement_score >= 50 %}winner{% endif %}">
                    <div class="strategy-badge {% if improvement_score >= 50 %}winner-badge{% else %}trend-badge{% endif %}">趋势跟踪版</div>
                    <div class="strategy-title">增强Pinbar策略</div>
                    <div class="metric-card">
                        <div class="metric-value">{{trend_results.total_return | round(2)}}%</div>
                        <div class="metric-label">总收益率</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{trend_results.total_trades}}</div>
                        <div class="metric-label">交易次数</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{trend_results.win_rate | round(1)}}%</div>
                        <div class="metric-label">胜率</div>
                    </div>
                </div>
            </div>
            
            <!-- 详细对比表格 -->
            <div class="chart-container">
                <div class="chart-title">📊 详细指标对比</div>
                <table class="comparison-table">
                    <thead>
                        <tr>
                            <th>指标</th>
                            <th>原版策略</th>
                            <th>趋势跟踪版</th>
                            <th>改进幅度</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for metric in comparison_metrics %}
                        <tr>
                            <td class="metric-name">{{metric.metric}}</td>
                            <td>{{metric.original}}</td>
                            <td>{{metric.trend}}</td>
                            <td class="{% if metric.better %}improvement-positive{% elif metric.improvement == 'N/A' %}improvement-neutral{% else %}improvement-negative{% endif %}">
                                {{metric.improvement}}
                                {% if metric.better %}📈{% elif metric.improvement != 'N/A' %}📉{% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <!-- 趋势跟踪特有指标 -->
            <div class="chart-container">
                <div class="chart-title">🎯 趋势跟踪特有优势</div>
                <div class="special-metrics">
                    <div class="metric-card">
                        <div class="metric-value">{{trend_results.get('trend_tracking_trades', 0)}}</div>
                        <div class="metric-label">趋势跟踪交易数</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{trend_results.get('avg_max_profit_seen', 0) | round(2)}}%</div>
                        <div class="metric-label">平均最大浮盈</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{trend_results.get('partial_close_rate', 0) | round(1)}}%</div>
                        <div class="metric-label">部分平仓率</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{trend_results.get('signal_stats', {}).get('signal_execution_rate', 0) | round(1)}}%</div>
                        <div class="metric-label">信号执行率</div>
                    </div>
                </div>
            </div>
            
            <!-- 结论 -->
            <div class="conclusion {{conclusion_class}}">
                <h2>📋 测试结论</h2>
                <div class="improvement-score">{{improvement_score | round(1)}}%</div>
                <p style="font-size: 1.1em; margin-bottom: 0;">综合改进指标</p>
                <div style="font-size: 1.3em; font-weight: bold; margin: 20px 0;">
                    {{conclusion}}
                </div>
                
                <div style="text-align: left; margin-top: 30px; background: rgba(255,255,255,0.5); padding: 20px; border-radius: 10px;">
                    <h4>📈 改进分析：</h4>
                    <ul style="list-style: none; padding: 0;">
                        {% for metric in comparison_metrics %}
                        <li style="margin: 10px 0; padding: 8px; {% if metric.better %}background: rgba(40, 167, 69, 0.1);{% else %}background: rgba(220, 53, 69, 0.1);{% endif %} border-radius: 5px;">
                            <strong>{{metric.metric}}:</strong> 
                            {% if metric.better %}
                                <span style="color: #28a745;">✅ 改进 {{metric.improvement}}</span>
                            {% else %}
                                <span style="color: #dc3545;">❌ 下降 {{metric.improvement}}</span>
                            {% endif %}
                        </li>
                        {% endfor %}
                    </ul>
                </div>
                
                {% if improvement_score >= 70 %}
                <div style="margin-top: 30px; padding: 20px; background: rgba(40, 167, 69, 0.1); border-radius: 10px;">
                    <h4>🎉 建议：</h4>
                    <p>趋势跟踪版策略表现卓越！建议：</p>
                    <ul>
                        <li>正式采用趋势跟踪版策略</li>
                        <li>进一步优化趋势识别参数</li>
                        <li>扩大测试币种范围验证稳定性</li>
                    </ul>
                </div>
                {% elif improvement_score >= 50 %}
                <div style="margin-top: 30px; padding: 20px; background: rgba(0, 123, 255, 0.1); border-radius: 10px;">
                    <h4>✅ 建议：</h4>
                    <p>趋势跟踪版整体更优，建议：</p>
                    <ul>
                        <li>采用趋势跟踪版作为主策略</li>
                        <li>针对弱势指标进行优化</li>
                        <li>在不同市场环境下进一步测试</li>
                    </ul>
                </div>
                {% else %}
                <div style="margin-top: 30px; padding: 20px; background: rgba(255, 193, 7, 0.1); border-radius: 10px;">
                    <h4>⚠️ 建议：</h4>
                    <p>需要进一步优化，建议：</p>
                    <ul>
                        <li>分析趋势跟踪策略的弱点</li>
                        <li>调整策略参数</li>
                        <li>在更多数据集上测试</li>
                        <li>考虑混合策略方案</li>
                    </ul>
                </div>
                {% endif %}
            </div>
            
            <!-- 测试环境信息 -->
            <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-radius: 10px; font-size: 0.9em; color: #666;">
                <h4>🔬 测试环境：</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div><strong>测试币种:</strong> {{symbol}}</div>
                    <div><strong>时间周期:</strong> {{interval}}</div>
                    <div><strong>测试类型:</strong> A/B对比测试</div>
                    <div><strong>生成时间:</strong> {{report_time}}</div>
                </div>
            </div>
        </div>
        
        <script>
            // 添加一些交互效果
            document.addEventListener('DOMContentLoaded', function() {
                // 为胜者卡片添加动画
                const winnerCard = document.querySelector('.strategy-card.winner');
                if (winnerCard) {
                    setTimeout(() => {
                        winnerCard.style.transform = 'scale(1.02)';
                        winnerCard.style.transition = 'all 0.5s ease';
                    }, 1000);
                }
                
                // 表格行悬停效果增强
                const tableRows = document.querySelectorAll('.comparison-table tr');
                tableRows.forEach(row => {
                    row.addEventListener('mouseenter', function() {
                        this.style.background = 'linear-gradient(135deg, #e3f2fd 0%, #f8f9fa 100%)';
                    });
                    row.addEventListener('mouseleave', function() {
                        this.style.background = '';
                    });
                });
            });
        </script>
    </body>
    </html>
        """
        
        # 使用Jinja2模板渲染
        from jinja2 import Template
        template = Template(template_str)
        return template.render(
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
    def open_report_in_browser(self, filepath: str):
        """在浏览器中打开报告"""
        try:
            abs_path = os.path.abspath(filepath)
            webbrowser.open(f'file://{abs_path}', new=2)
            print(f"✅ 报告已在浏览器中打开: {filepath}")
        except Exception as e:
            print(f"❌ 打开浏览器失败: {e}")

if __name__ == "__main__":
    print("增强版报告生成器完成 - 详细成本分析版")
    print("主要增强:")
    print("1. ✅ 页面顶部显示累计总手续费、资金费率、总成本")
    print("2. ✅ 新增成本分析区域 - 显示各项成本占比")
    print("3. ✅ 新增保证金分析区域 - 显示保证金使用效率")
    print("4. ✅ 交易明细表格增加成本列：保证金占用、手续费、资金费率、滑点")
    print("5. ✅ 交易详情弹窗增加详细成本分析")
    print("6. ✅ K线图标题显示交易成本")
    print("7. ✅ 完整的成本效率分析")