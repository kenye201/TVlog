import os, requests, re, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 基础配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 2
MAX_THREADS_CHECK = 100 # 第一阶段体检并发
MAX_THREADS_SCAN = 40   # 第二阶段爆破并发

def check_url(url):
    """检测单个 URL 是否通畅"""
    try:
        # stream=True 只读头部，速度最快
        with requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except:
        return False

def main():
    if not os.path.exists(MERGED_SOURCE):
        print(f"❌ 错误：找不到源文件 {MERGED_SOURCE}", flush=True)
        return

    # 1. 解析原始网段
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

    print(f"📖 基因库解析完成，共 {len(ip_groups)} 个原始网段。", flush=True)
    
    final_results = []
    found_ips = set()
    to_rescue = []

    # --- 阶段 1：先测存活 (全量体检) ---
    print(f"\n📡 阶段 1：全量体检开始 (并发:{MAX_THREADS_CHECK})...", flush=True)
    with ThreadPoolExecutor(max_workers=MAX_THREADS_CHECK) as executor:
        future_to_ip = {executor.submit(check_url, data[0].split(',')[1]): ip for ip, data in ip_groups.items()}
        for future in as_completed(future_to_ip):
            ip_port = future_to_ip[future]
            if future.result():
                if ip_port not in found_ips:
                    found_ips.add(ip_port)
                    print(f"  ✅ [存活] {ip_port}", flush=True)
                    block = f"{ip_port},#genre#\n" + "\n".join(ip_groups[ip_port]) + "\n\n"
                    final_results.append(block)
            else:
                to_rescue.append(ip_port)

    print(f"\n📊 统计：直连存活 {len(final_results)} 个，需爆破抢救 {len(to_rescue)} 个。", flush=True)

    # --- 阶段 2：只对失效 IP 进行爆破 ---
    if to_rescue:
        print(f"\n🚀 阶段 2：开始地毯式爆破失效网段...", flush=True)
        to_rescue.sort()
        for idx, base_ip_port in enumerate(to_rescue):
            ip_parts = base_ip_port.split(':')
            if len(ip_parts) != 2: continue
            ip, port = ip_parts
            if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip): continue
            
            prefix = '.'.join(ip.split('.')[:-1])
            channels = ip_groups[base_ip_port]
            path = channels[0].split(',')[1].split(base_ip_port)[-1]
            
            print(f"进度:[{idx+1}/{len(to_rescue)}] 🔎 爆破中: {prefix}.0/24:{port}", flush=True)

            test_tasks = {f"http://{prefix}.{i}:{port}{path}": f"{prefix}.{i}:{port}" for i in range(1, 256)}
            
            with ThreadPoolExecutor(max_workers=MAX_THREADS_SCAN) as executor:
                future_to_url = {executor.submit(check_url, url): target_ip for url, target_ip in test_tasks.items()}
                for future in as_completed(future_to_url):
                    target_ip = future_to_url[future]
                    if future.result():
                        if target_ip not in found_ips:
                            found_ips.add(target_ip)
                            print(f"  ✨ [命中!!] -> {target_ip}", flush=True)
                            new_block = f"{target_ip},#genre#\n"
                            for ch in channels:
                                name, old_url = ch.split(',', 1)
                                new_url = old_url.replace(base_ip_port, target_ip)
                                new_block += f"{name},{new_url}\n"
                            final_results.append(new_block + "\n")

    # 3. 最终写入 manual_fix.txt
    if final_results:
        with open(MANUAL_FIX, 'w', encoding='utf-8') as f:
            f.writelines(final_results)
        print(f"\n🎉 任务完成！结果已同步至 {MANUAL_FIX}", flush=True)

if __name__ == "__main__":
    main()
