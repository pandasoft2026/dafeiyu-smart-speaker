# -*- coding: utf-8 -*-
"""诊断：播放语音时录 4 声道，逐声道看能量与识别结果，找出主麦克风通道"""
import ctypes, json, subprocess, sys, time, wave, array, os

BASE = "/data/local/tmp/voicebot"
LIB = BASE + "/libvosk_android.so"
MODEL = BASE + "/model"
SR = 16000


def log(*a):
    print(*a); sys.stdout.flush()


subprocess.Popen(["/vendor/bin/tinyplay", BASE + "/spk_a.wav", "-D", "0", "-d", "0"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.35)

p = BASE + "/diag4.wav"
if os.path.exists(p):
    os.remove(p)
subprocess.run(["/vendor/bin/tinycap", p, "-D", "0", "-d", "2", "-c", "4", "-r", str(SR),
                "-b", "16", "-T", "6"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

w = wave.open(p, "rb")
nch, n = w.getnchannels(), w.getnframes()
raw = w.readframes(n)
w.close()
pcm = array.array("h"); pcm.frombytes(raw)
log("ch=%d frames=%d dur=%.1fs" % (nch, n, n / SR))

lib = ctypes.CDLL(LIB)
for nm, r, a in [("vosk_model_new", ctypes.c_void_p, [ctypes.c_char_p]),
                 ("vosk_recognizer_new", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_float]),
                 ("vosk_recognizer_accept_waveform", ctypes.c_int, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]),
                 ("vosk_recognizer_final_result", ctypes.c_char_p, [ctypes.c_void_p]),
                 ("vosk_recognizer_reset", None, [ctypes.c_void_p]),
                 ("vosk_model_free", None, [ctypes.c_void_p]),
                 ("vosk_recognizer_free", None, [ctypes.c_void_p])]:
    f = getattr(lib, nm); f.restype = r; f.argtypes = a

model = lib.vosk_model_new(MODEL.encode())
rec = lib.vosk_recognizer_new(model, float(SR))
lib.vosk_recognizer_accept_waveform(rec, b"\x00\x00" * SR, SR * 2); lib.vosk_recognizer_final_result(rec); lib.vosk_recognizer_reset(rec)

for ch in range(nch):
    mono = pcm[ch::nch]
    peak = max((abs(v) for v in mono), default=0)
    rms = int((sum(v * v for v in mono[::8]) / max(1, len(mono[::8]))) ** 0.5)
    lib.vosk_recognizer_accept_waveform(rec, mono.tobytes(), len(mono) * 2)
    txt = json.loads(lib.vosk_recognizer_final_result(rec).decode()).get("text", "").replace(" ", "")
    lib.vosk_recognizer_reset(rec)
    log("  ch%d peak=%5d rms=%4d | %s" % (ch, peak, rms, txt))

# 混合 ch0+ch1 尝试
if nch >= 2:
    a0 = pcm[0::nch]; a1 = pcm[1::nch]
    mix = array.array("h", [max(-32768, min(32767, (a0[i] + a1[i]) // 2)) for i in range(min(len(a0), len(a1)))])
    lib.vosk_recognizer_accept_waveform(rec, mix.tobytes(), len(mix) * 2)
    txt = json.loads(lib.vosk_recognizer_final_result(rec).decode()).get("text", "").replace(" ", "")
    lib.vosk_recognizer_reset(rec)
    log("  ch0+ch1 mix | %s" % txt)

lib.vosk_recognizer_free(rec); lib.vosk_model_free(model)
