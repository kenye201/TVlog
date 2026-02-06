import os
import re
from urllib.parse import urlparse

# --- 配置区 ---
INPUT_RAW = "tvbox_output.txt"
INPUT_REVIVED = "revived_hotel.txt"
SAVE_PATH = "aggregated_hotel.txt"

def get_ip_port(url):
    try:
        if not url.startswith("http"): url = "http://" + url
        parsed = urlparse(url)
        return parsed.netloc if parsed.netloc else None
    except: return None

def clean_name(name):
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd|综合|财经|影视)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s\t]+', '', name)
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match: return f"CCTV-{int(cctv_match.group(1))}"
    return name

def parse_file(file_path, ip_groups):
    if not os.path.exists(file_path): return
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or "#genre#" in line or line.startswith("#"): continue
            if ',' in line:
                try:
                    name_part, url_part = line.split(',', 1)
                    ip_port = get_ip_port(url_part)
                    if ip_port:
                        if ip_port not in ip_groups: ip_groups[ip_port] = {}
                        c_name = clean_name(name_part)
                        if c_name not in ip_groups[ip_port]: ip_groups[ip_port][c_name] = url_part
                except: continue

def main():
    # 1. 提取所有 IP 组
    ip_groups = {}
    parse_file(INPUT_RAW, ip_groups)
    parse_file(INPUT_REVIVED, ip_groups)

    # 2. 基因过滤与段去重
    # 策略：如果一个 C 段在 revived_hotel.txt 已经存在（说明是复活成功的变异 IP），
    # 那么排除掉 aggregated 中来自 raw 文件但同段且过时的旧 IP。
    segments_best_ip = {}
    for ip_port in ip_groups.keys():
        host = ip_port.split(':')[0]
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
            # 将 IP 归类到 C 段
            c_seg = ".".join(host.split('.')[:3])
            # 记录该段的所有 IP，后续 revive.py 会挨个扫
            if c_seg not in segments_best_ip: segments_best_ip[c_seg] = []
            segments_best_ip[c_seg].append(ip_port)

    # 3. 写入聚合底库
    count = 0
    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        for c_seg in sorted(segments_best_ip.keys()):
            for ip in segments_best_ip[c_seg]:
                f.write(f"{ip},#genre#\n")
                channels = ip_groups[ip]
                sorted_names = sorted(channels.keys(), key=lambda x: (not x.startswith("CCTV"), x))
                for name in sorted_names:
                    f.write(f"{name},{channels[name]}\n")
                f.write("\n")
                count += 1
    
    print(f"✅ 聚合完成：已从新旧源中提取 {count} 个潜在酒店段基因。")

if __name__ == "__main__":
    main()
