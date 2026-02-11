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

def get_existing_ip_ports():
    """从现有的 manual_fix.txt 中提取所有 IP:端口"""
    ip_ports = set()
    if os.path.exists(MANUAL_FIX):
        try:
            with open(MANUAL_FIX, 'r', encoding='utf-8') as f:
                content = f.read()
                # 匹配格式如 123.123.123.123:808
                found = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)', content)
                ip_ports.update(found)
        except Exception as e:
            print(f"⚠️ 读取现有库失败: {e}")
    return ip_ports

def main():
    if not os.path.exists(MERGED_SOURCE):
        print(f"❌ 错误：找不到源文件 {MERGED_SOURCE}", flush=True)
        return

    # 0. 预读取现有库，防止重复追加
    existing_set = get_existing_ip_ports()
    print(f"📑 现有库检测：已存在 {len(existing_set)} 个唯一网段。", flush=True)

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
    found_ips = set() # 本次任务中新发现的 IP
    to_rescue = []

    # --- 阶段 1：先测存活 (全量体检) ---
    print(f"\n📡 阶段 1：全量体检开始 (并发:{MAX_THREADS_CHECK})...", flush=True)
    with ThreadPoolExecutor(max_workers=MAX_THREADS_CHECK) as executor:
        future_to_ip = {executor.submit(check_url, data[0].split(',')[1]): ip for ip, data in ip_groups.items()}
        for future in as_completed(future_to_ip):
            ip_port = future_to_ip[future]
            if future.result():
                # 过滤：如果库里已经有了，就不再处理
                if ip_port not in existing_set and ip_port not in found_ips:
                    found_ips.add(ip_port)
                    print(f"  ✅ [新发现-存活] {ip_port}", flush=True)
                    block = f"{ip_port},#genre#\n" + "\n".join(ip_groups[ip_port]) + "\n\n"
                    final_results.append(block)
                # 如果已在库中，默默跳过
            else:
                to_rescue.append(ip_port)

    # --- 阶段 2：只对失效 IP 进行爆破 ---
    if to_rescue:
        print(f"\n🚀 阶段 2：开始地毯式爆破失效网段 (待处理:{len(to_rescue)})...", flush=True)
        to_rescue.sort()
        for idx, base_ip_port in enumerate(to_rescue):
            ip_parts = base_ip_port.split(':')
            if len(ip_parts) != 2: continue
            ip, port = ip_parts
            if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip): continue
            
            prefix = '.'.join(ip.split('.')[:-1])
            channels = ip_groups[base_ip_port]
            path = channels[0].split(',')[1].split(base_ip_port)[-1]
            
            test_tasks = {f"http://{prefix}.{i}:{port}{path}": f"{prefix}.{i}:{port}" for i in range(1, 256)}
            
            with ThreadPoolExecutor(max_workers=MAX_THREADS_SCAN) as executor:
                future_to_url = {executor.submit(check_url, url): target_ip for url, target_ip in test_tasks.items()}
                for future in as_completed(future_to_url):
                    target_ip = future_to_url[future]
                    if future.result():
                        # 过滤：库里没有 且 本次也没发现过
                        if target_ip not in existing_set and target_ip not in found_ips:
                            found_ips.add(target_ip)
                            print(f"  ✨ [命中新源!!] -> {target_ip}", flush=True)
                            new_block = f"{target_ip},#genre#\n"
                            for ch in channels:
                                name, old_url = ch.split(',', 1)
                                new_url = old_url.replace(base_ip_port, target_ip)
                                new_block += f"{name},{new_url}\n"
                            final_results.append(new_block + "\n")

    # 3. 最终追加写入 manual_fix.txt
    if final_results:
        print(f"\n💾 准备写入：本次共发现 {len(final_results)} 个新网段。", flush=True)
        try:
            with open(MANUAL_FIX, 'a', encoding='utf-8') as f:
                # 检查文件末尾是否有换行
                if os.path.exists(MANUAL_FIX) and os.path.getsize(MANUAL_FIX) > 0:
                    f.write("\n\n")
                f.writelines(final_results)
            print(f"🎉 任务完成！新内容已追加至 {MANUAL_FIX}", flush=True)
        except Exception as e:
            print(f"❌ 写入失败: {e}")
    else:
        print("\n📭 本次扫描未发现库以外的新网段。", flush=True)

if __name__ == "__main__":
    main()
