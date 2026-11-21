# -*- coding: utf-8 -*-
"""从大肥鱼主形象生成主题素材：透明立绘、圆头像、竖屏壁纸、开机动画帧。"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os, math

SRC = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\Chibi_Q_version_cute_anime_gir_2026-11-20T03-35-24.png"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert("RGBA")
W, H = im.size

# ---- 1. 裁掉右下角水印（底部 ~75px）----
crop = im.crop((0, 0, W, H - 78))

# ---- 2. 去白底 -> 透明 ----
px = crop.load()
for y in range(crop.height):
    for x in range(crop.width):
        r, g, b, a = px[x, y]
        # 白/近白背景转透明；保留柔和阴影边缘
        mn = min(r, g, b)
        if mn > 238:
            alpha = max(0, min(255, int((255 - mn) / 17 * 255)))
            px[x, y] = (r, g, b, int(a * alpha / 255))
crop.save(os.path.join(OUT, "dafeiyu_transparent.png"))
print("1. transparent:", crop.size)

# 收紧到实际内容边界
bbox = crop.getbbox()
char = crop.crop(bbox) if bbox else crop
char.save(os.path.join(OUT, "dafeiyu_cutout.png"))
print("1b. cutout:", char.size, "bbox", bbox)

# ---- 3. 圆形头像（界面用）----
def circle_avatar(img, size=256):
    s = img.copy()
    s.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # 取上半身：用 cutout 缩放到稍大再裁中心
    s2 = img.copy()
    ratio = size / (min(s2.size) * 0.9)
    s2 = s2.resize((int(s2.width * ratio), int(s2.height * ratio)), Image.LANCZOS)
    ox = (size - s2.width) // 2
    oy = -int(s2.height * 0.05)
    canvas.alpha_composite(s2, (ox, oy))
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0, 0, size - 1, size - 1), fill=255)
    canvas.putalpha(mask)
    return canvas

av = circle_avatar(char, 256)
av.save(os.path.join(OUT, "avatar.png"))
print("2. avatar:", av.size)

# ---- 4. 竖屏壁纸 800x1280（淡蓝渐变 + 角色 + 气泡点缀）----
def gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line((0, y, w, y), fill=c)
    return img.convert("RGBA")

SW, SH = 800, 1280
wall = gradient((SW, SH), (230, 243, 255), (176, 214, 245))

# 装饰：柔和气泡
d = ImageDraw.Draw(wall, "RGBA")
import random
random.seed(7)
for _ in range(28):
    x = random.randint(0, SW); y = random.randint(0, SH)
    r = random.randint(12, 55)
    d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 26))
    d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 55), width=2)

# 角色放大居中下半部
ch = char.copy()
scale = 1.18
ch = ch.resize((int(ch.width * scale), int(ch.height * scale)), Image.LANCZOS)
if ch.width > SW:
    ch.thumbnail((SW, int(SH * 0.72)), Image.LANCZOS)
px_ = (SW - ch.width) // 2
py_ = SH - ch.height - 40
wall.alpha_composite(ch, (px_, py_))

# 顶部文字
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 62)
    font2 = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30)
except Exception:
    font = ImageFont.load_default(); font2 = font
d = ImageDraw.Draw(wall)
title = "大肥鱼"
d.text((SW // 2, 150), title, font=font, fill=(30, 90, 150, 255), anchor="mm")
d.text((SW // 2, 220), "随时为你解答", font=font2, fill=(70, 130, 180, 255), anchor="mm")

wall.convert("RGB").save(os.path.join(OUT, "wallpaper_800x1280.jpg"), quality=92)
print("3. wallpaper:", wall.size)

# ---- 5. 开机动画帧（简版：淡入 + 角色浮现，10 帧）----
BOOTS = os.path.join(OUT, "bootframes")
os.makedirs(BOOTS, exist_ok=True)
bgc = gradient((SW, SH), (18, 42, 74), (36, 88, 140))
bch = char.copy()
bch.thumbnail((520, 620), Image.LANCZOS)
bx = (SW - bch.width) // 2
by = 330
for i in range(10):
    t = i / 9
    frame = bgc.copy()
    fd = ImageDraw.Draw(frame, "RGBA")
    # 进度圆环
    cx, cy, rr = SW // 2, 980, 34
    fd.arc((cx - rr, cy - rr, cx + rr, cy + rr), -90, -90 + 360 * t,
           fill=(255, 255, 255, 220), width=7)
    # 角色淡入 + 轻微上浮
    layer = bch.copy()
    alpha = int(255 * min(1, t * 1.4))
    layer.putalpha(layer.getchannel("A").point(lambda a: a * alpha // 255))
    frame.alpha_composite(layer, (bx, by - int((1 - t) * 26)))
    try:
        f2 = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 46)
    except Exception:
        f2 = ImageFont.load_default()
    ImageDraw.Draw(frame).text((SW // 2, 160), "大肥鱼", font=f2,
                               fill=(235, 245, 255, 255), anchor="mm")
    frame.convert("RGB").save(os.path.join(BOOTS, "%02d.png" % i))

print("4. boot frames: 10")
print("DONE ->", OUT)
