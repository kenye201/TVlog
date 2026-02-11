import os, requests, re, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")

TIMEOUT = 3
MAX_THREADS_SCAN = 40

def check_url(url):
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except: return False

def main():
    if not os.path.exists(MANUAL_FIX):
        print("❌ manual_fix.txt 不存在", flush=True)
        return

    with open(MANUAL_FIX, 'r', encoding='utf-8') as f:
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]
    
    revived_list, dead_list = [], []
    
    for idx, block in enumerate(blocks):
        lines = block.split('\n')
        base_ip_port = lines[0].split(',')[0].strip()
        test_url = lines[1].split(',', 1)[1].strip()
        
        print(f"[{idx+1}/{len(blocks)}] ⚖️ 检查: {base_ip_port}", flush=True)
        
        if check_url(test_url):
            print("  ✅ 存活", flush=True)
            revived_list.append(block + "\n\n")
        else:
            print("  💀 失效 -> 尝试即时复活...", flush=True)
            ip, port = base_ip_port.split(':')
            prefix = '.'.join(ip.split('.')[:-1])
            path = test_url.split(base_ip_port)[-1]
            
            revived_ip = None
            test_tasks = {f"http://{prefix}.{i}:{port}{path}": f"{prefix}.{i}:{port}" for i in range(1, 256)}
            
            with ThreadPoolExecutor(max_workers=MAX_THREADS_SCAN) as executor:
                futures = {executor.submit(check_url, url): t_ip for url, t_ip in test_tasks.items()}
                for f in as_completed(futures):
                    if f.result():
                        revived_ip = futures[f]
                        break
            
            if revived_ip:
                print(f"  ✨ 复活成功: {revived_ip}", flush=True)
                new_block = f"{revived_ip},#genre#\n"
                for ch in lines[1:]:
                    name, old_url = ch.split(',', 1)
                    new_block += f"{name},{old_url.replace(base_ip_port, revived_ip)}\n"
                revived_list.append(new_block + "\n\n")
            else:
                print("  ❌ 复活失败", flush=True)
                dead_list.append(block + "\n\n")

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived_list)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead_list)

if __name__ == "__main__":
    main()
