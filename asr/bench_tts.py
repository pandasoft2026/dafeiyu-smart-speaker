# -*- coding: utf-8 -*-
import sys,time
sys.path.insert(0,"/data/local/tmp/voicebot")
import edge_tts_lite as E
# 先预热连接池
s=time.time(); E.synth("嗯",pitch=28,rate=4); print("预热",round(time.time()-s,2))
for i,t in enumerate(["完全新的句子一","另一句全新内容二","第三句不一样的话"]):
    s=time.time(); d=E.synth(t,pitch=28,rate=4)
    print(i,round(time.time()-s,2),len(d))
