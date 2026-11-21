# -*- coding: utf-8 -*-
import subprocess, os, time

adb = r"D:\workbuddy\2026-11-19-10-59-25\tools\platform-tools\adb.exe"
dev = "${SPEAKER_IP:-192.168.1.50}:5555"
subprocess.run([adb, "connect", dev], capture_output=True)
time.sleep(1)

pairs = [
    (r"D:\workbuddy\2026-11-19-10-59-25\tools\apk\vosk-armv7l.whl", "vosk.whl"),
    (r"D:\workbuddy\2026-11-19-10-59-25\tools\apk\vosk-model-small-cn.zip", "model.zip"),
]

for local, name in pairs:
    r = subprocess.run([adb, "-s", dev, "push", local, "/data/local/tmp/" + name],
                       capture_output=True, text=True)
    print(name, "push rc", r.returncode, r.stdout.strip()[-50:])

# root: chmod dir, move files in
shell_cmd = (
    "chmod 777 /data/local/tmp/voicebot; "
    "mv /data/local/tmp/vosk.whl /data/local/tmp/voicebot/; "
    "mv /data/local/tmp/model.zip /data/local/tmp/voicebot/; "
    "chmod 644 /data/local/tmp/voicebot/vosk.whl /data/local/tmp/voicebot/model.zip; "
    "ls -lh /data/local/tmp/voicebot/"
)
r = subprocess.run([adb, "-s", dev, "shell", "su -c '" + shell_cmd + "'"],
                   capture_output=True, text=True)
print("MOVE stdout:", r.stdout)
print("MOVE stderr:", r.stderr[:200])
