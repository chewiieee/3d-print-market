import sqlite3
import os
import pandas as pd
from datetime import datetime

# 从config导入DB_PATH，如果导入失败使用默认值
try:
    from config import DB_PATH
except ImportError:
    DB_PATH = "data/market.db"

def init_db():
    """创建数据库表并确保data目录存在"""
    # 确保data目录存在
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建淘宝商品表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS taobao_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            title TEXT,
            price REAL,
            monthly_sales INTEGER,
            review_count INTEGER,
            shop_name TEXT,
            url TEXT UNIQUE,
            crawled_at TEXT,
            shipping_time TEXT,
            has_video INTEGER DEFAULT 0
        )
    ''')
    
    # 创建小红书笔记表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS xhs_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            title TEXT,
            likes INTEGER,
            comments INTEGER,
            collects INTEGER,
            author TEXT,
            url TEXT UNIQUE,
            crawled_at TEXT,
            purchase_intent INTEGER DEFAULT 0
        )
    ''')
    
    # 迁移旧表：为已有表补充新列（忽略已存在的错误）
    migrations = [
        "ALTER TABLE taobao_products ADD COLUMN shipping_time TEXT",
        "ALTER TABLE taobao_products ADD COLUMN has_video INTEGER DEFAULT 0",
        "ALTER TABLE xhs_notes ADD COLUMN purchase_intent INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass  # 列已存在，忽略
    
    conn.commit()
    conn.close()

def insert_taobao_product(keyword, title, price, monthly_sales, review_count, shop_name, url,
                          shipping_time=None, has_video=0):
    """插入淘宝商品数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    cursor.execute('''
        INSERT OR IGNORE INTO taobao_products 
        (keyword, title, price, monthly_sales, review_count, shop_name, url, crawled_at,
         shipping_time, has_video)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (keyword, title, price, monthly_sales, review_count, shop_name, url, current_time,
          shipping_time, has_video))
    
    conn.commit()
    conn.close()

def insert_xhs_note(keyword, title, likes, comments, collects, author, url, purchase_intent=0):
    """插入小红书笔记数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    cursor.execute('''
        INSERT OR IGNORE INTO xhs_notes 
        (keyword, title, likes, comments, collects, author, url, crawled_at, purchase_intent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (keyword, title, likes, comments, collects, author, url, current_time, purchase_intent))
    
    conn.commit()
    conn.close()

def get_taobao_products():
    """获取所有淘宝数据为DataFrame"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM taobao_products", conn)
    conn.close()
    return df

def get_xhs_notes():
    """获取所有小红书数据为DataFrame"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM xhs_notes", conn)
    conn.close()
    return df

def get_stats():
    """获取统计数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取淘宝总数
    cursor.execute("SELECT COUNT(*) FROM taobao_products")
    taobao_total = cursor.fetchone()[0]
    
    # 获取小红书总数
    cursor.execute("SELECT COUNT(*) FROM xhs_notes")
    xhs_total = cursor.fetchone()[0]
    
    # 获取最新的爬取时间
    cursor.execute("SELECT MAX(crawled_at) FROM (SELECT crawled_at FROM taobao_products UNION SELECT crawled_at FROM xhs_notes)")
    last_crawled = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "taobao_total": taobao_total,
        "xhs_total": xhs_total,
        "last_crawled": last_crawled if last_crawled else "从未爬取"
    }

if __name__ == "__main__":
    init_db()
    print("数据库初始化成功")