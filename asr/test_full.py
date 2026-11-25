# -*- coding: utf-8 -*-
"""综合回归测试（真实 API 入口），不依赖出声。
用法：sh py.sh test_full.py
"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8899"
ok = fail = 0


def req(path, body=None, timeout=25):
    if body is None:
        r = urllib.request.urlopen(BASE + path, timeout=timeout)
    else:
        data = json.dumps(body).encode()
        rq = urllib.request.Request(BASE + path, data=data,
                                    headers={"Content-Type": "application/json"})
        r = urllib.request.urlopen(rq, timeout=timeout)
    return json.loads(r.read().decode())


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  OK   %s %s" % (name, detail))
    else:
        fail += 1
        print("  FAIL %s %s" % (name, detail))


print("=== 1. 健康与状态 ===")
h = req("/health")
check("服务健康", h.get("ok") and h.get("asr"))
check("默认字段齐", all(k in h for k in ("mode", "wake", "busy", "build")))
print("  build=%s mode=%s wake=%s" % (h["build"], h["mode"], h["wake"]))

print("=== 2. 唤醒分流（严格白名单）===")
cases = [
    ("肥鱼肥鱼", "ask"), ("肥鱼肥鱼今天天气", "ask"),
    ("你好梁圣", "ask"), ("梁圣梁圣几点了", "ask"),
    ("你大肥鱼", "reject"), ("大肥鱼", "reject"),
    ("到后面你的意思是", "reject"),
    ("召唤梁圣", "mode"), ("切换大肥鱼", "mode"),
]
for text, want in cases:
    r = req("/api/route", {"text": text})
    check("route %s" % text, r.get("action") == want, "→%s" % r.get("action"))

print("=== 3. 问答（含天气上下文）===")
for q in ("你好", "今天天气怎么样", "1加1等于几"):
    r = req("/api/ask", {"text": q})
    a = r.get("answer", "")
    check("ask %s" % q, len(a) > 3, "→%s" % a[:30])

print("=== 4. 人设切换 ===")
orig = "fish"
req("/api/mode", {"mode": orig})
for mode in ("sage", "fish"):
    r = req("/api/mode", {"mode": mode})
    check("切到 %s" % mode, r.get("mode") == mode)
    a = req("/api/ask", {"text": "你是谁"}).get("answer", "")
    check("%s 人设生效" % mode, ("梁圣" in a) if mode == "sage" else ("大肥鱼" in a or "小鲸鱼" in a), a[:20])
req("/api/mode", {"mode": orig})

print("=== 5. 统计与行情 ===")
s = req("/api/stats")
check("token 字段", "usage" in s and "calls" in s["usage"])
check("余额字段", "balance" in s)
check("GitHub star", "github" in s and "stars" in s["github"],
      "★%s" % s.get("github", {}).get("stars", {}).get("count"))
d = req("/api/dashboard")
items = d.get("market") or []
check("行情项数", len(items) >= 10, "%d项" % len(items))
check("天气五天", len((d.get("weather") or {}).get("days") or []) == 5)
no_fake = all(x.get("price") is not None for x in items if x.get("name") != "韩KOSPI")
check("无编造数据", no_fake)

print("=== 6. TTS ===")
try:
    u = BASE + "/api/tts?text=" + urllib.request.quote("测试") + "&pitch=28&rate=4"
    mp3 = urllib.request.urlopen(u, timeout=25).read()
    check("TTS", mp3[:2] == b"\xff\xfb" or mp3[:2] == b"\xff\xf3", "%d bytes" % len(mp3))
except Exception as e:
    check("TTS", False, type(e).__name__)

print("\n" + "=" * 48)
print("通过 %d / 失败 %d" % (ok, fail))
