# -*- coding: utf-8 -*-
"""生成梁圣音色候选，供音箱试听挑选"""
import asyncio, os, io
import edge_tts

OUT = os.path.join(os.path.dirname(__file__), "..", "samples")
LINE = "梁圣已上线。有事直说，我时间不多。"

CANDS = [
    ("A", "zh-CN-YunxiNeural", -16, -8, "云希 · 压低版", "年轻，压低语调试出的沉稳感"),
    ("B", "zh-CN-YunxiNeural", -8, -4, "云希 · 轻压版", "年轻清亮，攻击性弱一些"),
    ("C", "zh-CN-YunyangNeural", -10, -6, "云扬 · 低沉版", "播音底子，冷峻克制"),
    ("D", "zh-CN-YunjianNeural", 8, 4, "云健 · 提亮版", "在现在这版基础上年轻化"),
]


async def synth(text, voice, pitch, rate, path):
    c = edge_tts.Communicate(text, voice, rate="%+d%%" % rate, pitch="%+dHz" % pitch)
    buf = io.BytesIO()
    async for ch in c.stream():
        if ch["type"] == "audio":
            buf.write(ch["data"])
    open(path, "wb").write(buf.getvalue())
    return len(buf.getvalue())


async def main():
    os.makedirs(OUT, exist_ok=True)
    for key, voice, pitch, rate, name, desc in CANDS:
        p = os.path.join(OUT, key + ".mp3")
        n = await synth(LINE, voice, pitch, rate, p)
        print("%s  %-22s pitch=%+d rate=%+d  %d bytes" % (key, voice, pitch, rate, n))


if __name__ == "__main__":
    asyncio.run(main())
