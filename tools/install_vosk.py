# -*- coding: utf-8 -*-
"""在设备上运行：安装 vosk wheel + 解压中文模型。用设备 Termux 的 python 执行。"""
import os, sys, zipfile, subprocess

VB = "/data/local/tmp/voicebot"
PREFIX = "/data/data/com.termux/files/usr"
PYBIN = PREFIX + "/bin/python"
SITE = PREFIX + "/lib/python3.14/site-packages"
# verify actual path
import sysconfig
SITE = sysconfig.get_paths().get("purelib", SITE)

print("=== 1. 检查文件 ===")
for f in ["vosk.whl", "model.zip", "api_key.conf"]:
    p = os.path.join(VB, f)
    print("  ", f, os.path.getsize(p) if os.path.exists(p) else "MISSING")

print("\n=== 2. 安装 vosk wheel ===")
whl = VB + "/vosk.whl"
# pip may not exist; unzip wheel into site-packages manually
try:
    with zipfile.ZipFile(whl) as z:
        names = z.namelist()
        print("   wheel entries:", len(names))
        z.extractall(SITE)
    print("   extracted to site-packages")
except Exception as e:
    print("   FAIL:", e)

print("\n=== 3. 解压模型 ===")
mz = VB + "/model.zip"
modeldir = VB + "/model"
if not os.path.exists(modeldir + "/am"):
    with zipfile.ZipFile(mz) as z:
        top = z.namelist()[0].split("/")[0]
        z.extractall(VB)
    extracted = VB + "/" + top
    if extracted != modeldir and os.path.exists(extracted):
        if os.path.exists(modeldir):
            import shutil; shutil.rmtree(modeldir)
        os.rename(extracted, modeldir)
    print("   model at", modeldir)
else:
    print("   model already present")
print("   model files:", os.listdir(modeldir)[:10] if os.path.exists(modeldir) else "NONE")

print("\n=== 4. 验证 vosk import ===")
sys.path.insert(0, SITE)
try:
    import vosk
    print("   vosk OK", vosk.__file__)
except Exception as e:
    print("   vosk IMPORT FAIL:", e)
