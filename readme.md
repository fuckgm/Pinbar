# 🎯 Pinbar策略回测系统

一个功能强大的加密货币Pinbar策略回测系统，支持多币种测试、参数优化、动态杠杆管理和详细的回测报告生成。

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

## ✨ 核心特性

### 🧠 智能信号生成
- **多重确认机制**: 结合RSI、布林带、ADX等多个技术指标
- **信号质量评分**: 5级信号强度评估系统
- **趋势对齐检测**: 确保信号符合主要趋势方向
- **盘整市场过滤**: 自动识别并避免在盘整期间交易

### 📊 动态杠杆管理
- **智能杠杆调节**: 根据信号质量和市场波动自动调整杠杆
- **风险自适应**: 高质量信号使用更高杠杆，低质量信号降低杠杆
- **最大杠杆限制**: 防止过度杠杆造成的风险

### 🎯 增强回测功能
- **实盘级别回测**: 考虑滑点、手续费、资金费率等真实成本
- **多币种并行测试**: 同时测试多个交易对的策略表现
- **参数智能优化**: 网格搜索、随机搜索、贝叶斯优化等多种方法
- **详细交易分析**: 每笔交易的完整记录和分析

### 📈 专业报告系统
- **交互式图表**: 基于Plotly的动态价格图表和统计分析
- **交易详情查看**: 点击查看每笔交易的K线图和详细信息
- **信号质量统计**: 全面的信号生成和执行统计
- **多币种对比**: 不同币种的表现对比和排名

## 🏗️ 系统架构

```
📦 Pinbar策略回测系统
├── 📄 main.py                           # 主程序入口
├── 📄 pinbar_strategy.py                # 策略核心逻辑
├── 📄 data_utils.py                     # 数据处理工具
├── 📄 menu_handlers.py                  # 菜单处理函数
├── 📄 utils.py                          # 通用工具函数
├── 📄 config.py                         # 配置管理
├── 📄 data_manager.py                   # 数据获取管理
├── 📄 enhanced_signal_generator.py      # 增强信号生成器
├── 📄 parameter_optimizer.py            # 参数优化器
├── 📄 dynamic_leverage_manager.py       # 动态杠杆管理器
├── 📄 report_generator.py               # 报告生成器
├── 📄 enhanced_report_generator.py      # 增强报告生成器
├── 📄 report_data_processor.py          # 报告数据处理器
├── 📄 report_chart_generator.py         # 报告图表生成器
└── 📄 data_downloader.py                # 数据下载器
```

## 🚀 快速开始

### 📋 系统要求

- Python 3.7+
- 内存: 4GB+ (推荐8GB+)
- 存储: 2GB+ 可用空间

### 🔧 安装依赖

```bash
# 克隆项目
git clone https://github.com/your-username/pinbar-backtest-system.git
cd pinbar-backtest-system

# 安装依赖
pip install -r requirements.txt
```

### 📦 依赖列表

```txt
pandas>=1.3.0
numpy>=1.21.0
backtrader>=1.9.76
plotly>=5.0.0
jinja2>=3.0.0
inquirer>=2.7.0
requests>=2.25.1
openpyxl>=3.0.7
python-binance>=1.0.15
ccxt>=1.70.0
```

### 🎮 运行程序

```bash
python main.py
```

## 📖 使用指南

### 1️⃣ 数据准备

#### 使用数据下载器
```bash
# 启动程序后选择"数据下载器"
# 支持下载多个币种和时间周期的历史数据
```

#### 本地数据格式
```
data/
├── BTCUSDT/
│   ├── BTCUSDT_1h.csv
│   ├── BTCUSDT_4h.csv
│   └── BTCUSDT_1d.csv
├── ETHUSDT/
│   └── ETHUSDT_1h.csv
└── ...
```

### 2️⃣ 快速回测

```python
# 选择"快速回测"菜单
# 1. 选择数据源（本地/在线）
# 2. 选择币种和时间周期
# 3. 启用动态杠杆（推荐）
# 4. 自动生成回测报告
```

### 3️⃣ 自定义回测

