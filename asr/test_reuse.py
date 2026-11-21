# -*- coding: utf-8 -*-
"""验证：recognizer 复用 + reset 后，第二段起是否快很多"""
import ctypes, json, sys, wave, time

LIB = "/data/local/tmp/voicebot/libvosk_android.so"
MODEL = "/data/local/tmp/voicebot/model"


def log(*a):
    print(*a); sys.stdout.flush()


lib = ctypes.CDLL(LIB)
for n, r, a in [
    ("vosk_model_new", ctypes.c_void_p, [ctypes.c_char_p]),
    ("vosk_recognizer_new", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_float]),
    ("vosk_recognizer_reset", None, [ctypes.c_void_p]),
    ("vosk_recognizer_accept_waveform", ctypes.c_int, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]),
    ("vosk_recognizer_final_result", ctypes.c_char_p, [ctypes.c_void_p]),
    ("vosk_recognizer_free", None, [ctypes.c_void_p]),
    ("vosk_model_free", None, [ctypes.c_void_p]),
]:
    f = getattr(lib, n); f.restype = r; f.argtypes = a

t0 = time.time()
model = lib.vosk_model_new(MODEL.encode())
log("model load %.2fs" % (time.time() - t0))

rec = lib.vosk_recognizer_new(model, 16000.0)
log("recognizer create %.2fs" % (time.time() - t0))

files = ["spk_a.wav", "spk_b.wav", "spk_c.wav", "spk_b.wav", "spk_a.wav"]
for i, fn in enumerate(files):
    w = wave.open("/data/local/tmp/voicebot/" + fn, "rb")
    raw = w.readframes(w.getnframes()); sr = w.getframerate(); w.close()
    dur = len(raw) / 2.0 / sr
    t0 = time.time()
    CH = 4000
    for j in range(0, len(raw), CH):
        lib.vosk_recognizer_accept_waveform(rec, raw[j:j + CH], min(CH, len(raw) - j))
    txt = json.loads(lib.vosk_recognizer_final_result(rec).decode()).get("text", "")
    dt = time.time() - t0
    log("run%d %-9s %4.2fs -> %4.2fs  RTF %.2f | %s" % (i + 1, fn, dur, dt, dt / dur, txt))
    lib.vosk_recognizer_reset(rec)

lib.vosk_recognizer_free(rec)
lib.vosk_model_free(model)
