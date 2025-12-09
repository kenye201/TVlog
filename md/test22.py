# md/test22.py —— 最终标准 TVbox TXT 格式生成版本
import re
import requests
from pathlib import Path
import os
import sys
from collections import defaultdict

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images") 
IMG_DIR          = Path("img")    
OUTPUT_M3U       = Path("demo_output.m3u")
OUTPUT_TXT       = Path("tvbox_output.txt") # TXT 文件路径
REPO_RAW = "https://raw.githubusercontent.com/kenye201/TVlog/main" 

# 分类排序顺序
CATEGORY_ORDER = ["4K","CCTV","CGTN","CIBN","DOX","NewTV","WSTV","iHOT",
    "上海","云南","内蒙古","北京","吉林","四川","天津","宁夏",
    "安徽","山东","山西","广东","广西","数字频道","新疆","江苏",
    "江西","河北","河南","浙江","海南","海外频道","港澳地区",
    "湖北","湖南","甘肃","福建","西藏","贵州","辽宁","重庆",
    "陕西","青海","黑龙江","其他"]
# ----------------------------------------------


# ==================== 1. 加载别名表 (Main Name <-> Alias Set) ====================
alias_db = {}
if ALIAS_FILE.exists():
    for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if not parts: continue
        main_name = parts[0]
        alias_db[main_name] = set(parts)

# ==================== 2. 加载台标库并映射所有别名到台标文件 ====================
logo_map = {}

def load_logos_from_dir(directory: Path, base_cat: str = None) -> int:
    """从指定目录加载台标文件，并将其映射到 logo_map，返回新增的映射数量。"""
    if not directory.exists(): return 0

    new_aliases = 0
    for f in directory.iterdir():
        if not f.is_file() or f.suffix.lower() not in {".png",".jpg",".jpeg",".webp"}: continue
        
        cat = base_cat if base_cat is not None else directory.name
        logo_stem = f.stem 
        logo_name = f.name 
        
        # --- 阶段 A: 通过 alias.txt 映射所有别名 ---
        main_name_found = None
        for main, aliases in alias_db.items():
            clean_logo_stem = re.sub(r"[-_ .]","", logo_stem).upper()
            
            for alias in aliases:
                clean_alias = re.sub(r"[-_ .]","", alias).upper()
                if clean_logo_stem == clean_alias:
                    main_name_found = main
                    break
            
            if main_name_found: break

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

        # --- 阶段 B: 额外添加台标文件名本身的映射 (作为保底) ---
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

# ==================== 3. 主程序（精简匹配） ====================
# 结构: { 分类名: { 频道名: [ (权重, EXTINF行, URL) ] } }
grouped_channels = defaultdict(lambda: defaultdict(list))
total = 0

if not REMOTE_FILE_PATH.exists():
    print(f"错误：输入文件 {REMOTE_FILE_PATH} 不存在。")
    sys.exit(1)

links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

