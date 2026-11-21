# -*- coding: utf-8 -*-
"""Generic chunked APK downloader. Usage: download_apk.py <url> <outfile> <total_size>"""
import os, sys, time, requests

url, out = sys.argv[1], sys.argv[2]
total = int(sys.argv[3])
CHUNK = 1 << 20
os.makedirs(os.path.dirname(out), exist_ok=True)
part = out + ".part"

have = os.path.getsize(part) if os.path.exists(part) else 0
if have % CHUNK != 0:
    have = (have // CHUNK) * CHUNK
    with open(part, "rb+") as f:
        f.truncate(have)
print(f"resume {have}/{total}", flush=True)

s = requests.Session(); s.trust_env = True
h = {"User-Agent": "Mozilla/5.0"}
with open(part, "ab" if have else "wb") as f:
    pos = have
    while pos < total:
        end = min(pos + CHUNK - 1, total - 1)
        ok = False
        for a in range(5):
            try:
                r = s.get(url, headers={**h, "Range": f"bytes={pos}-{end}"}, timeout=(10, 25))
                if r.status_code in (200, 206) and len(r.content) == end - pos + 1:
                    f.write(r.content); f.flush(); ok = True; break
            except Exception:
                pass
            time.sleep(0.4 * (a + 1))
        if not ok:
            print(f"FAIL at {pos}", flush=True); sys.exit(2)
        pos = end + 1
        if (pos // CHUNK) % 8 == 0:
            print(f"  {pos/1048576:.0f}/{total/1048576:.0f} MB", flush=True)

size = os.path.getsize(part)
with open(part, "rb") as f: magic = f.read(4)
if size == total and magic == b"PK\x03\x04":
    os.replace(part, out)
    print(f"SUCCESS {out} ({size} bytes)", flush=True)
else:
    print(f"MISMATCH size={size} magic={magic!r}", flush=True); sys.exit(3)
