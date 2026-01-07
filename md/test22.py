import re
import requests
from pathlib import Path
import os
import sys
from collections import defaultdict

# 禁用 SSL 警告（忽略过期证书等）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -------------------- 配置 --------------------
# 链接文件路径（每行一个 m3u 链接，支持 # 注释）
LINKS_FILE_PATH = Path("md/httop_links.txt")

# 可选：保存原始下载的 m3u 文件（推荐保留，便于备份和调试）
SAVE_ORIGINAL_PATH = Path("md/hotel_original.m3u")

ALIAS_FILE = Path("md/alias.txt")
TVLOGO_DIR = Path("Images")
IMG_DIR = Path("img")
OUTPUT_M3U = Path("demo_output.m3u")
OUTPUT_TXT = Path("tvbox_output.txt")
REPO_RAW = "https://raw.githubusercontent.com/kenye201/TVlog/main"

# 内部代号 到 显示名 映射
GROUP_MAPPING = {
    "CCTV": "央视频道",
    "WSTV": "卫视频道",
    "CGTN": "国际频道",
    "DOX": "求索系列",
    "NewTV": "新视听",
    "iHOT": "iHOT系列",
    "img": "地方频道",
    "其他": "其它频道"
}

# 分类排序顺序
CATEGORY_ORDER = ["4K","央视频道","卫视频道","国际频道","CIBN","求索系列","新视听","iHOT系列",
    "上海","云南","内蒙古","北京","吉林","四川","天津","宁夏",
    "安徽","山东","山西","广东","广西","数字频道","新疆","江苏",
    "江西","河北","河南","浙江","海南","海外频道","港澳地区",
    "湖北","湖南","甘肃","福建","西藏","贵州","辽宁","重庆",
    "陕西","青海","黑龙江","地方频道","其它频道"]

# ==================== 1. 从 md/httop_links.txt 下载 m3u ====================
def download_m3u_from_links() -> str:
    if not LINKS_FILE_PATH.exists():
        print(f"❌ 链接文件不存在: {LINKS_FILE_PATH}")
        sys.exit(1)

    links = []
    for line in LINKS_FILE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            links.append(line)

    if not links:
        print(f"❌ {LINKS_FILE_PATH} 中没有有效的链接")
        sys.exit(1)

    print(f"🔗 发现 {len(links)} 个待尝试的链接")

    for idx, url in enumerate(links, 1):
        print(f"[{idx}/{len(links)}] 正在尝试下载: {url}")
        try:
            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()
            content = response.text.strip()
            if content.startswith("#EXTM3U") or "#EXTINF" in content:
                print(f"✅ 成功下载有效内容: {url}")
                # 保存本次成功的原始备份
                SAVE_ORIGINAL_PATH.parent.mkdir(parents=True, exist_ok=True)
                save_path = SAVE_ORIGINAL_PATH.with_name(f"hotel_original_success_{idx}.m3u")
                save_path.write_text(content, encoding="utf-8")
                print(f"💾 已保存原始文件: {save_path}")
                # 更新主备份路径为最新成功文件（可选）
                content_to_use = content
                SAVE_ORIGINAL_PATH.write_text(content, encoding="utf-8")
                print(f"💾 主备份已更新: {SAVE_ORIGINAL_PATH}")
                return content_to_use
            else:
                print(f"⚠️ 下载内容无效（非 m3u 格式）: {url}")
        except Exception as e:
            print(f"❌ 下载失败 {url}: {e}")

    print("❌ 所有链接均下载失败或内容无效")
    sys.exit(1)

m3u_content = download_m3u_from_links()

# ==================== 2. 加载别名表 ====================
alias_db = {}
if ALIAS_FILE.exists():
    for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"): 
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if not parts: 
            continue
        main_name = parts[0]
        alias_db[main_name] = set(parts)

# ==================== 3. 加载台标库 ====================
logo_map = {}
def load_logos_from_dir(directory: Path, base_cat: str = None) -> int:
    if not directory.exists(): 
        return 0
    new_aliases = 0
    for f in directory.iterdir():
        if not f.is_file() or f.suffix.lower() not in {".png",".jpg",".jpeg",".webp"}: 
            continue
       
        cat = base_cat if base_cat is not None else directory.name
        logo_stem = f.stem
        logo_name = f.name
       
        # 阶段 A: 通过 alias.txt 映射
        main_name_found = None
        for main, aliases in alias_db.items():
            clean_logo_stem = re.sub(r"[-_ .]","", logo_stem).upper()
            for alias in aliases:
                clean_alias = re.sub(r"[-_ .]","", alias).upper()
                if clean_logo_stem == clean_alias:
                    main_name_found = main
                    break
            if main_name_found: 
                break
       
        if main_name_found:
            all_aliases = alias_db.get(main_name_found, {main_name_found})
            for alias in all_aliases:
                keys_to_add = {
                    alias.upper(),
                    re.sub(r"[-_ .]","", alias).upper(),
                    re.sub(r"(高清|HD|超清|4K|PLUS).*$","", alias, flags=re.I).strip().upper()
                }
                for k in keys_to_add:
                    if k and k not in logo_map:
                        logo_map[k] = (cat, logo_name)
                        new_aliases += 1
       
        # 阶段 B: 添加文件名本身映射
        clean_stem = re.sub(r"[-_ .]","", logo_stem).upper()
        if logo_stem.upper() not in logo_map:
            logo_map[logo_stem.upper()] = (cat, logo_name)
            new_aliases += 1
        if clean_stem not in logo_map:
            logo_map[clean_stem] = (cat, logo_name)
            new_aliases += 1
   
    return new_aliases

