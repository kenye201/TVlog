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
THREADS = 60  
TIMEOUT = 3

class ReviveScanner:
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
        self.found_count = 0
        self.current_scanning_seg = ""

    def check_alive(self, url):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.18"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                if response.getcode() in [200, 206]:
                    content = response.read(300).decode('utf-8', errors='ignore')
                    return "#EXTM3U" in content
        except:
            pass
        return False

    def worker(self, q):
        while not q.empty():
            task = q.get()
            c_seg, port, last_num, templates = task
            test_ip = f"{c_seg}.{last_num}"
            
            # 拿到探针频道名和完整URL模型
            probe_name = list(templates.keys())[0]
            orig_url = templates[probe_name]
            
            # 精准拼接
            p = urlparse(orig_url)
            new_netloc = f"{test_ip}:{port}"
            new_parts = list(p)
            new_parts[1] = new_netloc
            test_url = urlunparse(new_parts)

            if self.check_alive(test_url):
                with self.lock:
                    self.found_count += 1
                    self.results[test_ip] = {}
                    for name, old_url in templates.items():
                        op = urlparse(old_url)
                        ou = list(op)
                        ou[1] = new_netloc
                        self.results[test_ip][name] = urlunparse(ou)
                
                # 发现成功，高亮显示
                sys.stdout.write(f"\n✅ [成功复活] {test_ip}:{port} | 频道: {probe_name}\n")
                sys.stdout.flush()
            
            q.task_done()

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误: 找不到 {INPUT_FILE}"); return

    # 解析段基因
    segments = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        current_templates = {}
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                if current_templates:
                    first_url = next(iter(current_templates.values()))
                    p = urlparse(first_url)
                    c_seg = ".".join(p.netloc.split(':')[0].split('.')[:3])
                    port = p.netloc.split(':')[1] if ':' in p.netloc else "80"
                    segments.append({'c_seg': c_seg, 'port': port, 'tpl': current_templates.copy()})
                current_templates = {}
            elif ',' in line:
                name, url = line.split(',', 1)
                current_templates[name] = url

    print(f"🚀 开始扫描，共 {len(segments)} 个原始 IP 段待复活...")
    scanner = ReviveScanner()

    # 按组顺序执行扫描，但组内使用多线程并发
    for i, seg in enumerate(segments):
        c_seg = seg['c_seg']
        port = seg['port']
        tpl = seg['tpl']
        
        print(f"\n📡 [{i+1}/{len(segments)}] 正在扫描 C 段: {c_seg}.0/24 (端口: {port})")
        
        # 为当前段建立队列
        q = Queue()
        for last_num in range(1, 255):
            q.put((c_seg, port, last_num, tpl))

        # 启动线程池处理这 254 个 IP
        threads = []
        for _ in range(THREADS):
            t = threading.Thread(target=scanner.worker, args=(q,))
            t.daemon = True
            t.start()
            threads.append(t)

        # 等待这一组扫完再扫下一组，方便前台观察
        while not q.empty():
            # 简单的进度反馈
            remaining = q.qsize()
            done = 254 - remaining
            percent = (done / 254) * 100
            sys.stdout.write(f"\r   进度: {percent:.1f}% | 已发现: {scanner.found_count} ")
            sys.stdout.flush()
            time.sleep(0.5)
        
        q.join() # 确保线程收尾

    # 保存结果
    print(f"\n\n💾 正在保存结果到 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip in sorted(scanner.results.keys()):
            chans = scanner.results[ip]
            netloc = urlparse(next(iter(chans.values()))).netloc
            f.write(f"{netloc},#genre#\n")
            for name in sorted(chans.keys(), key=lambda x: (not x.startswith("CCTV"), x)):
                f.write(f"{name},{chans[name]}\n")
            f.write("\n")

    print(f"✅ 扫描结束！共复活 {scanner.found_count} 个新源。")

if __name__ == "__main__":
    main()
