# -*- coding: utf-8 -*-
"""回放对比：单阈值 0.45s vs 双阈值判停，看能否更快且不误切。

用法：python sim_dual.py <wav...>
"""
import array
import sys
import wave

SR = 16000
POLL = 0.12
HI = 700
LO = 280
MIN_SEC = 1.0


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


def cut_single(pk, silence, thresh=HI):
    started = False
    lv = 0.0
    for t, p in pk:
        if p > thresh:
            started = True
            lv = t
        elif started and (t - lv) > silence and t > MIN_SEC:
            return t
    return pk[-1][0] if pk else 0.0


def cut_dual(pk, hi_silence, lo_silence, hi=HI, lo=LO):
    """双阈值：高声重置高计数，低声只重置低计数；两个都超才停。"""
    started = False
    last_hi = 0.0
    last_lo = 0.0
    for t, p in pk:
        if p > hi:
            started = True
            last_hi = t
            last_lo = t
        elif p > lo:
            started = True
            last_lo = t
        elif started and (t - last_hi) > hi_silence and (t - last_lo) > lo_silence \
                and t > MIN_SEC:
            return t
    return pk[-1][0] if pk else 0.0


def tail(pk, cut, thresh=HI, sec=0.5):
    hits = tot = 0
    for t, p in pk:
        if cut <= t < cut + sec:
            tot += 1
            if p > thresh:
                hits += 1
    return hits, tot


for path in sys.argv[1:]:
    try:
        pk = peaks(path)
    except Exception as e:
        print(path, "ERR", e)
        continue
    base = cut_single(pk, 2.0)
    print("\n%s 基准%.2fs" % (path.split("\\")[-1].split("/")[-1], base))
    c1 = cut_single(pk, 0.45)
    h, t = tail(pk, c1)
    print("  单阈值0.45    切%.2fs 早%.2fs 后续有声%d/%d" % (c1, base - c1, h, t))
    for hs, ls in [(0.30, 0.45), (0.25, 0.40), (0.35, 0.50)]:
        c = cut_dual(pk, hs, ls)
        h, t = tail(pk, c)
        flag = " <<<误切" if h >= 2 else ""
        print("  双阈值%.2f/%.2f 切%.2fs 早%.2fs 后续有声%d/%d%s"
              % (hs, ls, c, base - c, h, t, flag))
