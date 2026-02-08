import subprocess
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt")
OUTPUT_FILE = os.path.join(CURRENT_DIR, "test_result.txt")

# CCTV 标准映射
CCTV_MAP = {
    'CCTV1': 'CCTV-1', 'CCTV2': 'CCTV-2', 'CCTV3': 'CCTV-3', 'CCTV4': 'CCTV-4',
    'CCTV5': 'CCTV-5', 'CCTV5+': 'CCTV-5+', 'CCTV6': 'CCTV-6', 'CCTV7': 'CCTV-7',
    'CCTV8': 'CCTV-8', 'CCTV9': 'CCTV-9', 'CCTV10': 'CCTV-10', 'CCTV11': 'CCTV-11',
    'CCTV12': 'CCTV-12', 'CCTV13': 'CCTV-13', 'CCTV14': 'CCTV-14', 'CCTV15': 'CCTV-15',
    'CCTV16': 'CCTV-16', 'CCTV17': 'CCTV-17'
}

def get_stream_quality(url):
    """
    深度探测函数：包含3次重试，增加采样深度
    """
    for attempt in range(3):
        # 增加 analyzeduration 和 probesize 以确保读取到视频头信息
        # timeout 单位为微秒，15000000 = 15秒
        cmd = [
            'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'json',
            '-analyzeduration', '15000000', 
            '-probesize', '15000000',       
            '-timeout', '15000000',         
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
        except Exception:
            pass
        
        # 如果不是最后一次尝试，稍作等待再重试
        if attempt < 2:
            time.sleep(2) 
            
    return "Unknown"

def clean_and_sort_key(name):
    """彻底清洗名称并返回标准名和排序权重"""
    # 去除所有括号及其内容，如 (SD), (Unknown)
    clean = re.sub(r'\(.*?\)', '', name)
    # 转大写并去除常见杂质
    clean = clean.upper().replace(' ', '').replace('-', '').replace('中央', '').replace('台', '').replace('PLUS', '+')
    
    for key, std_name in CCTV_MAP.items():
        if key in clean:
            num_match = re.search(r'\d+', std_name)
            order = int(num_match.group()) if num_match else 0
            if '5+' in std_name: order = 5.5
            return std_name, order
            
    return name.strip(), 999

def process_ip_group(index, total, block):
    """处理单个 IP 分组"""
    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
    if not lines: return None
    
    # 获取 IP 标题和测试链接
    raw_ip = lines[0].split(',')[0]
    test_url = lines[1].split(',')[1] if len(lines) > 1 else ""
    
    # 执行深度探测
    quality = get_stream_quality(test_url)
    
    # 实时反馈日志
    icon = "✅" if quality == "1080P" else ("⚠️" if quality == "Unknown" else "ℹ️")
    print(f"[{index}/{total}] {icon} 探测: {raw_ip} -> {quality}", flush=True)
    
    # 根据要求构建分类标题
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
            # 存入列表用于排序
            processed_channels.append({
                'order': sort_order,
                'line': f"{std_name},{url.strip()}"
            })
    
    # 组内执行排序（央视 1-17 优先）
    processed_channels.sort(key=lambda x: x['order'])
    
    result = [new_header] + [ch['line'] for ch in processed_channels]
    return "\n".join(result)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 找不到输入文件: {INPUT_FILE}")
        return

    print(f"--- 🚀 酒店源深度洗版探测开始 ---", flush=True)
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # 以双换行符分割网段
    groups = [g.strip() for g in content.split('\n\n') if g.strip()]
    total = len(groups)
    
    # 存储结果字典以保持原始 IP 块顺序
    indexed_results = {}
    
    # 降低并发至 5，确保每个连接有足够的带宽和稳定性
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_index = {executor.submit(process_ip_group, i+1, total, groups[i]): i for i in range(total)}
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            indexed_results[idx] = future.result()

    # 按照 index 顺序合并
    final_list = [indexed_results[i] for i in range(total) if indexed_results[i]]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(final_list))
    
    print(f"\n✨ 任务圆满完成！", flush=True)
    print(f"📂 结果文件: {OUTPUT_FILE}", flush=True)

if __name__ == "__main__":
    main()
