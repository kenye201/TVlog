import os, requests, concurrent.futures, re
from urllib.parse import urlparse

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 2
MAX_WORKERS_CHECK = 100 
MAX_WORKERS_RESCUE = 5   # 同时扫描的 C 段任务数
MAX_THREADS_PER_C = 25  # 每个 C 段内部的探测并发数

# 使用 Session 提升连接效率
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
session.mount('http://', adapter)
session.mount('https://', adapter)

def check_url(url):
    try:
        # stream=True 配合 close()，只读头部不读正文，速度最快
        with session.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except:
        return False

found_alive_ips = set()

def rescue_task(base_ip_port, channels):
    """地毯式扫描整个 C 段"""
    ip_parts = base_ip_port.split(':')
    if len(ip_parts) != 2: return []
    ip, port = ip_parts
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip): return []
        
    prefix = '.'.join(ip.split('.')[:-1])
    path = channels[0].split(',')[1].split(base_ip_port)[-1]
    
    print(f"🔎 挖掘中: {prefix}.0/24:{port}")
    
    discovered_blocks = []
    test_tasks = [(f"{prefix}.{i}:{port}", f"http://{prefix}.{i}:{port}{path}") for i in range(1, 256)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS_PER_C) as inner_executor:
        future_to_ip = {inner_executor.submit(check_url, url): t_ip for t_ip, url in test_tasks}
        for future in concurrent.futures.as_completed(future_to_ip):
            target_ip = future_to_ip[future]
            if future.result():
                if target_ip not in found_alive_ips:
                    found_alive_ips.add(target_ip)
                    print(f"  ✨ [命中] {target_ip}")
                    block = f"{target_ip},#genre#\n"
                    for ch in channels:
                        name, old_url = ch.split(',', 1)
                        new_url = old_url.replace(base_ip_port, target_ip)
                        block += f"{name},{new_url}\n"
                    discovered_blocks.append(block + "\n")
    return discovered_blocks

def main():
    # 启动前拉取最新代码，防止底库过旧
    os.system("git pull --rebase origin main")
    
    if not os.path.exists(MERGED_SOURCE): return

    ip_groups = {}
    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if "," not in line or "http" not in line: continue
            url = line.split(',', 1)[1].strip()
            ip_port = urlparse(url).netloc
            if ip_port:
                if ip_port not in ip_groups: ip_groups[ip_port] = []
                ip_groups[ip_port].append(line)

    final_results = []
    to_rescue = []

    print(f"📡 阶段 1：快速筛选直连存活...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_CHECK) as executor:
        future_to_ip = {executor.submit(check_url, data[0].split(',')[1]): ip for ip, data in ip_groups.items()}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip_port = future_to_ip[future]
            if future.result():
                if ip_port not in found_alive_ips:
                    found_alive_ips.add(ip_port)
                    final_results.append(f"{ip_port},#genre#\n" + "\n".join(ip_groups[ip_port]) + "\n\n")
            else:
                to_rescue.append(ip_port)

    if to_rescue:
        print(f"🚀 阶段 2：深度挖掘 {len(to_rescue)} 个失效网段...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_RESCUE) as executor:
            rescue_futures = {executor.submit(rescue_task, ip, ip_groups[ip]): ip for ip in to_rescue}
            for future in concurrent.futures.as_completed(rescue_futures):
                blocks = future.result()
                if blocks: final_results.extend(blocks)

    if final_results:
        with open(MANUAL_FIX, 'w', encoding='utf-8') as f:
            f.writelines(final_results)
        print(f"🎉 挖掘结束，共保存 {len(found_alive_ips)} 个存活源。")

if __name__ == "__main__":
    main()
