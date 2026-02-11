import os, sys, requests, re, concurrent.futures

# --- 路径配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

# 1. 大库源 (只读)
INPUT_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
# 2. 手动补丁 (你可以在这里改名字、改顺序)
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

# 输出文件
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")

TIMEOUT = 3
MAX_WORKERS = 30

def is_valid_ip(ip_str):
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def load_to_map(path, ip_map, is_override=False):
    if not os.path.exists(path):
        return
    print(f"📖 正在加载: {path} {'(强制覆盖模式)' if is_override else '(常规加载)'}")
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        cur_ip = None
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                potential_ip = line.split(',')[0].strip()
                if is_valid_ip(potential_ip):
                    # 如果是常规加载且补丁库已经有了这个IP，我们就跳过整个块
                    if not is_override and potential_ip in ip_map:
                        cur_ip = "SKIP_EXISTING" 
                    else:
                        cur_ip = potential_ip
                        ip_map[cur_ip] = {}
                else: cur_ip = None
                continue
            
            if ',' in line and cur_ip and cur_ip != "SKIP_EXISTING":
                name, url = line.split(',', 1)
                # 保持文件里的原始顺序
                if name.strip() not in ip_map[cur_ip]:
                    ip_map[cur_ip][name.strip()] = url.strip()

def main():
    ip_map = {} # { "IP": { "Name": "URL" } }

    # 1. 先加载【手动补丁】，占据位置
    if os.path.exists(MANUAL_FIX):
        load_to_map(MANUAL_FIX, ip_map, is_override=True)
    
    # 2. 再加载【大库汇总】，如果IP已在补丁中，则跳过
    load_to_map(INPUT_SOURCE, ip_map, is_override=False)

    all_ips = list(ip_map.keys())
    if not all_ips:
        print("❌ 未加载到任何有效 IP")
        return

    print(f"📡 共有 {len(all_ips)} 个 IP 网段参与探测...", flush=True)

    # --- 探测逻辑 (与之前一致) ---
    revived, dead = [], []
    processed = 0

    def check(ip):
        try:
            first_name = list(ip_map[ip].keys())[0]
            test_url = ip_map[ip][first_name]
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"Mozilla/5.0"})
            return ip, r.status_code == 200
        except: return ip, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(check, ip): ip for ip in all_ips}
        for f in concurrent.futures.as_completed(futures):
            processed += 1
            ip, ok = f.result()
            
            block = f"{ip},#genre#\n"
            for name, url in ip_map[ip].items():
                block += f"{name},{url}\n"
            block += "\n"
            
            if ok:
                revived.append(block)
                print(f"[{processed}/{len(all_ips)}] ✅ [存活] {ip}")
            else:
                dead.append(block)
                print(f"[{processed}/{len(all_ips)}] 💀 [失效] {ip}")

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead)

if __name__ == "__main__":
    main()
