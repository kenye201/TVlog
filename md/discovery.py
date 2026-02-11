import os, requests, concurrent.futures, re
from urllib.parse import urlparse

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 2
MAX_WORKERS_CHECK = 100 
MAX_THREADS_PER_C = 30  # 每个C段内部的并发数（加速全段扫描）

def extract_ip_port(url):
    try:
        parsed = urlparse(url)
        if parsed.netloc: return parsed.netloc
    except: return None
    return None

def check_url(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"})
        return r.status_code == 200
    except:
        return False

# 全局去重，防止同一个网段多次录入
found_alive_ips = set()

def main():
    if not os.path.exists(MERGED_SOURCE):
        print("❌ 未找到 history/merged.txt")
        return

    ip_groups = {}
    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if "," not in line or "http" not in line: continue
            parts = line.split(',', 1)
            ip_port = extract_ip_port(parts[1].strip())
            if ip_port:
                if ip_port not in ip_groups: ip_groups[ip_port] = []
                ip_groups[ip_port].append(line)

    print(f"📖 基因库解析完成，共 {len(ip_groups)} 个原始网段。")
    
    final_results = []
    to_rescue = []

    # --- 阶段 1：快测 ---
    print(f"\n📡 阶段 1：直连探测...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_CHECK) as executor:
        future_to_ip = {executor.submit(check_url, data[0].split(',')[1]): ip for ip, data in ip_groups.items()}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip_port = future_to_ip[future]
            if future.result():
                if ip_port not in found_alive_ips:
                    found_alive_ips.add(ip_port)
                    print(f"  ✅ [直连存活] {ip_port}")
                    block = f"{ip_port},#genre#\n" + "\n".join(ip_groups[ip_port]) + "\n\n"
                    final_results.append(block)
            else:
                to_rescue.append(ip_port)

    # --- 阶段 2：深度挖掘（实时可见过程） ---
    if to_rescue:
        print(f"\n🚀 阶段 2：开始执行 C 段挖掘任务 (共 {len(to_rescue)} 个)...")
        for idx, base_ip_port in enumerate(to_rescue):
            ip_parts = base_ip_port.split(':')
            if len(ip_parts) != 2: continue
            ip, port = ip_parts
            if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip): continue
            
            prefix = '.'.join(ip.split('.')[:-1])
            channels = ip_groups[base_ip_port]
            path = channels[0].split(',')[1].split(base_ip_port)[-1]
            
            print(f"[{idx+1}/{len(to_rescue)}] 🔎 正在扫描网段: {prefix}.1-255:{port}")
            
            test_tasks = [(f"{prefix}.{i}:{port}", f"http://{prefix}.{i}:{port}{path}") for i in range(1, 256)]
            
            # 使用内层并发加速 C 段扫描
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS_PER_C) as inner_executor:
                future_to_target = {inner_executor.submit(check_url, url): t_ip for t_ip, url in test_tasks}
                for future in concurrent.futures.as_completed(future_to_target):
                    target_ip = future_to_target[future]
                    if future.result():
                        if target_ip not in found_alive_ips:
                            found_alive_ips.add(target_ip)
                            print(f"  ✨ [爆破命中!!] {target_ip}")
                            block = f"{target_ip},#genre#\n"
                            for ch in channels:
                                name, old_url = ch.split(',', 1)
                                new_url = old_url.replace(base_ip_port, target_ip)
                                block += f"{name},{new_url}\n"
                            final_results.append(block + "\n")

    # 3. 写入文件
    if final_results:
        with open(MANUAL_FIX, 'w', encoding='utf-8') as f:
            f.writelines(final_results)
        print(f"\n🎉 任务完成！共捕获 {len(found_alive_ips)} 个独立网段。")

if __name__ == "__main__":
    main()
