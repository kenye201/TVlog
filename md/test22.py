import re
import requests
from pathlib import Path
from collections import defaultdict, OrderedDict

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images")
OUTPUT_M3U       = Path("demo_output.m3u")

# 你的分类顺序（前面越靠前）
CATEGORY_ORDER = [
    "4K", "CCTV", "CGTN", "CIBN", "DOX", "NewTV", "WSTV", "iHOT",
    "上海", "云南", "内蒙古", "北京", "吉林", "四川", "天津", "宁夏",
    "安徽", "山东", "山西", "广东", "广西", "数字频道", "新疆", "江苏",
    "江西", "河北", "河南", "浙江", "海南", "海外频道", "港澳地区",
    "湖北", "湖南", "甘肃", "福建", "西藏", "贵州", "辽宁", "重庆",
    "陕西", "青海", "黑龙江"
]

REPO_URL = "https://raw.githubusercontent.com/kenye201/TVlog/main"   # 你的仓库地址
# ---------------------------------------------

# Step 1: 加载所有台标 → {标准化名字: (分类, 文件名.后缀)}
logo_db = {}
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if not folder.is_dir() or folder.name not in CATEGORY_ORDER:
            continue
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                clean = re.sub(r"[ _\-](HD|4K|超清|高清|plus|频道|台|卫视)$", "", file.stem, flags=re.I)
                clean = clean.replace(" ", "").replace("-", "").replace("_", "")
                logo_db[clean.lower()] = (folder.name, file.name)

print(f"台标库就绪：{len(logo_db)} 张 → {len(set(c for c,_ in logo_db.values()))} 个分类")

# Step 2: 加载 alias.txt → {所有别名标准化后: 主名}
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
            clean = re.sub(r"[ _\-](HD|4K|高清|超清|plus|频道|台|卫视)$", "", name, flags=re.I)
            clean = clean.replace(" ", "").replace("-", "").replace("_", "")
            alias_to_main[clean.lower()] = main

print(f"别名表就绪：{len(alias_to_main)} 条")

# Step 3: 全局去重表：标准名 → (分类, 台标相对路径, 播放URL)
final_channels = OrderedDict()

def normalize_name(raw: str) -> str:
    s = raw.strip()
    cleaned = re.sub(r"[ _\-](HD|4K|高清|超清|plus|频道|台|卫视)$", "", s, flags=re.I)
    cleaned = cleaned.replace(" ", "").replace("-", "").replace("_", "")
    return alias_to_main.get(cleaned.lower(), s.split()[0] if s.split() else s)

# 主程序
def main():
    links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

    for url in links:
        try:
            text = requests.get(url, timeout=20).text
        except:
            continue

        extinf = None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#EXTINF:"):
                extinf = line
            elif line and not line.startswith("#"):
                if not extinf: 
                    continue

                display_name = extinf.split(",", 1)[-1] if "," in extinf else "未知"
                std_name = normalize_name(display_name)                     # 最终显示的名字

                cleaned_key = re.sub(r"[ _\-](HD|4K|高清|超清|plus|频道|台|卫视)$", "", display_name, flags=re.I)
                cleaned_key = cleaned_key.replace(" ", "").replace("-", "").replace("_", "").lower()

                if cleaned_key in logo_db:
                    cat, logo_file = logo_db[cleaned_key]
                    logo_url = f"{REPO_URL}/Images/{cat}/{logo_file}"

                    # 同一个频道保留第一个出现的链接（或你可以后面再加存活检测选最快的）
                    if std_name not in final_channels:
                        new_extinf = f'#EXTINF:-1 group-title="{cat}" tvg-logo="{logo_url}" tvg-name="{std_name}",{std_name}'
                        final_channels[std_name] = (cat, new_extinf, line)

                extinf = None

    # 按分类顺序写文件
    result = ['#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"']
    for cat in CATEGORY_ORDER:
        for name, (c, extinf, url) in final_channels.items():
            if c == cat:
                result.append(extinf)
                result.append(url)

    OUTPUT_M3U.write_text("\n".join(result) + "\n", encoding="utf-8")
    print(f"最终大功告成！去重后保留 {len(final_channels)} 个频道，全带在线台标，分类排序完美！")

if __name__ == "__main__":
    main()
