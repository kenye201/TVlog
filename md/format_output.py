import re, os, requests

# Cloudflare 配置 (请填入你的信息)
CF_INFO = {"id": "ID", "ns": "NS", "tk": "TOKEN", "key": "hotel_list"}

def clean_name(name):
    name = re.sub(r'(高清|标清|普清|超清|超高清|H\.265|4K|HD|SD|hd|sd|综合|财经|影视)', '', name, flags=re.I)
    name = re.sub(r'[\(\)\[\]\-\s\t]+', '', name)
    cctv_match = re.search(r'CCTV[- ]?(\d+)', name, re.I)
    if cctv_match: return f"CCTV-{int(cctv_match.group(1))}"
    return name

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def main():
    # 1. 汇总所有数据
    all_data = {}
    for f_name in ["revived_temp.txt", "rescued_temp.txt"]:
        if not os.path.exists(f_name): continue
        with open(f_name, 'r', encoding='utf-8') as f:
            for block in f.read().split('\n\n'):
                lines = block.strip().split('\n')
                if len(lines) < 2: continue
                ip = lines[0].split(',')[0]
                if ip not in all_data: all_data[ip] = {}
                for l in lines[1:]:
                    name, url = l.split(',', 1)
                    all_data[ip][clean_name(name)] = url

    # 2. 生成 TXT 和 M3U
    txt_output = ""
    m3u_output = '#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n'
    
    for ip in sorted(all_data.keys()):
        txt_output += f"{ip},#genre#\n"
        sorted_ch = sorted(all_data[ip].keys(), key=natural_sort_key)
        for name in sorted_ch:
            url = all_data[ip][name]
            txt_output += f"{name},{url}\n"
            m3u_output += f'#EXTINF:-1 tvg-name="{name}" tvg-logo="https://tb.yubo.qzz.io/logo/{name}.png" group-title="{ip}",{name}\n{url}\n'
        txt_output += "\n"

    # 3. 更新本地底库与成品
    with open("aggregated_hotel.txt", 'w', encoding='utf-8') as f: f.write(txt_output)
    with open("final_hotel.txt", 'w', encoding='utf-8') as f: f.write(txt_output)
    
    # 4. 上传 KV (这里只演示上传 TXT，M3U 建议走 Worker 动态转换)
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_INFO['id']}/storage/kv/namespaces/{CF_INFO['ns']}/values/{CF_INFO['key']}"
    requests.put(url, headers={"Authorization": f"Bearer {CF_INFO['tk']}"}, data=txt_output.encode('utf-8'))
    print("🎨 洗版完成，底库已更新并同步云端。")

if __name__ == "__main__": main()
