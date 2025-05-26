# Pinbar策略深度优化系统 - Docker配置文件
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libta-lib0-dev \
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
