# -*- coding: utf-8 -*-
"""验证新的 min_after_voice 判停逻辑：回放录音，对比新旧切点。

新逻辑：voice_t0 之后 silence 秒 + 至少 min_after_voice 秒即可停；
        旧逻辑：从录音开始至少 min_sec 秒才允许停。
"""
import array
import sys
import wave

SR = 16000
POLL = 0.12
THRESH = 700


def peaks(path):
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    a = array.array("h")
    a.frombytes(raw[:len(raw) // 2 * 2])
    ch = a[0::nch]
    win = int(rate * POLL)
    out = []
    for i in range(0, len(ch), win):
        b = ch[i:i + win]
        out.append((i / rate, max((abs(v) for v in b), default=0)))
    return out


def cut_old(pk, min_sec=2.2, silence=0.9):
    started = False
    lv = 0.0
    for t, p in pk:
        if p > THRESH:
            started = True
            lv = t
        elif started and (t - lv) > silence and t > min_sec:
            return t, None
    return (pk[-1][0] if pk else 0.0), None


def cut_new(pk, min_sec=2.2, silence=0.45, min_after=0.5):
    started = False
    v0 = None
    lv = 0.0
    for t, p in pk:
        if p > THRESH:
            if not started:
                v0 = t
            started = True
            lv = t
        elif started:
            quiet = (t - lv) > silence
            long_enough = ((v0 is not None and t - v0 > min_after) or t > min_sec)
            if quiet and long_enough:
                return t, v0
    return (pk[-1][0] if pk else 0.0), v0


def tail(pk, cut, sec=0.5):
    return sum(1 for t, p in pk if cut <= t < cut + sec and p > THRESH)


for path in sys.argv[1:]:
    try:
        pk = peaks(path)
    except Exception as e:
        print(path, "ERR", e)
        continue
    old, _ = cut_old(pk)
    new, v0 = cut_new(pk)
    print("\n%s  时长%.2fs  首个字%.2fs" % (path.split("/")[-1].split("\\")[-1], pk[-1][0], v0 or 0))
    print("  旧逻辑(2.2/0.9): 切%.2fs" % old)
    print("  新逻辑(0.5/0.45): 切%.2fs  提前%.2fs  切后0.5s有声块%d"
          % (new, old - new, tail(pk, new)))
