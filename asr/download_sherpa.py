# -*- coding: utf-8 -*-
"""从镜像完整下载 sherpa armv7 包，流式写盘，断线自动重试。"""
import os
import time
import urllib.request

URL = ("https://ghproxy.net/https://github.com/k2-fsa/sherpa-onnx/releases/"
       "download/v2.0.1/sherpa-onnx-v2.0.1-android-armeabi-v7a-termux-shared.tar.bz2")
OUT = "/data/local/tmp/sherpa_v7.tar.bz2"
TOTAL = 16141190
STEP = 1024 * 1024          # 每次请求 1MB，小片更不容易断


def log(*a):
    print(*a)
    import sys
    sys.stdout.flush()


# 从头下，避免旧文件错位
with open(OUT, "wb") as f:
    pass

have = 0
tries = 0
while have < TOTAL and tries < 40:
    end = min(have + STEP, TOTAL) - 1
    want = end - have + 1
    req = urllib.request.Request(URL, headers={"Range": "bytes=%d-%d" % (have, end)})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
        if len(data) != want:
            log("short", have, len(data), want, "status", r.status)
            tries += 1
            time.sleep(1)
            continue
        with open(OUT, "r+b") as f:
            f.seek(have)
            f.write(data)
        have += len(data)
        log("ok %d/%d" % (have, TOTAL))
        tries = 0
    except Exception as e:
        log("retry", have, type(e).__name__, str(e)[:60])
        tries += 1
        time.sleep(2)

log("FINAL", os.path.getsize(OUT), "expect", TOTAL)
