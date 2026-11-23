# -*- coding: utf-8 -*-
"""回放一段录音，逐块打印 Vosk partial，看能否用语义完整度辅助端点判断。

用法：sh py.sh replay_partial.py <wav>
"""
import sys
import time
import wave

sys.path.insert(0, "/data/local/tmp/voicebot")
import service as S

path = sys.argv[1] if len(sys.argv) > 1 else "/data/local/tmp/voicebot/keep_user1.wav"
S.init_asr()
with wave.open(path, "rb") as w:
    nch = w.getnchannels()
    rate = w.getframerate()
    raw = w.readframes(w.getnframes())
import array
a = array.array("h")
a.frombytes(raw[:len(raw) // 2 * 2])
mono = a[0::nch]

lib = S._asr["lib"]
rec = lib.vosk_recognizer_new(S._asr["model"], float(rate))
win = int(rate * 0.24)
t0 = time.time()
for i in range(0, len(mono), win):
    block = mono[i:i + win]
    if len(block) < 8:
        break
    lib.vosk_recognizer_accept_waveform(rec, block.tobytes(), len(block) * 2)
    pk = max((abs(v) for v in block), default=0)
    part = lib.vosk_recognizer_partial_result(rec).decode("utf-8", "replace")
    try:
        part = __import__("json").loads(part).get("partial", "")
    except Exception:
        pass
    print("%.2fs pk=%4d partial=%s" % (i / rate, pk, part))
lib.vosk_recognizer_free(rec)
