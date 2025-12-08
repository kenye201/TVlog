# md/test22.py  —— 绝对最终版（再也不用改了！）
import re
import requests
from pathlib import Path

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images")
OUTPUT_M3U       = Path("demo_output.m3u")

# 分类顺序（前面越靠前）
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
        for n in parts:
            c = re.sub(r"[ _\-](HD|4K|超清|高清|plus|频道|台|卫视)$", "", n, flags=re.I)
            c = c.replace(" ", "").replace("-", "").replace("_", "")
            alias_to_main[c.lower()] = main

print(f"别名表加载完成：{len(alias_to_main)} 条")

# 3. 收集所有匹配成功的频道（带播放地址！）
result = ['#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"']
total = 0
cat_weight = {cat: i for i, cat in enumerate(CATEGORY_ORDER)}

def normalize(s: str) -> str:
    c = re.sub(r"[ _\-](HD|4K|超清|高清|标清|plus|频道|台|卫视)$", "", s, flags=re.I)
    c = c.replace(" ", "").replace("-", "").replace("_", "")
    return alias_to_main.get(c.lower(), c)

# 开始遍历所有源
links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

for url in links:
    try:
        text = requests.get(url, timeout=25).text
    except Exception:
        continue

    extinf = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            extinf = line
        elif line and not line.startswith("#"):
            if not extinf:
                continue

            display = extinf.split(",", 1)[-1] if "," in extinf else "未知"
            key = normalize(display)

            if key.lower() in logo_db:
                cat, logo_file = logo_db[key.lower()]
                logo_url = f"{REPO_RAW}/Images/{cat}/{logo_file}"
                show_name = alias_to_main.get(key.lower(), display)

                new_line = f'#EXTINF:-1 group-title="{cat}" tvg-logo="{logo_url}" tvg-name="{show_name}",{show_name}'
                weight = cat_weight.get(cat, 999)
                result.append((weight, new_line, line))   # 存三元组用于排序
                total += 1

            extinf = None

# 按分类顺序排序后写入
result[1:] = sorted(result[1:], key=lambda x: x[0])

with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.write(result[0] + "\n")                     # 写入头部
    for _, extinf_line, url_line in result[1:]:
        f.write(extinf_line + "\n")
        f.write(url_line + "\n")

print(f"生成成功！共 {total} 条真实线路，全带高清台标，已按分类完美排序！")
