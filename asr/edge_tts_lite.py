# -*- coding: utf-8 -*-
"""极简 edge-tts 客户端 —— 只用 Python 标准库，连微软 Edge 的朗读服务合成语音。

为什么要自己写：这台音箱（MT8167S / armv7 / Python 3.14）装不了 edge-tts 官方包，
它依赖 aiohttp，而 aiohttp 的 C 扩展在 armv7 上没有预编译 wheel，硬编要拖一整套
clang 工具链。可这套协议本身并不复杂：TLS + WebSocket + 三条文本消息 + 收音频帧，
用 socket/ssl/hashlib 手写两百行就够，还省掉一个几十兆的依赖。

协议要点（对齐 edge-tts 7.3.1）：
  * URL 必须带 TrustedClientToken、ConnectionId，以及 Sec-MS-GEC 令牌
    —— 最后这个是微软的防滥用签名，算法在 sec_ms_gec.py 里
  * 连上先发 speech.config（告诉它要 mp3、不要逐字时间戳）
  * 再发 ssml（真正的文本和音色）
  * 回来的二进制帧前面有 2 字节头长度，头里有 Path:audio，后面才是 mp3 数据
  * 文本帧 Path:turn.end 表示结束
  * 不开 permessage-deflate：我们不在握手时提议，服务器就不会压缩返回
"""

import base64
import hashlib
import os
import queue
import socket
import ssl
import struct
import threading
import time
import uuid

try:
    from sec_ms_gec import sec_ms_gec, TRUSTED_CLIENT_TOKEN
except ImportError:                                    # 允许作为包被导入
    from .sec_ms_gec import sec_ms_gec, TRUSTED_CLIENT_TOKEN

HOST = "speech.platform.bing.com"
WS_PATH = "/consumer/speech/synthesize/readaloud/edge/v1"
CHROMIUM_MAJOR = "143"
GEC_VERSION = "2-143.0.3650.75"
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/%s.0.0.0 Safari/537.36 Edg/%s.0.0.0"
       % (CHROMIUM_MAJOR, CHROMIUM_MAJOR))

_WS_KEY_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class TTSError(Exception):
    pass


def _js_date():
    """微软要的 JS 风格时间串，而且底层是 GMT+0000（不是本地时区）。"""
    return time.strftime("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
                         time.gmtime())


def _ssl_context(insecure=False):
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    # 先按系统默认来（Termux 装了 ca-certificates 就有），再退回 certifi，
    # 都没有就只能不校验 —— 宁可少校验也别整个功能不可用。
    try:
        return ssl.create_default_context()
    except Exception:
        pass
    for fp in ("/data/data/com.termux/files/usr/etc/tls/cert.pem",
               "/system/etc/security/cacerts",
               "/data/data/com.termux/files/usr/lib/python3.14/site-packages/certifi/cacert.pem"):
        if os.path.isfile(fp):
            try:
                return ssl.create_default_context(cafile=fp)
            except Exception:
                continue
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ---------------------------------------------------------------------------
# 建连：并行竞速 + 好 IP 缓存
#
# 实测这台音箱所在的网络里，bing 的两个 A 记录只有 150.171.27.10 通，
# 150.171.28.10 是个黑洞 —— 能发出 SYN，但一直不回，只能等到超时才失败。
# 而 DNS 返回这两条的先后顺序并不保证，一旦黑洞地址排在前面，
# socket.create_connection 就得先把 20 秒超时吃满才轮到下一个。
# 现场确实撞到过一次：TCP 建连耗时 20.29 秒，而 TLS 只用 0.29 秒。
#
# 顺序重试天生有这个毛病，所以改成并发竞速：所有 IPv4 地址同时开拨，
# 谁先连上就用谁，其余立刻丢弃。正常 0.1 秒出结果，最坏也就单个 4 秒超时。
# 胜出的 IP 记 15 分钟，下次直接跳过 DNS。
# ---------------------------------------------------------------------------

_IP_CACHE = {"ip": None, "at": 0.0}
_IP_TTL = 900.0
_CONNECT_TIMEOUT = 4.0


def _resolve_v4(host, port):
    ips = []
    for af, st, p, c, sa in socket.getaddrinfo(host, port, socket.AF_INET,
                                               socket.SOCK_STREAM):
        if sa[0] not in ips:
            ips.append(sa[0])
    return ips


