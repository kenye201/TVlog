# md/test22.py   ← 直接覆盖原文件
import re
import requests
from pathlib import Path
from collections import defaultdict

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images")
OUTPUT_M3U       = Path("demo_output.m3u")

# 你的分类显示顺序（前面越靠前）
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

# Step 1: 加载台标数据库 → {标准化名字: (分类, 完整文件名)}
logo_db = {}
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if not folder.is_dir():
            continue
        cat = folder.name
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in {".png",".jpg",".jpeg",".webp"}:
                clean = re.sub(r"[ _\-](HD|4K|超清|高清|plus|频道|台|卫视)$", "", f.stem, flags=re.I)
                clean = clean.replace(" ","").replace("-","").replace("_","")
                logo_db[clean.lower()] = (cat, f.name)   # 保存完整 Path 对象，后面取名字用

print(f"台标库加载完成：{len(logo_db)} 张")

# Step 2: 加载别名表 → 把所有别名统一映射到主名（提升命中率）
alias_to_main = {}
if ALIAS_FILE.exists():
    for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if not parts: continue
        main = parts[0]
        for name in parts:
            clean = re.sub(r"[ _\-](HD|4K|高清|超清|plus|频道|台|卫视)$", "", name, flags=re.I)
            clean = clean.replace(" ","").replace("-","").replace("_","")
            alias_to_main[clean.lower()] = main

print(f"别名表加载完成：{len(alias_to_main)} 条")

# Step 3: 用来排序的辅助字典
cat_priority = {cat: i for i, cat in enumerate(CATEGORY_ORDER)}

# 最终结果列表
result_lines = ['#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"']
total_count = 0

def normalize(name: str) -> str:
    """把任意名字标准化，尽量命中台标库"""
    s = name.strip()
    cleaned = re.sub(r"[ _\-](HD|4K|超清|高清|标清|plus|频道|台|卫视)$", "", s, flags=re.I)
    cleaned = cleaned.replace(" ","").replace("-","").replace("_","")
    return alias_to_main.get(cleaned.lower(), cleaned)

# 主程序开始
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

            # 提取显示名（,后面的部分）
            display_name = extinf.split(",", 1)[-1] if "," in extinf else "未知频道"

            key = normalize(display_name)
            if key.lower() in logo_db:                              # 命中台标！
                cat, logo_path_obj = logo_db[key.lower()]
                logo_url = f"{REPO_RAW}/Images/{cat}/{logo_path_obj.name}"

                # 用别名表里的主名作为最终显示名（最规范）
                final_show_name = alias_to_main.get(key.lower(), display_name.split()[0] if display_name.split() else display_name)

                new_extinf = f'#EXTINF:-1 group-title="{cat}" tvg-logo="{logo_url}" tvg-name="{final_show_name}",{final_show_name}'
                result_lines.append(new_extinf)
                result_lines.append(line)
                total_count += 1

            extinf = None

# 按分类顺序排序（同分类内保持原始出现顺序）
def sort_key(line):
    if not line.startswith('#EXTINF'): return (999, line)
    m = re.search(r'group-title="([^"]+)"', line)
    cat = m.group(1) if m else "其他"
    return (cat_priority.get(cat, 999), line)

result_lines[1:] = sorted(result_lines[1:], key=lambda x: sort_key(x))

# 写文件
OUTPUT_M3U.write_text("\n".join(result_lines) + "\n", encoding="utf-8")
print(f"全量合集生成完毕！共 {total_count} 条线路（一个频道多条线路并存），全部带正确台标和分类排序"))
