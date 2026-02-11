import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MID_REVIVED = os.path.join(CURRENT_DIR, "revived_temp.txt")
MID_RESCUED = os.path.join(CURRENT_DIR, "rescued_temp.txt")
OUTPUT_TXT = os.path.join(PARENT_DIR, "final_hotel.txt")
OUTPUT_M3U = os.path.join(PARENT_DIR, "final_hotel.m3u")

LOGO_BASE_URL = "https://tb.yubo.qzz.io/logo/"
EPG_URL = "https://live.fanmingming.com/e.xml"

def main():
    all_blocks = []
    for path in [MID_REVIVED, MID_RESCUED]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
                    all_blocks.extend(blocks)

    if not all_blocks:
        print("❌ 未发现有效数据。")
        return

    # 生成 TXT
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(all_blocks))

    # 生成 M3U
    m3u_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    for block in all_blocks:
        lines = block.split('\n')
        group_title = lines[0].split(',')[0].strip()
        for line in lines[1:]:
            if ',' in line:
                name, url = line.split(',', 1)
                m3u_lines.append(f'#EXTINF:-1 tvg-id="{name.strip()}" tvg-logo="{LOGO_BASE_URL}{name.strip()}.png" group-title="{group_title}",{name.strip()}')
                m3u_lines.append(url.strip())

    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_lines))
    print(f"🎉 处理完成，网段总数: {len(all_blocks)}")

if __name__ == "__main__":
    main()
