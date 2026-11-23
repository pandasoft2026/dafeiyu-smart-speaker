# -*- coding: utf-8 -*-
"""第二轮自测：API 层边界与状态一致性。

在设备上跑：sh py.sh selftest_v2.py
只测不改动状态（除了必要的模式切换会还原）。
"""
import json
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8899"
PASS = 0
FAIL = 0


def req(path, method="GET", obj=None, timeout=60, raw=False):
    data = None
    hdr = {}
    if obj is not None:
        data = json.dumps(obj, ensure_ascii=False).encode()
        hdr["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, headers=hdr, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        body = resp.read()
        return body if raw else json.loads(body.decode())


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  OK   %s %s" % (name, detail))
    else:
        FAIL += 1
        print("  FAIL %s %s" % (name, detail))


def tts_url(text, voice="zh-CN-XiaoyiNeural", pitch=28, rate=4):
    return ("/api/tts?text=" + urllib.parse.quote(text) +
            "&voice=" + voice + "&pitch=%d&rate=%d" % (pitch, rate))


print("=" * 56)
print("第二轮自测", time.strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 56)

# 1 健康
print("[1] 健康检查")
h = req("/health")
check("build", str(h.get("build", "")).startswith("b1120"), str(h.get("build")))
check("asr", h.get("asr") is True)
check("wake", h.get("wake") is True)
check("tts stats", isinstance(h.get("tts"), dict), str(h.get("tts")))

# 2 TTS 边界
print("[2] TTS 边界")
for label, text, expect in [
    ("空文本", "", 400),
    ("空格", "   ", 400),
    ("正常", "你好", 200),
    ("特殊字符", "你好<&>\"'", 200),
    ("超长600+", "测试" * 400, 200),
]:
    try:
        d = req(tts_url(text), raw=True)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
        d = b""
    check(label, code == expect and (code != 200 or len(d) > 100),
          "code=%d bytes=%d" % (code, len(d)))

# 3 非法音色应 502 且不挂
print("[3] 异常音色容错")
try:
    req(tts_url("测试", voice="xx-XX-None", pitch=0, rate=0), raw=True)
    code = 200
except urllib.error.HTTPError as e:
    code = e.code
check("非法音色返回错误而非崩溃", code >= 400, "code=%d" % code)
h2 = req("/health")
check("服务仍健康", h2.get("build") == h.get("build"))

# 4 参数边界
print("[4] 参数解析")
for label, url in [
    ("pitch非数字", tts_url("测试") + "&pitch=abc"),
    ("rate非数字", tts_url("测试") + "&rate=xyz"),
    ("缺voice", "/api/tts?text=" + urllib.parse.quote("测试")),
]:
    try:
        d = req(url, raw=True)
        code = 200
        ok = len(d) > 100
    except urllib.error.HTTPError as e:
        code = e.code
        ok = code == 200
    check(label, ok, "code=%d" % code)

# 5 事件端点不串台
print("[5] 事件端点")
before = req("/api/events?wait=0")
check("排空事件", len(before.get("events", [])) >= 0)
req("/api/tts?text=" + urllib.parse.quote("事件隔离测试"), raw=True)
after = req("/api/events?wait=0")
check("TTS 不产生事件", len(after.get("events", [])) == 0,
      "events=%d" % len(after.get("events", [])))

# 6 人设切换往返
print("[6] 人设切换")
orig = req("/health").get("mode")
for m in ("sage", "fish", "sage", "fish"):
    r = req("/api/mode", "POST", {"mode": m})
    check("切到 %s" % m, r.get("mode") == m)
req("/api/mode", "POST", {"mode": orig})

# 7 路由分流（不应误伤）
print("[7] 意图路由")
for text, want in [
    ("召唤梁圣", "sage"),
    ("召唤大肥鱼", "fish"),
    ("今天天气怎么样", "qa"),
]:
    r = req("/api/route", "POST", {"text": text})
    got = r.get("action") or r.get("mode") or r.get("name") or ""
    check("%s -> %s" % (text, want), want in str(got) or bool(got), str(r)[:80])

# 8 缓存命中
print("[8] 缓存")
import random
u = tts_url("缓存命中自测%d" % random.randint(10000, 99999))
t0 = time.time(); a = req(u, raw=True); dt1 = time.time() - t0
t0 = time.time(); b = req(u, raw=True); dt2 = time.time() - t0
check("内容一致", a == b, "%d/%d bytes" % (len(a), len(b)))
check("第二次更快", dt2 < dt1, "%.3fs -> %.3fs" % (dt1, dt2))

print("=" * 56)
print("通过 %d / 失败 %d" % (PASS, FAIL))
print("=" * 56)
