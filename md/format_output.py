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
    all_data = {} # {ip: {name: url}}
    for f_name in ["revived_temp.txt", "rescued_temp.txt"]:
        if not os.path.exists(f_name): continue
        with open(f_name, 'r', encoding='utf-8') as f:
            for block in f.read().strip().split('\n\n'):
                lines = block.strip().split('\n')
                if len(lines) < 2: continue
                ip = lines[0].split(',')[0]
                if ip not in all_data: all_data[ip] = {}
                for l in lines[1:]:
                    if ',' in l:
                        n, u = l.split(',', 1)
                        all_data[ip][clean_name(n)] = u

    txt_out, m3u_out = "", '#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n'
    for ip in sorted(all_data.keys()):
        txt_out += f"{ip},#genre#\n"
        for name in sorted(all_data[ip].keys(), key=natural_sort_key):
            url = all_data[ip][name]
            txt_out += f"{name},{url}\n"
            m3u_out += f'#EXTINF:-1 tvg-name="{name}" tvg-logo="https://tb.yubo.qzz.io/logo/{name}.png" group-title="{ip}",{name}\n{url}\n'
        txt_out += "\n"

    # 写回根目录：同时更新底库和成品
    with open("aggregated_hotel.txt", 'w', encoding='utf-8') as f: f.write(txt_out)
    with open("final_hotel.txt", 'w', encoding='utf-8') as f: f.write(txt_out)
    with open("final_hotel.m3u", 'w', encoding='utf-8') as f: f.write(m3u_out)
    print("🎨 洗版完成，底库与成品已更新。", flush=True)

if __name__ == "__main__": main()
