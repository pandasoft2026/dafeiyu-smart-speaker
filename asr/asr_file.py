# -*- coding: utf-8 -*-
"""设备端：识别指定的 16k 单声道 wav 列表，输出文本与耗时"""
import ctypes, json, sys, wave, time, glob

LIB = "/data/local/tmp/voicebot/libvosk_android.so"
MODEL = "/data/local/tmp/voicebot/model"
SR = 16000


def log(*a):
    print(*a); sys.stdout.flush()


lib = ctypes.CDLL(LIB)
lib.vosk_model_new.restype = ctypes.c_void_p
lib.vosk_model_new.argtypes = [ctypes.c_char_p]
lib.vosk_recognizer_new.restype = ctypes.c_void_p
lib.vosk_recognizer_new.argtypes = [ctypes.c_void_p, ctypes.c_float]
lib.vosk_recognizer_accept_waveform.restype = ctypes.c_int
lib.vosk_recognizer_accept_waveform.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
lib.vosk_recognizer_final_result.restype = ctypes.c_char_p
lib.vosk_recognizer_final_result.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_partial_result.restype = ctypes.c_char_p
lib.vosk_recognizer_partial_result.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_free.argtypes = [ctypes.c_void_p]
lib.vosk_model_free.argtypes = [ctypes.c_void_p]

t0 = time.time()
model = lib.vosk_model_new(MODEL.encode())
log("model %.1fs" % (time.time() - t0))

files = sys.argv[1:] or sorted(glob.glob("/data/local/tmp/voicebot/spk_*.wav"))
for f in files:
    w = wave.open(f, "rb")
    nch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    rec = lib.vosk_recognizer_new(model, float(sr))
    t0 = time.time()
    CH = 4000
    for i in range(0, len(raw), CH):
        lib.vosk_recognizer_accept_waveform(rec, raw[i:i + CH], min(CH, len(raw) - i))
    res = json.loads(lib.vosk_recognizer_final_result(rec).decode())
    dt = time.time() - t0
    dur = n / float(sr)
    log("%-14s %4.2fs audio -> %4.2fs | %s" % (f.split("/")[-1], dur, dt, res.get("text", "")))
    lib.vosk_recognizer_free(rec)

lib.vosk_model_free(model)
