import os, requests, re, concurrent.futures
from urllib.parse import urlparse

# --- 路径锁定 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 明确指向 md 目录下的临时文件
INPUT_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")
OUTPUT_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")

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
    # 打印路径调试信息
    print(f"🚑 检查抢救清单: {INPUT_DEAD}", flush=True)
    if not os.path.exists(INPUT_DEAD):
        print("⚠️ 未发现待抢救任务文件，跳过。")
        return

    with open(INPUT_DEAD, 'r', encoding='utf-8') as f:
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]
    
    # 过滤格式
    valid_blocks = []
    for b in blocks:
        header = b.split('\n')[0].split(',')[0]
        if is_valid_ip(header):
            valid_blocks.append(b)
    
    if not valid_blocks:
        print("📊 待抢救清单中没有符合格式的 IP 段。")
        return

    print(f"🚑 准备抢救 {len(valid_blocks)} 个网段...", flush=True)

    with open(OUTPUT_RESCUED, 'w', encoding='utf-8') as f_out:
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
                            print(f"   ✨ [救回成功] {old_ip} -> {new_host}", flush=True)
                            f_out.write(f"{new_host},#genre#\n")
                            for l in lines[1:]:
                                name, url = l.split(',', 1)
                                f_out.write(f"{name},http://{new_host}{urlparse(url).path}\n")
                            f_out.write("\n")
                            found = True
                            exe.shutdown(wait=False, cancel_futures=True)
                            break
                if not found:
                    print(f"   ❌ [失败]", flush=True)
            except Exception as e:
                print(f"   ⚠️ 错误: {e}", flush=True)
                continue

    print("\n🏁 抢救阶段全部结束。", flush=True)

if __name__ == "__main__":
    main()
