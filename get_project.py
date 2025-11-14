import os

OUTPUT_FILE = 'project.txt'
EXCLUDED_DIRS = {'.venv'}
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

with open(OUTPUT_FILE, 'w', encoding='utf-8') as output:
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        # Удаляем исключённые директории из списка для обхода
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for filename in filenames:
            if not "get_project" in filename and (filename.endswith('.py') or filename.endswith('.html') or filename.endswith('.css')):
                file_path = os.path.join(dirpath, filename)
                # Относительный путь от корня, используем его для форматирования
                rel_path = os.path.relpath(file_path, ROOT_DIR)
                dotted_path = rel_path.replace(os.sep, '.')

                output.write(f"{dotted_path}\n")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    output.write(content + "\n\n")
                except Exception as e:
                    output.write(f"# Ошибка при чтении {dotted_path}: {e}\n\n")
