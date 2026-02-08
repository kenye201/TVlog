import subprocess
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt")
OUTPUT_FILE = os.path.join(CURRENT_DIR, "test_result.txt")

CCTV_MAP = {
    'CCTV1': 'CCTV-1', 'CCTV2': 'CCTV-2', 'CCTV3': 'CCTV-3', 'CCTV4': 'CCTV-4',
    'CCTV5': 'CCTV-5', 'CCTV5+': 'CCTV-5+', 'CCTV6': 'CCTV-6', 'CCTV7': 'CCTV-7',
    'CCTV8': 'CCTV-8', 'CCTV9': 'CCTV-9', 'CCTV10': 'CCTV-10', 'CCTV11': 'CCTV-11',
    'CCTV12': 'CCTV-12', 'CCTV13': 'CCTV-13', 'CCTV14': 'CCTV-14', 'CCTV15': 'CCTV-15',
    'CCTV16': 'CCTV-16', 'CCTV17': 'CCTV-17'
}

def get_stream_quality(url):
    """通过 ffprobe 探测分辨率"""
    cmd = [
        'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'json',
        '-timeout', '8000000', 
        url
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        data = json.loads(result.stdout)
        if 'streams' in data and len(data['streams']) > 0:
            w = data['streams'][0].get('width', 0)
            h = data['streams'][0].get('height', 0)
            if h >= 1080 or w >= 1920: return "1080P"
            if h >= 720 or w >= 1280: return "720P"
            return "SD"
    except:
        pass
    return "Unknown"

def clean_and_sort_key(name):
    clean = name.upper().replace(' ', '').replace('-', '').replace('中央', '').replace('台', '').replace('PLUS', '+')
    for key, std_name in CCTV_MAP.items():
        if key in clean:
            num_match = re.search(r'\d+', std_name)
            order = int(num_match.group()) if num_match else 0
            if '5+' in std_name: order = 5.5
            return std_name, order
    return name, 999

def process_ip_group(index, total, block):
    """处理单个组并返回进度信息"""
    lines = block.strip().split('\n')
    if not lines: return None
    
    ip_header = lines[0]
    pure_ip = ip_header.split(',')[0]
    test_url = lines[1].split(',')[1] if len(lines) > 1 else ""
    
    # 执行探测
    quality = get_stream_quality(test_url)
    
    # 实时打印到前台
    status_icon = "✅" if quality != "Unknown" else "⚠️"
    print(f"[{index}/{total}] {status_icon} 探测完成: {pure_ip} -> {quality}", flush=True)
    
    processed_channels = []
    for l in lines[1:]:
        if ',' in l:
            name, url = l.split(',', 1)
            std_name, sort_order = clean_and_sort_key(name.strip())
            display_name = f"{std_name} ({quality})" if quality != "Unknown" else std_name
            processed_channels.append({
                'order': sort_order,
                'line': f"{display_name},{url.strip()}"
            })
    
    processed_channels.sort(key=lambda x: x['order'])
    result = [ip_header] + [ch['line'] for ch in processed_channels]
    return "\n".join(result)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误: 找不到底库文件 {INPUT_FILE}", flush=True)
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        groups = [g.strip() for g in f.read().split('\n\n') if g.strip()]
    
    total = len(groups)
    print(f"--- 🚀 酒店源画质洗版测试任务开始 (共 {total} 个网段) ---", flush=True)

    final_results = []
    # 使用线程池，设置较小的 max_workers 以便日志能有序跳出
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_index = {executor.submit(process_ip_group, i+1, total, groups[i]): i for i in range(total)}
        
        # 按完成顺序获取结果
        for future in as_completed(future_to_index):
            res = future.result()
            if res:
                final_results.append(res)

    # 写入文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(final_results))
    
    print(f"\n✨ 任务全部结束！", flush=True)
    print(f"📂 结果预览已保存至: {OUTPUT_FILE}", flush=True)

if __name__ == "__main__":
    main()
