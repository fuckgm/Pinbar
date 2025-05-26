#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pinbar策略深度优化系统 - 一键目录结构生成脚本
自动创建完整的项目目录结构和空白文件

使用方法：
1. 将此脚本放在 pinbar_strategy/ 目录的上级目录
2. 运行: python create_pinbar_structure.py
3. 脚本会自动创建所有目录和空白文件
"""

import os
import sys
from pathlib import Path

class PinbarStructureCreator:
    def __init__(self, base_path="pinbar"):
        self.base_path = Path(base_path)
        self.created_files = []
        self.created_dirs = []
        
    def create_directory(self, dir_path):
        """创建目录"""
        full_path = self.base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        self.created_dirs.append(str(full_path))
        print(f"📁 Created directory: {full_path}")
        
    def create_file(self, file_path, content=""):
        """创建文件"""
        full_path = self.base_path / file_path
        
        # 确保父目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 只有文件不存在时才创建
        if not full_path.exists():
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.created_files.append(str(full_path))
            print(f"📄 Created file: {full_path}")
        else:
            print(f"⚠️  File already exists, skipped: {full_path}")
    
    def create_python_module_file(self, file_path, module_description=""):
        """创建Python模块文件，包含基础模板"""
        content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{module_description}
Pinbar策略深度优化系统 - {Path(file_path).stem}模块

Created: 2024-12
Author: Pinbar Strategy Optimization Team
"""

# TODO: 实现{module_description}功能

class {self._get_class_name(file_path)}:
    """
    {module_description}
    """
    
    def __init__(self):
        # TODO: 初始化参数
        pass
    
    def analyze(self):
        """
        TODO: 实现核心分析功能
        """
        raise NotImplementedError("待实现")

