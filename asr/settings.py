# -*- coding: utf-8 -*-
"""集中配置：持久化到 config.json，供 service.py 与前端控制中心读写。

设计原则：
  - 所有可调项都有默认值，config.json 缺项就用默认，升级不破坏老配置。
  - 写入 atomic（tmp + replace），后台线程正在读也不会读到半截文件。
  - 只存「数据」，不存函数/密钥明文以外的东西；API key 单独文件沿用历史。
"""
import json
import os
import threading

# 允许环境变量覆盖路径，方便在 PC 上跑单测（设备上用默认路径）
CFG_PATH = os.environ.get("DFY_CONFIG_PATH", "/data/local/tmp/voicebot/config.json")
_lock = threading.Lock()

DEFAULTS = {
    # ---- 大模型 ----
    "llm": {
        "provider": "deepseek",        # deepseek | openai_compatible
        "base_url": "https://api.deepseek.com",
        "chat_path": "/chat/completions",
        "model": "deepseek-chat",
        "temperature_fish": 0.7,
        "temperature_sage": 0.4,
        "max_tokens": 120,
        "timeout": 20,
        "api_key": "",                 # 留空则用 api_key.conf
    },
    # ---- ASR ----
    "asr": {
        "engine": "vosk",              # vosk | cloud (预留)
        "model_dir": "/data/local/tmp/voicebot/model",
        "wake_model_dir": "/data/local/tmp/voicebot/model",
        "gate_floor": 800,             # 唤醒开闸门限
        "silence_sec": 0.45,           # 判停静音时长
        "wake_timeout_sec": 4.0,       # 开闸最长时长（防误唤醒）
    },
    # ---- TTS ----
    "tts": {
        "engine": "edge",              # edge | cloud (预留)
        "voice_fish": "zh-CN-XiaoyiNeural",
        "voice_sage": "zh-CN-YunjianNeural",
        "pitch_fish": 28,
        "rate_fish": 4,
        "pitch_sage": -22,
        "rate_sage": -18,
        "cache_max": 60,
        "text_max": 600,
    },
    # ---- 界面/交互 ----
    "ui": {
        "animation": False,            # 动效开关（这台设备默认关闭）
        "idle_off_sec": 600,           # 息屏时间
        "brightness_adj": -0.5,        # 亮度微调
        "font_scale": 1.0,             # 字号缩放
    },
    # ---- 人设提示词 ----
    "prompts": {
        "fish": (
            "你是“大肥鱼”，一只软萌爱撒娇的小鲸鱼助手。用口语化短句回答，带一点撒娇。"
            "严格规则：只说一句话，20 字以内，直接给答案，不要铺垫和复述问题，不解释过程。"
            "用户让你讲故事/笑话/创作时可以到 40 字，要真的讲出来、别拒绝。"
            "这是语音播报，用户听完就要走。禁止 Markdown、表情、列表、引号。"
        ),
        "sage": (
            "你是“梁圣”，一位气场很强的技术型老板。说话简洁克制、直接给判断，不寒暄不卖萌。"
            "严格规则：只说一句话，20 字以内，先给结论，不解释过程。"
            "用户让你讲故事/笑话/创作时可以到 40 字，要真的讲出来、别拒绝。"
            "这是语音播报，用户听完就要走。禁止 Markdown、表情、列表、引号。"
        ),
    },
    # ---- 场景 ----
    "scene": {
        "weather_city": "",            # 留空自动定位
        "wake_enabled": True,
        "volume_music": 8,             # Android STREAM_MUSIC 0-15
    },
}


def _deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load():
    with _lock:
        try:
            with open(CFG_PATH, encoding="utf-8") as f:
                disk = json.load(f)
        except Exception:
            disk = {}
    return _deep_merge(DEFAULTS, disk)


def save(cfg):
    """整体覆盖写入（调用方应先 load 再改），原子替换。"""
    merged = _deep_merge(DEFAULTS, cfg)
    with _lock:
        try:
            os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
        except OSError:
            pass
        tmp = CFG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CFG_PATH)
    return merged


def patch(part):
    """局部更新：只覆盖传入的键，返回合并后的全量配置。"""
    cfg = load()
    return save(_deep_merge(cfg, part))


def get(section, key, default=None):
    return load().get(section, {}).get(key, default)


def reset():
    with _lock:
        try:
            os.remove(CFG_PATH)
        except OSError:
            pass
    return dict(DEFAULTS)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        print(json.dumps(load(), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "reset":
        print("reset", json.dumps(reset(), ensure_ascii=False)[:80])
    else:
        print("usage: settings.py show|reset")
