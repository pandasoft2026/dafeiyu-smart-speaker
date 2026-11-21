# -*- coding: utf-8 -*-
"""诊断：把 wake_stream.wav 的最后 N 秒四个通道分别识别一遍，看电平和文本"""
import ctypes, json, sys, array, os

LIB = "/data/local/tmp/voicebot/libvosk_android.so"
MODEL = "/data/local/tmp/voicebot/model"
WAV = "/data/local/tmp/voicebot/wake_stream.wav"
SR = 16000
SEC = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
WAV = sys.argv[2] if len(sys.argv) > 2 else WAV

lib = ctypes.CDLL(LIB)
for name, res, args in [
    ("vosk_model_new", ctypes.c_void_p, [ctypes.c_char_p]),
    ("vosk_recognizer_new", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_float]),
    ("vosk_recognizer_accept_waveform", ctypes.c_int, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]),
    ("vosk_recognizer_final_result", ctypes.c_char_p, [ctypes.c_void_p]),
    ("vosk_recognizer_free", None, [ctypes.c_void_p]),
    ("vosk_model_free", None, [ctypes.c_void_p]),
]:
    f = getattr(lib, name)
    f.restype = res
    f.argtypes = args

d = open(WAV, "rb").read()
i = d.find(b"data")
pcm = d[i + 8:] if i >= 0 else d[44:]
n = len(pcm) - (len(pcm) % 8)
pcm = pcm[-int(SR * 8 * SEC):][: (int(SR * 8 * SEC)) // 8 * 8]
print("file %.1f MB, 取尾部 %.1f 秒" % (len(d) / 1048576.0, len(pcm) / float(SR * 8)))

a = array.array("h")
a.frombytes(pcm)

print("--- 各通道电平和识别结果 ---")
model = lib.vosk_model_new(MODEL.encode())
for ch in range(4):
    mono = a[ch::4]
    peak = max((abs(v) for v in mono), default=0)
    s = 0
    for v in mono:
        s += v * v
    rms = (s / max(1, len(mono))) ** 0.5
    rec = lib.vosk_recognizer_new(model, float(SR))
    raw = mono.tobytes()
    CH = 4000
    for k in range(0, len(raw), CH):
        lib.vosk_recognizer_accept_waveform(rec, raw[k:k + CH], min(CH, len(raw) - k))
    txt = json.loads(lib.vosk_recognizer_final_result(rec).decode()).get("text", "")
    lib.vosk_recognizer_free(rec)
    print("ch%d  peak=%6d rms=%7.1f  %r" % (ch, peak, rms, txt))
lib.vosk_model_free(model)