def _tcp_connect(host, port=443, timeout=_CONNECT_TIMEOUT):
    """并发拨号，返回第一个连上的 socket。全部失败则抛出最后一个异常。"""
    ips = []
    if _IP_CACHE["ip"] and time.time() - _IP_CACHE["at"] < _IP_TTL:
        ips.append(_IP_CACHE["ip"])          # 上次好用的排最前，且只多花一次并发
    try:
        for ip in _resolve_v4(host, port):
            if ip not in ips:
                ips.append(ip)
    except OSError:
        if not ips:
            raise
    if not ips:
        raise OSError("解析不出 IPv4 地址: %s" % host)

    q = queue.Queue()
    won = threading.Event()

    def worker(ip, idx):
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((ip, port))
            if won.is_set():                 # 已经有人赢了，自己的白连，关掉
                s.close()
                return
            q.put((idx, ip, s, None))
        except Exception as exc:             # noqa: BLE001 - 任何失败都记录后交给主线程
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass
            q.put((idx, ip, None, exc))

    for i, ip in enumerate(ips):
        threading.Thread(target=worker, args=(ip, i), daemon=True).start()

    last = None
    for _ in range(len(ips)):
        try:
            idx, ip, s, err = q.get(timeout=timeout + 0.5)
        except queue.Empty:
            break
        if s is not None:
            won.set()
            _IP_CACHE["ip"] = ip
            _IP_CACHE["at"] = time.time()
            return s
        last = err
    raise last or OSError("所有地址都连不上: %s" % host)


def _recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise TTSError("连接被对端关闭")
        buf += chunk
    return buf


def _read_until(s, sep, cap=65536):
    buf = b""
    while sep not in buf:
        if len(buf) > cap:
            raise TTSError("响应头过长")
        chunk = s.recv(4096)
        if not chunk:
            raise TTSError("握手中连接断开")
        buf += chunk
    return buf


def _connect(timeout=15, insecure=False):
    """建 TLS 连接并完成 WebSocket 握手，返回已就绪的 socket。"""
    cid = uuid.uuid4().hex
    query = ("?TrustedClientToken=%s&ConnectionId=%s&Sec-MS-GEC=%s&Sec-MS-GEC-Version=%s"
             % (TRUSTED_CLIENT_TOKEN, cid, sec_ms_gec(), GEC_VERSION))
    key = base64.b64encode(os.urandom(16)).decode("ascii")

    raw = _tcp_connect(HOST, 443, min(timeout, _CONNECT_TIMEOUT))
    ctx = _ssl_context(insecure)
    try:
        sock = ctx.wrap_socket(raw, server_hostname=HOST)
    except Exception:
        raw.close()
        raise

    req = (
        "GET %s%s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: %s\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Pragma: no-cache\r\n"
        "Cache-Control: no-cache\r\n"
        "Origin: chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold\r\n"
        "User-Agent: %s\r\n"
        "Accept-Encoding: gzip, deflate, br, zstd\r\n"
        "Accept-Language: en-US,en;q=0.9\r\n"
        "Cookie: muid=%s;\r\n"
        "\r\n"
        % (WS_PATH, query, HOST, key, _UA, uuid.uuid4().hex.upper())
    )
    sock.sendall(req.encode("ascii"))
    resp = _read_until(sock, b"\r\n\r\n")
    head = resp.split(b"\r\n\r\n", 1)[0].decode("latin-1")
    status = head.split("\r\n", 1)[0]
    if " 101 " not in status:
        sock.close()
        raise TTSError("WebSocket 握手失败: %s" % status)
    # 校验 accept，确认没被中间人/代理截胡
    want = base64.b64encode(hashlib.sha1(key.encode("ascii") + _WS_KEY_GUID).digest()).decode()
    for line in head.split("\r\n")[1:]:
        if line.lower().startswith("sec-websocket-accept:"):
            got = line.split(":", 1)[1].strip()
            if got != want:
                sock.close()
                raise TTSError("Sec-WebSocket-Accept 不匹配")
            break
    return sock


