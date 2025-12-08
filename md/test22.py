# md/test22.py  —— 终极全量版（多线路全保留 + 自动打台标 + 分类排序）
import re
import requests
from pathlib import Path

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images")
OUTPUT_M3U         = Path("demo_output.m3u")

# 分类显示顺序（前面越靠前）
CATEGORY_ORDER = [
    "4K", "CCTV", "CGTN", "CIBN", "DOX", "NewTV", "WSTV", "iHOT",
    "上海", "云南", "内蒙古", "北京", "吉林", "四川", "天津", "宁夏",
    "安徽", "山东", "山西", "广东", "广西", "数字频道", "新疆", "江苏",
    "江西", "河北", "河南", "浙江", "海南", "海外频道", "港澳地区",
    "湖北", "湖南", "甘肃", "福建", "西藏", "贵州", "辽宁", "重庆",
    "陕西", "青海", "黑龙江"
]

REPO_RAW = "https://raw.githubusercontent.com/kenye201/TVlog/main"
# ---------------------------------------------

# 1. 加载台标库
logo_db = {}
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if not folder.is_dir():
            continue
        cat = folder.name
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                clean = re.sub(r"[ _\-](HD|4K|超清|高清|plus|频道|台|卫视)$", "", f.stem, flags=re.I)
                clean = clean.replace(" ", "").replace("-", "").replace("_", "")
                logo_db[clean.lower()] = (cat, f.name)

print(f"台标库加载完成：{len(logo_db)} 张")

# 2. 加载别名表
alias_to_main = {}
if ALIAS_FILE.exists():
    for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if not parts:
            continue
        main = parts[0]
        for name in parts:
            clean = re.sub(r"[ _\-](HD|4K|超清|高清|plus|频道|台|卫视)$", "", name, flags=re.I)
            clean = clean.replace(" ", "").replace("-", "").replace("_", "")
            alias_to_main[clean.lower()] = main

print(f"别名表加载完成：{len(alias_to_main)} 条")

# 3. 分类排序权重
cat_priority = {cat: i for i, cat in enumerate(CATEGORY_ORDER)}

# 收集所有匹配成功的行
temp_lines = []
total_count = 0

def normalize(name: str) -> str:
    s = name.strip()
    cleaned = re.sub(r"[ _\-](HD|4K|超清|高清|标清|plus|频道|台|卫视)$", "", s, flags=re.I)
    cleaned = cleaned.replace(" ", "").replace("-", "").replace("_", "")
    return alias_to_main.get(cleaned.lower(), cleaned)

# 主循环
links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

for url in links:
    try:
        text = requests.get(url, timeout=25).text
    except Exception as e:
        print(f"下载失败 {url} → {e}")
        continue

    extinf = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            extinf = line
        elif line and not line.startswith("#"):
            if not extinf:
                continue

            display_name = extinf.split(",", 1)[-1] if "," in extinf else "未知频道"
            key = normalize(display_name)

            if key.lower() in logo_db:
                cat, logo_file = logo_db[key.lower()]
                logo_url = f"{REPO_RAW}/Images/{cat}/{logo_file}"
                show_name = alias_to_main.get(key.lower(), display_name.split()[0] if display_name.split() else display_name)

                new_extinf = f'#EXTINF:-1 group-title="{cat}" tvg-logo="{logo_url}" tvg-name="{show_name}",{show_name}'
                temp_lines.append(new_extinf)
                temp_lines.append(line)
                total_count += 1

            extinf = None

# 按分类顺序排序
def sort_key(line):
    if not line.startswith("#EXTINF"):
        return (9999, line)
    m = re.search(r'group-title="([^"]+)"', line)
    cat = m.group(1) if m else "其他"
    return (cat_priority.get(cat, 999), line)

temp_lines.sort(key=sort_key)

# 写文件
final_content = '#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n' + "\n".join(temp_lines) + "\n"
OUTPUT_M3U.write_text(final_content, encoding="utf-8")

print(f"全量合集生成完毕！共 {total_count} 条线路（多源全保留），全部带台标，已按分类完美排序！")