```python
# 选择"配置参数后回测"菜单
# 可自定义以下参数：
# - 杠杆倍数
# - 单笔风险比例
# - 止损止盈比例
# - 信号质量阈值
# - 时间周期等
```

### 4️⃣ 多币种回测

```python
# 选择"多币种同时回测"菜单
# 支持批量测试多个币种
# 自动生成对比报告
```

### 5️⃣ 参数优化

```python
# 选择"智能参数优化"菜单
# 支持多种优化算法：
# - 网格搜索（全面但耗时）
# - 随机搜索（快速采样）
# - 贝叶斯优化（智能搜索）
```

## 📊 策略逻辑

### Pinbar信号识别

```python
# 锤形线（看涨信号）
if (lower_shadow / body_size >= 2.0 and    # 下影线至少是实体的2倍
    body_size / candle_range <= 0.35 and   # 实体不超过整根K线的35%
    upper_shadow / body_size <= 0.5):      # 上影线较短
    signal_type = "HAMMER"

# 射击线（看跌信号）
if (upper_shadow / body_size >= 2.0 and    # 上影线至少是实体的2倍
    body_size / candle_range <= 0.35 and   # 实体不超过整根K线的35%
    lower_shadow / body_size <= 0.5):      # 下影线较短
    signal_type = "SHOOTING_STAR"
```

### 信号确认机制

1. **技术指标确认**
   - RSI超买超卖区域
   - 布林带上下轨支撑阻力
   - ADX趋势强度确认

2. **趋势对齐检测**
   - 短期和中期趋势方向
   - 关键支撑阻力位
   - 成交量确认

3. **风险管理**
   - 动态止损止盈
   - 杠杆风险控制
   - 最大回撤限制

### 交易执行逻辑

```python
# 信号质量评分（1-5级）
signal_score = calculate_signal_strength(
    pinbar_quality,      # Pinbar形态质量
    trend_alignment,     # 趋势对齐度
    volume_confirmation, # 成交量确认
    rsi_position,        # RSI位置
    support_resistance   # 支撑阻力确认
)

# 动态杠杆计算
leverage = base_leverage * signal_score * market_volatility_factor

# 仓位大小计算
position_size = (account_balance * risk_per_trade) / stop_loss_distance
```

## 📈 回测报告

### 核心指标
- **总收益率**: 整个回测期间的总收益
- **夏普比率**: 风险调整后收益
- **最大回撤**: 资金曲线的最大下跌幅度
- **胜率**: 盈利交易占总交易的比例
- **盈亏比**: 平均盈利与平均亏损的比值

### 信号质量统计
- **总信号数**: 检测到的所有Pinbar信号
- **执行信号数**: 通过质量筛选的信号
- **信号执行率**: 执行信号占总信号的比例
- **信号成功率**: 盈利信号占执行信号的比例
- **平均信号强度**: 执行信号的平均质量评分

### 交易分析
- **交易明细表**: 每笔交易的详细记录
- **月度收益**: 按月统计的收益分布
- **持仓时间**: 平均持仓时间分析
- **杠杆使用**: 杠杆使用情况统计

## ⚙️ 配置说明

### 基础交易参数

```python
# config.py
class TradingParams:
    leverage = 10                    # 基础杠杆倍数
    risk_per_trade = 0.02           # 单笔交易风险比例 (2%)
    stop_loss_pct = 0.03            # 止损比例 (3%)
    take_profit_pct = 0.06          # 止盈比例 (6%)
    max_positions = 3               # 最大同时持仓数
    use_trailing_stop = True        # 是否使用移动止损
    trail_activation_pct = 0.02     # 移动止损激活比例
    trail_percent = 0.5             # 移动止损回撤比例
```

### 信号检测参数

```python
# enhanced_signal_generator.py
detector_config = {
    'min_shadow_body_ratio': 2.0,    # 最小影线实体比
    'max_body_ratio': 0.35,          # 最大实体比例
    'min_candle_size': 0.003,        # 最小K线大小
    'rsi_period': 14,                # RSI周期
    'rsi_oversold': 30,              # RSI超卖线
    'rsi_overbought': 70,            # RSI超买线
    'volume_threshold': 1.3,         # 成交量阈值
    'min_signal_score': 3            # 最小信号评分
}
```

