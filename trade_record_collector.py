#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易记录收集器
收集、整理和分析历史交易记录，用于批量训练
"""

import pandas as pd
import numpy as np
import json
import csv
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import os
from pathlib import Path

from batch_training_system import TradeRecord

class TradeRecordCollector:
    """交易记录收集器"""
    
    def __init__(self, data_dir: str = "trade_data/"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 输出文件路径
        self.records_file = self.data_dir / "trade_records.json"
        self.summary_file = self.data_dir / "trade_summary.csv"
        
    def collect_from_backtest_results(self, backtest_results: List[Dict[str, Any]], 
                                    symbol: str, interval: str) -> List[TradeRecord]:
        """从回测结果收集交易记录"""
        
        print(f"📊 收集 {symbol} {interval} 回测记录...")
        
        trade_records = []
        
        for trade_data in backtest_results:
            try:
                # 创建交易记录
                record = self._create_trade_record_from_backtest(trade_data, symbol, interval)
                if record:
                    trade_records.append(record)
                    
            except Exception as e:
                print(f"⚠️  记录处理失败: {e}")
                continue
        
        print(f"✅ 收集完成: {len(trade_records)} 条记录")
        return trade_records
    
    def _create_trade_record_from_backtest(self, trade_data: Dict[str, Any], 
                                         symbol: str, interval: str) -> Optional[TradeRecord]:
        """从回测数据创建交易记录"""
        
        try:
            # 计算最大有利/不利价格（需要从策略中获取）
            max_favorable = trade_data.get('highest_price', trade_data['entry_price'])
            max_adverse = trade_data.get('lowest_price', trade_data['entry_price'])
            
            # 如果是卖单，调整最大有利/不利
            if trade_data['direction'] == 'sell':
                max_favorable = trade_data.get('lowest_price', trade_data['entry_price'])
                max_adverse = trade_data.get('highest_price', trade_data['entry_price'])
            
            # 计算持仓时间（K线数量）
            entry_time = pd.to_datetime(trade_data['entry_time'])
            exit_time = pd.to_datetime(trade_data['exit_time'])
            
            # 估算持仓K线数量（基于时间间隔）
            time_diff = exit_time - entry_time
            interval_minutes = self._get_interval_minutes(interval)
            hold_duration = max(1, int(time_diff.total_seconds() / 60 / interval_minutes))
            
            # 创建记录
            record = TradeRecord(
                trade_id=trade_data.get('trade_id', f"{symbol}_{entry_time.strftime('%Y%m%d_%H%M%S')}"),
                symbol=symbol,
                interval=interval,
                entry_time=trade_data['entry_time'],
                exit_time=trade_data['exit_time'],
                entry_price=float(trade_data['entry_price']),
                exit_price=float(trade_data['exit_price']),
                direction=trade_data['direction'],
                profit_loss=float(trade_data.get('net_profit', 0)),
                profit_pct=float(trade_data.get('profit_pct', 0)),
                hold_duration=hold_duration,
                max_favorable=float(max_favorable),
                max_adverse=float(max_adverse),
                exit_reason=trade_data.get('reason', 'unknown'),
                
                # 策略信息
                signal_strength=int(trade_data.get('signal_strength', 3)),
                confidence_score=float(trade_data.get('confidence_score', 0.5)),
                trend_alignment=bool(trade_data.get('trend_alignment', False)),
                volume_confirmation=bool(trade_data.get('volume_confirmation', False)),
                
                # 市场环境（需要后续分析）
                market_volatility=0.0,  # 待填充
                trend_strength=0.0      # 待填充
            )
            
            return record
            
        except Exception as e:
            print(f"❌ 创建交易记录失败: {e}")
            return None
    
    def _get_interval_minutes(self, interval: str) -> int:
        """获取时间间隔分钟数"""
        interval_map = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
            '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200
        }
        return interval_map.get(interval, 60)
    
    def collect_from_manual_input(self, trades_data: List[Dict[str, Any]]) -> List[TradeRecord]:
        """从手动输入数据收集交易记录"""
        
        print("📝 从手动输入收集交易记录...")
        
        trade_records = []
        
        for trade_data in trades_data:
            try:
                record = TradeRecord(
                    trade_id=trade_data.get('trade_id', f"manual_{len(trade_records)}"),
                    symbol=trade_data['symbol'],
                    interval=trade_data['interval'],
                    entry_time=trade_data['entry_time'],
                    exit_time=trade_data['exit_time'],
                    entry_price=float(trade_data['entry_price']),
                    exit_price=float(trade_data['exit_price']),
                    direction=trade_data['direction'],
                    profit_loss=float(trade_data['profit_loss']),
                    profit_pct=float(trade_data['profit_pct']),
                    hold_duration=int(trade_data.get('hold_duration', 1)),
                    max_favorable=float(trade_data.get('max_favorable', trade_data['entry_price'])),
                    max_adverse=float(trade_data.get('max_adverse', trade_data['entry_price'])),
                    exit_reason=trade_data.get('exit_reason', 'manual'),
                    signal_strength=int(trade_data.get('signal_strength', 3)),
                    confidence_score=float(trade_data.get('confidence_score', 0.5)),
                    trend_alignment=bool(trade_data.get('trend_alignment', False)),
                    volume_confirmation=bool(trade_data.get('volume_confirmation', False)),
                    market_volatility=float(trade_data.get('market_volatility', 0.02)),
                    trend_strength=float(trade_data.get('trend_strength', 0.5))
                )
                
                trade_records.append(record)
                
            except Exception as e:
                print(f"⚠️  手动记录处理失败: {e}")
                continue
        
        print(f"✅ 手动记录收集完成: {len(trade_records)} 条")
        return trade_records
    
    def collect_from_csv(self, csv_file: str) -> List[TradeRecord]:
        """从CSV文件收集交易记录"""
        
        print(f"📄 从CSV文件收集记录: {csv_file}")
        
        try:
            df = pd.read_csv(csv_file)
            trade_records = []
            
            for _, row in df.iterrows():
                try:
                    record = TradeRecord(
                        trade_id=str(row.get('trade_id', f"csv_{len(trade_records)}")),
                        symbol=str(row['symbol']),
                        interval=str(row['interval']),
                        entry_time=str(row['entry_time']),
                        exit_time=str(row['exit_time']),
                        entry_price=float(row['entry_price']),
                        exit_price=float(row['exit_price']),
                        direction=str(row['direction']),
                        profit_loss=float(row['profit_loss']),
                        profit_pct=float(row['profit_pct']),
                        hold_duration=int(row.get('hold_duration', 1)),
                        max_favorable=float(row.get('max_favorable', row['entry_price'])),
                        max_adverse=float(row.get('max_adverse', row['entry_price'])),
                        exit_reason=str(row.get('exit_reason', 'unknown')),
                        signal_strength=int(row.get('signal_strength', 3)),
                        confidence_score=float(row.get('confidence_score', 0.5)),
                        trend_alignment=bool(row.get('trend_alignment', False)),
                        volume_confirmation=bool(row.get('volume_confirmation', False)),
                        market_volatility=float(row.get('market_volatility', 0.02)),
                        trend_strength=float(row.get('trend_strength', 0.5))
                    )
                    
                    trade_records.append(record)
                    
                except Exception as e:
                    print(f"⚠️  CSV行处理失败: {e}")
                    continue
            
            print(f"✅ CSV记录收集完成: {len(trade_records)} 条")
            return trade_records
            
        except Exception as e:
            print(f"❌ CSV文件读取失败: {e}")
            return []
    
    def enhance_records_with_market_data(self, trade_records: List[TradeRecord]) -> List[TradeRecord]:
        """用市场数据增强交易记录"""
        
        print("🔧 增强交易记录...")
        
        enhanced_records = []
        
        for record in trade_records:
            try:
                # 加载对应的K线数据
                from data_utils import load_local_data
                market_data = load_local_data(record.symbol, record.interval)
                
                if market_data is None:
                    enhanced_records.append(record)
                    continue
                
                # 计算市场环境特征
                enhanced_record = self._calculate_market_environment(record, market_data)
                enhanced_records.append(enhanced_record)
                
            except Exception as e:
                print(f"⚠️  记录增强失败 {record.trade_id}: {e}")
                enhanced_records.append(record)
                continue
        
        print(f"✅ 记录增强完成: {len(enhanced_records)} 条")
        return enhanced_records
    
    def _calculate_market_environment(self, record: TradeRecord, 
                                    market_data: pd.DataFrame) -> TradeRecord:
        """计算市场环境特征"""
        
        try:
            # 找到交易时间对应的K线
            market_data['timestamp'] = pd.to_datetime(market_data['timestamp'])
            entry_time = pd.to_datetime(record.entry_time)
            
            # 找到入场时间附近的数据
            time_diff = (market_data['timestamp'] - entry_time).abs()
            entry_idx = time_diff.idxmin()
            
            # 确保有足够的历史数据
            if entry_idx < 50:
                return record
            
            # 计算市场波动率（过去20期）
            recent_data = market_data.iloc[entry_idx-20:entry_idx]
            returns = recent_data['close'].pct_change().dropna()
            market_volatility = returns.std() if len(returns) > 0 else 0.02
            
            # 计算趋势强度
            trend_strength = self._calculate_trend_strength_simple(recent_data)
            
            # 更新记录
            enhanced_record = TradeRecord(
                trade_id=record.trade_id,
                symbol=record.symbol,
                interval=record.interval,
                entry_time=record.entry_time,
                exit_time=record.exit_time,
                entry_price=record.entry_price,
                exit_price=record.exit_price,
                direction=record.direction,
                profit_loss=record.profit_loss,
                profit_pct=record.profit_pct,
                hold_duration=record.hold_duration,
                max_favorable=record.max_favorable,
                max_adverse=record.max_adverse,
                exit_reason=record.exit_reason,
                signal_strength=record.signal_strength,
                confidence_score=record.confidence_score,
                trend_alignment=record.trend_alignment,
                volume_confirmation=record.volume_confirmation,
                market_volatility=market_volatility,
                trend_strength=trend_strength
            )
            
            return enhanced_record
            
        except Exception as e:
            print(f"⚠️  市场环境计算失败: {e}")
            return record
    
    def _calculate_trend_strength_simple(self, data: pd.DataFrame) -> float:
        """简化的趋势强度计算"""
        
        if len(data) < 10:
            return 0.5
        
        try:
            close = data['close']
            
            # 计算线性回归斜率
            x = np.arange(len(close))
            slope = np.polyfit(x, close, 1)[0]
            
            # 标准化斜率
            avg_price = close.mean()
            normalized_slope = abs(slope) / avg_price if avg_price > 0 else 0
            
            # 转换为0-1范围
            trend_strength = min(normalized_slope * 100, 1.0)
            
            return trend_strength
            
        except Exception:
            return 0.5
    
    def save_records(self, trade_records: List[TradeRecord], 
                    append: bool = True) -> str:
        """保存交易记录"""
        
        # 转换为字典列表
        records_data = [record.to_dict() for record in trade_records]
        
        # 保存JSON格式
        if append and os.path.exists(self.records_file):
            # 加载现有记录
            with open(self.records_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # 合并记录
            all_records = existing_data + records_data
        else:
            all_records = records_data
        
        # 保存JSON
        with open(self.records_file, 'w', encoding='utf-8') as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
        
        # 保存CSV摘要
        self._save_summary_csv(all_records)
        
        print(f"💾 交易记录已保存: {len(all_records)} 条记录")
        print(f"   JSON文件: {self.records_file}")
        print(f"   CSV摘要: {self.summary_file}")
        
        return str(self.records_file)
    
    def _save_summary_csv(self, records_data: List[Dict[str, Any]]):
        """保存CSV摘要"""
        
        if not records_data:
            return
        
        # 创建DataFrame
        df = pd.DataFrame(records_data)
        
        # 选择主要列
        summary_columns = [
            'trade_id', 'symbol', 'interval', 'entry_time', 'exit_time',
            'entry_price', 'exit_price', 'direction', 'profit_loss', 'profit_pct',
            'hold_duration', 'exit_reason', 'signal_strength', 'confidence_score'
        ]
        
        summary_df = df[summary_columns]
        summary_df.to_csv(self.summary_file, index=False)
    
    def load_records(self) -> List[TradeRecord]:
        """加载交易记录"""
        
        if not os.path.exists(self.records_file):
            print("❌ 交易记录文件不存在")
            return []
        
        try:
            with open(self.records_file, 'r', encoding='utf-8') as f:
                records_data = json.load(f)
            
            trade_records = []
            for data in records_data:
                record = TradeRecord(**data)
                trade_records.append(record)
            
            print(f"✅ 交易记录加载完成: {len(trade_records)} 条")
            return trade_records
            
        except Exception as e:
            print(f"❌ 交易记录加载失败: {e}")
            return []
    
    def analyze_records(self, trade_records: List[TradeRecord]) -> Dict[str, Any]:
        """分析交易记录"""
        
        if not trade_records:
            return {}
        
        print("📊 分析交易记录...")
        
        # 基础统计
        total_trades = len(trade_records)
        profitable_trades = [r for r in trade_records if r.profit_pct > 0]
        win_rate = len(profitable_trades) / total_trades * 100
        
        # 按币种统计
        symbol_stats = {}
        for record in trade_records:
            if record.symbol not in symbol_stats:
                symbol_stats[record.symbol] = []
            symbol_stats[record.symbol].append(record.profit_pct)
        
        # 按时间周期统计
        interval_stats = {}
        for record in trade_records:
            if record.interval not in interval_stats:
                interval_stats[record.interval] = []
            interval_stats[record.interval].append(record.profit_pct)
        
        # 按退出原因统计
        exit_reason_stats = {}
        for record in trade_records:
            reason = record.exit_reason
            if reason not in exit_reason_stats:
                exit_reason_stats[reason] = {'count': 0, 'profits': []}
            exit_reason_stats[reason]['count'] += 1
            exit_reason_stats[reason]['profits'].append(record.profit_pct)
        
        analysis = {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_profit': np.mean([r.profit_pct for r in trade_records]),
            'avg_hold_duration': np.mean([r.hold_duration for r in trade_records]),
            'symbol_performance': {
                symbol: {
                    'count': len(profits),
                    'avg_profit': np.mean(profits),
                    'win_rate': len([p for p in profits if p > 0]) / len(profits) * 100
                }
                for symbol, profits in symbol_stats.items()
            },
            'interval_performance': {
                interval: {
                    'count': len(profits),
                    'avg_profit': np.mean(profits),
                    'win_rate': len([p for p in profits if p > 0]) / len(profits) * 100
                }
                for interval, profits in interval_stats.items()
            },
            'exit_reason_analysis': {
                reason: {
                    'count': data['count'],
                    'avg_profit': np.mean(data['profits']),
                    'percentage': data['count'] / total_trades * 100
                }
                for reason, data in exit_reason_stats.items()
            }
        }
        
        # 打印分析结果
        print(f"📈 分析结果:")
        print(f"   总交易数: {total_trades}")
        print(f"   胜率: {win_rate:.1f}%")
        print(f"   平均收益: {analysis['avg_profit']:.2f}%")
        print(f"   平均持仓: {analysis['avg_hold_duration']:.1f} 周期")
        
        return analysis
    
    def create_sample_records(self) -> List[TradeRecord]:
        """创建示例交易记录（用于测试）"""
        
        print("📝 创建示例交易记录...")
        
        sample_records = [
            TradeRecord(
                trade_id="BTCUSDT_20231201_001",
                symbol="BTCUSDT",
                interval="1h",
                entry_time="2023-12-01 10:00:00",
                exit_time="2023-12-01 14:00:00",
                entry_price=42000.0,
                exit_price=42800.0,
                direction="buy",
                profit_loss=800.0,
                profit_pct=1.9,
                hold_duration=4,
                max_favorable=43200.0,
                max_adverse=41800.0,
                exit_reason="止盈",
                signal_strength=4,
                confidence_score=0.75,
                trend_alignment=True,
                volume_confirmation=True,
                market_volatility=0.025,
                trend_strength=0.7
            ),
            TradeRecord(
                trade_id="ETHUSDT_20231201_002",
                symbol="ETHUSDT",
                interval="4h",
                entry_time="2023-12-01 08:00:00",
                exit_time="2023-12-01 20:00:00",
                entry_price=2200.0,
                exit_price=2150.0,
                direction="sell",
                profit_loss=50.0,
                profit_pct=2.3,
                hold_duration=3,
                max_favorable=2120.0,
                max_adverse=2250.0,
                exit_reason="止盈",
                signal_strength=3,
                confidence_score=0.65,
                trend_alignment=False,
                volume_confirmation=True,
                market_volatility=0.03,
                trend_strength=0.4
            )
        ]
        
        print(f"✅ 示例记录创建完成: {len(sample_records)} 条")
        return sample_records

# 使用示例
if __name__ == "__main__":
    collector = TradeRecordCollector()
    
    # 创建示例记录
    sample_records = collector.create_sample_records()
    
    # 保存记录
    collector.save_records(sample_records, append=False)
    
    # 加载并分析
    loaded_records = collector.load_records()
    analysis = collector.analyze_records(loaded_records)
    
    print("🎯 交易记录收集器测试完成")