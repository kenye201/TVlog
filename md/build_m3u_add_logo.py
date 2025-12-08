import re
from pathlib import Path
import os

INPUT_FILE = "output.m3u"
OUTPUT_FILE = "output_with_logo.m3u"
MISSING_LOGO_FILE = "missing_logos.txt"
TVLOGO_DIR = Path("TVlogo_Images")
BASE_LOGO_URL = "https://raw.githubusercontent.com/qunhui201/logo/main/TVlogo_Images"
PROVINCES = [
    "北京", "上海", "天津", "重庆", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽",
    "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "四川",
    "贵州", "云南", "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙", "西藏", "香港",
    "澳门", "台湾", "延边", "大湾区"
]

def normalize_name(name: str):
    """清理频道名，去掉 BTV、频道、高清"""
    return name.replace("BTV", "").replace("频道", "").replace("高清", "").strip()

def find_fuzzy_folder(name):
    """模糊匹配省份文件夹"""
    for folder in TVLOGO_DIR.iterdir():
        if folder.is_dir() and name in folder.name:
            return folder
    return None

def match_logo(channel_name, group_title):
    """匹配台标，支持模糊匹配"""
    logo_path = ""
    clean_name = normalize_name(channel_name)
    
    folder = None
    if group_title == "央视频道":
        folder = TVLOGO_DIR / "中央电视台"
    elif group_title == "卫视频道":
        folder = TVLOGO_DIR / "全国卫视"
    elif group_title == "地方频道":
        # 先匹配省份
        for province in PROVINCES:
            if province in channel_name:
                folder = TVLOGO_DIR / province
                if not folder.exists():
                    folder = find_fuzzy_folder(province)
                break
    
    # 文件夹存在则尝试模糊匹配
    if folder and folder.is_dir():
        for file in folder.iterdir():
            if not file.is_file():
                continue
            filename = file.stem
            if clean_name in filename or filename in clean_name:
                logo_path = f"{BASE_LOGO_URL}/{folder.name}/{file.name}"
                return logo_path

    # 其他频道全局模糊匹配
    if not logo_path:
        for folder in TVLOGO_DIR.iterdir():
            if not folder.is_dir():
                continue
            for file in folder.iterdir():
                if not file.is_file():
                    continue
                filename = file.stem
                if clean_name in filename or filename in clean_name:
                    logo_path = f"{BASE_LOGO_URL}/{folder.name}/{file.name}"
                    return logo_path

    return logo_path

def main():
    output_lines = ['#EXTM3U x-tvg-url="https://raw.githubusercontent.com/qunhui201/iptv-api/refs/heads/master/output/epg/epg.gz"']
    missing_logos = []

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            info = line
            url = lines[i + 1] if i + 1 < len(lines) else ""
            tvg_name = re.search(r'tvg-name="([^"]+)"', info)
            group_title = re.search(r'group-title="([^"]+)"', info)
            name = tvg_name.group(1) if tvg_name else ""
            group = group_title.group(1) if group_title else ""
            logo = match_logo(name, group)
            if not logo:
                missing_logos.append(f"{group} - {name}")
            output_lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
            output_lines.append(url)
            i += 2
        else:
            i += 1

    # 写入带台标的 m3u 文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")  # 强制末尾换行

    # 写入未匹配台标列表
    with open(MISSING_LOGO_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(missing_logos))

    print(f"✅ 已生成 {OUTPUT_FILE}")
    print(f"📺 共 {sum(1 for l in output_lines if l.startswith('#EXTINF'))} 个频道")
    print(f"⚠️ 未匹配台标的频道已保存至 {MISSING_LOGO_FILE}（共 {len(missing_logos)} 个）")

if __name__ == "__main__":
    main()
