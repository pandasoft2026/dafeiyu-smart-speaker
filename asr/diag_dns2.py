# -*- coding: utf-8 -*-
"""重复取样：getaddrinfo 返回顺序是否轮换 + 两个 A 记录各自可达性。"""
import socket
import time

HOST = "speech.platform.bing.com"

for i in range(6):
    t = time.time()
    infos = socket.getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)
    order = [sa[0] for af, st, p, c, sa in infos]
    dt = time.time() - t
    print("%d) dns %.2fs  order=%s" % (i + 1, dt, " -> ".join(order)))

    for ip in ("150.171.27.10", "150.171.28.10"):
        t = time.time()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((ip, 443))
            s.close()
            print("     %-16s %.2fs OK" % (ip, time.time() - t))
        except Exception as e:
            print("     %-16s %.2fs FAIL %s" % (ip, time.time() - t, e))
    time.sleep(1)

# 真实 synth 计时（含完整建连 + 合成）
try:
    import edge_tts_lite as E
    for i in range(3):
        t = time.time()
        try:
            data = E.synth("好的", voice="zh-CN-XiaoyiNeural", pitch=26, rate=4)
            print("synth %d) %.2fs  %d bytes" % (i + 1, time.time() - t, len(data)))
        except Exception as e:
            print("synth %d) %.2fs FAIL %s" % (i + 1, time.time() - t, e))
except Exception as e:
    print("synth 不可用: %s" % e)
