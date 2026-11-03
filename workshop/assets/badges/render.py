"""工坊描述顶部的双徽章：SVG 几何 + 2 倍透明 PNG。照搬 EU5 地块发布工程 workshop/assets/badges-20261031-vector/render.py，只换了文字。

运行：python -B workshop/assets/badges/render.py（Windows，需要 Pillow 和微软雅黑粗体）。"""
from pathlib import Path
import hashlib
import html
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SCALE = 4
HEIGHT, PADDING, GAP, RADIUS, FONT_SIZE = 40, 16, 12, 5, 20
INK_HEIGHT = 20
FONT = Path('C:/Windows/Fonts/msyhbd.ttc')
font = ImageFont.truetype(str(FONT), FONT_SIZE * SCALE)
# 英文页不提中文（2026-11-04 作者要求），第二个徽章换成 Bigger UI 兼容。
rows = {
    'en': [('coverage', '100%', '#238636'), ('Bigger UI', 'compatible', '#1f6feb')],
    'zh-CN': [('覆盖率', '100%', '#238636'), ('支持语言', '英文 + 简中', '#1f6feb')],
}

def glyph(text):
    box = font.getbbox(text, anchor='ls')
    mask = Image.new('L', (box[2]-box[0]+16, box[3]-box[1]+16))
    ImageDraw.Draw(mask).text((8-box[0], 8-box[1]), text, font=font, fill=255, anchor='ls')
    actual = mask.getbbox()
    ink = mask.crop(actual)
    ratio = INK_HEIGHT*SCALE/ink.height
    target_width = round(ink.width*ratio)
    ink = ink.resize((target_width, INK_HEIGHT*SCALE), Image.Resampling.LANCZOS)
    return ink, ratio, (box[0]+actual[0]-8, box[1]+actual[1]-8)

def width(text):
    ink, _, _ = glyph(text)
    return (ink.width + SCALE - 1) // SCALE

# Corresponding segments share geometry across both languages.
widths = [[max(width(rows[lang][i][j]) for lang in rows) + 2 * PADDING
           for j in range(2)] for i in range(2)]
canvas_width = sum(sum(pair) for pair in widths) + GAP
metadata = {'renderer': 'SVG geometry and Pillow raster export', 'scale': SCALE,
            'height': HEIGHT, 'horizontal_padding_minimum': PADDING,
            'gap': GAP, 'radius': RADIUS, 'font': FONT.name, 'files': {}}
metadata['ink_height'] = INK_HEIGHT
metadata['vertical_padding'] = (HEIGHT-INK_HEIGHT)/2
metadata['optical_alignment'] = 'coverage uses ink-weight centroid; other labels retain their approved positions'

for lang, badges in rows.items():
    image = Image.new('RGBA', (canvas_width * SCALE, HEIGHT * SCALE))
    draw = ImageDraw.Draw(image)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{HEIGHT}" viewBox="0 0 {canvas_width} {HEIGHT}">']
    x = 0
    for index, (label, value, color) in enumerate(badges):
        left, right = widths[index]
        total = left + right
        mask = Image.new('L', image.size)
        ImageDraw.Draw(mask).rounded_rectangle((x*SCALE, 0, (x+total)*SCALE-1, HEIGHT*SCALE-1), RADIUS*SCALE, fill=255)
        fills = Image.new('RGBA', image.size)
        fill_draw = ImageDraw.Draw(fills)
        fill_draw.rectangle((x*SCALE, 0, (x+left)*SCALE-1, HEIGHT*SCALE-1), fill='#34383d')
        fill_draw.rectangle(((x+left)*SCALE, 0, (x+total)*SCALE-1, HEIGHT*SCALE-1), fill=color)
        image.paste(fills, (0, 0), mask)
        svg += [f'<defs><clipPath id="b{index}"><rect x="{x}" width="{total}" height="{HEIGHT}" rx="{RADIUS}"/></clipPath></defs>',
                f'<g clip-path="url(#b{index})"><path fill="#34383d" d="M{x} 0h{left}v{HEIGHT}H{x}z"/><path fill="{color}" d="M{x+left} 0h{right}v{HEIGHT}H{x+left}z"/></g>']
        for text, start, segment_width in [(label, x, left), (value, x+left, right)]:
            ink, ratio, actual_origin = glyph(text)
            text_x = round(start*SCALE + (segment_width*SCALE-ink.width)/2)
            text_y = (HEIGHT-INK_HEIGHT)*SCALE//2
            if text == 'coverage':
                pixels = ink.tobytes()
                weights = [sum(pixels[y*ink.width:(y+1)*ink.width]) for y in range(ink.height)]
                center = sum(y*weight for y, weight in enumerate(weights))/sum(weights)
                text_y = round((HEIGHT*SCALE-1)/2-center)
                metadata['coverage_optical_shift'] = (text_y-(HEIGHT-INK_HEIGHT)*SCALE//2)/SCALE
            image.paste('white', (text_x, text_y, text_x+ink.width, text_y+ink.height), ink)
            svg_x = (text_x-actual_origin[0]*ratio)/SCALE
            baseline = (text_y-actual_origin[1]*ratio)/SCALE
            svg.append(f'<text x="{svg_x:.3f}" y="{baseline:.3f}" font-family="Microsoft YaHei" font-weight="700" font-size="{FONT_SIZE*ratio:.4f}" fill="white">{html.escape(text)}</text>')
        x += total + GAP
    svg.append('</svg>')
    (ROOT/f'badges.{lang}.svg').write_text('\n'.join(svg)+'\n', encoding='utf-8')
    image.resize((canvas_width*2, HEIGHT*2), Image.Resampling.LANCZOS).save(ROOT/f'badges.{lang}.png')
    for extension in ['svg', 'png']:
        path = ROOT/f'badges.{lang}.{extension}'
        metadata['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
(ROOT/'provenance.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
print(f'Rendered two language variants: {canvas_width} x {HEIGHT} logical pixels, 2x PNG.')
