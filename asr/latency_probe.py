# -*- coding: utf-8 -*-
"""延迟基线测量：走真实 /api/turn 和 /api/tts，记录各段时间。

用法（设备上）：sh py.sh latency_probe.py "你叫什么名字"
"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8899"


def post(path, obj, timeout=90):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(obj, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return body, time.time() - t0


def get_raw(path, timeout=60):
    t0 = time.time()
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        if r.status != 200:
            return b"", time.time() - t0
        body = r.read()
    return body, time.time() - t0


q = " ".join(sys.argv[1:]) or "你叫什么名字"
print("问题:", q)

# 1) 直接问 DeepSeek，测纯模型延迟
body, dt_ask = post("/api/ask", {"text": q})
ans = json.loads(body.decode()).get("answer", "")
print("DeepSeek 全文: %.2fs  %d 字" % (dt_ask, len(ans)))
print("  回答:", ans[:60])

# 2) 合成全文（这次是缓存 miss）
import urllib.parse
url = "/api/tts?text=" + urllib.parse.quote(ans) + \
      "&voice=zh-CN-XiaoyiNeural&pitch=28&rate=4"
mp3, dt_tts_miss = get_raw(url)
print("TTS 首次:      %.2fs  %d 字节" % (dt_tts_miss, len(mp3)))

# 3) 同句再合成，测缓存
mp3, dt_tts_hit = get_raw(url)
print("TTS 缓存:      %.2fs  %d 字节" % (dt_tts_hit, len(mp3)))

# 4) 统计
print("-" * 40)
print("串行基线（模型 + 合成）: %.2fs" % (dt_ask + dt_tts_miss))
print("目标：首句流式 ≤1.5s；当前首声约 2.7s（实测）")
