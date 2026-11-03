"""把 data/entries.jsonl 构建成 EU4 模组。只用标准库（Python 3.10+），不上传。

python -B tools/build.py --check                      # 只检查数据和配置
python -B tools/build.py --output dist/<新目录>        # 构建模组文件夹、ZIP 和构建回执（目录必须是新的）
python -B tools/build.py --verify dist/<目录>          # 按当前源文件重算，核对已构建的文件夹、ZIP 和回执
python -B tools/build.py --install [--debug]          # 开发用：构建到 dist/dev，以「<模组名> (dev)」装进本机 EU4 模组目录
python -B tools/build.py --check --game-root "<EU4 安装目录>"   # 另外核对原版省份窗口有没有随游戏更新变化

数据由研究工程导出（研究工程 tools/sync_workshop.sh 在 MacBook 上一步做完导出、拷贝、构建、安装）。
模组名、版本、按钮位置等在 project.json。

省份窗口：不覆盖 interface/provinceview.gui（那个文件谁后加载用谁的，会和 Bigger UI 等界面模组互相顶掉），
而是把原版省份窗口定义连同按钮写进 interface/00_eu4lg_provinceview.gui。游戏遇到同名窗口用先读到的定义，
00_ 排在 provinceview.gui 前面，所以装不装 Bigger UI 按钮都在（2026-11-03 在游戏里验证）。
原版底稿收在 assets/vanilla/provinceview.gui，哈希记在 project.json；游戏更新后用 --game-root 核对。
未殖民省份不用省份窗口，用 colonisationpanel.gui 里的殖民面板（风景图占满整宽，右边没有空白）。同样的办法写进
interface/00_eu4lg_colonisationpanel.gui，按钮放在风景图里靠右、和关闭按钮上下对齐（project.json 的 colony_gui）。

EU4 英文界面只能显示 Windows-1252 字符：英文正文里的 ō、ł、ı、ʻ 等在生成时换成最接近的可显示字母，
希腊文、汉字等直接去掉（fold_latin1）。中文正文按中文模组字体实际收录的字符处理（fold_latin_in_zh）。

中英文都写进 l_english：中文按中文模组的编码存（tools/eu4zh.py），游戏里用 is_mod_active 检测中文模组，
启用时显示中文，否则显示英文。l_french / l_german / l_spanish 放英文正文。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import eu4zh  # noqa: E402

MOD_ROOT = Path(os.environ.get('USERPROFILE') or Path.home()) / 'Documents' / 'Paradox Interactive' / 'Europa Universalis IV' / 'mod'
LICENSE_FILES = ('LICENSE', 'LICENSES/MIT.txt', 'LICENSES/CC-BY-SA-4.0.txt', 'CREDITS.md')
PLAYER_DOCS = {'README.md': 'workshop/player-readme.en.md', 'README.zh-CN.md': 'workshop/player-readme.zh-CN.md'}
LANGS = ('english', 'french', 'german', 'spanish')
VERSION_RE = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+')


# ───────────────────────────── 字符处理

LATIN_FALLBACK = {'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D', 'ı': 'i', 'ə': 'e', 'Ə': 'E', 'ŋ': 'ng', 'Ŋ': 'Ng',
                  'ʌ': 'u', 'ɬ': 'l', 'ħ': 'h', 'Ħ': 'H', 'ŧ': 't', 'ʻ': "'", 'ʼ': "'", 'ʿ': "'", 'ʾ': "'", 'ˀ': "'",
                  'ʔ': "'", 'ː': '', 'ʷ': 'w', 'ʰ': 'h', 'ß': 'ss'}
GREEK = {'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'e', 'θ': 'th', 'ι': 'i', 'κ': 'k',
         'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't',
         'υ': 'y', 'φ': 'ph', 'χ': 'ch', 'ψ': 'ps', 'ω': 'o', 'ά': 'a', 'έ': 'e', 'ή': 'e', 'ί': 'i', 'ό': 'o',
         'ύ': 'y', 'ώ': 'o'}


def cp1252_ok(s):
    """英文界面能显示 Windows-1252（游戏日志证实 š、ž、弯引号、长破折号不报错）。"""
    try:
        s.encode('cp1252')
        return True
    except UnicodeEncodeError:
        return False


def _fold_char(ch):
    if cp1252_ok(ch):
        return ch
    if ch in LATIN_FALLBACK:
        return LATIN_FALLBACK[ch]
    if ch.lower() in GREEK:
        g = GREEK[ch.lower()]
        return g.capitalize() if ch.isupper() else g
    base = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c))
    return base if cp1252_ok(base) else ''


def fold_latin1(s):
    """英文正文：把 EU4 英文界面显示不了的字符换成最接近的 Windows-1252 字符，换不了的去掉。"""
    out = ''.join(_fold_char(c) for c in unicodedata.normalize('NFC', s))
    out = re.sub(r'\(\s*[,;]?\s*\)', '', out)      # 去掉只剩空壳的括号
    out = re.sub(r'[ \t]{2,}', ' ', out)
    return re.sub(r' ([,.;:])', r'\1', out)


# 中文模组（工坊 2976470733）字体收录的西文字符：ASCII 全有；另外只有拼音声调字母和几个符号
# （2026-11-03 查 gfx/fonts/zh-hans-*.fnt，各字号一致）。ñ、ö、ç、ß、大写带符号字母都没有。
ZH_FONT_EXTRA = set('àáèéêìíòóùúüāō¢£¤¥§¨°±·×÷')


def zh_ok(ch):
    o = ord(ch)
    return o < 0x80 or ch in ZH_FONT_EXTRA or 0x2000 <= o <= 0x206F or 0x2E80 <= o <= 0xFFFF and not 0x3400 <= o <= 0x4DBF


def fold_latin_in_zh(s):
    """中文正文：字体里没有的西文字母换成不带符号的形式（ö→o、ł→l），西里尔文、高棉文、希腊文、生僻字等去掉。"""
    out = []
    for ch in unicodedata.normalize('NFC', s):
        if zh_ok(ch):
            out.append(ch)
            continue
        if ch in LATIN_FALLBACK:
            out.append(LATIN_FALLBACK[ch])
            continue
        base = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c))
        out.append(base if base and all(zh_ok(c) for c in base) else '')
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


def folded_count(rows):
    """统计构建时会改动字符的条目数：(英文条数, 中文条数)。"""
    en = sum(any(not cp1252_ok(c) for c in r['en']) for r in rows)
    zh = sum(any(not zh_ok(c) for c in r['zh']) for r in rows)
    return en, zh


# ───────────────────────────── 配置与数据

def sha256(b):
    return hashlib.sha256(b).hexdigest()


def project_file(root, rel):
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file():
        raise ValueError(f'缺少文件或路径在工程外：{rel}')
    return p


def load_config(root):
    cfg = json.loads((root / 'project.json').read_text(encoding='utf-8'))
    if cfg.get('game_id') != 'eu4' or cfg.get('steam_app_id') != 236850:
        raise ValueError('project.json 的 game_id / steam_app_id 不是 EU4')
    if not re.fullmatch(r'[a-z0-9_]{3,40}', cfg.get('mod_dir', '')):
        raise ValueError('mod_dir 只能用小写字母、数字和下划线')
    if not VERSION_RE.fullmatch(cfg.get('version', '')):
        raise ValueError('version 必须是 x.y.z')
    for k in ('name', 'name_zh'):
        v = cfg.get(k)
        if not isinstance(v, str) or not 3 <= len(v) <= 60 or '"' in v:
            raise ValueError(f'{k} 不合规')
    pid = cfg.get('publishedfileid')
    if pid is not None and (type(pid) is not int or pid <= 0):
        raise ValueError('publishedfileid 要么是 null（还没建工坊条目），要么是正整数')
    if cfg.get('licenses') != {'tools': 'MIT', 'descriptions': 'CC-BY-SA-4.0'}:
        raise ValueError('licenses 和 LICENSE 文件不一致')
    if not cfg.get('zh_mods'):
        raise ValueError('zh_mods 不能为空')
    return cfg


def load_rows(root):
    rows, seen = [], set()
    with open(root / 'data' / 'entries.jsonl', encoding='utf-8') as fh:
        for n, line in enumerate(fh, 1):
            r = json.loads(line)
            pid = r.get('id')
            if type(pid) is not int or pid <= 0 or pid in seen:
                raise ValueError(f'第 {n} 行：省份 id 不是正整数或重复：{pid!r}')
            seen.add(pid)
            if r.get('status') not in ('revised', 'final'):
                raise ValueError(f'省份 {pid} 的 status 不能发布：{r.get("status")}')
            for lang in ('en', 'zh'):
                t = r.get(lang)
                if not isinstance(t, str) or not t.strip() or any(ord(c) < 32 and c not in '\n\r\t' for c in t):
                    raise ValueError(f'省份 {pid} 的 {lang} 正文为空或有控制字符')
            src = r.get('sources')
            if not isinstance(src, list) or not src:
                raise ValueError(f'省份 {pid} 没有资料来源（署名要用）；研究工程重新导出')
            for u in src:
                p = urlsplit(u)
                if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
                    raise ValueError(f'省份 {pid} 的来源网址不合规：{u}')
            rows.append(r)
    return sorted(rows, key=lambda r: r['id'])


def base_gui_text(root, cfg):
    b = project_file(root, cfg['base_gui']).read_bytes()
    if sha256(b) != cfg['base_gui_sha256']:
        raise ValueError(f'{cfg["base_gui"]} 的哈希和 project.json 记的不一致')
    return b.decode('utf-8', errors='surrogateescape')


def colony_gui_text(root, cfg):
    c = cfg['colony_gui']
    b = project_file(root, c['base']).read_bytes()
    if sha256(b) != c['sha256']:
        raise ValueError(f'{c["base"]} 的哈希和 project.json 记的不一致')
    return b.decode('utf-8', errors='surrogateescape')


def check_game(root, cfg, game_root):
    """游戏更新后，原版省份窗口或殖民面板变了就要重新取底稿、重新量按钮位置。"""
    g = Path(game_root) / 'interface' / 'provinceview.gui'
    same = sha256(g.read_bytes()) == cfg['base_gui_sha256']
    gc = Path(game_root) / 'interface' / 'colonisationpanel.gui'
    same_colony = sha256(gc.read_bytes()) == cfg['colony_gui']['sha256']
    ver = None
    ls = Path(game_root) / 'launcher-settings.json'
    if ls.exists():
        ver = json.loads(ls.read_text(encoding='utf-8')).get('rawVersion')
    return {'game_version': ver, 'provinceview_unchanged': same, 'colonisationpanel_unchanged': same_colony,
            'checked_version': cfg.get('game_version_checked')}


# ───────────────────────────── 生成文件

def add_button(g, x, y):
    anchor = 'name = "province_window"'
    if g.count(anchor) != 1:
        raise ValueError('原版底稿里找不到唯一的 province_window')
    i = g.index('### Core', g.index(anchor)) + len('### Core')
    button = f'''

			# Descriptions for Every Province: scripted button in the empty strip right of the terrain picture
			guiButtonType = {{
				name = "eu4lg_button"
				quadTextureSprite = "GFX_eu4lg_button"
				position = {{ x = {x} y = {y} }}
				scripted = yes
			}}
'''
    return g[:i] + button + g[i:]


def add_colony_button(g, x, y):
    anchor = 'name = "colonisationpanel"'
    if g.count(anchor) != 1:
        raise ValueError('殖民面板底稿里找不到唯一的 colonisationpanel')
    start = g.index(anchor)
    m = re.compile(r'guiButtonType = \{\s*name = "close_button".*?\n\t\t\}', re.S).search(g, start)
    if not m:
        raise ValueError('殖民面板底稿里找不到 close_button')
    button = f'''

		# Descriptions for Every Province: uncolonized provinces use this panel; button inside the terrain picture, right side
		guiButtonType = {{
			name = "eu4lg_button"
			quadTextureSprite = "GFX_eu4lg_button"
			position = {{ x = {x} y = {y} }}
			scripted = yes
		}}'''
    return g[:m.end()] + button + g[m.end():]


def descriptor(cfg, local_path=None):
    tags = ''.join(f'\t"{t}"\n' for t in cfg['tags'])
    deps = ''.join(f'\t"{d}"\n' for d in cfg['depends'])
    s = (f'name="{cfg["name"]}"\nversion="{cfg["version"]}"\ntags={{\n{tags}}}\npicture="thumbnail.png"\n'
         f'supported_version="{cfg["supported_version"]}"\n')
    if deps:
        s += f'dependencies={{\n{deps}}}\n'
    if cfg.get('publishedfileid'):
        s += f'remote_file_id="{cfg["publishedfileid"]}"\n'
    if local_path:
        s += f'path="{local_path}"\n'
    return s


def payload(root, cfg, rows, debug=False):
    """模组里每个文件的内容：{相对路径: bytes}。构建和核对都用它，保证两边一致。"""
    files = {}
    zh = eu4zh.encode
    tt = '§Y[Root.GetEU4LGLabel][Root.GetName]§!\\n\\n[Root.GetEU4LGText]'
    if debug:
        tt += '\\n\\n§G[Root.GetEU4LGDebug]§!'
    loc = [f' eu4lg_button_tt:0 "{tt}"',
           f' eu4lg_label_zh:0 "{q(zh("地方志："))}"',
           ' eu4lg_label_en:0 "Gazetteer: "',
           ' eu4lg_route_zh:0 "[Root.GetEU4LGTextZH]"',
           ' eu4lg_route_en:0 "[Root.GetEU4LGTextEN]"',
           f' eu4lg_text_none_zh:0 "{q(zh("这个省份还没有介绍。"))}"',
           ' eu4lg_text_none_en:0 "No description for this province yet."',
           ' eu4lg_debug_line:0 "[Root.GetEU4LGDebugReal][Root.GetEU4LGDebugFake]"',
           ' eu4lg_debug_yes:0 "[debug] Chinese mod detected: YES"',
           ' eu4lg_debug_no:0 "[debug] Chinese mod detected: NO"',
           ' eu4lg_debug_fake_yes:0 " / fake mod: YES (detection broken)"',
           ' eu4lg_debug_fake_no:0 " / fake mod: NO"']
    for r in rows:
        loc.append(f' eu4lg_text_{r["id"]}_zh:0 "{loc_text(r["zh"], True)}"')
        loc.append(f' eu4lg_text_{r["id"]}_en:0 "{loc_text(r["en"], False)}"')
    for lang in LANGS:
        files[f'localisation/eu4lg_l_{lang}.yml'] = (f'l_{lang}:\n' + '\n'.join(loc) + '\n').encode('utf-8-sig')

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
    files['customizable_localization/eu4lg.txt'] = ('\n'.join(cl) + '\n').encode('utf-8')
    # 不写 trigger：写了 always = yes，提示框底部会多出一行"✓ 总是"
    files['common/custom_gui/eu4lg.txt'] = (b'custom_button = {\n\tname = eu4lg_button\n\tpotential = { always = yes }\n'
                                            b'\ttooltip = eu4lg_button_tt\n}\n')
    files[f'interface/{cfg["gui_file"]}'] = add_button(base_gui_text(root, cfg), *cfg['button_pos']).encode(
        'utf-8', errors='surrogateescape')
    c = cfg['colony_gui']
    files[f'interface/{c["file"]}'] = add_colony_button(colony_gui_text(root, cfg), *c['button_pos']).encode(
        'utf-8', errors='surrogateescape')
    files['interface/eu4lg.gfx'] = (b'spriteTypes = {\n\tspriteType = {\n\t\tname = "GFX_eu4lg_button"\n'
                                    b'\t\ttexturefile = "gfx//interface//eu4lg_button.dds"\n'
                                    b'\t\teffectFile = "gfx/FX/buttonstate.lua"\n\t\tclicksound = click\n\t}\n}\n')
    files['gfx/interface/eu4lg_button.dds'] = project_file(root, 'assets/eu4lg_button.dds').read_bytes()
    files['descriptor.mod'] = descriptor(cfg).encode('utf-8')
    files['thumbnail.png'] = project_file(root, cfg['thumbnail_file']).read_bytes()
    for name in LICENSE_FILES:
        files[name] = project_file(root, name).read_bytes()
    for name, src in PLAYER_DOCS.items():
        files[name] = project_file(root, src).read_bytes()
    files['sources/sources.jsonl'] = ''.join(json.dumps({'id': r['id'], 'sources': r['sources']}, ensure_ascii=False)
                                             + '\n' for r in rows).encode('utf-8')
    check_payload(files, rows)
    return files


def check_payload(files, rows):
    """生成结果的硬性检查：英文全部能用 Windows-1252 显示、中文编码可逆、引号和换行没有破坏本地化格式。"""
    en_keys = zh_keys = 0
    # 只按 \n 分行：中文编码后可能含 \x1c、\x85 这类 splitlines 也会当换行的字符
    for line in files['localisation/eu4lg_l_english.yml'].decode('utf-8-sig').rstrip('\n').split('\n')[1:]:
        m = re.fullmatch(r' ([a-z0-9_]+):0 "(.*)"', line, re.S)
        if not m or '"' in m.group(2):
            raise ValueError(f'本地化行格式坏了：{line[:80]}')
        key, val = m.groups()
        if not key.endswith('_zh') and not cp1252_ok(val):   # 中文按中文模组的编码存，另行检查
            raise ValueError(f'{key} 里有英文界面显示不了的字符')
        if re.fullmatch(r'eu4lg_text_\d+_en', key):
            en_keys += 1
        elif re.fullmatch(r'eu4lg_text_\d+_zh', key):
            zh_keys += 1
    if en_keys != len(rows) or zh_keys != len(rows):
        raise ValueError(f'本地化条数不对：英文 {en_keys}、中文 {zh_keys}、数据 {len(rows)}')
    if files['thumbnail.png'][:8] != b'\x89PNG\r\n\x1a\n' or len(files['thumbnail.png']) >= 1_000_000:
        raise ValueError('thumbnail.png 不是 PNG 或超过 1 MB（工坊上限）')


def page_counts(root, n):
    """工坊文案、更新说明和玩家说明里写的数量（如 [b]3,272[/b]、"3,272 个"）要和这次构建的条数一致，不一致的文件列出来。"""
    bad = []
    for rel in ('workshop/description.en.txt', 'workshop/description.zh-CN.txt', 'workshop/changenotes.en.txt',
                'workshop/changenotes.zh-CN.txt', 'workshop/player-readme.en.md', 'workshop/player-readme.zh-CN.md'):
        p = root / rel
        if p.exists():
            # 推荐其他模组的行（带别的工坊条目链接）里是那个模组的数字，不参与核对
            text = '\n'.join(l for l in p.read_text(encoding='utf-8').split('\n') if 'sharedfiles/filedetails/?id=' not in l)
            nums = {int(x.replace(',', '')) for x in re.findall(r'\b\d{1,3}(?:,\d{3})+\b', text)}
            if nums and nums != {n}:
                bad.append(f'{rel}: {sorted(nums)}')
    return bad


# ───────────────────────────── 构建、核对、安装

def write_tree(files, out):
    for name, b in files.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)


def tree_digests(d):
    return {p.relative_to(d).as_posix(): sha256(p.read_bytes()) for p in sorted(d.rglob('*')) if p.is_file()}


def mod_folder_name(cfg):
    return cfg['mod_dir']


def zip_extra(cfg):
    """ZIP 顶层另放一个 <mod_dir>.mod，手动安装时整个解压进 mod 目录就能用。"""
    return {f'{cfg["mod_dir"]}.mod': descriptor(cfg, f'mod/{cfg["mod_dir"]}').encode('utf-8')}


def zip_name(cfg):
    return f'{cfg["mod_dir"]}-{cfg["version"]}.zip'


def build(root, output):
    root, output = root.resolve(), output.resolve()
    cfg, rows = load_config(root), load_rows(root)
    if output.exists():
        raise FileExistsError(f'输出目录已存在，换一个新目录：{output}')
    files = payload(root, cfg, rows)
    mod = output / cfg['mod_dir']
    write_tree(files, mod)
    archive = output / zip_name(cfg)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(f'{cfg["mod_dir"]}/{name}', date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[name], compresslevel=9)
        for name, b in zip_extra(cfg).items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, b, compresslevel=9)
    en, zh = folded_count(rows)
    receipt = {'name': cfg['name'], 'mod_dir': cfg['mod_dir'], 'version': cfg['version'],
               'publishedfileid': cfg.get('publishedfileid'), 'provinces': len(rows),
               'folded_entries': {'en': en, 'zh': zh}, 'licenses': cfg['licenses'],
               'built_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               'files': {k: sha256(v) for k, v in sorted(files.items())},
               'bytes': sum(len(v) for v in files.values()), 'archive_sha256': sha256(archive.read_bytes())}
    (output / 'build_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verify(root, output)
    return receipt


def verify(root, output):
    root, output = root.resolve(), output.resolve()
    cfg, rows = load_config(root), load_rows(root)
    files = payload(root, cfg, rows)
    want = {k: sha256(v) for k, v in sorted(files.items())}
    mod = output / cfg['mod_dir']
    if tree_digests(mod) != want:
        diff = sorted(set(tree_digests(mod).items()) ^ set(want.items()))[:5]
        raise ValueError(f'已构建的文件和当前源文件算出的不一致：{diff}')
    receipt = json.loads((output / 'build_receipt.json').read_text(encoding='utf-8'))
    if receipt['files'] != want or receipt['version'] != cfg['version'] or receipt['provinces'] != len(rows):
        raise ValueError('构建回执和当前源文件不一致')
    archive = output / zip_name(cfg)
    if sha256(archive.read_bytes()) != receipt['archive_sha256']:
        raise ValueError('ZIP 哈希和回执不一致')
    with zipfile.ZipFile(archive) as z:
        extra = zip_extra(cfg)
        if z.testzip() is not None or sorted(z.namelist()) != sorted([f'{cfg["mod_dir"]}/{k}' for k in want] + list(extra)):
            raise ValueError('ZIP 文件清单或校验不对')
        for k, b in extra.items():
            if z.read(k) != b:
                raise ValueError(f'ZIP 里 {k} 不对')
        for k, h in want.items():
            if sha256(z.read(f'{cfg["mod_dir"]}/{k}')) != h:
                raise ValueError(f'ZIP 里 {k} 和回执不一致')
    return receipt


def game_running():
    if os.name != 'nt':
        return False
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq eu4.exe'], capture_output=True, text=True, errors='replace')
    return 'eu4.exe' in r.stdout.lower()


def dev_config(cfg):
    """本机开发安装用另一个名字和目录：和订阅版同名时，游戏不加载订阅版（2026-11-04 实测）。不带工坊编号。"""
    return {**cfg, 'name': f'{cfg["name"]} (dev)', 'mod_dir': f'{cfg["mod_dir"]}_dev', 'publishedfileid': None}


def install(cfg, src, mod_root=MOD_ROOT):
    """装进 EU4 用户模组目录（开发副本，名字带 (dev)）：先写临时目录、核对哈希，再整体替换；只替换本模组自己的旧开发副本。"""
    dev = dev_config(cfg)
    name = dev['mod_dir']
    dst, tmp, old = mod_root / name, mod_root / f'.{name}.new', mod_root / f'.{name}.old'
    if dst.exists() and not (dst / 'descriptor.mod').read_text(encoding='utf-8').startswith(f'name="{dev["name"]}"'):
        raise ValueError(f'{dst} 已存在但不是本模组的开发副本，不替换')
    for p in (tmp, old):
        if p.exists():
            shutil.rmtree(p)
    shutil.copytree(src, tmp)
    (tmp / 'descriptor.mod').write_text(descriptor(dev), encoding='utf-8', newline='\n')
    same = lambda d: {k: v for k, v in tree_digests(d).items() if k != 'descriptor.mod'}
    if same(src) != same(tmp):
        raise RuntimeError('临时目录哈希不一致，没有替换')
    if dst.exists():
        os.replace(dst, old)
    os.replace(tmp, dst)
    shutil.rmtree(old, ignore_errors=True)
    (mod_root / f'{name}.mod').write_text(descriptor(dev, f'mod/{name}'), encoding='utf-8', newline='\n')
    n = len(tree_digests(dst))
    print(f'已装进 {dst}（播放集里叫「{dev["name"]}」，和订阅版不要同时启用），{n} 个文件核对一致。'
          + ('EU4 正在运行，要完全退出再重开才会生效。' if game_running() else '启动 EU4 后在播放集里启用。'))
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='只检查数据和配置')
    mode.add_argument('--verify', type=Path, help='核对已构建的目录')
    mode.add_argument('--install', action='store_true', help='开发用：构建到 dist/dev 并装进本机')
    ap.add_argument('--output', type=Path, help='构建目录（必须是新的）')
    ap.add_argument('--debug', action='store_true', help='和 --install 一起用：提示框底部多一行中文模组检测结果')
    ap.add_argument('--game-root', type=Path, help='EU4 安装目录，和 --check 一起用')
    a = ap.parse_args()
    if a.debug and not a.install:
        ap.error('--debug 只能和 --install 一起用（调试行不进正式构建）')
    if a.check:
        cfg, rows = load_config(ROOT), load_rows(ROOT)
        payload(ROOT, cfg, rows)
        en, zh = folded_count(rows)
        out = {'ok': True, 'version': cfg['version'], 'provinces': len(rows), 'folded_entries': {'en': en, 'zh': zh}}
        out['page_count_mismatch'] = page_counts(ROOT, len(rows))
        if a.game_root:
            out['game'] = check_game(ROOT, cfg, a.game_root)
        print(json.dumps(out, ensure_ascii=False))
    elif a.verify:
        r = verify(ROOT, a.verify)
        print(json.dumps({'verified': True, 'version': r['version'], 'files': len(r['files']),
                          'archive_sha256': r['archive_sha256']}, ensure_ascii=False))
    elif a.install:
        cfg, rows = load_config(ROOT), load_rows(ROOT)
        out = ROOT / 'dist' / 'dev' / cfg['mod_dir']
        if out.exists():
            shutil.rmtree(out)
        write_tree(payload(ROOT, cfg, rows, debug=a.debug), out)
        print(f'构建 {len(rows)} 条到 {out}（版本 {cfg["version"]}{"，带调试行" if a.debug else ""}）')
        install(cfg, out)
    else:
        if not a.output:
            ap.error('正式构建要给 --output dist/<新目录>')
        r = build(ROOT, a.output)
        print(json.dumps({k: r[k] for k in ('version', 'provinces', 'folded_entries', 'bytes', 'archive_sha256')},
                         ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
