import os, sys, requests, re, concurrent.futures
from urllib.parse import urlparse

# 配置
INPUT_RAW = "tvbox_output.txt"
LOCAL_BASE = "md/aggregated_hotel.txt"
MID_REVIVED = "revived_temp.txt"
MID_DEAD = "dead_tasks.txt"
TIMEOUT = 3
MAX_WORKERS = 30

def is_valid_ip(ip_str):
    """校验 IP:Port 或 域名:Port"""
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def main():
    ip_map = {} # 字典嵌套结构，自动去重

    def load_data(path, label):
        if not os.path.exists(path): return
        print(f"📖 正在加载 {label}: {path}", flush=True)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            cur_ip = None
            for line in f:
                line = line.strip()
                if not line: continue
                if "#genre#" in line:
                    potential_ip = line.split(',')[0].strip()
                    if is_valid_ip(potential_ip):
                        cur_ip = potential_ip
                        if cur_ip not in ip_map: ip_map[cur_ip] = {}
                    else: cur_ip = None
                    continue
                if ',' in line and cur_ip:
                    name, url = line.split(',', 1)
                    # 关键修改：如果底库已经有的频道，绝对不覆盖，保护手动修改
                    if name.strip() not in ip_map[cur_ip]:
                        ip_map[cur_ip][name.strip()] = url.strip()

    # ！！！顺序至关重要：先加载底库（你的修改），再加载抓取源！！！
    load_data("aggregated_hotel.txt", "手动底库")
    load_data("tvbox_output.txt", "新抓取源")

    all_ips = list(ip_map.keys())
    total_ips = len(all_ips)
    print(f"📡 共有 {total_ips} 个有效 IP 网段参与探测...", flush=True)

    revived, dead = [], []
    processed = 0

    def check(ip):
        try:
            # 取该 IP 下的第一个频道测试
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
            # 还原成文件格式
            block_content = f"{ip},#genre#\n"
            for name, url in ip_map[ip].items():
                block_content += f"{name},{url}\n"
            block_content += "\n"
            
            if ok:
                revived.append(block_content)
                print(f"[{processed}/{total_ips}] ✅ [存活] {ip}", flush=True)
            else:
                dead.append(block_content)
                print(f"[{processed}/{total_ips}] 💀 [失效] {ip}", flush=True)

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead)
    print(f"📊 探测完成。存活: {len(revived)} | 待抢救: {len(dead)}", flush=True)

if __name__ == "__main__": main()
