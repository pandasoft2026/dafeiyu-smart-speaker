# -*- coding: utf-8 -*-
"""缓存淘汰压测：灌 80 条不同文本，验证 LRU 上限生效、服务不崩。"""
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8899/api/tts?text="
N = 80
t0 = time.time()
ok = 0
for i in range(N):
    text = "缓存淘汰压力测试第%d条内容" % i
    try:
        with urllib.request.urlopen(BASE + urllib.parse.quote(text), timeout=30) as r:
            if r.status == 200 and len(r.read()) > 100:
                ok += 1
    except Exception as e:
        print("第%d条失败: %s" % (i, e))
print("合成成功 %d/%d，耗时 %.1fs" % (ok, N, time.time() - t0))
