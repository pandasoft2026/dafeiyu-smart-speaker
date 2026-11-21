# -*- coding: utf-8 -*-
"""
生成「梁圣模式」界面素材：
  apk/assets/sage_bg.jpg     1280x800 全屏背景（原图 + 右侧深色渐层 + 顶部/底部压暗 + 冷调 + 暗角）
  apk/assets/avatar_sage.png 192x192 圆形头像（裁头部）
原图比例正好 1.6，与舞台一致，不拉伸。
"""
import os
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

SRC = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets\boot_final_1280x800.jpg"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\apk\assets"
W, H = 1280, 800


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def build_bg():
    im = Image.open(SRC).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)

    # ---- 0) 稍放大后左移取景，把人物压到左侧，右侧留出干净的对话区 ----
    #      原图脸心 x≈557；放大 1.12 后裁掉左侧 144，脸心落到 480
    sc = 1.12
    im = im.resize((int(W * sc), int(H * sc)), Image.LANCZOS)
    im = im.crop((144, 2, 144 + W, 2 + H))

    # 轻微降饱和 + 提对比，冷调
    im = ImageEnhance.Color(im).enhance(0.86)
    im = ImageEnhance.Contrast(im).enhance(1.06)
    im = ImageEnhance.Brightness(im).enhance(0.97)

    px = im.load()

    # ---- 1) 右侧深色渐层：从 x=38% 开始压到 92% 不透明 ----
    #     色值取极深藏蓝，末端略带青
    for x in range(W):
        t = (x / W - 0.34) / (1.0 - 0.34)
        a = smooth(t) ** 1.25 * 0.945
        if a <= 0.002:
            continue
        for y in range(H):
            r, g, b = px[x, y]
            # 深色随纵向也变化：底部更暗一点
            k = 0.86 + 0.14 * (1 - y / H)
            dr = int(5 * k)
            dg = int(12 * k)
            db = int(23 * k)
            px[x, y] = (
                int(lerp(r, dr, a)),
                int(lerp(g, dg, a)),
                int(lerp(b, db, a)),
            )

    # ---- 2) 顶部压暗（顶栏可读） ----
    for y in range(150):
        a = smooth(1 - y / 150.0) ** 1.4 * 0.62
        for x in range(W):
            r, g, b = px[x, y]
            px[x, y] = (int(lerp(r, 4, a)), int(lerp(g, 10, a)), int(lerp(b, 20, a)))

    # ---- 3) 底部压暗（麦克风区） ----
    for y in range(H - 190, H):
        a = smooth((y - (H - 190)) / 190.0) ** 1.25 * 0.72
        for x in range(W):
            r, g, b = px[x, y]
            px[x, y] = (int(lerp(r, 3, a)), int(lerp(g, 8, a)), int(lerp(b, 17, a)))

    # ---- 4) 暗角：小图算径向衰减再放大，快且平滑 ----
    sw, sh = 96, 60
    small = Image.new("L", (sw, sh), 0)
    sp = small.load()
    for yy in range(sh):
        for xx in range(sw):
            dx = (xx / (sw - 1) - 0.5) * 2.0
            dy = (yy / (sh - 1) - 0.5) * 2.0
            d = min(1.0, ((dx * dx) * 1.02 + (dy * dy) * 1.14) ** 0.5)
            v = max(0.0, (d - 0.52) / 0.48)
            sp[xx, yy] = int(255 * (v ** 1.7) * 0.62)
    vig = small.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(30))
    dark = Image.new("RGB", (W, H), (4, 9, 18))
    im = Image.composite(dark, im, vig)

    im.save(os.path.join(OUT, "sage_bg.jpg"), quality=90, optimize=True, progressive=True)
    print("sage_bg.jpg", im.size)


def build_avatar():
    im = Image.open(SRC).convert("RGB")
    # 头顶约 y=30、下巴约 y=325，头高 295；圆头像留白多些，先在顶部补 40px 再取 460 方框
    # 补边用原图顶部 3 行纵向拉伸，逐列贴合原背景，避免色带
    strip = im.crop((0, 0, W, 3)).resize((W, 40), Image.BILINEAR)
    padded = Image.new("RGB", (W, H + 40))
    padded.paste(strip, (0, 0))
    padded.paste(im, (0, 40))
    box = (320, 0, 780, 460)          # 460x460，脸心水平居中
    head = padded.crop(box).resize((480, 480), Image.LANCZOS)
    head = ImageEnhance.Color(head).enhance(0.95)
    head = ImageEnhance.Contrast(head).enhance(1.04)
    head.save(os.path.join(OUT, "avatar_sage.png"), optimize=True)
    print("avatar_sage.png", head.size, "crop", box, "(top padded 40)")


if __name__ == "__main__":
    build_bg()
    build_avatar()
