import hashlib
from pathlib import Path
import os

# --- 配置 ---
HISTORY_FOLDER = Path("history")
# 要保留的文件的类型。merged.* 文件通常需要保留。
FILE_PATTERNS = ["*.m3u", "*.txt"]
# 保留策略: 'earliest' (保留时间戳最早的文件), 'latest' (保留时间戳最新的文件)
RETENTION_POLICY = 'earliest' 
# ---------------

def get_file_hash(file_path):
    """计算文件的 SHA256 哈希值，用于内容比较。"""
    hasher = hashlib.sha256()
    # 以二进制模式分块读取文件，处理大文件
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            hasher.update(chunk)
    return hasher.hexdigest()

def cleanup_duplicate_files():
    print(f"🧹 开始清理 {HISTORY_FOLDER} 文件夹中的重复文件...")
    
    # 结构: { 文件类型: { 内容哈希: [文件路径列表 (按时间戳排序)] } }
    duplicates = {}
    
    for pattern in FILE_PATTERNS:
        # 只处理带时间戳的备份文件，忽略 'merged' 文件
        files_to_check = [f for f in HISTORY_FOLDER.glob(pattern) 
                          if not f.name.startswith("merged.")]
        
        # 按文件名（即时间戳）排序文件，确保保留策略的正确性
        # 文件名如 logo12081157.m3u，sorted() 默认按字母顺序排，时间戳越小越靠前
        files_to_check.sort(key=lambda f: f.name) 
        
        duplicates[pattern] = {}
        
        for file_path in files_to_check:
            try:
                file_hash = get_file_hash(file_path)
                
                if file_hash not in duplicates[pattern]:
                    duplicates[pattern][file_hash] = []
                    
                duplicates[pattern][file_hash].append(file_path)
                
            except Exception as e:
                print(f"警告：无法读取文件 {file_path}: {e}")
    
    total_removed = 0
    
    # 遍历所有文件类型和哈希值
    for pattern, hash_groups in duplicates.items():
        for file_hash, file_list in hash_groups.items():
            
            # 如果列表长度大于 1，则存在重复项
            if len(file_list) > 1:
                
                # 保留的文件索引
                if RETENTION_POLICY == 'latest':
                    # 文件列表已按时间戳从小到大排序，保留最后一个
                    file_to_keep = file_list[-1]
                    files_to_delete = file_list[:-1]
                else: # 'earliest'
                    # 保留第一个
                    file_to_keep = file_list[0]
                    files_to_delete = file_list[1:]
                
                print(f"\n发现 {len(file_list)} 个内容相同的重复文件 ({pattern}, 哈希: {file_hash[:8]}...)")
                print(f"✅ 保留文件: {file_to_keep.name}")
                
                # 删除重复文件
                for f_path in files_to_delete:
                    try:
                        os.remove(f_path)
                        print(f"❌ 删除重复项: {f_path.name}")
                        total_removed += 1
                    except Exception as e:
                        print(f"警告：删除文件 {f_path} 失败: {e}")
                        
    print(f"\n✅ 清理完成！共删除 {total_removed} 个重复的备份文件。")

if __name__ == "__main__":
    if not HISTORY_FOLDER.exists():
        print(f"错误：文件夹 {HISTORY_FOLDER} 不存在，跳过清理。")
    else:
        cleanup_duplicate_files()
