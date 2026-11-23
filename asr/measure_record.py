# -*- coding: utf-8 -*-
"""测 record() 实际录音时长：播放固定语音，同时录音，报告从开始到判停的耗时。"""
import subprocess
import sys
import time

sys.path.insert(0, "/data/local/tmp/voicebot")
import service as S

S.init_asr()

text = sys.argv[1] if len(sys.argv) > 1 else "这是一句测试录音时长的话"
# 用本地 TTS 拿音频
import urllib.parse
import urllib.request
u = ("http://127.0.0.1:8899/api/tts?text=" + urllib.parse.quote(text) +
     "&voice=zh-CN-XiaoyiNeural&pitch=28&rate=4")
mp3 = urllib.request.urlopen(u, timeout=30).read()
open("/dev/selftest.mp3", "wb").write(mp3)

# 播放 + 同时录音
t0 = time.time()
p = subprocess.Popen(["/system/bin/sh", "-c",
                      "tinyplay /dev/selftest.mp3 >/dev/null 2>&1"])
time.sleep(0.25)          # 等喇叭出声
r0 = time.time()
pcm, nch = S.record(max_sec=7.0, min_sec=1.0)
rec_dt = time.time() - r0
total = time.time() - t0
print("SILENCE_DEFAULT=%.2f" % S.SILENCE_DEFAULT)
print("录音判停耗时 %.2fs（从开始录音算）" % rec_dt)
print("全程 %.2fs" % total)
print("采样点数 %d / %d 通道 ≈ %.2fs 音频"
      % (len(pcm) if pcm else 0, nch, (len(pcm) / nch / S.SR) if pcm else 0))