# TODO: 添加更多功能函数和类
'''
        self.create_file(file_path, content)
    
    def create_init_file(self, dir_path, module_name=""):
        """创建__init__.py文件"""
        content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{module_name}模块初始化文件
Pinbar策略深度优化系统
"""

# TODO: 导入模块中的主要类和函数
# from .main_module import MainClass

__version__ = "1.0.0"
__author__ = "Pinbar Strategy Team"
'''
        self.create_file(dir_path / "__init__.py", content)
    
    def create_yaml_config_file(self, file_path, config_type=""):
        """创建YAML配置文件"""
        content = f'''# {config_type}配置文件
# Pinbar策略深度优化系统

# 基础配置
name: "{config_type}"
version: "1.0.0"
created: "2024-12"

# TODO: 添加具体配置参数
parameters:
  # 示例参数
  risk_level: 0.02
  max_position_size: 0.1
  
# TODO: 根据具体需求修改配置结构
'''
        self.create_file(file_path, content)
    
    def create_json_config_file(self, file_path, config_type=""):
        """创建JSON配置文件"""
        content = f'''{{
    "_comment": "{config_type}配置文件 - Pinbar策略深度优化系统",
    "_version": "1.0.0",
    "_created": "2024-12",
    
    "config_name": "{config_type}",
    "parameters": {{
        "example_param": 0.01
    }},
    
    "_todo": "根据具体需求修改配置结构"
}}
'''
        self.create_file(file_path, content)
    
    def _get_class_name(self, file_path):
        """根据文件名生成类名"""
        filename = Path(file_path).stem
        # 转换为驼峰命名
        parts = filename.split('_')
        return ''.join(word.capitalize() for word in parts)
    
    def create_deep_optimization_system(self):
        """创建深度优化系统"""
        print("\n🌊 创建深度优化核心系统...")
        
        # 1. 盘整带缓存系统
        system_path = Path("consolidation_system")
        self.create_init_file(system_path, "盘整带缓存系统")
        self.create_python_module_file(system_path / "consolidation_detector.py", "盘整带识别器")
        self.create_python_module_file(system_path / "breakout_analyzer.py", "突破分析器")
        self.create_python_module_file(system_path / "range_cache_manager.py", "区间缓存管理器")
        self.create_python_module_file(system_path / "dynamic_stop_controller.py", "动态止损控制器")
        self.create_python_module_file(system_path / "liquidity_hunter_detector.py", "流动性猎杀检测器")
        
        # 2. 止损后续航系统
        system_path = Path("post_stop_system")
        self.create_init_file(system_path, "止损后续航系统")
        self.create_python_module_file(system_path / "reversal_detector.py", "逆转检测器")
        self.create_python_module_file(system_path / "washout_analyzer.py", "洗盘分析器")
        self.create_python_module_file(system_path / "re_entry_signal_generator.py", "重入信号生成器")
        self.create_python_module_file(system_path / "relaxed_condition_manager.py", "放宽条件管理器")
        self.create_python_module_file(system_path / "continuation_tracker.py", "续航跟踪器")
        
        # 3. 多时间框架流动性分析
        system_path = Path("multi_timeframe_liquidity")
        self.create_init_file(system_path, "多时间框架流动性分析")
        self.create_python_module_file(system_path / "liquidity_zone_detector.py", "流动性区域检测器")
        self.create_python_module_file(system_path / "timeframe_resonance_analyzer.py", "时间框架共振分析器")
        self.create_python_module_file(system_path / "support_resistance_hunter.py", "支撑阻力猎手")
        self.create_python_module_file(system_path / "psychological_level_calculator.py", "心理价位计算器")
        self.create_python_module_file(system_path / "stop_hunt_predictor.py", "止损猎杀预测器")
        
        # 4. 加密市场适应系统
        system_path = Path("crypto_market_adapter")
        self.create_init_file(system_path, "加密市场适应系统")
        self.create_python_module_file(system_path / "volatility_regime_detector.py", "波动率状态检测器")
        self.create_python_module_file(system_path / "crypto_specific_analyzer.py", "加密市场特殊分析器")
        self.create_python_module_file(system_path / "coin_classifier.py", "币种分类器")
        self.create_python_module_file(system_path / "market_sentiment_analyzer.py", "市场情绪分析器")
        self.create_python_module_file(system_path / "fomo_fud_detector.py", "FOMO/FUD检测器")
        
        # 5. 动态持仓管理系统
        system_path = Path("dynamic_position_system")
        self.create_init_file(system_path, "动态持仓管理系统")
        self.create_python_module_file(system_path / "layered_position_manager.py", "分层持仓管理器")
        self.create_python_module_file(system_path / "trend_strength_assessor.py", "趋势强度评估器")
        self.create_python_module_file(system_path / "profit_target_optimizer.py", "止盈目标优化器")
        self.create_python_module_file(system_path / "position_scaling_controller.py", "仓位缩放控制器")
        self.create_python_module_file(system_path / "risk_adjusted_sizer.py", "风险调整仓位器")
    
    def create_symbol_specific_system(self):
        """创建币种特定参数系统"""
        print("\n🎯 创建币种特定参数系统...")
        
        # 核心模块
        system_path = Path("symbol_specific_params")
        self.create_init_file(system_path, "币种特定参数系统")
        self.create_python_module_file(system_path / "symbol_analyzer.py", "币种特征分析器")
        self.create_python_module_file(system_path / "param_optimizer.py", "参数优化器")
        self.create_python_module_file(system_path / "param_manager.py", "参数管理器")
        self.create_python_module_file(system_path / "symbol_classifier.py", "币种分类器")
        self.create_python_module_file(system_path / "dynamic_adjuster.py", "动态参数调整器")
        self.create_python_module_file(system_path / "param_validator.py", "参数验证器")
        
        # 配置文件架构
        config_base = Path("config")
        
        # 策略配置
        self.create_yaml_config_file(config_base / "strategy" / "base_strategy_config.yaml", "基础策略参数")
        self.create_yaml_config_file(config_base / "strategy" / "trend_tracking_config.yaml", "趋势跟踪参数")
        self.create_yaml_config_file(config_base / "strategy" / "ml_config.yaml", "机器学习参数")
        self.create_yaml_config_file(config_base / "strategy" / "adaptive_config.yaml", "自适应参数")
        
        # 主流币种配置
        major_coins = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
        for coin in major_coins:
            self.create_yaml_config_file(config_base / "symbol_specific" / "major_coins" / f"{coin}_config.yaml", f"{coin}专用参数")
        
        # DeFi代币配置
        defi_tokens = ["UNIUSDT", "AAVEUSDT", "COMPUSDT"]
        for token in defi_tokens:
            self.create_yaml_config_file(config_base / "symbol_specific" / "defi_tokens" / f"{token}_config.yaml", f"{token}专用参数")
        
        # 公链代币配置
        layer1_chains = ["ADAUSDT", "DOTUSDT", "AVAXUSDT"]
        for chain in layer1_chains:
            self.create_yaml_config_file(config_base / "symbol_specific" / "layer1_chains" / f"{chain}_config.yaml", f"{chain}专用参数")
        
        # 其他山寨币配置
        altcoins = ["LINKUSDT", "LTCUSDT", "XLMUSDT"]
        for alt in altcoins:
            self.create_yaml_config_file(config_base / "symbol_specific" / "altcoins" / f"{alt}_config.yaml", f"{alt}专用参数")
        
        # 币种分组配置
        groups = [
            "high_volatility_group", "medium_volatility_group", "low_volatility_group",
            "high_liquidity_group", "defi_tokens_group", "layer1_chains_group",
            "meme_coins_group", "stablecoins_group"
        ]
        for group in groups:
            self.create_yaml_config_file(config_base / "symbol_groups" / f"{group}.yaml", f"{group.replace('_', ' ').title()}")
        
        # 市场条件配置
        market_conditions = [
            "bull_market_params", "bear_market_params", 
            "sideways_market_params", "high_volatility_params"
        ]
        for condition in market_conditions:
            self.create_yaml_config_file(config_base / "market_conditions" / f"{condition}.yaml", f"{condition.replace('_', ' ').title()}")
        
        # 动态参数配置
        self.create_json_config_file(config_base / "dynamic_params" / "real_time_adjustments.json", "实时参数调整")
        self.create_json_config_file(config_base / "dynamic_params" / "performance_based_updates.json", "基于表现的参数更新")
        self.create_json_config_file(config_base / "dynamic_params" / "risk_based_limits.json", "基于风险的参数限制")
        
        # 模板文件
        self.create_yaml_config_file(config_base / "templates" / "symbol_config_template.yaml", "币种参数模板")
        self.create_yaml_config_file(config_base / "templates" / "group_config_template.yaml", "组参数模板")
        self.create_yaml_config_file(config_base / "templates" / "custom_config_template.yaml", "自定义参数模板")
    
    def create_live_trading_system(self):
        """创建实盘交易系统"""
        print("\n🏭 创建实盘交易系统...")
        
        # 1. 风控系统
        system_path = Path("risk_management")
        self.create_init_file(system_path, "风控管理系统")
        self.create_python_module_file(system_path / "global_risk_controller.py", "全局风控总控制器")
        self.create_python_module_file(system_path / "position_size_calculator.py", "动态仓位计算")
        self.create_python_module_file(system_path / "drawdown_protector.py", "回撤保护机制")
        self.create_python_module_file(system_path / "correlation_manager.py", "多币种相关性管理")
        self.create_python_module_file(system_path / "emergency_handler.py", "紧急情况处理")
        self.create_python_module_file(system_path / "risk_limits_config.py", "风控参数配置")
        self.create_python_module_file(system_path / "risk_monitor.py", "实时风险监控")
        
        # 2. 交易所接口
        system_path = Path("exchange_integration")
        self.create_init_file(system_path, "交易所接口集成")
        self.create_python_module_file(system_path / "base_exchange.py", "交易所基类")
        self.create_python_module_file(system_path / "binance_adapter.py", "币安接口适配器")
        self.create_python_module_file(system_path / "okx_adapter.py", "OKX接口适配器")
        self.create_python_module_file(system_path / "bybit_adapter.py", "Bybit接口适配器")
        self.create_python_module_file(system_path / "exchange_factory.py", "交易所工厂类")
        self.create_python_module_file(system_path / "api_key_manager.py", "API密钥安全管理")
        self.create_python_module_file(system_path / "rate_limiter.py", "API调用频率限制")
        self.create_python_module_file(system_path / "connection_manager.py", "连接管理和重连机制")
        
        # 3. 实时交易
        system_path = Path("live_trading")
        self.create_init_file(system_path, "实时交易系统")
        self.create_python_module_file(system_path / "signal_processor.py", "信号处理器")
        self.create_python_module_file(system_path / "order_executor.py", "订单执行器")
        self.create_python_module_file(system_path / "portfolio_manager.py", "投资组合管理")
        self.create_python_module_file(system_path / "market_data_manager.py", "实时行情管理")
        self.create_python_module_file(system_path / "position_tracker.py", "持仓跟踪")
        self.create_python_module_file(system_path / "trade_logger.py", "交易日志记录")
        self.create_python_module_file(system_path / "coin_screener.py", "币种自动筛选")
        self.create_python_module_file(system_path / "execution_engine.py", "执行引擎主控制器")
        
        # 4. 监控系统
        system_path = Path("monitoring")
        self.create_init_file(system_path, "系统监控")
        self.create_python_module_file(system_path / "system_monitor.py", "系统状态监控")
        self.create_python_module_file(system_path / "performance_tracker.py", "实时表现跟踪")
        self.create_python_module_file(system_path / "alert_system.py", "告警系统")
        self.create_python_module_file(system_path / "health_checker.py", "健康检查")
        self.create_python_module_file(system_path / "recovery_manager.py", "故障恢复")
        self.create_python_module_file(system_path / "dashboard_generator.py", "实时监控面板")
        
        # 5. 数据管理
        system_path = Path("data_management")
        self.create_init_file(system_path, "数据管理系统")
        self.create_python_module_file(system_path / "real_time_data_feed.py", "实时数据流")
        self.create_python_module_file(system_path / "historical_data_manager.py", "历史数据管理")
        self.create_python_module_file(system_path / "data_synchronizer.py", "数据同步器")
        self.create_python_module_file(system_path / "data_validator.py", "数据验证器")
        self.create_python_module_file(system_path / "backup_manager.py", "数据备份管理")
    
    def create_data_directories(self):
        """创建数据目录结构"""
        print("\n📊 创建实盘数据目录...")
        
        # 实时数据目录
        data_dirs = [
            "live_data/real_time_prices",
            "live_data/order_history", 
            "live_data/position_snapshots",
            "live_data/system_logs",
            
            # 配置备份
            "config_backup/daily_backups",
            "config_backup/parameter_versions",
            "config_backup/emergency_configs",
            
            # 性能数据
            "performance_data/daily_reports",
            "performance_data/weekly_summaries", 
            "performance_data/monthly_analysis",
            "performance_data/risk_assessments"
        ]
        
        for dir_path in data_dirs:
            self.create_directory(dir_path)
            # 创建说明文件
            readme_content = f"""# {dir_path.split('/')[-1].title().replace('_', ' ')}

此目录用于存储{dir_path.split('/')[-1].replace('_', '')}相关数据。

## 使用说明
- 请勿手动删除此目录下的文件
- 系统会自动管理文件的创建和清理
- 如需备份，请使用系统提供的备份功能

Generated by Pinbar Strategy Optimization System
"""
            self.create_file(f"{dir_path}/README.md", readme_content)
    
    def create_requirements_files(self):
        """创建依赖文件"""
        print("\n📦 创建依赖配置文件...")
        
        # 深度优化系统依赖
        deep_requirements = """# Pinbar策略深度优化系统 - 新增依赖

# 现有依赖 (保持不变)
backtrader>=1.9.76.123
pandas>=1.3.0
numpy>=1.21.0
scikit-learn>=1.0.0
joblib>=1.1.0
matplotlib>=3.5.0
tqdm>=4.62.0
loguru>=0.6.0
statsmodels>=0.13.0
jinja2>=3.0.0

# 深度优化系统新增依赖
scipy>=1.8.0                # 高级数学计算
ta-lib>=0.4.25              # 技术分析指标库
networkx>=2.6.0             # 图论分析（相关性网络）
hdbscan>=0.8.28             # 聚类分析（币种分类）

# 实盘交易系统依赖
ccxt>=2.5.0                 # 交易所API统一接口
python-binance>=1.0.16      # 币安API
okx>=1.0.0                  # OKX API  
pybit>=5.0.0               # Bybit API

# WebSocket和异步支持
websockets>=10.4           # WebSocket连接
aiohttp>=3.8.0             # 异步HTTP客户端
asyncio-mqtt>=0.11.0       # 异步MQTT客户端

# 加密和安全
cryptography>=3.4.8        # 密码学库
pycryptodome>=3.15.0       # 加密算法
python-decouple>=3.6       # 环境变量管理

# 数据库支持
sqlalchemy>=1.4.0          # ORM框架
alembic>=1.8.0             # 数据库迁移
redis>=4.3.0               # Redis缓存

# 配置管理
pyyaml>=6.0                # YAML配置文件
toml>=0.10.2               # TOML配置文件
configparser>=5.3.0        # INI配置文件

# 监控和告警
schedule>=1.1.0            # 任务调度
python-telegram-bot>=13.13 # Telegram通知
slack-sdk>=3.18.0          # Slack通知
email-validator>=1.3.0     # 邮件验证

# 数据验证和序列化
pydantic>=1.10.0           # 数据验证
marshmallow>=3.17.0        # 序列化
cerberus>=1.3.4            # 配置验证

# 性能监控
psutil>=5.9.0              # 系统监控
memory-profiler>=0.60.0    # 内存分析
py-spy>=0.3.14             # 性能分析

# 机器学习增强
xgboost>=1.6.0             # 梯度提升
lightgbm>=3.3.0            # 轻量级梯度提升
catboost>=1.1.0            # 类别型数据梯度提升
optuna>=3.0.0              # 超参数优化

# 时间序列分析
pmdarima>=2.0.0            # ARIMA模型
prophet>=1.1.0             # Facebook时间序列预测
arch>=5.3.0                # GARCH模型

# 可视化增强
plotly>=5.10.0             # 交互式图表
dash>=2.6.0                # Web应用框架
bokeh>=2.4.0               # 交互式可视化
seaborn>=0.11.0            # 统计可视化

# 数据处理增强
pyarrow>=9.0.0             # 高性能数据格式
fastparquet>=0.8.0         # Parquet文件处理
h5py>=3.7.0                # HDF5文件处理
"""
        
        self.create_file("requirements_deep_optimization.txt", deep_requirements)
        
        # Docker支持
        dockerfile_content = """# Pinbar策略深度优化系统 - Docker配置文件
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    make \\
    libta-lib0-dev \\
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements_deep_optimization.txt .
RUN pip install --no-cache-dir -r requirements_deep_optimization.txt

# 复制项目文件
COPY . .

# 暴露端口（用于监控面板）
EXPOSE 8080

# 启动命令
CMD ["python", "main.py"]
"""
        self.create_file("Dockerfile", dockerfile_content)
        
        # Docker Compose配置
        docker_compose_content = """version: '3.8'

services:
  pinbar-strategy:
    build: .
    container_name: pinbar-deep-optimization
    volumes:
      - ./live_data:/app/live_data
      - ./config:/app/config
      - ./performance_data:/app/performance_data
    environment:
      - PYTHONPATH=/app
      - TZ=UTC
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    container_name: pinbar-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    
  monitoring:
    image: grafana/grafana:latest
    container_name: pinbar-monitoring
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    restart: unless-stopped

volumes:
  redis_data:
  grafana_data:
"""
        self.create_file("docker-compose.yml", docker_compose_content)
    
    def update_readme(self):
        """更新README文件"""
        print("\n📝 更新项目说明文档...")
        
        readme_content = """# Pinbar策略深度优化系统

## 🌊 项目概述

基于市场流动性原理和多时间框架分析的高盈亏比Pinbar交易策略优化系统，专门针对加密货币市场设计。

### 🎯 核心优势
- **高盈亏比目标**: 5:1 到 10:1 盈亏比
- **抗洗盘设计**: 盘整带缓存机制
- **智能续航**: 止损后二次机会捕获
- **多时间框架**: 流动性共振分析
- **加密优化**: 专门适配加密市场特性

## 🏗️ 系统架构

### ✅ 已完成模块
- 基础策略框架
- 趋势跟踪系统
- ML优化引擎
- 批量训练系统
- A/B测试对比
- 报告生成系统

### 🚀 深度优化系统 (开发中)
- **盘整带缓存系统**: 抗洗盘智能止损
- **止损后续航系统**: 二次机会智能捕获
- **多时间框架流动性分析**: 基于流动性理论的信号优化
- **加密市场适应系统**: 专门针对加密市场的参数优化
- **动态持仓管理系统**: 分层持仓和趋势感知止盈

### 🏭 实盘交易系统 (规划中)
- **全局风控系统**: 多层风控保护
- **交易所接口**: 支持币安/OKX/Bybit
- **实时监控**: 24/7系统监控和告警
- **智能执行**: 高效订单执行引擎

## 🚀 快速开始

### 环境准备
```bash
# 1. 克隆项目
git clone <repository_url>
cd pinbar_strategy

# 2. 安装依赖
pip install -r requirements_deep_optimization.txt

# 3. 运行主程序
python main.py
```

### Docker部署
```bash
# 构建和启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f pinbar-strategy
```

## 📊 使用说明

### 基础功能
1. **快速回测**: 趋势跟踪版策略回测
2. **A/B测试**: 原版vs优化版策略对比
3. **参数调优**: 自适应参数优化
4. **ML训练**: 机器学习模型训练

### 深度优化功能 (开发中)
1. **盘整带分析**: 识别和缓存盘整区间
2. **续航系统**: 止损后智能判断和重入
3. **流动性分析**: 多时间框架流动性共振
4. **市场适配**: 加密市场特殊性处理

## 🔧 配置管理

### 币种特定参数
- 位置: `config/symbol_specific/`
- 支持主流币、DeFi代币、公链代币等分类配置

### 市场条件参数
- 位置: `config/market_conditions/`
- 支持牛市、熊市、震荡市等不同市场环境

### 动态参数调整
- 位置: `config/dynamic_params/`
- 支持实时参数调整和性能优化

## 📈 性能指标

### 目标指标
- **盈亏比**: 5:1 ~ 10:1
- **胜率**: 45-50%
- **年化收益**: 50-100% (控制风险前提下)
- **最大回撤**: < 10%

### 实盘指标
- **订单执行成功率**: > 95%
- **信号处理延迟**: < 1秒
- **系统稳定性**: 连续运行 > 30天
- **资金安全**: 零损失事故

## 🛡️ 风险管理

### 多层风控
1. **账户级别**: 总资金5-10%最大风险
2. **交易所级别**: 单交易所不超过40%资金
3. **币种级别**: 主流币2-5%，其他1-2%仓位
4. **策略级别**: 单策略严格止损控制

### 紧急机制
- 自动熔断机制
- 紧急平仓功能
- 异常监控告警
- 人工干预接口

## 📞 支持与联系

- **问题反馈**: 通过GitHub Issues
- **文档**: 查看 `PROJECT_CONTEXT.md`
- **更新日志**: 查看版本更新记录

## 📄 许可证

MIT License

---

**⚠️ 风险提示**: 
- 加密货币交易存在高风险，可能导致资金损失
- 本系统仅供学习和研究使用
- 实盘交易前请充分测试并谨慎评估风险
- 建议从小资金开始，逐步验证策略有效性

**🚀 版本**: v4.0 深度优化完整版
**📅 更新**: 2024年12月
"""
        self.create_file("README.md", readme_content)
    
    def run(self):
        """执行完整的目录结构创建"""
        print("🚀 开始创建Pinbar策略深度优化系统目录结构...")
        print(f"📁 基础路径: {self.base_path.absolute()}")
        
        try:
            # 检查基础目录是否存在
            if not self.base_path.exists():
                print(f"❌ 基础目录不存在: {self.base_path}")
                print("请确保在正确的项目目录下运行此脚本")
                return False
            
            print("✅ 检测到现有项目，只创建深度优化模块...")
            
            # 1. 创建深度优化系统
            self.create_deep_optimization_system()
            
            # 2. 创建币种特定参数系统
            self.create_symbol_specific_system()
            
            # 3. 创建实盘交易系统
            self.create_live_trading_system()
            
            # 4. 创建新增数据目录
            self.create_data_directories()
            
            # 5. 创建深度优化依赖文件
            self.create_requirements_files()
            
            # 6. 更新说明文档 (追加内容，不覆盖)
            # self.update_readme()  # 暂时注释，手动更新README
            
            # 统计信息
            print(f"\n✅ 深度优化系统创建完成!")
            print(f"📁 创建目录数量: {len(self.created_dirs)}")
            print(f"📄 创建文件数量: {len(self.created_files)}")
            print(f"\n🎯 接下来的步骤:")
            print("1. 检查创建的深度优化模块")
            print("2. 安装新增依赖: pip install -r requirements_deep_optimization.txt")
            print("3. 开始开发盘整带缓存系统")
            print("4. 集成止损后续航机制")
            print("5. 逐步完善所有深度优化功能")
            
            return True
            
        except Exception as e:
            print(f"❌ 创建过程中出现错误: {str(e)}")
            return False

def main():
    """主函数"""
    print("🌊 Pinbar策略深度优化系统 - 目录结构生成器")
    print("=" * 60)
    
    # 检查当前目录
    current_dir = Path.cwd()
    print(f"📍 当前目录: {current_dir}")
    
    # 询问用户确认
    response = input("\n🤔 是否在当前目录下创建 'pinbar_strategy' 目录结构? (y/n): ")
    if response.lower() not in ['y', 'yes', '是']:
        print("❌ 操作取消")
        return
    
    # 创建目录结构
    creator = PinbarStructureCreator()
    success = creator.run()
    
    if success:
        print("\n🎉 恭喜! 深度优化系统目录结构创建成功!")
        print("📖 请查看 README.md 了解详细使用说明")
        print("🔧 请查看 PROJECT_CONTEXT.md 了解项目详细信息")
    else:
        print("\n💥 创建失败，请检查错误信息")

if __name__ == "__main__":
    main()