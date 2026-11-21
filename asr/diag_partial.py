# -*- coding: utf-8 -*-
"""诊断：分片喂音频，逐步打印 partial_result，看流式识别是否真的出字"""
import ctypes, json, array, sys

LIB = "/data/local/tmp/voicebot/libvosk_android.so"
MODEL = "/data/local/tmp/voicebot/model"
WAV = "/data/local/tmp/voicebot/wake_stream.wav"
SR = 16000
SEC = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
GAIN = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
WAV = sys.argv[3] if len(sys.argv) > 3 else WAV

lib = ctypes.CDLL(LIB)
for name, res, args in [
    ("vosk_model_new", ctypes.c_void_p, [ctypes.c_char_p]),
    ("vosk_recognizer_new", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_float]),
    ("vosk_recognizer_accept_waveform", ctypes.c_int, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]),
    ("vosk_recognizer_final_result", ctypes.c_char_p, [ctypes.c_void_p]),
    ("vosk_recognizer_partial_result", ctypes.c_char_p, [ctypes.c_void_p]),
    ("vosk_recognizer_result", ctypes.c_char_p, [ctypes.c_void_p]),
    ("vosk_recognizer_reset", None, [ctypes.c_void_p]),
    ("vosk_recognizer_free", None, [ctypes.c_void_p]),
    ("vosk_model_free", None, [ctypes.c_void_p]),
]:
    f = getattr(lib, name); f.restype = res; f.argtypes = args

d = open(WAV, "rb").read()
i = d.find(b"data")
pcm = d[i + 8:] if i >= 0 else d[44:]
take = int(SR * 8 * SEC)
pcm = pcm[-take:][: (take // 8) * 8]

a = array.array("h")
a.frombytes(pcm)
mono = a[0::4]
pk = max((abs(v) for v in mono), default=0)
print("取 %.0f 秒，ch0 peak=%d，放大 %.1f 倍" % (SEC, pk, GAIN))

model = lib.vosk_model_new(MODEL.encode())
rec = lib.vosk_recognizer_new(model, float(SR))
try:
    lib.vosk_recognizer_set_partial_words.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.vosk_recognizer_set_partial_words(rec, 1)
    lib.vosk_recognizer_set_words.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.vosk_recognizer_set_words(rec, 1)
    print("已开启 set_partial_words / set_words")
except AttributeError as e:
    print("接口不可用:", e)

g = int(GAIN * 256)
scaled = array.array("h", (max(-32768, min(32767, (v * g) >> 8)) for v in mono))
raw = scaled.tobytes()

CH = 2400 * 2
last = ""
step = 0
for k in range(0, len(raw), CH):
    step += 1
    chunk = raw[k:k + CH]
    lib.vosk_recognizer_accept_waveform(rec, chunk, len(chunk))
    praw = lib.vosk_recognizer_partial_result(rec).decode()
    rraw = lib.vosk_recognizer_result(rec).decode()
    if step % 5 == 0:
        print("  第%2d片 t=%.1fs partial=%s result=%s"
              % (step, (k + len(chunk)) / 32000.0, praw[:60], rraw[:60]))
    p = json.loads(praw).get("text", "")
    if p != last:
        print("  >> partial 变化 %r" % (p,))
        last = p
print("final =", json.loads(lib.vosk_recognizer_final_result(rec).decode()).get("text", ""))
lib.vosk_recognizer_free(rec)
lib.vosk_model_free(model)
