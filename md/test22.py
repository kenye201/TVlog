import re
import requests
from pathlib import Path

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")   # 远程源列表，每行一个 m3u 链接
ALIAS_FILE = Path("md/alias.txt")               # 别名表
TVLOGO_DIR = Path("img")                     # 台标目录
OUTPUT_M3U = Path("demo_output.m3u")              # 输出文件
# ---------------------------------------------

def load_alias_map(alias_file):
    alias_map = {}
    regex_map = []
    with open(alias_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",") if p.strip()]
            main_name = parts[0]
            for alias in parts[1:]:
                if alias.startswith("re:"):
                    try:
                        regex_map.append((re.compile(alias[3:], re.IGNORECASE), main_name))
                    except re.error as e:
                        print(f"正则错误: {alias[3:]} → {e}")
                else:
                    alias_map[alias.lower()] = main_name
    return alias_map, regex_map

def map_to_main_name(name, alias_map, regex_map):
    if not name:
        return "未知频道"
    key = name.lower()
    if key in alias_map:
        return alias_map[key]
    for pattern, main_name in regex_map:
        if pattern.search(name):        # 用 search 更宽松一些
            return main_name
    return name

def match_logo_class(main_name, tvlogo_dir):
    if not tvlogo_dir.exists():
        return "其他"
    for folder in tvlogo_dir.iterdir():
        if not folder.is_dir():
            continue
        for logo_file in folder.iterdir():
            if logo_file.is_file() and logo_file.stem.lower() == main_name.lower():
                return folder.name
    return "其他"

def download_m3u_content(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except Exception as e:
        print(f"下载失败 {url} → {e}")
        return None

def generate_m3u():
    alias_map, regex_map = load_alias_map(ALIAS_FILE)
    links = [l.strip() for l in open(REMOTE_FILE_PATH, encoding="utf-8") if l.strip()]

    output_lines = ["#EXTM3U x-tvg-url=\"https://live.fanmingming.com/e.xml\""]

    for url in links:
        content = download_m3u_content(url)
        if not content:
            continue

        lines = None
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line.startswith("#EXTINF:"):
                # 保留原始的 tvg-logo、tvg-name 等属性
                extinf = line
                # 提取频道显示名（逗号之后的部分）
                if "," in line:
                    display_name = line.split(",", 1)[1].strip()
                else:
                    display_name = "未知频道"

                # 映射标准名称 + 分类
                main_name = map_to_main_name(display_name, alias_map, regex_map)
                category = match_logo_class(main_name, TVLOGO_DIR)

                # 重新拼装正确的 EXTINF 行
                new_extinf = f'#EXTINF:-1 group-title="{category}" tvg-name="{main_name}",{main_name}'
                output_lines.append(new_extinf)
                extinf = None  # 等待下一行的 URL
            elif line and not line.startswith("#") and line.startswith("http"):
                # 这才是真正的播放地址
                if extinf is not None:  # 上一个 EXTINF 没配对到 URL（异常情况）
                    output_lines.append(extinf)  # 先把没地址的也写上
                output_lines.append(line)

    # 写入文件
    with open(OUTPUT_M3U, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(output_lines) + "\n")

    print(f"成功生成 {OUTPUT_M3U}，共 {len(output_lines)} 行")

if __name__ == "__main__":
    generate_m3u()
