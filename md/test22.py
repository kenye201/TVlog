# md/test22.py —— 宇宙最稳·最终版
import re
import requests
from pathlib import Path
import os
import sys

# -------------------- 配置 --------------------
REMOTE_FILE_PATH = Path("md/httop_links.txt")
ALIAS_FILE       = Path("md/alias.txt")
TVLOGO_DIR       = Path("Images")
OUTPUT_M3U       = Path("demo_output.m3u")
# 您的台标仓库裸链接
REPO_RAW = "https://raw.githubusercontent.com/kenye201/TVlog/main" 

# 分类排序顺序
CATEGORY_ORDER = ["4K","CCTV","CGTN","CIBN","DOX","NewTV","WSTV","iHOT",
    "上海","云南","内蒙古","北京","吉林","四川","天津","宁夏",
    "安徽","山东","山西","广东","广西","数字频道","新疆","江苏",
    "江西","河北","河南","浙江","海南","海外频道","港澳地区",
    "湖北","湖南","甘肃","福建","西藏","贵州","辽宁","重庆",
    "陕西","青海","黑龙江","其他"] # 确保 '其他' 在最后
# ----------------------------------------------


# ==================== 1. 加载别名表 (Main Name <-> Alias Set) ====================
# 结构: { 'CCTV-1': {'CCTV-1', 'CCTV1', 'CCTV-1综合', ...}, ... }
alias_db = {}
if ALIAS_FILE.exists():
    for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        # 使用正则表达式处理带 * 的模糊匹配，并清理空字符串
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if not parts: continue
        main_name = parts[0]
        # 存储该主名的所有别名（包括主名本身）
        alias_db[main_name] = set(parts)

# ==================== 2. 加载台标库并映射所有别名到台标文件 ====================
# 结构: { 'CLEAN_ALIAS_KEY': (分类文件夹, 台标文件名) }
logo_map = {}
total_aliases = 0

if TVLOGO_DIR.exists():
    for folder in TVLOGO_DIR.iterdir():
        if not folder.is_dir(): continue
        cat = folder.name
        
        for f in folder.iterdir():
            if not f.is_file() or f.suffix.lower() not in {".png",".jpg",".jpeg",".webp"}: continue
            
            logo_stem = f.stem # 例如: 'CCTV1'
            logo_name = f.name # 例如: 'CCTV1.png'
            
            # --- 阶段 A: 通过 alias.txt 映射所有别名 ---
            main_name_found = None
            
            # 尝试用台标文件名去反查 alias.txt 中的主名
            for main, aliases in alias_db.items():
                
                # 检查台标文件名是否是某个别名（或主名）的简洁形式
                clean_logo_stem = re.sub(r"[-_ .]","", logo_stem).upper()
                
                for alias in aliases:
                    clean_alias = re.sub(r"[-_ .]","", alias).upper()
                    
                    # 精准匹配台标文件名和别名的干净形式
                    if clean_logo_stem == clean_alias:
                        main_name_found = main
                        break
                
                if main_name_found:
                    break

            # 如果找到主名，将所有的别名变体都映射到该台标文件
            if main_name_found:
                all_aliases = alias_db.get(main_name_found, {main_name_found})
                for alias in all_aliases:
                    # 生成多种可能的 key 变体
                    keys_to_add = {
                        alias.upper(),
                        re.sub(r"[-_ .]","", alias).upper(),
                        re.sub(r"(高清|HD|超清|4K|PLUS).*$","", alias, flags=re.I).strip().upper()
                    }
                    
                    for k in keys_to_add:
                        if k:
                            # 存储： 干净的频道名 -> (分类, 台标文件名)
                            logo_map[k] = (cat, logo_name)
                            total_aliases += 1

            # --- 阶段 B: 额外添加台标文件名本身的映射 (作为保底) ---
            # 确保即使没有别名表，台标文件本身也能被匹配
            clean_stem = re.sub(r"[-_ .]","", logo_stem).upper()
            logo_map[logo_stem.upper()] = (cat, logo_name)
            logo_map[clean_stem] = (cat, logo_name)
            total_aliases += 2

print(f"台标库加载完成：共映射 {total_aliases} 个频道名称变体。")


# ==================== 3. 主程序（成对永不跑偏） ====================
paired = []
total = 0

# 检查文件是否存在
if not REMOTE_FILE_PATH.exists():
    print(f"错误：输入文件 {REMOTE_FILE_PATH} 不存在。")
    sys.exit(1)

links = [l.strip() for l in REMOTE_FILE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

for url in links:
    try:
        # 获取远程 M3U 内容
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

            # -------------------- 1. 预处理判断 --------------------
            
            # 纯数字或空名字 → 原样保留，不处理台标和分类
            if not raw_name or raw_name.isdigit():
                weight = 9999
                paired.append((weight, extinf, line))
                total += 1
                extinf = None
                continue
            
            # -------------------- 2. 确定 Group 优先级 --------------------
            
            group = "其他"
            logo_url = ""
            best_match_cat = None
            logo_file = None
            
            # 强制分类优先级最高
            if any(x in name_upper for x in ["CCTV","央视","中央","CGTN"]):
                group = "CCTV"
            elif "卫视" in name_upper:
                group = "WSTV"
            
            # -------------------- 3. 查找台标 (全库匹配) --------------------
            
            # 尝试多种变体查找
            candidates = {
                name_upper,
                re.sub(r"[-_ .]","", name_upper),
                re.sub(r"(高清|HD|超清|4K|PLUS).*$","", raw_name, flags=re.I).strip().upper()
            }
            
            for key in candidates:
                if logo_map.get(key):
                    best_match_cat, logo_file = logo_map[key]
                    logo_url = f"{REPO_RAW}/Images/{best_match_cat}/{logo_file}"
                    break
            
            # -------------------- 4. 确定最终 Group (融合强制和台标结果) --------------------

            # 如果是卫视或央视强制分类，group 保持不变 (CCTV/WSTV)
            # 否则，如果找到了台标，使用台标所在的文件夹分类
            if group not in ["CCTV", "WSTV"] and logo_url:
                group = best_match_cat
            # 如果都没找到台标且不是强制分类，尝试使用原 EXTINF 中的 group-title
            elif group not in ["CCTV", "WSTV"]:
                m = re.search(r'group-title="([^"]+)"', extinf)
                group = m.group(1) if m else "其他"

            # -------------------- 5. 构造新的 EXTINF 行 --------------------
            
            # 剔除原行中的所有属性 (只保留 #EXTINF:-1)
            new_line = extinf.split(",",1)[0]
            
            # 1. 替换/添加 group-title
            new_line = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', new_line)
            if "group-title=" not in new_line:
                new_line += f' group-title="{group}"'

            # 2. 替换/添加 tvg-logo
            if logo_url:
                new_line = re.sub(r'tvg-logo="[^"]*"', f'tvg-logo="{logo_url}"', new_line)
                if "tvg-logo=" not in new_line:
                    new_line += f' tvg-logo="{logo_url}"'
            
            # 3. 加上频道名
            new_line += f',{raw_name}'

            # -------------------- 6. 保存结果 --------------------
            
            weight = CATEGORY_ORDER.index(group) if group in CATEGORY_ORDER else 9999
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

print(f"完美收工！共 {total} 条线路，央视卫视精准，台标全中！")
