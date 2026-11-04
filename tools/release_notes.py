"""GitHub Release 说明：CHANGELOG 里这个版本的条目，加安装步骤和 ZIP 的 SHA-256。

python -B tools/release_notes.py 1.2.0 dist/release-1.2.0/province_descriptions-1.2.0.zip
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSHOP = 'https://steamcommunity.com/sharedfiles/filedetails/?id=3833082096'
ZH_MOD = 'https://steamcommunity.com/sharedfiles/filedetails/?id=2976470733'


def notes(version, zip_path):
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    m = re.search(rf'^## {re.escape(version)}\b[^\n]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not m:
        raise SystemExit(f'CHANGELOG.md 里没有 {version}')
    zip_path = Path(zip_path)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return f'''{m.group(1).strip()}

### Install / 安装

1. Download **{zip_path.name}** below. / 下载下方的 **{zip_path.name}**。
2. Extract it into `Documents\\Paradox Interactive\\Europa Universalis IV\\mod\\`, so that the `province_descriptions` folder and `province_descriptions.mod` sit side by side. / 解压到 `文档\\Paradox Interactive\\Europa Universalis IV\\mod\\`，让 `province_descriptions` 文件夹和 `province_descriptions.mod` 并排。
3. Enable **Descriptions for Every Province** in the launcher. For Chinese text, also enable the [Chinese Language Mod for 1.37]({ZH_MOD}). / 在启动器里启用 **Descriptions for Every Province**；要显示中文，同时启用 [Chinese Language Mod for 1.37]({ZH_MOD})。

Don't enable this copy and the [Steam Workshop]({WORKSHOP}) copy at the same time. / 不要同时启用这份和创意工坊订阅的那份。

SHA-256 `{digest}`
'''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(notes(sys.argv[1], sys.argv[2]))
