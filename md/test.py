import requests
import time
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://tonkiang.us/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def fetch_hotel_page(url, retries=5):
    for i in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
            if response.status_code == 200:
                print("✅ 抓取成功！")
                return response.text
            elif response.status_code == 403:
                print(f"⚠️ 403 Forbidden，尝试第 {i+2} 次（等待 {2**(i+1)} 秒）...")
            elif response.status_code == 503:
                print(f"⚠️ 503 Unavailable，服务器维护中，第 {i+2} 次重试...")
        except Exception as e:
            print(f"❌ 请求异常: {e}")
        
        time.sleep(2 ** (i + 1))  # 指数退避：2s, 4s, 8s...
    print("❌ 多次尝试失败，网站可能长期不可用")
    return None

# 使用示例
html = fetch_hotel_page("https://tonkiang.us/iptvhotel.php")
if html:
    # 保存或解析...
    Path("hotel_page.html").write_text(html, encoding="utf-8")
