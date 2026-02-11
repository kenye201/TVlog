import os, requests, concurrent.futures, re
from urllib.parse import urlparse

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 3
MAX_WORKERS_CHECK = 100 # 第一步快测：并发开大
MAX_WORKERS_RESCUE = 100 # 第二步爆破：总并发控制

def extract_ip_port(url):
    try:
        parsed = urlparse(url)
        if parsed.netloc: return parsed.netloc
    except: return None
    return None

def check_url(url):
    """检测单个 URL 是否存活"""
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"})
        return r.status_code == 200
    except:
        return False

def rescue_task(base_ip_port, channels):
    """C段爆破单个网段的任务函数"""
    ip, port = base_ip_port.split(':')
    # 过滤掉非 IP 的域名（域名无法爆破 C 段）
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
        return None
        
    prefix = '.'.join(ip.split('.')[:-1])
    path = channels[0].split(',')[1].split(base_ip_port)[-1]
    
    # 构造该 C 段所有 255 个探测地址
    for i in range(1, 256):
        target_ip = f"{prefix}.{i}:{port}"
        if target_ip == base_ip_port: continue # 跳过已知的死 IP
        
        test_url = f"http://{target_ip}{path}"
        if check_url(test_url):
            # 只要找到一个活的，立即返回块内容
            block = f"{target_ip},#genre#\n"
            for ch in channels:
                name, old_url = ch.split(',', 1)
                new_url = old_url.replace(base_ip_port, target_ip)
                block += f"{name},{new_url}\n"
            return block + "\n"
    return None

def main():
    if not os.path.exists(MERGED_SOURCE):
        print("❌ 未找到 history/merged.txt")
        return

    # 1. 解析归类
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
    to_rescue = [] # 存放失效网段进行爆破

    # --- 第一步：并发快测原始 IP ---
    print(f"📡 阶段 1：正在快速检测原始 IP 存活情况...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_CHECK) as executor:
        future_to_ip = {executor.submit(check_url, data[0].split(',')[1]): ip for ip, data in ip_groups.items()}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip_port = future_to_ip[future]
            if future.result():
                print(f"✅ [直连存活] {ip_port}")
                block = f"{ip_port},#genre#\n" + "\n".join(ip_groups[ip_port]) + "\n\n"
                final_results.append(block)
            else:
                to_rescue.append(ip_port)

    print(f"📊 统计：直连成功 {len(final_results)} 个，待爆破抢救 {len(to_rescue)} 个。")

    # --- 第二步：并发执行 C 段爆破 ---
    if to_rescue:
        print(f"🚀 阶段 2：开始并行 C 段爆破（耗时较长，请耐心等待）...")
        # 限制爆破任务的并发，防止 CPU/带宽 瞬间过载
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            rescue_futures = {executor.submit(rescue_task, ip, ip_groups[ip]): ip for ip in to_rescue}
            for future in concurrent.futures.as_completed(rescue_futures):
                orig_ip = rescue_futures[future]
                result_block = future.result()
                if result_block:
                    print(f"✨ [抢救成功] 原始: {orig_ip}")
                    final_results.append(result_block)
                else:
                    # print(f"💀 [彻底失效] {orig_ip}")
                    pass

    # 3. 写入文件
    if final_results:
        with open(MANUAL_FIX, 'w', encoding='utf-8') as f:
            f.writelines(final_results)
        print(f"🎉 任务完成！共导出 {len(final_results)} 个活网段至 manual_fix.txt")

if __name__ == "__main__":
    main()
