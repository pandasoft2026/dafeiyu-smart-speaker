# -*- coding: utf-8 -*-
"""端到端自测：本机播放中文语音 -> 服务录音识别 -> DeepSeek 回答"""
import json, subprocess, sys, time, urllib.request

BASE = "http://127.0.0.1:8899"


def post(path, obj, timeout=90):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def log(*a):
    print(*a); sys.stdout.flush()


# 1. 后台播放一段中文语音，同时立刻开始录音
log("[1] 播放测试语音 spk_a.wav 并录音 ...")
subprocess.Popen(["/vendor/bin/tinyplay", "/data/local/tmp/voicebot/spk_a.wav", "-D", "0", "-d", "0"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.time()
r = post("/api/listen", {"seconds": 5})
log("    listen ->", json.dumps(r, ensure_ascii=False), "%.1fs" % (time.time() - t0))

if not r.get("text"):
    log("!! 没识别到内容，可能音量太小或没播出来")
    sys.exit(1)

# 2. 交给 DeepSeek
log("[2] 调用 DeepSeek ...")
t0 = time.time()
a = post("/api/ask", {"text": r["text"]})
log("    answer ->", a.get("answer"), "%.1fs" % (time.time() - t0))
