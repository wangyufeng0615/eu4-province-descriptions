"""把 data/entries.jsonl 构建成 EU4 模组，可选装进本机游戏的模组目录。只用标准库，在 Windows 上运行。

python -B tools\\build.py                  # 构建到 dist\\<mod_dir>
python -B tools\\build.py --install        # 构建并装进 Documents\\Paradox Interactive\\Europa Universalis IV\\mod，逐文件核对哈希
python -B tools\\build.py --install --debug   # 提示框底部多一行中文模组检测结果，验收 is_mod_active 用

数据由研究工程导出（研究工程 tools/sync_workshop.sh 在 MacBook 上一步做完导出、拷贝、构建、安装）。
模组名、版本、依赖、按钮位置、底稿 GUI 路径都在 project.json。

中英文都写进 l_english：中文按中文模组的编码存（tools/eu4zh.py），游戏里用 is_mod_active 检测中文模组，
启用时显示中文，否则显示英文。l_french / l_german / l_spanish 暂时放英文正文。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import eu4zh  # noqa: E402

MOD_ROOT = Path.home() / 'Documents' / 'Paradox Interactive' / 'Europa Universalis IV' / 'mod'


def q(s):
    return s.replace('"', "'")


def paras(s):
    return [p.strip() for p in s.replace('\r', '').split('\n\n') if p.strip()]


def loc_text(text, zh):
    enc = eu4zh.encode if zh else (lambda s: s)
    return q('\\n\\n'.join(enc(p.replace('\n', ' ')) for p in paras(text)))


def load(cfg):
    rows = []
    with open(ROOT / 'data' / 'entries.jsonl', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            if not r.get('en', '').strip() or not r.get('zh', '').strip():
                sys.exit(f'省份 {r.get("id")} 缺中文或英文正文')
            rows.append(r)
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)):
        sys.exit('data/entries.jsonl 里有重复的省份 id')
    return rows


def build(cfg, rows, out, base_gui, debug):
    if out.exists():
        shutil.rmtree(out)
    for d in ('interface', 'common/custom_gui', 'customizable_localization', 'localisation', 'gfx/interface'):
        (out / d).mkdir(parents=True, exist_ok=True)
    zh = eu4zh.encode
    tt = '§Y[Root.GetEU4LGLabel][Root.GetName]§!\\n\\n[Root.GetEU4LGText]'
    if debug:
        tt += '\\n\\n§G[Root.GetEU4LGDebug]§!'
    loc = [f' eu4lg_button_tt:0 "{tt}"',
           f' eu4lg_label_zh:0 "{q(zh("地方志："))}"',
           ' eu4lg_label_en:0 "Gazetteer: "',
           ' eu4lg_route_zh:0 "[Root.GetEU4LGTextZH]"',
           ' eu4lg_route_en:0 "[Root.GetEU4LGTextEN]"',
           f' eu4lg_text_none_zh:0 "{q(zh("这个省份还没有地方志。"))}"',
           ' eu4lg_text_none_en:0 "No gazetteer entry for this province yet."',
           ' eu4lg_debug_line:0 "[Root.GetEU4LGDebugReal][Root.GetEU4LGDebugFake]"',
           ' eu4lg_debug_yes:0 "[debug] Chinese mod detected: YES"',
           ' eu4lg_debug_no:0 "[debug] Chinese mod detected: NO"',
           ' eu4lg_debug_fake_yes:0 " / fake mod: YES (detection broken)"',
           ' eu4lg_debug_fake_no:0 " / fake mod: NO"']
    for r in rows:
        loc.append(f' eu4lg_text_{r["id"]}_zh:0 "{loc_text(r["zh"], True)}"')
        loc.append(f' eu4lg_text_{r["id"]}_en:0 "{loc_text(r["en"], False)}"')
    for lang in ('english', 'french', 'german', 'spanish'):
        (out / 'localisation' / f'eu4lg_l_{lang}.yml').write_text(f'l_{lang}:\n' + '\n'.join(loc) + '\n',
                                                                encoding='utf-8-sig', newline='\n')

    zh_trigger = 'OR = { ' + ' '.join(f'is_mod_active = "{n}"' for n in cfg['zh_mods']) + ' }'

    def dt(name, branches):
        o = ['defined_text = {', '\tname = ' + name, '\trandom = no']
        for key, trig in branches:
            o += ['\ttext = {', '\t\tlocalisation_key = ' + key, '\t\ttrigger = { %s }' % trig, '\t}']
        return o + ['}']

    cl = dt('GetEU4LGLabel', [('eu4lg_label_zh', zh_trigger), ('eu4lg_label_en', 'always = yes')])
    cl += dt('GetEU4LGText', [('eu4lg_route_zh', zh_trigger), ('eu4lg_route_en', 'always = yes')])
    for lang in ('zh', 'en'):
        cl += dt('GetEU4LGText' + lang.upper(),
                 [(f'eu4lg_text_{r["id"]}_{lang}', f'province_id = {r["id"]}') for r in rows]
                 + [('eu4lg_text_none_' + lang, 'always = yes')])
    cl += dt('GetEU4LGDebug', [('eu4lg_debug_line', 'always = yes')])
    cl += dt('GetEU4LGDebugReal', [('eu4lg_debug_yes', zh_trigger), ('eu4lg_debug_no', 'always = yes')])
    cl += dt('GetEU4LGDebugFake', [('eu4lg_debug_fake_yes', 'is_mod_active = "No Such Mod 4f2a"'),
                                   ('eu4lg_debug_fake_no', 'always = yes')])
    (out / 'customizable_localization' / 'eu4lg.txt').write_text('\n'.join(cl) + '\n', encoding='utf-8', newline='\n')
    (out / 'common' / 'custom_gui' / 'eu4lg.txt').write_text(
        'custom_button = {\n\tname = eu4lg_button\n\tpotential = { always = yes }\n'
        '\ttrigger = { always = yes }\n\ttooltip = eu4lg_button_tt\n}\n', encoding='utf-8', newline='\n')

    g = Path(base_gui).read_text(encoding='utf-8', errors='surrogateescape')
    anchor = 'name = "province_window"'
    if g.count(anchor) != 1:
        sys.exit(f'{base_gui} 里找不到唯一的 province_window')
    i = g.index('### Core', g.index(anchor)) + len('### Core')
    x, y = cfg['button_pos']
    button = f'''

			# EU4 gazetteer: scripted button in the empty strip right of the terrain picture
			guiButtonType = {{
				name = "eu4lg_button"
				quadTextureSprite = "GFX_eu4lg_button"
				position = {{ x = {x} y = {y} }}
				scripted = yes
			}}
'''
    (out / 'interface' / 'provinceview.gui').write_text(g[:i] + button + g[i:], encoding='utf-8',
                                                        errors='surrogateescape', newline='')
    shutil.copyfile(ROOT / 'assets' / 'eu4lg_button.dds', out / 'gfx' / 'interface' / 'eu4lg_button.dds')
    (out / 'interface' / 'eu4lg.gfx').write_text(
        'spriteTypes = {\n\tspriteType = {\n\t\tname = "GFX_eu4lg_button"\n'
        '\t\ttexturefile = "gfx//interface//eu4lg_button.dds"\n'
        '\t\teffectFile = "gfx/FX/buttonstate.lua"\n\t\tclicksound = click\n\t}\n}\n', encoding='utf-8', newline='\n')
    deps = ''.join(f'\t"{d}"\n' for d in cfg['depends'])
    (out / 'descriptor.mod').write_text(
        f'name="{cfg["name"]}"\nversion="{cfg["version"]}"\ntags={{\n\t"Interface"\n}}\n'
        f'supported_version="{cfg["supported_version"]}"\n' + (f'dependencies={{\n{deps}}}\n' if deps else ''),
        encoding='utf-8', newline='\n')


def digests(d):
    return {str(p.relative_to(d)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob('*')) if p.is_file()}


def game_running():
    if os.name != 'nt':
        return False
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq eu4.exe'], capture_output=True, text=True, errors='replace')
    return 'eu4.exe' in r.stdout.lower()


def install(cfg, out):
    name = cfg['mod_dir']
    dst = MOD_ROOT / name
    if game_running():
        print('提示：EU4 正在运行，装好后要完全退出再重开才会生效')
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(out, dst)
    (MOD_ROOT / f'{name}.mod').write_text((out / 'descriptor.mod').read_text(encoding='utf-8')
                                         + f'path="mod/{name}"\n', encoding='utf-8', newline='\n')
    a, b = digests(out), digests(dst)
    if a != b:
        sys.exit(f'安装后哈希不一致：{sorted(set(a.items()) ^ set(b.items()))[:5]}')
    print(f'已装进 {dst}，{len(a)} 个文件哈希一致。完全重启 EU4 后生效。')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, help='构建目录，默认 dist\\<mod_dir>')
    ap.add_argument('--base-gui', type=Path, help='要在其上加按钮的省份窗口文件，默认用 project.json 的 base_gui')
    ap.add_argument('--version', help='覆盖 project.json 的版本号')
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--install', action='store_true')
    a = ap.parse_args()
    cfg = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    if a.version:
        cfg['version'] = a.version
    rows = load(cfg)
    out = a.out or ROOT / 'dist' / cfg['mod_dir']
    build(cfg, rows, out, a.base_gui or cfg['base_gui'], a.debug)
    print(f'构建 {len(rows)} 条地方志到 {out}（版本 {cfg["version"]}{"，调试行" if a.debug else ""}）')
    if a.install:
        install(cfg, out)


if __name__ == '__main__':
    main()
