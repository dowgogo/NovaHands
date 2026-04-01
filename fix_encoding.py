# -*- coding: utf-8 -*-
"""
修复 action_replayer.py 的中文注释编码问题
"""

# 文件路径
source_file = "learning/action_replayer.py"
target_file = "learning/action_replayer_fixed.py"
# 备份原文件
import shutil
backup_file = "learning/action_replayer.py.bak"
shutil.copy(source_file, backup_file)

# 读取文件内容
with open(source_file, "rb") as f:
    lines = f.read().split(b"\n")

# 删除中文注释行
filtered_lines = []
for line in lines:
    try:
        line_str = line.decode("utf-8")
        # 检查是否是中文注释行
        if "# 隐私保护" in line_str:
            continue
        filtered_lines.append(line)
    except:
        filtered_lines.append(line)

# 写入新文件
with open(target_file, "wb") as f:
    for line in filtered_lines:
        f.write(line)

# 替换原文件
os.remove(source_file)
os.rename(target_file, source_file)

print(f"完成：删除了 {len(lines) - len(filtered_lines)} 行中文注释")
print(f"新文件已保存到 {target_file}")