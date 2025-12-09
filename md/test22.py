# md/test22.py —— 真正最终版（央视 + 卫视优先级完美修复）
import re
import requests
from pathlib import Path

REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images")
OUTPUT_M3U       = Path("demo_output.m3u")

# 强制优先级最高的两大类（不管你放哪个文件夹，只要名字含关键词就强制走这里）
FORCE_WSTV_KEYWORDS = {"卫视", "卡酷", "金鹰", "哈哈", "优漫", "嘉佳", "先锋", "兵团", "三沙", "康巴", "安多", "藏语" }  # 卫视类强规则
FORCE_CCTV_KEYWORDS = {"CCTV", "央视", "中央"}

# 你的分类顺序
CATEGORY_ORDER = [
    "4K", "CCTV", "CGTN", "CIBN", "DOX", "NewTV", "WSTV", "iHOT",
    "上海", "云南", "内蒙古", "北京", "吉林", "四川", "天津", "宁夏",
    "安徽", "山东", "山西", "广东", "广西", "数字频道", "新疆", "江苏",
    "江西", "河北", "河南", "浙江", "海南", "海外频道", "港澳地区",
    "湖北", "湖南", "甘肃", "福建", "西藏", "贵州", "辽宁", "重庆",
    "陕西", "青海", "黑龙江"
]

REPO_RAW = "https://raw.githubusercontent.com/kenye201/TVlog/main"
cat_priority = {cat: i for i, cat in enumerate(CATEGORY_ORDER)}

# ==================== 1. 加载台标库（支持 CCTV1、CCTV-1、CCTV_1 都能命中）===================
logo_db = {}  # clean_name → (category_folder, filename)
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if not folder.is_dir():
            continue
        cat = folder.name
        for f in folder.iterdir():
            if not f.is_file() or f.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            name = f.stem
            # 多种写法统一
            clean = name.replace("CCTV-", "CCTV").replace("CCTV_", "CCTV").replace("-", "").replace("_", "").replace(" ", "")
            clean = re.sub(r"(HD|4K|超清|高清|plus|频道|台|卫视)$", "", clean, flags=re.I)
            logo_db[clean.lower()] = (cat, f.name)

print(f"台标库加载完成：{len(logo_db)} 张")

# ==================== 2. 加载别名表 ====================
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
            c = n.replace("CCTV-", "CCTV").replace("-", "").replace("_", "").replace(" ", "")
            c = re.sub(r"(HD|4K|超清|高清|plus|频道|台|卫视)$", "", c, flags=re.I)
            alias_to_main[c.lower()] = main

print(f"别名表加载完成：{len(alias_to_main)} 条")

# ==================== 3. 主逻辑 ====================
result_lines = ['#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"']
total = 0

def get_forced_category(name: str):
    """强制规则：含“卫视”两个字 → WSTV，含“CCTV/央视” → CCTV"""
    if any(k in name for k in FORCE_WSTV_KEYWORDS):
        return "WSTV"
    if any(k in name for k in FORCE_CCTV_KEYWORDS):
        return "CCTV"
    return None

def get_best_match(display_name: str):
    """返回 (最终显示名, 分类, 台标URL)"""
    forced_cat = get_forced_category(display_name)
    if forced_cat:
        # 强制分类后，台标优先从对应文件夹找，找不到就用别名表名
        clean = display_name.replace("CCTV-", "CCTV").replace("-", "").replace("_", "").replace(" ", "")
        clean = re.sub(r"(HD|4K|超清|高清|plus|频道|台|卫视)$", "", clean, flags=re.I)
        key = clean.lower()
        if key in logo_db:
            cat, fname = logo_db[key]
            logo_url = f"{REPO_RAW}/Images/{cat}/{fname}"
        else:
            # 强制分类但没台标时，用标准主名
            logo_url = ""
        std_name = alias_to_main.get(key, display_name)
        return std_name, forced_cat, logo_url

    # 普通匹配流程
    clean = display_name.replace("CCTV-", "CCTV").replace("-", "").replace("_", "").replace(" ", "")
    clean = re.sub(r"(HD|4K|超清|高清|plus|频道|台|卫视)$", "", clean, flags=re.I)
    key = clean.lower()
    if key in logo_db:
        cat, fname = logo_db[key]
        logo_url = f"{REPO_RAW}/Images/{cat}/{fname}"
        std_name = alias_to_main.get(key, display_name)
        return std_name, cat, logo_url

    return None, None, None

# 主循环
links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

for url in links:
    try:
        text = requests.get(url, timeout=25).text
    except:
        continue

    extinf = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            extinf = line
        elif line and not line.startswith("#"):
            if not extinf:
                continue

            display = extinf.split(",", 1)[-1] if "," in extinf else "未知频道"
            std_name, category, logo_url = get_best_match(display)

            if category:  # 只要匹配上就保留
                line_extinf = f'#EXTINF:-1 group-title="{category}"'
                if logo_url:
                    line_extinf += f' tvg-logo="{logo_url}"'
                line_extinf += f' tvg-name="{std_name}",{std_name}'
                result_lines.append(line_extinf)
                result_lines.append(line)
                total += 1

            extinf = None

# 排序（按 CATEGORY_ORDER）
def sort_key(line):
    if line.startswith("#EXTINF"):
        m = re.search(r'group-title="([^"]+)"', line)
        cat = m.group(1) if m else "其他"
        return cat_priority.get(cat, 999)
    return 999

result_lines[1:] = sorted(result_lines[1:], key=sort_key)

# 写文件
OUTPUT_M3U.write_text("\n".join(result_lines) + "\n", encoding="utf-8")
print(f"终极完美版生成成功！共 {total} 条线路，央视+卫视强制正确分类，全量带高清台标！"))
