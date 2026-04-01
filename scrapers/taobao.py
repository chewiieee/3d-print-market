from playwright.sync_api import sync_playwright
import time, random, re, json, os, sys
sys.path.insert(0, ".")
from config import TAOBAO_KEYWORDS, TAOBAO_PAGES_PER_KEYWORD, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from db import init_db, insert_taobao_product

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TAOBAO_COOKIES_PATH = "data/taobao_cookies.json"

# ========== CSS 选择器（淘宝经常改版，如果失效请更新这里） ==========
# 商品卡片：每个卡片是一个 <a class="doubleCardWrapperAdapt--..."> 链接
PRODUCT_CARD_SELECTOR = "a[class*='doubleCardWrapper']"
# 备选：用父容器 search-content-col
PRODUCT_CARD_SELECTOR_ALT = ".search-content-col > a"
# 标题
TITLE_SELECTOR = "[class*='title--']"
# 价格整数
PRICE_INT_SELECTOR = "[class*='priceInt']"
# 价格小数
PRICE_FLOAT_SELECTOR = "[class*='priceFloat']"
# 销量文本（如 "1000+人付款"）
SALES_SELECTOR = "[class*='realSales']"
# 店铺名
SHOP_SELECTOR = "[class*='shopNameText'], [class*='shopName']"
# 发货时间（如“24h发货”“48小时发货”“7天定制”）
SHIPPING_SELECTOR = "[class*='deliverTime'], [class*='deliveryTime'], [class*='delivery--'], [class*='service--']"
# 视频标记（有视频的展示卡片）
HAS_VIDEO_SELECTOR = "[class*='video'], [class*='Video'], video"
def save_cookies(context, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cookies = context.cookies()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

def load_cookies(context, path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    return False

def extract_monthly_sales(sales_text):
    if not sales_text:
        return None
    try:
        # "月销1234件" / "1234人付款" / "1234+人付款" / "1.2万+"
        text = sales_text.replace(',', '').replace('+', '')
        if '万' in text:
            m = re.search(r'([\d.]+)万', text)
            if m:
                return int(float(m.group(1)) * 10000)
        m = re.search(r'(\d+)', text)
        if m:
            return int(m.group(1))
        return None
    except:
        return None

def extract_price(card):
    try:
        int_el = card.query_selector(PRICE_INT_SELECTOR)
        float_el = card.query_selector(PRICE_FLOAT_SELECTOR)
        if int_el:
            int_part = int_el.inner_text().strip().replace(',', '')
            float_part = float_el.inner_text().strip().lstrip('.') if float_el else "0"
            return float(f"{int_part}.{float_part}")
    except:
        pass
    try:
        el = card.query_selector("[class*='price']")
        if el:
            txt = el.inner_text().strip()
            m = re.search(r'[\d,]+\.?\d*', txt.replace(',', ''))
            if m:
                return float(m.group())
    except:
        pass
    return 0.0

def parse_product_url(href):
    if not href:
        return None
    m = re.search(r'id=(\d+)', href)
    if m:
        return f"https://item.taobao.com/item.htm?id={m.group(1)}"
    return None

def find_cards(page):
    """尝试多种选择器找到商品卡片"""
    cards = page.query_selector_all(PRODUCT_CARD_SELECTOR)
    if cards:
        return cards
    cards = page.query_selector_all(PRODUCT_CARD_SELECTOR_ALT)
    return cards

def main():
    init_db()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=CHROME_PATH)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        # ===== 登录处理 =====
        cookies_loaded = load_cookies(context, TAOBAO_COOKIES_PATH)
        page = context.new_page()

        if not cookies_loaded:
            page.goto("https://login.taobao.com/", timeout=30000)
            print("=" * 50)
            print("请在浏览器中登录淘宝（扫码或账号密码）")
            print("登录成功后按回车继续...")
            print("=" * 50)
            input()
            save_cookies(context, TAOBAO_COOKIES_PATH)
            print("✅ 淘宝 Cookies 已保存")
        else:
            # 带 cookies 访问一次，让会话生效
            page.goto("https://www.taobao.com/", timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

        # ===== 爬取 =====
        for keyword in TAOBAO_KEYWORDS:
            print(f"\n🔍 开始爬取关键词: {keyword}")
            for page_num in range(1, TAOBAO_PAGES_PER_KEYWORD + 1):
                print(f"  📄 第 {page_num} 页...")
                try:
                    start_index = (page_num - 1) * 44
                    url = f"https://s.taobao.com/search?q={keyword}&s={start_index}"
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state("domcontentloaded")
                    # 等待真实商品渲染（骨架屏消失）
                    time.sleep(random.uniform(3, 5))

                    # 额外滚动触发懒加载
                    for _ in range(3):
                        page.evaluate("window.scrollBy(0, 800)")
                        time.sleep(0.5)

                    cards = find_cards(page)
                    if not cards:
                        print(f"  ⚠️ 未找到商品卡片（共0个），可能需要重新登录或更新选择器")
                        # 保存调试HTML
                        with open(f"data/debug_{keyword}_{page_num}.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                        continue

                    print(f"  📦 找到 {len(cards)} 个商品卡片")
                    for card in cards:
                        try:
                            title_el = card.query_selector(TITLE_SELECTOR)
                            title = title_el.inner_text().strip() if title_el else "未知"
                            if title == "未知" or len(title) < 2:
                                continue

                            price = extract_price(card)

                            sales_el = card.query_selector(SALES_SELECTOR)
                            sales_text = sales_el.inner_text().strip() if sales_el else ""
                            monthly_sales = extract_monthly_sales(sales_text)

                            shop_el = card.query_selector(SHOP_SELECTOR)
                            shop_name = shop_el.inner_text().strip() if shop_el else "未知"

                            # 发货时间
                            shipping_el = card.query_selector(SHIPPING_SELECTOR)
                            shipping_time = shipping_el.inner_text().strip() if shipping_el else None

                            # 是否有视频（卡片内存在video相关元素则为1）
                            has_video = 1 if card.query_selector(HAS_VIDEO_SELECTOR) else 0

                            # 卡片本身就是 <a> 标签，直接取 href
                            href = card.get_attribute("href")
                            if href and href.startswith("//"):
                                href = "https:" + href
                            product_url = parse_product_url(href)
                            if not product_url:
                                continue

                            insert_taobao_product(keyword, title, price, monthly_sales, None, shop_name, product_url,
                                                  shipping_time=shipping_time, has_video=has_video)
                            print(f"  ✅ {title[:30]} - ¥{price} - 月销: {monthly_sales or 'N/A'} - 发货: {shipping_time or '-'} - 视频: {'是' if has_video else '否'}")

                        except Exception as e:
                            print(f"  ⚠️ 解析出错: {e}")
                            continue

                    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

                except Exception as e:
                    print(f"  ❌ 爬取第 {page_num} 页出错: {e}")
                    continue

        browser.close()
    print("\n🎉 淘宝爬取完成！")

if __name__ == "__main__":
    main()