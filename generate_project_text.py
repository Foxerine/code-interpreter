"""此工具用于将项目全部文本化，生成一个包含项目结构树和所有代码文件内容的Markdown文件，方便与AI助手共享项目内容。"""

import os

# --- 配置 ---
# 要扫描的项目根目录，'.' 表示当前目录
ROOT_DIR = '.'

# 输出文件名
OUTPUT_FILE = 'project_text.md'

# 要包含内容的文件扩展名
INCLUDE_EXTENSIONS = ('.py', '.md', '.ps1', '.html', '.yml', '.txt', '.sh', '.conf')

# 要包含内容的确切文件名 (不区分大小写)
INCLUDE_FILENAMES = ('dockerfile',)

# 要忽略的目录
IGNORE_DIRS = {
    '.git',
    '__pycache__',
    '.venv',
    '.venvwsl',
    'env',
    '.vscode',
    'node_modules',
    'dist',
    '.idea',
    'build'
}

# 要忽略的文件
# 脚本自身和输出文件会自动被忽略
IGNORE_FILES = {'.DS_Store'}
# --- 结束配置 ---


def get_language_for_file(filename):
    """根据文件名后缀猜测Markdown代码块的语言标识符"""
    name_lower = filename.lower()
    if name_lower.endswith('.py'):
        return 'python'
    if name_lower.endswith('.md'):
        return 'markdown'
    if name_lower == 'dockerfile':
        return 'dockerfile'
    # 对于其他文件，可以返回空字符串，不指定语言
    return ''

def generate_tree(start_path, ignore_dirs, prefix=''):
    """生成目录树状结构"""
    tree_lines = []
    # os.walk会返回(当前路径, [子目录], [子文件])
    # topdown=True 确保我们可以在遍历前修改子目录列表来排除某些目录
    for root, dirs, files in os.walk(start_path, topdown=True):
        # 过滤掉需要忽略的目录
        # dirs[:] 的切片赋值是必须的，因为它会修改os.walk后续要遍历的列表
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        # 计算当前深度和缩进
        level = root.replace(start_path, '').count(os.sep)
        indent = '│   ' * (level - 1) + '├── ' if level > 0 else ''

        # 避免打印根目录 '.'
        if level > 0:
            tree_lines.append(f"{indent}{os.path.basename(root)}/")

        sub_indent = '│   ' * level + '├── '
        for i, file in enumerate(sorted(files)):
            # 最后一个文件使用不同的连接符
            connector = '└── ' if i == len(files) - 1 and not dirs else '├── '
            tree_lines.append(f"{'│   ' * level}{connector}{file}")

    return "\n".join(tree_lines)


def main():
    """主函数，执行所有操作"""
    # 将脚本自身和输出文件添加到忽略列表
    script_name = os.path.basename(__file__)
    all_ignore_files = IGNORE_FILES.union({script_name, OUTPUT_FILE})

    # 存储所有内容的列表
    all_content = []

    # 1. 生成项目结构树
    print("正在生成项目结构树...")
    # 使用修改后的方法生成更美观的树
    project_tree = generate_tree(ROOT_DIR, IGNORE_DIRS)

    # 2. 遍历文件并读取内容
    print("正在遍历文件并读取内容...")
    paths_to_process = []
    for root, dirs, files in os.walk(ROOT_DIR, topdown=True):
        # 过滤掉需要忽略的目录
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            # 检查文件是否应被忽略
            if file in all_ignore_files:
                continue

            # 检查文件是否是我们想要包含的类型
            file_lower = file.lower()
            if file_lower.endswith(INCLUDE_EXTENSIONS) or file_lower in INCLUDE_FILENAMES:
                paths_to_process.append(os.path.join(root, file))

    # 排序以保证输出顺序一致
    paths_to_process.sort()

    for file_path in paths_to_process:
        relative_path = os.path.relpath(file_path, ROOT_DIR)
        print(f"  - 正在处理: {relative_path}")

        lang = get_language_for_file(relative_path)

        content_header = f"--- \n\n`{relative_path}`\n\n```{lang}"
        all_content.append(content_header)

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_content.append(f.read())
        except Exception as e:
            all_content.append(f"无法读取文件: {e}")

        all_content.append("```\n")

    # 3. 写入到输出文件
    print(f"正在将结果写入到 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 项目文本化总览\n\n")

        f.write("## 项目结构树\n\n")
        f.write("```\n")
        f.write(project_tree)
        f.write("\n```\n\n")

        f.write("## 文件内容\n\n")
        f.write("\n".join(all_content))

    print(f"\n成功！项目内容已全部写入到 '{OUTPUT_FILE}' 文件中。")
    print("现在您可以将该文件的内容复制并粘贴给AI助手。")


if __name__ == '__main__':
    main()
