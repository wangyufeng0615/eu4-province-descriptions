"""EU4 地方志按钮：沿用原版历史按钮的金框和石板底座，中间画卷轴＋火漆印。

uv run --with pillow tools/draw_icon.py <游戏目录>/gfx/interface/button_history.dds assets/eu4lg_button
输出 .png 预览和 .dds（36×36，未压缩 32 位 ARGB，和原版按钮同格式）。
"""
import sys
from PIL import Image, ImageDraw, ImageFilter
SRC, OUT = sys.argv[1], sys.argv[2]
base = Image.open(SRC).convert('RGBA')
W = 36; K = 8  # 超采样倍数
im = base.copy(); px = im.load()

# 1. 抹掉书本：内框 x/y 8..28 用竖向渐变＋轻微暗角填充，接上原有的左上高光
def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
top, bot = (0x36, 0x42, 0x4c), (0x25, 0x31, 0x3b)
for y in range(8, 29):
    for x in range(8, 29):
        c = lerp(top, bot, (y - 8) / 20)
        d = ((x - 18) ** 2 + (y - 18) ** 2) ** 0.5 / 14  # 暗角
        c = tuple(max(0, int(v * (1 - 0.18 * d))) for v in c)
        px[x, y] = c + (255,)

# 2. 在 8 倍画布上画卷轴，再缩回 36 像素
H = Image.new('RGBA', (W * K, W * K), (0, 0, 0, 0)); d = ImageDraw.Draw(H)
def R(x0, y0, x1, y1): return [int(x0 * K), int(y0 * K), int(x1 * K), int(y1 * K)]
ink = (0x3f, 0x30, 0x18, 255)
outline = (0x2a, 0x1e, 0x0e, 255)
# 投影
sh = Image.new('RGBA', H.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
ds.rounded_rectangle(R(11.6, 10.6, 26.4, 29.0), radius=1.5 * K, fill=(0, 0, 0, 150))
sh = sh.filter(ImageFilter.GaussianBlur(1.2 * K))
H.alpha_composite(sh)
# 纸面：竖向渐变
body = R(12, 10.5, 24.5, 27)
grad = Image.new('RGBA', H.size, (0, 0, 0, 0)); g = grad.load()
for y in range(body[1], body[3]):
    t = (y - body[1]) / (body[3] - body[1])
    c = lerp((0xf0, 0xd8, 0x9c), (0xb8, 0x98, 0x5c), t)
    for x in range(body[0], body[2]):
        s = (x - body[0]) / (body[2] - body[0])
        cc = tuple(int(v * (1 - 0.12 * s)) for v in c)  # 右侧略暗
        g[x, y] = cc + (255,)
H.alpha_composite(grad)
d.rectangle(body, outline=outline, width=int(0.7 * K))
# 上下卷轴筒
def roll(y0, y1):
    d.rounded_rectangle(R(10.6, y0, 25.9, y1), radius=1.4 * K, fill=(0xa8, 0x86, 0x4c, 255), outline=outline, width=int(0.7 * K))
    d.rounded_rectangle(R(11.4, y0 + 0.6, 25.1, y0 + 1.5), radius=0.5 * K, fill=(0xf6, 0xe2, 0xaa, 255))  # 高光
    d.ellipse(R(9.6, y0 + 0.1, 11.6, y1 - 0.1), fill=(0x6b, 0x3e, 0x1c, 255), outline=outline, width=int(0.5 * K))  # 轴头
    d.ellipse(R(24.9, y0 + 0.1, 26.9, y1 - 0.1), fill=(0x6b, 0x3e, 0x1c, 255), outline=outline, width=int(0.5 * K))
roll(8.6, 11.8)
roll(25.6, 28.8)
# 字迹
for y, x1 in ((14.0, 22.6), (16.3, 21.4), (18.6, 22.6), (20.9, 18.8)):
    d.line(R(13.8, y, x1, y), fill=ink, width=int(0.9 * K))
# 火漆印和飘带
d.polygon([((21.0) * K, 23.2 * K), (20.0 * K, 27.4 * K), (21.4 * K, 26.6 * K), (22.2 * K, 27.6 * K), (22.6 * K, 23.4 * K)], fill=(0x7a, 0x14, 0x18, 255))
d.ellipse(R(19.4, 21.2, 24.0, 25.8), fill=(0xa8, 0x1c, 0x22, 255), outline=(0x4a, 0x0c, 0x0e, 255), width=int(0.6 * K))
d.ellipse(R(20.4, 22.0, 21.8, 23.4), fill=(0xe0, 0x5a, 0x50, 255))  # 印面高光
small = H.resize((W, W), Image.LANCZOS)
im.alpha_composite(small)
im.save(OUT + '.png')
im.save(OUT + '.dds')
print('saved', im.size)
