# -*- coding: utf-8 -*-
"""行情与天气聚合（顶栏信息条用）。

设计原则：
  - 禁止编造数据：取不到就返回 None，前端显示「—」，绝不填充假数字。
  - 一次腾讯请求拿全部 A股/美股/港股指数 + 美元金；新浪补日经和人民币金；
    Open-Meteo 拿天气。全部免费、无需 key。
  - 缓存：行情 30s、天气 10min。前端每 10s 拉，绝大多数命中缓存。
  - 任何单点失败只影响那一项，其余照常显示。
"""
import json
import re
import threading
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}

# 腾讯行情代码 → (显示名, 分类)
TX_CODES = [
    ("sh000001", "上证", "cn"),
    ("sz399001", "深证", "cn"),
    ("sz399006", "创业板", "cn"),
    ("usDJI", "道指", "us"),
    ("usIXIC", "纳指", "us"),
    ("usINX", "标普", "us"),
    ("hkHSI", "恒生", "hk"),
    ("hkHSTECH", "恒科", "hk"),
]
# 新浪补充：日经、人民币金(沪金99)、美元金(伦敦金)
SINA_CODES = [
    ("int_nikkei", "日经", "jp", 0),
    ("gds_AU9999", "沪金", "gold", 0),
    ("hf_XAU", "伦敦金", "gold", 0),
]

_cache = {"data": None, "at": 0.0}
_weather_cache = {"data": None, "at": 0.0}
_lock = threading.Lock()
MARKET_TTL = 30.0
WEATHER_TTL = 600.0
WMO = {0: "晴", 1: "多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾",
       51: "小雨", 53: "小雨", 55: "中雨", 61: "小雨", 63: "中雨", 65: "大雨",
       71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨", 81: "阵雨", 82: "暴雨",
       95: "雷雨", 96: "雷雨", 99: "雷雨"}


def _http(url, timeout=8):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _num(s):
    try:
        v = float(s)
        return v if v == v else None          # 过滤 nan
    except Exception:
        return None


def _parse_tx(txt):
    out = {}
    for line in txt.strip().split(";"):
        if "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].strip()
        code = key[2:] if key.startswith("v_") else key   # v_sh000001 -> sh000001
        parts = line.split('"')[1].split("~")
        if len(parts) < 33:
            continue
        out[code] = {"price": _num(parts[3]), "chg": _num(parts[31]),
                     "pct": _num(parts[32]), "time": parts[30]}
    return out


def _parse_sina(txt):
    out = {}
    for m in re.finditer(r'hq_str_(\w+)="([^"]*)"', txt):
        code, val = m.group(1), m.group(2)
        f = val.split(",")
        if not val or not f[0]:
            continue
        if code == "int_nikkei":
            # 日经指数,44946.64,-408.35,-0.90
            out[code] = {"price": _num(f[1]), "chg": _num(f[2]), "pct": _num(f[3])}
        elif code == "gds_AU9999":
            # 沪金99: 现价,0,买,卖,高,低,时间,昨收,...  → 用昨收算涨跌幅
            price, prev = _num(f[0]), _num(f[7]) if len(f) > 7 else None
            pct = round((price - prev) / prev * 100, 2) if (price and prev) else None
            out[code] = {"price": price, "pct": pct}
        elif code == "hf_XAU":
            # 伦敦金: 现价,昨收,买,卖,高,低,时间,...  → 第1项是昨收（不是涨跌幅！）
            price, prev = _num(f[0]), _num(f[1]) if len(f) > 1 else None
            pct = round((price - prev) / prev * 100, 2) if (price and prev) else None
            out[code] = {"price": price, "pct": pct}
    return out


def _fetch_market():
    items = []
    errors = []

    # 腾讯：一次拿全部主要指数
    tx = {}
    try:
        codes = ",".join(c for c, _, _ in TX_CODES)
        tx = _parse_tx(_http("https://qt.gtimg.cn/q=" + codes).decode("gbk", "replace"))
    except Exception as e:
        errors.append("tx:" + type(e).__name__)

    for code, name, cat in TX_CODES:
        d = tx.get(code)
        items.append({"name": name, "cat": cat,
                      "price": d["price"] if d else None,
                      "pct": d["pct"] if d else None,
                      "time": d["time"] if d else None})

    # 新浪：日经 + 人民币金 + 美元金
    try:
        codes = ",".join(c for c, _, _, _ in SINA_CODES)
        sn = _parse_sina(_http("https://hq.sinajs.cn/list=" + codes).decode("gbk", "replace"))
    except Exception as e:
        errors.append("sina:" + type(e).__name__)
        sn = {}
    for code, name, cat, _ in SINA_CODES:
        d = sn.get(code)
        items.append({"name": name, "cat": cat,
                      "price": d["price"] if d else None,
                      "pct": d.get("pct") if d else None,
                      "time": None})

    # 韩国指数暂无稳定免费源——留空位、不编造
    items.append({"name": "韩KOSPI", "cat": "kr", "price": None, "pct": None, "time": None})

    return {"items": items, "at": time.time(), "errors": errors}


def _fetch_weather():
    # 成都 30.57N 104.07E，当前天气 + 未来 5 天
    url = ("https://api.open-meteo.com/v1/forecast?latitude=30.57&longitude=104.07"
           "&current=temperature_2m,relative_humidity_2m,weather_code"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min"
           "&forecast_days=5&timezone=Asia%2FShanghai")
    try:
        d = json.loads(_http(url, timeout=12).decode())
        cur = d.get("current", {})
        code = cur.get("weather_code")
        daily = d.get("daily", {})
        days = []
        times = daily.get("time") or []
        codes = daily.get("weather_code") or []
        hi = daily.get("temperature_2m_max") or []
        lo = daily.get("temperature_2m_min") or []
        for i, t in enumerate(times[:5]):
            # 日期显示 周几
            try:
                import datetime
                dt = datetime.date.fromisoformat(t)
                label = "周" + "一二三四五六日"[dt.weekday()]
            except Exception:
                label = t[5:] if len(t) >= 10 else "—"
            days.append({"day": label,
                         "desc": WMO.get(codes[i] if i < len(codes) else None, "—"),
                         "hi": _num(str(hi[i])) if i < len(hi) else None,
                         "lo": _num(str(lo[i])) if i < len(lo) else None})
        return {"temp": _num(str(cur.get("temperature_2m"))),
                "desc": WMO.get(code, "—"),
                "hum": cur.get("relative_humidity_2m"),
                "city": "成都", "days": days,
                "at": time.time()}
    except Exception:
        return {"temp": None, "desc": "—", "hum": None,
                "city": "成都", "days": [], "at": time.time()}


def get_dashboard(force=False):
    """返回聚合数据。force=1 跳过缓存强制抓。线程安全。"""
    now = time.time()
    with _lock:
        if (not force and _cache["data"] and now - _cache["data"]["at"] < MARKET_TTL):
            market = _cache["data"]
        else:
            market = _fetch_market()
            _cache["data"] = market

        if (not force and _weather_cache["data"]
                and now - _weather_cache["data"]["at"] < WEATHER_TTL):
            weather = _weather_cache["data"]
        else:
            weather = _fetch_weather()
            _weather_cache["data"] = weather

    # 汇率：美元金→人民币金是不同计价，不在这里换算，各自显示各自单位
    return {"market": market["items"], "weather": weather,
            "market_at": market["at"], "errors": market["errors"]}


if __name__ == "__main__":
    import pprint
    pprint.pprint(get_dashboard(force=True))
