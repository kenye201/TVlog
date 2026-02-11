import os, requests, concurrent.futures, re

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 3
MAX_WORKERS = 50 # 挖矿脚本，线程开大一点

def is_valid_ip(ip_str):
    """同时匹配 IP:Port 和 域名:Port"""
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def load_existing_ips(path):
    """读取已有的补丁库 IP，避免重复追加"""
    ips = set()
    if not os.path.exists(path): return ips
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if "#genre#" in line:
                parts = line.split(',')
                if parts: ips.add(parts[0].strip())
    return ips

def main():
    existing_ips = load_existing_ips(MANUAL_FIX)
    all_ip_data = {} # { "IP:Port": [频道列表] }

    print(f"📖 正在扫描汇总源: {MERGED_SOURCE}")
    if not os.path.exists(MERGED_SOURCE):
        print("❌ 错误：源文件不存在")
        return

    # --- 1. 改进的解析器 ---
    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        current_ip = None
        for line in f:
            line = line.strip()
            if not line: continue
            
            # 识别 IP 分组行 (例如: 122.114.131.154:8080,#genre#)
            if "#genre#" in line:
                ip_part = line.split(',')[0].strip()
                if is_valid_ip(ip_part):
                    current_ip = ip_part
                    if current_ip not in all_ip_data:
                        all_ip_data[current_ip] = []
                continue
            
            # 识别频道行 (例如: CCTV1,http://...)
            if "," in line and current_ip:
                all_ip_data[current_ip].append(line)

    # 过滤掉 manual_fix 里已经存在的 IP
    targets = {ip: data for ip, data in all_ip_data.items() if ip not in existing_ips}
    
    print(f"📡 基因库总计: {len(all_ip_data)} 个 IP")
    print(f"🔎 补丁库已存: {len(existing_ips)} 个 IP")
    print(f"🚀 本次待测新 IP: {len(targets)} 个")

    if not targets:
        print("✨ 没有发现新 IP。")
        return

    # --- 2. 探测存活 ---
    newly_discovered = []
    
    def check_worker(ip):
        try:
            # 抽样检测该 IP 下第一个频道
            test_url = targets[ip][0].split(',')[1].strip()
            # 模拟 VLC 请求
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent": "VLC/3.0"})
            if r.status_code == 200:
                return ip, True
        except:
            pass
        return ip, False

    

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ip = {executor.submit(check_worker, ip): ip for ip in targets}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip, is_alive = future.result()
            if is_alive:
                print(f"🌟 [发现新存活] {ip}")
                # 构造标准块
                block = f"{ip},#genre#\n" + "\n".join(targets[ip]) + "\n\n"
                newly_discovered.append(block)

    # --- 3. 追加写入 ---
    if newly_discovered:
        # 使用 'a' 追加模式，不破坏你手动改好的 manual_fix.txt 前面部分
        with open(MANUAL_FIX, 'a', encoding='utf-8') as f:
            f.writelines(newly_discovered)
        print(f"✅ 成功追加 {len(newly_discovered)} 个新网段到 manual_fix.txt")
    else:
        print("本次未发现新存活网段。")

if __name__ == "__main__":
    main()
