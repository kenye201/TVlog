import os, requests, re, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置区 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 输入源：唯一的补丁库
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

# 输出源
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_DEAD = os.path.join(CURRENT_DIR, "dead_tasks.txt")

TIMEOUT = 3
MAX_THREADS_CHECK = 50  # 基础体检并发
MAX_THREADS_SCAN = 40   # 爆破复活并发

def check_url(url):
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"}) as r:
            return r.status_code == 200
    except:
        return False

def parse_manual_fix():
    """解析 manual_fix.txt，保留用户的手动排序和频道名"""
    if not os.path.exists(MANUAL_FIX):
        return []
    
    with open(MANUAL_FIX, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 按两个换行符分割块
    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    parsed_data = []
    
    for block in blocks:
        lines = block.split('\n')
        header = lines[0] # 例如: 122.114.131.1:80,#genre#
        channels = lines[1:] # 剩下的频道行
        
        ip_port = header.split(',')[0].strip()
        parsed_data.append({
            'header': header,
            'ip_port': ip_port,
            'channels': channels,
            'original_block': block
        })
    return parsed_data

def main():
    tasks = parse_manual_fix()
    if not tasks:
        print("❌ manual_fix.txt 为空或不存在", flush=True)
        return

    print(f"📡 补丁库加载完成，开始对 {len(tasks)} 个网段执行体检+复活程序...", flush=True)
    
    revived_list = []
    dead_list = []
    found_ips = set() # 用于检测期间的去重

    for idx, item in enumerate(tasks):
        base_ip_port = item['ip_port']
        # 拿该组第一个频道测试
        test_url = item['channels'][0].split(',', 1)[1].strip()
        
        print(f"[{idx+1}/{len(tasks)}] ⚖️ 正在体检: {base_ip_port}", flush=True)
        
        if check_url(test_url):
            # --- 情况 A: 直接存活 ---
            print(f"  ✅ [直连存活]", flush=True)
            revived_list.append(item['original_block'] + "\n\n")
            found_ips.add(base_ip_port)
        else:
            # --- 情况 B: 失效，尝试复活 (C段爆破) ---
            print(f"  💀 [已失效] -> 正在尝试 C 段复活...", flush=True)
            ip, port = base_ip_port.split(':')
            prefix = '.'.join(ip.split('.')[:-1])
            path = test_url.split(base_ip_port)[-1]
            
            # 构造探测任务
            test_tasks = {f"http://{prefix}.{i}:{port}{path}": f"{prefix}.{i}:{port}" for i in range(1, 256)}
            revived_ip = None
            
            with ThreadPoolExecutor(max_workers=MAX_THREADS_SCAN) as executor:
                futures = {executor.submit(check_url, url): t_ip for url, t_ip in test_tasks.items()}
                for f in as_completed(futures):
                    target_ip = futures[f]
                    if f.result():
                        revived_ip = target_ip
                        # 发现第一个活的就作为该组的救命稻草（保持 1 组 1 IP 的整洁）
                        break 
            
            if revived_ip:
                print(f"  ✨ [复活成功] -> 新 IP: {revived_ip}", flush=True)
                # 构造复活后的块，保持原来的频道名和顺序
                new_block = f"{revived_ip},#genre#\n"
                for ch in item['channels']:
                    name, old_url = ch.split(',', 1)
                    new_block += f"{name},{old_url.replace(base_ip_port, revived_ip)}\n"
                revived_list.append(new_block + "\n\n")
                found_ips.add(revived_ip)
            else:
                print(f"  ❌ [复活失败] 该网段已彻底离线", flush=True)
                dead_list.append(item['original_block'] + "\n\n")

    # 写入结果
    with open(MID_REVIVED, 'w', encoding='utf-8') as f:
        f.writelines(revived_list)
    with open(MID_DEAD, 'w', encoding='utf-8') as f:
        f.writelines(dead_list)

    print(f"\n📊 维保完成：存活/复活 {len(revived_list)} 个 | 彻底失效 {len(dead_list)} 个", flush=True)

if __name__ == "__main__":
    main()
