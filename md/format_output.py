import re, os

def clean_name(name):
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd|综合|财经|影视)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s\t]+', '', name)
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match: return f"CCTV-{int(cctv_match.group(1))}"
    return name

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def main():
    all_data = {}
    # 汇总直连和抢救的数据
    for f_name in ["revived_temp.txt", "rescued_temp.txt"]:
        if not os.path.exists(f_name): continue
        with open(f_name, 'r', encoding='utf-8') as f:
            blocks = f.read().strip().split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 2: continue
                ip = lines[0].split(',')[0]
                if ip not in all_data: all_data[ip] = {}
                for l in lines[1:]:
                    if ',' in l:
                        name, url = l.split(',', 1)
                        all_data[ip][clean_name(name)] = url

    txt_output = ""
    m3u_output = '#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n'
    
    # 按 IP 排序
    for ip in sorted(all_data.keys()):
        txt_output += f"{ip},#genre#\n"
        # 频道自然排序
        sorted_ch = sorted(all_data[ip].keys(), key=natural_sort_key)
        for name in sorted_ch:
            url = all_data[ip][name]
            txt_output += f"{name},{url}\n"
            m3u_output += f'#EXTINF:-1 tvg-name="{name}" tvg-logo="https://tb.yubo.qzz.io/logo/{name}.png" group-title="{ip}",{name}\n{url}\n'
        txt_output += "\n"

    # 在根目录生成文件
    with open("md/aggregated_hotel.txt", 'w', encoding='utf-8') as f: f.write(txt_output)
    with open("final_hotel.txt", 'w', encoding='utf-8') as f: f.write(txt_output)
    with open("final_hotel.m3u", 'w', encoding='utf-8') as f: f.write(m3u_output)
    print("🎨 洗版完成：final_hotel.txt & final_hotel.m3u 已生成。")

if __name__ == "__main__": main()
