import os
import re
from urllib.parse import urlparse

# --- 配置区 ---
# 输入源1：定期更新的抓取杂源
INPUT_RAW = "tvbox_output.txt"
# 输入源2：之前复活成功及存活的活源（具有优选基因）
INPUT_REVIVED = "revived_hotel.txt"
# 输出：聚合后的扫描底库
SAVE_PATH = "aggregated_hotel.txt"

def get_ip_port(url):
    """提取 URL 中的 IP:Port"""
    try:
        if not url.startswith("http"):
            url = "http://" + url
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc
    except:
        return None
    return None

def clean_name(name):
    """标准化频道名"""
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd|综合|财经|影视)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s\t]+', '', name)
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match:
        return f"CCTV-{int(cctv_match.group(1))}"
    return name

def parse_file(file_path, ip_groups):
    """解析文件并将频道存入对应的 IP 组"""
    if not os.path.exists(file_path):
        print(f"⚠️ 跳过: 找不到文件 {file_path}")
        return
    
    print(f"📖 正在处理: {file_path}")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            # 跳过空行、分类行和 M3U 头部
            if not line or "#genre#" in line or line.startswith("#"):
                continue
            
            if ',' in line:
                try:
                    name_part, url_part = line.split(',', 1)
                    ip_port = get_ip_port(url_part)
                    if ip_port:
                        if ip_port not in ip_groups:
                            ip_groups[ip_port] = {}
                        
                        # 标准化频道名
                        c_name = clean_name(name_part)
                        # 如果该 IP 组还没存过这个频道，则存入
                        if c_name not in ip_groups[ip_port]:
                            ip_groups[ip_port][c_name] = url_part
                except:
                    continue

def main():
    # 数据结构: { "IP:Port": { "标准化频道名": "URL" } }
    ip_groups = {}

    # 1. 处理两个来源
    parse_file(INPUT_RAW, ip_groups)
    parse_file(INPUT_REVIVED, ip_groups)

    # 2. 写入聚合底库
    print(f"🧪 正在提取基因并写入 {SAVE_PATH}...")
    
    # 过滤掉非 IP 形式的域名源 (比如带有 hotel.com 的)
    # 同时过滤掉频道数太少的 IP（比如一个 IP 只有一个频道，可能不是酒店机房）
    valid_ips = []
    for ip_port in ip_groups.keys():
        host = ip_port.split(':')[0]
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
            valid_ips.append(ip_port)

    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        for ip in sorted(valid_ips):
            # 写入酒店标识头
            f.write(f"{ip},#genre#\n")
            
            channels = ip_groups[ip]
            # 排序：CCTV在前
            sorted_names = sorted(channels.keys(), key=lambda x: (not x.startswith("CCTV"), x))
            
            for name in sorted_names:
                f.write(f"{name},{channels[name]}\n")
            
            f.write("\n") # 组间距

    print(f"✨ 聚合完成！")
    print(f"📉 原始数据点：{len(ip_groups)} 个 IP 组合")
    print(f"🎯 最终扫描目标：{len(valid_ips)} 个酒店基因段")

if __name__ == "__main__":
    main()
