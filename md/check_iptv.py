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
        # 使用 stream=True 仅读取头部，节省流量和时间
        with requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except:
        return False

def is_valid_hotel_format(first_line):
    """判断是否为标准的 IP:端口 格式"""
    # 检查是否包含冒号，且冒号前是 IP 格式
    if ':' not in first_line:
        return False
    # 简单正则校验：xxx.xxx.xxx.xxx:port
    return bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+', first_line))

def main():
    if not os.path.exists(MANUAL_FIX):
        print("❌ 错误: manual_fix.txt 不存在", flush=True)
        return

    # 读取并按双换行符分割块
    with open(MANUAL_FIX, 'r', encoding='utf-8') as f:
        blocks = [b.strip() for b in f.read().split('\n\n') if b.strip()]
    
    revived_list, dead_list = [], []
    
    print(f"🚀 开始体检，共计 {len(blocks)} 个源块...", flush=True)

    for idx, block in enumerate(blocks):
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        
        # 提取第一行作为 IP:端口 标识
        raw_base = lines[0].split(',')[0].strip()
        
        # --- 健壮性检查 1：跳过非标准格式 ---
        if not is_valid_hotel_format(raw_base):
            print(f"[{idx+1}/{len(blocks)}] ⚠️ 跳过(非酒店源格式): {raw_base}", flush=True)
            revived_list.append(block + "\n\n")
            continue

        # 尝试获取测试 URL（通常是块中的第一个频道地址）
        try:
            test_url = lines[1].split(',', 1)[1].strip()
        except IndexError:
            print(f"[{idx+1}/{len(blocks)}] ❌ 格式错误(缺少地址): {raw_base}", flush=True)
            continue

        base_ip_port = raw_base
        print(f"[{idx+1}/{len(blocks)}] ⚖️ 检查: {base_ip_port}", flush=True)
        
        # 1. 检查当前 IP 是否依然存活
        if check_url(test_url):
            print("  ✅ 存活", flush=True)
            revived_list.append(block + "\n\n")
        else:
            print("  💀 失效 -> 尝试即时复活...", flush=True)
            
            # --- 健壮性检查 2：异常保护防止 split 崩溃 ---
            try:
                ip, port = base_ip_port.split(':')
                prefix = '.'.join(ip.split('.')[:-1])
                # 提取路径后缀
                path_match = re.search(f"{re.escape(base_ip_port)}(.*)", test_url)
                path = path_match.group(1) if path_match else ""
                
                revived_ip = None
                # 构建 C 段 255 个测试任务
                test_tasks = {f"http://{prefix}.{i}:{port}{path}": f"{prefix}.{i}:{port}" for i in range(1, 256)}
                
                # 并发扫描同网段
                with ThreadPoolExecutor(max_workers=MAX_THREADS_SCAN) as executor:
                    futures = {executor.submit(check_url, url): t_ip for url, t_ip in test_tasks.items()}
                    for f in as_completed(futures):
                        if f.result():
                            revived_ip = futures[f]
                            break # 只要找到一个活的就停止本组扫描
                
                if revived_ip:
                    print(f"  ✨ 复活成功: {revived_ip}", flush=True)
                    # 替换块内所有频道的 IP 为新 IP
                    new_block = f"{revived_ip},#genre#\n"
                    for ch in lines[1:]:
                        if ',' in ch:
                            name, old_url = ch.split(',', 1)
                            new_url = old_url.replace(base_ip_port, revived_ip)
                            new_block += f"{name},{new_url}\n"
                    revived_list.append(new_block + "\n\n")
                else:
                    print("  ❌ 复活失败", flush=True)
                    dead_list.append(block + "\n\n")
                    
            except Exception as e:
                print(f"  ⚠️ 扫描逻辑异常: {e}", flush=True)
                # 遇到未知异常时保留原块，避免丢失数据
                revived_list.append(block + "\n\n")

    # 保存结果到中间文件，供后续环节使用
    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived_list)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead_list)
    
    print(f"\n✅ 任务结束：复活/存活 {len(revived_list)} 组，彻底失效 {len(dead_list)} 组。", flush=True)

if __name__ == "__main__":
    main()
