# -*- coding: utf-8 -*-
"""sherpa-onnx 流式 ASR 模型断点续传下载（在设备上运行）。

模型包 511274346 字节，设备网速约 20KB/s，需要数小时。
设计要点：
  - 1MB 分片，逐片校验长度，防止 ghproxy 返回截断数据
  - 每次成功追加后写进度文件，断电/断网后可续
  - 单次请求失败自动重试，退避
  - 无限循环直到下完（由外部 setsid 保证进程存活）

用法：sh py.sh resume_model_download.py
"""
import os
import time
import urllib.request

URL = ("https://ghproxy.net/https://github.com/k2-fsa/sherpa-onnx/releases/"
       "download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2")
OUT = "/data/local/tmp/sherpa_model.tar.bz2"
TOTAL = 511274346
STEP = 1024 * 1024


def log(*a):
    print(time.strftime("%H:%M:%S"), *a)
    import sys
    sys.stdout.flush()


have = os.path.getsize(OUT) if os.path.exists(OUT) else 0
if have > TOTAL:
    log("文件超大，截断到", TOTAL)
    with open(OUT, "r+b") as f:
        f.truncate(TOTAL)
    have = TOTAL
log("起始进度", have, "/", TOTAL)

fails = 0
while have < TOTAL:
    end = min(have + STEP, TOTAL) - 1
    want = end - have + 1
    req = urllib.request.Request(URL, headers={"Range": "bytes=%d-%d" % (have, end)})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if len(data) != want:
            log("短包", have, len(data), "期望", want, "status", getattr(r, "status", "?"))
            fails += 1
            time.sleep(min(30, 2 ** min(fails, 5)))
            continue
        with open(OUT, "r+b" if have else "wb") as f:
            f.seek(have)
            f.write(data)
        have += len(data)
        fails = 0
        if have % (10 * 1024 * 1024) < STEP:
            log("进度 %.1f%%  %d/%d" % (100.0 * have / TOTAL, have, TOTAL))
    except Exception as e:
        fails += 1
        log("重试", fails, type(e).__name__, str(e)[:70])
        time.sleep(min(30, 2 ** min(fails, 5)))

log("完成", os.path.getsize(OUT), "=", TOTAL)
