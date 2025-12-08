import re
from pathlib import Path

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")  # 存放直播源 URL，每行一个
ALIAS_FILE = Path("md/alias.txt")         # 频道别名表
TVLOGO_DIR = Path("Images")                    # 台标文件夹，每个子文件夹为分类，里面是台标文件
OUTPUT_M3U = Path("demo_output.m3u")          # 输出 M3U 文件
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

# 读取远程链接列表
def load_remote_links(remote_file):
    links = []
    with open(remote_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                links.append(line)
    return links

# 生成 M3U 文件
def generate_m3u(links, alias_map, regex_map, tvlogo_dir, output_file):
    output_lines = ["#EXTM3U"]
    for link in links:
        # 从 URL 或文件名提取频道名，假设 URL 格式是 .../频道名.xxx
        # 也可自定义规则
        channel_name = Path(link).stem
        main_name = map_to_main_name(channel_name, alias_map, regex_map)
        category = match_logo_class(main_name, tvlogo_dir)
        # 写入 M3U
        output_lines.append(f'#CATEGORY:{category} #EXTINF:-1,{main_name}')
        output_lines.append(link)
    # 写入输出文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"✅ 已生成输出文件: {output_file}")

# -------------------- 主程序 --------------------
if __name__ == "__main__":
    alias_map, regex_map = load_alias_map(ALIAS_FILE)
    links = load_remote_links(REMOTE_FILE_PATH)
    generate_m3u(links, alias_map, regex_map, TVLOGO_DIR, OUTPUT_M3U)

