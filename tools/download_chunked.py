# -*- coding: utf-8 -*-
"""Download the Termux APK in 1MB ranged chunks (survives proxy connection resets)."""
import os, sys, time, requests

URL = "https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_arm64-v8a.apk"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\tools\apk\termux-arm64.apk"
CHUNK = 1 << 20  # 1 MB
TOTAL = 35106607

os.makedirs(os.path.dirname(OUT), exist_ok=True)
part = OUT + ".part"

# resume support: keep already downloaded bytes
have = os.path.getsize(part) if os.path.exists(part) else 0
if have % CHUNK != 0:
    have = (have // CHUNK) * CHUNK
    with open(part, "rb+") as f:
        f.truncate(have)
print(f"resuming from {have}/{TOTAL} bytes", flush=True)

s = requests.Session()
s.trust_env = True
h = {"User-Agent": "Mozilla/5.0"}

mode = "ab" if have > 0 else "wb"
with open(part, mode) as f:
    pos = have
    while pos < TOTAL:
        end = min(pos + CHUNK - 1, TOTAL - 1)
        ok = False
        for attempt in range(5):
            try:
                r = s.get(URL, headers={**h, "Range": f"bytes={pos}-{end}"}, timeout=(10, 25))
                if r.status_code in (200, 206) and len(r.content) == (end - pos + 1):
                    f.write(r.content)
                    f.flush()
                    ok = True
                    break
                else:
                    print(f"  chunk {pos//CHUNK}: status={r.status_code} len={len(r.content)} expected={end-pos+1}", flush=True)
            except Exception as e:
                pass
            time.sleep(0.5 * (attempt + 1))
        if not ok:
            print(f"FAILED at chunk {pos//CHUNK} (offset {pos})", flush=True)
            sys.exit(2)
        pos = end + 1
        if (pos // CHUNK) % 5 == 0:
            print(f"  {pos/1048576:.0f}/{TOTAL/1048576:.0f} MB", flush=True)

size = os.path.getsize(part)
with open(part, "rb") as f:
    magic = f.read(4)
print(f"downloaded {size} bytes, magic={magic!r}", flush=True)
if size == TOTAL and magic == b"PK\x03\x04":
    os.replace(part, OUT)
    print(f"SUCCESS: {OUT}", flush=True)
else:
    print("SIZE/MAGIC MISMATCH", flush=True)
    sys.exit(3)
