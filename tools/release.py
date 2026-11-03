"""准备一个版本：升版本号、写 CHANGELOG、跑完全部检查并构建。不上传。

python -B tools/release.py 1.0.0 --note "First public release."
python -B tools/release.py 1.0.1 --notes-file notes.txt --install --commit
python -B tools/release.py --dry-run                       # 只检查和构建到 dist/dryrun-<时间>，什么都不改

步骤：版本号必须是比 project.json 新的 x.y.z → 改 project.json、CHANGELOG.md 加一节 → 单元测试 → build.py --check
→ 构建到 dist/release-x.y.z/（目录必须是新的）→ build.py --verify。任何一步失败都把 project.json 和 CHANGELOG.md 改回去。
--install 把构建结果以开发副本「<模组名> (dev)」装进本机游戏的模组目录（逐文件核对哈希）；--commit 提交 project.json、CHANGELOG.md 和 data/。
上传是单独的一步，见 AGENTS.md「发布」。本文件在两个发布工程里相同，差别都在 project.json 和 tools/build.py。
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

VERSION_RE = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+')
CHANGELOG_HEAD = '# Changelog\n\n'


def parse_version(text):
    if not VERSION_RE.fullmatch(text or ''):
        raise ValueError(f'版本号必须是 x.y.z：{text!r}')
    return tuple(int(x) for x in text.split('.'))


def set_project_version(text, old, new):
    out, n = re.subn(r'("version"\s*:\s*")' + re.escape(old) + '"', lambda m: m.group(1) + new + '"', text)
    if n != 1:
        raise ValueError('project.json 里必须正好有一个 version')
    return out


def add_changelog_entry(text, version, date, notes):
    if not text.startswith(CHANGELOG_HEAD):
        raise ValueError("CHANGELOG.md 必须以 '# Changelog' 和一个空行开头")
    if re.search(rf'^## {re.escape(version)}\b', text, re.M):
        raise ValueError(f'CHANGELOG.md 已有 {version}')
    if not notes or not all(n.strip() for n in notes):
        raise ValueError('至少要一条非空的 --note')
    entry = f'## {version} — {date}\n\n' + ''.join(f'- {n.strip()}\n' for n in notes) + '\n'
    return CHANGELOG_HEAD + entry + text[len(CHANGELOG_HEAD):]


def run(*args, capture=False):
    print('+ ' + ' '.join(args), flush=True)
    r = subprocess.run(list(args), cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return r.stdout or ''


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('version', nargs='?')
    ap.add_argument('--note', action='append', default=[], help='CHANGELOG 的一行（英文），可重复')
    ap.add_argument('--notes-file', type=Path, help='每个非空行一条')
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--commit', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if a.notes_file:
        a.note += [ln.strip() for ln in a.notes_file.read_text(encoding='utf-8-sig').splitlines() if ln.strip()]
    pj, cl = ROOT / 'project.json', ROOT / 'CHANGELOG.md'
    pj_text = pj.read_text(encoding='utf-8').replace('\r\n', '\n')
    cl_text = cl.read_text(encoding='utf-8').replace('\r\n', '\n')
    current = json.loads(pj_text)['version']
    if a.dry_run:
        if a.install or a.commit:
            raise SystemExit('--dry-run 不能和 --install、--commit 一起用')
        version, out = current, ROOT / 'dist' / f'dryrun-{datetime.datetime.now():%Y%m%d-%H%M%S}'
    else:
        if parse_version(a.version) <= parse_version(current):
            raise SystemExit(f'{a.version} 不比当前的 {current} 新')
        version, out = a.version, ROOT / 'dist' / f'release-{a.version}'
        if a.commit:
            dirty = [ln[3:] for ln in git('status', '--porcelain').splitlines() if not ln[3:].startswith('data/')]
            if dirty:
                raise SystemExit('data/ 以外有未提交的改动：' + ', '.join(dirty))
        new_cl = add_changelog_entry(cl_text, version, datetime.date.today().isoformat(), a.note)
        new_pj = set_project_version(pj_text, current, version)
    if out.exists():
        raise SystemExit(f'{out} 已存在；构建从不覆盖旧产物')
    if not a.dry_run:
        pj.write_text(new_pj, encoding='utf-8', newline='')
        cl.write_text(new_cl, encoding='utf-8', newline='')
    try:
        py = [sys.executable, '-B']
        run(*py, '-m', 'unittest', 'discover', '-s', 'tests')
        checked = json.loads(run(*py, 'tools/build.py', '--check', capture=True))
        if checked.get('page_count_mismatch'):
            raise SystemExit('工坊文案里的数量和这次构建的条数不一致，先改文案：' + '；'.join(checked['page_count_mismatch']))
        run(*py, 'tools/build.py', '--output', str(out))
        verified = json.loads(run(*py, 'tools/build.py', '--verify', str(out), capture=True))
    except BaseException:
        if not a.dry_run:
            pj.write_text(pj_text, encoding='utf-8', newline='')
            cl.write_text(cl_text, encoding='utf-8', newline='')
            print('已把 project.json 和 CHANGELOG.md 改回去', file=sys.stderr)
        raise
    cfg = build.load_config(ROOT)
    folder = out / build.mod_folder_name(cfg)
    files = [p for p in folder.rglob('*') if p.is_file()]
    summary = {'version': version, 'build': str(out.relative_to(ROOT)), 'files': len(files),
               'bytes': sum(p.stat().st_size for p in files), 'archive_sha256': verified['archive_sha256'],
               'upload_folder': str(folder)}
    if a.install:
        summary['installed'] = str(build.install(cfg, folder))
    if a.commit:
        git('add', 'project.json', 'CHANGELOG.md', 'data')
        git('commit', '-q', '-m', f'Version {version}: {a.note[0].strip().rstrip(".")[:60]}')
        summary['commit'] = git('rev-parse', '--short', 'HEAD').strip()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
