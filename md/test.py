import requests
from bs4 import BeautifulSoup
from pathlib import Path
import urllib3

# 忽略SSL警告（如果站点证书有问题）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 主页面URL（2025年版本，根据年份可能变，如hoteliptv2024.php）
URL = "https://tonkiang.us/hoteliptv2025.php"  # 如果失效，试 https://tonkiang.us/ 或其他子页

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_hotel_sources():
    try:
        response = requests.get(URL, headers=HEADERS, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = 'utf-8'  # 确保中文不乱码
        print("✅ 页面抓取成功！")
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # 保存整个HTML（包含所有条目）
    output_file = Path("hotel_sources_full.html")
    output_file.write_text(response.text, encoding="utf-8")
    print(f"💾 完整页面已保存到 {output_file}")

    # 提取并解析列表条目（根据页面结构调整selector）
    sources = []
    # 常见结构：表格<tr>或<div class="item">
    for item in soup.find_all(['tr', 'div'], class_=['item', 'row', 'list-item']):  # 需根据实际调整
        ip = item.find(string=re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'))
        channels = item.find(string=re.compile(r'频道数'))
        region = item.find(string=re.compile(r'河南|北京|广东|酒店'))
        time = item.find(string=re.compile(r'\d{4}-\d{2}-\d{2}'))
        if ip:
            sources.append({
                "IP": ip.strip() if ip else "未知",
                "频道数": channels.strip() if channels else "未知",
                "地区": region.strip() if region else "未知",
                "上线时间": time.strip() if time else "未知"
            })

    # 保存解析后的文本列表
    txt_file = Path("hotel_sources_list.txt")
    with open(txt_file, "w", encoding="utf-8") as f:
        for s in sources:
            f.write(f"IP: {s['IP']} | 频道数: {s['频道数']} | 地区: {s['地区']} | 上线时间: {s['上线时间']}\n")
    print(f"✅ 解析并保存 {len(sources)} 条酒店源到 {txt_file}")

    # 示例：找到特定IP
    target_ip = "1.197.253.98"
    for s in sources:
        if target_ip in s['IP']:
            print(f"🎯 找到目标: {s}")

if __name__ == "__main__":
    fetch_hotel_sources()
