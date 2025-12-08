import requests
from bs4 import BeautifulSoup
import os

URL = "https://httop.top/"
OUTPUT_PATH = "md/httop_links.txt"
os.makedirs("md", exist_ok=True)

try:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []
    link_rows = soup.find_all("div", class_="link-row")
    for row in link_rows:
        link = row.get("data-copy")
        if link and link.endswith(".m3u"):
            results.append(link)

    # 保存为每行一个链接，方便 build 脚本逐行读取
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(results))

    print(f"提取成功，共 {len(results)} 条 m3u 链接。已保存至 {OUTPUT_PATH}")

except Exception as e:
    print(f"抓取失败: {e}")
