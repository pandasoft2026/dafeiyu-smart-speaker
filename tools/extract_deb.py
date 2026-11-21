# -*- coding: utf-8 -*-
"""Extract libatomic.so.1 from a .deb (ar archive containing data.tar.xz)."""
import os, io, tarfile, lzma, gzip

deb = r"D:\workbuddy\2026-11-19-10-59-25\tools\libatomic.deb"
outdir = r"D:\workbuddy\2026-11-19-10-59-25\tools\libatomic_out"
os.makedirs(outdir, exist_ok=True)

data = open(deb, "rb").read()
assert data[:8] == b"!<arch>\n", "not ar"
pos = 8
members = {}
while pos < len(data):
    header = data[pos:pos+60]
    if len(header) < 60: break
    name = header[0:16].decode().strip().rstrip("/")
    size = int(header[48:58].decode().strip())
    content = data[pos+60:pos+60+size]
    members[name] = content
    pos += 60 + size
    if size % 2: pos += 1

print("members:", list(members.keys()))
data_name = [k for k in members if k.startswith("data.tar")]
print("data member:", data_name)
raw = members[data_name[0]]

# decompress based on extension
if data_name[0].endswith(".xz"):
    raw = lzma.decompress(raw)
elif data_name[0].endswith(".gz"):
    raw = gzip.decompress(raw)

t = tarfile.open(fileobj=io.BytesIO(raw))
for m in t.getmembers():
    print("  ", m.name)
    if "libatomic.so" in m.name:
        f = t.extractfile(m)
        outname = os.path.join(outdir, os.path.basename(m.name))
        # handle symlinks
        if m.issym() or m.islnk():
            print("   (symlink ->", m.linkname, ")")
            continue
        open(outname, "wb").write(f.read())
        print("   EXTRACTED:", outname, os.path.getsize(outname))