## 🔧 高级功能

### 1. 参数优化示例

```python
# 优化杠杆和风险参数
optimization_space = {
    'leverage': [5, 10, 15, 20],
    'risk_per_trade': [0.01, 0.02, 0.03],
    'stop_loss_pct': [0.02, 0.03, 0.04],
    'min_signal_score': [2, 3, 4, 5]
}

# 运行优化
optimizer = ParameterOptimizer()
results = optimizer.optimize_parameters(
    data=data,
    optimization_type='grid',
    max_workers=4
)
```

### 2. 自定义信号检测器

```python
# 继承EnhancedPinbarDetector
class CustomPinbarDetector(EnhancedPinbarDetector):
    def detect_custom_pattern(self, df):
        # 实现自定义检测逻辑
        pass
```

### 3. 添加新的技术指标

```python
# 在enhanced_signal_generator.py中添加
def calculate_macd(self, df):
    exp1 = df['close'].ewm(span=12).mean()
    exp2 = df['close'].ewm(span=26).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9).mean()
    return macd, signal
```

## 📊 性能优化

### 1. 数据缓存
- 使用pickle格式存储预处理数据
- 内存中缓存最近使用的数据
- 分批处理大量历史数据

### 2. 并行计算
- 多进程参数优化
- 多币种并行回测
- 异步数据下载

### 3. 内存管理
- 滑动窗口处理历史数据
- 及时释放不需要的数据
- 使用生成器处理大数据集

## 🐛 故障排除

### 常见问题

**Q: 程序运行时提示"模块未找到"**
```bash
# 确保安装了所有依赖
pip install -r requirements.txt

# 检查Python路径
python -c "import sys; print(sys.path)"
```

**Q: 数据下载失败**
```bash
# 检查网络连接
# 确认API密钥配置正确
# 尝试使用代理服务器
```

**Q: 回测速度很慢**
```bash
# 减少历史数据量
# 降低并行进程数
# 使用更快的存储设备
```

**Q: 内存不足**
```bash
# 减少同时处理的币种数量
# 缩短回测时间周期
# 使用分批处理模式
```

### 调试模式

```python
# 在main.py中启用调试
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看详细的策略执行日志
```

## 🤝 贡献指南

### 开发环境设置

```bash
# 克隆开发分支
git clone -b develop https://github.com/your-username/pinbar-backtest-system.git

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/
```

### 代码规范

- 遵循PEP 8编码规范
- 使用类型提示
- 编写单元测试
- 添加详细的文档字符串

### 提交流程

1. Fork项目到个人仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [Backtrader](https://www.backtrader.com/) - 专业的Python回测框架
- [Plotly](https://plotly.com/) - 强大的交互式图表库
- [CCXT](https://github.com/ccxt/ccxt) - 统一的加密货币交易API
- [Pandas](https://pandas.pydata.org/) - 数据分析和处理库

## 📞 联系方式

- 项目主页: [GitHub Repository](https://github.com/your-username/pinbar-backtest-system)
- 问题反馈: [Issues](https://github.com/your-username/pinbar-backtest-system/issues)
- 讨论交流: [Discussions](https://github.com/your-username/pinbar-backtest-system/discussions)

## 🔄 更新日志

### v2.0.0 (最新版本)
- ✨ 新增模块化架构设计
- 🔧 增强信号生成器优化
- 📊 动态杠杆管理系统
- 📈 交互式回测报告
- 🎯 多币种并行测试
- 🧠 智能参数优化

### v1.5.0
- 📊 增强版报告生成器
- 🔍 信号质量评分系统
- ⚡ 性能优化和内存管理
- 🛠️ 配置管理系统重构

### v1.0.0
- 🎯 基础Pinbar策略实现
- 📈 基本回测功能
- 📊 简单报告生成
- 💾 数据管理系统

---

<div align="center">

**🎯 打造专业的量化交易工具，助力投资决策**

[⭐ Star](https://github.com/your-username/pinbar-backtest-system) | [🍴 Fork](https://github.com/your-username/pinbar-backtest-system/fork) | [📢 Report Bug](https://github.com/your-username/pinbar-backtest-system/issues)

</div>