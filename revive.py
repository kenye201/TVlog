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
THREADS = 80
TIMEOUT = 3

class SmartScanner:
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
        self.found_count = 0

    def is_ip(self, netloc):
        ip_part = netloc.split(':')[0]
        return re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_part)

    def check_alive(self, url):
        """核心探测：返回 (是否存活, 延迟ms)"""
        headers = {"User-Agent": "Mozilla/5.0 VLC/3.0.18"}
        start_time = time.time()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                if response.getcode() in [200, 206]:
                    content = response.read(300).decode('utf-8', errors='ignore')
                    if "#EXTM3U" in content:
                        duration = (time.time() - start_time) * 1000
                        return True, duration
        except:
            pass
        return False, 99999

    def worker(self, q):
        while not q.empty():
            task = q.get()
            c_seg, port, last_num, templates = task
            test_ip = f"{c_seg}.{last_num}"
            
            probe_name = list(templates.keys())[0]
            new_netloc = f"{test_ip}:{port}"
            
            p = urlparse(templates[probe_name])
            test_url = urlunparse(list(p)[:1] + [new_netloc] + list(p)[2:])

            is_ok, ms = self.check_alive(test_url)
            if is_ok:
                with self.lock:
                    if test_ip not in self.results: # 防止重复录入
                        self.found_count += 1
                        self.results[test_ip] = {
                            'ms': ms,
                            'chans': {name: urlunparse(list(urlparse(u))[:1] + [new_netloc] + list(urlparse(u))[2:]) 
                                     for name, u in templates.items()}
                        }
                sys.stdout.write(f"\n✨ [发现活源] {test_ip}:{port} ({int(ms)}ms)\n")
                sys.stdout.flush()
            q.task_done()

def main():
    if not os.path.exists(INPUT_FILE):
        print("❌ 错误: 找不到输入文件"); return

    # 阶段 1: 解析基因
    segments = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        current_tpl = {}
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                if current_tpl:
                    u = list(current_tpl.values())[0]
                    p = urlparse(u)
                    if scanner.is_ip(p.netloc):
                        if len(set(urlparse(x).query for x in current_tpl.values())) == 1:
                            ip_full = p.netloc.split(':')[0]
                            c_seg = ".".join(ip_full.split('.')[:3])
                            port = p.netloc.split(':')[1] if ':' in p.netloc else "80"
                            segments.append({'full_ip': ip_full, 'c_seg': c_seg, 'port': port, 'tpl': current_tpl.copy()})
                current_tpl = {}
            elif ',' in line:
                name, url = line.split(',', 1)
                current_tpl[name] = url

    print(f"🚀 准备处理 {len(segments)} 组源...")

    # 阶段 2: 循环处理每一组
    for i, seg in enumerate(segments):
        full_ip = seg['full_ip']
        c_seg = seg['c_seg']
        port = seg['port']
        tpl = seg['tpl']

        print(f"\n🔍 [{i+1}/{len(segments)}] 正在分析段: {c_seg}.x")
        
        # --- 步骤 A: 预检原 IP ---
        probe_name = list(tpl.keys())[0]
        test_url = tpl[probe_name]
        print(f"   📡 预检原IP {full_ip}...", end="")
        is_ok, ms = scanner.check_alive(test_url)
        
        if is_ok:
            print(f" [OK] {int(ms)}ms (跳过段扫描)")
            with scanner.lock:
                scanner.found_count += 1
                scanner.results[full_ip] = {
                    'ms': ms,
                    'chans': tpl.copy()
                }
            continue # 直接跳过，处理下一组
        else:
            print(" [失效] 启动 C 段复活扫描...")

        # --- 步骤 B: 失效后才执行扫描 ---
        q = Queue()
        for n in range(1, 255):
            # 排除掉已经预检过的原 IP，不重复测
            if f"{c_seg}.{n}" == full_ip: continue
            q.put((c_seg, port, n, tpl))

        threads = []
        for _ in range(THREADS):
            t = threading.Thread(target=scanner.worker, args=(q,))
            t.daemon = True
            t.start()
            threads.append(t)

        while not q.empty():
            sys.stdout.write(f"\r   进度: {((254-q.qsize())/254)*100:.1f}% | 累计复活: {scanner.found_count}")
            sys.stdout.flush()
            time.sleep(0.4)
        q.join()

    # 阶段 3: 排序保存
    print(f"\n\n💾 正在优选排序并保存到 {OUTPUT_FILE}...")
    sorted_res = sorted(scanner.results.items(), key=lambda x: x[1]['ms'])
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip, data in sorted_res:
            netloc = urlparse(list(data['chans'].values())[0]).netloc
            f.write(f"{netloc} (延迟:{int(data['ms'])}ms),#genre#\n")
            for name in sorted(data['chans'].keys(), key=lambda x: (not x.startswith("CCTV"), x)):
                f.write(f"{name},{data['chans'][name]}\n")
            f.write("\n")

    print(f"✅ 处理完成！")

if __name__ == "__main__":
    scanner = SmartScanner()
    main()
