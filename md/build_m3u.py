import os
import re
import requests
from pathlib import Path
from collections import defaultdict

TVLOGO_DIR = Path("TVlogo_Images")
OUTPUT_FILE = "output.m3u"
TVBOX_TXT_FILE = "tvbox_output.txt"
OUTPUT_WITH_LOGO_FILE = "output_with_logo.m3u"
MISSING_LOGOS_FILE = "missing_logos.txt"
REMOTE_FILE_PATH = Path("md/httop_links.txt")

PROVINCES = [
    "北京","上海","天津","重庆","辽宁","吉林","黑龙江","江苏","浙江","安徽",
    "福建","江西","山东","河南","湖北","湖南","广东","广西","海南","四川",
    "贵州","云南","陕西","甘肃","青海","宁夏","新疆","内蒙","西藏","香港",
    "澳门","台湾","延边","大湾区"
]
SPECIAL_CHANNELS = {"CCTV17": "央视频道"}

# 新增：频道简称映射表（用于地方频道判定）
PREFIX_MAP = {
    "BTV": "北京",
    "JSTV": "江苏",
    "GDTV": "广东",
    "HNTV": "湖南",
    "SDTV": "山东",
    "LNTV": "辽宁",
    "HLJTV": "黑龙江",
    "ZJTV": "浙江",
    "CQTV": "重庆",
    "CCTV": "央视频道",
}

def is_content_changed(file_path, new_content):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            old_content = f.read()
            return old_content != new_content
    return True

def download_m3u(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text

def parse_m3u(content):
    lines = content.splitlines()
    result = []
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF"):
            info = lines[i]
            url = lines[i+1] if i+1 < len(lines) else ""
            tvg_name = re.search(r'tvg-name="([^"]+)"', info)
            group_title = re.search(r'group-title="([^"]+)"', info)
            tvg_logo = re.search(r'tvg-logo="([^"]+)"', info)
            name = tvg_name.group(1) if tvg_name else ""
            grp = group_title.group(1) if group_title else ""
            logo = tvg_logo.group(1) if tvg_logo else ""
            result.append((name, url, grp, logo))
    return result

def classify_channel(name, original_group, tvlogo_dir):
    # 特殊频道直接分类
    for key, val in SPECIAL_CHANNELS.items():
        if key in name:
            return val

    # 简称前缀匹配（优先）
    for prefix, province in PREFIX_MAP.items():
        if name.upper().startswith(prefix):
            if province == "央视频道":
                return "央视频道"
            return "地方频道"

    # 省份名匹配
    for province in PROVINCES:
        if province in name and "卫视" not in name:
            return "地方频道"

    # 卫视频道
    if "卫视" in name:
        return "卫视频道"

    # 台标文件夹匹配
    for folder in tvlogo_dir.iterdir():
        if not folder.is_dir():
            continue
        folder_name = folder.name
        if folder_name in ["央视频道", "卫视频道", "地方频道"]:
            continue
        for logo_file in folder.iterdir():
            if not logo_file.is_file():
                continue
            filename = logo_file.stem
            ch_name = re.sub(r'^[A-Za-z0-9\+\-]+', '', filename)
            if ch_name and ch_name in name:
                return folder_name

    return "其他频道"

def generate_tvbox_txt(channels):
    grouped = defaultdict(list)
    for name, url, grp, logo in channels:
        final_group = classify_channel(name, grp, TVLOGO_DIR)
        grouped[final_group].append((name, url))

    lines = []
    for group in grouped:
        lines.append(f"📺{group},#genre#")
        for name, url in grouped[group]:
            lines.append(f"{name},{url}")

    new_tvbox_content = "\n".join(lines)
    if is_content_changed(TVBOX_TXT_FILE, new_tvbox_content):
        with open(TVBOX_TXT_FILE, "w", encoding="utf-8") as f:
            f.write(new_tvbox_content)
        print(f"✅ 已生成 {TVBOX_TXT_FILE}, 共 {len(channels)} 个频道")
    else:
        print(f"⚠️ 文件内容无变化，未生成 {TVBOX_TXT_FILE}")

def generate_output_with_logo(channels):
    out_lines = ["#EXTM3U"]
    missing_logos = []
    for name, url, grp, logo in channels:
        final_group = classify_channel(name, grp, TVLOGO_DIR)
        if not logo:
            missing_logos.append(f"{name}: {url}")
            out_lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{final_group}",{name}')
        else:
            out_lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{final_group}",{name}')
        out_lines.append(url)

    new_output_with_logo_content = "\n".join(out_lines)
    if is_content_changed(OUTPUT_WITH_LOGO_FILE, new_output_with_logo_content):
        with open(OUTPUT_WITH_LOGO_FILE, "w", encoding="utf-8") as f:
            f.write(new_output_with_logo_content)
        print(f"✅ 已生成 {OUTPUT_WITH_LOGO_FILE}, 共 {len(channels)} 个频道")
    else:
        print(f"⚠️ 文件内容无变化，未生成 {OUTPUT_WITH_LOGO_FILE}")

    if missing_logos:
        with open(MISSING_LOGOS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(missing_logos))
        print(f"⚠️ 未匹配台标的频道已保存至 {MISSING_LOGOS_FILE}, 共 {len(missing_logos)} 个频道")

def main():
    if not REMOTE_FILE_PATH.exists():
        raise FileNotFoundError(f"{REMOTE_FILE_PATH} 不存在，请先运行 httop_crawler.py 获取最新 m3u 链接")

    with open(REMOTE_FILE_PATH, "r", encoding="utf-8") as f:
        REMOTE_FILES = [line.strip() for line in f if line.strip()]

    all_channels = []
    for url in REMOTE_FILES:
        content = download_m3u(url)
        channels = parse_m3u(content)
        all_channels.extend(channels)

    out_lines = ["#EXTM3U"]
    for name, url, grp, logo in all_channels:
        final_group = classify_channel(name, grp, TVLOGO_DIR)
        out_lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{final_group}",{name}')
        out_lines.append(url)

    new_output_content = "\n".join(out_lines)
    if is_content_changed(OUTPUT_FILE, new_output_content):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(new_output_content)
        print(f"✅ 已生成 {OUTPUT_FILE}, 共 {len(all_channels)} 个频道")
    else:
        print(f"⚠️ 文件内容无变化，未生成 {OUTPUT_FILE}")

    generate_output_with_logo(all_channels)
    generate_tvbox_txt(all_channels)

if __name__ == "__main__":
    main()
