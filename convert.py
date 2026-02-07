import os
import re

# --- 配置区 ---
INPUT_FILE = "revived_hotel.txt"
OUTPUT_FILE = "hotel_list.m3u"
EPG_URL = "https://live.fanmingming.com/e.xml"
LOGO_BASE_URL = "https://tb.yubo.qzz.io/logo/"
# --------------

def get_sort_key(name):
    """
    自定义排序逻辑：
    1. CCTV 排在最前面
    2. 按照 CCTV 后面的数字大小排序 (1, 2, 3... 10, 11)
    3. 非 CCTV 频道按字母顺序排在后面
    """
    # 匹配 CCTV 后面的数字
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match:
        # 返回 (0, 数字) 确保 CCTV 组内部有序且整体靠前
        return (0, int(cctv_match.group(1)))
    # 非 CCTV 频道，返回 (1, 频道名)
    return (1, name)

def convert():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 找不到输入文件: {INPUT_FILE}")
        return

    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 按 IP 组（双换行）分割
    groups = content.strip().split('\n\n')
    
    for group in groups:
        lines = group.strip().split('\n')
        if not lines: continue
        
        # 提取分组名（IP 延迟信息）
        group_name = lines[0].split(',')[0].strip()
        
        # 提取当前组内的所有频道
        channels = []
        for channel_line in lines[1:]:
            if ',' in channel_line:
                name, url = channel_line.split(',', 1)
                channels.append({'name': name.strip(), 'url': url.strip()})
        
        # --- 核心排序步骤 ---
        # 使用我们定义的 get_sort_key 进行排序
        channels.sort(key=lambda x: get_sort_key(x['name']))
        
        # 写入排序后的频道
        for ch in channels:
            name = ch['name']
            url = ch['url']
            
            # 生成台标名：CCTV-1 -> CCTV1
            logo_name = re.sub(r'[\-\s]', '', name)
            logo_url = f"{LOGO_BASE_URL}{logo_name}.png"
            
            m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo_url}" group-title="{group_name}",{name}')
            m3u_lines.append(url)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines))
    
    print(f"✨ M3U 转换完成（已优化 CCTV 排序）！生成文件: {OUTPUT_FILE}")

if __name__ == "__main__":
    convert()
