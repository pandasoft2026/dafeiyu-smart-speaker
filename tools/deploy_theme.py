# -*- coding: utf-8 -*-
"""部署大肥鱼主题：备份+替换开机动画、设置壁纸、推送素材。"""
import subprocess, time, os

adb = r"D:\workbuddy\2026-11-19-10-59-25\tools\platform-tools\adb.exe"
dev = "${SPEAKER_IP:-192.168.1.50}:5555"
BK = r"D:\workbuddy\2026-11-19-10-59-25\backup_speaker"
AST = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
subprocess.run([adb, "connect", dev], capture_output=True)
time.sleep(1)

def sh(cmd):
    return subprocess.run([adb, "-s", dev, "shell", "su -c '" + cmd + "'"],
                          capture_output=True, text=True)

def push(local, remote):
    return subprocess.run([adb, "-s", dev, "push", local, remote],
                          capture_output=True, text=True)

# 1. 备份原开机动画
print("=== 1. 备份原 bootanimation ===")
r = subprocess.run([adb, "-s", dev, "exec-out", "cat", "/system/media/bootanimation.zip"],
                   capture_output=True)
open(os.path.join(BK, "bootanimation_original.zip"), "wb").write(r.stdout)
print("   backed up", len(r.stdout), "bytes")

# 2. 推送新开机动画到 tmp 再替换
print("=== 2. 替换开机动画 ===")
boot = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\bootanimation.zip"
push(boot, "/data/local/tmp/bootanimation_new.zip")
r = sh("mount -o rw,remount /system; cp /system/media/bootanimation.zip /system/media/bootanimation.zip.bak; "
       "cp /data/local/tmp/bootanimation_new.zip /system/media/bootanimation.zip; "
       "chmod 644 /system/media/bootanimation.zip; ls -l /system/media/bootanimation.zip")
print("  ", r.stdout.strip(), r.stderr[:100])

# 3. 推送壁纸并用 wallpaper manager 设置
print("=== 3. 设置壁纸 ===")
wp = os.path.join(AST, "wallpaper_800x1280.jpg")
push(wp, "/data/local/tmp/wallpaper.jpg")
# 用 am 广播 + settings 无法直接设壁纸；用 cmd wallpaper (Android 8 不一定有)
r = sh("cp /data/local/tmp/wallpaper.jpg /sdcard/wallpaper.jpg; "
       "am broadcast -a android.intent.action.SET_WALLPAPER --es path /sdcard/wallpaper.jpg 2>&1; "
       "cmd wallpaper 2>&1 | head -3")
print("  ", r.stdout.strip()[:200], r.stderr[:80])

# 4. 推送头像与透明立绘到 voicebot（界面用）
print("=== 4. 推送界面素材 ===")
os.makedirs(r"/data/local/tmp/voicebot/assets", exist_ok=True) if False else None
sh("mkdir -p /data/local/tmp/voicebot/assets; chmod 777 /data/local/tmp/voicebot/assets")
for f in ["avatar.png", "dafeiyu_char.png", "wallpaper_800x1280.jpg"]:
    p = os.path.join(AST, f)
    if os.path.exists(p):
        push(p, "/data/local/tmp/wallpaper_tmp_" + f)  # push to writable tmp
        sh("mv /data/local/tmp/wallpaper_tmp_" + f + " /data/local/tmp/voicebot/assets/" + f)
        print("   pushed", f)
print("DONE")
