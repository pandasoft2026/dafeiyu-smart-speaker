# -*- coding: utf-8 -*-
"""sherpa-onnx armv7 冒烟测试：能否加载 .so 并识别一段 wav。

用法：sh py.sh test_sherpa.py [wav路径]
"""
import os
import sys
import time

BASE = "/data/local/tmp/sherpa_v7"
sys.path.insert(0, BASE)

print("=== 目录 ===")
for root, dirs, files in os.walk(BASE):
    for f in files:
        print(" ", os.path.join(root, f).replace(BASE, ""), os.path.getsize(os.path.join(root, f)))

try:
    import sherpa_onnx
    print("import OK", getattr(sherpa_onnx, "__version__", "?"))
except Exception as e:
    print("import FAIL", type(e).__name__, e)
    raise SystemExit(1)

wav = sys.argv[1] if len(sys.argv) > 1 else "/data/local/tmp/voicebot/keep_user1.wav"
model_dir = os.path.join(BASE, "model")
if not os.path.isdir(model_dir):
    print("无模型目录，跳过识别测试")
    raise SystemExit(0)

print("=== 建模 ===")
t0 = time.time()
try:
    rec = sherpa_onnx.OfflineRecognizer.from_paraformer(
        paraformer=os.path.join(model_dir, "model.onnx"),
        tokens=os.path.join(model_dir, "tokens.txt"),
        num_threads=2,
    )
except Exception as e:
    print("建识别器失败:", type(e).__name__, e)
    raise SystemExit(1)
print("加载 %.2fs" % (time.time() - t0))

import wave
import array
with wave.open(wav, "rb") as w:
    rate = w.getframerate()
    raw = w.readframes(w.getnframes())
a = array.array("f")
import struct
pcm = struct.unpack("<%dh" % (len(raw) // 2), raw[:len(raw) // 2 * 2])
samples = [v / 32768.0 for v in pcm]

t0 = time.time()
s = rec.create_stream()
s.accept_waveform(rate, samples)
rec.decode_stream(s)
dt = time.time() - t0
print("识别 %.2fs -> %r" % (dt, s.result.text))
