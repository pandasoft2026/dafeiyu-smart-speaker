# -*- coding: utf-8 -*-
"""离线模拟 _record_once 的判停逻辑，对比不同 silence 的切点。

用法：python sim_endpoint.py <wav路径> [wav2 ...]
判停逻辑与服务一致：每 0.12s 轮询、ch0 峰值>700 更新 last_voice、
静音超过 silence 且超过 min_sec 就停。
"""
import array
import sys
import wave

SR = 16000
THRESH = 700
POLL = 0.12
MIN_SEC = 1.0


def peaks(path):
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    a = array.array("h")
    a.frombytes(raw[:len(raw) // 2 * 2])
    # 服务只取 ch0（arr[0::4]），这里按实际通道数取
    ch = a[0::nch]
    # 按 0.12s 窗口分块，取每块峰值
    win = int(rate * POLL)
    out = []
    for i in range(0, len(ch), win):
        block = ch[i:i + win]
        out.append((i / rate, max((abs(v) for v in block), default=0)))
    return out, len(ch) / rate


def cut_at(pk, silence, min_sec=MIN_SEC):
    started = False
    last_voice = 0.0
    for t, p in pk:
        if p > THRESH:
            started = True
            last_voice = t
        elif started and (t - last_voice) > silence and t > min_sec:
            return t
    return pk[-1][0] if pk else 0.0


def tail_energy(pk, cut, seconds=0.5):
    """切点之后 seconds 秒内还有多少峰值超阈值的块 —— 用来判断切早了没。"""
    hits = 0
    total = 0
    for t, p in pk:
        if cut <= t < cut + seconds:
            total += 1
            if p > THRESH:
                hits += 1
    return hits, total


for path in sys.argv[1:]:
    try:
        pk, dur = peaks(path)
    except Exception as e:
        print("%s: 读取失败 %s" % (path, e))
        continue
    base = cut_at(pk, 2.0)          # 大阈值当"说完"基准
    print("\n%s  时长%.2fs  基准切点%.2fs  块数%d" % (path.split("/")[-1], dur, base, len(pk)))
    for s in (0.62, 0.45, 0.35, 0.30, 0.25):
        c = cut_at(pk, s)
        hits, total = tail_energy(pk, c, 0.5)
        print("  silence=%.2f  切点%.2fs  早%.2fs  后续0.5s有声块 %d/%d %s"
              % (s, c, base - c, hits, total,
                 "<<< 危险" if hits >= 2 else ""))
