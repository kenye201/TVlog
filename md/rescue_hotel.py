import os, requests, concurrent.futures
from urllib.parse import urlparse

def check_url(url):
    try:
        r = requests.get(url, timeout=2, stream=True)
        return True if r.status_code == 200 else False
    except: return False

def main():
    if not os.path.exists("dead_tasks.txt"): return
    
    with open("dead_tasks.txt", 'r', encoding='utf-8') as f, open("rescued_temp.txt", 'w', encoding='utf-8') as f_out:
        content = f.read().split('\n\n')
        for block in content:
            lines = block.strip().split('\n')
            if len(lines) < 2: continue
            old_ip = lines[0].split(',')[0]
            prefix = ".".join(old_ip.split('.')[:3])
            port = old_ip.split(':')[1]
            path = urlparse(lines[1].split(',')[1]).path
            
            print(f"🔎 扫描 C 段: {prefix}.x:{port}")
            with concurrent.futures.ThreadPoolExecutor(max_workers=60) as exe:
                tasks = {exe.submit(check_url, f"http://{prefix}.{i}:{port}{path}"): i for i in range(1, 256)}
                for fut in concurrent.futures.as_completed(tasks):
                    if fut.result():
                        new_ip = f"{prefix}.{tasks[fut]}:{port}"
                        print(f"✨ 复活成功: {new_ip}")
                        f_out.write(f"{new_ip},#genre#\n")
                        for l in lines[1:]:
                            name, old_url = l.split(',', 1)
                            f_out.write(f"{name},http://{new_ip}{urlparse(old_url).path}\n")
                        f_out.write("\n")
                        exe.shutdown(wait=False, cancel_futures=True)
                        break

if __name__ == "__main__": main()
