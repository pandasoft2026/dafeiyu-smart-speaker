# -*- coding: utf-8 -*-
"""
大肥鱼 / 梁圣 语音服务（设备端常驻）

HTTP:
  GET  /health
  GET  /api/events            取走待处理事件（前端轮询）
  POST /api/listen            录音(VAD 说完即停) + 离线识别
  POST /api/ask               文本 -> DeepSeek
  POST /api/mode              {"mode":"fish"|"sage"} 手动切换
  POST /api/wake              {"active":true|false} 开关唤醒监听

语音唤醒：常驻分片监听，命中"肥鱼肥鱼""你好肥鱼""召唤梁圣""召唤大肥鱼"
"""
import ctypes, hashlib, json, os, struct, subprocess, sys, threading, time, traceback, wave, array, collections
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen
from urllib.error import URLError

BASE = "/data/local/tmp/voicebot"
# 录音落盘一律走 /dev（tmpfs，内存里）。tinycap 是 128KB/s 连续写入，
# 放在 /data 上是 11GB/天的 flash 写放大，一年就能把 eMMC 磨穿。
# /dev 是 tmpfs，写它等于写内存，零磨损，而且读写都更快。
SCRATCH = "/dev"
LIB = os.path.join(BASE, "libvosk_android.so")
MODEL = os.path.join(BASE, "model")
REC = os.path.join(SCRATCH, "dfy_live.wav")
REC_WAKE = os.path.join(SCRATCH, "dfy_wake.wav")
WAKE_STREAM = os.path.join(SCRATCH, "dfy_wake_stream.wav")
WAKE_LAST = os.path.join(SCRATCH, "dfy_wake_last.wav")
WAKE_PRE = os.path.join(SCRATCH, "dfy_wake_pre.wav")
GATE_LAST = os.path.join(SCRATCH, "dfy_gate_last.wav")
RAW_KEEP = os.path.join(SCRATCH, "dfy_last_raw.wav")
SR = 16000
PORT = 8899
API_KEY_FILE = os.path.join(BASE, "api_key.conf")

PROMPTS = {
    "fish": (
        "你是“大肥鱼”，一只软萌爱撒娇的 DeepSeek 小鲸鱼助手，说话简短、口语化、带一点撒娇语气，"
        "每次回答控制在两三句话以内，适合语音播报。不要使用 Markdown、表情符号或列表。"
    ),
    "sage": (
        "你是“梁圣”，一位三十岁出头、气场很强的技术型老板。说话简洁克制、有掌控力，"
        "习惯用短句直接给判断和结论，不寒暄、不卖萌、不用语气词和感叹号。"
        "语气平静但有分量，偶尔不动声色地锋利一下。"
        "每次回答控制在三句以内，适合语音播报。不要使用 Markdown、表情符号或列表。"
    ),
}

STATE = {"mode": "fish", "busy": False, "wake": True}
EVENTS = []
# ---- 息屏 ----
# 这台固件没有 SystemUI，系统的 screen_off_timeout 走到"做梦"这一步就没人接手，
# 试过 15 秒超时也不熄屏（mUserActivitySummary 在 0x4/0x1 之间反复）。所以自己算：
# 界面每次真的有人碰（点击、音量键）或者有人跟它说话，就刷新时间戳。
IDLE_OFF = 600.0          # 秒；10 分钟
_last_act = time.time()
EV_LOCK = threading.Condition()   # 既当锁用，也能让长轮询挂在这里等事件
_lock = threading.Lock()
_asr = {}
WAKE_DEBUG = True
BUILD = "b1120-78"
# 实时拾音峰值诊断（给 PC 喇叭回环测试用）：滑动窗口最大值，只观测不改逻辑
LIVE_PEAK = {"max": 0, "at": 0.0}
# 开闸门限：默认 800（真人对着喊 peak 2000+）。PC 喇叭回环测试时可临时调低，
# 测完必须恢复——这是诊断旋钮，不是生产默认值。
WAKE_GATE_FLOOR = [800.0]

FIX = [("肥腴", "肥鱼"), ("肥于", "肥鱼"), ("飞鱼", "肥鱼"), ("菲鱼", "肥鱼"),
       ("梁生", "梁圣"), ("良圣", "梁圣"), ("梁胜", "梁圣"), ("凉圣", "梁圣")]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a)
    sys.stdout.flush()


def fix_text(t):
    for a, b in FIX:
        t = t.replace(a, b)
    return t


def push_event(ev):
    with EV_LOCK:
        EVENTS.append(ev)
        while len(EVENTS) > 20:
            EVENTS.pop(0)
        EV_LOCK.notify_all()          # 叫醒正在长轮询的界面
    log("event", ev)


# ---------------------------------------------------------------------------
# 本地 TTS
#
# 语音原先靠 PC 上的 tts_server.py（8900 端口）合成，电脑一关音箱就哑了。
# 这里把 edge_tts_lite 直接接进来：音箱自己连微软朗读服务、自己拿 mp3，
# 电脑彻底退出链路。
#
# 合成结果按 (音色|音调|语速|文本) 存一份到 /dev（tmpfs，不磨损 flash）。
# 日常对话里「好的」「我在」「嗯？」这类短句复用率很高，第二次就是零延迟。
# ---------------------------------------------------------------------------
TTS_DIR = os.path.join(SCRATCH, "dfy_tts")
TTS_VOICE = {"fish": "zh-CN-XiaoyiNeural", "sage": "zh-CN-YunyangNeural"}
TTS_TUNE = {"fish": (28, 4), "sage": (-10, -6)}     # (pitch 加多少 Hz, rate 加多少 %)
TTS_CACHE_MAX = 60                                  # 最多留 60 条
TTS_CACHE_BYTES = 16 << 20                          # 或者 16MB，谁先到算谁
TTS_TEXT_MAX = 600                                  # 单次合成的字数上限
_tts_locks = {}
_tts_lk = threading.Lock()
_tts_stat = {"hit": 0, "miss": 0, "err": 0}
_tts = None


def tts_mod():
    """延迟导入：就算 edge_tts_lite 出问题，也不该让整个服务起不来。"""
    global _tts
    if _tts is None:
        import edge_tts_lite
        _tts = edge_tts_lite
    return _tts


def _tts_trim():
    """缓存超限就按 mtime 从旧到新删。"""
    try:
        items = []
        total = 0
        for n in os.listdir(TTS_DIR):
            if not n.endswith(".mp3"):
                continue
            fp = os.path.join(TTS_DIR, n)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            items.append((st.st_mtime, st.st_size, fp))
            total += st.st_size
        cnt = len(items)
        if cnt <= TTS_CACHE_MAX and total <= TTS_CACHE_BYTES:
            return
        items.sort()
        for mt, sz, fp in items:
            if cnt <= TTS_CACHE_MAX and total <= TTS_CACHE_BYTES:
                break
            try:
                os.remove(fp)
            except OSError:
                pass
            total -= sz
            cnt -= 1
    except OSError:
        pass


def _tts_read(fp):
    try:
        with open(fp, "rb") as f:
            d = f.read()
        if d:
            try:
                os.utime(fp, None)        # 刷 mtime，LRU 才准
            except OSError:
                pass
        return d
    except OSError:
        return b""


def tts_get(text, voice="", pitch=None, rate=None):
    """合成一段话，返回 mp3 字节。命中缓存就直接读文件。"""
    text = (text or "").strip()
    if not text:
        return b""
    if len(text) > TTS_TEXT_MAX:
        text = text[:TTS_TEXT_MAX]

    m = STATE["mode"]
    voice = (voice or "").strip() or TTS_VOICE.get(m, "zh-CN-XiaoyiNeural")
    dp, dr = TTS_TUNE.get(m, (0, 0))
    pitch = dp if pitch is None else int(pitch)
    rate = dr if rate is None else int(rate)

    key = hashlib.md5(("%s|%d|%d|%s" % (voice, pitch, rate, text))
                      .encode("utf-8")).hexdigest()[:12]
    fp = os.path.join(TTS_DIR, key + ".mp3")

    data = _tts_read(fp)
    if data:
        _tts_stat["hit"] += 1
        return data

    # 同一句话被并发请求时只合成一次，后面的人等结果
    with _tts_lk:
        lk = _tts_locks.setdefault(key, threading.Lock())
        if len(_tts_locks) > 500:      # 这台机器要开几个月，别让锁表无限长
            _tts_locks.clear()
            _tts_locks[key] = lk
    with lk:
        data = _tts_read(fp)
        if data:
            _tts_stat["hit"] += 1
            return data

        t0 = time.time()
        try:
            data = tts_mod().synth(text, voice=voice, pitch=pitch, rate=rate, timeout=20)
        except Exception as e:
            _tts_stat["err"] += 1
            log("tts 失败 %s %r: %s" % (key, text[:20], e))
            raise
        _tts_stat["miss"] += 1
        try:
            os.makedirs(TTS_DIR, exist_ok=True)
            tmp = fp + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, fp)
            _tts_trim()
        except OSError:
            pass
        log("tts %s %d 字 -> %d 字节 %.2fs" % (key, len(text), len(data), time.time() - t0))
        return data


# 开机预合成的固定话术。这些句子每次都一模一样，提前合成好命中缓存，
# 用户一喊就能出声，不用等那两秒多的网络往返。
# 键是 (音色, pitch, rate)，值与前端 P[mode].hello / back 保持一致。
TTS_PHRASES = [
    ("你好呀，我是大肥鱼～点下面的麦克风，跟我说句话吧！",
     "zh-CN-XiaoyiNeural", 28, 4),
    ("大肥鱼回来啦～想我了吗？",
     "zh-CN-XiaoyiNeural", 28, 4),
    ("梁圣已上线。有事直说。",
     "zh-CN-YunyangNeural", -10, -6),
]


def tts_warm():
    """开机预热：探好 IP，并把固定话术合成好塞进缓存。失败也无所谓。"""
    try:
        E = tts_mod()
        s = E._tcp_connect(E.HOST, 443, 4)
        s.close()
        log("tts 预热完成 ip=%s" % E._IP_CACHE["ip"])
    except Exception as e:
        log("tts 预热失败（不影响使用）: %s" % e)

    # 固定话术：一条条合成，别并发 ——  concurrency 在这颗 4×A35 上反而更慢
    for text, voice, pitch, rate in TTS_PHRASES:
        try:
            t0 = time.time()
            tts_get(text, voice, pitch, rate)
            log("tts 预合成 %d 字 %.2fs" % (len(text), time.time() - t0))
        except Exception as e:
            log("tts 预合成失败（%s）: %s" % (text[:8], e))


