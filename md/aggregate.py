import subprocess
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 底库：已标记画质且洗过版的库
LOCAL_BASE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt")  
# 新源：当天抓取的原始 tvbox_output.txt (位于项目根目录)
INPUT_RAW = os.path.join(os.path.dirname(CURRENT_DIR), "tvbox_output.txt") 
# 输出：写回底库
OUTPUT_FILE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt") 

CCTV_MAP = {
    'CCTV1': 'CCTV-1', 'CCTV2': 'CCTV-2', 'CCTV3': 'CCTV-3', 'CCTV4': 'CCTV-4',
    'CCTV5': 'CCTV-5', 'CCTV5+': 'CCTV-5+', 'CCTV6': 'CCTV-6', 'CCTV7': 'CCTV-7',
    'CCTV8': 'CCTV-8', 'CCTV9': 'CCTV-9', 'CCTV10': 'CCTV-10', 'CCTV11': 'CCTV-11',
    'CCTV12': 'CCTV-12', 'CCTV13': 'CCTV-13', 'CCTV14': 'CCTV-14', 'CCTV15': 'CCTV-15',
    'CCTV16': 'CCTV-16', 'CCTV17': 'CCTV-17'
}

def is_valid_ip(ip_str):
    """正则判断是否为 123.123.123.123:80 格式"""
    return bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', ip_str.strip()))

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
    """清洗频道名并获取排序权重"""
    clean = re.sub(r'\(.*?\)', '', name).upper().replace(' ', '').replace('-', '').replace('中央', '').replace('台', '').replace('PLUS', '+')
    for key, std_name in CCTV_MAP.items():
        if key in clean:
            num_match = re.search(r'\d+', std_name)
            order = int(num_match.group()) if num_match else 0
            if '5+' in std_name: order = 5.5
            return std_name, order
    return name.strip(), 999

def parse_content(content):
    """解析 M3U 块，以双换行分割"""
    groups = {}
    blocks = content.replace('\r\n', '\n').split('\n\n')
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        header = lines[0]
        # 提取分类标签（去除已有的画质后缀）
        tag = header.split(',')[0].split('(')[0].strip()
        groups[tag] = lines
    return groups

def process_group(tag, lines, should_probe=False):
    """处理单个组，洗版并可选探测画质"""
    header = lines[0]
    test_url = lines[1].split(',')[1] if len(lines) > 1 else ""
    
    # 只有明确需要探测且标题中没有标记过的才执行探测
    if should_probe and ("(" not in header):
        quality = get_stream_quality(test_url)
        print(f"🔎 探测新 IP: {tag} -> {quality}", flush=True)
        if quality in ["SD", "720P"]: header = f"{tag}(SD),#genre#"
        elif quality == "Unknown": header = f"{tag}(Unknown),#genre#"
        else: header = f"{tag},#genre#"
    
    processed = []
    for l in lines[1:]:
        if ',' in l:
            name, url = l.split(',', 1)
            std_name, sort_order = clean_and_sort_key(name)
            processed.append({'order': sort_order, 'line': f"{std_name},{url.strip()}"})
    
    processed.sort(key=lambda x: x['order'])
    return "\n".join([header] + [ch['line'] for ch in processed])

def main():
    # 1. 加载底库 (已手动/自动打标过的)
    base_groups = {}
    if os.path.exists(LOCAL_BASE):
        with open(LOCAL_BASE, 'r', encoding='utf-8') as f:
            base_groups = parse_content(f.read())
    
    # 2. 加载新抓取的源 (tvbox_output.txt)
    new_raw_groups = {}
    if os.path.exists(INPUT_RAW):
        with open(INPUT_RAW, 'r', encoding='utf-8') as f:
            new_raw_groups = parse_content(f.read())

    # 3. 分类逻辑
    # a. 老源：直接保留
    # b. 新 IP 源：底库没有且符合 IP 格式 -> 需要探测
    # c. 非 IP 新分类：底库没有但不符合 IP 格式 -> 直接合并
    ips_to_probe = [t for t in new_raw_groups if t not in base_groups and is_valid_ip(t)]
    others_to_add = [t for t in new_raw_groups if t not in base_groups and not is_valid_ip(t)]

    print(f"📉 老底库已有: {len(base_groups)} 个网段")
    print(f"📈 发现新 IP 需要探测: {len(ips_to_probe)} 个")
    if others_to_add:
        print(f"📦 发现新分类直接加入: {len(others_to_add)} 个 ({', '.join(others_to_add[:3])}...)")

    # 4. 并发探测新 IP
    new_probed_results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_tag = {executor.submit(process_group, tag, new_raw_groups[tag], True): tag for tag in ips_to_probe}
        for future in as_completed(future_to_tag):
            tag = future_to_tag[future]
            new_probed_results[tag] = future.result()

    # 5. 处理老源和非 IP 新源 (不探测，仅洗版排序)
    final_list = []
    
    # 先加老底库
    for tag, lines in base_groups.items():
        final_list.append(process_group(tag, lines, False))
        
    # 再加非 IP 的新分类
    for tag in others_to_add:
        final_list.append(process_group(tag, new_raw_groups[tag], False))
        
    # 最后加新探测到的 IP
    for tag in ips_to_probe:
        if tag in new_probed_results:
            final_list.append(new_probed_results[tag])

    # 6. 写入结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(final_list))
    
    print(f"✨ 任务完成！底库当前总规模: {len(final_list)} 个分组。")

if __name__ == "__main__":
    main()
