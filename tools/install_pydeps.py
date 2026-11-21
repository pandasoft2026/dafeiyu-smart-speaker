# -*- coding: utf-8 -*-
"""本地运行：下载纯Python依赖wheel并推到设备安装。"""
import requests, os, subprocess, time, zipfile, io

adb = r"D:\workbuddy\2026-11-19-10-59-25\tools\platform-tools\adb.exe"
dev = "${SPEAKER_IP:-192.168.1.50}:5555"
localdir = r"D:\workbuddy\2026-11-19-10-59-25\tools\pydeps"
os.makedirs(localdir, exist_ok=True)

wheels = {
    "requests": "https://files.pythonhosted.org/packages/a0/f4/c67b0b3f1b9245e8d266f0f112c500d50e5b4e83cb6f3b71b6528104182a/requests-2.34.2-py3-none-any.whl",
    "urllib3": "https://files.pythonhosted.org/packages/92/9d/c4e665119135114480843e7ab388fa94d8480650450e6f8e26b70d323a4c/urllib3-2.8.0-py3-none-any.whl",
    "certifi": "https://files.pythonhosted.org/packages/32/d1/a3652fe2c19134d0d15922177821d863cbd7e842d53a21bbe7e8e3a1b5ac/certifi-2026.10.23-py3-none-any.whl",
    "charset_normalizer": "https://files.pythonhosted.org/packages/fc/ad/d07d7862a62ffa6d79d68074d14823243dd235a77c45262acbf6adeb28bf/charset_normalizer-3.5.2-py3-none-any.whl",
    "idna": "https://files.pythonhosted.org/packages/58/a2/bb081bab032533a855d44de1d56f8e8426114ff1ba5d1f07a438a0a654f8/idna-3.20-py3-none-any.whl",
}

# download all locally
print("=== 下载 wheels ===")
for name, url in wheels.items():
    p = os.path.join(localdir, name + ".whl")
    if not os.path.exists(p):
        data = requests.get(url, timeout=60).content
        open(p, "wb").write(data)
    print(" ", name, os.path.getsize(p))

subprocess.run([adb, "connect", dev], capture_output=True)
time.sleep(1)

# Build a single zip containing all wheel contents, push once
print("\n=== 打包所有依赖 ===")
merged = os.path.join(localdir, "all_deps.zip")
with zipfile.ZipFile(merged, "w", zipfile.ZIP_DEFLATED) as out:
    for name in wheels:
        with zipfile.ZipFile(os.path.join(localdir, name + ".whl")) as z:
            for item in z.namelist():
                out.writestr(item, z.read(item))
print("  merged", os.path.getsize(merged))

# push to tmp, extract on device
r = subprocess.run([adb, "-s", dev, "push", merged, "/data/local/tmp/all_deps.zip"],
                   capture_output=True, text=True)
print("\n=== 推送 ===", r.returncode, r.stdout.strip()[-50:])

script = r'''
import zipfile, sysconfig
site = sysconfig.get_paths()["purelib"]
with zipfile.ZipFile("/data/local/tmp/all_deps.zip") as z:
    z.extractall(site)
print("EXTRACTED to", site)
'''
open(os.path.join(localdir, "extract.py"), "w").write(script)
subprocess.run([adb, "-s", dev, "push", os.path.join(localdir, "extract.py"),
                "/data/local/tmp/extract_deps.py"], capture_output=True)
PYBIN = "/data/data/com.termux/files/usr/bin/python"
cmd = "su -c '" + PYBIN + " /data/local/tmp/extract_deps.py'"
r = subprocess.run([adb, "-s", dev, "shell", cmd], capture_output=True, text=True)
print("=== 解压 ===", r.stdout, r.stderr[:200])
