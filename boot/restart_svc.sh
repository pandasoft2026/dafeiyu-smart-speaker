#!/system/bin/sh
# 重启语音服务（需 root）。放在设备上执行，避免 pkill 误杀 adb shell 自身
export PATH=/system/bin:/system/xbin:/vendor/bin:/data/data/com.termux/files/usr/bin:$PATH
cd /data/local/tmp/voicebot || exit 1

for p in $(ps -A -o PID,ARGS | grep -E 'service\.py|tinycap' | grep -v grep | sed 's/^ *//' | cut -d' ' -f1); do
  kill -9 "$p" 2>/dev/null
done
sleep 1

# 确认端口与麦克风都释放了
if netstat -tln 2>/dev/null | grep -q ':8899'; then
  echo "WARN: 8899 still listening"
fi
if ps -A -o ARGS | grep -q '[t]inycap'; then
  echo "WARN: tinycap still alive"
fi

setsid sh py.sh service.py > svc.log 2>&1 &
sleep 1
echo "restarted, pid=$(ps -A -o PID,ARGS | grep 'service\.py' | grep -v grep | sed 's/^ *//' | cut -d' ' -f1 | tr '\n' ' ')"
