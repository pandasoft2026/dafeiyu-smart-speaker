# -*- coding: utf-8 -*-
"""解析 MTK logo 分区：解出全部图片，生成联系表，确认哪张是开机 logo"""
import struct, zlib, os
from PIL import Image

SRC = r"D:\workbuddy\2026-11-19-10-59-25\backup_speaker\logo_partition_original.bin"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\logo_work"
os.makedirs(OUT, exist_ok=True)

d = open(SRC, "rb").read()
count, total = struct.unpack("<II", d[0x200:0x208])
offs = list(struct.unpack("<%dI" % count, d[0x208:0x208 + count * 4]))
BASE = 0x200

thumbs = []
for k in range(count):
    s = BASE + offs[k]
    e = BASE + (offs[k + 1] if k + 1 < count else total)
    try:
        raw = zlib.decompress(d[s:e])
    except Exception as ex:
        print(k, "zlib fail", ex); continue
    if len(raw) != 1280 * 800 * 4:
        print(k, "size", len(raw)); continue
    im = Image.frombytes("RGBA", (1280, 800), raw)
    # 自动判断通道：若整体偏蓝/偏红说明是 BGRA
    r, g, b = im.split()[:3]
    # 用角落像素判断：京智康 logo 通常白色/彩色
    im.save(os.path.join(OUT, "logo_%02d.png" % k))
    thumbs.append((k, im.convert("RGB").resize((256, 160), Image.LANCZOS)))
    print(k, "ok", len(raw), "comp", e - s)

# 联系表 6x10
cols, rows = 6, (len(thumbs) + 5) // 6
sheet = Image.new("RGB", (cols * 256, rows * 168), (20, 20, 20))
from PIL import ImageDraw
dr = ImageDraw.Draw(sheet)
for i, (k, t) in enumerate(thumbs):
    x, y = (i % cols) * 256, (i // cols) * 168
    sheet.paste(t, (x, y + 14))
    dr.text((x + 4, y + 2), "#%d" % k, fill=(255, 230, 120))
sheet.save(os.path.join(OUT, "_sheet.png"))
print("sheet", sheet.size)
