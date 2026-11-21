# -*- coding: utf-8 -*-
"""
构造新的 MTK logo 分区镜像（1280x800 RGBA + zlib，格式与原件一致）
布局: [header 0x200][count/total][count 个偏移][图片数据...][cert1+cert2 段]
偏移基准 = 0x200，首个数据块偏移 = 8 + count*4 = 0xF8
#0 与 #59 均换成新图（各存一份，保持偏移单调），#1..#58 原样
"""
import struct, zlib
from PIL import Image

ORIG = r"D:\workbuddy\2026-11-19-10-59-25\backup_speaker\logo_partition_original.bin"
NEWIMG = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets\boot_final_1280x800.jpg"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\logo_work\logo_new.bin"
PART = 8388608
BASE = 0x200

d = open(ORIG, "rb").read()
count, total = struct.unpack("<II", d[BASE:BASE + 8])
offs = list(struct.unpack("<%dI" % count, d[BASE + 8:BASE + 8 + count * 4]))

blobs = {}
for k in range(count):
    s = BASE + offs[k]
    e = BASE + (offs[k + 1] if k + 1 < count else total)
    blobs[k] = d[s:e]

# cert 区：从 16 对齐处到最后一个非零字节
cert_start = (BASE + total + 15) // 16 * 16
cert_end = len(d)
while cert_end > cert_start and d[cert_end - 1] == 0:
    cert_end -= 1
cert_end = (cert_end + 15) // 16 * 16
cert = d[cert_start:cert_end]
print("cert", hex(cert_start), hex(cert_end), "len", len(cert))
for tag, off in (("cert1", 0), ("cert2", 0x8AD)):
    pass
print("  cert1 magic", cert[:4].hex(), "size", struct.unpack("<I", cert[4:8])[0],
      "tag", cert[8:13])

im = Image.open(NEWIMG).convert("RGBA")
assert im.size == (1280, 800), im.size
new_raw = im.tobytes()
new_comp = zlib.compress(new_raw, 9)
print("new img comp", len(new_comp))

data = bytearray()
new_offs = []
rel0 = 8 + count * 4
for k in range(count):
    blob = new_comp if k in (0, 59) else blobs[k]
    new_offs.append(rel0 + len(data))
    data.extend(blob)

new_total = rel0 + len(data)
print("data", len(data), "new_total", new_total, hex(new_total))

img = bytearray(PART)
hdr = bytearray(d[:BASE])
struct.pack_into("<I", hdr, 4, new_total)
img[0:BASE] = hdr
struct.pack_into("<I", img, BASE, count)
struct.pack_into("<I", img, BASE + 4, new_total)
for i, o in enumerate(new_offs):
    struct.pack_into("<I", img, BASE + 8 + i * 4, o)
ds = BASE + rel0
img[ds:ds + len(data)] = data
cs = (BASE + new_total + 15) // 16 * 16
img[cs:cs + len(cert)] = cert
print("data", hex(ds), "cert", hex(cs), "used", hex(cs + len(cert)), "of", hex(PART))
assert cs + len(cert) < PART

open(OUT, "wb").write(img)

# ---------- 自检 ----------
v = open(OUT, "rb").read()
c2, t2 = struct.unpack("<II", v[BASE:BASE + 8])
assert (c2, t2) == (count, new_total), (c2, t2)
o2 = list(struct.unpack("<%dI" % c2, v[BASE + 8:BASE + 8 + c2 * 4]))

def get(k):
    s = BASE + o2[k]
    e = BASE + (o2[k + 1] if k + 1 < c2 else t2)
    return zlib.decompress(v[s:e])

checks = [
    ("offsets strictly increasing", all(o2[i] < o2[i + 1] for i in range(c2 - 1))),
    ("60 images all decode", all(len(get(k)) == 4096000 for k in range(c2))),
    ("#0 == new image", get(0) == new_raw),
    ("#59 == new image", get(59) == new_raw),
    ("#1 unchanged", get(1) == zlib.decompress(blobs[1])),
    ("#30 unchanged", get(30) == zlib.decompress(blobs[30])),
    ("#58 unchanged", get(58) == zlib.decompress(blobs[58])),
    ("cert intact", v[cs:cs + len(cert)] == cert),
    ("no overlap data/cert", ds + len(data) <= cs),
]
for n, ok in checks:
    print(("  OK  " if ok else " FAIL ") + n)
print("ALL PASS" if all(o for _, o in checks) else "*** HAS FAILURE ***")

# 预览新 #0
Image.frombytes("RGBA", (1280, 800), get(0)).convert("RGB").save(
    r"D:\workbuddy\2026-11-19-10-59-25\logo_work\_preview_new0.png")
