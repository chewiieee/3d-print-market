from playwright.sync_api import sync_playwright
import time, random, json, os, sys
sys.path.insert(0, ".")
from config import XHS_KEYWORDS, XHS_NOTES_PER_KEYWORD, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, COOKIES_PATH
from db import init_db, insert_xhs_note

# CSS选择器变量（搜索结果页，搜索结果页只有点赞数，评论/收藏仅详情页有）
NOTE_CARD_SELECTOR = "section.note-item"
TITLE_SELECTOR = "a.title span"
LIKES_SELECTOR = ".like-wrapper .count"
AUTHOR_SELECTOR = ".author .name"
# 搜索列表页暂无评论/收藏数，留空占位
COMMENTS_SELECTOR = None
COLLECTS_SELECTOR = None

def parse_number(num_str):
    """解析数字，处理'1.2万'等格式"""
    if not num_str:
        return 0
    try:
        num_str = num_str.strip()
        if '万' in num_str:
            num_str = num_str.replace('万', '')
            return int(float(num_str) * 10000)
        elif '千' in num_str:
            num_str = num_str.replace('千', '')
            return int(float(num_str) * 1000)
        else:
            return int(num_str.replace(',', ''))
    except:
        return 0

# 购买意愿关键词：出现则标记此笔记具备较高购买意图
PURCHASE_INTENT_KEYWORDS = [
    "在哪买", "哪里买", "求链接", "链接在哪", "有没有链接",
    "怎么买", "在哪购买", "求购买链接", "能买吗", "可以买吗",
    "求购", "想买", "购买渠道", "多少錢", "需要多少"
]

def has_purchase_intent(text):
    """检测文本中是否包含购买意愿关键词"""
    if not text:
        return 0
    return 1 if any(kw in text for kw in PURCHASE_INTENT_KEYWORDS) else 0

def save_cookies(context, cookies_path):
    """保存cookies到文件"""
    os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
    cookies = context.cookies()
    with open(cookies_path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

def load_cookies(context, cookies_path):
    """从文件加载cookies"""
    if os.path.exists(cookies_path):
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    return False

def scroll_and_extract_notes(page, keyword, max_notes):
    """滚动页面并提取笔记数据"""
    notes = []
    note_count = 0
    
    # 滚动3-5次
    scroll_times = random.randint(3, 5)
    for i in range(scroll_times):
        if note_count >= max_notes:
            break
            
        # 滚动到页面底部
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(1, 2))
        
        # 提取当前可见的笔记卡片
        note_cards = page.query_selector_all(NOTE_CARD_SELECTOR)
        
        for card in note_cards:
            if note_count >= max_notes:
                break
                
            try:
                # 提取标题
                title_element = card.query_selector(TITLE_SELECTOR)
                title = title_element.inner_text().strip() if title_element else "未知标题"
                if not title or len(title) < 2:
                    continue

                # 提取点赞数
                likes_element = card.query_selector(LIKES_SELECTOR)
                likes_text = likes_element.inner_text().strip() if likes_element else "0"
                likes = parse_number(likes_text)

                # 搜索结果页无评论/收藏数
                comments = 0
                collects = 0

                # 提取作者
                author_element = card.query_selector(AUTHOR_SELECTOR)
                author = author_element.inner_text().strip() if author_element else "未知作者"

                # 购买意愿检测
                purchase_intent = has_purchase_intent(title)

                # 提取URL：第一个 href 含 /explore/ 的 <a>
                url_element = card.query_selector("a[href*='/explore/']")
                if url_element:
                    url_href = url_element.get_attribute("href")
                    note_url = f"https://www.xiaohongshu.com{url_href}" if url_href.startswith("/") else url_href
                else:
                    continue
                
                # 检查是否已存在（简单去重）
                if any(note['url'] == note_url for note in notes):
                    continue
                    
                notes.append({
                    'keyword': keyword,
                    'title': title,
                    'likes': likes,
                    'comments': comments,
                    'collects': collects,
                    'author': author,
                    'url': note_url,
                    'purchase_intent': purchase_intent,
                })
                note_count += 1
                
            except Exception as e:
                print(f"解析笔记出错: {e}")
                continue
    
    return notes[:max_notes]

def main():
    """主爬取流程：共用一个浏览器实例，登录只做一次"""
    init_db()

    CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            executable_path=CHROME_PATH,
        )
        context = browser.new_context()

        # 登录处理（只做一次）
        cookies_loaded = load_cookies(context, COOKIES_PATH)
        page = context.new_page()

        if not cookies_loaded:
            page.goto("https://www.xiaohongshu.com")
            print("请在浏览器中扫码登录小红书，登录成功后按回车继续...")
            input()
            save_cookies(context, COOKIES_PATH)
            print("✅ Cookies 已保存，下次无需登录")
        else:
            # 带 cookies 直接跳到搜索页，无需等首页完全加载
            page.goto("https://www.xiaohongshu.com", timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)

        # 遍历所有关键词
        for keyword in XHS_KEYWORDS:
            print(f"\n🔍 开始爬取小红书关键词: {keyword}")
            try:
                search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
                page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_load_state("domcontentloaded")
                time.sleep(random.uniform(2, 3))

                notes = scroll_and_extract_notes(page, keyword, XHS_NOTES_PER_KEYWORD)

                for note in notes:
                    insert_xhs_note(
                        note['keyword'],
                        note['title'],
                        note['likes'],
                        note['comments'],
                        note['collects'],
                        note['author'],
                        note['url'],
                        note.get('purchase_intent', 0),
                    )
                    print(f"  ✅ [{keyword}] {note['title'][:30]} - 👍{note['likes']}")

                # 关键词之间随机延迟
                time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

            except Exception as e:
                print(f"  ❌ 爬取关键词 {keyword} 出错: {e}")
                continue

        browser.close()
    print("\n🎉 小红书爬取完成！")

if __name__ == "__main__":
    main()