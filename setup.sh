#!/bin/bash
set -e

# 检查python3是否存在
if ! command -v python3 &> /dev/null; then
    echo "错误：未找到 python3，请先安装 Python 3"
    exit 1
fi

# 创建虚拟环境
echo "🐍 创建虚拟环境..."
python3 -m venv venv

# 激活虚拟环境并安装依赖
echo "📦 安装依赖..."
source venv/bin/activate
pip install -r requirements.txt

# 使用系统已安装的 Google Chrome，跳过下载
echo "🌐 检测系统 Chrome..."
if [ ! -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    echo "⚠️  未检测到 Google Chrome，请先安装后再运行爬虫"
else
    echo "✅ 已找到 Google Chrome"
fi

# 创建data目录
echo "📁 创建数据目录..."
mkdir -p data

# 初始化数据库
echo "💾 初始化数据库..."
python3 db.py

echo "✅ 安装完成！请运行 bash run.sh 开始使用"