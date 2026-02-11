import os, requests, re, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 基础配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")

TIMEOUT = 3
MAX_THREADS_SCAN = 40

def check_url(url):
    """检测 URL 是否通畅"""
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except:
        return False

def is_ip_format(host):
    """判断是否为纯 IP 格式 (用于决定是否启动爆破)"""
    # 匹配数字.数字.数字.数字:端口
    return bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$', host))

def main():
    if not os.path.exists(MANUAL_FIX):
        print("❌ 错误: manual_fix.txt 不存在", flush=True)
        return

    with open(MANUAL_FIX, 'r', encoding='utf-8') as f:
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]
    
    revived_list, dead_list = [], []
    
    print(f"🚀 开始全量体检，共计 {len(blocks)} 个源块...", flush=True)

    for idx, block in enumerate(blocks):
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        
        # 第一行通常是：124.93.18.239:81,#genre# 或 域名:端口,#genre#
        first_line_parts = lines[0].split(',')
        base_host = first_line_parts[0].strip() # 提取 IP:端口 或 域名:端口
        
        # 获取测试 URL
        try:
            test_url = lines[1].split(',', 1)[1].strip()
        except IndexError:
            print(f"[{idx+1}/{len(blocks)}] ❌ 格式错误: {base_host}", flush=True)
            continue

        print(f"[{idx+1}/{len(blocks)}] ⚖️ 检查: {base_host}", flush=True)
        
        # --- 第一步：所有源不论类型，先测存活 ---
        if check_url(test_url):
            print("  ✅ 存活 (直接保留)", flush=True)
            revived_list.append(block + "\n\n")
        else:
            # --- 第二步：如果失效，判断是否具备“复活”资格 ---
            if is_ip_format(base_host):
                print("  💀 失效 -> 识别为 IP 源，尝试即时复活...", flush=True)
                try:
                    # 只有 IP 格式才支持 C 段爆破
                    ip_port = base_host.split(':')
                    ip = ip_port[0]
                    port = ip_port[1] if len(ip_port) > 1 else "80"
                    
                    prefix = '.'.join(ip.split('.')[:-1])
                    path = test_url.split(base_host)[-1]
                    
                    revived_ip_port = None
                    test_tasks = {f"http://{prefix}.{i}:{port}{path}": f"{prefix}.{i}:{port}" for i in range(1, 256)}
                    
                    with ThreadPoolExecutor(max_workers=MAX_THREADS_SCAN) as executor:
                        futures = {executor.submit(check_url, url): t_host for url, t_host in test_tasks.items()}
                        for f in as_completed(futures):
                            if f.result():
                                revived_ip_port = futures[f]
                                break
                    
                    if revived_ip_port:
                        print(f"  ✨ 复活成功: {revived_ip_port}", flush=True)
                        new_block = f"{revived_ip_port},#genre#\n"
                        for ch in lines[1:]:
                            if ',' in ch:
                                name, old_url = ch.split(',', 1)
                                new_block += f"{name},{old_url.replace(base_host, revived_ip_port)}\n"
                        revived_list.append(new_block + "\n\n")
                    else:
                        print("  ❌ 复活失败", flush=True)
                        dead_list.append(block + "\n\n")
                except Exception as e:
                    print(f"  ⚠️ 复活逻辑异常: {e}", flush=True)
                    dead_list.append(block + "\n\n")
            else:
                # 域名源失效，无法爆破，直接标记死亡
                print("  💀 失效 -> 识别为域名源，无法复活", flush=True)
                dead_list.append(block + "\n\n")

    # 保存结果
    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived_list)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead_list)
    
    print(f"\n✅ 任务完成：存活/复活 {len(revived_list)} 组，失效 {len(dead_list)} 组。", flush=True)

if __name__ == "__main__":
    main()
