# -*- coding: utf-8 -*-
"""分阶段测 TTS 各步骤耗时，定位 22 秒花在哪。"""
import socket
import ssl
import time

import edge_tts_lite as E
from sec_ms_gec import sec_ms_gec

t = time.time(); tok = sec_ms_gec(); print("1 sec_ms_gec      %.2fs  %s" % (time.time() - t, tok[:20]))
t = time.time(); ctx = ssl.create_default_context(); print("2 ssl ctx default %.2fs" % (time.time() - t))
t = time.time(); raw = socket.create_connection((E.HOST, 443), 20); print("3 tcp connect     %.2fs" % (time.time() - t))
t = time.time(); s = ctx.wrap_socket(raw, server_hostname=E.HOST); print("4 tls handshake   %.2fs  %s" % (time.time() - t, s.version()))
s.close()

t = time.time(); ctx2 = E._ssl_context(); print("5 module _ssl_context %.2fs" % (time.time() - t))
t = time.time(); s2 = E._connect(timeout=20); print("6 full _connect   %.2fs" % (time.time() - t))
s2.close()
