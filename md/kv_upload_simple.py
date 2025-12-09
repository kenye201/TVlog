# md/kv_upload_simple.py
import os
import requests
import glob
import re

# 从环境变量中获取 Secrets
ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID")
API_TOKEN = os.environ.get("CF_API_TOKEN")

if not all([ACCOUNT_ID, NAMESPACE_ID, API_TOKEN]):
    print("错误：缺少 Cloudflare 环境变量。请检查 Secrets 是否已正确设置。")
    exit(1)

CF_URL_BASE = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}/values"
AUTH_HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

def find_latest_timestamp_key():
    """找到 history/ 目录下最新的带时间戳的备份文件，并提取其时间戳。"""
    
    # 查找所有匹配的文件 (logo 或 tvbox 备份)
    files = glob.glob("history/*_*.m3u") + glob.glob("history/*_*.txt")
    
    # 匹配格式 logo[时间戳].m3u 或 tvbox_[时间戳].txt
    pattern_logo = re.compile(r"history/logo(\d{8})\.m3u$")
    pattern_tvbox = re.compile(r"history/tvbox_(\d{8})\.txt$")
    
    latest_timestamp = None
    
    for f in files:
        timestamp = None
        match_logo = pattern_logo.search(f)
        match_tvbox = pattern_tvbox.search(f)
            
        if match_logo:
            timestamp = match_logo.group(1)
        elif match_tvbox:
            timestamp = match_tvbox.group(1)
            
        if timestamp:
            if latest_timestamp is None or timestamp > latest_timestamp:
                latest_timestamp = timestamp

    return latest_timestamp

def upload_kv_files():
    """执行 KV 上传操作，只上传固定的 6 个文件。"""
    latest_timestamp = find_latest_timestamp_key()
    if not latest_timestamp:
        print("错误：未找到最新的备份文件时间戳。KV 上传中止。")
        return

    print("--- 正在上传 6 个 Key 到 KV 存储 (覆盖固定 Key) ---")
    print(f"使用的最新时间戳：{latest_timestamp}")

    # 定义要上传的文件和对应的 KV Key 名称
    uploads = [
        # 根目录固定文件 (覆盖)
        ("demo_output.m3u", "latest_m3u"),
        ("tvbox_output.txt", "latest_txt"),
        
        # 合并文件 (覆盖)
        ("history/merged.m3u", "history/merged.m3u"),
        ("history/merged.txt", "history/merged.txt"),
        
        # 最新时间戳备份文件 (新 Key)
        (f"history/logo{latest_timestamp}.m3u", f"history/logo_{latest_timestamp}.m3u"),
        (f"history/tvbox_{latest_timestamp}.txt", f"history/tvbox_{latest_timestamp}.txt"),
    ]
    
    
    for local_file, kv_key in uploads:
        if not os.path.exists(local_file):
            print(f"警告：本地文件 {local_file} 不存在，跳过上传。")
            continue
            
        upload_url = f"{CF_URL_BASE}/{kv_key}"
        
        try:
            with open(local_file, 'rb') as f:
                response = requests.put(upload_url, data=f, headers=AUTH_HEADERS)
            
            if response.status_code == 200 and response.json().get("success"):
                print(f"  ✅ 成功上传 Key: {kv_key}")
            else:
                print(f"  ❌ 上传 Key {kv_key} 失败 (HTTP {response.status_code}): {response.text[:100]}...")
                
        except Exception as e:
            print(f"  致命错误：上传 {local_file} 时发生异常: {e}")

    print("Cloudflare KV 文件上传完成。")

if __name__ == "__main__":
    upload_kv_files()
