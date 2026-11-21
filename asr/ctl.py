# -*- coding: utf-8 -*-
"""设备端小工具：用 py.sh 直接戳本地服务
用法:
  sh py.sh ctl.py health
  sh py.sh ctl.py wake 1|0
  sh py.sh ctl.py mode fish|sage
  sh py.sh ctl.py ask 一段文字
  sh py.sh ctl.py answer 一段文字        -> /api/debug/answer（造一轮完整对话，含前端播报）
  sh py.sh ctl.py selftest <wav> [raw]
  sh py.sh ctl.py replay <wav>
  sh py.sh ctl.py route 一段文字
  sh py.sh ctl.py turn [秒数]
  sh py.sh ctl.py idle [秒数]
  sh py.sh ctl.py activity
  sh py.sh ctl.py events [等几秒]
  sh py.sh ctl.py get /api/xxx
  sh py.sh ctl.py post /api/xxx '{"k":1}'
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8899"


def post(path, obj):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=300).read().decode()

def get(path):
    return urllib.request.urlopen(BASE + path, timeout=300).read().decode()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "health"
    a = sys.argv[2:]
    if cmd == "wake":
        print(post("/api/wake", {"active": a[0] == "1"}))
    elif cmd == "mode":
        print(post("/api/mode", {"mode": a[0]}))
    elif cmd == "ask":
        print(post("/api/ask", {"q": " ".join(a)}))
    elif cmd == "answer":
        print(post("/api/debug/answer", {"text": " ".join(a)}))
    elif cmd == "selftest":
        print(post("/api/selftest", {"path": a[0], "raw": (len(a) > 1 and a[1] == "raw")}))
    elif cmd == "replay":
        print(post("/api/replay", {"path": a[0]}))
    elif cmd == "route":
        print(post("/api/route", {"text": " ".join(a)}))
    elif cmd == "idle":
        print(post("/api/idle", {"sec": float(a[0]) if a else 0}))
    elif cmd == "activity":
        print(post("/api/activity", {}))
    elif cmd == "turn":
        print(post("/api/turn", {"seconds": float(a[0]) if a else 6.0}))
    elif cmd == "events":
        print(get("/api/events?wait=%s" % (a[0] if a else "3")))
    elif cmd == "get":
        print(get(a[0]))
    elif cmd == "post":
        print(post(a[0], json.loads(a[1]) if len(a) > 1 else {}))
    else:
        print(get("/health"))
