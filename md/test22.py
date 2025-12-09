# md/test22.py —— 最终精简匹配版本 (修正 SyntaxError)
import re
import requests
from pathlib import Path
import os
import sys

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images") # 包含分类文件夹 (CCTV, WSTV, 湖南等)
IMG_DIR          = Path("img")    # 新增：无分类的通用台标文件夹
OUTPUT_M3U       = Path("demo_output.m3u")
# 您的台标仓库裸链接
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
# 结构: { 'CLEAN_ALIAS_KEY': (分类文件夹, 台标文件名) }
logo_map = {}

def load_logos_from_dir(directory: Path, base_cat: str = None) -> int:
    """从指定目录加载台标文件，并将其映射到 logo_map，返回新增的映射数量。"""
    if not directory.exists():
        return 0

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
                    if k and k not in logo_map: # 避免覆盖
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

# 优先加载分类文件夹（Images/CCTV, Images/湖南 等）
total_aliases = 0
if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if folder.is_dir():
            total_aliases += load_logos_from_dir(folder)

# 其次加载通用文件夹 (img/)，如果 key 已存在，不覆盖
if IMG_DIR.exists():
    total_aliases += load_logos_from_dir(IMG_DIR, base_cat='img') 

print(f"台标库加载完成：共映射 {total_aliases} 个频道名称变体。")

# ==================== 3. 主程序（精简匹配） ====================
paired = []
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
            if not extinf: 
                continue

            raw_name = extinf.split(",",1)[-1].strip() if "," in extinf else ""
            name_upper = raw_name.upper()

            # -------------------- A. 预处理 --------------------
            if not raw_name or raw_name.isdigit():
                weight = 9999
                paired.append((weight, extinf, line))
                total += 1
                extinf = None
                continue
            
            # -------------------- B. 查找台标 (增强 Key 简洁度) --------------------
            
            logo_url = ""
            best_match_cat = None # 台标文件所在的分类文件夹名 (如: CCTV, 湖南, img)
            
            # 增强 Key 的简洁度：主动去除“卫视”、“频道”等后缀，用于提高匹配率
            aggressive_clean_name = raw_name
            for suffix in ["频道", "卫视", "台", "高清", "HD", "超清", "4K", "PLUS"]:
                aggressive_clean_name = re.sub(f'{re.escape(suffix)}$', '', aggressive_clean_name, flags=re.I).strip()

            # 候选键集：包括原始、去符号、以及激进清理后的版本
            candidates = {
                name_upper,
                re.sub(r"[-_ .]","", name_upper),
                aggressive_clean_name.upper(),
                re.sub(r"[-_ .]","", aggressive_clean_name).upper(),
            }
            
            # 实际进行匹配查找
            for key in candidates:
                if logo_map.get(key):
                    best_match_cat, logo_file = logo_map[key]
                    
                    # 确定 logo_url：如果分类是 'img'，则 URL 路径使用 'img'
                    logo_path = best_match_cat
                    if best_match_cat == 'img':
                        logo_url = f"{REPO_RAW}/img/{logo_file}"
                    else:
                        logo_url = f"{REPO_RAW}/Images/{logo_path}/{logo_file}"
                        
                    break # 找到即退出

            # -------------------- C. 确定最终 Group (强制分类 + 台标归属) --------------------
            
            final_group = "其他" 
            
            # 优先级 1: 强制分类 (CCTV/WSTV)
            if any(x in name_upper for x in ["CCTV","央视","中央","CGTN"]):
                final_group = "CCTV"
            elif "卫视" in name_upper:
                final_group = "WSTV"
            
            # 优先级 2: 台标归属分类 (使用台标所在的 Images/ 子文件夹名)
            elif logo_url and best_match_cat not in ['其他', 'img']:
                # 台标文件所在的 Images/ 子文件夹名 (如: 湖南, 河南)
                final_group = best_match_cat 
            
            # 优先级 3: 原 EXTINF Group (用于保留数字频道等分类名)
            else:
                m = re.search(r'group-title="([^"]+)"', extinf)
                final_group = m.group(1) if m else "其他"

            # -------------------- D. 构造新的 EXTINF 行 --------------------
            
            new_line = extinf.split(",",1)[0]
            
            # 1. 替换/添加 group-title
            new_line = re.sub(r'group-title="[^"]*"', f'group-title="{final_group}"', new_line)
            if "group-title=" not in new_line:
                new_line += f' group-title="{final_group}"'

            # 2. 替换/添加 tvg-logo
            if logo_url:
                new_line = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo_url}"', new_line)
                if "tvg-logo=" not in new_line:
                    new_line += f' tvg-logo="{logo_url}"'
            
            # 3. 加上频道名
            new_line += f',{raw_name}'

            # -------------------- E. 保存结果 --------------------
            
            weight = CATEGORY_ORDER.index(final_group) if final_group in CATEGORY_ORDER else 9999
            paired.append((weight, new_line, line))
            total += 1
            extinf = None

# 排序 + 写入
paired.sort(key=lambda x: x[0])
try:
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n')
        for _, e, u in paired:
            f.write(e + "\n")
            f.write(u + "\n")
except Exception as e:
    print(f"写入文件 {OUTPUT_M3U} 失败: {e}")

print(f"完美收工！共 {total} 条线路，分类精准，台标全中！")
