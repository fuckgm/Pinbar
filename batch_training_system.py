#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量训练数据系统
通过历史交易记录批量训练，优化策略参数
"""

import pandas as pd
import numpy as np
import pickle
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import concurrent.futures
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import mean_squared_error, r2_score
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

@dataclass
class TradeRecord:
    """交易记录数据结构"""
    trade_id: str
    symbol: str
    interval: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    direction: str  # 'buy' or 'sell'
    profit_loss: float
    profit_pct: float
    hold_duration: int  # 持仓K线数量
    max_favorable: float  # 最大有利价格
    max_adverse: float   # 最大不利价格
    exit_reason: str
    
    # 策略相关
    signal_strength: int
    confidence_score: float
    trend_alignment: bool
    volume_confirmation: bool
    
    # 市场环境
    market_volatility: float
    trend_strength: float
    
    def to_dict(self):
        return asdict(self)

@dataclass
class BatchTrainingConfig:
    """批量训练配置"""
    # 数据路径
    data_directory: str = "data/"
    trade_records_file: str = "trade_records.json"
    model_output_dir: str = "models/batch/"
    
    # 训练参数
    min_samples_per_symbol: int = 100
    test_size: float = 0.2
    cv_folds: int = 5
    
    # 特征工程
    lookback_periods: List[int] = None
    feature_groups: List[str] = None
    
    # 并行处理
    max_workers: int = 4
    
    def __post_init__(self):
        if self.lookback_periods is None:
            self.lookback_periods = [5, 10, 20, 50]
        if self.feature_groups is None:
            self.feature_groups = ['price', 'technical', 'volume', 'volatility', 'pattern']

class BatchTrainingSystem:
    """批量训练数据系统"""
    
    def __init__(self, config: BatchTrainingConfig = None):
        if not ML_AVAILABLE:
            raise ImportError("机器学习模块未安装")
        
        self.config = config or BatchTrainingConfig()
        self.trained_models = {}
        self.feature_importance = {}
        self.performance_metrics = {}
        
        # 创建输出目录
        os.makedirs(self.config.model_output_dir, exist_ok=True)
    
    def prepare_batch_training_data(self, trade_records: List[TradeRecord], 
                                  symbols: List[str] = None) -> Dict[str, pd.DataFrame]:
        """准备批量训练数据"""
        
        print("🔧 准备批量训练数据...")
        
        if symbols is None:
            symbols = list(set(record.symbol for record in trade_records))
        
        batch_data = {}
        
        for symbol in symbols:
            print(f"📊 处理 {symbol} 数据...")
            
            # 过滤该币种的交易记录
            symbol_records = [r for r in trade_records if r.symbol == symbol]
            
            if len(symbol_records) < self.config.min_samples_per_symbol:
                print(f"⚠️  {symbol} 样本不足 ({len(symbol_records)} < {self.config.min_samples_per_symbol})")
                continue
            
            try:
                # 为每个币种准备训练数据
                symbol_data = self._prepare_symbol_data(symbol, symbol_records)
                if symbol_data is not None and len(symbol_data) > 0:
                    batch_data[symbol] = symbol_data
                    print(f"✅ {symbol} 数据准备完成: {len(symbol_data)} 样本")
                
            except Exception as e:
                print(f"❌ {symbol} 数据准备失败: {e}")
                continue
        
        print(f"📊 批量数据准备完成: {len(batch_data)} 个币种")
        return batch_data
    
    def _prepare_symbol_data(self, symbol: str, trade_records: List[TradeRecord]) -> Optional[pd.DataFrame]:
        """为单个币种准备训练数据"""
        
        # 加载K线数据
        intervals = list(set(record.interval for record in trade_records))
        
        combined_data = []
        
        for interval in intervals:
            interval_records = [r for r in trade_records if r.interval == interval]
            
            try:
                # 加载K线数据
                from data_utils import load_local_data
                kline_data = load_local_data(symbol, interval)
                
                if kline_data is None:
                    continue
                
                # 为每个交易记录创建训练样本
                for record in interval_records:
                    sample = self._create_training_sample(kline_data, record)
                    if sample is not None:
                        combined_data.append(sample)
                        
            except Exception as e:
                print(f"❌ {symbol} {interval} 数据处理失败: {e}")
                continue
        
        if not combined_data:
            return None
        
        # 合并所有样本
        result_df = pd.DataFrame(combined_data)
        return result_df
    
    def _create_training_sample(self, kline_data: pd.DataFrame, 
                              trade_record: TradeRecord) -> Optional[Dict[str, Any]]:
        """根据交易记录创建训练样本"""
        
        try:
            # 找到入场时间对应的K线索引
            entry_time = pd.to_datetime(trade_record.entry_time)
            kline_data['timestamp'] = pd.to_datetime(kline_data['timestamp'])
            
            # 找到最接近的K线
            time_diff = (kline_data['timestamp'] - entry_time).abs()
            entry_idx = time_diff.idxmin()
            
            # 确保有足够的历史数据
            lookback = max(self.config.lookback_periods)
            if entry_idx < lookback:
                return None
            
            # 提取入场前的K线数据用于特征工程
            feature_data = kline_data.iloc[entry_idx-lookback:entry_idx+1].copy()
            
            # 提取特征
            features = self._extract_comprehensive_features(feature_data, trade_record)
            
            # 创建目标变量（多个优化目标）
            targets = self._create_optimization_targets(trade_record)
            
            # 合并特征和目标
            sample = {**features, **targets}
            
            # 添加元数据
            sample.update({
                'symbol': trade_record.symbol,
                'interval': trade_record.interval,
                'entry_time': trade_record.entry_time,
                'trade_id': trade_record.trade_id
            })
            
            return sample
            
        except Exception as e:
            print(f"❌ 创建训练样本失败: {e}")
            return None
    
    def _extract_comprehensive_features(self, kline_data: pd.DataFrame, 
                                      trade_record: TradeRecord) -> Dict[str, float]:
        """提取综合特征"""
        
        features = {}
        
        # 1. 价格特征
        if 'price' in self.config.feature_groups:
            features.update(self._extract_price_features(kline_data))
        
        # 2. 技术指标特征
        if 'technical' in self.config.feature_groups:
            features.update(self._extract_technical_features(kline_data))
        
        # 3. 成交量特征
        if 'volume' in self.config.feature_groups:
            features.update(self._extract_volume_features(kline_data))
        
        # 4. 波动率特征
        if 'volatility' in self.config.feature_groups:
            features.update(self._extract_volatility_features(kline_data))
        
        # 5. 形态特征
        if 'pattern' in self.config.feature_groups:
            features.update(self._extract_pattern_features(kline_data))
        
        # 6. 交易信号特征（从原始信号）
        features.update({
            'original_signal_strength': trade_record.signal_strength,
            'original_confidence_score': trade_record.confidence_score,
            'original_trend_alignment': float(trade_record.trend_alignment),
            'original_volume_confirmation': float(trade_record.volume_confirmation),
        })
        
        return features
    
    def _extract_price_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """提取价格特征"""
        features = {}
        close = data['close']
        high = data['high'] 
        low = data['low']
        
        # 多周期收益率
        for period in self.config.lookback_periods:
            if len(close) > period:
                features[f'return_{period}d'] = close.iloc[-1] / close.iloc[-period-1] - 1
                features[f'volatility_{period}d'] = close.pct_change().tail(period).std()
        
        # 价格位置特征
        for period in [10, 20, 50]:
            if len(close) > period:
                rolling_high = high.tail(period).max()
                rolling_low = low.tail(period).min()
                if rolling_high > rolling_low:
                    features[f'price_position_{period}d'] = (close.iloc[-1] - rolling_low) / (rolling_high - rolling_low)
        
        return features
    
    def _extract_technical_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """提取技术指标特征"""
        import talib
        
        features = {}
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        
        # RSI
        rsi = talib.RSI(close, 14)
        if len(rsi) > 0 and not np.isnan(rsi[-1]):
            features['rsi'] = rsi[-1]
        
        # MACD
        macd, signal, hist = talib.MACD(close)
        if len(macd) > 0 and not np.isnan(macd[-1]):
            features['macd'] = macd[-1]
            features['macd_signal'] = signal[-1] if not np.isnan(signal[-1]) else 0
        
        # ADX
        adx = talib.ADX(high, low, close, 14)
        if len(adx) > 0 and not np.isnan(adx[-1]):
            features['adx'] = adx[-1]
        
        # 布林带
        upper, middle, lower = talib.BBANDS(close)
        if len(upper) > 0 and not np.isnan(upper[-1]):
            bb_width = upper[-1] - lower[-1]
            if bb_width > 0:
                features['bb_position'] = (close[-1] - lower[-1]) / bb_width
                features['bb_width'] = bb_width / middle[-1]
        
        return features
    
    def _extract_volume_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """提取成交量特征"""
        features = {}
        
        if 'volume' in data.columns:
            volume = data['volume']
            
            # 成交量比率
            for period in [5, 10, 20]:
                if len(volume) > period:
                    avg_volume = volume.tail(period).mean()
                    if avg_volume > 0:
                        features[f'volume_ratio_{period}d'] = volume.iloc[-1] / avg_volume
        
        return features
    
    def _extract_volatility_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """提取波动率特征"""
        import talib
        
        features = {}
        high = data['high'].values
        low = data['low'].values
        close = data['close'].values
        
        # ATR
        atr = talib.ATR(high, low, close, 14)
        if len(atr) > 0 and not np.isnan(atr[-1]):
            features['atr'] = atr[-1]
            features['atr_ratio'] = atr[-1] / close[-1]
        
        return features
    
    def _extract_pattern_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """提取形态特征"""
        import talib
        
        features = {}
        open_price = data['open'].values
        high = data['high'].values
        low = data['low'].values  
        close = data['close'].values
        
        # 常见形态
        patterns = {
            'doji': talib.CDLDOJI(open_price, high, low, close),
            'hammer': talib.CDLHAMMER(open_price, high, low, close),
            'shooting_star': talib.CDLSHOOTINGSTAR(open_price, high, low, close),
        }
        
        for pattern_name, pattern_values in patterns.items():
            if len(pattern_values) > 0:
                features[f'pattern_{pattern_name}'] = float(pattern_values[-1] != 0)
        
        return features
    
    def _create_optimization_targets(self, trade_record: TradeRecord) -> Dict[str, float]:
        """创建优化目标变量"""
        
        targets = {
            # 主要目标：盈利率
            'profit_pct': trade_record.profit_pct,
            
            # 风险调整收益
            'risk_adjusted_return': self._calculate_risk_adjusted_return(trade_record),
            
            # 持仓效率
            'holding_efficiency': self._calculate_holding_efficiency(trade_record),
            
            # 退出时机评分
            'exit_timing_score': self._calculate_exit_timing_score(trade_record),
            
            # 分类目标：交易质量
            'trade_quality': self._classify_trade_quality(trade_record),
        }
        
        return targets
    
    def _calculate_risk_adjusted_return(self, trade_record: TradeRecord) -> float:
        """计算风险调整收益"""
        if trade_record.max_adverse == 0:
            return trade_record.profit_pct
        
        max_risk = abs(trade_record.max_adverse - trade_record.entry_price) / trade_record.entry_price
        if max_risk == 0:
            return trade_record.profit_pct
        
        return trade_record.profit_pct / max_risk
    
    def _calculate_holding_efficiency(self, trade_record: TradeRecord) -> float:
        """计算持仓效率"""
        if trade_record.hold_duration == 0:
            return 0
        
        # 每单位时间的收益
        return trade_record.profit_pct / trade_record.hold_duration
    
    def _calculate_exit_timing_score(self, trade_record: TradeRecord) -> float:
        """计算退出时机评分"""
        if trade_record.direction == 'buy':
            max_possible = trade_record.max_favorable - trade_record.entry_price
        else:
            max_possible = trade_record.entry_price - trade_record.max_favorable
        
        actual_profit = trade_record.exit_price - trade_record.entry_price
        if trade_record.direction == 'sell':
            actual_profit = -actual_profit
        
        if max_possible <= 0:
            return 0 if actual_profit <= 0 else 1
        
        return actual_profit / max_possible
    
    def _classify_trade_quality(self, trade_record: TradeRecord) -> int:
        """分类交易质量"""
        if trade_record.profit_pct > 5:
            return 4  # 优秀
        elif trade_record.profit_pct > 2:
            return 3  # 良好
        elif trade_record.profit_pct > 0:
            return 2  # 一般
        elif trade_record.profit_pct > -2:
            return 1  # 较差
        else:
            return 0  # 很差
    
    def train_batch_models(self, batch_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """批量训练模型"""
        
        print("🎯 开始批量模型训练...")
        
        # 合并所有数据
        all_data = []
        for symbol, data in batch_data.items():
            data['symbol'] = symbol
            all_data.append(data)
        
        if not all_data:
            raise ValueError("没有可用的训练数据")
        
        combined_data = pd.concat(all_data, ignore_index=True)
        print(f"📊 合并数据: {len(combined_data)} 个样本")
        
        # 分离特征和目标
        feature_columns = [col for col in combined_data.columns 
                          if not col.startswith(('profit_', 'risk_adjusted_', 'holding_', 'exit_', 'trade_', 'symbol', 'interval', 'entry_time', 'trade_id'))]
        
        X = combined_data[feature_columns].fillna(0)
        
        # 多目标训练
        targets = {
            'profit_predictor': 'profit_pct',
            'risk_adjusted_predictor': 'risk_adjusted_return', 
            'efficiency_predictor': 'holding_efficiency',
            'exit_timing_predictor': 'exit_timing_score',
            'quality_classifier': 'trade_quality'
        }
        
        trained_models = {}
        performance_metrics = {}
        
        for model_name, target_col in targets.items():
            print(f"\n🔄 训练 {model_name}...")
            
            if target_col not in combined_data.columns:
                print(f"⚠️  目标列 {target_col} 不存在，跳过")
                continue
            
            y = combined_data[target_col].fillna(0)
            
            # 数据分割
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.config.test_size, random_state=42
            )
            
            # 选择模型
            if model_name == 'quality_classifier':
                from sklearn.ensemble import RandomForestClassifier
                model = RandomForestClassifier(n_estimators=100, random_state=42)
            else:
                model = RandomForestRegressor(n_estimators=100, random_state=42)
            
            # 特征标准化
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # 训练模型
            model.fit(X_train_scaled, y_train)
            
            # 评估模型
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            
            print(f"   训练得分: {train_score:.3f}")
            print(f"   测试得分: {test_score:.3f}")
            
            # 保存模型和评估结果
            trained_models[model_name] = {
                'model': model,
                'scaler': scaler,
                'feature_columns': feature_columns,
                'target_column': target_col
            }
            
            performance_metrics[model_name] = {
                'train_score': train_score,
                'test_score': test_score,
                'feature_importance': dict(zip(feature_columns, model.feature_importances_)) if hasattr(model, 'feature_importances_') else {}
            }
        
        print(f"\n✅ 批量训练完成: {len(trained_models)} 个模型")
        
        # 保存结果
        self.trained_models = trained_models
        self.performance_metrics = performance_metrics
        
        return {
            'models': trained_models,
            'metrics': performance_metrics,
            'feature_columns': feature_columns
        }
    
    def optimize_strategy_parameters(self, symbol: str, interval: str, 
                                   current_params: Dict[str, Any]) -> Dict[str, Any]:
        """基于训练结果优化策略参数"""
        
        if not self.trained_models:
            raise ValueError("没有训练好的模型，请先运行批量训练")
        
        print(f"🔧 为 {symbol} {interval} 优化策略参数...")
        
        # 加载当前市场数据
        try:
            from data_utils import load_local_data
            current_data = load_local_data(symbol, interval)
            
            if current_data is None:
                raise ValueError(f"无法加载 {symbol} {interval} 数据")
            
            # 提取当前市场特征
            recent_data = current_data.tail(100)  # 使用最近100根K线
            current_features = self._extract_comprehensive_features(recent_data, 
                                                                   TradeRecord("", symbol, interval, "", "", 0, 0, "buy", 0, 0, 0, 0, 0, "", 3, 0.5, True, True, 0.02, 0.5))
            
            # 使用训练好的模型预测
            predictions = self._predict_with_ensemble(current_features)
            
            # 基于预测结果调整参数
            optimized_params = self._adjust_parameters_based_predictions(
                current_params, predictions, symbol, interval
            )
            
            print("📊 参数优化完成:")
            for param, value in optimized_params.items():
                if param in current_params:
                    old_value = current_params[param]
                    change = "📈" if value > old_value else "📉" if value < old_value else "➡️"
                    print(f"   {param}: {old_value} → {value} {change}")
                else:
                    print(f"   {param}: {value} (新增)")
            
            return optimized_params
            
        except Exception as e:
            print(f"❌ 参数优化失败: {e}")
            return current_params
    
    def _predict_with_ensemble(self, features: Dict[str, float]) -> Dict[str, float]:
        """使用集成模型进行预测"""
        
        predictions = {}
        
        for model_name, model_data in self.trained_models.items():
            try:
                model = model_data['model']
                scaler = model_data['scaler']
                feature_columns = model_data['feature_columns']
                
                # 准备特征向量
                feature_vector = []
                for col in feature_columns:
                    feature_vector.append(features.get(col, 0))
                
                # 标准化和预测
                feature_vector = np.array(feature_vector).reshape(1, -1)
                feature_vector_scaled = scaler.transform(feature_vector)
                
                prediction = model.predict(feature_vector_scaled)[0]
                predictions[model_name] = prediction
                
            except Exception as e:
                print(f"⚠️  {model_name} 预测失败: {e}")
                predictions[model_name] = 0
        
        return predictions
    
    def _adjust_parameters_based_predictions(self, current_params: Dict[str, Any], 
                                           predictions: Dict[str, float],
                                           symbol: str, interval: str) -> Dict[str, Any]:
        """基于预测结果调整参数"""
        
        optimized_params = current_params.copy()
        
        # 根据盈利预测调整信号阈值
        expected_profit = predictions.get('profit_predictor', 0)
        if expected_profit > 3:  # 预期盈利>3%
            optimized_params['min_signal_score'] = max(1, current_params.get('min_signal_score', 3) - 1)
            optimized_params['min_shadow_body_ratio'] = max(1.0, current_params.get('min_shadow_body_ratio', 2.0) - 0.2)
        elif expected_profit < 0:  # 预期亏损
            optimized_params['min_signal_score'] = min(5, current_params.get('min_signal_score', 3) + 1)
            optimized_params['min_shadow_body_ratio'] = min(4.0, current_params.get('min_shadow_body_ratio', 2.0) + 0.3)
        
        # 根据退出时机预测调整止盈策略
        exit_timing_score = predictions.get('exit_timing_predictor', 0.5)
        if exit_timing_score < 0.3:  # 历史上经常过早退出
            optimized_params['trend_profit_extension'] = True
            optimized_params['max_trend_profit_pct'] = min(20.0, current_params.get('max_trend_profit_pct', 8.0) * 1.5)
        elif exit_timing_score > 0.8:  # 历史上退出时机很好
            optimized_params['trend_profit_extension'] = False
            optimized_params['max_trend_profit_pct'] = max(5.0, current_params.get('max_trend_profit_pct', 8.0) * 0.8)
        
        # 根据持仓效率调整
        efficiency = predictions.get('efficiency_predictor', 0)
        if efficiency > 0.5:  # 持仓效率高
            optimized_params['enable_trend_tracking'] = True
            optimized_params['trailing_stop_buffer'] = min(3.0, current_params.get('trailing_stop_buffer', 1.5) * 1.2)
        
        # 根据风险调整收益预测调整杠杆
        risk_adjusted_return = predictions.get('risk_adjusted_predictor', 0)
        if risk_adjusted_return > 2:  # 风险调整收益好
            optimized_params['leverage_multiplier'] = min(1.5, current_params.get('leverage_multiplier', 1.0) + 0.2)
        elif risk_adjusted_return < 0:  # 风险调整收益差
            optimized_params['leverage_multiplier'] = max(0.5, current_params.get('leverage_multiplier', 1.0) - 0.2)
        
        return optimized_params
    
    def save_batch_models(self, output_dir: str = None) -> str:
        """保存批量训练的模型"""
        
        if output_dir is None:
            output_dir = self.config.model_output_dir
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(output_dir, f"batch_models_{timestamp}.pkl")
        
        save_data = {
            'models': self.trained_models,
            'metrics': self.performance_metrics,
            'config': self.config,
            'timestamp': timestamp
        }
        
        with open(save_path, 'wb') as f:
            pickle.dump(save_data, f)
        
        print(f"💾 批量模型已保存: {save_path}")
        return save_path
    
    def load_batch_models(self, model_path: str):
        """加载批量训练的模型"""
        
        with open(model_path, 'rb') as f:
            save_data = pickle.load(f)
        
        self.trained_models = save_data['models']
        self.performance_metrics = save_data['metrics']
        
        print(f"✅ 批量模型已加载: {model_path}")
        print(f"   包含 {len(self.trained_models)} 个模型")
    
    def generate_optimization_report(self, symbol: str, predictions: Dict[str, float], 
                                   old_params: Dict[str, Any], new_params: Dict[str, Any]) -> str:
        """生成优化报告"""
        
        report = f"""
