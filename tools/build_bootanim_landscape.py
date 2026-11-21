# -*- coding: utf-8 -*-
"""1280x800 横屏开机动画：主体等比完整居中，左右用自身虚化延展补齐，绝不拉伸变形"""
import os, shutil, zipfile
from PIL import Image, ImageFilter

SRC = r"C:\Users\zlw\.workbuddy\clipboard-images\clipboard-2026-11-20T03-51-40-741Z-998253cf.jpg"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu"
W, H = 1280, 800
# 推近余量：母图放大到 1.08 倍
MS = 1.08

im = Image.open(SRC).convert("RGB")

# ---------- 构造 1.08 倍母图（先按最终排版做好，再整体放大）----------
def compose(im, W, H):
    # 主体：等比缩放到高度满屏
    s = H / im.height
    fw, fh = int(round(im.width * s)), H
    fg = im.resize((fw, fh), Image.LANCZOS)

    if fw >= W:  # 宽度也够（横图），直接居中裁
        left = (fw - W) // 2
        return fg.crop((left, 0, left + W, H))

    # 宽度不够：模糊背景 + 主体居中 + 边缘羽化融合
    bs = max(W / im.width, H / im.height)
    bw, bh = int(round(im.width * bs)), int(round(im.height * bs))
    bg = im.resize((bw, bh), Image.LANCZOS)
    bl = (bw - W) // 2
    bt = (bh - H) // 2
    bg = bg.crop((bl, bt, bl + W, bt + H)).filter(ImageFilter.GaussianBlur(46))
    bg = Image.eval(bg, lambda v: int(v * 0.96))

    canvas = bg.convert("RGB")
    px = (W - fw) // 2
    # 主体左/右各 46px 做 alpha 羽化
    FE = 46
    mask = Image.new("L", (fw, fh), 255)
    mp = mask.load()
    for x in range(FE):
        v = int(255 * (x / FE) ** 0.8)
        for y in range(fh):
            mp[x, y] = v
            mp[fw - 1 - x, y] = v
    canvas.paste(fg, (px, 0), mask)
    return canvas


base = compose(im, W, H)
mw, mh = int(W * MS), int(H * MS)
master = base.resize((mw, mh), Image.LANCZOS)
print("master", master.size)

work = os.path.join(OUT, "_bootwork800")
if os.path.isdir(work):
    shutil.rmtree(work)
os.makedirs(os.path.join(work, "part0"))
os.makedirs(os.path.join(work, "part1"))


def frame(scale, alpha):
    cw = int(round(W * scale))
    ch = int(round(H * scale))
    cx, cy = mw // 2, mh // 2
    box = (cx - cw // 2, cy - ch // 2, cx - cw // 2 + cw, cy - ch // 2 + ch)
    f = master.crop(box).resize((W, H), Image.LANCZOS)
    if alpha < 1.0:
        f = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), f, alpha)
    return f


def save_png(img, path, colors=0):
    if colors:
        img = img.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG)
    img.save(path, "PNG", optimize=True)


N = 4
for i in range(N):
    t = i / (N - 1)
    save_png(frame(0.965 + 0.035 * t, [0.15, 0.45, 0.75, 1.0][i]),
             os.path.join(work, "part0", "%02d.png" % i), colors=160)
save_png(frame(1.0, 1.0), os.path.join(work, "part1", "00.png"))

with open(os.path.join(work, "desc.txt"), "w", newline="\n") as f:
    f.write("1280 800 10\np 1 0 part0\np 0 0 part1\n")

zp = os.path.join(OUT, "bootanimation_1280x800.zip")
if os.path.exists(zp):
    os.remove(zp)
files = ["desc.txt"] + sorted("part0/" + n for n in os.listdir(os.path.join(work, "part0"))) \
        + ["part1/00.png"]
with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
    for rel in files:
        z.write(os.path.join(work, rel.replace("/", os.sep)), rel)
print("zip", os.path.getsize(zp) // 1024, "KB")

frame(1.0, 1.0).save(os.path.join(OUT, "assets", "boot_final_1280x800.jpg"), quality=93)
