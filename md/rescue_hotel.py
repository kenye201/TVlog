import os, requests, re, concurrent.futures
from urllib.parse import urlparse

TIMEOUT = 2
MAX_WORKERS = 60

def is_valid_ip(ip_str):
    pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:[0-9]+$'
    return bool(re.match(pattern, ip_str))

def check_url(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True)
        return True if r.status_code == 200 else False
    except: return False

def main():
    if not os.path.exists("dead_tasks.txt"): return
    with open("dead_tasks.txt", 'r', encoding='utf-8') as f:
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]
    
    valid_blocks = [b for b in blocks if is_valid_ip(b.split('\n')[0].split(',')[0])]
    print(f"🚑 准备抢救 {len(valid_blocks)} 个网段...", flush=True)

    with open("rescued_temp.txt", 'w', encoding='utf-8') as f_out:
        for idx, block in enumerate(valid_blocks, 1):
            lines = block.split('\n')
            old_ip = lines[0].split(',')[0]
            try:
                ip_part, port = old_ip.split(':')
                prefix = ".".join(ip_part.split('.')[:3])
                path = urlparse(lines[1].split(',')[1]).path
                print(f"[{idx}/{len(valid_blocks)}] 🔎 爆破 C 段: {prefix}.x:{port}", flush=True)
                
                found = False
                tasks = [f"http://{prefix}.{i}:{port}{path}" for i in range(1, 255)]
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                    future_to_url = {exe.submit(check_url, u): u for u in tasks}
                    for fut in concurrent.futures.as_completed(future_to_url):
                        if fut.result():
                            new_host = urlparse(future_to_url[fut]).netloc
                            print(f"   ✨ [成功] {old_ip} -> {new_host}", flush=True)
                            f_out.write(f"{new_host},#genre#\n")
                            for l in lines[1:]:
                                name, url = l.split(',', 1)
                                f_out.write(f"{name},http://{new_host}{urlparse(url).path}\n")
                            f_out.write("\n")
                            found = True
                            exe.shutdown(wait=False, cancel_futures=True)
                            break
                if not found: print(f"   ❌ [失败]", flush=True)
            except: continue
    print("🏁 抢救结束。", flush=True)

if __name__ == "__main__": main()
