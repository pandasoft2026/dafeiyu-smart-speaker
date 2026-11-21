import subprocess, time, os
adb = r"D:\workbuddy\2026-11-19-10-59-25\tools\platform-tools\adb.exe"
dev = "${SPEAKER_IP:-192.168.1.50}:5555"
subprocess.run([adb, "connect", dev], capture_output=True)
time.sleep(1)
outdir = r"D:\workbuddy\2026-11-19-10-59-25\tools\libs"
os.makedirs(outdir, exist_ok=True)
pairs = [
    ("/system/lib/libcompiler_rt.so", "libcompiler_rt.so"),
    ("/data/local/tmp/voicebot/libvosk.so", "libvosk.so"),
]
for remote, name in pairs:
    r = subprocess.run([adb, "-s", dev, "exec-out", "cat", remote], capture_output=True)
    p = os.path.join(outdir, name)
    open(p, "wb").write(r.stdout)
    print(name, len(r.stdout))
