# -*- coding: utf-8 -*-
"""验证 tinycap 是否边录边写（文件实时增长），以决定能否做"说完即停" """
import os, subprocess, time, sys

BASE = "/data/local/tmp/voicebot"
P = BASE + "/probe.wav"


def log(*a):
    print(*a); sys.stdout.flush()


if os.path.exists(P):
    os.remove(P)

proc = subprocess.Popen(["/vendor/bin/tinycap", P, "-D", "0", "-d", "2", "-c", "4",
                         "-r", "16000", "-b", "16", "-T", "5"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.time()
last = -1
for i in range(22):
    time.sleep(0.25)
    try:
        sz = os.path.getsize(P)
    except Exception:
        sz = -1
    log("%5.2fs size=%d delta=%d" % (time.time() - t0, sz, sz - last if last >= 0 else 0))
    last = sz
proc.wait()
log("done size", os.path.getsize(P))
