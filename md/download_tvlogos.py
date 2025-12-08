import os
import re
import requests
from pathlib import Path

# GitHub 原始内容 URL 模板（不要在这里再加 .md）
MD_BASE_URL = "https://raw.githubusercontent.com/qunhui201/TVlogo/main/md/{}"

# 要下载的 md 文件列表
md_files = [f"{i:02}.md" for i in range(1, 51)]

# 下载图片的根目录
ROOT_DIR = Path("TVlogo_Images")
ROOT_DIR.mkdir(exist_ok=True)

# 重试次数
MAX_RETRIES = 3

# 记录失败下载
failed_downloads = []

def download_image(url, save_path):
    """下载图片，失败重试"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                print(f"下载成功: {save_path}")
                return True
            else:
                print(f"请求状态码 {resp.status_code}，重试 {attempt}/{MAX_RETRIES}")
        except Exception as e:
            print(f"请求异常 {e}，重试 {attempt}/{MAX_RETRIES}")
    print(f"下载失败: {save_path}")
    failed_downloads.append(str(save_path))
    return False

def process_md(md_url):
    """处理单个 md 文件"""
    try:
        resp = requests.get(md_url)
        if resp.status_code != 200:
            print(f"下载 md 文件失败: {md_url}")
            return
        content = resp.text

        # 获取子文件夹标题 【台湾频道一】 -> 台湾频道一
        folder_match = re.search(r"#\s*【(.+?)】", content)
        folder_name = folder_match.group(1) if folder_match else "Unknown"
        folder_path = ROOT_DIR / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        # 匹配 img src 链接和对应频道名
        matches = re.findall(r'\|([^|]+)\|<img\s+src="([^"]+)"', content)
        for title, img_url in matches:
            # 清理 img_url，去掉可能多余的属性
            img_url = img_url.split('"')[0].split()[0]
            ext = os.path.splitext(img_url)[1]
            file_name = f"{title}{ext}"
            save_path = folder_path / file_name
            if not save_path.exists():
                download_image(img_url, save_path)

    except Exception as e:
        print(f"处理 md 文件异常: {md_url} -> {e}")

def main():
    for md_file in md_files:
        md_url = MD_BASE_URL.format(md_file)
        print(f"开始处理: {md_url}")
        process_md(md_url)

    print("\n全部下载完成")
    if failed_downloads:
        print("以下文件下载失败：")
        for f in failed_downloads:
            print(f)

if __name__ == "__main__":
    main()
