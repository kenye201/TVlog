# md/test22.py —— 宇宙最稳终极版（永不乱套，2025.12.08 封笔之作）
import re
import requests
from pathlib import Path

REMOTE_FILE_PATH = Path("md/httop_links.txt")
TVLOGO_DIR       = Path("Images")
OUTPUT_M3U       = Path("demo_output.m3u")
REPO_RAW = "https://raw.githubusercontent.com/kenye201/TVlog/main"

# 分类排序
CATEGORY_ORDER = ["4K","CCTV","CGTN","CIBN","DOX","NewTV","WSTV","iHOT",
    "上海","云南","内蒙古","北京","吉林","四川","天津","宁夏",
    "安徽","山东","山西","广东","广西","数字频道","新疆","江苏",
    "江西","河北","河南","浙江","海南","海外频道","港澳地区",
    "湖北","湖南","甘肃","福建","西藏","贵州","辽宁","重庆",
    "陕西","青海","黑龙江"]

# 1. 加载台标库（按文件夹存，精准匹配
logo_db = {}  # cat -> {文件名大写: 文件名}
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if not folder.is_dir(): continue
        cat = folder.name
        logo_db[cat] = {}
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in {".png",".jpg",".jpeg",".webp"}:
                key = f.stem.upper()
                logo_db[cat][key] = f.name
                logo_db[cat][key.replace("_","")] = f.name
                logo_db[cat][re.sub(r"[-_ .]","",key)] = f.name

print(f"台标库加载完成，共 {sum(len(v) for v in logo_db.values())} 张")

# 2. 最终结果：成对保存（EXTINF + URL）
paired）
paired = []
total = 0

links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

for url in links:
    try:
        text = requests.get(url, timeout=30).text
    except:
        continue

    extinf = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            extinf = line
        elif line and not line.startswith("#"):
            if not extinf: continue

            raw_name = extinf.split(",",1)[-1] if "," in extinf else ""
            name_upper = raw_name.upper()

            # 情况1：纯数字频道 → 原样保留
            if raw_name.strip().isdigit() or raw_name.strip() == "":
                paired.append((9999, extinf, line))
                total += 1
                extinf = None
                continue

            # 情况2：央视强制进 CCTV
            if any(x in name_upper for x in ["CCTV","央视","中央","CGTN"]):
                group = "CCTV"
            # 情况3：卫视只看“卫视”二字
            elif "卫视" in name_upper:
                group = "WSTV"
            # 情况4：其他频道 → 按台标实际所在文件夹
            else:
                group = "其他"
                logo_url = ""
                for cat, names in logo_db.items():
                    clean = re.sub(r"[-_ .]","", name_upper)
                    if name_upper in names or clean in names:
                        group = cat
                        logo_url = f"{REPO_RAW}/Images/{cat}/{names[name_upper] if name_upper in names else names[clean]}"
                        break

                # 没台标时保留原 group-title
                if group == "其他":
                    m = re.search(r'group-title="([^"]+)"', extinf)
                    if m:
                        group = m.group(1)

            # 构造新EXTINF（保留原始所有属性，只改 group-title 和加 tvg-logo）
            new_line = extinf.split(",",1)[0]
            new_line = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', new_line)
            if 'group-title=' not in new_line:
                new_line += f' group-title="{group}"'

            # 加台标（只在非央视卫视时加，央视卫视用自己文件夹的图）
            if group not in ["CCTV","WSTV"]:
                if 'logo_url' in locals() and logo_url:
                    if 'tvg-logo=' not in new_line:
                        new_line += f' tvg-logo="{logo_url}"'
            else:
                # 央视和卫视也尝试打自己文件夹的图
                if group in logo_db:
                    clean = re.sub(r"[-_ .]","", name_upper)
                    if name_upper in logo_db[group]:
                        logo_url = f"{REPO_RAW}/Images/{group}/{logo_db[group][name_upper]}"
                    elif clean in logo_db[group]:
                        logo_url = f"{REPO_RAW}/Images/{group}/{logo_db[group][clean]}"
                    else:
                        logo_url = ""
                    if logo_url and 'tvg-logo=' not in new_line:
                        new_line += f' tvg-logo="{logo_url}"'

            new_line += f',{raw_name}'

            # 排序权重
            weight = CATEGORY_ORDER.index(group) if group in CATEGORY_ORDER else 9999
            paired.append((weight, new_line, line))
            total += 1
            extinf = None

# 排序 + 写入
paired.sort(key=lambda x: x[0])
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n')
    for _, e, u in paired:
        f.write(e + "\n")
        f.write(u + "\n")

print(f"宇宙最稳版完成！共 {total} 条线路，标题链接永不分离，央视卫视精准，其余按文件夹，纯数字全保")
