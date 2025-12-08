import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# ---------------- 配置 ----------------
LOCAL_DIR = "./"  # 当前仓库路径
MAX_THREADS = 4           # 并发上传线程数
OVERWRITE_EXISTING = False  # True = 覆盖已存在 KV，False = 跳过
EXCLUDE_FOLDERS = ['img', 'TVlogo_Images', 'md']  # 需要排除的文件夹
VALID_EXTENSIONS = ['.txt', '.md', '.json', '.m3u']  # 允许上传的文件扩展名，包括 .m3u 文件

# ---------------- 函数 ----------------
def kv_key_exists(key):
    url = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('KV_ACCOUNT_ID')}/storage/kv/namespaces/{os.getenv('KV_NAMESPACE_ID')}/values/{key}"
    headers = {"Authorization": f"Bearer {os.getenv('KV_API_TOKEN')}"}
    try:
        res = requests.head(url, headers=headers, timeout=20)
        return res.status_code == 200
    except requests.exceptions.RequestException:
        return False

def safe_put(url, headers, data, retries=5, delay=1):
    for i in range(retries):
        try:
            res = requests.put(url, headers=headers, data=data, timeout=30)
            res.raise_for_status()
            return res
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            print(f"⚠️ 上传失败，重试 {i+1}/{retries}：{e}")
            time.sleep(delay)
    raise Exception(f"❌ 上传失败超过 {retries} 次：{url}")

def upload_to_kv(key, value):
    url = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('KV_ACCOUNT_ID')}/storage/kv/namespaces/{os.getenv('KV_NAMESPACE_ID')}/values/{key}"
    headers = {"Authorization": f"Bearer {os.getenv('KV_API_TOKEN')}"}
    safe_put(url, headers, value)
    print(f"✅ 上传成功: {key}")

def process_file(local_file, key):
    # 排除指定文件夹
    if any(exclude in local_file for exclude in EXCLUDE_FOLDERS):
        print(f"⏭ 跳过文件夹: {local_file}")
        return

    # 只上传允许的文件类型
    if not any(local_file.endswith(ext) for ext in VALID_EXTENSIONS):
        print(f"⏭ 跳过非允许文件: {local_file}")
        return

    if not OVERWRITE_EXISTING and kv_key_exists(key):
        print(f"⏭ 跳过已存在: {key}")
        return

    with open(local_file, "rb") as f:
        content = f.read()
        if len(content) > 24 * 1024 * 1024:
            print(f"⚠️ 文件过大无法上传 KV: {key}")
            return
        timestamp = time.time()
        content_with_timestamp = f"{content.decode(errors='ignore')}\n# Last modified at {timestamp}".encode('utf-8')
        upload_to_kv(key, content_with_timestamp)
        time.sleep(0.1)  # 避免请求过快

def upload_local_dir(local_dir, prefix=""):
    tasks = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        for root, dirs, files in os.walk(local_dir):
            for f in files:
                local_file = os.path.join(root, f)
                key = os.path.join(prefix, os.path.relpath(local_file, local_dir)).replace("\\", "/")
                tasks.append(executor.submit(process_file, local_file, key))
        # 等待所有任务完成
        for t in tasks:
            t.result()

# ---------------- 主程序 ----------------
start = time.time()
print("🚀 开始同步 GitHub 仓库到 Cloudflare KV...")
upload_local_dir(LOCAL_DIR)
print(f"🎉 同步完成！耗时 {time.time() - start:.1f} 秒")
