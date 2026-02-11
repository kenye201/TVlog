import os, requests, concurrent.futures, re
from urllib.parse import urlparse

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 4
MAX_WORKERS = 50

def extract_ip_port(url):
    """从 URL 中提取 Host:Port"""
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc
    except:
        return None
    return None

def load_fix_ips():
    """读取补丁库现有的所有 IP"""
    ips = set()
    if os.path.exists(MANUAL_FIX):
        with open(MANUAL_FIX, 'r', encoding='utf-8', errors='ignore') as f:
            # 匹配所有形如 1.2.3.4:80 的字符串
            found = re.findall(r'([\w\.\-]+:\d+)', f.read())
            for item in found:
                ips.add(item.strip())
    return ips

def main():
    existing_ips = load_fix_ips()
    # 结构: { "122.114.131.154:4060": [ "CCTV1,url1", "CCTV2,url2" ] }
    ip_groups = {} 

    print(f"📖 正在解析混合源文件: {MERGED_SOURCE}")
    if not os.path.exists(MERGED_SOURCE):
        print("❌ 错误：找不到文件")
        return

    # --- 1. 扫描提取并按 IP 聚合 ---
    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if "," not in line or "http" not in line:
                continue
            
            parts = line.split(',', 1)
            name = parts[0].strip()
            url = parts[1].strip()
            
            ip_port = extract_ip_port(url)
            if ip_port and ip_port not in existing_ips:
                if ip_port not in ip_groups:
                    ip_groups[ip_port] = []
                # 存入频道名和完整 URL
                ip_groups[ip_port].append(f"{name},{url}")

    if not ip_groups:
        print("✅ 大库中所有 IP 已存在于补丁库或未发现有效 URL。")
        return

    print(f"📡 提取到 {len(ip_groups)} 个全新网段，开始探测存活...")

    # --- 2. 并发探测 ---
    newly_found = []
    
    def check_worker(ip):
        try:
            # 抽取该 IP 下的第一个频道链接进行测试
            test_url = ip_groups[ip][0].split(',')[1]
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"})
            return ip, r.status_code == 200
        except:
            return ip, False

    

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ip = {executor.submit(check_worker, ip): ip for ip in ip_groups}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip, ok = future.result()
            if ok:
                print(f"🌟 [挖到新矿] {ip} ({len(ip_groups[ip])} 频道)")
                # 按照你喜欢的 IP 分组格式构建块
                block = f"{ip},#genre#\n"
                block += "\n".join(ip_groups[ip])
                block += "\n\n"
                newly_found.append(block)

    # --- 3. 追加写入 ---
    if newly_found:
        with open(MANUAL_FIX, 'a', encoding='utf-8') as f:
            f.writelines(newly_found)
        print(f"🚀 追加完成！本次发现 {len(newly_found)} 个新活网段并已格式化存入补丁库。")
    else:
        print("⛈️ 探测结束，没发现能连通的新源。")

if __name__ == "__main__":
    main()
