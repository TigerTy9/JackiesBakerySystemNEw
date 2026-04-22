import os

# Config: Add folders or files you want to ignore
EXCLUDE_DIRS = {'.venv', '.env', '.git', '__pycache__', 'node_modules'}
EXCLUDE_FILES = {'collect_code.py', 'full_project_review.txt', 'foodkeeper_data.json'}

def collect_code():
    project_root = os.getcwd()
    output_file = "full_project_review.txt"

    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write("PROJECT STRUCTURE:\n")
        # 1. Generate a quick directory tree for the AI
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            level = root.replace(project_root, '').count(os.sep)
            indent = ' ' * 4 * level
            outfile.write(f"{indent}{os.path.basename(root)}/\n")
            sub_indent = ' ' * 4 * (level + 1)
            for f in files:
                if f not in EXCLUDE_FILES:
                    outfile.write(f"{sub_indent}{f}\n")
        
        outfile.write("\n" + "="*50 + "\nFILE CONTENTS:\n" + "="*50 + "\n")

        # 2. Append the actual contents
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, project_root)
                
                outfile.write(f"\n\nFILE: {relative_path}\n")
                outfile.write("-" * (len(relative_path) + 6) + "\n")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"[Error reading file: {e}]")
                
                outfile.write("\n\n" + "#" * 30 + "\n")

    print(f"✅ Success! Your entire codebase is now in {output_file}")

if __name__ == "__main__":
    collect_code()