def tts_wake_prewarm():
    """方案D：唤醒瞬间预热。异步跑，绝不挡住唤醒/录音链路。

    只做一件无声的事：确保复用池里有一条已握手的 WebSocket。
    用户听完叮才开始想问题，这几秒足够预热完成，回答时直接拿现成连接。

    为什么不出声播「我在」：本机已经有 ding() 提示音，用户听到就知道开口。
    再叠一句 TTS 反而会盖住开头几个字，把半双工体验搞坏。
    """
    try:
        E = tts_mod()
        # 必须直接碰连接池：tts_get 命中缓存时根本不会建连，预热就白做了。
        # 拿一条连接发极短音再放回；池空就新建。
        t0 = time.time()
        s = E._pool_get(4, False)
        if s is None:
            s = E._connect(timeout=E._CONNECT_TIMEOUT)
        try:
            E._synth_on(s, "嗯", "zh-CN-XiaoyiNeural",
                        TTS_TUNE["fish"][0], TTS_TUNE["fish"][1], 8)
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            s = E._connect(timeout=E._CONNECT_TIMEOUT)
        E._pool_put(s)
        log("tts 唤醒预热 %.2fs ip=%s" % (time.time() - t0, E._IP_CACHE["ip"]))
    except Exception as e:
        log("tts 唤醒预热失败（不影响）: %s" % e)


BL_PATH = "/sys/class/leds/lcd-backlight/brightness"
_CLEAN_ENV = None


