import os
import re

# --- 配置区 ---
INPUT_FILE = "revived_hotel.txt"
OUTPUT_FILE = "hotel_list.m3u"
EPG_URL = "https://live.fanmingming.com/e.xml"
LOGO_BASE_URL = "https://tb.yubo.qzz.io/logo/" # 自动拼接 频道名.png
# --------------

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
        
        # 第一行通常是 IP,#genre# 或者是我们脚本生成的 1.1.1.1 (延迟:xx ms),#genre#
        header = lines[0]
        # 提取当前 IP 组的名称（用于 M3U 分组）
        group_name = header.split(',')[0].strip()
        
        for channel_line in lines[1:]:
            if ',' not in channel_line: continue
            
            name, url = channel_line.split(',', 1)
            name = name.strip()
            url = url.strip()
            
            # 标准化频道名用于台标（去除特殊符号）
            logo_name = re.sub(r'[\-\s]', '', name)
            logo_url = f"{LOGO_BASE_URL}{logo_name}.png"
            
            # 组装 M3U 格式
            # tvg-name 匹配 EPG，tvg-logo 匹配台标，group-title 按 IP 端口分组
            m3u_lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo_url}" group-title="{group_name}",{name}')
            m3u_lines.append(url)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines))
    
    print(f"✨ M3U 转换完成！已生成: {OUTPUT_FILE}")

if __name__ == "__main__":
    convert()
