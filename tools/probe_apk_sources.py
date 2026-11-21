# -*- coding: utf-8 -*-
"""Probe APK mirrors with a 5-byte Range request to find a working download channel."""
import requests

GH = "https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_arm64-v8a.apk"

sources = [
    ("f-droid-1183",  "https://f-droid.org/repo/com.termux_1183.apk"),
    ("f-droid-1180",  "https://f-droid.org/repo/com.termux_1180.apk"),
    ("f-droid-11900", "https://f-droid.org/repo/com.termux_11900.apk"),
    ("fdroid-tuna-1183", "https://mirrors.tuna.tsinghua.edu.cn/fdroid/fdroid/repo/com.termux_1183.apk"),
    ("fdroid-ustc-1183", "https://mirrors.ustc.edu.cn/fdroid/repo/com.termux_1183.apk"),
    ("github-api-asset", GH),
    ("ghproxy",       "https://ghproxy.net/" + GH),
    ("ghproxy-io",    "https://gh-proxy.com/" + GH),
    ("jsdelivr-gh",   "https://cdn.jsdelivr.net/gh/termux/termux-app@master/README.md"),
    ("gitee-release", "https://gitee.com/mirrors/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_arm64-v8a.apk"),
    ("sourceforge",   "https://sourceforge.net/projects/termux/files/latest/download"),
    ("oppo-store",    "https://m.oppo.com/"),
    ("tencent-qq",    "https://im.qq.com/"),
]

def probe(name, url, proxy):
    s = requests.Session()
    s.trust_env = proxy
    try:
        r = s.get(url, headers={"Range": "bytes=0-4", "User-Agent": "Mozilla/5.0"},
                  stream=True, timeout=(10, 20))
        data = next(r.iter_content(8), b"")
        cl = r.headers.get("content-length")
        cr = r.headers.get("content-range")
        ok = r.status_code in (200, 206) and (data[:2] == b"PK" or len(data) >= 2)
        print(f"  {name:20s} proxy={str(proxy):5s} status={r.status_code} "
              f"bytes={data[:5]!r} range={cr} len={cl}", flush=True)
        return ok
    except Exception as e:
        print(f"  {name:20s} proxy={str(proxy):5s} FAIL {type(e).__name__}: {str(e)[:70]}", flush=True)
        return False

for proxy in (True, False):
    print(f"\n===== proxy={proxy} =====", flush=True)
    for name, url in sources:
        probe(name, url, proxy)