def android_env():
    """去掉 Termux 的 LD_LIBRARY_PATH 再启子进程

    py.sh 给了解释器 LD_LIBRARY_PATH=.../com.termux/files/usr/lib，这个变量会
    原样传给子进程。`input` 底层是 app_process，动态链接时去 Termux 目录捞到
    了另一份 liblzma，符号对不上直接挂：
        CANNOT LINK EXECUTABLE "app_process": cannot locate symbol
        "XzUnpacker_Construct" referenced by "/system/lib/libunwind.so"
    表现就是 input 静默失败、屏幕怎么都不灭。
    """
    global _CLEAN_ENV
    if _CLEAN_ENV is None:
        _CLEAN_ENV = {k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"}
    return _CLEAN_ENV


def apply_brightness():
    """开机把亮度压到护眼档：开自动亮度 + 基准调暗。

    这台机原厂背光默认拉满 255，小屏在室内刺眼。设备有光线传感器，
    所以开自动亮度让环境光自己调，再用 adj=-0.5 把整体基准压暗。
    settings 是系统设置，重启服务后仍会保留（除非恢复出厂）。
    """
    cmds = ("settings put system screen_brightness_mode 1",
            "settings put system screen_auto_brightness_adj -0.5",
            "settings put system screen_brightness 60")
    for c in cmds:
        try:
            subprocess.Popen(["/system/bin/sh", "-c", c],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env=android_env())
        except Exception:
            pass
    log("亮度：自动模式 + 基准 -0.5")


def screen_on():
    """读背光判断屏幕亮没亮；读不到就当亮着，别乱注入按键"""
    try:
        with open(BL_PATH) as f:
            return int(f.read().strip() or "0") > 0
    except Exception:
        return True


def wake_screen():
    """息屏状态下被叫醒：点亮屏幕并把界面叫回前台

    本机没有 SystemUI，也没有锁屏，KEYCODE_WAKEUP(224) 直接就能亮。
    用 Popen 不等结果，免得按键注入慢吞吞地拖住对话。
    """
    if screen_on():
        return
    try:
        subprocess.Popen(
            ["/system/bin/sh", "-c",
             "input keyevent 224; sleep 0.4; am start -n com.dafeiyu.home/.MainActivity"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=android_env())
        log("wake: 屏幕是灭的，已点亮")
    except Exception as e:
        log("wake: 点屏失败 %s" % e)


def touch_activity():
    """有人说/碰了一下：把息屏倒计时清零"""
    global _last_act
    _last_act = time.time()


def wake_watch():
    """唤醒开关的兜底。

    前端播 TTS 时会先 /api/wake {active:false} 把唤醒压住，防止音箱听见自己
    说话又醒一次；播完再打开。这套配合平时没问题，但它自己的定时器一旦没跑
    成（音频被打断、页面重载、服务正好在重启），唤醒就永远关着 —— 用户看到
    的现象是「喊破喉咙也不理，点麦克风却好用」。实测真的踩到过。
    所以这里兜一层：关掉超过 60 秒就强制恢复。
    """
    while True:
        time.sleep(5)
        try:
            if STATE.get("wake"):
                continue
            off = STATE.get("wake_off_at") or 0.0
            if off and time.time() - off > 60.0:
                STATE["wake"] = True
                STATE["wake_off_at"] = 0.0
                log("唤醒被前端关了 %.0f 秒，强制恢复" % (time.time() - off))
        except Exception as e:
            log("wake_watch 出错 %s: %s" % (type(e).__name__, e))


def idle_watch():
    """没人操作就熄屏。麦克风不受影响：唤醒锁钉着，tinycap 照常跑。

    注意：这里绝对不能直接给 _last_act 赋值 —— 一旦赋值它就成了本函数的局部
    变量，上面那行读取会抛 UnboundLocalError，被 except 吞掉，屏幕永远不灭。
    统一走 touch_activity()。
    """
    while True:
        time.sleep(5)
        try:
            idle = time.time() - _last_act
            if idle < IDLE_OFF:
                continue
            if not screen_on():        # 已经灭了就别再按（POWER 是开关）
                touch_activity()
                continue
            subprocess.Popen(["/system/bin/sh", "-c", "input keyevent 26"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env=android_env())
            log("idle %.0f 秒没人操作，熄屏（唤醒服务照常）" % idle)
            touch_activity()
        except Exception as e:
            log("idle 看门出错 %s: %s" % (type(e).__name__, e))


def set_mode(m):
    if m not in PROMPTS:
        return
    STATE["mode"] = m
    touch_activity()
    push_event({"type": "mode", "mode": m})


# ---------------- 录音 ----------------
def read_pcm_all(path):
    with open(path, "rb") as f:
        d = f.read()
    i = d.find(b"data")
    if i >= 0:
        return d[i + 8:]
    # tinycap 被杀时来不及写头，前 44 字节是占位零
    return d[44:] if len(d) > 44 else b""


def record_raw(seconds):
    if os.path.exists(REC_WAKE):
        try:
            os.remove(REC_WAKE)
        except OSError:
            pass
    subprocess.run(["/vendor/bin/tinycap", REC_WAKE, "-D", "0", "-d", "2", "-c", "4",
                    "-r", str(SR), "-b", "16", "-T", str(seconds)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=seconds + 5)
    try:
        raw = read_pcm_all(REC_WAKE)
    except OSError:
        return None, 0
    if not raw:
        return None, 0
    pcm = array.array("h")
    pcm.frombytes(raw[:len(raw) // 2 * 2])
    return pcm, 4


def _record_once(max_sec, min_sec, silence, thresh, min_after_voice=None):
    """录音到说完自动停。

    min_sec 是「从开始录音算至少要录多久」，唤醒后原来给 2.2s —— 为了等人想问题。
    但这会导致用户张口就说时也要干等满 2.2s。min_after_voice 是「从第一个字算起
    至少录多久」：一旦真的开始说话，就用这个更短的门槛，不再被 min_sec 拖住。
    """
    if os.path.exists(REC):
        try:
            os.remove(REC)
        except OSError:
            pass
    proc = subprocess.Popen(["/vendor/bin/tinycap", REC, "-D", "0", "-d", "2", "-c", "4",
                             "-r", str(SR), "-b", "16", "-T", str(int(max_sec) + 1)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    seen = 0
    started = False
    voice_t0 = None                    # 第一个字出现的时刻
    last_voice = t0
    first_seen = False
    while time.time() - t0 < max_sec:
        time.sleep(0.12)
        if not first_seen:
            # tinycap 抢不到麦克风时会立刻退出，别在这儿干等 6 秒
            if proc.poll() is not None:
                log("record: tinycap 退出 rc=%s" % proc.returncode)
                return None, 0
            if time.time() - t0 > 0.9 and not os.path.exists(REC):
                log("record: 0.9s 内没生成文件")
                break
        try:
            sz = os.path.getsize(REC)
        except OSError:
            continue
        first_seen = True
        if sz - seen < 8192:
            continue
        try:
            with open(REC, "rb") as f:
                f.seek(seen)
                chunk = f.read(sz - seen)
        except OSError:
            continue
        seen = sz
        arr = array.array("h")
        arr.frombytes(chunk[:len(chunk) // 2 * 2])
        pk = max((abs(v) for v in arr[0::4]), default=0)
        now = time.time()
        if pk > thresh:
            if not started:
                voice_t0 = now
            started = True
            last_voice = now
        elif started:
            # 静音够长；最短时长分两套：从开录算 or 从第一个字算
            quiet_enough = (now - last_voice) > silence
            if min_after_voice is None:
                long_enough = (now - t0) > min_sec
            else:
                long_enough = ((now - voice_t0) > min_after_voice
                               or (now - t0) > min_sec)   # 兜底：始终不超过原上限
            if quiet_enough and long_enough:
                break
    try:
        proc.kill()
        proc.wait(timeout=2)
    except Exception:
        pass
    time.sleep(0.10)
    try:
        raw = read_pcm_all(REC)
    except OSError:
        return None, 0
    if not raw:
        return None, 0
    pcm = array.array("h")
    pcm.frombytes(raw[:len(raw) // 2 * 2])
    return pcm, 4


# 静音判停：0.62 太保守，用户说完要白等半秒多才开播。
# 2026-11-22 用真人录音插入 300/400/500ms 句中停顿做回放验证：
#   0.62 / 0.45 都不误切；0.35 在 500ms 停顿处误切（早 2.64s）。
# 所以取 0.45 —— 安全且仍省 0.17s。
# 唤醒后那条路径单独放宽到 0.9（人喊完唤醒词会顿一下），不在这里改。
SILENCE_DEFAULT = 0.45


def record(max_sec=6.0, min_sec=1.0, silence=SILENCE_DEFAULT, thresh=700,
           min_after_voice=None):
    """说完自动停；抢不到麦克风时自动重试一次"""
    for i in range(2):
        pcm, nch = _record_once(max_sec, min_sec, silence, thresh, min_after_voice)
        if pcm:
            return pcm, nch
        log("record 第 %d 次没拿到音频" % (i + 1))
        if i == 0:
            time.sleep(0.45)
    return None, 0


def agc(pcm, target=24000, max_gain=8.0):
    peak = max((abs(v) for v in pcm), default=0)
    if peak < 200:
        return pcm
    g = min(max_gain, target / float(peak))
    if g <= 1.02:
        return pcm
    out = array.array("h", [0]) * len(pcm)
    for i, v in enumerate(pcm):
        x = int(v * g)
        out[i] = 32767 if x > 32767 else (-32768 if x < -32768 else x)
    return out


def trim_silence(pcm, thresh=None, margin=int(SR * 0.18)):
    """按底噪自适应裁掉首尾静音

    固定阈值 350 在底噪峰值 450 的机器上等于没裁：整段 7 秒都送进识别，
    又慢又容易把噪音当字。这里先估底噪，再以它 1.8 倍作为人声门限。
    """
    n = len(pcm)
    if n == 0:
        return pcm
    win = int(SR * 0.02)
    peaks = []
    for i in range(0, n - win, win):
        peak = max(abs(v) for v in pcm[i:i + win])
        peaks.append((i, peak))
    if not peaks:
        return pcm
    if thresh is None:
        vals = sorted(p for _, p in peaks)
        floor = vals[int(len(vals) * 0.2)]      # 20 分位当底噪
        thresh = max(380, int(floor * 3.0))
    first, last = 0, n
    for i, peak in peaks:
        if peak > thresh:
            first = max(0, i - margin)
            break
    for i, peak in reversed(peaks):
        if peak > thresh:
            last = min(n, i + win + margin)
            break
    if last - first < int(SR * 0.3):            # 裁过头就退回原样
        return pcm
    return pcm[first:last]


def pick_channel(pcm, nch):
    best, best_rms = 0, -1
    for c in range(nch):
        ch = pcm[c::nch]
        r = (sum(v * v for v in ch[::16]) / max(1, len(ch[::16]))) ** 0.5
        if r > best_rms:
            best, best_rms = c, r
    return pcm[best::nch], best, best_rms


def mix4(pcm, nch):
    """四通道求和平均

    实测同一段真人录音：单通道识别成「和预防与」，四通道平均识别成「肥鱼」。
    各路麦克风的噪声互不相关，叠加后被压掉，人声是相关的会留下来。
    """
    if nch < 2:
        return pcm
    chs = [pcm[c::nch] for c in range(nch)]
    n = min(len(c) for c in chs)
    if nch == 4:
        c0, c1, c2, c3 = (x[:n] for x in chs)
        return array.array("h", [(p + q + r + s) >> 2 for p, q, r, s in zip(c0, c1, c2, c3)])
    if nch == 2:
        c0, c1 = (x[:n] for x in chs)
        return array.array("h", [(p + q) >> 1 for p, q in zip(c0, c1)])
    return array.array("h", [sum(v) // nch for v in zip(*chs)])


def _mix_raw(raw, nch=4):
    """把一段交织的原始字节直接混成单声道数组"""
    a = array.array("h")
    a.frombytes(raw[:len(raw) // (2 * nch) * (2 * nch)])
    return mix4(a, nch)


def finish(pcm, nch):
    mono = mix4(pcm, nch)
    peak = max((abs(v) for v in mono), default=0)
    if peak < 300 and nch > 1:
        # 相位抵消等极端情况：退回最响的那一路
        single, best, rms = pick_channel(pcm, nch)
        sp = max((abs(v) for v in single), default=0)
        if sp > peak:
            log("  mix 失败(peak=%d)，改用 ch%d peak=%d" % (peak, best, sp))
            mono, peak = single, sp
    try:
        with wave.open(RAW_KEEP, "wb") as o:
            o.setnchannels(1); o.setsampwidth(2); o.setframerate(SR)
            o.writeframes(mono.tobytes())
    except Exception:
        pass
    mono = trim_silence(mono)
    mono = agc(mono)
    peak2 = max((abs(v) for v in mono), default=0)
    log("  mix peak=%d -> agc %d, %.2fs" % (peak, peak2, len(mono) / SR))
    return mono, peak


# ---------------- ASR ----------------
def init_asr():
    lib = ctypes.CDLL(LIB)
    for n, r, a in [
        ("vosk_model_new", ctypes.c_void_p, [ctypes.c_char_p]),
        ("vosk_model_free", None, [ctypes.c_void_p]),
        ("vosk_recognizer_new", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_float]),
        ("vosk_recognizer_free", None, [ctypes.c_void_p]),
        ("vosk_recognizer_reset", None, [ctypes.c_void_p]),
        ("vosk_recognizer_accept_waveform", ctypes.c_int, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]),
        ("vosk_recognizer_final_result", ctypes.c_char_p, [ctypes.c_void_p]),
        ("vosk_recognizer_partial_result", ctypes.c_char_p, [ctypes.c_void_p]),
    ]:
        f = getattr(lib, n); f.restype = r; f.argtypes = a

    t0 = time.time()
    model = lib.vosk_model_new(MODEL.encode())
    rec = lib.vosk_recognizer_new(model, float(SR))
    _asr.update(lib=lib, model=model, rec=rec)
    log("ASR ready in %.1fs" % (time.time() - t0))

    t0 = time.time()
    silence = b"\x00\x00" * SR
    lib.vosk_recognizer_accept_waveform(rec, silence, len(silence))
    lib.vosk_recognizer_final_result(rec)
    lib.vosk_recognizer_reset(rec)
    log("warmup %.1fs" % (time.time() - t0))


def asr_decode(pcm):
    """返回 (文本, 耗时, 置信度)；置信度是逐字 conf 的均值，越低越不可靠"""
    lib, rec = _asr["lib"], _asr["rec"]
    raw = pcm.tobytes()
    t0 = time.time()
    CH = 4000
    for i in range(0, len(raw), CH):
        lib.vosk_recognizer_accept_waveform(rec, raw[i:i + CH], min(CH, len(raw) - i))
    d = json.loads(lib.vosk_recognizer_final_result(rec).decode())
    txt = d.get("text", "").replace(" ", "")
    words = d.get("result") or []
    conf = 0.0
    if words:
        conf = sum(float(w.get("conf", 0)) for w in words) / len(words)
    lib.vosk_recognizer_reset(rec)
    return fix_text(txt), time.time() - t0, conf


def asr_text(rec, mono):
    lib = _asr["lib"]
    raw = mono.tobytes()
    CH = 4000
    for i in range(0, len(raw), CH):
        lib.vosk_recognizer_accept_waveform(rec, raw[i:i + CH], min(CH, len(raw) - i))
    txt = json.loads(lib.vosk_recognizer_final_result(rec).decode()).get("text", "").replace(" ", "")
    lib.vosk_recognizer_reset(rec)
    return fix_text(txt)


# ---------------- 唤醒 ----------------
# Vosk 小模型对专有名词很吃力，实测「召唤梁圣」会被听成「就会两胜」，
# 所以按同音字组合做匹配，而不是只认那一个写法。
FEI = "肥飞非费菲"
YU = "鱼渔余于愉腴育瑜"
LIANG = "梁良两量凉亮粮谅"
SHENG = "圣胜生声盛升性兴星姓省"

FISH_PAIRS = tuple(a + b for a in FEI for b in YU)
SAGE_PAIRS = tuple(a + b for a in LIANG for b in SHENG)
NAME_WORDS = FISH_PAIRS + SAGE_PAIRS + ("大肥鱼",)

# 「召唤」本身也常被听错，一并容错
SWITCH_WORDS = ("召唤", "切换", "照换", "找换", "就会", "召回", "叫唤")

# 唤醒用「限定词表」识别器：只可能输出这几句，搜索空间从几万词缩到十几句，
# 又省 CPU 又准。[unk] 必须保留，否则随便说句话都会被硬掰成唤醒词。
WAKE_GRAMMAR = json.dumps([
    # 这个中文模型是按「字」切的词表，必须用空格分开写；
    # 实测写成 "肥鱼" 会被判为未登录词整句丢弃，只剩 [unk]。
    "肥 鱼", "肥 鱼 肥 鱼", "大 肥 鱼", "你 好 肥 鱼",
    "梁 圣", "梁 圣 梁 圣", "你 好 梁 圣",
    "召 唤 梁 圣", "召 唤 大 肥 鱼", "切 换 梁 圣", "切 换 大 肥 鱼",
    # 同音写法：小模型分不清 梁/良、圣/性、肥/飞，与其让它只能吐 [unk]，
    # 不如把这些写法也放进词表，识别出来之后再按近音对归并。
    "良 性", "良 圣", "梁 性", "凉 圣", "粮 圣",
    "飞 鱼", "肥 余", "非 鱼", "大 飞 鱼",
    "召 唤 良 性", "召 唤 大 飞 鱼", "切 换 良 性", "切 换 大 飞 鱼",
    "[unk]",
], ensure_ascii=False)
FILLERS = ("你好", "您好", "喂", "嗨", "哎", "嗯", "那个", "在吗", "在不在", "呀", "啊")

# 「梁圣」被通用识别器听成「良性」、「大肥鱼」听成「大飞鱼」是常态，
# 所以名字判定除了精确匹配，还要认「近音字紧挨着出现」这种写法。
_SAGE_HEAD = set("梁良凉粮两亮量谅")
_SAGE_TAIL = set("圣胜生声省性兴星姓升绳盛")
_FISH_HEAD = set("肥飞非肺废费匪")
_FISH_TAIL = set("鱼余于玉雨与语遇育")


def _find_fuzzy_name(t):
    """按近音字对找名字，返回 (名字结束下标, 'fish'|'sage')；找不到返回 (-1, None)"""
    best_i, best_k = -1, None
    for i in range(len(t) - 1):
        a, b = t[i], t[i + 1]
        k = None
        if a in _SAGE_HEAD and b in _SAGE_TAIL:
            k = "sage"
        elif a in _FISH_HEAD and b in _FISH_TAIL:
            k = "fish"
        if k and i + 2 > best_i:
            best_i, best_k = i + 2, k
    return best_i, best_k


def _name_of(t):
    """先精确、后近音，返回 'fish'/'sage'/None"""
    end, who = _find_name(t)
    if end < 0:
        end, who = _find_fuzzy_name(t)
    return who



def _has_fish(t):
    return any(p in t for p in FISH_PAIRS)


def _has_sage(t):
    return any(p in t for p in SAGE_PAIRS)


def _strip_name(t):
    for w in sorted(NAME_WORDS, key=len, reverse=True):
        t = t.replace(w, "")
    for w in SWITCH_WORDS + FILLERS:
        t = t.replace(w, "")
    return t.strip("，。！？、,.!?~～ 　")


def _find_name(t):
    """找最后一次出现的名字，返回 (名字结束下标, 'fish'|'sage')；找不到返回 (-1, None)

    必须用 rfind：分片结果会把整段话累积在一起，问题永远在唤醒词之后，
    唤醒词之前那些字多半是噪音被识别成的残渣，不能当成问题。
    """
    best_i, best_k = -1, None
    for p in FISH_PAIRS:
        i = t.rfind(p)
        if i >= 0 and i + len(p) > best_i:
            best_i, best_k = i + len(p), "fish"
    for p in SAGE_PAIRS:
        i = t.rfind(p)
        if i >= 0 and i + len(p) > best_i:
            best_i, best_k = i + len(p), "sage"
    return best_i, best_k


def _clean_tail(t):
    for w in SWITCH_WORDS + FILLERS:
        t = t.replace(w, "")
    return t.strip("，。！？、,.!?~～ 　")


def _push_wake(q):
    # 方案D：唤醒即预热 TTS 连接，异步，不挡住后续录音
    threading.Thread(target=tts_wake_prewarm, daemon=True).start()
    # 一口气把「肥鱼肥鱼，今天天气怎样」说完时，q 里已经带了问题，事件直接带上
    if len(q) >= 4:
        push_event({"type": "wake", "q": q})
        return ("wake", q)
    push_event({"type": "wake"})
    return ("wake", "")


# 严格唤醒白名单（2026-11-24）：
# 实测限定词表会把噪音里凑巧的字序列拼成「你大肥鱼」并误命中，随后把周围人
# 说话（「到后面你的意思是…」）当问题发给大模型。用户明确要求：只有喊
# 「肥鱼肥鱼」「你好梁圣」这种完整唤醒语才拾音。所以对话唤醒只认下面这些
# 明确形式；裸名字、近音碎字一律不算。切人设（召唤/切换）单独走，不拾音。
_STRICT_WAKE = (
    "肥鱼肥鱼", "肥鱼肥余", "费鱼肥鱼",
    "你好肥鱼", "您好肥鱼", "你好大肥鱼", "您好大肥鱼",
    "你好梁圣", "您好梁圣", "梁圣梁圣", "良圣良圣",
)
# 唤醒词专用近音归一：只用在唤醒判定，不碰通用 ASR 输出。
# 真人实测「肥鱼肥鱼」Vosk 会听成「肥育肥鱼」/「肥腴肥鱼」，不归一就唤醒失败。
_WAKE_FIX = (("肥育", "肥鱼"), ("肥雨", "肥鱼"), ("肥语", "肥鱼"),
             ("肥腴", "肥鱼"), ("肥余", "肥鱼"), ("费鱼", "肥鱼"),
             ("良圣", "梁圣"), ("梁胜", "梁圣"), ("凉圣", "梁圣"))


def _strict_wake_hit(t):
    """返回 (是否严格命中, 名字结束下标, 'fish'|'sage')；没命中返回 (False,-1,None)。"""
    best_end, best_who = -1, None
    for w in _STRICT_WAKE:
        i = t.find(w)
        if i < 0:
            continue
        who = "sage" if ("圣" in w or "良" in w) else "fish"
        if i + len(w) > best_end:
            best_end, best_who = i + len(w), who
    return (best_end >= 0), best_end, best_who


def classify_wake(t):
    """纯判定（无副作用）：返回 (动作, 人设, 问题)。
    动作: 'mode' 切人设 / 'ask' 唤醒拾音 / 'reject' 不理会。
    handle_wake_text 和 /api/route 都用它，保证自测和线上判定完全一致。
    """
    t2 = (t or "").replace(" ", "")
    if not t2:
        return ("reject", None, "")
    # 只在唤醒判定层做近音归一，不影响通用识别结果
    for a, b in _WAKE_FIX:
        t2 = t2.replace(a, b)

    # 切人设：只在明确的「召唤/切换 + 名字」时才切，不拾音。
    if any(w in t2 for w in SWITCH_WORDS):
        hf, hs = _has_fish(t2), _has_sage(t2)
        if hf or hs:
            return ("mode", "sage" if (hs and not hf) else "fish", "")
        return ("reject", None, "")

    # 对话唤醒：必须严格白名单命中
    hit, end, who = _strict_wake_hit(t2)
    if not hit:
        return ("reject", None, "")
    return ("ask", who, _clean_tail(t2[end:]))


def handle_wake_text(t):
    """命中返回 ("wake", 问题) / ("mode", 模式)；没命中返回 False"""
    act, who, q = classify_wake(t)
    if act == "reject":
        return False
    if act == "mode":
        set_mode(who)
        return ("mode", STATE["mode"])
    # 严格命中即唤醒拾音。若喊的是另一人设且没带问题，顺便切过去（不额外播报）。
    if who == "sage" and STATE["mode"] != "sage" and not q:
        set_mode("sage")
    elif who == "fish" and STATE["mode"] != "fish" and not q:
        set_mode("fish")
    return _push_wake(q)


def _ch_peaks(raw):
    a = array.array("h")
    a.frombytes(raw)
    return [max((abs(v) for v in a[c::4]), default=0) for c in range(4)]


def _mono_arr(raw, ch):
    a = array.array("h")
    a.frombytes(raw)
    return a[ch::4]


def _scale(arr, gain):
    """按倍数放大并限幅到 int16"""
    g = int(gain * 256)
    return array.array("h", (max(-32768, min(32767, (v * g) >> 8)) for v in arr)).tobytes()


def _wav_hdr(n, ch=4, bits=16):
    ba = ch * bits // 8
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE" + b"fmt "
            + struct.pack("<IHHIIHH", 16, 1, ch, SR, SR * ba, ba, bits)
            + b"data" + struct.pack("<I", n))


_RING_MAX = SR * 8 * 8        # 最近 8 秒原始 4 声道（唤醒前的话要能捡回来）
_PRE_MAX = SR * 8 * 3         # 选通道前的静音缓存上限


def make_wake_rec(lib, model):
    """优先用限定词表的识别器，失败就退回通用识别器"""
    try:
        lib.vosk_recognizer_new_grm.restype = ctypes.c_void_p
        lib.vosk_recognizer_new_grm.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_char_p]
        rec = lib.vosk_recognizer_new_grm(model, float(SR), WAKE_GRAMMAR.encode())
        if rec:
            # 热身，不然冷启动前几秒不吐分片
            lib.vosk_recognizer_accept_waveform(rec, b"\x00\x00" * SR, SR * 2)
            lib.vosk_recognizer_final_result(rec)
            lib.vosk_recognizer_reset(rec)
            log("wake: 限定词表识别器已启用")
            return rec
    except Exception as e:
        log("wake: new_grm 不可用 %s" % e)
    log("wake: 退回通用识别器")
    rec = lib.vosk_recognizer_new(model, float(SR))
    lib.vosk_recognizer_accept_waveform(rec, b"\x00\x00" * SR, SR * 2)
    lib.vosk_recognizer_final_result(rec)
    lib.vosk_recognizer_reset(rec)
    return rec


def stream_wake(rec, lib, max_sec=90):
    """连续录音 + 流式识别，命中唤醒词立即返回

    返回 ("wake", 问题) / ("mode", 模式) / False
    麦克风在 20%~30% 音量下峰值只有 2000 出头，Vosk 会听成噪声，
    所以这里做自适应增益（AGC）：安静时放大，够响就不动。
    """
    path = WAKE_STREAM
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    proc = subprocess.Popen(
        ["/vendor/bin/tinycap", path, "-D", "0", "-d", "2", "-c", "4",
         "-r", str(SR), "-b", "16", "-T", str(int(max_sec))],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lib.vosk_recognizer_reset(rec)
    # tinycap 若因麦克风被占而立刻退出，要能看见，否则会静默空转
    time.sleep(0.25)
    if proc.poll() is not None:
        log("wake: tinycap 启动失败 rc=%s（麦克风可能被占用）" % proc.returncode)
        return False
    off = 44          # 跳过 wav 头
    tail = b""        # 不足一帧的残字节
    ring = collections.deque(maxlen=70)   # 最近约 10 秒原始音频，出错时落盘分析
    ch = None
    gain = 1.0
    result = False
    last_part = ""
    last_dump = 0.0
    loud_pk = 0       # 近一秒内的响度（缓慢衰减），用来挡住噪音幻觉
    last_voice = time.time()
    # ---- 能量门控 ----
    # 连续把 16k 音频灌进 Vosk，在 4×A35 上要吃掉 0.4 个核；可一间屋里绝大
    # 多数时间根本没人说话，那些静音块解码完全是白烧电。实测底噪峰值 ≤300，
    # 说话峰值 1000~2200，两者差得远，门限卡在 500 很安全。
    nf = -1.0         # 底噪峰值估计（首块直接取，之后快跟下慢跟上）
    gate = False      # 门控开没开
    flush_pre = False # 开闸那一块要不要先补预卷
    pre = collections.deque(maxlen=5)   # 开闸前预卷（约 0.6 秒原始四声道）
    quiet = 0.0       # 连续安静时长（秒）
    n_block = 0       # 统计：总块数
    n_gate = 0        # 统计：真正送进 Vosk 的采样点数
    fed_gate = 0      # 本次开闸喂进去的采样点数
    gate_peak = 0     # 本次开闸期间的最大响度（混音后）
    GATE_FLOOR = WAKE_GATE_FLOOR[0]
    thr = GATE_FLOOR
    # 诊断用：闲置块峰值落在哪个区间，用来校准门限（WAKE_DEBUG 时打印）
    hist = [0, 0, 0, 0, 0]
    mx = 0
    t0 = time.time()
    try:
        while proc.poll() is None:
            time.sleep(0.15)
            if STATE["busy"] or not STATE["wake"]:
                break
            if time.time() - t0 > max_sec - 3:
                break
            try:
                with open(path, "rb") as f:
                    f.seek(off)
                    new = f.read()
            except OSError:
                continue
            if not new:
                continue
            off += len(new)
            buf = tail + new
            n = len(buf) - (len(buf) % 8)     # 4 声道 × 2 字节 = 8
            tail, buf = buf[n:], buf[:n]
            if not buf:
                continue
            ring.append(buf)
            n_block += 1
            now = time.time()

            # ---- 廉价门控 ----
            # 只做「四路各取峰谷」：array 切片 + max/min 全在 C 里跑，不用把四路
            # 混成单声道，也不用逐点扫。实测闲置时这一步比旧版省一个数量级。
            if not gate:
                a0 = array.array("h")
                a0.frombytes(buf)
                # 只看每路 1/16 的采样点（相当于 1kHz），够抓人声起头了；
                # 全量 9600 点跑 max/min 每块要多花 8 倍时间，白烧电。
                rpk = 0
                for c in range(4):
                    seg = a0[c::16]
                    if not seg:
                        continue
                    hi = max(seg)
                    lo = min(seg)
                    v = hi if hi > -lo else -lo
                    if v > rpk:
                        rpk = v
                # 诊断：记录最近拾音峰值（3 秒窗口自然衰减）
                if rpk > LIVE_PEAK["max"] or time.time() - LIVE_PEAK["at"] > 3:
                    LIVE_PEAK["max"] = rpk
                    LIVE_PEAK["at"] = time.time()
                if nf < 0:
                    # 首块就用它定底噪，但万一开口就是人声（或一声巨响），
                    # 不能把门限永久抬高，否则这一整段唤醒就废了
                    nf = rpk if rpk < GATE_FLOOR else 300.0
                elif rpk < nf:
                    nf += (rpk - nf) * 0.25
                elif rpk < nf * 2.5:
                    nf += (rpk - nf) * 0.02
                thr = GATE_FLOOR if nf * 2.2 < GATE_FLOOR else nf * 2.2
                if WAKE_DEBUG:
                    if rpk > mx:
                        mx = rpk
                    if rpk <= 300:
                        hist[0] += 1
                    elif rpk <= 500:
                        hist[1] += 1
                    elif rpk <= 900:
                        hist[2] += 1
                    elif rpk <= 1500:
                        hist[3] += 1
                    else:
                        hist[4] += 1
                if rpk <= thr:
                    pre.append(buf)          # 只存不拼，开闸时一次性 join
                    continue
                gate = True
                quiet = 0.0
                fed_gate = 0
                gate_peak = 0
                flush_pre = True          # 等这一块的响度算完再补预卷
                if WAKE_DEBUG:
                    log("wake 开闸 pk=%d nf=%.0f" % (rpk, nf))

            # ---- 闸开了才做重活：混音、算响度、喂 Vosk ----
            arr = _mix_raw(buf, 4)
            if not arr:
                continue
            pk = 0
            for v in arr:
                if v < 0:
                    v = -v
                if v > pk:
                    pk = v
            loud_pk = max(pk, int(loud_pk * 0.85))
            if pk > gate_peak:            # 整句的最大响度，命中判定看它
                gate_peak = pk
            if pk > 350:
                last_voice = now
            # 增益跟着"近一秒有多响"走。开口第一块必须快攻：慢悠悠地爬的话，
            # 一句「肥鱼」说完增益才到 2.0（17:00 实测），大半句都泡在低电平里。
            if loud_pk > 600:
                target = min(6.0, max(1.0, 24000.0 / loud_pk))
                gain += (target - gain) * (0.6 if flush_pre else 0.25)
            if flush_pre:
                flush_pre = False
                if pre:                   # 补预卷，别把字头切掉（用刚算出来的增益）
                    pa = _mix_raw(b"".join(pre), 4)
                    pre.clear()
                    pm = _scale(pa, gain) if gain > 1.05 else pa.tobytes()
                    lib.vosk_recognizer_accept_waveform(rec, pm, len(pm))
                    n_gate += len(pm) // 2
                    fed_gate += len(pm) // 2
            mono = _scale(arr, gain) if gain > 1.05 else arr.tobytes()

            # 注意这里用的是「开闸门限的一半」。开闸要 800 是为了不被环境噪音
            # 骗开，但闸已经开着的时候还拿 800 当"有没有声音"就太苛刻了：
            # 实测 20% 音量下 TTS/人声念「召唤大肥鱼」，"大肥"峰值 893 刚过线，
            # "鱼"字轻一点就掉到 500 上下，于是被判成静音、0.9 秒后关闸，
            # 结果只认出「召唤大肥」，整句白费。400 这条线只用来续命，不放闸。
            if pk <= thr * 0.5:
                quiet += len(arr) / SR
                if quiet > 1.2:           # 说完就关闸并清空，残字不会攒着
                    gate = False
                    # 分片结果会在最后一个字之前停住（"肥鱼肥"），真正的终稿要
                    # 从 final_result 拿。先判终稿，再 reset。
                    fin = ""
                    try:
                        d = json.loads(lib.vosk_recognizer_final_result(rec).decode())
                        fin = fix_text(d.get("text", "").replace(" ", "").replace("[unk]", ""))
                    except Exception:
                        pass
                    if fin and len(fin) >= 2 and gate_peak >= 800 and fin != last_part:
                        if WAKE_DEBUG:
                            log("wake 终稿 %r pk=%d" % (fin, gate_peak))
                        rr = handle_wake_text(fin)
                        if rr:
                            result = rr
                            try:
                                raw = b"".join(ring)
                                with open(WAKE_PRE, "wb") as f:
                                    f.write(_wav_hdr(len(raw), 4))
                                    f.write(raw)
                            except OSError:
                                pass
                            break
                    lib.vosk_recognizer_reset(rec)
                    if WAKE_DEBUG and fed_gate > 0:
                        # 把刚过去这段落盘：用 /api/replay 能判断"是音频本身不
                        # 行，还是门控把字切坏了"
                        try:
                            raw = b"".join(ring)
                            with open(GATE_LAST, "wb") as f:
                                f.write(_wav_hdr(len(raw), 4))
                                f.write(raw)
                        except OSError:
                            pass
                        log("wake 关闸 本段解码 %.1fs 末分片=%r"
                            % (fed_gate / float(SR), last_part))
                    last_part = ""
                    loud_pk = 0
                    if WAKE_DEBUG:
                        log("wake 关闸")
                    continue
            else:
                quiet = 0.0
            # 兜底：环境噪音把闸顶开时，靠"太久没变化"清一次
            if now - last_voice > 2.5 and last_part:
                lib.vosk_recognizer_reset(rec)
                gate = False
                last_part = ""
                loud_pk = 0
                continue

            lib.vosk_recognizer_accept_waveform(rec, mono, len(mono))
            n_gate += len(mono) // 2
            fed_gate += len(mono) // 2
            # 注意：分片结果的键是 "partial"，不是 "text"
            part = lib.vosk_recognizer_partial_result(rec).decode()
            part = json.loads(part).get("partial", "").replace(" ", "")
            part = fix_text(part.replace("[unk]", ""))
            if part and part != last_part:
                last_part = part
                if WAKE_DEBUG:
                    log("wake part %r pk=%d g=%.1f" % (part[-20:], pk, gain))
                if len(part) >= 2 and now - last_dump > 1.0:
                    last_dump = now
                    try:
                        raw = b"".join(ring)
                        with open(WAKE_LAST, "wb") as f:
                            f.write(_wav_hdr(len(raw)))
                            f.write(raw)
                    except OSError:
                        pass
            # 只有真的有人说话（近一秒够响）时才认这句话，避免噪音瞎猜出唤醒词
            if part and len(part) >= 2 and gate_peak >= 800:
                r = handle_wake_text(part)
                if r:
                    result = r
                    # 把唤醒前的音频留一份：用户常常是「先说问题、没反应、再喊名字」
                    try:
                        raw = b"".join(ring)
                        with open(WAKE_PRE, "wb") as f:
                            f.write(_wav_hdr(len(raw), 4))
                            f.write(raw)
                    except OSError:
                        pass
                    break
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            pass
        lib.vosk_recognizer_reset(rec)
        # 一次唤醒周期结束：把"到底喂了多少音频给 Vosk"打出来，用来量化门控收益
        try:
            total = n_block * 0.15
            fed = n_gate / float(SR)
            log("wake 收工 %.1fs 音频，实际解码 %.1fs（%.0f%%），结果=%r"
                % (total, fed, (fed / total * 100.0) if total > 0.1 else 0.0, result))
            if WAKE_DEBUG:
                log("  闲置块峰值分布 ≤300:%d ≤500:%d ≤900:%d ≤1500:%d >1500:%d  最大=%d nf=%.0f"
                    % (hist[0], hist[1], hist[2], hist[3], hist[4], mx, nf))
        except Exception:
            pass
    return result


def strip_names(t):
    for w in sorted(NAME_WORDS, key=len, reverse=True):
        t = t.replace(w, "")
    for w in SWITCH_WORDS + FILLERS:
        t = t.replace(w, "")
    return t.strip("，。！？、,.!?~～ 　")


def decode_file(path, strip=False, tail_sec=0):
    """把一个 wav 文件解码成文本（混音 + 裁静音 + AGC）

    tail_sec>0 时只取文件最后这么多秒。wake_pre.wav 是 60 秒的滚动缓冲，
    整段跑一遍混音要十来秒，用户那边就是「喊完名字、半天没动静」。
    """
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        total = w.getnframes()
        start = 0
        if tail_sec and tail_sec > 0:
            keep = int(SR * tail_sec)
            if total > keep:
                start = total - keep
                w.setpos(start)
        a = array.array("h")
        a.frombytes(w.readframes(total - start))
    mono = mix4(a, nch)
    peak = max((abs(v) for v in mono), default=0)
    mono = agc(trim_silence(mono))
    txt, dt, conf = asr_decode(mono)
    if strip:
        txt = strip_names(txt)
    return txt, peak, dt, conf


def replay_wake(path, chunk_ms=150):
    """把一段录音按 stream_wake 的算法回放一遍（不需要人说话也能验证唤醒逻辑）

    返回识别过程与最终判定，用来确认「唤醒词前的残渣」会不会被误当成问题。
    """
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        raw = w.readframes(w.getnframes())
    lib = _asr["lib"]
    rec = make_wake_rec(lib, _asr["model"])   # 和线上完全一致的识别器
    fr = nch * 2
    step = int(SR * chunk_ms / 1000) * fr
    ch = None
    gain = 1.0
    loud_pk = 0
    last_voice = 0.0
    last_part = ""
    result = False
    maxpk = 0
    timeline = []
    saved_mode = STATE["mode"]
    with EV_LOCK:
        n0 = len(EVENTS)
    for i, off in enumerate(range(0, len(raw), step)):
        buf = raw[off:off + step]
        buf = buf[:len(buf) - (len(buf) % fr)]
        if not buf:
            break
        arr = _mix_raw(buf, nch) if nch > 1 else array.array("h", buf)
        if ch is None:
            ch = 0
        pk = max((abs(v) for v in arr), default=0)
        maxpk = max(maxpk, pk)
        loud_pk = max(pk, int(loud_pk * 0.85))
        t = (i + 1) * chunk_ms / 1000.0
        if pk > 350:
            last_voice = t
        if loud_pk > 600:
            target = min(5.0, max(1.0, 24000.0 / loud_pk))
            gain += (target - gain) * 0.25
        if t - last_voice > 2.5 and last_part:
            lib.vosk_recognizer_reset(rec)
            last_part = ""
            loud_pk = 0
            timeline.append([round(t, 1), "(reset)"])
            continue
        mono = _scale(arr, gain) if gain > 1.05 else arr.tobytes()
        lib.vosk_recognizer_accept_waveform(rec, mono, len(mono))
        part = lib.vosk_recognizer_partial_result(rec).decode()
        part = fix_text(json.loads(part).get("partial", "").replace(" ", ""))
        if part and part != last_part:
            last_part = part
            timeline.append([round(t, 1), part, pk, round(gain, 1)])
        if part and len(part) >= 2 and loud_pk >= 800:
            r = handle_wake_text(part)
            if r:
                result = r
                timeline.append([round(t, 1), "HIT", str(r)])
                break
    lib.vosk_recognizer_free(rec)
    # 回放不能影响线上状态：模式和事件都还原
    STATE["mode"] = saved_mode
    with EV_LOCK:
        del EVENTS[n0:]
    return {"channel": ch, "result": result, "timeline": timeline[-14:],
            "dbg": {"nch": nch, "bytes": len(raw), "blocks": i + 1,
                    "maxpk": maxpk, "partials": len(timeline)}}


def wake_loop():
    lib = _asr["lib"]
    model = _asr["model"]
    rec = make_wake_rec(lib, model)
    log("wake loop ready")
    while True:
        try:
            if not STATE["wake"] or STATE["busy"]:
                time.sleep(0.25)
                continue
            if not _lock.acquire(timeout=0.4):
                continue
            t_s = time.time()
            try:
                r = stream_wake(rec, lib)
            finally:
                _lock.release()
            if not r:
                if time.time() - t_s < 1.5:
                    time.sleep(0.8)   # 会话异常地短，避免空转
                continue
            kind, val = r
            # 有人叫它：屏幕若是灭的，先点亮再往下走，不然用户对着黑屏听答案
            touch_activity()
            wake_screen()
            if kind == "mode":
                time.sleep(0.8)       # 刚切完主题，等前端画完再说
                continue
            if val:
                # 一句话里连问题都录进来了，直接作答
                time.sleep(0.35)
                answer_question(val)
            else:
                # 只喊了名字，服务端接着把这句话听完，不再让前端来回跑
                # 等提示音「叮」播完再开录（前端收到事件后立刻响），
                # 顺便等 tinycap 把麦克风彻底放开
                time.sleep(0.55)
                # 唤醒后只喊了名字这一路：
                #   min_sec=2.2 保留作为「一直不说话」时的最长耐心；
                #   但一旦开始说话，min_after_voice=0.5 就让判停立刻生效，
                #   不再让用户说完还要干等满 2.2s。silence 与按钮路径一致用 0.45
                #   （回放验证过 0.45 不误切 500ms 句中停顿）。
                do_turn(max_sec=7.0, min_sec=2.2, silence=SILENCE_DEFAULT,
                        from_wake=True, min_after_voice=0.5)
        except Exception:
            log("wake err", traceback.format_exc()[-300:])
            STATE["busy"] = False
            time.sleep(0.5)


# ---------------- DeepSeek ----------------
# token 用量与余额统计（右下角状态面板用）
# 进程重启归零；余额带缓存，避免每次请求都去查 DeepSeek。
USAGE_FILE = os.path.join(BASE, "usage.json")
USAGE = {"calls": 0, "prompt": 0, "completion": 0, "total": 0,
         "errors": 0, "last_at": 0.0, "started_at": time.time()}
BALANCE = {"value": None, "currency": "CNY", "at": 0.0, "err": ""}
BALANCE_TTL = 300.0          # 余额缓存 5 分钟
LLM_MODEL = "deepseek-chat"
GITHUB_REPO = "pandasoft2026/dafeiyu-smart-speaker"
GH_STARS = {"count": None, "at": 0.0, "err": ""}
GH_STARS_TTL = 1800.0        # star 变化慢，缓存 30 分钟
GH_URL = "https://api.github.com/repos/" + GITHUB_REPO


def get_github_stars(force=False):
    """查项目 GitHub star 数。失败返回上次值或 None，绝不影响对话。"""
    now = time.time()
    if not force and GH_STARS["count"] is not None and now - GH_STARS["at"] < GH_STARS_TTL:
        return dict(GH_STARS)
    try:
        req = Request(GH_URL, headers={"Accept": "application/vnd.github+json",
                                       "User-Agent": "dafeiyu-speaker"})
        with urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode())
        GH_STARS["count"] = int(d.get("stargazers_count") or 0)
        GH_STARS["err"] = ""
        GH_STARS["at"] = now
    except Exception as e:
        GH_STARS["err"] = type(e).__name__
        if not GH_STARS["at"]:
            GH_STARS["at"] = now
    return dict(GH_STARS)


def _load_usage():
    """从文件恢复累计用量——服务一天会被看门狗拉起几次，不能每次归零。"""
    try:
        with open(USAGE_FILE) as f:
            d = json.load(f)
        for k in ("calls", "prompt", "completion", "total", "errors"):
            USAGE[k] = int(d.get(k) or 0)
        if d.get("started_at"):
            USAGE["started_at"] = float(d["started_at"])
    except Exception:
        pass


def _save_usage():
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump({k: USAGE[k] for k in
                       ("calls", "prompt", "completion", "total", "errors", "started_at")},
                      f)
    except Exception:
        pass


_load_usage()


def _record_usage(usage):
    """把一次 API 返回的 usage 累加进全局计数，并落盘。"""
    if not isinstance(usage, dict):
        return
    try:
        USAGE["calls"] += 1
        USAGE["prompt"] += int(usage.get("prompt_tokens") or 0)
        USAGE["completion"] += int(usage.get("completion_tokens") or 0)
        USAGE["total"] += int(usage.get("total_tokens") or 0)
        USAGE["last_at"] = time.time()
        _save_usage()
    except Exception:
        pass


def get_balance(force=False):
    """查 DeepSeek 账户余额。失败返回上次成功值或 None，绝不影响对话。"""
    now = time.time()
    if not force and BALANCE["value"] is not None and now - BALANCE["at"] < BALANCE_TTL:
        return dict(BALANCE)
    key = load_key()
    if not key:
        BALANCE["err"] = "未配置密钥"
        return dict(BALANCE)
    try:
        req = Request("https://api.deepseek.com/user/balance",
                      headers={"Authorization": "Bearer " + key})
        with urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode())
        # 返回形如 {"is_available":true,"balance_infos":[{"currency":"CNY","total_balance":"12.34"}]}
        infos = d.get("balance_infos") or []
        if infos:
            BALANCE["value"] = infos[0].get("total_balance")
            BALANCE["currency"] = infos[0].get("currency", "CNY")
        BALANCE["err"] = ""
        BALANCE["at"] = now
    except Exception as e:
        BALANCE["err"] = type(e).__name__
        if not BALANCE["at"]:
            BALANCE["at"] = now       # 失败也设个时间，避免每次都重试拖慢
    return dict(BALANCE)


def load_key():
    try:
        with open(API_KEY_FILE) as f:
            return f.read().strip().splitlines()[0].strip()
    except Exception:
        return ""


def _weather_context():
    """把当前天气塞进 system prompt，让「今天天气怎么样」有数据可答。
    复用 market.py 的缓存（天气 10min），不会每次对话都去抓接口。"""
    try:
        import market as _mk
        d = _mk.get_dashboard().get("weather") or {}
        if d.get("temp") is None:
            return ""
        days = d.get("days") or []
        today = days[0] if days else {}
        forecast = "；".join(
            "%s %s %s~%s°C" % (x.get("day", "?"), x.get("desc", "?"),
                              round(x["lo"]) if x.get("lo") is not None else "?",
                              round(x["hi"]) if x.get("hi") is not None else "?")
            for x in days[:5])
        return ("\n\n【实时信息，回答天气问题时要用到】地点：%s；当前 %s°C %s；"
                "未来五天：%s。这是真实数据，别再说「我看不到天气」，"
                "问哪天就按上面哪天答，别自己编。"
                % (d.get("city", "成都"), round(d["temp"]), d.get("desc", ""),
                   forecast or "暂无"))
    except Exception:
        return ""


def ask_deepseek(text, history=None):
    key = load_key()
    if not key:
        return "（还没配置接口密钥）"
    msgs = [{"role": "system", "content": PROMPTS.get(STATE["mode"], PROMPTS["fish"]) + _weather_context()}]
    if history:
        msgs.extend(history[-6:])
    msgs.append({"role": "user", "content": text})
    body = json.dumps({"model": LLM_MODEL, "messages": msgs,
                       "temperature": 0.7 if STATE["mode"] == "fish" else 0.4,
                       "max_tokens": 200}).encode()
    req = Request("https://api.deepseek.com/chat/completions", data=body,
                  headers={"Content-Type": "application/json",
                           "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        # 20 秒够 DeepSeek 正常回一轮了（实测 0.9~2 秒）。原来给 40 秒，
        # 断网或信号差的时候用户要干等半分钟，看着就像死机。
        with urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        _record_usage(d.get("usage"))
        ans = d["choices"][0]["message"]["content"].strip()
    except URLError as e:
        ans = "网络好像不太通呢，%s" % e
    except Exception as e:
        ans = "出了点小问题：%s" % e
    log("deepseek %.1fs" % (time.time() - t0))
    return ans


# ---------------- 流式回答：第一句生成完就推给前端开播 ----------------
# 为什么必须做这个：实测非流式拿全文要 0.97s，TTS 全文又要 2.28s，
# 两者串行 = 3.25s，加上 ASR 一共四秒多，用户说完要干等。
# 流式实测首句 0.68s、全文 0.81s：本身只快 0.3s，但首句一出来就能
# 立刻送 TTS，后面几句在它播放期间并行合成 —— 省掉的是整段等待。
#
# 事件协议（前端 poll 消费）：
#   {"type":"heard",  "q": ...}                        听到什么（沿用）
#   {"type":"partial","q":...,"text":...,"idx":0}       逐句，前端立刻播
#   {"type":"turn",   "q":...,"answer":...,"streamed":1} 收尾（只记聊天，不重播）
SENT_END = "。！？；!?;\n"


def _split_stream_sentence(buf, final=False):
    """从累积文本里切出完整句子。返回的 (句子列表, 剩余)。"""
    out = []
    start = 0
    for i, ch in enumerate(buf):
        if ch in SENT_END:
            seg = buf[start:i + 1].strip()
            if seg:
                out.append(seg)
            start = i + 1
    rest = buf[start:]
    if final and rest.strip():
        out.append(rest.strip())
    return out, rest


def ask_deepseek_stream(text, on_sentence=None, history=None):
    """流式调用 DeepSeek。每切出一句回调一次，返回 (全文, 首句耗时, 全文耗时)。

    on_sentence(sentence, idx) 里可以立刻推事件让前端开播。
    失败时回退到非流式 ask_deepseek，保证有答案。
    """
    key = load_key()
    if not key:
        return "（还没配置接口密钥）", 0.0, 0.0
    msgs = [{"role": "system", "content": PROMPTS.get(STATE["mode"], PROMPTS["fish"]) + _weather_context()}]
    if history:
        msgs.extend(history[-6:])
    msgs.append({"role": "user", "content": text})
    body = json.dumps({"model": LLM_MODEL, "messages": msgs,
                       "stream": True,
                       "stream_options": {"include_usage": True},
                       "temperature": 0.7 if STATE["mode"] == "fish" else 0.4,
                       "max_tokens": 200}).encode()
    req = Request("https://api.deepseek.com/chat/completions", data=body,
                  headers={"Content-Type": "application/json",
                           "Authorization": "Bearer " + key})
    t0 = time.time()
    buf = ""
    full = []                 # 另存全文：buf 每切出一句就清空，不能用它当答案
    first_dt = 0.0
    idx = 0
    try:
        with urlopen(req, timeout=20) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    d = json.loads(payload)
                except Exception:
                    continue
                # usage 在最后一个 chunk 里给，那个 chunk 的 choices 是空的
                if d.get("usage"):
                    _record_usage(d["usage"])
                try:
                    delta = d["choices"][0]["delta"].get("content", "")
                except Exception:
                    continue
                if not delta:
                    continue
                buf += delta
                full.append(delta)
                sents, buf = _split_stream_sentence(buf)
                for s in sents:
                    if first_dt == 0.0:
                        first_dt = time.time() - t0
                        log("deepseek 首句 %.2fs" % first_dt)
                    if on_sentence:
                        try:
                            on_sentence(s, idx)
                        except Exception:
                            log("partial 回调失败", traceback.format_exc()[-160:])
                    idx += 1
        sents, buf = _split_stream_sentence(buf, final=True)
        for s in sents:
            if first_dt == 0.0:
                first_dt = time.time() - t0
            if on_sentence:
                try:
                    on_sentence(s, idx)
                except Exception:
                    pass
            idx += 1
        ans = "".join(full).strip()
        dt = time.time() - t0
        log("deepseek 流式 首句 %.2fs 全文 %.2fs" % (first_dt, dt))
        return ans, first_dt, dt
    except Exception as e:
        log("deepseek 流式失败，回退非流式: %s" % e)
        t1 = time.time()
        ans = ask_deepseek(text, history)
        return ans, time.time() - t1, time.time() - t1


def answer_question(q, notify=True):
    # 先把「听到了什么」推回去，等大模型的那几秒界面不至于干等着
    if notify:
        push_event({"type": "heard", "q": q, "streaming": 1})

    def emit(sentence, idx):
        if notify:
            push_event({"type": "partial", "q": q, "text": sentence,
                        "idx": idx, "mode": STATE["mode"]})

    ans, first_dt, total_dt = ask_deepseek_stream(q, emit)
    ev = {"type": "turn", "q": q, "answer": ans, "mode": STATE["mode"],
          "streamed": 1}
    if notify:
        push_event(ev)
    return ev


def do_turn(notify=True, max_sec=6.0, min_sec=1.0,
            silence=SILENCE_DEFAULT, from_wake=False, min_after_voice=None):
    """录音 -> 离线识别 -> DeepSeek，一个函数走完

    唤醒后这条路径要放宽 min_sec/silence：人喊完唤醒词通常会顿一下，
    按 0.62 秒判停会把停顿当成说完，只录到唤醒词本身。
    """
    STATE["busy"] = True
    touch_activity()
    rec_t0 = time.time()
    try:
        with _lock:
            raw, nch = record(max_sec, min_sec=min_sec, silence=silence,
                              min_after_voice=min_after_voice)
        rec_dt = time.time() - rec_t0
        if raw is None:
            log("turn: record failed")
            ev = {"type": "turn", "q": "", "answer": "", "err": "record failed"}
            if notify:
                push_event(ev)
            return ev
        pcm, peak = finish(raw, nch)
        log("turn 录音 %.2fs silence=%.2f peak=%d"
            % (rec_dt, silence, peak))
        txt = ""
        if peak >= 700:          # 实测底噪峰值 ~450，太低就是没人说话
            txt, dt, conf = asr_decode(pcm)
            txt = (txt or "").strip()
            log("turn peak=%d conf=%.2f -> %r (%.2fs)" % (peak, conf, txt, dt))
        else:
            log("turn: 没听到人声 peak=%d" % peak)

        # 唤醒后没说话（或者只憋出一个字）：很可能是先把问题说了、没反应才补喊
        # 名字，把唤醒前 8 秒的音频也解一遍，捡回来当问题。
        #
        # 但这招只在「语音唤醒」这条路上成立。点按钮进来的这一路，WAKE_PRE 里装的
        # 是上一轮遗留的环境音，硬喂给大模型就会出现「用户没说话，它却自问自答」：
        # 实测解开一句 conf=0.00 的「哇我是放松一点」，还真发给了 DeepSeek。
        # 所以既要限定来源，也要置信度/时长/响度同时像句人话才采纳。
        if from_wake and len(txt) < 2 and os.path.exists(WAKE_PRE):
            try:
                t0 = time.time()
                ptxt, ppeak, pdt, pconf = decode_file(WAKE_PRE, strip=True, tail_sec=10.0)
                # 判据用「字/秒」而不是置信度：实测 Vosk 对这类零碎杂音给 conf=0.00，
                # 但真话也不一定给高分，而语速是硬指标 —— 正常说话 2~6 字/秒。
                # 门槛踩过坑：1.88 字/秒的「红红与」曾经混过去（其实是「肥鱼肥鱼」
                # 的尾音被听岔），一路发给了 DeepSeek 自问自答。所以既要求够长
                # （≥4 字），也要求语速像人话（≥2.2 字/秒），响度再抬到 1200。
                rate = len(ptxt) / max(0.2, pdt)
                good = (pdt >= 1.2 and 2.2 <= rate <= 9.0 and len(ptxt) >= 4
                        and ppeak >= 1200)
                log("turn 回看唤醒前 peak=%d conf=%.2f %.2fs %.2f字/秒 -> %r %s (%.1fs)"
                    % (ppeak, pconf, pdt, rate, ptxt,
                       "采纳" if good else "丢弃", time.time() - t0))
                if good and len(ptxt) >= len(txt):
                    txt = ptxt
            except Exception:
                log("turn 回看失败", traceback.format_exc()[-200:])

        if len(txt) < 2:
            ev = {"type": "turn", "q": "", "answer": ""}
            if notify:
                push_event(ev)
            return ev
        # 短句里带切换词、或者整句基本就是个名字，就直接切人设，不用麻烦大模型。
        # 注意这里必须走近音匹配：实测用户说「召唤梁圣」，通用识别器吐的是
        # 「召唤良性」，精确匹配对不上，那句话就被当成问题发给 DeepSeek 了。
        if len(txt) <= 12:
            who = _name_of(txt)
            if who and (any(w in txt for w in SWITCH_WORDS) or len(txt) <= 6):
                set_mode(who)
                return {"type": "mode", "mode": who}
        return answer_question(txt, notify)
    except Exception:
        log("turn err", traceback.format_exc()[-300:])
        ev = {"type": "turn", "q": "", "answer": "", "err": "internal"}
        if notify:
            push_event(ev)
        return ev
    finally:
        STATE["busy"] = False


# ---------------- HTTP ----------------
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # 不用长连接：WebView 复用 keep-alive 连接时偶发请求丢失，
        # 表现就是 fetch 永不返回、界面卡在「让我想想」。
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        try:
            self.wfile.write(b)
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/tts"):
            # 本地合成，直接吐 mp3。参数和 PC 上的 tts_server 完全一致，
            # 前端只要把基址从 :8900/tts 改到 :8899/api/tts 就行。
            q = {}
            if "?" in self.path:
                for kv in self.path.split("?", 1)[1].split("&"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        q[k] = unquote(v)
            try:
                pitch = int(q["pitch"]) if "pitch" in q else None
                rate = int(q["rate"]) if "rate" in q else None
            except ValueError:
                pitch = rate = None
            try:
                data = tts_get(q.get("text", ""), q.get("voice", ""), pitch, rate)
            except Exception as e:
                return self._send({"err": "tts %s" % e}, 502)
            if not data:
                return self._send({"err": "empty text"}, 400)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            try:
                self.wfile.write(data)
            except Exception:
                pass
            return
        if self.path.startswith("/api/wav"):
            # 临时调试用：把正在用的 wav 回给前端，方便用扬声器放一段话做端到端自测。
            # 录音都挪到 /dev（tmpfs）了，所以 BASE 和 SCRATCH 两处都找。
            name = self.path.split("name=", 1)[-1].split("&")[0] if "name=" in self.path else ""
            base = os.path.basename(name or "")
            fp = ""
            for d in (SCRATCH, BASE):
                cand = os.path.join(d, base)
                if name and os.path.isfile(cand):
                    fp = cand
                    break
            if name and fp and fp.endswith(".wav"):
                try:
                    with open(fp, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass
            return self._send({"err": "no such wav"}, 404)
        if self.path.startswith("/health"):
            return self._send({"ok": True, "asr": bool(_asr), "mode": STATE["mode"],
                               "wake": STATE["wake"], "busy": STATE["busy"],
                               "build": BUILD, "tts": dict(_tts_stat)})
        if self.path.startswith("/api/stats"):
            # 右下角状态面板：token 用量 + 余额 + 当前模型。
            # 余额查询有 5 分钟缓存；force=1 可强制刷新。
            force = "force=1" in self.path
            bal = get_balance(force=force)
            up = dict(USAGE)
            up["uptime"] = round(time.time() - USAGE["started_at"], 0)
            # 不估算费用：DeepSeek 按时段/模型调价，估算数字只会误导。
            # 真实余额走 /user/balance，那个才准。
            return self._send({"usage": up, "balance": bal, "model": LLM_MODEL,
                               "github": {"repo": GITHUB_REPO,
                                          "stars": get_github_stars(force=force)},
                               "build": BUILD})
        if self.path.startswith("/api/peak"):
            # 诊断：最近 3 秒拾音峰值 + 当前开闸门限，用来对齐 PC 回环电平
            return self._send({"peak": LIVE_PEAK["max"],
                               "age": round(time.time() - LIVE_PEAK["at"], 2),
                               "gate": WAKE_GATE_FLOOR[0]})
        if self.path.startswith("/api/dashboard"):
            # 顶栏行情天气条。取不到的数据返回 null，前端显示「—」，绝不编造。
            try:
                import market as _mk
                force = "force=1" in self.path
                return self._send(_mk.get_dashboard(force=force))
            except Exception as e:
                return self._send({"err": "%s: %s" % (type(e).__name__, e),
                                   "market": [], "weather": {}}, 502)
        if self.path.startswith("/api/idle"):
            # 自测用：看息屏倒计时还剩多久
            return self._send({"idle_off": IDLE_OFF,
                               "age": round(time.time() - _last_act, 1),
                               "screen_on": screen_on()})
        if self.path.startswith("/api/events"):
            # 长轮询：没事件就挂着等（最多 20s）。原来界面 250ms 拉一次，
            # 一天要几万个空请求，光线程建销就吃掉半个核的几个点。
            wait = 0.0
            if "?" in self.path:
                for kv in self.path.split("?", 1)[1].split("&"):
                    if kv.startswith("wait="):
                        try:
                            wait = min(25.0, max(0.0, float(kv[5:])))
                        except ValueError:
                            pass
            dl = time.time() + wait
            with EV_LOCK:
                ev = EVENTS[:]
                EVENTS.clear()
                while not ev and wait > 0:
                    left = dl - time.time()
                    if left <= 0:
                        break
                    EV_LOCK.wait(left)
                    ev = EVENTS[:]
                    EVENTS.clear()
            return self._send({"events": ev, "mode": STATE["mode"]})
        self._send({"err": "not found"}, 404)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
            p = self.path

            if p.startswith("/api/peak"):
                # 诊断旋钮：临时调开闸门限（PC 回环测试用）。传 0 恢复默认 800。
                v = float(body.get("gate", 0))
                WAKE_GATE_FLOOR[0] = v if v > 0 else 800.0
                return self._send({"ok": True, "gate": WAKE_GATE_FLOOR[0]})
            if p.startswith("/api/mode"):
                set_mode(body.get("mode", "fish"))
                return self._send({"ok": True, "mode": STATE["mode"]})

            if p.startswith("/api/route"):
                # 自测用：把一段「识别结果」喂进唤醒判定，看真实会怎么分流。
                # 必须与线上 handle_wake_text 用同一个 classify_wake，否则自测会骗人。
                t = (body.get("text") or "").strip()
                act, who, q = classify_wake(t)
                return self._send({"text": t, "name": who, "action": act,
                                   "q": q, "wake": act == "ask"})

            if p.startswith("/api/activity"):
                # 界面点了/按了键就报一声，用来把息屏倒计时清零
                touch_activity()
                return self._send({"ok": True})

            if p.startswith("/api/idle"):
                # 自测用：把息屏阈值临时改小（秒），传 0 恢复 10 分钟
                global IDLE_OFF
                v = float(body.get("sec", 0))
                IDLE_OFF = v if v > 0 else 600.0
                touch_activity()
                return self._send({"ok": True, "idle_off": IDLE_OFF,
                                   "screen_on": screen_on()})

            if p.startswith("/api/wake"):
                on = bool(body.get("active", True))
                STATE["wake"] = on
                STATE["wake_off_at"] = 0.0 if on else time.time()
                return self._send({"ok": True, "wake": STATE["wake"]})

            if p.startswith("/api/grm"):
                # 试自定义词表，看这台设备的模型认哪种写法
                g = body.get("grammar") or []
                path = body.get("path") or os.path.join(BASE, "keep_user1.wav")
                lib = _asr["lib"]
                rec = None
                try:
                    lib.vosk_recognizer_new_grm.restype = ctypes.c_void_p
                    lib.vosk_recognizer_new_grm.argtypes = [ctypes.c_void_p, ctypes.c_float,
                                                            ctypes.c_char_p]
                    rec = lib.vosk_recognizer_new_grm(_asr["model"], float(SR),
                                                      json.dumps(g, ensure_ascii=False).encode())
                    if not rec:
                        return self._send({"err": "new_grm 返回空"})
                    with wave.open(path, "rb") as w:
                        nch = w.getnchannels()
                        a = array.array("h")
                        a.frombytes(w.readframes(w.getnframes()))
                    mono = mix4(a, nch) if nch > 1 else a
                    raw = agc(trim_silence(mono)).tobytes()
                    parts, fin = [], ""
                    for i in range(0, len(raw), 8000):
                        lib.vosk_recognizer_accept_waveform(rec, raw[i:i + 8000],
                                                            min(8000, len(raw) - i))
                        pt = json.loads(lib.vosk_recognizer_partial_result(rec).decode()).get("partial", "")
                        if pt:
                            parts.append(pt)
                    fin = json.loads(lib.vosk_recognizer_final_result(rec).decode()).get("text", "")
                    lib.vosk_recognizer_free(rec)
                    rec = None
                    return self._send({"grammar": g, "partials": parts[-6:], "final": fin})
                except Exception as e:
                    return self._send({"err": "%s: %s" % (type(e).__name__, e)})
                finally:
                    if rec:
                        try:
                            lib.vosk_recognizer_free(rec)
                        except Exception:
                            pass

            if p.startswith("/api/replay"):
                path = body.get("path") or WAKE_LAST
                try:
                    return self._send(replay_wake(path))
                except Exception as e:
                    return self._send({"err": "%s: %s" % (type(e).__name__, e)})

            if p.startswith("/api/selftest"):
                # 走和生产完全一样的流程：混音 -> 按底噪裁静音 -> AGC -> 识别
                path = body.get("path") or os.path.join(BASE, "t_wake.wav")
                try:
                    if body.get("raw"):
                        with wave.open(path, "rb") as w:
                            nch = w.getnchannels()
                            a = array.array("h")
                            a.frombytes(w.readframes(w.getnframes()))
                        pcm = mix4(a, nch) if nch > 1 else a
                        txt, dt, conf = asr_decode(pcm)
                        plen = len(pcm)
                    else:
                        txt, ppeak, dt, conf = decode_file(path)
                        plen = 0
                    return self._send({"text": txt, "sec": round(dt, 2),
                                       "conf": round(conf, 2), "samples": plen,
                                       "peak": ppeak if not body.get("raw") else 0,
                                       "fish": _has_fish(txt), "sage": _has_sage(txt),
                                       "mode": STATE["mode"]})
                except Exception as e:
                    return self._send({"err": "%s: %s" % (type(e).__name__, e)})

            if p.startswith("/api/debug/answer"):
                # 造一轮假对话推给前端，用来验证界面渲染与语音播报
                q = body.get("text") or "肥鱼肥鱼"
                ev = answer_question(q, notify=True)
                return self._send(ev)

            if p.startswith("/api/turn"):
                if STATE["busy"]:
                    return self._send({"err": "busy", "note": "正在处理上一轮"})
                # 改为 notify=True：逐句 partial 事件推给前端，第一句就能开播。
                # HTTP 响应仍带回完整结果，老版本前端照常工作。
                ev = do_turn(notify=True, max_sec=float(body.get("seconds", 6)))
                return self._send(ev)

            if p.startswith("/api/listen"):
                max_sec = float(body.get("seconds", 6))
                STATE["busy"] = True
                try:
                    with _lock:
                        raw, nch = record(max_sec)
                    if raw is None:
                        return self._send({"err": "record failed"})
                    pcm, peak = finish(raw, nch)
                    if peak < 300:
                        return self._send({"text": "", "peak": peak, "note": "no speech"})
                    txt, dt, conf = asr_decode(pcm)
                    log("listen peak=%d conf=%.2f -> %r (%.2fs)" % (peak, conf, txt, dt))
                    return self._send({"text": txt, "peak": peak, "decode_s": round(dt, 2)})
                finally:
                    STATE["busy"] = False

            if p.startswith("/api/ask"):
                q = body.get("text", "")
                ans = ask_deepseek(q, body.get("history"))
                return self._send({"answer": ans, "mode": STATE["mode"]})

            if p.startswith("/api/speak"):
                # 兼容老前端：给它一段文本，回一个本地合成好的 mp3 地址
                t = (body.get("text") or "").strip()
                try:
                    data = tts_get(t)
                except Exception as e:
                    return self._send({"ok": False, "err": "tts %s" % e}, 502)
                return self._send({"ok": bool(data), "bytes": len(data),
                                   "url": "/api/tts?text=" + quote(t)})

            self._send({"err": "not found"}, 404)
        except Exception as e:
            log("ERR", traceback.format_exc()[-400:])
            self._send({"err": str(e)}, 500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    # 先抢端口，抢到再干活。
    # 开机时自启脚本和看门狗会各拉一次，两个进程都去开麦克风会互相踩，
    # 表现就是唤醒时好时坏。谁先 bind 上谁就是正主，另一个安静退出。
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError as e:
        log("端口 %d 已被占用（%s），本进程退出，交给已在跑的那个" % (PORT, e))
        sys.exit(0)

    init_asr()
    apply_brightness()
    threading.Thread(target=wake_loop, daemon=True).start()
    threading.Thread(target=idle_watch, daemon=True).start()
    threading.Thread(target=wake_watch, daemon=True).start()
    threading.Thread(target=tts_warm, daemon=True).start()
    log("listening on 127.0.0.1:%d" % PORT)
    srv.serve_forever()
