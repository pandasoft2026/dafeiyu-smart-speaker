# -*- coding: utf-8 -*-
"""在设备上测试 bionic 版 libvosk：加载 -> 建模型 -> 识别一段合成音频"""
import ctypes, json, os, sys, time

LIB = "/data/local/tmp/voicebot/libvosk_android.so"
MODEL = "/data/local/tmp/voicebot/model"


def log(*a):
    print(*a)
    sys.stdout.flush()


t0 = time.time()
lib = ctypes.CDLL(LIB)
log("[1] dlopen OK", LIB, "%.1fs" % (time.time() - t0))

lib.vosk_model_new.restype = ctypes.c_void_p
lib.vosk_model_new.argtypes = [ctypes.c_char_p]
lib.vosk_model_free.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_new.restype = ctypes.c_void_p
lib.vosk_recognizer_new.argtypes = [ctypes.c_void_p, ctypes.c_float]
lib.vosk_recognizer_free.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_accept_waveform.restype = ctypes.c_int
lib.vosk_recognizer_accept_waveform.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
lib.vosk_recognizer_result.restype = ctypes.c_char_p
lib.vosk_recognizer_result.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_partial_result.restype = ctypes.c_char_p
lib.vosk_recognizer_partial_result.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_final_result.restype = ctypes.c_char_p
lib.vosk_recognizer_final_result.argtypes = [ctypes.c_void_p]
log("[2] symbols bound OK")

t0 = time.time()
model = lib.vosk_model_new(MODEL.encode())
log("[3] vosk_model_new ->", model, "%.1fs" % (time.time() - t0))
if not model:
    log("!! model load failed")
    sys.exit(2)

rec = lib.vosk_recognizer_new(model, 16000.0)
log("[4] recognizer ->", rec)
if not rec:
    sys.exit(3)

# 用 1 秒静音走一遍管线，确认不崩
silence = b"\x00\x00" * 16000
r = lib.vosk_recognizer_accept_waveform(rec, silence, len(silence))
log("[5] accept_waveform(silence) ->", r)
log("[6] partial:", lib.vosk_recognizer_partial_result(rec))
log("[7] final:", lib.vosk_recognizer_final_result(rec))

lib.vosk_recognizer_free(rec)
lib.vosk_model_free(model)
log("[8] DONE, no crash")
