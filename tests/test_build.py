"""python -B -m unittest discover -s tests -v"""
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'tools'))
import build  # noqa: E402
import release  # noqa: E402


def tiny_png():
    raw = b'\x00\xff\xff\xff'
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


ROWS = [
    {'id': 183, 'status': 'revised', 'en': 'Paris lies on the Seine.\n\nŌsaka-style macron and Łódź.',
     'zh': '巴黎位于塞纳河畔。\n\n（Царёво）城名保留。', 'sources': ['https://en.wikipedia.org/wiki/Paris']},
    {'id': 1, 'status': 'revised', 'en': 'Stockholm "quoted".', 'zh': '斯德哥尔摩，Göta 河。',
     'sources': ['https://sv.wikipedia.org/wiki/Stockholm']},
]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / 'repo'
        for rel in ('project.json', 'LICENSE', 'CREDITS.md', 'LICENSES', 'assets', 'workshop/player-readme.en.md',
                    'workshop/player-readme.zh-CN.md'):
            src, dst = REPO / rel, self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copyfile)(src, dst)
        cfg = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        thumb = self.root / cfg['thumbnail_file']
        thumb.parent.mkdir(parents=True, exist_ok=True)
        thumb.write_bytes(tiny_png())
        self.write_rows(ROWS)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_rows(self, rows):
        (self.root / 'data').mkdir(exist_ok=True)
        (self.root / 'data' / 'entries.jsonl').write_text(
            ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


class TestFolding(unittest.TestCase):
    def test_english_only_cp1252(self):
        s = build.fold_latin1('Ōsaka, Łódź, ʻOahu, Qaγalγan (Κρήτη)')
        self.assertTrue(build.cp1252_ok(s))
        self.assertIn('Osaka', s)
        self.assertIn('Lódz', s)   # ó 在 Windows-1252 里，保留
        self.assertIn('Qagalgan', s)

    def test_chinese_drops_other_scripts_and_rare_han(self):
        s = build.fold_latin_in_zh('布里亚特语称（Үдэ гол），㮵树，Göta 河，ā 保留')
        self.assertNotIn('Ү', s)
        self.assertNotIn('㮵', s)
        self.assertIn('Gota', s)
        self.assertIn('ā', s)
        self.assertNotIn('（）', s)


class TestBuild(Fixture):
    def test_build_verify_and_zip(self):
        out = self.tmp / 'dist' / 'r'
        r = build.build(self.root, out)
        self.assertEqual(r['provinces'], 2)
        cfg = build.load_config(self.root)
        mod = out / cfg['mod_dir']
        for name in ('descriptor.mod', 'thumbnail.png', 'sources/sources.jsonl', 'LICENSE', 'README.md',
                     f'interface/{cfg["gui_file"]}', 'localisation/eu4lg_l_english.yml'):
            self.assertTrue((mod / name).is_file(), name)
        desc = (mod / 'descriptor.mod').read_text(encoding='utf-8')
        self.assertIn('picture="thumbnail.png"', desc)
        self.assertNotIn('path=', desc)
        self.assertIn('eu4lg_button', (mod / 'interface' / cfg['gui_file']).read_text(encoding='utf-8'))
        build.verify(self.root, out)
        with self.assertRaises(FileExistsError):
            build.build(self.root, out)

    def test_verify_detects_tampering(self):
        out = self.tmp / 'dist' / 'r'
        build.build(self.root, out)
        cfg = build.load_config(self.root)
        p = out / cfg['mod_dir'] / 'localisation' / 'eu4lg_l_english.yml'
        p.write_bytes(p.read_bytes() + b'#')
        with self.assertRaises(ValueError):
            build.verify(self.root, out)

    def test_rejects_bad_rows(self):
        for bad in ({**ROWS[0], 'sources': []}, {**ROWS[0], 'status': 'draft'}, {**ROWS[0], 'en': ' '}):
            self.write_rows([bad])
            with self.assertRaises(ValueError):
                build.load_rows(self.root)
        self.write_rows([ROWS[0], ROWS[0]])
        with self.assertRaises(ValueError):
            build.load_rows(self.root)

    def test_base_gui_hash_checked(self):
        cfg = build.load_config(self.root)
        (self.root / cfg['base_gui']).write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError):
            build.payload(self.root, cfg, build.load_rows(self.root))

    def test_install_replaces_only_own_copy(self):
        out = self.tmp / 'dist' / 'r'
        build.build(self.root, out)
        cfg = build.load_config(self.root)
        mods = self.tmp / 'mod'
        build.install(cfg, out / cfg['mod_dir'], mods)
        build.install(cfg, out / cfg['mod_dir'], mods)
        dev = f'{cfg["mod_dir"]}_dev'
        reg = (mods / f'{dev}.mod').read_text(encoding='utf-8')
        self.assertIn(f'path="mod/{dev}"', reg)
        self.assertIn(f'name="{cfg["name"]} (dev)"', reg)    # 和订阅版同名时游戏不加载订阅版
        self.assertNotIn('remote_file_id', reg)
        self.assertFalse((mods / cfg['mod_dir']).exists())
        (mods / dev / 'descriptor.mod').write_text('name="Someone else"\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            build.install(cfg, out / cfg['mod_dir'], mods)


class TestPageCounts(unittest.TestCase):
    def test_other_mod_lines_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'workshop').mkdir()
            (root / 'workshop' / 'description.en.txt').write_text(
                'All [b]3,272[/b] provinces.\n[*][url=https://steamcommunity.com/sharedfiles/filedetails/?id=1]Other[/url]: 28,316 tiles, 1,700 subscribers.\n',
                encoding='utf-8')
            self.assertEqual(build.page_counts(root, 3272), [])
            self.assertEqual(len(build.page_counts(root, 3000)), 1)


class TestRelease(unittest.TestCase):
    def test_versions_and_changelog(self):
        self.assertEqual(release.parse_version('1.2.3'), (1, 2, 3))
        for bad in ('1.2', 'v1.2.3', '1.2.3-beta'):
            with self.assertRaises(ValueError):
                release.parse_version(bad)
        text = release.set_project_version('{"version": "0.15.0"}', '0.15.0', '1.0.0')
        self.assertEqual(json.loads(text)['version'], '1.0.0')
        cl = release.add_changelog_entry('# Changelog\n\n', '1.0.0', '2026-11-03', ['First.'])
        self.assertIn('## 1.0.0 — 2026-11-03\n\n- First.\n', cl)
        with self.assertRaises(ValueError):
            release.add_changelog_entry(cl, '1.0.0', '2026-11-03', ['Again.'])


if __name__ == '__main__':
    unittest.main()
