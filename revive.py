import os
import re
import urllib.request
import threading
import time
from queue import Queue
from urllib.parse import urlparse, urlunparse
import sys

# ================= 配置区 =================
INPUT_FILE = "aggregated_hotel.txt"
OUTPUT_FILE = "revived_hotel.txt"
THREADS_PRECHECK = 50   # 第一阶段：原始IP预检线程
THREADS_SCAN = 80       # 第二阶段：C段复活扫描线程
TIMEOUT = 3             # 探测超时（秒）
# ==========================================

class SmartScanner:
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
        self.found_count = 0
        self.to_rescue = []

    def is_ip(self, netloc):
        """判断地址是否为纯IP格式"""
        ip_part = netloc.split(':')[0]
        return re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_part)

    def check_alive(self, url):
        """核心验证逻辑：状态码200 + M3U头部校验"""
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

    def scan_worker(self, q):
        """第二阶段：C段扫描线程"""
        while not q.empty():
            task = q.get()
            c_seg, port, last_num, templates = task
            test_ip = f"{c_seg}.{last_num}"
            
            probe_name = list(templates.keys())[0]
            new_netloc = f"{test_ip}:{port}"
            
            # 精准URL重建
            p = urlparse(templates[probe_name])
            test_url = urlunparse(list(p)[:1] + [new_netloc] + list(p)[2:])

            is_ok, ms = self.check_alive(test_url)
            if is_ok:
                with self.lock:
                    if test_ip not in self.results:
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
        print(f"❌ 找不到输入文件: {INPUT_FILE}"); return

    # 1. 基因解析与初步过滤
    all_segments = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        current_tpl = {}
        for line in f:
            line = line.strip()
            if not line: continue
            if "#genre#" in line:
                if current_tpl:
                    u = list(current_tpl.values())[0]
                    p = urlparse(u)
                    # 过滤逻辑：必须是IP且Token统一
                    if scanner.is_ip(p.netloc):
                        if len(set(urlparse(x).query for x in current_tpl.values())) == 1:
                            ip_full = p.netloc.split(':')[0]
                            c_seg = ".".join(ip_full.split('.')[:3])
                            port = p.netloc.split(':')[1] if ':' in p.netloc else "80"
                            all_segments.append({'full_ip': ip_full, 'c_seg': c_seg, 'port': port, 'tpl': current_tpl.copy()})
                current_tpl = {}
            elif ',' in line:
                name, url = line.split(',', 1)
                current_tpl[name] = url

    print(f"🚀 总计加载 {len(all_segments)} 组待分析源")

    # --- 阶段 A: 多线程闪电预检 ---
    print("\n⏱️  阶段 A: 正在快速筛选原始 IP 存活状态...")
    def precheck_worker(q):
        while not q.empty():
            seg = q.get()
            probe_url = list(seg['tpl'].values())[0] # 只测第一个链接
            is_ok, ms = scanner.check_alive(probe_url)
            with scanner.lock:
                if is_ok:
                    scanner.found_count += 1
                    scanner.results[seg['full_ip']] = {'ms': ms, 'chans': seg['tpl'].copy()}
                else:
                    scanner.to_rescue.append(seg)
            # 实时进度反馈
            sys.stdout.write(f"\r   已检查: {scanner.found_count + len(scanner.to_rescue)}/{len(all_segments)} ")
            sys.stdout.flush()
            q.task_done()

    pre_q = Queue()
    for s in all_segments: pre_q.put(s)
    
    for _ in range(THREADS_PRECHECK):
        threading.Thread(target=precheck_worker, args=(pre_q,), daemon=True).start()
    pre_q.join()

    print(f"\n✅ 预检完成！存活: {scanner.found_count} 组 | 失效: {len(scanner.to_rescue)} 组")

    # --- 阶段 B: 复活扫描 ---
    if scanner.to_rescue:
        print(f"\n⚡ 阶段 B: 开始对 {len(scanner.to_rescue)} 组失效源执行 C 段复活扫描...")
        for i, seg in enumerate(scanner.to_rescue):
            c_seg, port, tpl = seg['c_seg'], seg['port'], seg['tpl']
            print(f"\n📡 [{i+1}/{len(scanner.to_rescue)}] 扫描段: {c_seg}.0/24 (端口: {port})")
            
            scan_q = Queue()
            for n in range(1, 255):
                if f"{c_seg}.{n}" == seg['full_ip']: continue
                scan_q.put((c_seg, port, n, tpl))

            for _ in range(THREADS_SCAN):
                threading.Thread(target=scanner.scan_worker, args=(scan_q,), daemon=True).start()

            while not scan_q.empty():
                done = 254 - scan_q.qsize()
                sys.stdout.write(f"\r   段进度: {(done/254)*100:.1f}% | 累计复活: {scanner.found_count} ")
                sys.stdout.flush()
                time.sleep(0.4)
            scan_q.join()

    # 3. 排序与结果保存
    print(f"\n\n💾 正在进行优选排序并保存至 {OUTPUT_FILE}...")
    sorted_res = sorted(scanner.results.items(), key=lambda x: x[1]['ms'])
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip, data in sorted_res:
            netloc = urlparse(list(data['chans'].values())[0]).netloc
            f.write(f"{netloc} (延迟:{int(data['ms'])}ms),#genre#\n")
            for name in sorted(data['chans'].keys(), key=lambda x: (not x.startswith("CCTV"), x)):
                f.write(f"{name},{data['chans'][name]}\n")
            f.write("\n")

    print(f"✅ 所有操作已完成！")

if __name__ == "__main__":
    scanner = SmartScanner()
    main()
