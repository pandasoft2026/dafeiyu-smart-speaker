# -*- coding: utf-8 -*-
"""Resolve python + all dependencies from Termux Packages index, download all .deb locally."""
import gzip, os, re, requests, sys

PKG_URL = "https://packages.termux.dev/apt/termux-main/dists/stable/main/binary-arm/Packages.gz"
BASE = "https://packages.termux.dev/apt/termux-main/"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\tools\debs"
os.makedirs(OUT, exist_ok=True)

# Load index
idx_path = r"D:\workbuddy\2026-11-19-10-59-25\tools\Packages.txt"
if os.path.exists(idx_path):
    text = open(idx_path, encoding="utf-8", errors="replace").read()
else:
    print("downloading index...", flush=True)
    r = requests.get(PKG_URL, timeout=60)
    text = gzip.decompress(r.content).decode("utf-8", "replace")
    open(idx_path, "w", encoding="utf-8").write(text)

# Parse into packages
pkgs = {}
cur = {}
for line in text.splitlines():
    if line.startswith("Package: "):
        if cur.get("Package"):
            pkgs[cur["Package"]] = cur
        cur = {"Package": line[9:]}
    elif ": " in line and cur:
        k, v = line.split(": ", 1)
        cur[k] = v
if cur.get("Package"):
    pkgs[cur["Package"]] = cur

print(f"index has {len(pkgs)} packages", flush=True)

# Resolve dependency closure
targets = ["python"]
seen = set()
queue = list(targets)
while queue:
    name = queue.pop(0)
    if name in seen or name not in pkgs:
        if name not in pkgs:
            print(f"  WARN missing package: {name}", flush=True)
        continue
    seen.add(name)
    p = pkgs[name]
    deps = p.get("Depends", "")
    for d in deps.split(","):
        d = d.strip()
        # strip version constraints and alternatives
        dname = re.split(r"[ |(]", d)[0].strip()
        if dname and dname not in seen:
            queue.append(dname)

print(f"need {len(seen)} packages:", flush=True)
print("  " + ", ".join(sorted(seen)), flush=True)

# Download each
s = requests.Session()
s.trust_env = True
ok, fail = [], []
for name in sorted(seen):
    p = pkgs[name]
    fn = p["Filename"]
    size = int(p.get("Size", 0))
    local = os.path.join(OUT, os.path.basename(fn))
    if os.path.exists(local) and os.path.getsize(local) == size:
        ok.append(name)
        continue
    url = BASE + fn
    try:
        r = s.get(url, timeout=(15, 60))
        if r.status_code == 200 and len(r.content) == size:
            open(local, "wb").write(r.content)
            ok.append(name)
            print(f"  OK {name} ({size//1024}KB)", flush=True)
        else:
            fail.append((name, r.status_code, len(r.content), size))
            print(f"  FAIL {name} status={r.status_code} got={len(r.content)} want={size}", flush=True)
    except Exception as e:
        fail.append((name, str(e)))
        print(f"  FAIL {name} {type(e).__name__}: {str(e)[:60]}", flush=True)

print(f"\nDownloaded {len(ok)}/{len(seen)}", flush=True)
if fail:
    print("FAILED:", fail, flush=True)