📊 策略参数优化报告 - {symbol}
{'='*60}
🤖 ML预测结果:
  - 预期盈利率: {predictions.get('profit_predictor', 0):.2f}%
  - 风险调整收益: {predictions.get('risk_adjusted_predictor', 0):.2f}
  - 持仓效率: {predictions.get('efficiency_predictor', 0):.3f}
  - 退出时机评分: {predictions.get('exit_timing_predictor', 0):.3f}
  - 交易质量评分: {predictions.get('quality_classifier', 0):.1f}/4

🔧 参数优化结果:
"""
        
        for param in new_params:
            old_val = old_params.get(param, "未设置")
            new_val = new_params[param]
            
            if param in old_params and old_params[param] != new_val:
                change_pct = ((new_val - old_params[param]) / old_params[param] * 100) if isinstance(old_params[param], (int, float)) and old_params[param] != 0 else 0
                report += f"  - {param}: {old_val} → {new_val} ({change_pct:+.1f}%)\n"
            elif param not in old_params:
                report += f"  - {param}: {new_val} (新增)\n"
        
        return report

# 使用示例和测试
if __name__ == "__main__":
    if ML_AVAILABLE:
        print("🎯 批量训练数据系统已就绪")
        print("   支持多币种、多模型协同训练")
        print("   提供基于历史交易记录的参数优化")
    else:
        print("❌ 机器学习模块未安装，请安装scikit-learn")