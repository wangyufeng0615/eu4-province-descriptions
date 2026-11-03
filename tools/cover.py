"""工坊封面：从游戏地图取参考图，交给 Codex 生图模型画成封面，再导出工坊和模组要的尺寸。

python tools/cover.py reference --game-root "<EU4 安装目录>"   # Windows：画 workshop/assets/map-reference.png（真实省份轮廓，四色）
python tools/cover.py derive                                   # 从 cover-master.en.png / cover-master.zh-CN.png 导出
                                                               # cover.jpg、cover.zh-CN.jpg（1254，JPEG 90）和 thumbnail.png（512）

要 Pillow（uv run --with pillow python tools/cover.py derive）。母版由 Codex 生图模型按参考图画成，提示词在 workshop/assets/cover-prompt.*.txt。
参考图只取轮廓和邻接关系，不含游戏美术；封面是宣传图，不是游戏截图。
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'workshop' / 'assets'
PALETTE = [(230, 112, 90), (236, 178, 64), (96, 168, 135), (98, 152, 202)]   # 红、黄、绿、蓝，和 EU5 地块封面一致
INK = (17, 17, 17)
REGIONS = ('british_isles_region',)
SCALE = 3


def region_provinces(game, regions):
    reg = (game / 'map' / 'region.txt').read_text(encoding='latin-1')
    area = (game / 'map' / 'area.txt').read_text(encoding='latin-1')
    ids = set()
    for r in regions:
        m = re.search(r'\n' + r + r'\s*=\s*\{\s*areas\s*=\s*\{([^}]*)\}', reg)
        for a in re.findall(r'\w+', re.sub(r'#.*', '', m.group(1))):
            mm = re.search(r'\n' + a + r'\s*=\s*\{([^}]*)\}', area)
            ids |= {int(x) for x in re.findall(r'\d+', re.sub(r'#.*', '', mm.group(1)))}
    return ids


def reference(game):
    keep = region_provinces(game, REGIONS)
    color_id = {}
    for line in (game / 'map' / 'definition.csv').read_text(encoding='latin-1').splitlines()[1:]:
        f = line.split(';')
        if len(f) >= 4 and f[0].isdigit() and int(f[0]) in keep:
            color_id[(int(f[1]), int(f[2]), int(f[3]))] = int(f[0])
    img = Image.open(game / 'map' / 'provinces.bmp').convert('RGB')
    W, H = img.size
    data = list(img.get_flattened_data()) if hasattr(img, 'get_flattened_data') else list(img.getdata())
    pid = [color_id.get(c, 0) for c in data]
    # 有几块像素离主体很远（远处小岛、零星同色像素）：按连通块算，只留落在最大连通块附近（横向外扩 80%、纵向 35%）的块
    seen, comps = set(), []
    for start, p in enumerate(pid):
        if not p or start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            k = stack.pop()
            comp.append(k)
            x, y = k % W, k // W
            for nk in ((k - 1) if x else -1, (k + 1) if x + 1 < W else -1, k - W, k + W):
                if 0 <= nk < W * H and pid[nk] and nk not in seen:
                    seen.add(nk)
                    stack.append(nk)
        comps.append(comp)
    main = max(comps, key=len)
    mx = [k % W for k in main]
    my = [k // W for k in main]
    bx0, bx1, by0, by1 = min(mx), max(mx), min(my), max(my)
    ex, ey = (bx1 - bx0) * .8, (by1 - by0) * .35
    drop = set()
    for comp in comps:
        cx = [k % W for k in comp]
        cy = [k // W for k in comp]
        if min(cx) < bx0 - ex or max(cx) > bx1 + ex or min(cy) < by0 - ey or max(cy) > by1 + ey:
            drop.update(comp)
    pid = [0 if k in drop else p for k, p in enumerate(pid)]
    xs = [i % W for i, p in enumerate(pid) if p]
    ys = [i // W for i, p in enumerate(pid) if p]
    x0, y0, x1, y1 = min(xs) - 4, min(ys) - 4, max(xs) + 5, max(ys) + 5
    w, h = x1 - x0, y1 - y0
    grid = [[pid[(y0 + y) * W + x0 + x] for x in range(w)] for y in range(h)]
    adj = {}
    for y in range(h):
        for x in range(w):
            a = grid[y][x]
            if not a:
                continue
            adj.setdefault(a, set())
            for dx, dy in ((1, 0), (0, 1)):
                if x + dx < w and y + dy < h and grid[y + dy][x + dx] not in (0, a):
                    adj[a].add(grid[y + dy][x + dx])
                    adj.setdefault(grid[y + dy][x + dx], set()).add(a)
    col = {}
    for i in sorted(adj, key=lambda i: -len(adj[i])):
        used = {col[j] for j in adj[i] if j in col}
        col[i] = next((c for c in range(4) if c not in used), 0)
    out = Image.new('RGB', (w * SCALE, h * SCALE), 'white')
    op = out.load()
    for y in range(h * SCALE):
        for x in range(w * SCALE):
            a = grid[y // SCALE][x // SCALE]
            if a:
                op[x, y] = PALETTE[col[a]]
    edge = Image.new('L', out.size, 0)
    ep = edge.load()
    for y in range(h * SCALE - 1):
        for x in range(w * SCALE - 1):
            a = grid[y // SCALE][x // SCALE]
            if a != grid[y // SCALE][(x + 1) // SCALE] or a != grid[(y + 1) // SCALE][x // SCALE]:
                ep[x, y] = 255
    out.paste(INK, mask=edge.filter(ImageFilter.MaxFilter(3)))
    ASSETS.mkdir(parents=True, exist_ok=True)
    out.save(ASSETS / 'map-reference.png', optimize=True)
    src = {'regions': REGIONS, 'provinces': sorted(adj), 'bbox_pixels': [x0, y0, x1, y1], 'scale': SCALE,
           'source': 'EU4 map/provinces.bmp, definition.csv, region.txt, area.txt'}
    (ASSETS / 'map-source.json').write_text(json.dumps(src, indent=1) + '\n', encoding='utf-8')
    print(f'{len(adj)} 个省份，参考图 {out.size} → {ASSETS / "map-reference.png"}')


def derive():
    files = {}
    for lang, jpg in (('en', 'cover.jpg'), ('zh-CN', 'cover.zh-CN.jpg')):
        m = Image.open(ASSETS / f'cover-master.{lang}.png').convert('RGB')
        side = min(m.size)
        m = m.crop(((m.width - side) // 2, (m.height - side) // 2, (m.width + side) // 2, (m.height + side) // 2))
        m.resize((1254, 1254), Image.LANCZOS).save(ASSETS / jpg, quality=90)
        files[jpg] = f'cover-master.{lang}.png'
        if lang == 'en':
            m.resize((512, 512), Image.LANCZOS).save(ASSETS / 'thumbnail.png', optimize=True)
            files['thumbnail.png'] = 'cover-master.en.png'
    for f in files:
        assert (ASSETS / f).stat().st_size < 1_000_000, f'{f} 超过工坊 1 MB 上限'
    sha = {f: hashlib.sha256((ASSETS / f).read_bytes()).hexdigest()
           for f in sorted(set(files) | set(files.values()) | {'map-reference.png'}) if (ASSETS / f).exists()}
    print(json.dumps(sha, indent=1))
    return sha


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('reference')
    r.add_argument('--game-root', type=Path, required=True)
    sub.add_parser('derive')
    a = ap.parse_args()
    reference(a.game_root) if a.cmd == 'reference' else derive()


if __name__ == '__main__':
    main()
