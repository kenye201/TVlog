import re
import requests
from pathlib import Path
from collections import defaultdict

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR        = Path("Images")
OUTPUT_M3U        = Path("demo_output.m3u")

# 你全部 38 个分类的正确顺序（前面 = 越靠前）
CATEGORY_ORDER = [
    "4K", "CCTV", "CGTN", "CIBN", "DOX", "NewTV", "WSTV", "iHOT",
    "上海", "云南", "内蒙古", "北京", "吉林", "四川", "天津", "宁夏",
    "安徽", "山东", "山西", "广东", "广西", "数字频道", "新疆", "江苏",
    "江西", "河北", "河南", "浙江", "海南", "海外频道", "港澳地区",
    "湖北", "湖南", "甘肃", "福建", "西藏", "贵州", "辽宁", "重庆",
    "陕西", "青海", "黑龙江"
]
# ---------------------------------------------

# 预扫描所有台标文件 → {标准频道名: 分类文件夹名}
logo_db = {}
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if not folder.is_dir():
            continue
        cat = folder.name
        for pic in folder.iterdir():
            if pic.is_file() and pic.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                name = pic.stem                     # 去掉后缀
                # 同时支持 CCTV1 和 CCTV-1 这两种文件名写法
                clean_names = {
                    name,
                    name.replace("-", ""),
                    name.replace(" ", ""),
                    name.replace("_", ""),
                }
                for n in clean_names:
                    logo_db[n.lower()] = cat

print(f"台标库加载完成，共 {len(logo_db)} 张台标，覆盖 {len(set(logo_db.values()))} 个分类")

# 加载别名表（可选）
alias_map = {}
if ALIAS_FILE.exists():
    for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        main = parts[0]
        for a in parts[1:]:
            if a.startswith("re:"):
                continue                              # 本版本不需要正则，台标文件名为主
            alias_map[a.lower()] = main

def get_standard_name(raw_name: str) -> str:
    """把原始频道名映射成我们在 Images 里用的标准文件名"""
    s = raw_name.strip()
    # 先走别名表
    if s.lower() in alias_map:
        s = alias_map[s.lower()]

    # 常见后缀清理
    s = re.sub(r"[ _\-]?(HD|4K|超清|高清|标清|plus|频道|台|卫视|国际|纪录|戏曲|少儿|音乐|新闻)$", "", s, flags=re.I)
    s = s.strip(" -_")

    # 生成几种常见变体，增加命中率
    variants = {
        s,
        s.replace(" ", ""),
        s.replace("-", ""),
        s.replace("_", ""),
        s.replace("CCTV", "CCTV"),
    }
    return list(variants)

def main():
    links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

    channels = defaultdict(list)        # cat → [(extinf, url), ...]
    total_found = 0

    for url in links:
        try:
            text = requests.get(url, timeout=20).text
        except:
            continue

        cur_extinf = None
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("#EXTINF:"):
                cur_extinf = line
            elif line and not line.startswith("#"):
                if not cur_extinf:
                    continue

                # 提取显示名
                display = cur_extinf.split(",", 1)[-1] if "," in cur_extinf else "未知频道"

                # 尝试各种写法去 logo_db 里找
                found = False
                for variant in get_standard_name(display):
                    key = variant.lower()
                    if key in logo_db:
                        cat = logo_db[key]
                        std_name = next((v for v in get_standard_name(display) if v.lower() == key), display)
                        new_line = f'#EXTINF:-1 group-title="{cat}" tvg-name="{std_name}",{std_name}'
                        channels[cat].append((new_line, line))
                        total_found += 1
                        found = True
                        break
                cur_extinf = None

    # 严格按 CATEGORY_ORDER 顺序写文件
    result = ['#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"']

    for cat in CATEGORY_ORDER:
        if cat in channels:
            for extinf, url in channels[cat]:
                result.append(extinf)
                result.append(url)

    OUTPUT_M3U.write_text("\n".join(result) + "\n", encoding="utf-8")
    print(f"精选完成！只保留有台标的频道，共 {total_found} 个，已完美分类排序 → {OUTPUT_M3U}")

if __name__ == "__main__":
    main()
