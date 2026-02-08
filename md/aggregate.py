import subprocess
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_BASE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt")  # 已打标的底库
INPUT_RAW = os.path.join(os.path.dirname(CURRENT_DIR), "tvbox_output.txt") # 新抓取的源
OUTPUT_FILE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt") # 最终写回底库

CCTV_MAP = {
    'CCTV1': 'CCTV-1', 'CCTV2': 'CCTV-2', 'CCTV3': 'CCTV-3', 'CCTV4': 'CCTV-4',
    'CCTV5': 'CCTV-5', 'CCTV5+': 'CCTV-5+', 'CCTV6': 'CCTV-6', 'CCTV7': 'CCTV-7',
    'CCTV8': 'CCTV-8', 'CCTV9': 'CCTV-9', 'CCTV10': 'CCTV-10', 'CCTV11': 'CCTV-11',
    'CCTV12': 'CCTV-12', 'CCTV13': 'CCTV-13', 'CCTV14': 'CCTV-14', 'CCTV15': 'CCTV-15',
    'CCTV16': 'CCTV-16', 'CCTV17': 'CCTV-17'
}

def get_stream_quality(url):
    """深度探测函数 (3次重试)"""
    for attempt in range(3):
        cmd = [
            'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'json',
            '-analyzeduration', '15000000', '-probesize', '15000000',
            '-timeout', '15000000', url
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
        except: pass
        if attempt < 2: time.sleep(2)
    return "Unknown"

def clean_and_sort_key(name):
    clean = re.sub(r'\(.*?\)', '', name).upper().replace(' ', '').replace('-', '').replace('中央', '').replace('台', '').replace('PLUS', '+')
    for key, std_name in CCTV_MAP.items():
        if key in clean:
            num_match = re.search(r'\d+', std_name)
            order = int(num_match.group()) if num_match else 0
            if '5+' in std_name: order = 5.5
            return std_name, order
    return name.strip(), 999

def parse_content(content):
    """解析 m3u/txt 块"""
    groups = {}
    for block in content.split('\n\n'):
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        header = lines[0]
        ip = header.split(',')[0].split('(')[0] # 提取纯IP
        groups[ip] = lines
    return groups

def process_group(ip, lines, is_new=False):
    """处理单个IP组，如果是新源则探测画质"""
    header = lines[0]
    test_url = lines[1].split(',')[1] if len(lines) > 1 else ""
    
    # 只有新源或者老源里没标画质的才探测
    if is_new or ("(" not in header):
        quality = get_stream_quality(test_url)
        print(f"🔎 探测新源: {ip} -> {quality}", flush=True)
        if quality in ["SD", "720P"]: header = f"{ip}(SD),#genre#"
        elif quality == "Unknown": header = f"{ip}(Unknown),#genre#"
        else: header = f"{ip},#genre#"
    
    processed = []
    for l in lines[1:]:
        if ',' in l:
            name, url = l.split(',', 1)
            std_name, sort_order = clean_and_sort_key(name)
            processed.append({'order': sort_order, 'line': f"{std_name},{url.strip()}"})
    
    processed.sort(key=lambda x: x['order'])
    return "\n".join([header] + [ch['line'] for ch in processed])

def main():
    # 1. 加载老底库
    base_groups = {}
    if os.path.exists(LOCAL_BASE):
        with open(LOCAL_BASE, 'r', encoding='utf-8') as f:
            base_groups = parse_content(f.read())
    
    # 2. 加载新抓取的源
    new_groups_raw = {}
    if os.path.exists(INPUT_RAW):
        with open(INPUT_RAW, 'r', encoding='utf-8') as f:
            new_groups_raw = parse_content(f.read())

    # 3. 找出真正需要探测的新 IP (底库里没有的)
    ips_to_probe = [ip for ip in new_groups_raw if ip not in base_groups]
    print(f"📈 发现 {len(ips_to_probe)} 个新网段需要探测...")

    # 4. 探测新源 (低并发模式)
    new_processed = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_ip = {executor.submit(process_group, ip, new_groups_raw[ip], True): ip for ip in ips_to_probe}
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            new_processed[ip] = future.result()

    # 5. 处理老源 (不探测，仅洗版排序)
    old_processed = {}
    for ip, lines in base_groups.items():
        old_processed[ip] = process_group(ip, lines, False)

    # 6. 合并结果并保持顺序 (老源在前，新源在后)
    final_output = list(old_processed.values()) + list(new_processed.values())
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(final_output))
    
    print(f"✨ 成功合并！当前底库总网段: {len(final_output)}")

if __name__ == "__main__":
    main()
