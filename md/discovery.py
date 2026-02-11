import os, requests, concurrent.futures, re
from urllib.parse import urlparse

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 3
MAX_WORKERS_IP = 40  # 提取 IP 的并发
MAX_WORKERS_C = 60   # C 段爆破的并发

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

def scan_c_segment(base_ip_port, channel_list):
    """
    对失效 IP 进行 C 段爆破 (1-255)
    返回第一个扫到的活 IP 块内容
    """
    ip, port = base_ip_port.split(':')
    prefix = '.'.join(ip.split('.')[:-1])
    
    # 构造探测任务：扫描该 C 段所有 255 个地址
    test_tasks = []
    for i in range(1, 256):
        target_ip = f"{prefix}.{i}:{port}"
        # 拿第一个频道的路径来测试
        path = channel_list[0].split(',')[1].split(base_ip_port)[-1]
        test_url = f"http://{target_ip}{path}"
        test_tasks.append((target_ip, test_url))

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_C) as executor:
        future_to_ip = {executor.submit(check_url, url): t_ip for t_ip, url in test_tasks}
        for future in concurrent.futures.as_completed(future_to_ip):
            target_ip = future_to_ip[future]
            if future.result():
                print(f"✨ C 段爆破成功: {base_ip_port} -> {target_ip}")
                # 构造新的频道块内容
                new_block = f"{target_ip},#genre#\n"
                for ch in channel_list:
                    name, old_url = ch.split(',', 1)
                    new_url = old_url.replace(base_ip_port, target_ip)
                    new_block += f"{name},{new_url}\n"
                return new_block + "\n"
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

    # 2. 串行处理每个网段（内部使用并发）
    for idx, (ip_port, channels) in enumerate(ip_groups.items()):
        print(f"[{idx+1}/{len(ip_groups)}] 正在处理: {ip_port}")
        
        # 先测原始 IP
        test_url = channels[0].split(',')[1]
        if check_url(test_url):
            print(f"✅ 原始 IP 存活: {ip_port}")
            block = f"{ip_port},#genre#\n" + "\n".join(channels) + "\n\n"
            final_results.append(block)
        else:
            # 原始 IP 不通，立即爆破 C 段
            print(f"🚀 原始 IP 失效，开始 C 段爆破...")
            rescued_block = scan_c_segment(ip_port, channels)
            if rescued_block:
                final_results.append(rescued_block)
            else:
                print(f"💀 该网段彻底失效，已放弃。")

    # 3. 覆盖写入 manual_fix.txt
    if final_results:
        with open(MANUAL_FIX, 'w', encoding='utf-8') as f:
            f.writelines(final_results)
        print(f"🎉 任务完成！共导出 {len(final_results)} 个活网段至 manual_fix.txt")
    else:
        print("⚠️ 未发现任何存活或可修复的网段。")

if __name__ == "__main__":
    main()
