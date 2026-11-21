# -*- coding: utf-8 -*-
"""两段式开机动画：嘘图淡入 -> 停留 -> 交叉淡变到大肥鱼 -> 循环"""
import os, shutil, zipfile
from PIL import Image

A = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets\boot_final_1280x800.jpg"   # 嘘图
B = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets\boot_dafeiyu_1280x800.jpg"  # 大肥鱼
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu"
W, H = 1280, 800

a = Image.open(A).convert("RGB").resize((W, H), Image.LANCZOS)
b = Image.open(B).convert("RGB").resize((W, H), Image.LANCZOS)
black = Image.new("RGB", (W, H), (0, 0, 0))

work = os.path.join(OUT, "_ba2")
if os.path.isdir(work):
    shutil.rmtree(work)
for d in ("part0", "part1", "part2", "part3"):
    os.makedirs(os.path.join(work, d))


def save(img, path, colors=0):
    if colors:
        img = img.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG)
    img.save(path, "PNG", optimize=True)


# part0: 黑 -> 嘘图 4 帧
for i, t in enumerate([0.2, 0.5, 0.78, 1.0]):
    save(Image.blend(black, a, t), os.path.join(work, "part0", "%02d.png" % i), colors=170)

# part1: 嘘图停留
save(a, os.path.join(work, "part1", "00.png"), colors=200)

# part2: 嘘图 -> 大肥鱼 交叉淡变 6 帧
for i in range(6):
    t = (i + 1) / 6.0
    save(Image.blend(a, b, t), os.path.join(work, "part2", "%02d.png" % i), colors=200)

# part3: 大肥鱼
save(b, os.path.join(work, "part3", "00.png"))

desc = "1280 800 12\np 1 0 part0\np 1 14 part1\np 1 0 part2\np 0 0 part3\n"
open(os.path.join(work, "desc.txt"), "w", newline="\n").write(desc)

zp = os.path.join(OUT, "bootanimation_final.zip")
if os.path.exists(zp):
    os.remove(zp)
files = ["desc.txt"]
for d in ("part0", "part1", "part2", "part3"):
    for n in sorted(os.listdir(os.path.join(work, d))):
        files.append("%s/%s" % (d, n))
with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
    for rel in files:
        z.write(os.path.join(work, rel.replace("/", os.sep)), rel)

print("zip %d KB, %d frames" % (os.path.getsize(zp) // 1024, len(files) - 1))
for rel in files:
    print("  ", rel, os.path.getsize(os.path.join(work, rel.replace("/", os.sep))) // 1024, "KB")
