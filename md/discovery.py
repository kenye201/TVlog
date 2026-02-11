import os, requests, concurrent.futures, re
from urllib.parse import urlparse

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 2  # 爆破时超时缩短，提高单任务周转率
MAX_WORKERS_CHECK = 100 
# 降低爆破任务并发，防止 GitHub 封锁，建议 5-8
MAX_WORKERS_RESCUE = 5 

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

def rescue_task(base_ip_port, channels):
    """C段爆破任务：现在会实时打印探测细节"""
    ip_parts = base_ip_port.split(':')
    if len(ip_parts) != 2: return None
    
    ip, port = ip_parts
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
        print(f"⏩ [跳过] {base_ip_port} 非标准IP，无法执行C段爆破。")
        return None
        
    prefix = '.'.join(ip.split('.')[:-1])
    path = channels[0].split(',')[1].split(base_ip_port)[-1]
    
    print(f"\n🔎 [开始挖掘] 目标网段: {prefix}.1-255:{port}")
    
    for i in range(1, 256):
        target_ip = f"{prefix}.{i}:{port}"
        # 这里是你要的：每个 IP 跳出来的过程
        # 使用 end='' 和 \r 可以让日志在同一行刷新（部分终端支持），
        # 或者直接 print 产生滚动流
        if i % 20 == 0: # 每20个IP打个招呼，防止日志过长
             print(f"  ⏳ {base_ip_port} 正在探测至 .{i} ...")
        
        test_url = f"http://{target_ip}{path}"
        if check_url(test_url):
            print(f"  ✨ [爆破命中!!] {base_ip_port} -> 找到活源: {target_ip}")
            block = f"{target_ip},#genre#\n"
            for ch in channels:
                name, old_url = ch.split(',', 1)
                new_url = old_url.replace(base_ip_port, target_ip)
                block += f"{name},{new_url}\n"
            return block + "\n"
            
    print(f"  ❌ [挖掘失败] {base_ip_port} C段无存活。")
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
    to_rescue = []

    # --- 阶段 1：并发快测 ---
    print(f"\n📡 阶段 1：全量直连探测 (并发:{MAX_WORKERS_CHECK})")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_CHECK) as executor:
        future_to_ip = {executor.submit(check_url, data[0].split(',')[1]): ip for ip, data in ip_groups.items()}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip_port = future_to_ip[future]
            if future.result():
                print(f"  ✅ [直连存活] {ip_port}")
                block = f"{ip_port},#genre#\n" + "\n".join(ip_groups[ip_port]) + "\n\n"
                final_results.append(block)
            else:
                to_rescue.append(ip_port)

    print(f"\n📊 统计：直连成功 {len(final_results)} | 需要爆破 {len(to_rescue)}")

    # --- 阶段 2：串行化/低并发爆破 ---
    if to_rescue:
        print(f"\n🚀 阶段 2：开始执行 C 段挖掘任务 (任务并发:{MAX_WORKERS_RESCUE})")
        # 使用较小的线程池，方便观察每一个任务的滚动日志
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_RESCUE) as executor:
            rescue_futures = {executor.submit(rescue_task, ip, ip_groups[ip]): ip for ip in to_rescue}
            for future in concurrent.futures.as_completed(rescue_futures):
                result_block = future.result()
                if result_block:
                    final_results.append(result_block)

    # 3. 写入文件
    if final_results:
        with open(MANUAL_FIX, 'w', encoding='utf-8') as f:
            f.writelines(final_results)
        print(f"\n🎉 任务完成！有效网段已写入 {MANUAL_FIX}")

if __name__ == "__main__":
    main()
