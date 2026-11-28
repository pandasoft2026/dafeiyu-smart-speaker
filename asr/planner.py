# -*- coding: utf-8 -*-
"""闹钟 / 备忘录 / 日程：持久化 + 对话指令解析 + 卡片数据。

设计：
  - 数据存 JSON（设备本地，重启不丢）；写入带锁，避免唤醒线程和 API 线程同时写坏。
  - 指令解析走规则，不调大模型：本地、确定、零延迟。
  - 卡片是「一页放下」的紧凑周视图：闹钟=未来7天，备忘录=最近7条，日程=本周7天。
  - 时间取设备本地时钟；RTC 可能有偏差，但各功能之间一致。
"""
import json
import os
import re
import threading
import time

DB_PATH = "/data/local/tmp/voicebot/planner_data.json"
_lock = threading.Lock()

FULL_WEEK = ["一", "二", "三", "四", "五", "六", "日"]

# 中文数字 → 阿拉伯（支持到 59，够闹钟/日期用）
_CN = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
       "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_num(s):
    """把中文数字串转成整数：'二十三'->23, '七'->7, '10'->10"""
    if not s:
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    if "十" in s:
        a, _, b = s.partition("十")
        hi = _CN.get(a, 1) if a else 1
        lo = _CN.get(b, 0) if b else 0
        return hi * 10 + lo
    total = 0
    for c in s:
        if c not in _CN:
            return None
        total = total * 10 + _CN[c]
    return total if total else None


def _load():
    try:
        with open(DB_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("alarms", [])
    d.setdefault("notes", [])
    d.setdefault("events", [])
    return d


def _save(d):
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DB_PATH)


def _now():
    return time.localtime()


def today_str():
    t = _now()
    return "%d-%02d-%02d" % (t.tm_year, t.tm_mon, t.tm_mday)


def weekday_cn(offset=0):
    """offset=0 今天, 1 明天 ... 返回 '周三'"""
    t = time.localtime(time.time() + offset * 86400)
    return "周" + FULL_WEEK[t.tm_wday]


def date_str(offset=0):
    t = time.localtime(time.time() + offset * 86400)
    return "%02d/%02d" % (t.tm_mon, t.tm_mday)


def _parse_day(s):
    """解析 '明天/后天/周三/下周一/11月27号' → 距今天的天数；失败 None"""
    if not s:
        return None
    if "今天" in s or "今日" in s:
        return 0
    if "明天" in s or "明日" in s:
        return 1
    if "后天" in s:
        return 2
    if "大后天" in s:
        return 3
    m = re.search(r"(下)?周([一二三四五六日天])", s)
    if m:
        target = 6 if m.group(2) == "天" else "一二三四五六日".index(m.group(2))
        cur = _now().tm_wday
        delta = (target - cur) % 7
        if m.group(1):
            delta += 7 if delta else 7
        return delta
    m = re.search(r"(\d{1,2})[月/](\d{1,2})[号日]?", s)
    if m:
        try:
            t = _now()
            mo, da = int(m.group(1)), int(m.group(2))
            import datetime
            target = datetime.date(t.tm_year, mo, da)
            today = datetime.date(t.tm_year, t.tm_mon, t.tm_mday)
            return (target - today).days
        except Exception:
            return None
    return None


