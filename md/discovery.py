import os, requests, concurrent.futures, re

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
# 源头：汇总了 400 多个 IP 的大冷库
MERGED_SOURCE = os.path.join(PARENT_DIR, "history", "merged.txt")
# 目的地：你手动维护的补丁库 (追加模式)
MANUAL_FIX = os.path.join(CURRENT_DIR, "manual_fix.txt")

TIMEOUT = 3
MAX_WORKERS = 50

def is_valid_ip(ip_str):
    """极致校验：匹配 IP:Port 或 域名:Port"""
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def load_fix_ips():
    """读取补丁库已有的 IP，避免重复挖掘"""
    ips = set()
    if os.path.exists(MANUAL_FIX):
        with open(MANUAL_FIX, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if "#genre#" in line:
                    ips.add(line.split(',')[0].strip())
    return ips

def main():
    existing_ips = load_fix_ips()
    ip_map = {} # 结构: { "IP:Port": [ "频道,URL", ... ] }

    print(f"🔍 正在从大库挖掘新基因: {MERGED_SOURCE}")
    if not os.path.exists(MERGED_SOURCE):
        print("❌ 错误：找不到源文件 history/merged.txt")
        return

    # --- 1. 强力解析逻辑 ---
    with open(MERGED_SOURCE, 'r', encoding='utf-8', errors='ignore') as f:
        active_ip = None
        for line in f:
            line = line.strip()
            if not line: continue
            
            # 兼容多种格式：无论是 IP,#genre# 还是直接带端口的行
            parts = line.split(',')
            potential_ip = parts[0].strip()
            
            if is_valid_ip(potential_ip):
                # 如果这一行是新 IP 标识
                if potential_ip not in existing_ips:
                    active_ip = potential_ip
                    if active_ip not in ip_map:
                        ip_map[active_ip] = []
                else:
                    active_ip = None # 已在补丁库，跳过该段
                continue
            
            # 如果是频道数据行，且当前处于有效 IP 段内
            if "," in line and active_ip:
                ip_map[active_ip].append(line)

    if not ip_map:
        print("✅ 大库中没有发现不在补丁库的新 IP。")
        return

    print(f"📡 发现 {len(ip_map)} 个新网段，准备全量体检...")

    # --- 2. 并发探测存活 ---
    new_revived = []
    
    def check_alive(ip):
        try:
            # 随便找这个 IP 下的一个频道测一下
            test_url = ip_map[ip][0].split(',')[1].strip()
            # 模拟 VLC 播放器请求，绕过简单的防火墙
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"VLC/3.0"})
            return ip, r.status_code == 200
        except:
            return ip, False

    

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = {executor.submit(check_alive, ip): ip for ip in ip_map}
        for f in concurrent.futures.as_completed(results):
            ip, ok = f.result()
            if ok:
                print(f"🌟 [发现活鲜] {ip}")
                # 构建标准追加块
                block = f"{ip},#genre#\n"
                for item in ip_map[ip]:
                    block += f"{item}\n"
                new_revived.append(block + "\n")

    # --- 3. 追加到 manual_fix.txt ---
    if new_revived:
        with open(MANUAL_FIX, 'a', encoding='utf-8') as f:
            f.writelines(new_revived)
        print(f"🚀 搞定！已将 {len(new_revived)} 个新活 IP 追加到 manual_fix.txt 末尾。")
    else:
        print("⛈️ 扫了一圈，400 个 IP 里没发现新的活口。")

if __name__ == "__main__":
    main()
