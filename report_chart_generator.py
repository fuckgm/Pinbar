#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告图表生成器
负责生成回测报告中的各种图表
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from typing import Dict, List, Any, Optional
from report_data_processor import ReportDataProcessor

class ReportChartGenerator:
    """报告图表生成器"""
    
    def __init__(self):
        self.data_processor = ReportDataProcessor()
    
    def create_enhanced_backtest_charts(self, data: pd.DataFrame, 
                                      results: Dict[str, Any]) -> Dict[str, str]:
        """创建增强版回测图表"""
        charts = {}
        
        # 1. 增强版价格走势图
        fig_price = make_subplots(
            rows=3, cols=1,
            subplot_titles=['价格走势与交易点', 'RSI指标', '成交量'],
            vertical_spacing=0.1,
            row_heights=[0.6, 0.2, 0.2]
        )
        
        # K线图
        if 'timestamp' in data.columns:
            fig_price.add_trace(go.Candlestick(
                x=data['timestamp'],
                open=data['open'],
                high=data['high'],
                low=data['low'],
                close=data['close'],
                name='价格'
            ), row=1, col=1)
            
            # 移动平均线
            if 'sma_fast' in data.columns:
                fig_price.add_trace(go.Scatter(
                    x=data['timestamp'],
                    y=data['sma_fast'],
                    name='快线',
                    line=dict(color='blue', width=1)
                ), row=1, col=1)
            
            if 'sma_slow' in data.columns:
                fig_price.add_trace(go.Scatter(
                    x=data['timestamp'],
                    y=data['sma_slow'],
                    name='慢线',
                    line=dict(color='orange', width=1)
                ), row=1, col=1)
            
            # 增强版交易点标记
            trades = results.get('trades', [])
            if trades:
                long_entries = []
                long_exits = []
                short_entries = []
                short_exits = []
                trade_info = []  # 用于点击交互
                
                for i, trade in enumerate(trades):
                    trade_info.append({
                        'trade_id': trade.get('trade_id', f'Trade_{i+1}'),
                        'direction': trade.get('direction', 'unknown'),
                        'profit': trade.get('profit', 0),
                        'entry_time': trade.get('entry_time'),
                        'exit_time': trade.get('exit_time')
                    })
                    
                    if trade.get('direction') == 'buy':
                        if 'entry_time' in trade and 'entry_price' in trade:
                            long_entries.append((trade['entry_time'], trade['entry_price'], i))
                        if 'exit_time' in trade and 'exit_price' in trade:
                            long_exits.append((trade['exit_time'], trade['exit_price'], i))
                    else:
                        if 'entry_time' in trade and 'entry_price' in trade:
                            short_entries.append((trade['entry_time'], trade['entry_price'], i))
                        if 'exit_time' in trade and 'exit_price' in trade:
                            short_exits.append((trade['exit_time'], trade['exit_price'], i))
                
                # 做多开仓（绿色向上三角）
                if long_entries:
                    times, prices, indices = zip(*long_entries)
                    fig_price.add_trace(go.Scatter(
                        x=times,
                        y=prices,
                        mode='markers',
                        marker=dict(symbol='triangle-up', size=12, color='green'),
                        name='做多开仓',
                        customdata=indices,
                        hovertemplate='<b>做多开仓</b><br>' +
                                    '时间: %{x}<br>' +
                                    '价格: %{y}<br>' +
                                    '交易ID: %{customdata}<extra></extra>'
                    ), row=1, col=1)
                
                # 做多平仓（绿色向下三角）
                if long_exits:
                    times, prices, indices = zip(*long_exits)
                    fig_price.add_trace(go.Scatter(
                        x=times,
                        y=prices,
                        mode='markers',
                        marker=dict(symbol='triangle-down', size=12, color='lightgreen'),
                        name='做多平仓',
                        customdata=indices,
                        hovertemplate='<b>做多平仓</b><br>' +
                                    '时间: %{x}<br>' +
                                    '价格: %{y}<br>' +
                                    '交易ID: %{customdata}<extra></extra>'
                    ), row=1, col=1)
                
                # 做空开仓（红色向下三角）
                if short_entries:
                    times, prices, indices = zip(*short_entries)
                    fig_price.add_trace(go.Scatter(
                        x=times,
                        y=prices,
                        mode='markers',
                        marker=dict(symbol='triangle-down', size=12, color='red'),
                        name='做空开仓',
                        customdata=indices,
                        hovertemplate='<b>做空开仓</b><br>' +
                                    '时间: %{x}<br>' +
                                    '价格: %{y}<br>' +
                                    '交易ID: %{customdata}<extra></extra>'
                    ), row=1, col=1)
                
                # 做空平仓（红色向上三角）
                if short_exits:
                    times, prices, indices = zip(*short_exits)
                    fig_price.add_trace(go.Scatter(
                        x=times,
                        y=prices,
                        mode='markers',
                        marker=dict(symbol='triangle-up', size=12, color='lightcoral'),
                        name='做空平仓',
                        customdata=indices,
                        hovertemplate='<b>做空平仓</b><br>' +
                                    '时间: %{x}<br>' +
                                    '价格: %{y}<br>' +
                                    '交易ID: %{customdata}<extra></extra>'
                    ), row=1, col=1)
            
            # RSI指标
            if 'rsi' in data.columns:
                fig_price.add_trace(go.Scatter(
                    x=data['timestamp'],
                    y=data['rsi'],
                    name='RSI',
                    line=dict(color='purple', width=2)
                ), row=2, col=1)
                
                # RSI超买超卖线
                fig_price.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig_price.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
            
            # 成交量
            fig_price.add_trace(go.Bar(
                x=data['timestamp'],
                y=data['volume'],
                name='成交量',
                marker_color='lightblue'
            ), row=3, col=1)
        
        fig_price.update_layout(
            title='增强版价格走势分析',
            height=800,
            showlegend=True
        )
        
        charts['enhanced_price'] = fig_price.to_html(include_plotlyjs='cdn', div_id='enhanced-price-chart')
        
        # 2. 收益分析图表
        trades = results.get('trades', [])
        if trades:
            # 累计收益曲线
            cumulative_pnl = []
            cumulative_sum = 0
            trade_numbers = []
            
            for i, trade in enumerate(trades, 1):
                cumulative_sum += trade.get('profit', 0)
                cumulative_pnl.append(cumulative_sum)
                trade_numbers.append(i)
            
            fig_pnl = make_subplots(
                rows=2, cols=2,
                subplot_titles=['累计收益曲线', '单笔交易收益分布', '保证金占用分布', '月度收益统计'],
                specs=[[{'secondary_y': False}, {'type': 'histogram'}],
                       [{'type': 'pie'}, {'type': 'bar'}]]
            )
            
            # 累计收益曲线
            colors = ['green' if pnl >= 0 else 'red' for pnl in cumulative_pnl]
            fig_pnl.add_trace(go.Scatter(
                x=trade_numbers,
                y=cumulative_pnl,
                mode='lines+markers',
                name='累计收益',
                line=dict(color='blue', width=2),
                marker=dict(color=colors, size=6)
            ), row=1, col=1)
            
            # 单笔交易收益分布
            profits = [t.get('profit', 0) for t in trades]
            fig_pnl.add_trace(go.Histogram(
                x=profits,
                nbinsx=20,
                name='收益分布',
                marker_color='lightblue'
            ), row=1, col=2)
            
            # 保证金占用分布（模拟数据）
            margin_ratios = [np.random.uniform(5, 25) for _ in trades]  # 模拟保证金占用
            bins = [0, 5, 10, 15, 20, 25, 100]
            labels = ['0-5%', '5-10%', '10-15%', '15-20%', '20-25%', '>25%']
            margin_groups = pd.cut(margin_ratios, bins=bins, labels=labels, include_lowest=True)
            margin_counts = margin_groups.value_counts()
            
            fig_pnl.add_trace(go.Pie(
                labels=margin_counts.index,
                values=margin_counts.values,
                name='保证金占用'
            ), row=2, col=1)
            
            # 月度收益统计
            monthly_data = self.data_processor._calculate_enhanced_monthly_returns(trades)
            if monthly_data:
                months = [m['month'] for m in monthly_data]
                profits = [m['profit'] for m in monthly_data]
                
                fig_pnl.add_trace(go.Bar(
                    x=months,
                    y=profits,
                    name='月度收益',
                    marker_color=['green' if p >= 0 else 'red' for p in profits]
                ), row=2, col=2)
            
            fig_pnl.update_layout(
                title='收益与风险分析',
                height=600,
                showlegend=False
            )
            
            charts['pnl_analysis'] = fig_pnl.to_html(include_plotlyjs='cdn', div_id='pnl-analysis-chart')
        
        return charts
    
    def create_multi_symbol_charts(self, multi_results: Dict[str, Dict]) -> Dict[str, str]:
        """创建多币种图表"""
        charts = {}
        
        # 准备数据
        symbols = list(multi_results.keys())
        returns = [multi_results[symbol]['results']['total_return'] for symbol in symbols]
        trades = [multi_results[symbol]['results']['total_trades'] for symbol in symbols]
        win_rates = [multi_results[symbol]['results']['win_rate'] for symbol in symbols]
        
        # 1. 收益率对比图
        fig_returns = go.Figure()
        
        colors = ['green' if r >= 0 else 'red' for r in returns]
        
        fig_returns.add_trace(go.Bar(
            x=symbols,
            y=returns,
            name='收益率',
            marker_color=colors,
            text=[f'{r:.2f}%' for r in returns],
            textposition='outside'
        ))
        
        fig_returns.update_layout(
            title='各币种收益率对比',
            xaxis_title='币种',
            yaxis_title='收益率 (%)',
            height=400,
            showlegend=False
        )
        
        charts['returns_comparison'] = fig_returns.to_html(include_plotlyjs='cdn')
        
        # 2. 风险收益散点图
        fig_scatter = go.Figure()
        
        drawdowns = [multi_results[symbol]['results']['max_drawdown'] * 100 for symbol in symbols]
        
        fig_scatter.add_trace(go.Scatter(
            x=drawdowns,
            y=returns,
            mode='markers+text',
            text=symbols,
            textposition='top center',
            marker=dict(
                size=10,
                color=returns,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title='收益率 (%)')
            ),
            name='币种'
        ))
        
        fig_scatter.update_layout(
            title='风险收益散点图',
            xaxis_title='最大回撤 (%)',
            yaxis_title='收益率 (%)',
            height=500
        )
        
        charts['risk_return_scatter'] = fig_scatter.to_html(include_plotlyjs='cdn')
        
        # 3. 信号质量对比图
        signal_stats = []
        for symbol in symbols:
            results = multi_results[symbol]['results']
            signal_stats.append({
                'symbol': symbol,
                'execution_rate': results.get('signal_stats', {}).get('signal_execution_rate', 0),
                'success_rate': results.get('signal_stats', {}).get('signal_success_rate', 0),
                'avg_strength': results.get('avg_signal_strength', 0),
                'avg_confidence': results.get('avg_confidence_score', 0)
            })
        
        if signal_stats:
            fig_signal = make_subplots(
                rows=2, cols=2,
                subplot_titles=['信号执行率', '信号成功率', '平均信号强度', '平均置信度']
            )
            
            # 信号执行率
            fig_signal.add_trace(go.Bar(
                x=symbols,
                y=[s['execution_rate'] for s in signal_stats],
                name='执行率',
                marker_color='lightblue'
            ), row=1, col=1)
            
            # 信号成功率
            fig_signal.add_trace(go.Bar(
                x=symbols,
                y=[s['success_rate'] for s in signal_stats],
                name='成功率',
                marker_color='lightgreen'
            ), row=1, col=2)
            
            # 平均信号强度
            fig_signal.add_trace(go.Bar(
                x=symbols,
                y=[s['avg_strength'] for s in signal_stats],
                name='信号强度',
                marker_color='orange'
            ), row=2, col=1)
            
            # 平均置信度
            fig_signal.add_trace(go.Bar(
                x=symbols,
                y=[s['avg_confidence'] for s in signal_stats],
                name='置信度',
                marker_color='purple'
            ), row=2, col=2)
            
            fig_signal.update_layout(
                title='信号质量对比分析',
                height=600,
                showlegend=False
            )
            
            charts['signal_quality'] = fig_signal.to_html(include_plotlyjs='cdn')
        
        return charts