def _parse_time(s):
    """解析 '早上七点/7点半/14:30' → (hour, minute)；失败 None"""
    if not s:
        return None
    m = re.search(r"(\d{1,2})\s*[:：]\s*(\d{2})", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        return (h, mi) if 0 <= h < 24 and 0 <= mi < 60 else None
    m = re.search(r"([零〇一二两三四五六七八九十\d]+)点(半|([零〇一二两三四五六七八九十\d]{1,3})分?)?", s)
    if not m:
        return None
    h = cn_num(m.group(1))
    if h is None or h >= 24:
        return None
    rest = (m.group(2) or "").rstrip("分")   # 去掉「分」字：15分/09分/十五分
    if rest == "半":
        mi = 30
    elif rest:
        mi = cn_num(rest) if (rest[0] in _CN or "十" in rest) else (
             int(rest) if rest.isdigit() else 0)
    else:
        mi = 0
    if mi is None or mi >= 60:
        mi = 0
    if any(k in s for k in ("下午", "晚上")) and h < 12:
        h += 12
    return h, mi


def _strip_cmd(t, words):
    for w in words:
        t = t.replace(w, "")
    return t.strip("，,。.：: 的")


# ---------- 指令入口 ----------
def handle(text):
    """返回 None 表示不是我们的指令；否则返回 {'type':'card'|'say', ...}"""
    t = (text or "").strip().replace(" ", "")
    if not t:
        return None
    # 打开界面（优先，避免被当成设置指令）
    if re.search(r"(打开|看看|查看|显示).*(闹钟|闹铃)", t):
        r = card("alarm"); r["answer"] = "闹钟在这儿啦，都给你列好了～"; return r
    if re.search(r"(打开|看看|查看|显示).*(备忘|便签|记事)", t):
        r = card("note"); r["answer"] = "你的备忘录，都记着呢～"; return r
    if re.search(r"(打开|看看|查看|显示).*(日程|安排|计划)", t):
        r = card("event"); r["answer"] = "日程表在这儿，一周的都列好了～"; return r

    # 设置闹钟：必须同时有「点/时刻」和闹钟语义
    if re.search(r"(设|定|加|创建|来)?\s*(个)?\s*(闹钟|闹铃|提醒)", t) and _parse_time(t) is not None:
        return _set_alarm(t)
    # 设置日程：有「日程/安排」且有日期或时间
    if re.search(r"(日程|安排)", t) and (_parse_day(t) is not None or _parse_time(t) is not None):
        return _set_event(t)
    # 设置备忘录：有「记/备忘/提醒我」且不是闹钟时间
    if re.search(r"(备忘|记一下|记住|记下|便签)", t):
        return _set_note(t)
    return None


def _set_alarm(t):
    hm = _parse_time(t)
    if not hm:
        return None
    off = _parse_day(t)
    if off is None:
        # 没说哪天：若时间已过则明天，否则今天
        t0 = _now()
        off = 0 if (hm[0], hm[1]) > (t0.tm_hour, t0.tm_min) else 1
    content = _strip_cmd(t, ["设置", "设定", "定", "设", "个", "闹钟", "闹铃", "提醒",
                              "明天", "明早", "后天", "今天", "早上", "上午", "下午",
                              "晚上", "点", "半", "分", "的"])
    content = re.sub(r"[零〇一二两三四五六七八九十\d]+", "", content).strip("，,。 ")
    if not content:
        content = "起床" if hm[0] < 9 else "提醒"
    with _lock:
        d = _load()
        d["alarms"].append({
            "id": int(time.time() * 1000), "h": hm[0], "m": hm[1],
            "day": off, "text": content[:20], "done": False,
            "created": time.strftime("%m-%d %H:%M", _now())})
        _save(d)
    day = "今天" if off == 0 else ("明天" if off == 1 else weekday_cn(off))
    return {"type": "say", "answer": "好嘞，%s %02d:%02d 的「%s」闹钟设好啦～" %
            (day, hm[0], hm[1], content), "card": card("alarm")["card"]}


def _set_note(t):
    content = _strip_cmd(t, ["设置", "设", "备忘", "备忘录", "记一下", "记住", "记下",
                              "便签", "添加", "帮我", "一下", "的"])
    if not content:
        return {"type": "say", "answer": "要记什么呀？说清楚点我帮你记上～"}
    with _lock:
        d = _load()
        d["notes"].append({"id": int(time.time() * 1000), "text": content[:60],
                           "ts": time.strftime("%m-%d %H:%M", _now()),
                           "stamp": time.time()})
        _save(d)
    return {"type": "say", "answer": "记好啦：「%s」" % content[:30],
            "card": card("note")["card"]}


def _set_event(t):
    off = _parse_day(t)
    hm = _parse_time(t)
    if off is None and hm is None:
        return None
    content = _strip_cmd(t, ["设置", "设", "添加", "日程", "安排", "计划", "帮我",
                              "明天", "后天", "今天", "下周", "周", "早上", "上午",
                              "下午", "晚上", "点", "半", "分", "的"])
    content = re.sub(r"[零〇一二两三四五六七八九十\d]+", "", content).strip("，,。 ")
    if not content:
        content = "待办"
    if off is None:
        off = 0
    with _lock:
        d = _load()
        d["events"].append({"id": int(time.time() * 1000), "day": off,
                            "h": hm[0] if hm else None, "m": hm[1] if hm else None,
                            "text": content[:30], "done": False,
                            "created": time.strftime("%m-%d %H:%M", _now())})
        _save(d)
    day = "今天" if off == 0 else ("明天" if off == 1 else weekday_cn(off))
    when = day + ((" %02d:%02d" % hm) if hm else "")
    return {"type": "say", "answer": "好嘞，%s 的日程「%s」加上啦～" % (when, content),
            "card": card("event")["card"]}


def card(kind):
    """生成一页放下的周视图卡片数据"""
    with _lock:
        d = _load()
    now = time.time()
    if kind == "alarm":
        alarms = [a for a in d["alarms"] if not a.get("done")]
        alarms.sort(key=lambda a: (a.get("day", 0), a.get("h", 0), a.get("m", 0)))
        rows = []
        for a in alarms[:7]:
            day = a.get("day", 0)
            rows.append({"day": "今天" if day == 0 else ("明天" if day == 1 else weekday_cn(day)),
                         "time": "%02d:%02d" % (a.get("h", 0), a.get("m", 0)),
                         "text": a.get("text", ""), "id": a["id"]})
        return {"type": "card", "card": {"kind": "alarm", "title": "闹钟",
                "sub": "未来一周 · %d 个" % len(rows), "rows": rows}}
    if kind == "note":
        notes = sorted(d["notes"], key=lambda n: n.get("stamp", 0), reverse=True)
        rows = []
        for n in notes[:7]:
            days = int((now - n.get("stamp", now)) / 86400)
            when = "今天" if days < 1 else ("昨天" if days < 2 else n.get("ts", "")[:5])
            rows.append({"day": when, "time": n.get("ts", "")[-5:],
                         "text": n.get("text", ""), "id": n["id"]})
        return {"type": "card", "card": {"kind": "note", "title": "备忘录",
                "sub": "最近记录 · %d 条" % len(rows), "rows": rows}}
    if kind == "event":
        evs = [e for e in d["events"] if e.get("day", 0) >= 0 and not e.get("done")]
        evs.sort(key=lambda e: (e.get("day", 0), e.get("h") or 99, e.get("m") or 0))
        rows = []
        for e in evs[:7]:
            day = e.get("day", 0)
            rows.append({"day": "今天" if day == 0 else ("明天" if day == 1 else weekday_cn(day)),
                         "time": ("%02d:%02d" % (e["h"], e["m"])) if e.get("h") is not None else "全天",
                         "text": e.get("text", ""), "id": e["id"]})
        return {"type": "card", "card": {"kind": "event", "title": "日程",
                "sub": "最近一周 · %d 项" % len(rows), "rows": rows}}
    return None


# ---------- CRUD（控制中心用） ----------
def _kind_list(kind):
    return {"alarm": "alarms", "note": "notes", "event": "events"}.get(kind)


def item_update(kind, item_id, fields):
    """改一条：fields 是待合并的字段字典"""
    key = _kind_list(kind)
    if not key:
        return False
    with _lock:
        d = _load()
        for it in d[key]:
            if str(it.get("id")) == str(item_id):
                it.update(fields)
                _save(d)
                return True
    return False


def item_delete(kind, item_id):
    key = _kind_list(kind)
    if not key:
        return False
    with _lock:
        d = _load()
        before = len(d[key])
        d[key] = [it for it in d[key] if str(it.get("id")) != str(item_id)]
        if len(d[key]) != before:
            _save(d)
            return True
    return False


def item_add(kind, fields):
    key = _kind_list(kind)
    if not key:
        return None
    with _lock:
        d = _load()
        item = dict(fields)
        item.setdefault("id", int(time.time() * 1000))
        item.setdefault("created", time.strftime("%m-%d %H:%M", _now()))
        if kind == "note":
            item.setdefault("stamp", time.time())
        d[key].append(item)
        _save(d)
    return item["id"]


def due_alarms():
    """返回此刻到点的闹钟（每分钟由 service 轮询一次）"""
    t = _now()
    with _lock:
        d = _load()
        due = [a for a in d["alarms"]
               if not a.get("done") and a.get("day") == 0
               and a.get("h") == t.tm_hour and a.get("m") == t.tm_min]
        if due:
            for a in due:
                a["done"] = True
            _save(d)
    return due


if __name__ == "__main__":
    import sys
    for s in sys.argv[1:]:
        print(s, "->", handle(s))
