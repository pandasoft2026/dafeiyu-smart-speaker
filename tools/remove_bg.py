# -*- coding: utf-8 -*-
"""Flood-fill background removal from the four corners; character outline blocks fill."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from collections import deque
import os, random

SRC = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\Chibi_Q_version_cute_anime_gir_2026-11-20T03-35-24.png"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert("RGB")
W, H = im.size
im = im.crop((0, 0, W, H - 78))
w, h = im.size
pix = im.load()

# 背景判定：亮且低饱和
def is_bg(x, y):
    r, g, b = pix[x, y]
    mx, mn = max(r, g, b), min(r, g, b)
    return mx > 222 and (mx - mn) < 42

visited = bytearray(w * h)
q = deque()
# 从四条边的所有点开始
for x in range(w):
    q.append((x, 0)); q.append((x, h - 1))
for y in range(h):
    q.append((0, y)); q.append((w - 1, y))

while q:
    x, y = q.popleft()
    idx = y * w + x
    if visited[idx]: continue
    visited[idx] = 1
    if not is_bg(x, y): continue
    if x > 0: q.append((x - 1, y))
    if x < w - 1: q.append((x + 1, y))
    if y > 0: q.append((x, y - 1))
    if y < h - 1: q.append((x, y + 1))

print("flood done, bg pixels:", sum(visited))

# 生成 RGBA：外部连通背景 -> 透明；边缘做软化
out = Image.new("RGBA", (w, h))
op = out.load()
for y in range(h):
    for x in range(w):
        r, g, b = pix[x, y]
        if visited[y * w + x]:
            op[x, y] = (r, g, b, 0)
        else:
            # 半透明软化：靠近背景的边缘略微透明
            alpha = 255
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and visited[ny * w + nx]:
                    # 该像素紧贴背景，检查它自身是否也算浅色
                    if is_bg(x, y):
                        alpha = 120
                    break
            op[x, y] = (r, g, b, alpha)

out = out.filter(ImageFilter.GaussianBlur(0.3))
out.save(os.path.join(OUT, "dafeiyu_nobg.png"))
a = out.getchannel("A")
bbox = a.point(lambda v: 255 if v > 25 else 0).getbbox()
char = out.crop(bbox) if bbox else out
char.save(os.path.join(OUT, "dafeiyu_char.png"))
print("char bbox:", bbox, "size", char.size)

# 头像
def avatar(img, size=256):
    s2 = img.copy()
    ratio = size / (min(s2.size) * 0.86)
    s2 = s2.resize((int(s2.width * ratio), int(s2.height * ratio)), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0,0,0,0))
    canvas.alpha_composite(s2, ((size - s2.width)//2, -int(s2.height*0.01)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1), fill=255)
    canvas.putalpha(mask)
    return canvas
avatar(char).save(os.path.join(OUT, "avatar.png"))

# 壁纸
def grad(size, top, bottom):
    ww, hh = size
    img = Image.new("RGBA", size)
    dd = ImageDraw.Draw(img)
    for yy in range(hh):
        t = yy/(hh-1)
        c = tuple(int(top[i]+(bottom[i]-top[i])*t) for i in range(3))+(255,)
        dd.line((0,yy,ww,yy), fill=c)
    return img

SW, SH = 800, 1280
wall = grad((SW,SH), (232,244,255), (170,210,242))
dd = ImageDraw.Draw(wall,"RGBA")
random.seed(7)
for _ in range(24):
    x=random.randint(0,SW); y=random.randint(100,SH-80); r=random.randint(14,50)
    dd.ellipse((x-r,y-r,x+r,y+r), fill=(255,255,255,32))
ch = char.copy(); ch.thumbnail((770,920), Image.LANCZOS)
wall.alpha_composite(ch, ((SW-ch.width)//2, SH-ch.height-24))
try:
    f1=ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc",64)
    f2=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",30)
except Exception:
    f1=f2=ImageFont.load_default()
dr=ImageDraw.Draw(wall)
dr.text((SW//2,140),"大肥鱼",font=f1,fill=(30,90,150,255),anchor="mm")
dr.text((SW//2,205),"随时为你解答",font=f2,fill=(70,130,180,255),anchor="mm")
wall.convert("RGB").save(os.path.join(OUT,"wallpaper_800x1280.jpg"),quality=92)
print("wallpaper ok")

# 开机帧
BOOTS=os.path.join(OUT,"bootframes"); os.makedirs(BOOTS,exist_ok=True)
for f in os.listdir(BOOTS): os.remove(os.path.join(BOOTS,f))
bgc=grad((SW,SH),(16,38,68),(34,86,136))
bch=char.copy(); bch.thumbnail((500,600),Image.LANCZOS)
bx=(SW-bch.width)//2; by=340
for i in range(10):
    t=i/9; frame=bgc.copy(); fd=ImageDraw.Draw(frame,"RGBA")
    cx,cy,rr=SW//2,990,32
    fd.arc((cx-rr,cy-rr,cx+rr,cy+rr),-90,-90+360*t,fill=(255,255,255,230),width=7)
    layer=bch.copy(); al=int(255*min(1,t*1.5))
    layer.putalpha(layer.getchannel("A").point(lambda a:a*al//255))
    frame.alpha_composite(layer,(bx,by-int((1-t)*24)))
    ImageDraw.Draw(frame).text((SW//2,160),"大肥鱼",font=f1,fill=(235,245,255,255),anchor="mm")
    frame.convert("RGB").save(os.path.join(BOOTS,"%02d.png"%i))
print("boot ok")
