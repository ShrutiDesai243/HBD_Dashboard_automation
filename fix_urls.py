import os
import re

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'frontend', 'src'))

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Patterns to replace with /api (or their relative counter-parts)
    # We remove the hardcoded origin completely so it becomes relative.
    new_content = re.sub(r'https?://dashboard\.cityhangaround\.com/api', '/api', content)
    new_content = re.sub(r'https?://dashboard\.cityhangaround\.com', '', new_content)
    new_content = re.sub(r'http://localhost:5000', '', new_content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated: {filepath}')

for root, dirs, files in os.walk(src_dir):
    for file in files:
        if file.endswith(('.js', '.jsx', '.ts', '.tsx')):
            replace_in_file(os.path.join(root, file))

print('Done replacing hardcoded URLs.')
