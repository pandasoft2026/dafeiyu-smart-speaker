# -*- coding: utf-8 -*-
"""对话链路延迟剖析：ASR / LLM首句 / TTS 各自耗时，多次取分布。"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8899"


def post(path, body, timeout=40):
    rq = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=timeout).read().decode())


print("=== LLM 首句延迟（5 轮，warm）===")
for q in ("今天天气怎么样", "你是谁", "1加1", "讲个笑话", "现在几点"):
    t0 = time.time()
    d = post("/api/ask", {"text": q})
    dt = time.time() - t0
    print("  %-10s %.2fs  %s" % (q, dt, d.get("answer", "")[:24]))

print("=== TTS 延迟（首轮冷 + 3 轮热）===")
for i, text in enumerate(("好的呀", "好的呀", "今天成都13度多云", "今天成都13度多云")):
    t0 = time.time()
    try:
        u = BASE + "/api/tts?text=" + urllib.request.quote(text) + "&pitch=28&rate=4"
        data = urllib.request.urlopen(u, timeout=30).read()
        print("  [%d] %-12s %.2fs %d bytes" % (i, text, time.time() - t0, len(data)))
    except Exception as e:
        print("  [%d] %-12s FAIL %s" % (i, text, type(e).__name__))