total_aliases = 0
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if folder.is_dir():
            total_aliases += load_logos_from_dir(folder)
if IMG_DIR.exists():
    total_aliases += load_logos_from_dir(IMG_DIR, base_cat='img')
print(f"台标库加载完成：共映射 {total_aliases} 个频道名称变体。")

# ==================== 4. 主程序（解析下载的 m3u 内容） ====================
grouped_channels = defaultdict(lambda: defaultdict(list))
total = 0
extinf = None
for raw in m3u_content.splitlines():
    line = raw.strip()
   
    if line.startswith("#EXTINF:"):
        extinf = line
    elif line and not line.startswith("#"):
        if not extinf:
            extinf = None
            continue
       
        raw_name = extinf.split(",",1)[-1].strip() if "," in extinf else ""
        name_upper = raw_name.upper()
        stream_url = line
        skip_processing = False
       
        # A. 预处理：纯数字频道保留
        if not raw_name or raw_name.isdigit():
            final_group_internal = "其他"
            new_line = extinf
            skip_processing = True
       
        if not skip_processing:
            # B. 查找台标
            logo_url = ""
            best_match_cat = None
           
            aggressive_clean_name = raw_name
            for suffix in ["频道", "卫视", "台", "高清", "HD", "超清", "4K", "PLUS"]:
                aggressive_clean_name = re.sub(f'{re.escape(suffix)}$', '', aggressive_clean_name, flags=re.I).strip()
           
            candidates = {
                name_upper,
                re.sub(r"[-_ .]","", name_upper),
                aggressive_clean_name.upper(),
                re.sub(r"[-_ .]","", aggressive_clean_name).upper()
            }
           
            for key in candidates:
                if logo_map.get(key):
                    best_match_cat, logo_file = logo_map[key]
                    if best_match_cat == 'img':
                        logo_url = f"{REPO_RAW}/img/{logo_file}"
                    else:
                        logo_url = f"{REPO_RAW}/Images/{best_match_cat}/{logo_file}"
                    break
           
            # C. 确定最终 Group
            final_group_internal = "其他"
            if any(x in name_upper for x in ["CCTV","央视","中央","CGTN"]):
                final_group_internal = "CCTV"
            elif "卫视" in name_upper:
                final_group_internal = "WSTV"
            elif logo_url and best_match_cat and best_match_cat != '其他':
                final_group_internal = best_match_cat
            else:
                m = re.search(r'group-title="([^"]+)"', extinf)
                final_group_internal = m.group(1) if m else "其他"
           
            # D. 构造新的 EXTINF
            group_display_name = GROUP_MAPPING.get(final_group_internal, final_group_internal)
            new_line = extinf.split(",",1)[0]
            new_line = re.sub(r'group-title="[^"]*"', f'group-title="{group_display_name}"', new_line)
            if "group-title=" not in new_line:
                new_line += f' group-title="{group_display_name}"'
            if logo_url:
                new_line = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo_url}"', new_line)
                if "tvg-logo=" not in new_line:
                    new_line += f' tvg-logo="{logo_url}"'
            new_line += f',{raw_name}'
       
        # E. 保存结果
        group_display_name = GROUP_MAPPING.get(final_group_internal, final_group_internal)
        weight = CATEGORY_ORDER.index(group_display_name) if group_display_name in CATEGORY_ORDER else 9999
       
        cctv_match = re.search(r'CCTV[^\d]*(\d+)', raw_name, re.I)
        if cctv_match:
            channel_number = int(cctv_match.group(1))
            channel_sort_key = (0, channel_number)
        else:
            channel_sort_key = (1, raw_name)
       
        grouped_channels[final_group_internal][raw_name].append({
            'weight': weight,
            'channel_sort_key': channel_sort_key,
            'extinf': new_line,
            'url': stream_url
        })
        total += 1
        extinf = None

# ==================== 5. 排序 + 写入文件 ====================
def get_sort_key(group_internal_name):
    display_name = GROUP_MAPPING.get(group_internal_name, group_internal_name)
    return CATEGORY_ORDER.index(display_name) if display_name in CATEGORY_ORDER else 9999

sorted_groups_internal = sorted(grouped_channels.keys(), key=get_sort_key)
m3u_lines = ['#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"']
txt_lines = []

for group_internal_name in sorted_groups_internal:
    channels = grouped_channels[group_internal_name]
    group_display_name = GROUP_MAPPING.get(group_internal_name, group_internal_name)
   
    sorted_channels = sorted(channels.keys(), key=lambda c: channels[c][0]['channel_sort_key'])
   
    txt_lines.append(f"{group_display_name},#genre#")
    txt_lines.append("")  # 空行分隔
   
    for channel_name in sorted_channels:
        links = channels[channel_name]
        for item in links:
            m3u_lines.append(item['extinf'])
            m3u_lines.append(item['url'])
            txt_lines.append(f"{channel_name},{item['url']}")

# 写入 M3U
try:
    OUTPUT_M3U.write_text('\n'.join(m3u_lines) + '\n', encoding="utf-8")
    print(f"✅ 已生成 M3U 文件: {OUTPUT_M3U.name}")
except Exception as e:
    print(f"❌ 写入 M3U 失败: {e}")

# 写入 TXT
try:
    OUTPUT_TXT.write_text('\n'.join(txt_lines) + '\n', encoding="utf-8")
    print(f"✅ 已生成 TVbox TXT 文件: {OUTPUT_TXT.name}")
except Exception as e:
    print(f"❌ 写入 TXT 失败: {e}")

print(f"🎉 完美收工！共处理 {total} 条线路（包含纯数字频道）")
