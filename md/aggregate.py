import os, sys, requests, re, concurrent.futures
from urllib.parse import urlparse

# 配置
INPUT_RAW = "tvbox_output.txt"
LOCAL_BASE = "md/aggregated_hotel.txt"
MID_REVIVED = "revived_temp.txt"
MID_DEAD = "dead_tasks.txt"
TIMEOUT = 3
MAX_WORKERS = 30

def is_valid_ip(ip_str):
    """判断字符串是否为有效的 IP:Port 或 域名:Port 格式"""
    # 匹配 数字.数字.数字.数字:端口 或 域名:端口
    pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+):[0-9]+$'
    return bool(re.match(pattern, ip_str))

def get_ip_port(url):
    try: return urlparse(url).netloc
    except: return None

def main():
    ip_map = {}
    def load_file(path):
        if not os.path.exists(path): return
        print(f"📖 正在加载文件: {path}")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            cur_ip = None
            for line in f:
                line = line.strip()
                if not line: continue
                
                # 关键改进：解析 IP 块头
                if "#genre#" in line:
                    potential_ip = line.split(',')[0].strip()
                    # 只有符合 IP:Port 格式的才作为待测目标，过滤掉“央视频道”等文字分类
                    if is_valid_ip(potential_ip):
                        cur_ip = potential_ip
                        if cur_ip not in ip_map: ip_map[cur_ip] = []
                    else:
                        cur_ip = None # 如果是文字分类，后续频道行直接跳过，防止归类错误
                    continue
                
                # 解析频道 URL 行
                if ',' in line and cur_ip:
                    ip_map[cur_ip].append(line)

    load_file(INPUT_RAW)
    load_file(LOCAL_BASE)

    # 过滤掉没有频道数据的空 IP
    ip_map = {k: v for k, v in ip_map.items() if v}
    
    total_ips = len(ip_map)
    if total_ips == 0:
        print("⚠️ 未发现有效 IP 基因，请检查源文件格式。")
        return

    print(f"📡 共有 {total_ips} 个有效 IP 网段，启动并发探测...")

    revived, dead = [], []
    processed = 0

    def check(ip):
        try:
            # 找到第一个非空的 URL 进行测试
            test_url = ip_map[ip][0].split(',')[1].strip()
            r = requests.get(test_url, timeout=TIMEOUT, stream=True, headers={"User-Agent":"Mozilla/5.0"})
            return ip, r.status_code == 200
        except: return ip, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(check, ip): ip for ip in ip_map}
        for f in concurrent.futures.as_completed(futures):
            processed += 1
            ip, ok = f.result()
            target_data = f"{ip},#genre#\n" + "\n".join(ip_map[ip]) + "\n\n"
            
            if ok:
                revived.append(target_data)
                print(f"[{processed}/{total_ips}] ✅ [存活] {ip}")
            else:
                dead.append(target_data)
                print(f"[{processed}/{total_ips}] 💀 [失效] {ip}")

    with open(MID_REVIVED, 'w', encoding='utf-8') as f: f.writelines(revived)
    with open(MID_DEAD, 'w', encoding='utf-8') as f: f.writelines(dead)
    
    print(f"\n📊 探测总结: 直连存活 {len(revived)} 个，待抢救 {len(dead)} 个。")

if __name__ == "__main__":
    main()
