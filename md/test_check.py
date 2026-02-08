import subprocess
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

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
    """通过 ffprobe 探测分辨率"""
    cmd = [
        'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'json',
        '-timeout', '8000000', # 8秒探测时间，给酒店源足够的响应机会
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
    """统一名称并返回排序权重"""
    # 清洗：去杂质、转大写
    clean = name.upper().replace(' ', '').replace('-', '').replace('中央', '').replace('台', '').replace('PLUS', '+')
    
    # 匹配标准名
    for key, std_name in CCTV_MAP.items():
        if key in clean:
            # 提取数字排序，例如 CCTV-1 提取 1
            num_match = re.search(r'\d+', std_name)
            order = int(num_match.group()) if num_match else 0
            if '5+' in std_name: order = 5.5 # 5+ 排在 5 后面
            return std_name, order
    
    return name, 999 # 非央视频道排后面

def process_ip_group(block):
    """处理单个 IP 组的内容"""
    lines = block.strip().split('\n')
    if not lines: return None
    
    ip_header = lines[0] # 例如: 113.65.162.149:808,#genre#
    
    # 策略：抽取该组第一个频道进行画质探测
    test_url = lines[1].split(',')[1] if len(lines) > 1 else ""
    quality = get_stream_quality(test_url)
    
    processed_channels = []
    for l in lines[1:]:
        if ',' in l:
            name, url = l.split(',', 1)
            std_name, sort_order = clean_and_sort_key(name.strip())
            # 拼接最终显示名称 (带画质后缀)
            display_name = f"{std_name} ({quality})" if quality != "Unknown" else std_name
            processed_channels.append({
                'order': sort_order,
                'name': std_name,
                'line': f"{display_name},{url.strip()}"
            })
    
    # 组内排序：央视 1-17 顺序，其余按原样
    processed_channels.sort(key=lambda x: x['order'])
    
    result = [ip_header] + [ch['line'] for ch in processed_channels]
    return "\n".join(result)

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 找不到输入文件: {INPUT_FILE}")
        return

    print(f"🚀 读取底库: {INPUT_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    groups = [g.strip() for g in content.split('\n\n') if g.strip()]
    print(f"📡 发现 {len(groups)} 个 IP 网段，开始抽样探测...")

    # 并发探测：提升效率，GitHub 环境建议开启 10-20 并发
    results = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(process_ip_group, groups))

    # 过滤掉 None 并写入
    final_output = "\n\n".join([r for r in results if r])
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_output)
    
    print(f"✨ 测试完成！生成结果包含约 {final_output.count(',')/2:.0f} 条链接。")
    print(f"📂 预览文件已保存至: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
