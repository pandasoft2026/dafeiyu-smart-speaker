# -*- coding: utf-8 -*-
"""把用户提供的开机图排成 800x1280 竖屏，两种方案对比：cover 裁剪 / contain 上下延展"""
from PIL import Image, ImageFilter
import os

SRC = r"C:\Users\zlw\.workbuddy\clipboard-images\clipboard-2026-11-20T03-51-40-741Z-998253cf.jpg"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
W, H = 800, 1280

im = Image.open(SRC).convert("RGB")
sw, sh = im.size


def cover(im, W, H, cx=0.5, cy=0.5):
    s = max(W / im.width, H / im.height)
    nw, nh = int(round(im.width * s)), int(round(im.height * s))
    big = im.resize((nw, nh), Image.LANCZOS)
    # 裁剪中心可按比例偏移
    left = int(round((nw - W) * cx))
    top = int(round((nh - H) * cy))
    left = max(0, min(nw - W, left))
    top = max(0, min(nh - H, top))
    return big.crop((left, top, left + W, top + H))


def contain_blurfill(im, W, H):
    """等比缩放到宽度满屏，上下用自身模糊延展填充，绝不拉伸主体"""
    s = W / im.width
    nw, nh = W, int(round(im.height * s))
    fg = im.resize((nw, nh), Image.LANCZOS)

    # 背景：整图放大铺满 + 重模糊 + 压暗
    bg = cover(im, W, H).filter(ImageFilter.GaussianBlur(60))
    bg = Image.eval(bg, lambda v: int(v * 0.82))

    canvas = bg.copy()
    top = (H - nh) // 2
    canvas.paste(fg, (0, top))
    # 上下接缝做柔化
    for y in range(top, top + 26):
        a = (y - top) / 26.0
        row_fg = fg.crop((0, y - top, W, y - top + 1))
        row_bg = canvas.crop((0, y, W, y + 1)).filter(ImageFilter.GaussianBlur(8))
        canvas.paste(Image.blend(row_bg, row_fg, a), (0, y))
    return canvas


a = cover(im, W, H, cx=0.5, cy=0.5)
a.save(os.path.join(OUT, "boot_A_cover.jpg"), quality=92)
b = contain_blurfill(im, W, H)
b.save(os.path.join(OUT, "boot_B_contain.jpg"), quality=92)
print("A", a.size, "B", b.size)
