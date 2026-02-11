import os

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

# 输入文件 (确保这两个文件里的央视列表是完整的)
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")

# 输出文件
OUTPUT_TXT = os.path.join(PARENT_DIR, "final_hotel.txt")
OUTPUT_M3U = os.path.join(PARENT_DIR, "final_hotel.m3u")

# 配置
LOGO_BASE_URL = "https://tb.yubo.qzz.io/logo/"
EPG_URL = "https://live.fanmingming.com/e.xml"

def main():
    all_blocks = []
    
    # 1. 收集所有数据
    for path in [MID_REVIVED, MID_RESCUED]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                # 统一换行符，并根据双换行切分块
                content = f.read().replace('\r\n', '\n').strip()
                if content:
                    # 关键：过滤掉空块，确保每个 block 都是有效的网段数据
                    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
                    all_blocks.extend(blocks)

    if not all_blocks:
        print("❌ 警告：未发现任何待格式化的频道数据。")
        return

    # 2. 生成最终 TXT (合并后的原始格式)
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(all_blocks))

    # 3. 生成 M3U 格式 (精准洗版，带台标)
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    
    for block in all_blocks:
        lines = block.split('\n')
        if not lines: continue
        
        # 第一行通常是：IP:Port,#genre#
        header_parts = lines[0].split(',')
        group_title = header_parts[0].strip() # 提取 IP 作为组名
        
        # 处理该块下的所有频道行
        for line in lines:
            if ',' in line and '#genre#' not in line:
                name, url = line.split(',', 1)
                name = name.strip()
                url = url.strip()
                
                if not url.startswith('http'): continue
                
                # 拼接台标链接
                logo_url = f"{LOGO_BASE_URL}{name}.png"
                
                # 写入 M3U：tvg-id 对应 EPG，tvg-logo 对应台标
                m3u_lines.append(f'#EXTINF:-1 tvg-id="{name}" tvg-logo="{logo_url}" group-title="{group_title}",{name}')
                m3u_lines.append(url)

    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines))

    print(f"🎉 格式化成功！已处理 {len(all_blocks)} 个网段，M3U 行数：{len(m3u_lines)}")

if __name__ == "__main__":
    main()
