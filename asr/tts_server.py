# -*- coding: utf-8 -*-
"""
本机 TTS 服务（给音箱用）
GET /tts?text=xxx&voice=zh-CN-XiaoyiNeural&pitch=25&rate=3
返回 audio/mpeg

顺带托管 samples/ 目录（音色试听页）：GET / 与 GET /s/<文件名>
"""
import asyncio, hashlib, io, os, sys, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import edge_tts

PORT = 8900
DEFAULT_VOICE = "zh-CN-XiaoyiNeural"
SAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "samples")

MIME = {".html": "text/html; charset=utf-8", ".mp3": "audio/mpeg",
        ".js": "application/javascript", ".css": "text/css", ".png": "image/png"}


def log(*a):
    print(*a); sys.stdout.flush()


async def synth(text, voice, pitch, rate):
    c = edge_tts.Communicate(text, voice, rate="%+d%%" % rate, pitch="%+dHz" % pitch)
    buf = io.BytesIO()
    async for chunk in c.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


# ---- 本地缓存 ---------------------------------------------------------
# 和设备端用同一套 key（音色|音调|语速|文本），同一句话第二次直接读文件。
# 电脑做备选时也要够快，不然设备切过来一样要等两三秒。
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_cache")
CACHE_MAX = 200
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except OSError:
    pass


def cache_path(text, voice, pitch, rate):
    key = hashlib.md5(("%s|%d|%d|%s" % (voice, pitch, rate, text))
                      .encode("utf-8")).hexdigest()[:12]
    return os.path.join(CACHE_DIR, key + ".mp3")


def cached(path):
    try:
        with open(path, "rb") as f:
            d = f.read()
        if d:
            os.utime(path, None)
            return d
    except OSError:
        pass
    return b""


def cache_trim():
    try:
        items = []
        for n in os.listdir(CACHE_DIR):
            if not n.endswith(".mp3"):
                continue
            fp = os.path.join(CACHE_DIR, n)
            st = os.stat(fp)
            items.append((st.st_mtime, fp))
        while len(items) > CACHE_MAX:
            _, fp = items.pop(0)
            try:
                os.remove(fp)
            except OSError:
                pass
    except OSError:
        pass


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204); self._cors()
        self.send_header("Content-Length", "0"); self.end_headers()

    def _file(self, path):
        try:
            data = open(path, "rb").read()
        except OSError:
            self.send_error(404)
            return
        ext = os.path.splitext(path)[1].lower()
        self.send_response(200); self._cors()
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.startswith("/health"):
            b = b'{"ok":true}'
            self.send_response(200); self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers()
            self.wfile.write(b); return
        # 音色试听页
        if u.path in ("/", "/index.html", "/samples"):
            return self._file(os.path.join(SAMPLES, "index.html"))
        if u.path.startswith("/s/"):
            name = os.path.basename(urllib.parse.unquote(u.path[3:]))
            return self._file(os.path.join(SAMPLES, name))
        if not u.path.startswith("/tts"):
            self.send_error(404); return

        q = urllib.parse.parse_qs(u.query)
        text = (q.get("text", [""])[0] or "").strip()
        if not text:
            self.send_error(400, "empty text"); return
        voice = q.get("voice", [DEFAULT_VOICE])[0]
        try:
            pitch = int(q.get("pitch", ["25"])[0])
            rate = int(q.get("rate", ["3"])[0])
        except ValueError:
            pitch, rate = 25, 3

        fp = cache_path(text, voice, pitch, rate)
        data = cached(fp)
        if data:
            log("tts cache hit | %s" % text[:30])
        else:
            try:
                data = asyncio.run(synth(text, voice, pitch, rate))
                with open(fp, "wb") as f:
                    f.write(data)
                cache_trim()
            except Exception as e:
                log("tts fail", e)
                self.send_error(500, str(e)); return

        log("tts %d chars -> %d bytes | %s" % (len(text), len(data), text[:30]))
        self.send_response(200); self._cors()
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    # 只留一个实例。之前出现过双击两次 bat 留下两个进程，
    # 一个占着端口、另一个空转，排查时很容易被 health 骗过去。
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    except OSError as e:
        print("端口 %d 已被占用（%s）。服务可能已经在跑了，不用再开。" % (PORT, e))
        print("如果不确定，检查：netstat -ano | findstr :%d" % PORT)
        raise SystemExit(0)
    log("TTS on 0.0.0.0:%d" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("TTS 已停止")
