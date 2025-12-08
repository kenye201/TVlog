import re
import requests
from pathlib import Path

# -------------------- 配置 --------------------
REMOTE_FILE_URL = "https://httop.top/hotel.m3u"  # 直播源文件 URL
ALIAS_FILE = Path("md/alias.txt")  # 频道别名表
TVLOGO_DIR = Path("Images")  # 台标文件夹，每个子文件夹为分类，里面是台标文件
OUTPUT_M3U = Path("demo_output.m3u")  # 输出 M3U 文件
# ---------------------------------------------

# 解析别名表
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
                    pattern = alias[3:]
                    try:
                        compiled = re.compile(pattern, re.IGNORECASE)
                        regex_map.append((compiled, main_name))
                    except re.error:
                        print(f"⚠️ 正则编译失败: {pattern}")
                else:
                    alias_map[alias.lower()] = main_name
    return alias_map, regex_map

# 将频道名映射为主名
def map_to_main_name(name, alias_map, regex_map):
    if not name:
        return name
    key = name.lower()
    if key in alias_map:
        return alias_map[key]
    for regex, main_name in regex_map:
        if regex.fullmatch(name):
            return main_name
    return name

# 根据台标匹配分类
def match_logo_class(main_name, tvlogo_dir):
    for folder in tvlogo_dir.iterdir():
        if not folder.is_dir():
            continue
        for logo_file in folder.iterdir():
            if not logo_file.is_file():
                continue
            filename = logo_file.stem
            if filename.lower() == main_name.lower():
                return folder.name
    return "其他频道"

# 下载远程 M3U 文件内容
def download_m3u_file(url):
    response = requests.get(url)
    response.raise_for_status()  # 如果请求失败会抛出异常
    return response.text.splitlines()

# 生成 M3U 文件
def generate_m3u(links, alias_map, regex_map, tvlogo_dir, output_file):
    output_lines = ["#EXTM3U"]
    for line in links:
        # 跳过空行或注释行
        if not line or line.startswith("#"):
            continue
        # 解析 M3U 文件中的频道信息
        match = re.match(r'#EXTINF:-1\s+tvg-name="([^"]+)"\s+group-title="([^"]+)",(.+)', line)
        if match:
            tvg_name = match.group(1)
            group_title = match.group(2)
            channel_name = match.group(3).strip()

            # 映射频道名称
            main_name = map_to_main_name(channel_name, alias_map, regex_map)
            category = match_logo_class(main_name, tvlogo_dir)

            # 写入 M3U 格式
            output_lines.append(f'#CATEGORY:{category} #EXTINF:-1 tvg-name="{tvg_name}" group-title="{group_title}",{main_name}')
            output_lines.append(line.split(',')[1].strip())  # M3U 文件中的 URL
        else:
            print(f"⚠️ 无法解析行: {line}")

    # 写入输出文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"✅ 已生成输出文件: {output_file}")

# -------------------- 主程序 --------------------
if __name__ == "__main__":
    alias_map, regex_map = load_alias_map(ALIAS_FILE)
    links = download_m3u_file(REMOTE_FILE_URL)
    generate_m3u(links, alias_map, regex_map, TVLOGO_DIR, OUTPUT_M3U)
