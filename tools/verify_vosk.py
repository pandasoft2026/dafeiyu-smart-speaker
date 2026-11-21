# -*- coding: utf-8 -*-
import sys
print("python", sys.version.split()[0])
try:
    import vosk
    print("VOSK_OK", vosk.__file__)
    import srt
    print("SRT_OK")
    # try load model
    m = "/data/local/tmp/voicebot/model"
    print("loading model...", m)
    model = vosk.Model(m)
    print("MODEL_OK")
    rec = vosk.KaldiRecognizer(model, 16000)
    print("RECOGNIZER_OK")
except Exception as e:
    import traceback
    traceback.print_exc()
