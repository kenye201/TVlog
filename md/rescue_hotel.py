import os, requests, re, concurrent.futures
from urllib.parse import urlparse

# 配置
TIMEOUT = 2
MAX_WORKERS = 60 # GitHub Actions 环境建议并发数

def is_valid_ip(ip_str):
    """正则校验：确保只抢救 IP:Port 格式"""
    pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:[0-9]+$'
    return bool(re.match(pattern, ip_str))

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
    
    # 过滤掉非 IP 格式的块
    valid_blocks = []
    for b in blocks:
        header = b.split('\n')[0].split(',')[0]
        if is_valid_ip(header):
            valid_blocks.append(b)
    
    total_blocks = len(valid_blocks)
    if total_blocks == 0:
        print("📊 待抢救清单中没有符合格式的 IP 段，跳过抢救。")
        return

    print(f"🚑 准备抢救 {total_blocks} 个失效网段...")

    with open("rescued_temp.txt", 'w', encoding='utf-8') as f_out:
        for idx, block in enumerate(valid_blocks, 1):
            lines = block.split('\n')
            if len(lines) < 2: continue
            
            old_ip = lines[0].split(',')[0]
            try:
                ip_part, port = old_ip.split(':')
                prefix = ".".join(ip_part.split('.')[:3])
                path = urlparse(lines[1].split(',')[1]).path
                
                print(f"\n[{idx}/{total_blocks}] 🔎 正在爆破 C 段: {prefix}.x:{port}")
                print(f"   目标路径: {path}")
                
                found = False
                tasks_list = [f"http://{prefix}.{i}:{port}{path}" for i in range(1, 255)]
                
                # 用于记录扫描进度的计数器
                scan_count = 0
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                    future_to_url = {exe.submit(check_url, url): url for url in tasks_list}
                    
                    for fut in concurrent.futures.as_completed(future_to_url):
                        scan_count += 1
                        # 每扫描 50 个打印一次小进度，防止看起来像卡死了
                        if scan_count % 50 == 0:
                            print(f"   进度: 已扫描 {scan_count}/254 个地址...")
                            
                        if fut.result():
                            hit_url = future_to_url[fut]
                            new_host = urlparse(hit_url).netloc
                            print(f"   ✨ [救回成功!] 匹配地址: {hit_url}")
                            print(f"   🔄 映射关系: {old_ip} -> {new_host}")
                            
                            # 写入文件
                            f_out.write(f"{new_host},#genre#\n")
                            for l in lines[1:]:
                                name, old_url = l.split(',', 1)
                                f_out.write(f"{name},http://{new_host}{urlparse(old_url).path}\n")
                            f_out.write("\n")
                            
                            found = True
                            # 强行关闭该网段的其他扫描任务
                            exe.shutdown(wait=False, cancel_futures=True)
                            break
                
                if not found:
                    print(f"   ❌ [扫描结束] 该网段 254 个地址全部失效")
            
            except Exception as e:
                print(f"   ⚠️ [跳过] 处理该网段时出错: {e}")

    print("\n🏁 抢救阶段全部结束。")

if __name__ == "__main__":
    main()
