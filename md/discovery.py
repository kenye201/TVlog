import os, requests, concurrent.futures, re

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 3
MAX_WORKERS = 30

def is_valid_ip(ip_str):
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def load_existing_ips(path):
    """获取 manual_fix.txt 中已经存在的 IP，避免重复添加"""
    ips = set()
    if not os.path.exists(path): return ips
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if "#genre#" in line:
                ips.add(line.split(',')[0].strip())
    return ips

def main():
    existing_ips = load_existing_ips(MANUAL_FIX)
    new_ip_map = {} # 存放新发现的 IP 信息

    # 1. 加载大库中 manual_fix 里没有的 IP
    print(f"📖 正在扫描全量大库: {MERGED_SOURCE}")
    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        cur_ip = None
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                ip = line.split(',')[0].strip()
                # 只探测 manual_fix 里没有的
                if is_valid_ip(ip) and ip not in existing_ips:
                    cur_ip = ip
                    new_ip_map[cur_ip] = []
                else:
                    cur_ip = None
                continue
            if ',' in line and cur_ip:
                new_ip_map[cur_ip].append(line)

    if not new_ip_map:
        print("✅ 大库中的所有 IP 已在手动补丁文件中，无需扫描。")
        return

    print(f"📡 发现 {len(new_ip_map)} 个新基因，开始极速验证...")

    # 2. 探测逻辑
    discovered_blocks = []
    
    def check(ip):
        try:
            # 抽样检测该 IP 的第一个频道
            test_url = new_ip_map[ip][0].split(',')[1].strip()
            r = requests.get(test_url, timeout=TIMEOUT, stream=True)
            return ip, r.status_code == 200
        except: return ip, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(check, ip): ip for ip in new_ip_map}
        for f in concurrent.futures.as_completed(futures):
            ip, ok = f.result()
            if ok:
                print(f"🌟 [新发现] {ip}")
                block = f"{ip},#genre#\n" + "\n".join(new_ip_map[ip]) + "\n\n"
                discovered_blocks.append(block)

    # 3. 追加模式写入 manual_fix.txt
    if discovered_blocks:
        with open(MANUAL_FIX, 'a', encoding='utf-8') as f:
            f.writelines(discovered_blocks)
        print(f"✅ 成功将 {len(discovered_blocks)} 个新 IP 追加到 {MANUAL_FIX}")
    else:
        print("查无新活 IP。")

if __name__ == "__main__":
    main()
