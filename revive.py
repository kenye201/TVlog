import os
import re
import urllib.request
import threading
from queue import Queue
from urllib.parse import urlparse

# --- 配置 ---
INPUT_FILE = "aggregated_hotel.txt"
OUTPUT_FILE = "revived_hotel.txt"
SCAN_THREADS = 50  # 扫描线程数，群晖建议 30-50，GitHub Actions 可以设 100
TIMEOUT = 3        # 探测超时时间（秒）

def get_base_info(url):
    """提取 IP 段前三位、端口和后缀路径"""
    try:
        parsed = urlparse(url)
        ip_port = parsed.netloc
        path = parsed.path
        
        ip = ip_port.split(':')[0]
        port = ip_port.split(':')[1] if ':' in ip_port else "80"
        
        parts = ip.split('.')
        if len(parts) == 4:
            c_segment = f"{parts[0]}.{parts[1]}.{parts[2]}"
            return c_segment, port, path
    except:
        return None
    return None

class Scanner:
    def __init__(self):
        self.results = {} # { "IP:Port": [channels] }
        self.found_ips = set()
        self.lock = threading.Lock()

    def check_url(self, ip_port, path, channel_name):
        url = f"http://{ip_port}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VLC/3.0.11"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                if response.getcode() == 200:
                    # 关键验证：检查是否为真实的 M3U8 内容
                    content = response.read(200).decode('utf-8', errors='ignore')
                    if "#EXTM3U" in content:
                        return True
        except:
            pass
        return False

    def scan_worker(self, q):
        while not q.empty():
            task = q.get()
            c_seg, port, last_num, path, chan_map = task
            test_ip_port = f"{c_seg}.{last_num}:{port}"
            
            # 为了效率，每个 IP 只测试第一个频道（通常是 CCTV-1）
            test_chan_name = "CCTV-1"
            test_path = chan_map.get("CCTV-1", path)
            
            if self.check_url(test_ip_port, test_path, test_chan_name):
                print(f"  [+] 发现活源: {test_ip_port}")
                with self.lock:
                    self.found_ips.add(test_ip_port)
                    # 复活该 IP 下的所有频道
                    self.results[test_ip_port] = {name: f"http://{test_ip_port}{p}" for name, p in chan_map.items()}
            q.task_done()

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"未找到输入文件: {INPUT_FILE}")
        return

    # 1. 提取基因
    print("正在分析 IP 段基因...")
    segments_to_scan = [] # [(c_seg, port, path, {name: path})]
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        current_ip_group = {}
        current_ip_port = ""
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                current_ip_port = line.split(',')[0]
                current_ip_group = {}
            elif ',' in line:
                name, url = line.split(',', 1)
                parsed = urlparse(url)
                current_ip_group[name] = parsed.path
                # 当记录完一个组，或者遇到下一个组前，提取段信息
                info = get_base_info(url)
                if info:
                    c_seg, port, path = info
                    # 去重：同一个 C 段+端口只扫一遍
                    seg_key = (c_seg, port)
                    if not any(s[0] == c_seg and s[1] == port for s in segments_to_scan):
                        segments_to_scan.append((c_seg, port, path, current_ip_group))

    # 2. 放入队列开始并发扫描
    print(f"开始扫描 {len(segments_to_scan)} 个 C 段 (共计约 {len(segments_to_scan)*254} 次探测)...")
    scanner = Scanner()
    queue = Queue()

    for c_seg, port, path, chan_map in segments_to_scan:
        for i in range(1, 255):
            queue.put((c_seg, port, i, path, chan_map))

    threads = []
    for _ in range(SCAN_THREADS):
        t = threading.Thread(target=scanner.scan_worker, args=(queue,))
        t.daemon = True
        t.start()
        threads.append(t)

    queue.join()

    # 3. 写入文件
    print(f"扫描结束，正在写入 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip_port in sorted(scanner.results.keys()):
            f.write(f"{ip_port},#genre#\n")
            chans = scanner.results[ip_port]
            for name, url in chans.items():
                f.write(f"{name},{url}\n")
            f.write("\n")

    print(f"✨ 复活完成！共找到 {len(scanner.results)} 个可用酒店源。")

if __name__ == "__main__":
    main()