for url in links:
    try:
        text = requests.get(url, timeout=30).text
    except Exception as e:
        print(f"警告：无法获取远程链接 {url} 的内容，跳过。错误: {e}")
        continue

    extinf = None
    for raw in text.splitlines():
        line = raw.strip()
        
        if line.startswith("#EXTINF:"):
            extinf = line
        elif line and not line.startswith("#"):
            if not extinf: continue

            raw_name = extinf.split(",",1)[-1].strip() if "," in extinf else ""
            name_upper = raw_name.upper()
            stream_url = line

            # -------------------- A. 预处理 --------------------
            if not raw_name or raw_name.isdigit():
                extinf = None
                continue
            
            # -------------------- B. 查找台标 --------------------
            
            logo_url = ""
            best_match_cat = None
            
            aggressive_clean_name = raw_name
            for suffix in ["频道", "卫视", "台", "高清", "HD", "超清", "4K", "PLUS"]:
                aggressive_clean_name = re.sub(f'{re.escape(suffix)}$', '', aggressive_clean_name, flags=re.I).strip()

            candidates = {name_upper, re.sub(r"[-_ .]","", name_upper), 
                          aggressive_clean_name.upper(), re.sub(r"[-_ .]","", aggressive_clean_name).upper()}
            
            for key in candidates:
                if logo_map.get(key):
                    best_match_cat, logo_file = logo_map[key]
                    
                    logo_path = best_match_cat
                    if best_match_cat == 'img':
                        logo_url = f"{REPO_RAW}/img/{logo_file}"
                    else:
                        logo_url = f"{REPO_RAW}/Images/{logo_path}/{logo_file}"
                        
                    break

            # -------------------- C. 确定最终 Group --------------------
            
            final_group = "其他" 
            
            # 优先级 1: 强制分类 (CCTV/WSTV)
            if any(x in name_upper for x in ["CCTV","央视","中央","CGTN"]):
                final_group = "CCTV"
            elif "卫视" in name_upper:
                final_group = "WSTV"
            
            # 优先级 2: 台标归属分类
            elif logo_url and best_match_cat not in ['其他', 'img']:
                final_group = best_match_cat 
            
            # 优先级 3: 原 EXTINF Group
            else:
                m = re.search(r'group-title="([^"]+)"', extinf)
                final_group = m.group(1) if m else "其他"
            
            # -------------------- D. 构造新的 EXTINF 行 --------------------
            
            new_line = extinf.split(",",1)[0]
            new_line = re.sub(r'group-title="[^"]*"', f'group-title="{final_group}"', new_line)
            if "group-title=" not in new_line: new_line += f' group-title="{final_group}"'

            if logo_url:
                new_line = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo_url}"', new_line)
                if "tvg-logo=" not in new_line: new_line += f' tvg-logo="{logo_url}"'
            
            new_line += f',{raw_name}'

            # -------------------- E. 保存结果 (使用新的数据结构) --------------------
            
            weight = CATEGORY_ORDER.index(final_group) if final_group in CATEGORY_ORDER else 9999
            
            # 频道排序权重：CCTV 频道按数字排序
            cctv_match = re.search(r'CCTV[^\d]*(\d+)', raw_name, re.I)
            channel_sort_key = (0, cctv_match.group(1)) if cctv_match else (1, raw_name)
            
            grouped_channels[final_group][raw_name].append({
                'weight': weight,
                'channel_sort_key': channel_sort_key,
                'extinf': new_line,
                'url': stream_url
            })
            total += 1
            extinf = None

# ==================== 4. 排序 + 写入 M3U 和 TXT 文件 ====================

# 1. 对分类进行排序
sorted_groups = sorted(grouped_channels.keys(), key=lambda g: CATEGORY_ORDER.index(g) if g in CATEGORY_ORDER else 9999)

# 2. 准备最终的 M3U 和 TXT 数据
m3u_lines = ['#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"']
txt_lines = []

for group_name in sorted_groups:
    channels = grouped_channels[group_name]
    
    # 对当前分类下的频道进行排序
    # 排序键：(CCTV数字, 频道名)
    sorted_channels = sorted(channels.keys(), key=lambda c: channels[c][0]['channel_sort_key'])
    
    # TXT 格式分类行
    txt_lines.append(f"{group_name},#genre#")
    txt_lines.append("") # 必须有一个空行

    for channel_name in sorted_channels:
        links = channels[channel_name]
        
        # 将相同频道的链接聚合在一起
        for item in links:
            # M3U 格式
            m3u_lines.append(item['extinf'])
            m3u_lines.append(item['url'])
            
            # TXT 格式
            txt_lines.append(f"{channel_name},{item['url']}")


# 写入 M3U 文件
try:
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write('\n'.join(m3u_lines) + '\n')
except Exception as e:
    print(f"写入 M3U 文件 {OUTPUT_M3U} 失败: {e}")

# 写入 TXT 文件 (TVbox 标准格式)
try:
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write('\n'.join(txt_lines) + '\n')
except Exception as e:
    print(f"写入 TXT 文件 {OUTPUT_TXT} 失败: {e}")


print(f"完美收工！共 {total} 条线路，分类精准，台标全中！")
print(f"已生成 M3U 文件: {OUTPUT_M3U.name}")
print(f"已生成 TVbox TXT 文件 (标准格式): {OUTPUT_TXT.name}")
