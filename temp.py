import os
import re
from pathlib import Path


re_pat = re.compile(r'^(\w*)~(\d+\.\d+\.\d+)')

root = Path('\\\\devops\\depot\\inventories\\EdgePlus_CatB3_Arcade~Live')
for path in os.listdir(root):
    path = root / path

    if path.is_file():
        match = re_pat.match(path.stem)
        if match:
            name, ver = match.groups()
            print(f'| {name.ljust(25)} | {name.ljust(23)} | {ver.ljust(12)} |             |                  |                            |                                 |')
