"""把 data/entries.jsonl 构建成 EU4 模组，可选装进本机游戏的模组目录。只用标准库，在 Windows 上运行。

python -B tools\\build.py                  # 构建到 dist\\<mod_dir>
python -B tools\\build.py --install        # 构建并装进 Documents\\Paradox Interactive\\Europa Universalis IV\\mod，逐文件核对哈希
python -B tools\\build.py --install --debug   # 提示框底部多一行中文模组检测结果，验收 is_mod_active 用

数据由研究工程导出（研究工程 tools/sync_workshop.sh 在 MacBook 上一步做完导出、拷贝、构建、安装）。
模组名、版本、依赖、按钮位置、底稿 GUI 路径都在 project.json。

省份窗口：不覆盖 interface/provinceview.gui（那个文件谁后加载用谁的，会和 Bigger UI 等界面模组互相顶掉），
而是把原版省份窗口定义连同按钮写进 interface/00_eu4lg_provinceview.gui。游戏遇到同名窗口用先读到的定义，
00_ 排在 provinceview.gui 前面，所以装不装 Bigger UI 按钮都在（2026-11-03 在游戏里验证）。代价是装了 Bigger UI 时，
它给省份窗口加的 20 个键盘快捷键不生效；Bigger UI 和原版的这个文件布局完全相同，只差这些快捷键、一个列表高度和一处编码。
project.json 的 compat 可选，用来另外生成"某界面模组底稿＋按钮"的兼容补丁，目前不用。

EU4 英文界面只能显示 Windows-1252 字符：英文正文里的 ō、ł、ı、ʻ 等在生成时换成最接近的可显示字母，
希腊文、汉字等直接去掉（fold_latin1）。中文正文按中文模组字体实际收录的字符处理（fold_latin_in_zh）：
字体里只有 ASCII、拼音声调字母和几个符号，其他西文字母去掉附加符号，西里尔文、高棉文等去掉。

中英文都写进 l_english：中文按中文模组的编码存（tools/eu4zh.py），游戏里用 is_mod_active 检测中文模组，
启用时显示中文，否则显示英文。l_french / l_german / l_spanish 暂时放英文正文。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import eu4zh  # noqa: E402

MOD_ROOT = Path.home() / 'Documents' / 'Paradox Interactive' / 'Europa Universalis IV' / 'mod'


LATIN_FALLBACK = {'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D', 'ı': 'i', 'ə': 'e', 'Ə': 'E', 'ŋ': 'ng', 'Ŋ': 'Ng',
                  'ʌ': 'u', 'ɬ': 'l', 'ħ': 'h', 'Ħ': 'H', 'ŧ': 't', 'ʻ': "'", 'ʼ': "'", 'ʿ': "'", 'ʾ': "'", 'ˀ': "'",
                  'ʔ': "'", 'ː': '', 'ʷ': 'w', 'ʰ': 'h', 'ß': 'ss'}
GREEK = {'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'e', 'θ': 'th', 'ι': 'i', 'κ': 'k',
         'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't',
         'υ': 'y', 'φ': 'ph', 'χ': 'ch', 'ψ': 'ps', 'ω': 'o', 'ά': 'a', 'έ': 'e', 'ή': 'e', 'ί': 'i', 'ό': 'o',
         'ύ': 'y', 'ώ': 'o'}


def _ok(s, latin1_only):
    """英文界面能显示 Windows-1252（游戏日志证实 š、ž、弯引号、长破折号不报错）；
    中文模组把码位大于 255 的字符都当汉字编码，所以中文正文里的西文字母只能留 Latin-1。"""
    if latin1_only:
        return all(ord(c) <= 0xFF for c in s)
    try:
        s.encode('cp1252')
        return True
    except UnicodeEncodeError:
        return False


def _fold_char(ch, latin1_only=False):
    if _ok(ch, latin1_only):
        return ch
    if ch in LATIN_FALLBACK:
        return LATIN_FALLBACK[ch]
    if ch.lower() in GREEK:
        g = GREEK[ch.lower()]
        return g.capitalize() if ch.isupper() else g
    base = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c))
    return base if _ok(base, latin1_only) else ''


def fold_latin1(s):
    """英文正文：把 EU4 英文界面显示不了的字符换成最接近的 Windows-1252 字符，换不了的去掉。"""
    out = ''.join(_fold_char(c) for c in unicodedata.normalize('NFC', s))
    out = re.sub(r'\(\s*[,;]?\s*\)', '', out)      # 去掉只剩空壳的括号
    out = re.sub(r'[ \t]{2,}', ' ', out)
    return re.sub(r' ([,.;:])', r'\1', out)


# 中文模组（工坊 2976470733）字体收录的西文字符：ASCII 全有；另外只有拼音声调字母和几个符号
# （2026-11-03 查 gfx/fonts/zh-hans-*.fnt，各字号一致）。ñ、ö、ç、ß、大写带符号字母都没有。
ZH_FONT_EXTRA = set('àáèéêìíòóùúüāō¢£¤¥§¨°±·×÷')


def _zh_ok(ch):
    o = ord(ch)
    return o < 0x80 or ch in ZH_FONT_EXTRA or 0x2000 <= o <= 0x206F or o >= 0x2E80


def fold_latin_in_zh(s):
    """中文正文：字体里没有的西文字母换成不带符号的形式（ö→o、ł→l），西里尔文、高棉文、希腊文等整段去掉。"""
    out = []
    for ch in unicodedata.normalize('NFC', s):
        if _zh_ok(ch):
            out.append(ch)
            continue
        if ch in LATIN_FALLBACK:
            out.append(LATIN_FALLBACK[ch])
            continue
        base = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c))
        out.append(base if base and all(_zh_ok(c) for c in base) else '')
    r = ''.join(out)
    r = re.sub(r'[（(]\s*[，,、；;]?\s*[）)]', '', r)   # 去掉只剩空壳的括号
    return re.sub(r'[ \t]{2,}', ' ', r)


def q(s):
    return s.replace('"', "'")


def paras(s):
    return [p.strip() for p in s.replace('\r', '').split('\n\n') if p.strip()]


def loc_text(text, zh):
    enc = (lambda s: eu4zh.encode(fold_latin_in_zh(s))) if zh else fold_latin1
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


def add_button(base_gui, x, y):
    g = Path(base_gui).read_text(encoding='utf-8', errors='surrogateescape')
    anchor = 'name = "province_window"'
    if g.count(anchor) != 1:
        sys.exit(f'{base_gui} 里找不到唯一的 province_window')
    i = g.index('### Core', g.index(anchor)) + len('### Core')
    button = f'''

			# EU4 gazetteer: scripted button in the empty strip right of the terrain picture
			guiButtonType = {{
				name = "eu4lg_button"
				quadTextureSprite = "GFX_eu4lg_button"
				position = {{ x = {x} y = {y} }}
				scripted = yes
			}}
'''
    return g[:i] + button + g[i:]


def descriptor(name, version, supported, depends):
    deps = ''.join(f'\t"{d}"\n' for d in depends)
    return (f'name="{name}"\nversion="{version}"\ntags={{\n\t"Interface"\n}}\n'
            f'supported_version="{supported}"\n' + (f'dependencies={{\n{deps}}}\n' if deps else ''))


def build_compat(cfg, c, out):
    """兼容补丁：只有一份换了底稿的省份窗口文件。"""
    if out.exists():
        shutil.rmtree(out)
    (out / 'interface').mkdir(parents=True)
    (out / 'interface' / 'provinceview.gui').write_text(add_button(c['base_gui'], *cfg['button_pos']),
                                                        encoding='utf-8', errors='surrogateescape', newline='')
    (out / 'descriptor.mod').write_text(descriptor(c['name'], cfg['version'], cfg['supported_version'], c['depends']),
                                        encoding='utf-8', newline='\n')


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
        # 不写 trigger：写了 always = yes，提示框底部会多出一行"✓ 总是"
        'custom_button = {\n\tname = eu4lg_button\n\tpotential = { always = yes }\n'
        '\ttooltip = eu4lg_button_tt\n}\n', encoding='utf-8', newline='\n')

    (out / 'interface' / cfg['gui_file']).write_text(add_button(base_gui, *cfg['button_pos']), encoding='utf-8',
                                                     errors='surrogateescape', newline='')
    shutil.copyfile(ROOT / 'assets' / 'eu4lg_button.dds', out / 'gfx' / 'interface' / 'eu4lg_button.dds')
    (out / 'interface' / 'eu4lg.gfx').write_text(
        'spriteTypes = {\n\tspriteType = {\n\t\tname = "GFX_eu4lg_button"\n'
        '\t\ttexturefile = "gfx//interface//eu4lg_button.dds"\n'
        '\t\teffectFile = "gfx/FX/buttonstate.lua"\n\t\tclicksound = click\n\t}\n}\n', encoding='utf-8', newline='\n')
    (out / 'descriptor.mod').write_text(descriptor(cfg['name'], cfg['version'], cfg['supported_version'], cfg['depends']),
                                        encoding='utf-8', newline='\n')


def digests(d):
    return {str(p.relative_to(d)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob('*')) if p.is_file()}


def game_running():
    if os.name != 'nt':
        return False
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq eu4.exe'], capture_output=True, text=True, errors='replace')
    return 'eu4.exe' in r.stdout.lower()


def install(cfg, out, name=None):
    name = name or cfg['mod_dir']
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
    for c in cfg.get('compat', []):
        cout = out.parent / c['mod_dir']
        build_compat(cfg, c, cout)
        print(f'构建兼容补丁 {c["name"]} 到 {cout}')
        if a.install:
            install(cfg, cout, c['mod_dir'])


if __name__ == '__main__':
    main()
