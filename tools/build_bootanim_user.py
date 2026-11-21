# -*- coding: utf-8 -*-
"""用用户提供的图片生成 800x1280 开机动画：黑场淡入 + 微推近，之后静止停留"""
import os, shutil, zipfile
from PIL import Image

SRC = r"C:\Users\zlw\.workbuddy\clipboard-images\clipboard-2026-11-20T03-51-40-741Z-998253cf.jpg"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu"
W, H = 800, 1280
MASTER_W = 880  # 留出推近余量

work = os.path.join(OUT, "_bootwork")
if os.path.isdir(work):
    shutil.rmtree(work)
os.makedirs(os.path.join(work, "part0"))
os.makedirs(os.path.join(work, "part1"))

im = Image.open(SRC).convert("RGB")

# ---- master：等比铺满 880x1408，绝不拉伸 ----
s = max(MASTER_W / im.width, (MASTER_W * H / W) / im.height)
nw, nh = int(round(im.width * s)), int(round(im.height * s))
master = im.resize((nw, nh), Image.LANCZOS)
mh = MASTER_W * H // W
left = (nw - MASTER_W) // 2
top = max(0, (nh - mh) // 2)
master = master.crop((left, top, left + MASTER_W, top + mh))
print("master", master.size)


def frame(scale, alpha):
    """scale=1.0 时正好 800x1280；alpha 0..1 叠黑"""
    cw = int(round(W * scale))
    ch = int(round(H * scale))
    cx, cy = MASTER_W // 2, mh // 2
    box = (cx - cw // 2, cy - ch // 2, cx - cw // 2 + cw, cy - ch // 2 + ch)
    f = master.crop(box).resize((W, H), Image.LANCZOS)
    if alpha < 1.0:
        black = Image.new("RGB", (W, H), (0, 0, 0))
        f = Image.blend(black, f, alpha)
    return f


def save_png(img, path, colors=0):
    """colors>0 时减色压体积（用于快速闪过的帧）；0 表示全彩"""
    if colors:
        img = img.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG)
    img.save(path, "PNG", optimize=True)


# part0：4 帧淡入 + 推近
N = 4
for i in range(N):
    t = i / (N - 1) if N > 1 else 1.0
    scale = 0.965 + 0.035 * t          # 96.5% -> 100%
    alpha = [0.15, 0.45, 0.75, 1.0][i]  # 黑场渐入
    save_png(frame(scale, alpha), os.path.join(work, "part0", "%02d.png" % i), colors=160)

# part1：停留帧
save_png(frame(1.0, 1.0), os.path.join(work, "part1", "00.png"))

desc = "800 1280 10\np 1 0 part0\np 0 0 part1\n"
with open(os.path.join(work, "desc.txt"), "w", newline="\n") as f:
    f.write(desc)

zip_path = os.path.join(OUT, "bootanimation.zip")
if os.path.exists(zip_path):
    os.remove(zip_path)

# 必须 STORED 不压缩，且 desc.txt 在最前
files = ["desc.txt"]
for d in ("part0", "part1"):
    for n in sorted(os.listdir(os.path.join(work, d))):
        files.append("%s/%s" % (d, n))

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
    for rel in files:
        z.write(os.path.join(work, rel.replace("/", os.sep)), rel)

print("zip", os.path.getsize(zip_path) // 1024, "KB")
for rel in files:
    p = os.path.join(work, rel.replace("/", os.sep))
    print("  ", rel, os.path.getsize(p) // 1024, "KB")
