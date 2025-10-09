import os

# Folders to exclude
EXCLUDED_DIRS = {'.venv', '__pycache__', '.git', 'tools', 'assets', 'data'}
# Files to exclude
EXCLUDED_FILES = {'.gitignore', '.env'}

# Root folder name
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

structure_file = os.path.join(ROOT_DIR, 'project_structure.txt')
combined_file = os.path.join(ROOT_DIR, 'project_combined_scripts.txt')

def generate_structure(dir_path, prefix=""):
    entries = sorted(os.listdir(dir_path))
    tree_lines = []
    for index, entry in enumerate(entries):
        path = os.path.join(dir_path, entry)
        if entry in EXCLUDED_FILES or entry.startswith('.'):
            continue
        if os.path.isdir(path):
            if entry in EXCLUDED_DIRS:
                continue
            branch = "└── " if index == len(entries) - 1 else "├── "
            tree_lines.append(prefix + branch + entry + "/")
            extension = "    " if index == len(entries) - 1 else "│   "
            tree_lines.extend(generate_structure(path, prefix + extension))
        else:
            branch = "└── " if index == len(entries) - 1 else "├── "
            tree_lines.append(prefix + branch + entry)
    return tree_lines

def write_project_structure():
    lines = [os.path.basename(ROOT_DIR) + "/"]
    lines.extend(generate_structure(ROOT_DIR))
    with open(structure_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"✅ Project structure saved to {structure_file}")

def combine_python_scripts():
    with open(combined_file, 'w', encoding='utf-8') as output:
        for root, dirs, files in os.walk(ROOT_DIR):
            # Skip unwanted folders
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]
            for file in sorted(files):
                if file.endswith('.py') and file not in EXCLUDED_FILES:
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, ROOT_DIR)
                    output.write(f"\n\n# ===== {rel_path} =====\n\n")
                    with open(path, 'r', encoding='utf-8') as f:
                        output.write(f.read())
    print(f"✅ Combined .py scripts saved to {combined_file}")

if __name__ == "__main__":
    write_project_structure()
    combine_python_scripts()
