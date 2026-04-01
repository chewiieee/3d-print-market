from apscheduler.schedulers.blocking import BlockingScheduler
from config import SCHEDULE_INTERVAL_DAYS
import subprocess
import datetime

def crawl_task():
    """执行爬取任务"""
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{current_time} 开始定时爬取...")
    
    # 执行淘宝爬虫
    subprocess.run(["python3", "scrapers/taobao.py"])
    
    # 执行小红书爬虫
    subprocess.run(["python3", "scrapers/xiaohongshu.py"])
    
    print("本次爬取完成")

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    
    # 添加定时任务
    scheduler.add_job(
        crawl_task,
        'interval',
        days=SCHEDULE_INTERVAL_DAYS,
        id='market_crawl'
    )
    
    print(f"⏰ 定时任务已启动，每 {SCHEDULE_INTERVAL_DAYS} 天自动更新数据（按 Ctrl+C 停止）")
    scheduler.start()