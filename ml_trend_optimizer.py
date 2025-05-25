#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器学习趋势识别优化系统
使用机器学习技术提升趋势识别准确率
"""

import pandas as pd
import numpy as np
import talib
import pickle
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 机器学习模块
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
    from sklearn.feature_selection import SelectKBest, f_classif
    import joblib
    ML_AVAILABLE = True
except ImportError:
    print("⚠️  机器学习模块未安装，请运行: pip install scikit-learn joblib")
    ML_AVAILABLE = False

@dataclass
class MLPrediction:
    """ML预测结果"""
    direction: str              # 'up', 'down', 'sideways'
    confidence: float           # 0-1
    probability_up: float       # 上涨概率
    probability_down: float     # 下跌概率
    probability_sideways: float # 震荡概率
    feature_importance: Dict[str, float]
    
    def __str__(self):
        return f"预测: {self.direction} (置信度: {self.confidence:.3f})"

class MLTrendOptimizer:
    """机器学习趋势优化器"""
    
    def __init__(self):
        if not ML_AVAILABLE:
            raise ImportError("机器学习模块未安装")
        
        self.models = {}
        self.scalers = {}
        self.feature_selectors = {}
        self.label_encoders = {}
        
        # 特征工程参数
        self.lookback_periods = [5, 10, 20, 50]
        self.prediction_horizon = 10  # 预测未来10期的趋势
        
        # 模型配置
        self.model_configs = {
            'random_forest': {
                'model': RandomForestClassifier,
                'params': {
                    'n_estimators': 100,
                    'max_depth': 15,
                    'min_samples_split': 5,
                    'min_samples_leaf': 2,
                    'random_state': 42
                }
            },
            'gradient_boosting': {
                'model': GradientBoostingClassifier,
                'params': {
                    'n_estimators': 100,
                    'learning_rate': 0.1,
                    'max_depth': 6,
                    'random_state': 42
                }
            },
            'logistic_regression': {
                'model': LogisticRegression,
                'params': {
                    'random_state': 42,
                    'max_iter': 1000
                }
            }
        }
        
    def extract_comprehensive_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """提取综合特征"""
        
        features = pd.DataFrame(index=data.index)
        
        # 基础价格特征
        features = self._add_price_features(features, data)
        
        # 技术指标特征
        features = self._add_technical_indicators(features, data)
        
        # 统计特征
        features = self._add_statistical_features(features, data)
        
        # 时间特征
        features = self._add_temporal_features(features, data)
        
        # 成交量特征
        features = self._add_volume_features(features, data)
        
        # 波动率特征
        features = self._add_volatility_features(features, data)
        
        # 形态识别特征
        features = self._add_pattern_features(features, data)
        
        return features.dropna()
    
    def _add_price_features(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """添加价格相关特征"""
        
        close = data['close']
        high = data['high']
        low = data['low']
        open_price = data['open']
        
        # 基础价格特征
        features['price_change'] = close.pct_change()
        features['price_change_abs'] = features['price_change'].abs()
        features['high_low_ratio'] = high / low
        features['close_open_ratio'] = close / open_price
        features['upper_shadow'] = (high - np.maximum(close, open_price)) / (high - low + 1e-8)
        features['lower_shadow'] = (np.minimum(close, open_price) - low) / (high - low + 1e-8)
        features['body_ratio'] = np.abs(close - open_price) / (high - low + 1e-8)
        
        # 多周期价格变化
        for period in [3, 5, 10, 20]:
            features[f'price_change_{period}d'] = close.pct_change(period)
            features[f'high_{period}d'] = high.rolling(period).max() / close
            features[f'low_{period}d'] = low.rolling(period).min() / close
        
        # 价格位置特征
        for period in [10, 20, 50]:
            rolling_high = high.rolling(period).max()
            rolling_low = low.rolling(period).min()
            features[f'price_position_{period}d'] = (close - rolling_low) / (rolling_high - rolling_low + 1e-8)
        
        return features
    
    def _add_technical_indicators(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """添加技术指标特征"""
        
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        volume = data.get('volume', pd.Series([1]*len(data))).values
        
        # 趋势指标
        for period in [10, 20, 50]:
            sma = talib.SMA(close, period)
            ema = talib.EMA(close, period)
            features[f'sma_{period}'] = close / sma
            features[f'ema_{period}'] = close / ema
            features[f'sma_slope_{period}'] = pd.Series(sma).pct_change(5)
        
        # 动量指标
        features['rsi_14'] = talib.RSI(close, 14)
        features['rsi_7'] = talib.RSI(close, 7)
        features['rsi_21'] = talib.RSI(close, 21)
        
        # MACD
        macd, macd_signal, macd_hist = talib.MACD(close)
        features['macd'] = macd
        features['macd_signal'] = macd_signal
        features['macd_hist'] = macd_hist
        features['macd_ratio'] = macd / (macd_signal + 1e-8)
        
        # 随机指标
        slowk, slowd = talib.STOCH(high, low, close)
        features['stoch_k'] = slowk
        features['stoch_d'] = slowd
        features['stoch_ratio'] = slowk / (slowd + 1e-8)
        
        # ADX系统
        features['adx'] = talib.ADX(high, low, close, 14)
        features['plus_di'] = talib.PLUS_DI(high, low, close, 14)
        features['minus_di'] = talib.MINUS_DI(high, low, close, 14)
        features['di_ratio'] = features['plus_di'] / (features['minus_di'] + 1e-8)
        
        # 威廉指标
        features['williams_r'] = talib.WILLR(high, low, close, 14)
        
        # CCI
        features['cci'] = talib.CCI(high, low, close, 14)
        
        # 布林带
        bb_upper, bb_middle, bb_lower = talib.BBANDS(close)
        features['bb_upper'] = bb_upper
        features['bb_middle'] = bb_middle  
        features['bb_lower'] = bb_lower
        features['bb_width'] = (bb_upper - bb_lower) / bb_middle
        features['bb_position'] = (close - bb_lower) / (bb_upper - bb_lower + 1e-8)
        
        return features
    
    def _add_statistical_features(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """添加统计特征"""
        
        close = data['close']
        
        # 滚动统计特征
        for window in [5, 10, 20]:
            rolling_mean = close.rolling(window).mean()
            rolling_std = close.rolling(window).std()
            
            features[f'zscore_{window}'] = (close - rolling_mean) / (rolling_std + 1e-8)
            features[f'cv_{window}'] = rolling_std / (rolling_mean + 1e-8)
            features[f'skew_{window}'] = close.rolling(window).skew()
            features[f'kurt_{window}'] = close.rolling(window).kurt()
        
        # 百分位数特征
        for window in [20, 50]:
            features[f'percentile_rank_{window}'] = close.rolling(window).rank(pct=True)
        
        return features
    
    def _add_temporal_features(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """添加时间特征"""
        
        if 'timestamp' in data.columns:
            timestamp = pd.to_datetime(data['timestamp'])
            features['hour'] = timestamp.dt.hour
            features['day_of_week'] = timestamp.dt.dayofweek
            features['day_of_month'] = timestamp.dt.day
            features['month'] = timestamp.dt.month
            
            # 周期性特征
            features['hour_sin'] = np.sin(2 * np.pi * features['hour'] / 24)
            features['hour_cos'] = np.cos(2 * np.pi * features['hour'] / 24)
            features['dow_sin'] = np.sin(2 * np.pi * features['day_of_week'] / 7)
            features['dow_cos'] = np.cos(2 * np.pi * features['day_of_week'] / 7)
        
        return features
    
    def _add_volume_features(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """添加成交量特征"""
        
        if 'volume' not in data.columns:
            return features
        
        volume = data['volume']
        close = data['close']
        
        # 成交量指标
        for period in [5, 10, 20]:
            vol_sma = volume.rolling(period).mean()
            features[f'volume_ratio_{period}'] = volume / (vol_sma + 1e-8)
            features[f'volume_price_trend_{period}'] = volume.rolling(period).corr(close)
        
        # OBV
        features['obv'] = talib.OBV(close.values, volume.values)
        features['obv_sma'] = talib.SMA(features['obv'].values, 10)
        features['obv_ratio'] = features['obv'] / (features['obv_sma'] + 1e-8)
        
        # 成交量价格确认
        price_change = close.pct_change()
        volume_change = volume.pct_change()
        features['vol_price_confirmation'] = (
            (price_change > 0) & (volume_change > 0) |
            (price_change < 0) & (volume_change > 0)
        ).astype(int)
        
        return features
    
    def _add_volatility_features(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """添加波动率特征"""
        
        high = data['high']
        low = data['low']
        close = data['close']
        
        # ATR
        for period in [7, 14, 21]:
            atr = talib.ATR(high.values, low.values, close.values, period)
            features[f'atr_{period}'] = atr
            features[f'atr_ratio_{period}'] = atr / close.values
        
        # 真实波动率
        tr = talib.TRANGE(high.values, low.values, close.values)
        features['true_range'] = tr
        features['tr_ratio'] = tr / close.values
        
        # 价格变化的波动率
        returns = close.pct_change()
        for window in [5, 10, 20]:
            features[f'volatility_{window}'] = returns.rolling(window).std()
            features[f'volatility_ratio_{window}'] = (
                features[f'volatility_{window}'] / returns.rolling(50).std()
            )
        
        return features
    
    def _add_pattern_features(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """添加形态识别特征"""
        
        open_price = data['open'].values
        high = data['high'].values
        low = data['low'].values
        close = data['close'].values
        
        # K线形态
        features['doji'] = talib.CDLDOJI(open_price, high, low, close)
        features['hammer'] = talib.CDLHAMMER(open_price, high, low, close)
        features['shooting_star'] = talib.CDLSHOOTINGSTAR(open_price, high, low, close)
        features['engulfing_bullish'] = talib.CDLENGULFING(open_price, high, low, close)
        features['hanging_man'] = talib.CDLHANGINGMAN(open_price, high, low, close)
        features['inverted_hammer'] = talib.CDLINVERTEDHAMMER(open_price, high, low, close)
        
        # 价格突破
        for period in [10, 20]:
            rolling_high = pd.Series(high).rolling(period).max()
            rolling_low = pd.Series(low).rolling(period).min()
            features[f'breakout_high_{period}'] = (close > rolling_high.shift(1)).astype(int)
            features[f'breakout_low_{period}'] = (close < rolling_low.shift(1)).astype(int)
        
        return features
    
    def generate_labels(self, data: pd.DataFrame, horizon: int = 10, 
                       threshold: float = 0.02) -> pd.Series:
        """生成训练标签"""
        
        close = data['close']
        
        # 计算未来收益率
        future_returns = close.shift(-horizon) / close - 1
        
        # 三分类标签
        labels = pd.Series(index=data.index, dtype=str)
        labels[future_returns > threshold] = 'up'
        labels[future_returns < -threshold] = 'down'
        labels[(future_returns >= -threshold) & (future_returns <= threshold)] = 'sideways'
        
        # 去掉无法预测的最后几个数据点
        labels = labels[:-horizon]
        
        return labels
    
    def train_ensemble_model(self, features: pd.DataFrame, labels: pd.Series,
                           test_size: float = 0.2) -> Dict[str, Any]:
        """训练集成模型"""
        
        print("🎯 开始训练ML集成模型...")
        
        # 数据预处理
        print("🔧 数据预处理...")
        
        # 移除无效特征
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.fillna(method='ffill').fillna(0)
        
        # 特征选择
        print("📊 特征选择...")
        selector = SelectKBest(score_func=f_classif, k=min(50, features.shape[1]))
        features_selected = selector.fit_transform(features, labels)
        selected_feature_names = features.columns[selector.get_support()].tolist()
        
        print(f"   选择了 {len(selected_feature_names)} 个特征")
        
        # 数据分割
        X_train, X_test, y_train, y_test = train_test_split(
            features_selected, labels, test_size=test_size, 
            random_state=42, stratify=labels
        )
        
        # 特征标准化
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # 标签编码
        le = LabelEncoder()
        y_train_encoded = le.fit_transform(y_train)
        y_test_encoded = le.transform(y_test)
        
        print(f"📊 训练集: {len(X_train)} 样本")
        print(f"📊 测试集: {len(X_test)} 样本")
        print(f"📊 类别分布: {dict(zip(*np.unique(y_train, return_counts=True)))}")
        
        # 训练多个模型
        trained_models = {}
        model_scores = {}
        
        for model_name, config in self.model_configs.items():
            print(f"\n🔄 训练 {model_name}...")
            
            # 创建和训练模型
            model = config['model'](**config['params'])
            
            # 交叉验证
            cv_scores = cross_val_score(model, X_train_scaled, y_train_encoded, cv=5)
            print(f"   交叉验证得分: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
            
            # 训练最终模型
            model.fit(X_train_scaled, y_train_encoded)
            
            # 测试集评估
            test_score = model.score(X_test_scaled, y_test_encoded)
            print(f"   测试集准确率: {test_score:.3f}")
            
            trained_models[model_name] = model
            model_scores[model_name] = test_score
        
        # 选择最佳模型
        best_model_name = max(model_scores, key=model_scores.get)
        best_model = trained_models[best_model_name]
        
        print(f"\n🏆 最佳模型: {best_model_name} (准确率: {model_scores[best_model_name]:.3f})")
        
        # 详细评估
        y_pred = best_model.predict(X_test_scaled)
        y_pred_labels = le.inverse_transform(y_pred)
        
        print(f"\n📊 详细评估报告:")
        print(classification_report(y_test, y_pred_labels))
        
        # 特征重要性
        if hasattr(best_model, 'feature_importances_'):
            importance = best_model.feature_importances_
            feature_importance = dict(zip(selected_feature_names, importance))
            
            # 排序特征重要性
            sorted_importance = sorted(feature_importance.items(), 
                                     key=lambda x: x[1], reverse=True)
            
            print(f"\n📈 前10个重要特征:")
            for i, (feature, imp) in enumerate(sorted_importance[:10]):
                print(f"   {i+1}. {feature}: {imp:.3f}")
        
        # 保存模型组件
        model_package = {
            'model': best_model,
            'scaler': scaler,
            'selector': selector,
            'label_encoder': le,
            'feature_names': selected_feature_names,
            'model_name': best_model_name,
            'accuracy': model_scores[best_model_name],
            'feature_importance': feature_importance if hasattr(best_model, 'feature_importances_') else {}
        }
        
        return model_package
    
    def predict_trend(self, model_package: Dict[str, Any], 
                     features: pd.DataFrame) -> MLPrediction:
        """使用训练好的模型预测趋势"""
        
        model = model_package['model']
        scaler = model_package['scaler']
        selector = model_package['selector']
        le = model_package['label_encoder']
        
        # 预处理特征
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.fillna(method='ffill').fillna(0)
        
        # 选择特征
        features_selected = selector.transform(features.iloc[-1:])
        
        # 标准化
        features_scaled = scaler.transform(features_selected)
        
        # 预测
        prediction = model.predict(features_scaled)[0]
        probabilities = model.predict_proba(features_scaled)[0]
        
        # 解码标签
        direction = le.inverse_transform([prediction])[0]
        
        # 获取各类别概率 - 修复版
        class_labels = le.classes_  # 这是字符串标签 ['down', 'sideways', 'up']
        prob_dict = dict(zip(class_labels, probabilities))  # 直接使用，不需要inverse_transform
        
        # 置信度（最高概率）
        confidence = max(probabilities)
        
        return MLPrediction(
            direction=direction,
            confidence=confidence,
            probability_up=prob_dict.get('up', 0),
            probability_down=prob_dict.get('down', 0),
            probability_sideways=prob_dict.get('sideways', 0),
            feature_importance=model_package.get('feature_importance', {})
        )
    
    def save_model(self, model_package: Dict[str, Any], filepath: str):
        """保存模型"""
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_package, f)
        
        print(f"✅ 模型已保存到: {filepath}")
    
    def load_model(self, filepath: str) -> Dict[str, Any]:
        """加载模型"""
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"模型文件不存在: {filepath}")
        
        with open(filepath, 'rb') as f:
            model_package = pickle.load(f)
        
        print(f"✅ 模型已加载: {filepath}")
        print(f"   模型类型: {model_package['model_name']}")
        print(f"   准确率: {model_package['accuracy']:.3f}")
        
        return model_package
    
    def optimize_parameters_with_ml(self, data: pd.DataFrame, 
                                   model_package: Dict[str, Any]) -> Dict[str, Any]:
        """使用ML结果优化策略参数"""
        
        # 提取特征
        features = self.extract_comprehensive_features(data)
        
        # 预测趋势
        prediction = self.predict_trend(model_package, features)
        
        print(f"🤖 ML预测结果: {prediction}")
        
        # 根据ML预测调整参数
        base_params = {
            'min_shadow_body_ratio': 2.0,
            'max_body_ratio': 0.30,
            'min_signal_score': 3,
            'volume_threshold': 1.2,
            'adx_threshold': 20,
            'trend_profit_extension': False,
            'max_trend_profit_pct': 8.0
        }
        
        # 根据ML置信度调整
        if prediction.confidence > 0.8:
            base_params['min_signal_score'] = 2  # 高置信度降低要求
            base_params['trend_profit_extension'] = True
            
        if prediction.direction == 'up' and prediction.probability_up > 0.7:
            base_params['max_trend_profit_pct'] = 12.0  # 看涨时提高目标
        elif prediction.direction == 'down' and prediction.probability_down > 0.7:
            base_params['max_trend_profit_pct'] = 12.0  # 看跌时提高目标
        
        # 根据重要特征调整
        important_features = prediction.feature_importance
        
        # 如果RSI重要性高，调整RSI相关参数
        rsi_importance = sum(v for k, v in important_features.items() if 'rsi' in k.lower())
        if rsi_importance > 0.1:
            base_params['rsi_weight'] = 1.5
        
        # 如果成交量重要性高，调整成交量相关参数
        volume_importance = sum(v for k, v in important_features.items() if 'volume' in k.lower())
        if volume_importance > 0.1:
            base_params['volume_threshold'] = 1.0  # 降低成交量要求
        
        return base_params
    
    def generate_ml_report(self, model_package: Dict[str, Any], 
                          prediction: MLPrediction) -> str:
        """生成ML分析报告"""
        
        report = f"""
