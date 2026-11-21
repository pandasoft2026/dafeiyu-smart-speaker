# -*- coding: utf-8 -*-
"""Vosk ctypes binding - avoids the _cffi_backend dependency.
Wraps the same C API that vosk's CFFI binding uses, using Python stdlib ctypes only.
"""
import ctypes, os, json

# ensure Termux lib dir is searchable for libatomic.so.1 etc.
_TERMUX_LIB = "/data/data/com.termux/files/usr/lib"
try:
    ctypes.CDLL(_TERMUX_LIB + "/libatomic.so.1", mode=ctypes.RTLD_GLOBAL)
except Exception:
    pass

_LIB = os.path.join(os.path.dirname(__file__), "libvosk.so")
_lib = ctypes.CDLL(_LIB)

_lib.vosk_model_new.argtypes = [ctypes.c_char_p]
_lib.vosk_model_new.restype = ctypes.c_void_p
_lib.vosk_model_free.argtypes = [ctypes.c_void_p]

_lib.vosk_recognizer_new.argtypes = [ctypes.c_void_p, ctypes.c_float]
_lib.vosk_recognizer_new.restype = ctypes.c_void_p
_lib.vosk_recognizer_new_grm.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_char_p]
_lib.vosk_recognizer_new_grm.restype = ctypes.c_void_p
_lib.vosk_recognizer_free.argtypes = [ctypes.c_void_p]
_lib.vosk_recognizer_reset.argtypes = [ctypes.c_void_p]
_lib.vosk_recognizer_accept_waveform.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
_lib.vosk_recognizer_accept_waveform.restype = ctypes.c_int
_lib.vosk_recognizer_partial_result.argtypes = [ctypes.c_void_p]
_lib.vosk_recognizer_partial_result.restype = ctypes.c_char_p
_lib.vosk_recognizer_result.argtypes = [ctypes.c_void_p]
_lib.vosk_recognizer_result.restype = ctypes.c_char_p
_lib.vosk_recognizer_final_result.argtypes = [ctypes.c_void_p]
_lib.vosk_recognizer_final_result.restype = ctypes.c_char_p
_lib.vosk_set_log_level.argtypes = [ctypes.c_int]


class Model:
    def __init__(self, path):
        self._p = _lib.vosk_model_new(path.encode("utf-8"))
        if not self._p:
            raise RuntimeError("cannot load model: " + path)
    def __del__(self):
        try: _lib.vosk_model_free(self._p)
        except Exception: pass


class KaldiRecognizer:
    def __init__(self, model, rate, grammar=None):
        if grammar:
            self._p = _lib.vosk_recognizer_new_grm(model._p, float(rate), grammar.encode("utf-8"))
        else:
            self._p = _lib.vosk_recognizer_new(model._p, float(rate))
        if not self._p:
            raise RuntimeError("cannot create recognizer")
    def __del__(self):
        try: _lib.vosk_recognizer_free(self._p)
        except Exception: pass
    def AcceptWaveform(self, data):
        return bool(_lib.vosk_recognizer_accept_waveform(self._p, data, len(data)))
    def PartialResult(self):
        r = _lib.vosk_recognizer_partial_result(self._p)
        return r.decode("utf-8") if r else ""
    def Result(self):
        r = _lib.vosk_recognizer_result(self._p)
        return r.decode("utf-8") if r else ""
    def FinalResult(self):
        r = _lib.vosk_recognizer_final_result(self._p)
        return r.decode("utf-8") if r else ""
    def Reset(self):
        _lib.vosk_recognizer_reset(self._p)


def SetLogLevel(level):
    _lib.vosk_set_log_level(level)
