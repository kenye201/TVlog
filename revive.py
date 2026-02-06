import os
import re
import urllib.request
import threading
import time
from queue import Queue
from urllib.parse import urlparse
import sys

# --- 配置 ---
INPUT_FILE = "aggregated_hotel.txt"
OUTPUT_FILE = "revived_hotel.txt"
THREADS = 100 
TIMEOUT = 2

class ReviveScanner:
    def __init__(self, total_tasks):
        self.results = {}
        self.lock = threading.Lock()
        self.found_count = 0
        self.processed_count = 0
        self.total_tasks = total_tasks
        self.start_time = time.time()

    def update_progress(self):
        """在控制台刷新进度条"""
        with self.lock:
            self.processed_count += 1
            if self.processed_count % 50 == 0 or self.processed_count == self.total_tasks:
                percent = (self.processed_count / self.total_tasks) * 100
                elapsed = time.time() - self.start_time
                speed = self.processed_count / elapsed if elapsed > 0 else 0
                # \r 使光标回到行首，实现原地刷新
                sys.stdout.write(f"\r🚀 进度: [{self.processed_count}/{self.total_tasks}] {percent:.1f}% | 速度: {speed:.1f}次/秒 | 已发现: {self.found_count}个")
                sys.stdout.flush()

    def check_alive(self, url):
        headers = {"User-Agent": "VLC/3.0.11"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                if response.getcode() == 200:
                    content = response.read(200).decode('utf-8', errors='ignore')
                    return "#EXTM3U" in content
        except:
            return False
        return False

    def worker(self, q):
        while not q.empty():
            task = q.get()
            c_seg, port, last_num, templates = task
            test_ip_port = f"{c_seg}.{last_num}:{port}"
            
            first_name = list(templates.keys())[0]
            test_path = templates[first_name]
            test_url = f"http://{test_ip_port}{test_path}"

            if self.check_alive(test_url):
                with self.lock:
                    self.found_count += 1
                    self.results[test_ip_port] = {
                        name: f"http://{test_ip_port}{path}" for name, path in templates.items()
                    }
                # 发现活源时，换行打印，避免被进度条覆盖
                sys.stdout.write(f"\n✨ [发现活源] {test_ip_port} ({first_name})\n")
                sys.stdout.flush()
            
            self.update_progress()
            q.task_done()

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误: 找不到 {INPUT_FILE}")
        return

    print("🔍 步骤 1: 正在解析 IP 段基因...")
    segments = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        current_templates = {}
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                if current_templates:
                    parsed = urlparse(next(iter(current_templates.values())))
                    c_seg = ".".join(parsed.netloc.split(':')[0].split('.')[:3])
                    port = parsed.netloc.split(':')[1] if ':' in parsed.netloc else "80"
                    segments.append((c_seg, port, current_templates.copy()))
                current_templates = {}
            elif ',' in line:
                name, url = line.split(',', 1)
                current_templates[name] = urlparse(url).path

    total_tasks = len(segments) * 254
    print(f"📡 步骤 2: 开始并发扫描 {len(segments)} 个 C 段，共 {total_tasks} 个待测目标...")
    
    scanner = ReviveScanner(total_tasks)
    task_queue = Queue()

    for c_seg, port, templates in segments:
        for i in range(1, 255):
            task_queue.put((c_seg, port, i, templates))

    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=scanner.worker, args=(task_queue,))
        t.daemon = True
        t.start()
        threads.append(t)

    task_queue.join()
    
    print(f"\n\n💾 步骤 3: 扫描结束，正在写入 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip_port in sorted(scanner.results.keys()):
            f.write(f"{ip_port},#genre#\n")
            chans = scanner.results[ip_port]
            for name in sorted(chans.keys(), key=lambda x: (not x.startswith("CCTV"), x)):
                f.write(f"{name},{chans[name]}\n")
            f.write("\n")

    print(f"✅ 完成！本次共扫描 {total_tasks} 个地址，成功复活 {scanner.found_count} 组 IP。")

if __name__ == "__main__":
    main()
