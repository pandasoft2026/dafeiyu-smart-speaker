# -*- coding: utf-8 -*-
"""Download a Termux APK, trying direct and proxied connections across mirrors."""
import os, sys, time, requests

OUT = r"D:\workbuddy\2026-11-19-10-59-25\tools\apk\termux-arm64.apk"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

GH = "https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_arm64-v8a.apk"
attempts = [
    ("github-direct", GH, False),
    ("github-proxy",  GH, True),
    ("gitee-direct",  "https://gitee.com/mirrors/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_arm64-v8a.apk", False),
    ("gitee-proxy",   "https://gitee.com/mirrors/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_arm64-v8a.apk", True),
    ("termux-official","https://termux.dev/downloads/termux-app_0.118.0+github-debug_arm64-v8a.apk", True),
]

def valid(path):
    if not os.path.exists(path):
        return False
    size = os.path.getsize(path)
    if size < 5 * 1024 * 1024:
        return False
    with open(path, "rb") as f:
        return f.read(4) == b"PK\x03\x04"

for name, url, use_proxy in attempts:
    print(f"\n=== {name} ===", flush=True)
    print(f"    {url[:95]}", flush=True)
    tmp = OUT + ".part"
    try:
        s = requests.Session()
        s.trust_env = use_proxy
        h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        with s.get(url, headers=h, stream=True, timeout=(15, 60)) as r:
            print(f"    status={r.status_code} len={r.headers.get('content-length')}", flush=True)
            if r.status_code not in (200, 302):
                r.raise_for_status()
            got = 0
            t0 = time.time()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
                        got += len(chunk)
                        if got // (8 << 20) > (got - len(chunk)) // (8 << 20):
                            print(f"    {got/1048576:.1f} MB", flush=True)
        print(f"    total={got/1048576:.1f} MB in {time.time()-t0:.1f}s", flush=True)
        if valid(tmp):
            os.replace(tmp, OUT)
            print(f"    SUCCESS -> {OUT}", flush=True)
            sys.exit(0)
        else:
            print("    invalid APK, deleting", flush=True)
            os.remove(tmp)
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {str(e)[:180]}", flush=True)
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass

print("\nALL ATTEMPTS FAILED", flush=True)
sys.exit(1)
