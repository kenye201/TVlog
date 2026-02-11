import os, requests, concurrent.futures, re

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 3
MAX_WORKERS = 40  # 全量检测，并发开大一点

def is_valid_ip(ip_str):
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def main():
    all_ip_map = {} 

    # 1. 强制从大库加载所有 IP，不跳过
    print(f"📖 正在读取汇总源: {MERGED_SOURCE}")
    if not os.path.exists(MERGED_SOURCE):
        print("❌ 错误：找不到源文件")
        return

    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        cur_ip = None
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                ip = line.split(',')[0].strip()
                if is_valid_ip(ip):
                    cur_ip = ip
                    all_ip_map[cur_ip] = []
                else: cur_ip = None
                continue
            if ',' in line and cur_ip:
                all_ip_map[cur_ip].append(line)

    print(f"📡 共有 {len(all_ip_map)} 个网段等待全量体检...")

    # 2. 并发探测存活
    revived_blocks = []
    
    def check(ip):
        try:
            # 抽样该 IP 下的第一个频道
            test_url = all_ip_map[ip][0].split(',')[1].strip()
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"})
            return ip, r.status_code == 200
        except: return ip, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(check, ip): ip for ip in all_ip_map}
        for f in concurrent.futures.as_completed(futures):
            ip, ok = f.result()
            if ok:
                print(f"✅ [存活] {ip}")
                # 重新拼接成标准块格式
                block = f"{ip},#genre#\n" + "\n".join(all_ip_map[ip]) + "\n\n"
                revived_blocks.append(block)
            else:
                # print(f"💀 [失效] {ip}")
                pass

    # 3. 覆盖写入（或追加）到 manual_fix.txt
    # 建议使用 'w' 覆盖写入，因为这是全量体检，保证 manual_fix 里全是活的
    with open(MANUAL_FIX, 'w', encoding='utf-8') as f:
        f.writelines(revived_blocks)
    
    print(f"✨ 任务完成！共发现 {len(revived_blocks)} 个存活网段，已更新至 {MANUAL_FIX}")

if __name__ == "__main__":
    main()
