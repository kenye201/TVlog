import os, re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
FILE_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
FILE_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")
FINAL_TXT = os.path.join(ROOT_DIR, "final_hotel.txt")
FINAL_M3U = os.path.join(ROOT_DIR, "final_hotel.m3u")

def clean_channel_name(name):
    """
    清洗频道名称：将各种奇葩格式统一为标准 CCTVX
    """
    name = name.replace(" ", "").upper()
    # 匹配 央视/CCTV + 数字
    match = re.search(r'(?:央视|CCTV)[-]?(\d+)', name)
    if match:
        num = match.group(1)
        return f"CCTV{num}"
    
    # 常见汉字转换
    mapping = {"央视五": "CCTV5", "央视五+": "CCTV5+", "央视六": "CCTV6", "央视八": "CCTV8"}
    for k, v in mapping.items():
        if k in name: return v
        
    # 去除冗余后缀
    name = re.sub(r'(高清|标清|超高|H265|4K|HD|SD|频道)', '', name)
    return name

def get_priority(name):
    """
    排序权重：CCTV 开头的排在 0，其他排在 1
    """
    return 0 if "CCTV" in name.upper() else 1

def main():
    combined_content = ""
    for f_path in [FILE_REVIVED, FILE_RESCUED]:
        if os.path.exists(f_path):
            with open(f_path, 'r', encoding='utf-8') as f:
                combined_content += f.read()

    if not combined_content.strip():
        print("❌ 没有任何数据可供洗版", flush=True)
        return

    # 按块处理
    blocks = [b.strip() for b in combined_content.split('\n\n') if b.strip()]
    processed_blocks = []

    for block in blocks:
        lines = block.split('\n')
        ip_header = lines[0] # IP,#genre#
        channels = []
        
        for ch in lines[1:]:
            if ',' in ch:
                raw_name, url = ch.split(',', 1)
                clean_name = clean_channel_name(raw_name)
                channels.append((clean_name, url.strip()))
        
        # --- 核心排序逻辑 ---
        # 1. 优先 CCTV (get_priority)
        # 2. CCTV 内部按数字排序 (CCTV1 < CCTV2)
        channels.sort(key=lambda x: (get_priority(x[0]), x[0]))
        
        # 重新构建块
        new_block = f"{ip_header}\n"
        for name, url in channels:
            new_block += f"{name},{url}\n"
        processed_blocks.append(new_block)

    # 导出最终文件
    final_txt_content = "\n\n".join(processed_blocks)
    
    with open(FINAL_TXT, 'w', encoding='utf-8') as f:
        f.write(final_txt_content)

    # 生成 M3U
    m3u_lines = ["#EXTM3U"]
    for block in processed_blocks:
        lines = block.split('\n')
        group_title = lines[0].split(',')[0]
        for ch in lines[1:]:
            if ',' in ch:
                name, url = ch.split(',', 1)
                m3u_lines.append(f'#EXTINF:-1 group-title="{group_title}",{name}')
                m3u_lines.append(url)

    with open(FINAL_M3U, 'w', encoding='utf-8') as f:
        f.write("\n".join(m3u_lines))

    print(f"✨ 洗版完成！共处理 {len(processed_blocks)} 个网段，央视已置顶。", flush=True)

if __name__ == "__main__":
    main()
