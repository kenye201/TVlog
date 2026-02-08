import subprocess
import json
import os
import re
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
    # 彻底清洗掉已有的 (SD) 或 (Unknown) 标签，保持频道名纯净
    clean = re.sub(r'\(.*?\)', '', name)
    clean = clean.upper().replace(' ', '').replace('-', '').replace('中央', '').replace('台', '').replace('PLUS', '+')
    
    for key, std_name in CCTV_MAP.items():
        if key in clean:
            num_match = re.search(r'\d+', std_name)
            order = int(num_match.group()) if num_match else 0
            if '5+' in std_name: order = 5.5
            return std_name, order
    return name.strip(), 999

def process_ip_group(index, total, block):
    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
    if not lines: return None
    
    # 解析原始 IP 信息
    raw_ip = lines[0].split(',')[0]
    test_url = lines[1].split(',')[1] if len(lines) > 1 else ""
    
    # 探测
    quality = get_stream_quality(test_url)
    print(f"[{index}/{total}] 探测完毕: {raw_ip} -> {quality}", flush=True)
    
    # 重新构建分类标题 (根据要求：非1080P才加标记)
    if quality in ["SD", "720P"]:
        new_header = f"{raw_ip}(SD),#genre#"
    elif quality == "Unknown":
        new_header = f"{raw_ip}(Unknown),#genre#"
    else:
        new_header = f"{raw_ip},#genre#"
        
    processed_channels = []
    for l in lines[1:]:
        if ',' in l:
            name, url = l.split(',', 1)
            std_name, sort_order = clean_and_sort_key(name)
            processed_channels.append({
                'order': sort_order,
                'line': f"{std_name},{url.strip()}"
            })
    
    # 排序
    processed_channels.sort(key=lambda x: x['order'])
    
    result = [new_header] + [ch['line'] for ch in processed_channels]
    return "\n".join(result)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 找不到底库")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # 兼容处理底库中可能的各种换行情况
    groups = [g.strip() for g in content.split('\n\n') if g.strip()]
    total = len(groups)
    
    print(f"--- 🚀 开始对底库进行分类标记 (共 {total} 组) ---", flush=True)

    # 这里的结果需要按照原始顺序，所以我们先用字典存，最后按 index 排序
    indexed_results = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_index = {executor.submit(process_ip_group, i+1, total, groups[i]): i for i in range(total)}
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            indexed_results[idx] = future.result()

    # 按照原始顺序写回
    final_list = [indexed_results[i] for i in range(total) if indexed_results[i]]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(final_list))
    
    print(f"\n✨ 生成成功！请下载 test_result.txt 并替换底库。", flush=True)

if __name__ == "__main__":
    main()
