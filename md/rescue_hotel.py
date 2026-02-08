import os, requests, concurrent.futures
from urllib.parse import urlparse

# 配置
TIMEOUT = 2
MAX_WORKERS = 60 # C段扫描建议并发设高一点

def check_url(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, stream=True)
        return True if r.status_code == 200 else False
    except: return False

def main():
    if not os.path.exists("dead_tasks.txt"):
        print("⚠️ 未发现待抢救任务 dead_tasks.txt")
        return
    
    with open("dead_tasks.txt", 'r', encoding='utf-8') as f:
        # 按双换行符分割网段块
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]
    
    total_blocks = len(blocks)
    print(f"🚑 准备抢救 {total_blocks} 个失效网段...")

    with open("rescued_temp.txt", 'w', encoding='utf-8') as f_out:
        for idx, block in enumerate(blocks, 1):
            lines = block.split('\n')
            if len(lines) < 2: continue
            
            old_ip = lines[0].split(',')[0]
            try:
                # 提取 IP 段、端口和路径
                ip_part, port = old_ip.split(':')
                prefix = ".".join(ip_part.split('.')[:3])
                path = urlparse(lines[1].split(',')[1]).path
                
                print(f"\n[{idx}/{total_blocks}] 🔎 扫描 C 段: {prefix}.x:{port}")
                
                found = False
                # 预生成 1-254 的测试地址
                tasks_list = [f"http://{prefix}.{i}:{port}{path}" for i in range(1, 255)]
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                    # 使用 dict 记录 future 对应的 IP 后缀
                    future_to_ip = {exe.submit(check_url, url): url for url in tasks_list}
                    
                    for fut in concurrent.futures.as_completed(future_to_ip):
                        if fut.result():
                            hit_url = future_to_ip[fut]
                            new_host = urlparse(hit_url).netloc
                            print(f"   ✨ [救回成功] {old_ip} -> {new_host}")
                            
                            # 写入文件
                            f_out.write(f"{new_host},#genre#\n")
                            for l in lines[1:]:
                                name, old_url = l.split(',', 1)
                                f_out.write(f"{name},http://{new_host}{urlparse(old_url).path}\n")
                            f_out.write("\n")
                            
                            found = True
                            # 只要扫到一个活的，立刻停止该网段剩余的所有扫描任务
                            exe.shutdown(wait=False, cancel_futures=True)
                            break
                
                if not found:
                    print(f"   ❌ [扫描结束] 未能找到可用出口")
            
            except Exception as e:
                print(f"   ⚠️ [错误] 跳过该段，原因: {e}")

    print("\n🏁 抢救阶段全部结束。")

if __name__ == "__main__":
    main()
