# -*- coding: utf-8 -*-
"""PC 喇叭 → 设备麦克风 回环验证。
winsound 播放唤醒词 wav，同时设备 tinycap 录音，分析峰值确认设备能"听到"PC。
"""
import array
import subprocess
import sys
import threading
import time
import wave

import winsound

ADB = r"D:\workbuddy\2026-11-19-10-59-25\tools\platform-tools\adb.exe"
WAV = sys.argv[1] if len(sys.argv) > 1 else "wake_fish.wav"
DEV_WAV = "/data/local/tmp/loopcheck.wav"


def adb(args):
    r = subprocess.run([ADB] + args, capture_output=True, text=True)
    return r.stdout.strip() + r.stderr.strip()


def record(sec=4):
    adb(["shell", "su -c 'rm -f %s; /vendor/bin/tinycap %s -D 0 -d 2 -c 4 -r 16000 -b 16 -T %d'" %
         (DEV_WAV, DEV_WAV, sec + 1)])
    adb(["pull", DEV_WAV, "loopcheck.wav"])


def peak(path):
    with wave.open(path, "rb") as w:
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
    nch = w.getnchannels()
    # 4 通道混合取最大
    vals = [max((abs(v) for v in a[c::nch]), default=0) for c in range(nch)]
    return max(vals), sum(vals) / len(vals)


adb(["connect", "192.168.137.254:5555"])
time.sleep(1)
print("设备:", adb(["devices"]))

print("=== 基线：不播放时设备录音 2s ===")
record(2)
print("  峰值/均值:", peak("loopcheck.wav"))

print("=== PC 播放 %s，同时设备录音 ===" % WAV)
t = threading.Thread(target=lambda: winsound.PlaySound(WAV, winsound.SND_FILENAME))
t.start()
time.sleep(0.15)          # 等播放开始
record(4)
t.join()
print("  峰值/均值:", peak("loopcheck.wav"))
