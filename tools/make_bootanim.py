# -*- coding: utf-8 -*-
"""打包 bootanimation.zip：desc.txt + part0/帧序列。"""
import os, zipfile

ASSETS = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
FRAMES = os.path.join(ASSETS, "bootframes")
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\bootanimation.zip"

# desc.txt: width height fps
# p 计数 暂停 文件夹
# 循环播放 part0 一次淡入后停留
desc = "800 1280 10\np 10 0 part0\n"

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as z:  # 必须 STORED 不压缩
    z.writestr("desc.txt", desc)
    for f in sorted(os.listdir(FRAMES)):
        if f.endswith(".png"):
            z.write(os.path.join(FRAMES, f), "part0/" + f)
print("created", OUT, os.path.getsize(OUT), "bytes")
with zipfile.ZipFile(OUT) as z:
    print("entries:", len(z.namelist()), z.namelist()[:4])
