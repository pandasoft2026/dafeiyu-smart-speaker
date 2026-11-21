# -*- coding: utf-8 -*-
"""改进版：用色调差异去白底，生成透明立绘 + 融合壁纸 + 开机帧。"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os, random

SRC = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\Chibi_Q_version_cute_anime_gir_2026-11-20T03-35-24.png"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert("RGB")
W, H = im.size
im = im.crop((0, 0, W, H - 78))  # 去水印

# 去白底：计算每个像素与白色的距离，白->透明
px = im.load()
out = Image.new("RGBA", im.size)
opx = out.load()
for y in range(im.height):
    for x in range(im.width):
        r, g, b = px[x, y]
        # 亮度 + 饱和度的综合判断
        mx, mn = max(r, g, b), min(r, g, b)
        sat = mx - mn  # 白底饱和度接近0且很亮
        # 白底：非常亮且低饱和
        whiteness = max(0, min(1, (mx - 235) / 20)) * max(0, min(1, (28 - sat) / 28))
        alpha = int(255 * (1 - whiteness))
        opx[x, y] = (r, g, b, alpha)

# 轻微羽化边缘
out = out.filter(ImageFilter.GaussianBlur(0.4))
out.save(os.path.join(OUT, "dafeiyu_transparent2.png"))

# 收紧 bbox（用 alpha 通道）
a = out.getchannel("A")
bbox = a.point(lambda v: 255 if v > 30 else 0).getbbox()
char = out.crop(bbox) if bbox else out
char.save(os.path.join(OUT, "dafeiyu_cutout2.png"))
print("cutout2:", char.size, "bbox", bbox)

# 头像
def avatar(img, size=256):
    s2 = img.copy()
    ratio = size / (min(s2.size) * 0.88)
    s2 = s2.resize((int(s2.width * ratio), int(s2.height * ratio)), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(s2, ((size - s2.width) // 2, -int(s2.height * 0.02)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    canvas.putalpha(mask)
    return canvas
avatar(char).save(os.path.join(OUT, "avatar.png"))

# 壁纸
def gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line((0, y, w, y), fill=c)
    return img

SW, SH = 800, 1280
wall = gradient((SW, SH), (232, 244, 255), (170, 210, 242))
d = ImageDraw.Draw(wall, "RGBA")
random.seed(7)
for _ in range(26):
    x = random.randint(0, SW); y = random.randint(120, SH - 100)
    r = random.randint(14, 52)
    d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 30))

ch = char.copy()
ch.thumbnail((760, 900), Image.LANCZOS)
wall.alpha_composite(ch, ((SW - ch.width) // 2, SH - ch.height - 30))

try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 64)
    font2 = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30)
except Exception:
    font = font2 = ImageFont.load_default()
dd = ImageDraw.Draw(wall)
dd.text((SW // 2, 140), "大肥鱼", font=font, fill=(30, 90, 150, 255), anchor="mm")
dd.text((SW // 2, 205), "随时为你解答", font=font2, fill=(70, 130, 180, 255), anchor="mm")
wall.convert("RGB").save(os.path.join(OUT, "wallpaper_800x1280.jpg"), quality=92)
print("wallpaper ok")

# 开机帧
BOOTS = os.path.join(OUT, "bootframes")
os.makedirs(BOOTS, exist_ok=True)
for f in os.listdir(BOOTS):
    os.remove(os.path.join(BOOTS, f))
bgc = gradient((SW, SH), (16, 38, 68), (34, 86, 136))
bch = char.copy(); bch.thumbnail((500, 600), Image.LANCZOS)
bx = (SW - bch.width) // 2; by = 340
for i in range(10):
    t = i / 9
    frame = bgc.copy()
    fd = ImageDraw.Draw(frame, "RGBA")
    cx, cy, rr = SW // 2, 990, 32
    fd.arc((cx - rr, cy - rr, cx + rr, cy + rr), -90, -90 + 360 * t, fill=(255,255,255,230), width=7)
    layer = bch.copy()
    al = int(255 * min(1, t * 1.5))
    layer.putalpha(layer.getchannel("A").point(lambda a: a * al // 255))
    frame.alpha_composite(layer, (bx, by - int((1 - t) * 24)))
    ImageDraw.Draw(frame).text((SW//2, 160), "大肥鱼", font=font, fill=(235,245,255,255), anchor="mm")
    frame.convert("RGB").save(os.path.join(BOOTS, "%02d.png" % i))
print("boot frames ok")
print("DONE")
