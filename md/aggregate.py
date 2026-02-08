import os, sys, requests, concurrent.futures
from urllib.parse import urlparse

# 配置
INPUT_RAW = "tvbox_output.txt"
LOCAL_BASE = "aggregated_hotel.txt"
MID_REVIVED = "revived_temp.txt"
MID_DEAD = "dead_tasks.txt"
TIMEOUT = 3
MAX_WORKERS = 30  # 适当增加并发

def get_ip_port(url):
    try: return urlparse(url).netloc
    except: return None

def main():
    ip_map = {}
    def load_file(path):
        if not os.path.exists(path): return
        print(f"📖 正在加载文件: {path}")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            cur_ip = None
            for line in f:
                line = line.strip()
                if not line: continue
                if "#genre#" in line:
                    if "," in line: cur_ip = line.split(',')[0]
                    continue
                if ',' in line and cur_ip:
                    if cur_ip not in ip_map: ip_map[cur_ip] = []
                    ip_map[cur_ip].append(line)

    load_file(INPUT_RAW)
    load_file(LOCAL_BASE)

    total_ips = len(ip_map)
    print(f"📡 共有 {total_ips} 个待测网段，启动并发探测...")

    revived, dead = [], []
    processed = 0

    def check(ip):
        try:
            test_url = ip_map[ip][0].split(',')[1]
            # 模拟浏览器 Header 提高成功率
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"Mozilla/5.0"})
            return ip, r.status_code == 200
        except: return ip, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(check, ip): ip for ip in ip_map}
        for f in concurrent.futures.as_completed(futures):
            processed += 1
            ip, ok = f.result()
            target_data = f"{ip},#genre#\n" + "\n".join(ip_map[ip]) + "\n\n"
            
            if ok:
                revived.append(target_data)
                print(f"[{processed}/{total_ips}] ✅ [存活] {ip}")
            else:
                dead.append(target_data)
                print(f"[{processed}/{total_ips}] 💀 [失效] {ip}")

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead)
    
    print(f"\n📊 探测总结: 直连存活 {len(revived)} 个，待抢救 {len(dead)} 个。")

if __name__ == "__main__":
    main()
