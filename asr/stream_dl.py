# -*- coding: utf-8 -*-
"""流式下载：边收边写文件，每次工具调用下载一段，可断点续传。

用法：sh py.sh stream_dl.py [目标字节数]
每次最多下载 4MB，追加到文件末尾；多次调用直到完成。
"""
import os
import sys
import urllib.request

URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/"
       "download/v2.0.1/sherpa-onnx-v2.0.1-android-armeabi-v7a-termux-shared.tar.bz2")
OUT = "/data/local/tmp/sherpa_official.tar.bz2"
TOTAL = 16141190
CHUNK = 4 * 1024 * 1024

have = os.path.getsize(OUT) if os.path.exists(OUT) else 0
if have >= TOTAL:
    print("DONE already", have)
    raise SystemExit(0)

start = have
end = min(start + CHUNK, TOTAL) - 1
req = urllib.request.Request(URL, headers={"Range": "bytes=%d-%d" % (start, end)})
print("range", start, end)
with urllib.request.urlopen(req, timeout=300) as r:
    mode = "ab" if start > 0 else "wb"
    with open(OUT, mode) as f:
        got = 0
        while True:
            b = r.read(65536)
            if not b:
                break
            f.write(b)
            got += len(b)
    print("status", r.status, "got", got, "cr", r.headers.get("Content-Range"))
now = os.path.getsize(OUT)
print("progress %d/%d (%.1f%%)" % (now, TOTAL, 100.0 * now / TOTAL))
