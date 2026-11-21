# -*- coding: utf-8 -*-
"""检查 libvosk_android.so 里与 partial / words 相关的导出符号"""
p = "/data/local/tmp/voicebot/libvosk_android.so"
d = open(p, "rb").read()
names = [
    b"vosk_recognizer_partial_result",
    b"vosk_recognizer_set_partial_words",
    b"vosk_recognizer_set_words",
    b"vosk_recognizer_set_max_alternatives",
    b"vosk_recognizer_result",
    b"vosk_recognizer_final_result",
]
for n in names:
    print("%-40s %d" % (n.decode(), d.count(n)))
