# -*- coding: utf-8 -*-
"""离线验证唤醒/切换判定逻辑（不碰设备）"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("svc", os.path.join(HERE, "service.py"))
svc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(svc)

CASES = [
    # (识别到的文本, 初始模式, 期望: wake / sage / fish / none)
    ("肥鱼肥鱼", "fish", "wake"),
    ("肥肥鱼", "fish", "wake"),
    ("你好肥鱼", "fish", "wake"),
    ("肥育", "fish", "wake"),
    ("肥鱼肥鱼今天天气怎么样", "fish", "wake+q"),
    ("肥鱼肥鱼，今天天气怎么样", "fish", "wake+q"),
    ("召唤梁圣", "fish", "sage"),
    ("就会两胜", "fish", "sage"),
    ("召唤两胜", "fish", "sage"),
    ("梁圣梁圣", "fish", "sage"),
    ("你好梁圣", "fish", "sage"),
    ("梁圣", "fish", "sage"),
    ("梁圣是谁", "fish", "wake"),
    ("召唤大肥鱼", "sage", "fish"),
    ("肥鱼肥鱼", "sage", "fish"),
    ("你好梁圣", "sage", "wake"),
    ("梁圣你觉得呢", "sage", "wake+q"),
    # 唤醒词前面混进来的残渣不能当成问题（15:57 真实踩过的坑）
    ("哪一本与肥育肥鱼", "fish", "wake"),
    ("这个东西怎么样肥鱼肥鱼", "fish", "wake"),
    ("今天吃鱼", "fish", "none"),
    ("两个学生", "fish", "none"),
    ("这个方案怎么样", "fish", "none"),
]

ok = fail = 0
for text, init, want in CASES:
    svc.STATE["mode"] = init
    svc.EVENTS.clear()
    hit = svc.handle_wake_text(text)
    mode = svc.STATE["mode"]
    evs = list(svc.EVENTS)
    if not hit:
        got = "none"
    elif mode != init:
        got = mode
    else:
        got = "wake+q" if any(e.get("q") for e in evs) else "wake"
    flag = "OK " if got == want else "XX "
    if got == want:
        ok += 1
    else:
        fail += 1
    print("%s %-24s [%s] -> %-8s 期望 %-8s events=%s"
          % (flag, text, init, got, want, evs))

print("\n通过 %d / %d" % (ok, ok + fail))
