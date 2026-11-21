# -*- coding: utf-8 -*-
"""生成大肥鱼 1280x800 开机画面（桌面/锁屏风格）"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os

W, H = 1280, 800
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
CHAR = os.path.join(OUT, "char_620.png")

# 渐变底
base = Image.new("RGB", (W, H), (233, 245, 255))
px = base.load()
for y in range(H):
    for x in range(0, W, 2):
        t = (x / W * 0.35 + y / H * 0.65)
        r = int(233 + (250 - 233) * t)
        g = int(245 + (252 - 245) * t)
        b = int(255 + (255 - 255) * t)
        px[x, y] = (r, g, b)
        if x + 1 < W:
            px[x + 1, y] = (r, g, b)

# 柔光（白色提亮，不要压灰）
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse([-260, -300, 560, 500], fill=(255, 255, 255, 130))
gd.ellipse([820, 430, 1560, 1150], fill=(206, 235, 255, 105))
gd.ellipse([520, -180, 1180, 320], fill=(255, 255, 255, 70))
glow = glow.filter(ImageFilter.GaussianBlur(120))
base = Image.alpha_composite(base.convert("RGBA"), glow)

# 立绘
ch = Image.open(CHAR).convert("RGBA")
ch_h = 560
ch = ch.resize((int(ch.width * ch_h / ch.height), ch_h), Image.LANCZOS)

# 立绘落影
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
cx = 400
sd.ellipse([cx - 185, 676, cx + 185, 714], fill=(150, 190, 222, 62))
shadow = shadow.filter(ImageFilter.GaussianBlur(26))
base = Image.alpha_composite(base.convert("RGBA"), shadow)

# 贴立绘（底部对齐 y=690）
top = 690 - ch.height
base.alpha_composite(ch, (cx - ch.width // 2, top))

# 文字
d = ImageDraw.Draw(base)


def font(size, bold=True):
    for p in [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf"]:
        try:
            return ImageFont.truetype(p if bold else p.replace("msyhbd", "msyh"), size)
        except Exception:
            continue
    return ImageFont.load_default()


f1 = font(104)
f2 = font(38, bold=False)
tx = 760
# 主标题
d.text((tx, 268), "大肥鱼", font=f1, fill=(18, 58, 90))
# 英文小标
f3 = font(34)
d.text((tx + 6, 396), "DEEPSEEK VOICE", font=f3, fill=(94, 150, 190))
# 副标题
d.text((tx + 6, 452), "本地离线语音助手", font=f2, fill=(110, 147, 176))

# 细装饰线
d.line([(tx + 8, 430), (tx + 210, 430)], fill=(150, 200, 230), width=3)

base.convert("RGB").save(os.path.join(OUT, "boot_dafeiyu_1280x800.jpg"), quality=93)
print("saved", base.size)
