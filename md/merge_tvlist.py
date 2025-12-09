import re
from pathlib import Path
from collections import defaultdict

folder = Path("history")
output_m3u = folder / "merged.m3u"
output_txt = folder / "merged.txt"

# M3U 文件头
tvg_header = '#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n'

# 解析 M3U 结构
pattern_m3u = re.compile(r'(#EXTINF[^\n]*\n)(http[^\n]+)', re.MULTILINE)

def extract_m3u(file_path):
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    return pattern_m3u.findall(text)

def extract_txt(file_path):
    """提取 TXT 格式中的频道名和链接"""
    text = file_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    entries = []
    current_group = "其他频道"
    for line in text:
        line = line.strip()
        if not line:
            continue
        if line.startswith("📺"):
            current_group = line.strip().replace("📺", "").replace(",#genre#", "")
        elif "," in line:
            name, url = line.split(",", 1)
            entries.append((current_group, name.strip(), url.strip()))
    return entries

def merge_m3u():
    all_entries = []
    for f in folder.glob("*.m3u"):
        if f.name.startswith("merged."):
            continue
        all_entries.extend(extract_m3u(f))

    seen = set()
    unique = []
    for extinf, url in all_entries:
        if url not in seen:
            seen.add(url)
            unique.append((extinf.strip(), url.strip()))

    # 分类
    cctv, weishi, others = [], [], []
    for extinf, url in unique:
        if "央视频道" in extinf:
            cctv.append((extinf, url))
        elif "卫视频道" in extinf:
            weishi.append((extinf, url))
        else:
            others.append((extinf, url))

    lines = [tvg_header]
    for extinf, url in cctv + weishi + others:
        lines.append(extinf)
        lines.append(url)
    return "\n".join(lines) + "\n"

def merge_txt():
    all_entries = []
    for f in folder.glob("*.txt"):
        if f.name.startswith("merged."):
            continue
        all_entries.extend(extract_txt(f))

    # 去重：按 频道名 + 链接
    seen = set()
    grouped = defaultdict(list)
    for group, name, url in all_entries:
        key = (name, url)
        if key not in seen:
            seen.add(key)
            grouped[group].append((name, url))

    # 分类排序
    ordered_groups = []
    for title in ["央视频道", "卫视频道"]:
        if title in grouped:
            ordered_groups.append((title, grouped.pop(title)))
    ordered_groups += sorted(grouped.items())  # 其他分类按字母排序放最后

    # 输出格式
    lines = []
    for group, channels in ordered_groups:
        lines.append(f"📺{group},#genre#")
        for name, url in channels:
            lines.append(f"{name},{url}")
    return "\n".join(lines) + "\n"

def main():
    print("📺 正在合并 M3U 文件...")
    output_m3u.write_text(merge_m3u(), encoding="utf-8")

    print("📄 正在合并 TXT 文件...")
    output_txt.write_text(merge_txt(), encoding="utf-8")

    print("✅ 合并完成！")
    print(f" - {output_m3u}")
    print(f" - {output_txt}")

if __name__ == "__main__":
    main()
