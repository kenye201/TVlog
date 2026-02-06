import os
import re
import urllib.request
import threading
import time
from queue import Queue
from urllib.parse import urlparse, urlunparse
import sys

# --- 配置 ---
INPUT_FILE = "aggregated_hotel.txt"
OUTPUT_FILE = "revived_hotel.txt"
THREADS_PRECHECK = 50
THREADS_SCAN = 100 
TIMEOUT = 3

class SmartScanner:
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
        self.found_count = 0
        self.to_rescue = []
        self.checked_count = 0

    def check_alive(self, url):
        headers = {"User-Agent": "Mozilla/5.0 VLC/3.0.18"}
        start_time = time.time()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                if response.getcode() in [200, 206]:
                    content = response.read(300).decode('utf-8', errors='ignore')
                    if "#EXTM3U" in content:
                        return True, (time.time() - start_time) * 1000
        except: pass
        return False, 99999

    def scan_worker(self, q):
        while not q.empty():
            try:
                c_seg, port, last_num, templates = q.get_nowait()
            except: break
            
            test_ip = f"{c_seg}.{last_num}"
            p = urlparse(list(templates.values())[0])
            test_url = urlunparse(list(p)[:1] + [f"{test_ip}:{port}"] + list(p)[2:])
            is_ok, ms = self.check_alive(test_url)
            
            if is_ok:
                with self.lock:
                    if test_ip not in self.results:
                        self.found_count += 1
                        self.results[test_ip] = {
                            'ms': ms, 
                            'chans': {n: urlunparse(list(urlparse(u))[:1] + [f"{test_ip}:{port}"] + list(urlparse(u))[2:]) 
                                     for n, u in templates.items()}
                        }
                # 实时弹出发现结果
                sys.stdout.write(f"\n✨ [发现活源] {test_ip}:{port} ({int(ms)}ms)\n")
                sys.stdout.flush()
            q.task_done()

def main():
    scanner = SmartScanner()
    all_segments = []
    if not os.path.exists(INPUT_FILE): return

    # 1. 解析底库
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        current_tpl = {}
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                if current_tpl:
                    p = urlparse(list(current_tpl.values())[0])
                    ip_full = p.netloc.split(':')[0]
                    all_segments.append({'full_ip': ip_full, 'c_seg': ".".join(ip_full.split('.')[:3]), 'port': p.netloc.split(':')[1] if ':' in p.netloc else "80", 'tpl': current_tpl.copy()})
                current_tpl = {}
            elif ',' in line:
                name, url = line.split(',', 1)
                current_tpl[name] = url

    # 2. 阶段 A: 实时预检
    print(f"🚀 开始同步预检 {len(all_segments)} 组源...")
    pre_q = Queue()
    for s in all_segments: pre_q.put(s)

    def pre_worker():
        while not pre_q.empty():
            seg = pre_q.get()
            is_ok, ms = scanner.check_alive(list(seg['tpl'].values())[0])
            with scanner.lock:
                scanner.checked_count += 1
                if is_ok:
                    scanner.results[seg['full_ip']] = {'ms': ms, 'chans': seg['tpl']}
                    scanner.found_count += 1
                else:
                    scanner.to_rescue.append(seg)
            # 实时刷新预检进度
            sys.stdout.write(f"\r   正在预检: {scanner.checked_count}/{len(all_segments)} (已存活: {scanner.found_count})")
            sys.stdout.flush()
            pre_q.task_done()

    for _ in range(THREADS_PRECHECK):
        threading.Thread(target=pre_worker, daemon=True).start()
    pre_q.join()
    print(f"\n✅ 预检结束。")

    # 3. 阶段 B: 实时扫描
    rescued_segments = set()
    for i, seg in enumerate(scanner.to_rescue):
        if seg['c_seg'] in rescued_segments: continue
        
        print(f"\n📡 [{i+1}/{len(scanner.to_rescue)}] 正在爆破 C 段: {seg['c_seg']}.x (端口: {seg['port']})")
        scan_q = Queue()
        for n in range(1, 255):
            if f"{seg['c_seg']}.{n}" == seg['full_ip']: continue
            scan_q.put((seg['c_seg'], seg['port'], n, seg['tpl']))
        
        # 启动扫描线程
        for _ in range(THREADS_SCAN):
            threading.Thread(target=scanner.scan_worker, args=(scan_q,), daemon=True).start()
        
        # 实时监控该段进度
        while not scan_q.empty():
            progress = ((254 - scan_q.qsize()) / 254) * 100
            sys.stdout.write(f"\r   进度: {progress:.1f}% | 累计活源: {scanner.found_count} ")
            sys.stdout.flush()
            time.sleep(0.3)
        
        scan_q.join()
        rescued_segments.add(seg['c_seg'])

    # 4. 保存
    sorted_res = sorted(scanner.results.items(), key=lambda x: x[1]['ms'])
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip, data in sorted_res:
            netloc = urlparse(list(data['chans'].values())[0]).netloc
            f.write(f"{netloc} (延迟:{int(data['ms'])}ms),#genre#\n")
            for name in sorted(data['chans'].keys(), key=lambda x: (not x.startswith("CCTV"), x)):
                f.write(f"{name},{data['chans'][name]}\n")
            f.write("\n")
    print(f"\n💾 所有数据已写回 {OUTPUT_FILE}，任务完成。")

if __name__ == "__main__":
    main()
