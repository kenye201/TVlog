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
THREADS = 50  # 降低并发，确保请求质量
TIMEOUT = 4   # 增加超时容忍度

class ReviveScanner:
    def __init__(self, total_tasks):
        self.results = {}
        self.lock = threading.Lock()
        self.found_count = 0
        self.processed_count = 0
        self.total_tasks = total_tasks
        self.start_time = time.time()
        self.error_sample = "" # 记录一个错误样本

    def update_progress(self):
        with self.lock:
            self.processed_count += 1
            if self.processed_count % 10 == 0 or self.processed_count == self.total_tasks:
                percent = (self.processed_count / self.total_tasks) * 100
                elapsed = time.time() - self.start_time
                speed = self.processed_count / elapsed if elapsed > 0 else 0
                sys.stdout.write(f"\r🚀 进度: [{self.processed_count}/{self.total_tasks}] {percent:.1f}% | 发现: {self.found_count} | 样本错误: {self.error_sample}")
                sys.stdout.flush()

    def check_alive(self, url):
        """核心校验：必须包含 #EXTM3U 且返回 200"""
        try:
            # 模拟更像播放器的请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.18",
                "Accept": "*/*",
                "Icy-MetaData": "1"
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                if response.getcode() in [200, 206]:
                    content = response.read(500).decode('utf-8', errors='ignore')
                    if "#EXTM3U" in content:
                        return True
                    else:
                        self.error_sample = "非M3U8内容"
                else:
                    self.error_sample = f"HTTP {response.getcode()}"
        except Exception as e:
            self.error_sample = str(e)[:15] # 记录简短错误
        return False

    def worker(self, q):
        while not q.empty():
            task = q.get()
            # 这里的 template_url 是完整的 URL 模型
            c_seg, port, last_num, templates = task
            test_ip = f"{c_seg}.{last_num}"
            
            # 拿第一个频道做探针
            first_name = list(templates.keys())[0]
            orig_url = templates[first_name]
            
            # --- 关键：精准拼接逻辑 ---
            p = urlparse(orig_url)
            # 替换掉 netloc (IP:Port)，保留 path, params, query, fragment
            new_netloc = f"{test_ip}:{port}"
            new_url_parts = list(p)
            new_url_parts[1] = new_netloc 
            test_url = urlunparse(new_url_parts)

            if self.check_alive(test_url):
                with self.lock:
                    self.found_count += 1
                    # 复活整个 IP 组的所有频道
                    self.results[test_ip] = {}
                    for name, old_url in templates.items():
                        op = urlparse(old_url)
                        ou = list(op)
                        ou[1] = new_netloc
                        self.results[test_ip][name] = urlunparse(ou)
                
                sys.stdout.write(f"\n✨ [探测成功] {test_ip}:{port} -> {first_name}\n")
                sys.stdout.flush()
            
            self.update_progress()
            q.task_done()

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误: 找不到 {INPUT_FILE}")
        return

    print("🔍 步骤 1: 正在精准提取 URL 模板...")
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
                    ip_part = p.netloc.split(':')[0]
                    c_seg = ".".join(ip_part.split('.')[:3])
                    port = p.netloc.split(':')[1] if ':' in p.netloc else "80"
                    segments.append((c_seg, port, current_templates.copy()))
                current_templates = {}
            elif ',' in line:
                name, url = line.split(',', 1)
                current_templates[name] = url
    
    # 处理最后一个组
    if current_templates:
        p = urlparse(next(iter(current_templates.values())))
        ip_part = p.netloc.split(':')[0]
        c_seg = ".".join(ip_part.split('.')[:3])
        port = p.netloc.split(':')[1] if ':' in p.netloc else "80"
        segments.append((c_seg, port, current_templates.copy()))

    total_tasks = len(segments) * 254
    print(f"📡 步骤 2: 开始 C 段复活扫描 (任务总数: {total_tasks})")
    
    scanner = ReviveScanner(total_tasks)
    q = Queue()
    for c_seg, port, templates in segments:
        for i in range(1, 255):
            q.put((c_seg, port, i, templates))

    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=scanner.worker, args=(q,))
        t.daemon = True
        t.start()
        threads.append(t)

    q.join()
    
    print(f"\n\n💾 步骤 3: 正在整理复活后的列表...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip in sorted(scanner.results.keys()):
            # 随便拿一个该 IP 下的端口来显示分类名
            chans = scanner.results[ip]
            first_url = next(iter(chans.values()))
            netloc = urlparse(first_url).netloc
            f.write(f"{netloc},#genre#\n")
            for name in sorted(chans.keys(), key=lambda x: (not x.startswith("CCTV"), x)):
                f.write(f"{name},{chans[name]}\n")
            f.write("\n")

    print(f"✅ 完成！复活了 {scanner.found_count} 组 IP 地址。")

if __name__ == "__main__":
    main()
