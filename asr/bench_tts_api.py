# -*- coding: utf-8 -*-
import urllib.request, time
for text in ("这是第一句全新的测试话语没有缓存", "这是第二句不同的话语也没缓存", "第三句全新的内容测试速度"):
    u="http://127.0.0.1:8899/api/tts?text="+urllib.request.quote(text)+"&pitch=28&rate=4"
    t=time.time(); d=urllib.request.urlopen(u,timeout=30).read()
    print(text[:8], round(time.time()-t,2), len(d))
