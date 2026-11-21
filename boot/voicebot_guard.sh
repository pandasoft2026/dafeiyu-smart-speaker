#!/system/bin/sh
# voicebot_guard - 只保留「adb tcp 端口持久化」这一件事
#
# 老版本每 3 秒跑一次 dumpsys window，为的是压制豆包（com.larus.nova）的聊天页。
# 豆包早就卸载了，那段逻辑纯属空转；而 dumpsys 是重命令，在 4×A35 上一直跑着
# 很浪费。现在改成 5 分钟探一次属性，开销可以忽略。
#
# 也不再 stop/start adbd：那会把正在用的 adb 连接踢掉，反而更麻烦。

LOG=/data/local/tmp/voicebot/guard.log
mkdir -p /data/local/tmp/voicebot

# persist.adb.tcp.port 是持久属性，adbd 启动时自己会读，重启后照样能连。
# service.adb.tcp.port 只是本次运行时的，两样都设上最保险。
setprop persist.adb.tcp.port 5555
setprop service.adb.tcp.port 5555
RESETPROP=/data/data/com.termux/files/usr/bin/resetprop
[ -x "$RESETPROP" ] && "$RESETPROP" service.adb.tcp.port 5555 >> "$LOG" 2>&1

# 开机的 adbd 可能已经以 USB 模式起来了，重启一次让它按 tcp 端口监听。
# 只在启动阶段做一次，循环里绝不再动，免得把自己这条连接踢掉。
if ! netstat -tln 2>/dev/null | grep -q ':5555'; then
  stop adbd
  sleep 1
  start adbd
  sleep 2
fi
echo "$(date '+%m-%d %H:%M:%S') guard: adb port pinned ($(getprop service.adb.tcp.port))" >> "$LOG"

while true; do
  sleep 300
  p=$(getprop service.adb.tcp.port 2>/dev/null)
  if [ "$p" != "5555" ]; then
    setprop service.adb.tcp.port 5555
    echo "$(date '+%m-%d %H:%M:%S') adb port re-pinned" >> "$LOG"
  fi
done