def _send_text(sock, payload):
    """发一个客户端文本帧。客户端发出的帧必须加掩码。"""
    data = payload.encode("utf-8")
    n = len(data)
    head = bytearray([0x81])                       # FIN + opcode=text
    mask = os.urandom(4)
    if n < 126:
        head.append(0x80 | n)
    elif n < 65536:
        head.append(0x80 | 126)
        head += struct.pack(">H", n)
    else:
        head.append(0x80 | 127)
        head += struct.pack(">Q", n)
    head += mask
    out = bytearray(n)
    for i in range(n):
        out[i] = data[i] ^ mask[i & 3]
    sock.sendall(bytes(head) + bytes(out))


def _read_frame(sock):
    """读一帧，返回 (opcode, payload, fin)。"""
    b = _recv_exact(sock, 2)
    fin = bool(b[0] & 0x80)
    opcode = b[0] & 0x0F
    n = b[1] & 0x7F
    if n == 126:
        n = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack(">Q", _recv_exact(sock, 8))[0]
    masked = b[1] & 0x80
    mask = _recv_exact(sock, 4) if masked else None
    data = _recv_exact(sock, n) if n else b""
    if mask:
        data = bytes(ch ^ mask[i & 3] for i, ch in enumerate(data))
    return opcode, data, fin


def _ssml(text, voice, pitch, rate):
    def esc(t):
        return (t.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace("'", "&apos;").replace('"', "&quot;"))
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        "<voice name='%s'>"
        "<prosody pitch='%+dHz' rate='%+d%%' volume='+0%%'>%s</prosody>"
        "</voice></speak>" % (voice, int(pitch), int(rate), esc(text))
    )


def synth(text, voice="zh-CN-XiaoyiNeural", pitch=0, rate=0,
          timeout=20, insecure=False):
    """把一段文字合成 mp3 字节流。失败抛 TTSError / OSError / ssl.SSLError。"""
    text = (text or "").strip()
    if not text:
        return b""

    sock = _connect(timeout=timeout, insecure=insecure)
    audio = []
    try:
        sock.settimeout(timeout)

        # 1) 配置：要 mp3，不要句/词边界时间戳（那些是给字幕用的，白占带宽）
        cfg = ("X-Timestamp:%s\r\n"
               "Content-Type:application/json; charset=utf-8\r\n"
               "Path:speech.config\r\n\r\n"
               '{"context":{"synthesis":{"audio":{"metadataoptions":'
               '{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"false"},'
               '"outputFormat":"%s"}}}}\r\n' % (_js_date(), OUTPUT_FORMAT))
        _send_text(sock, cfg)

        # 2) 正文。X-Timestamp 后面这个 "Z" 是微软自己的 bug，照抄才能过。
        ssml = ("X-RequestId:%s\r\n"
                "Content-Type:application/ssml+xml\r\n"
                "X-Timestamp:%sZ\r\n"
                "Path:ssml\r\n\r\n"
                "%s" % (uuid.uuid4().hex, _js_date(), _ssml(text, voice, pitch, rate)))
        _send_text(sock, ssml)

        # 3) 收帧
        pending = {}
        while True:
            opcode, data, fin = _read_frame(sock)

            if opcode == 0x8:                                  # close
                break
            if opcode == 0x9:                                  # ping -> pong
                continue
            if opcode == 0xA:                                  # pong
                continue

            if opcode == 0x0 and pending:                      # 续帧
                pending["data"] += data
                if not fin:
                    continue
                data = pending["data"]
                opcode = pending["op"]
                pending = {}
            elif not fin:
                pending = {"op": opcode, "data": data}
                continue

            if opcode == 0x1:                                  # 文本
                txt = data.decode("utf-8", "replace")
                if "Path:turn.end" in txt:
                    break
                continue

            if opcode == 0x2:                                  # 二进制 = 音频
                if len(data) < 2:
                    continue
                hlen = struct.unpack(">H", data[:2])[0]
                head = data[2:2 + hlen].decode("latin-1", "replace")
                if "Path:audio" in head:
                    audio.append(data[2 + hlen:])
    finally:
        try:
            sock.close()
        except Exception:
            pass

    out = b"".join(audio)
    if not out:
        raise TTSError("没收到音频（可能被限流或参数不对）")
    return out


if __name__ == "__main__":
    import sys
    t = " ".join(sys.argv[1:]) or "你好，我是大肥鱼～"
    t0 = time.time()
    data = synth(t, voice="zh-CN-XiaoyiNeural", pitch=26, rate=4)
    print("ok %d bytes in %.2fs" % (len(data), time.time() - t0))
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_test.mp3"), "wb").write(data)