🤖 机器学习趋势分析报告
{'='*60}
模型信息:
  - 模型类型: {model_package['model_name']}
  - 训练准确率: {model_package['accuracy']:.3f}
  - 特征数量: {len(model_package['feature_names'])}

📊 预测结果:
{'='*60}
预测方向: {prediction.direction.upper()}
置信度: {prediction.confidence:.3f}

各方向概率:
  - 上涨概率: {prediction.probability_up:.3f}
  - 下跌概率: {prediction.probability_down:.3f}
  - 震荡概率: {prediction.probability_sideways:.3f}

📈 关键影响因子 (前10个):
{'='*60}
"""
        
        # 显示重要特征
        sorted_features = sorted(prediction.feature_importance.items(), 
                               key=lambda x: x[1], reverse=True)
        
        for i, (feature, importance) in enumerate(sorted_features[:10]):
            report += f"  {i+1}. {feature}: {importance:.3f}\n"
        
        # 交易建议
        report += f"""
💡 ML增强交易建议:
{'='*60}
"""
        
        if prediction.confidence > 0.8:
            report += f"✅ 高置信度{prediction.direction}信号，建议积极交易\n"
        elif prediction.confidence > 0.6:
            report += f"⚠️  中等置信度{prediction.direction}信号，谨慎交易\n"
        else:
            report += f"❌ 低置信度信号，建议观望\n"
        
        if prediction.direction != 'sideways':
            main_prob = max(prediction.probability_up, prediction.probability_down)
            if main_prob > 0.7:
                report += "📈 概率分布显示强烈趋势倾向\n"
            elif main_prob > 0.5:
                report += "📊 概率分布显示温和趋势倾向\n"
        
        return report

# 使用示例和测试
if __name__ == "__main__":
    if ML_AVAILABLE:
        print("🤖 机器学习趋势优化系统已就绪")
        print("   支持随机森林、梯度提升、逻辑回归模型")
        print("   提供50+技术特征的自动提取")
        print("   包含特征选择和模型集成功能")
    else:
        print("❌ 机器学习模块未安装，请安装scikit-learn")