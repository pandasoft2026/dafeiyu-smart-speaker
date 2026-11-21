# -*- coding: utf-8 -*-
import sys, wave, struct, json, time
sys.path.insert(0, "/data/local/tmp/voicebot")
import vosk_ctypes as vosk

print("1. SetLogLevel")
vosk.SetLogLevel(-1)

print("2. load model")
m = vosk.Model("/data/local/tmp/voicebot/model")
print("   MODEL OK")

print("3. recognizer")
r = vosk.KaldiRecognizer(m, 16000)
print("   REC OK")

# use the 8ch recording, take ch0 as mono 16k
w = wave.open("/data/local/tmp/audio_test/t4.tdm8.wav", "rb")
n = w.getnframes()
c = w.getnchannels()
raw = w.readframes(n)
data = struct.unpack("<" + "h" * (len(raw) // 2), raw)
mono = data[0::8]  # ch0
pcm = struct.pack("<" + "h" * len(mono), *mono)
w.close()
print("   audio frames:", len(mono), "dur=%.1fs" % (len(mono) / 16000))

print("4. feed in 4000-sample chunks")
t0 = time.time()
partials = []
for i in range(0, len(pcm), 8000):
    chunk = pcm[i:i+8000]
    if vosk.KaldiRecognizer.AcceptWaveform(r, chunk):
        res = vosk.KaldiRecognizer.Result(r)
        partials.append(("FINAL", res))
    else:
        p = vosk.KaldiRecognizer.PartialResult(r)
        if p: partials.append(("PART", p))
print("   processed in %.2fs" % (time.time() - t0))

final = vosk.KaldiRecognizer.FinalResult(r)
print("5. FINAL RESULT:", final)
print("   num events:", len(partials))
for t, v in partials[-3:]:
    print("   ", t, v[:150])
