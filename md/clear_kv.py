import os
import requests
import json
import re
import time
from datetime import datetime

# --- 配置 ---
# 设置要保留的最新备份文件数量 (M3U 和 TXT 各 N 个)
KEYS_TO_KEEP = 5 
# 每次删除操作之间的延迟（秒），用于避免触发 Cloudflare 的速率限制
DELAY_BETWEEN_DELETES = 0.2 
# --- 配置结束 ---

# 从环境变量中获取 Secrets
ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID")
NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID")
API_TOKEN = os.environ.get("CF_API_TOKEN")

if not all([ACCOUNT_ID, NAMESPACE_ID, API_TOKEN]):
    print("错误：缺少 Cloudflare 环境变量。请检查 CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN 是否已设置。")
    exit(1)

AUTH_HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}
BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{NAMESPACE_ID}"


def list_and_filter_keys():
    """
    列出所有带时间戳的 Keys，并按时间戳排序。
    """
    print("-> 正在从 Cloudflare KV 列出所有 Keys...")
    
    # 使用 cursor 实现分页，确保获取所有 keys
    all_keys = []
    cursor = None
    
    while True:
        list_url = f"{BASE_URL}/keys?prefix=history/"
        if cursor:
            list_url += f"&cursor={cursor}"
            
        response = requests.get(list_url, headers=AUTH_HEADERS)
        
        if not response.ok:
            print(f"致命错误：列出 Keys 失败 (HTTP {response.status_code}): {response.text}")
            return []

        data = response.json()
        if not data.get("success"):
            print(f"致命错误：列出 Keys API 错误: {data.get('errors')}")
            return []

        all_keys.extend(data['result'])
        
        # 检查是否还有下一页
        cursor = data['result_info'].get('cursor')
        if not cursor:
            break

    # 正则表达式匹配格式如 history/logo_MMDDHHMM.m3u 或 history/tvbox_MMDDHHMM.txt
    # 捕获时间戳部分 (8位数字)
    pattern = re.compile(r"history/(logo|tvbox)_(\d{8})\.(m3u|txt)$")
    
    timestamp_keys = []
    for key_info in all_keys:
        key_name = key_info['name']
        match = pattern.match(key_name)
        if match:
            # 时间戳格式 MMddHHmm (月日时分)
            timestamp_str = match.group(2)
            try:
                # 尝试将时间戳转换为 datetime 对象，用于精确排序
                # 假设时间戳是从当前年份开始的，但这通常不重要，直接按字符串排序即可
                timestamp_keys.append((timestamp_str, key_name))
            except ValueError:
                print(f"警告：无法解析 Key {key_name} 中的时间戳。跳过。")
            
    # 按照时间戳字符串从旧到新排序
    timestamp_keys.sort(key=lambda x: x[0]) 
    return timestamp_keys


def delete_kv_key(key_name):
    """发送 DELETE 请求删除指定的 KV Key"""
    delete_url = f"{BASE_URL}/values/{key_name}"
    
    response = requests.delete(delete_url, headers=AUTH_HEADERS)
    
    if response.status_code == 200 and response.json().get("success"):
        print(f"  ✅ 成功删除 Key: {key_name}")
        return True
    else:
        print(f"  ❌ 删除 Key {key_name} 失败 (HTTP {response.status_code}): {response.text}")
        return False


def cleanup_kv_keys(keys_to_keep):
    """保留最新的 N 个备份，删除其余的"""
    all_timestamp_keys = list_and_filter_keys()
    
    if not all_timestamp_keys:
        print("未找到任何带时间戳的备份 Key。无需清理。")
        return

    # 由于备份文件是成对出现的 (M3U 和 TXT)，我们需要确保保留的 Key 数量是偶数，
    # 并且只对 "logo" 和 "tvbox" 两组分别进行清理。
    
    logo_keys = [k for k in all_timestamp_keys if 'logo_' in k[1]]
    tvbox_keys = [k for k in all_timestamp_keys if 'tvbox_' in k[1]]
    
    keys_to_delete = []
    
    # 清理 logo M3U 备份
    keys_to_delete.extend(logo_keys[:-keys_to_keep])
    
    # 清理 tvbox TXT 备份
    keys_to_delete.extend(tvbox_keys[:-keys_to_keep])
    
    print(f"总共找到带时间戳的 Key: {len(all_timestamp_keys)} 个")
    print(f"每组将保留最新的 Key: {keys_to_keep} 个")
    print(f"共计将要删除 Key: {len(keys_to_delete)} 个")
    
    if not keys_to_delete:
        print("无需删除，所有备份均在保留数量内。")
        return

    print("--- 开始执行删除操作 ---")
    for timestamp, key_name in keys_to_delete:
        delete_kv_key(key_name)
        # 引入延迟，防止速率限制
        time.sleep(DELAY_BETWEEN_DELETES)

    print("--- KV 清理操作已完成 ---")


if __name__ == "__main__":
    cleanup_kv_keys(KEYS_TO_KEEP)
