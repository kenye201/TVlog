import re
import os

# --- 路径锁定逻辑 ---
# 获取当前脚本所在目录 (即 md 文件夹)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 根目录 (md 的上一级)
ROOT_DIR = os.path.dirname(CURRENT_DIR)

# 输入文件 (都在 md 文件夹内)
FILE_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
FILE_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")

# 输出文件
# 1. 更新 md 文件夹内的底库 (供下次运行 aggregate.py 使用)
LOCAL_BASE = os.path.join(CURRENT_DIR, "aggregated_hotel.txt")
# 2. 更新根目录的成品
FINAL_TXT = os.path.join(ROOT_DIR, "final_hotel.txt")
FINAL_M3U = os.path.join(ROOT_DIR, "final_hotel.m3u")

def clean_name(name):
    """清洗频道名称，使其规范化"""
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd|综合|财经|影视)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s\t]+', '', name)
    # CCTV 特殊处理：将 CCTV1 改为 CCTV-1
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match:
        return f"CCTV-{int(cctv_match.group(1))}"
    return name

def natural_sort_key(s):
    """自然排序算法，处理数字顺序"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def main():
    all_data = {}  # 格式: { "IP:Port": { "频道名": "URL" } }

    # 1. 加载并汇总所有存活数据
    sources = [
        (FILE_REVIVED, "探测存活"),
        (FILE_RESCUED, "抢救成功")
    ]

    for f_path, label in sources:
        if not os.path.exists(f_path):
            print(f"ℹ️ 未发现 {label} 文件，跳过。", flush=True)
            continue
        
        print(f"📖 正在汇总 {label} 数据...", flush=True)
        with open(f_path, 'r', encoding='utf-8') as f:
            # 按双换行符分割块
            content = f.read().strip()
            if not content:
                continue
            blocks = content.split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 2:
                    continue
                
                # 第一行是 IP,#genre#
                ip = lines[0].split(',')[0].strip()
                if ip not in all_data:
                    all_data[ip] = {}
                
                # 后续行是 频道,URL
                for l in lines[1:]:
                    if ',' in l:
                        raw_name, url = l.split(',', 1)
                        clean_n = clean_name(raw_name.strip())
                        all_data[ip][clean_n] = url.strip()

    if not all_data:
        print("❌ 错误：没有任何存活数据可供汇总！", flush=True)
        return

    # 2. 生成内容字符串
    txt_output = ""
    m3u_output = '#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n'
    
    # 对 IP 进行排序
    for ip in sorted(all_data.keys()):
        txt_output += f"{ip},#genre#\n"
        
        # 对该 IP 下的频道进行自然排序
        sorted_channels = sorted(all_data[ip].keys(), key=natural_sort_key)
        for name in sorted_channels:
            url = all_data[ip][name]
            txt_output += f"{name},{url}\n"
            # 组装 M3U 格式，logo 路径可根据需要修改
            m3u_output += f'#EXTINF:-1 tvg-name="{name}" tvg-logo="https://live.fanmingming.com/tv/{name}.png" group-title="{ip}",{name}\n{url}\n'
        
        txt_output += "\n"

    # 3. 写入各个目标文件
    try:
        # 更新 md 目录下的底库 (最关键的一步，保证你的手动修改和新结果被合并保存)
        with open(LOCAL_BASE, 'w', encoding='utf-8') as f:
            f.write(txt_output)
        
        # 更新根目录的成品
        with open(FINAL_TXT, 'w', encoding='utf-8') as f:
            f.write(txt_output)
            
        with open(FINAL_M3U, 'w', encoding='utf-8') as f:
            f.write(m3u_output)
            
        print(f"🎨 洗版成功！", flush=True)
        print(f"✅ 底库已更新: {LOCAL_BASE}", flush=True)
        print(f"✅ 成品已生成: {FINAL_TXT} & .m3u", flush=True)
        
    except Exception as e:
        print(f"❌ 写入文件失败: {e}", flush=True)

if __name__ == "__main__":
    main()
