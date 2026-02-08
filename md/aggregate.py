import os, sys, requests, concurrent.futures
from urllib.parse import urlparse

# 配置
INPUT_RAW = "tvbox_output.txt"
LOCAL_BASE = "aggregated_hotel.txt"
MID_REVIVED = "revived_temp.txt"
MID_DEAD = "dead_tasks.txt"
TIMEOUT = 3

def get_ip_port(url):
    try: return urlparse(url).netloc
    except: return None

def main():
    ip_map = {}
    def load_file(path):
        if not os.path.exists(path): return
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            cur_ip = None
            for line in f:
                line = line.strip()
                if not line: continue
                if "#genre#" in line:
                    cur_ip = line.split(',')[0]
                    if cur_ip not in ip_map: ip_map[cur_ip] = []
                elif ',' in line and cur_ip:
                    ip_map[cur_ip].append(line)

    load_file(INPUT_RAW)
    load_file(LOCAL_BASE)

    revived, dead = [], []
    def check(ip):
        try:
            test_url = ip_map[ip][0].split(',')[1]
            r = requests.get(test_url, timeout=TIMEOUT, stream=True)
            return ip, r.status_code == 200
        except: return ip, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
        futures = {exe.submit(check, ip): ip for ip in ip_map}
        for f in concurrent.futures.as_completed(futures):
            ip, ok = f.result()
            target = revived if ok else dead
            target.append(f"{ip},#genre#\n" + "\n".join(ip_map[ip]) + "\n")

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead)
    print(f"✅ 提取完成。存活: {len(revived)} | 待抢救: {len(dead)}")

if __name__ == "__main__": main()
