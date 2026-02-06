import os
import re
from urllib.parse import urlparse

# --- 配置区 ---
# 扫描 GitHub 仓库检出后的本地路径（GitHub Actions 默认路径为当前目录）
BASE_DIR = "history" 
SAVE_PATH = "aggregated_hotel.txt"

def get_ip_from_url(url):
    """提取 URL 中的 IP:Port"""
    try:
        # 兼容处理带 http 的和不带 http 的
        if not url.startswith("http"):
            url = "http://" + url
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return None

def clean_channel_name(name):
    """频道名标准化，去除杂质并统一 CCTV 格式"""
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s\t]+', '', name)
    # 处理 CCTV-01 -> CCTV-1
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match:
        return f"CCTV-{int(cctv_match.group(1))}"
    return name

def main():
    # 数据结构: { "IP:Port": { "标准化频道名": "原始行内容" } }
    ip_groups = {}

    print(f"开始遍历目录: {BASE_DIR}")

    if not os.path.exists(BASE_DIR):
        print(f"❌ 找不到目录: {BASE_DIR}")
        return

    # 1. 深度遍历 history 文件夹
    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            # 只要是文本类文件都尝试解析
            if file.endswith((".m3u", ".txt", ".list")):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        
                        current_info = ""
                        for line in lines:
                            line = line.strip()
                            if not line or line.startswith("#EXTM3U"): continue
                            
                            # 处理 #EXTINF 格式
                            if line.startswith("#EXTINF"):
                                current_info = line
                            # 处理 URL 行
                            elif line.startswith("http"):
                                url = line
                                # 获取频道名：优先从 EXTINF 提取，没有则从 URL 尾部或上一行提取
                                raw_name = ""
                                if current_info:
                                    raw_name = current_info.split(',')[-1]
                                
                                ip_port = get_ip_from_url(url)
                                if ip_port:
                                    if ip_port not in ip_groups:
                                        ip_groups[ip_port] = {}
                                    
                                    clean_name = clean_channel_name(raw_name)
                                    # 如果该 IP 组内没存过这个频道，则存入
                                    if clean_name not in ip_groups[ip_port]:
                                        ip_groups[ip_port][clean_name] = url
                                
                                current_info = "" # 清空，准备匹配下一个
                except Exception as e:
                    print(f"读取 {file} 出错: {e}")

    # 2. 写入聚合后的文件
    print(f"正在整理数据并写入 {SAVE_PATH}...")
    
    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        # 按 IP 排序，让结果整齐
        sorted_ips = sorted(ip_groups.keys())
        
        for ip in sorted_ips:
            # 写入你要求的分类头格式
            f.write(f"{ip},#genre#\n")
            
            channels = ip_groups[ip]
            # 内部频道排序：CCTV 排在最前，其余按名称排
            sorted_names = sorted(channels.keys(), 
                                 key=lambda x: (not x.startswith("CCTV"), x))
            
            for name in sorted_names:
                f.write(f"{name},{channels[name]}\n")
            
            f.write("\n") # 组与组之间空一行

    print(f"✨ 聚合完成！共处理 {len(sorted_ips)} 个独立 IP 地址组。")

if __name__ == "__main__":
    main()
