import re
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)

# 文件路径
FILE_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
FILE_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")
LOCAL_BASE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt")
FINAL_TXT = os.path.join(ROOT_DIR, "final_hotel.txt")
FINAL_M3U = os.path.join(ROOT_DIR, "final_hotel.m3u")

def clean_name(name):
    # 如果你不想脚本乱改你的名字，可以精简这个函数
    name = re.sub(r'(高清|标清|超高清|H\.265|4K|HD|SD|hd|sd)', '', name, flags=re.I)
    return name.strip()

def main():
    # 为了保持顺序，我们使用列表记录 IP 的出现顺序
    ip_order = []
    all_data = {}  # { "IP:Port": [ (原始名, URL), ... ] }

    sources = [FILE_REVIVED, FILE_RESCUED]

    for f_path in sources:
        if not os.path.exists(f_path):
            continue
        
        with open(f_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content: continue
            blocks = content.split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 2: continue
                
                ip = lines[0].split(',')[0].strip()
                if ip not in all_data:
                    all_data[ip] = []
                    ip_order.append(ip)
                
                for l in lines[1:]:
                    if ',' in l:
                        raw_name, url = l.split(',', 1)
                        # 这里不再通过字典键去重排序，而是直接记录元组保持顺序
                        all_data[ip].append((raw_name.strip(), url.strip()))

    if not all_data:
        print("❌ 没有存活数据", flush=True)
        return

    txt_output = ""
    m3u_output = '#EXTM3U\n'
    
    # 核心改进：按照脚本读取到的顺序（即底库中的顺序）写入
    for ip in ip_order:
        txt_output += f"{ip},#genre#\n"
        
        # 针对每个 IP 下的频道，直接按列表顺序写入，不再 sorted()
        for name, url in all_data[ip]:
            txt_output += f"{name},{url}\n"
            m3u_output += f'#EXTINF:-1 group-title="{ip}",{name}\n{url}\n'
        
        txt_output += "\n"

    # 写入文件
    with open(LOCAL_BASE, 'w', encoding='utf-8') as f:
        f.write(txt_output)
    with open(FINAL_TXT, 'w', encoding='utf-8') as f:
        f.write(txt_output)
    with open(FINAL_M3U, 'w', encoding='utf-8') as f:
        f.write(m3u_output)
    
    print(f"✅ 搞定！现在顺序已完全依照底库手动排列顺序。", flush=True)

if __name__ == "__main__":
    main()
