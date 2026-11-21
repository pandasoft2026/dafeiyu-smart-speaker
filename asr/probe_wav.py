# -*- coding: utf-8 -*-
d = open("/data/local/tmp/voicebot/live.wav", "rb").read()
print("len", len(d))
print("head", d[:64])
print("data tag at", d.find(b"data"))
print("RIFF", d[:4], "WAVE", d[8:12])
for tag in (b"fmt ", b"data", b"LIST"):
    print(tag, "->", d.find(tag))
print("tail", d[-12:])
