# -*- coding: utf-8 -*-
"""设备端：4 声道录音 -> 抽 ch0 -> 单声道 16k -> Vosk 识别"""
import ctypes, json, sys, wave, array, time

LIB = "/data/local/tmp/voicebot/libvosk_android.so"
MODEL = "/data/local/tmp/voicebot/model"
SRC = "/data/local/tmp/voicebot/rec4.wav"
OUT = "/data/local/tmp/voicebot/rec_mono.wav"


def log(*a):
    print(*a); sys.stdout.flush()


# ---- 抽道 ----
w = wave.open(SRC, "rb")
nch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
data = w.readframes(n)
w.close()
log("src", nch, "ch", sr, "Hz", n, "frames", sw * 8, "bit")

pcm = array.array("h")
pcm.frombytes(data)
mono = pcm[0::nch]
log("mono samples", len(mono))

# 音量统计（判断有没有人说话）
peak = max(abs(v) for v in mono) if len(mono) else 0
rms = (sum(v * v for v in mono[::16]) / max(1, len(mono[::16]))) ** 0.5
log("peak", peak, "rms", int(rms), "->", "有声音" if peak > 1200 else "近乎静音")

with wave.open(OUT, "wb") as o:
    o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr)
    o.writeframes(mono.tobytes())

# ---- 识别 ----
lib = ctypes.CDLL(LIB)
lib.vosk_model_new.restype = ctypes.c_void_p
lib.vosk_model_new.argtypes = [ctypes.c_char_p]
lib.vosk_recognizer_new.restype = ctypes.c_void_p
lib.vosk_recognizer_new.argtypes = [ctypes.c_void_p, ctypes.c_float]
lib.vosk_recognizer_accept_waveform.restype = ctypes.c_int
lib.vosk_recognizer_accept_waveform.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
lib.vosk_recognizer_final_result.restype = ctypes.c_char_p
lib.vosk_recognizer_final_result.argtypes = [ctypes.c_void_p]
lib.vosk_recognizer_free.argtypes = [ctypes.c_void_p]
lib.vosk_model_free.argtypes = [ctypes.c_void_p]

t0 = time.time()
model = lib.vosk_model_new(MODEL.encode())
log("model loaded %.1fs" % (time.time() - t0))
rec = lib.vosk_recognizer_new(model, float(sr))

raw = mono.tobytes()
CH = 8000  # 0.5s
t0 = time.time()
for i in range(0, len(raw), CH):
    lib.vosk_recognizer_accept_waveform(rec, raw[i:i + CH], min(CH, len(raw) - i))
res = json.loads(lib.vosk_recognizer_final_result(rec).decode())
log("decode %.2fs" % (time.time() - t0))
log("RESULT:", repr(res.get("text", "")))
lib.vosk_recognizer_free(rec)
lib.vosk_model_free(model)
