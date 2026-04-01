#!/bin/bash
set -e

# 激活虚拟环境
source venv/bin/activate

echo "🕷️ 开始爬取淘宝数据..."
python3 scrapers/taobao.py

echo "🕷️ 开始爬取小红书数据..."
python3 scrapers/xiaohongshu.py

echo "📊 启动分析仪表盘..."
streamlit run dashboard.py