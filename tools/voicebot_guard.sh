#!/system/bin/sh
# voicebot_guard - 京鱼座 SD-DP02 常驻守护
# 由 Magisk /data/adb/service.d 开机自动执行（已是 root）
# 1) 持久化 adb tcp 端口
# 2) 压制当贝内置的豆包聊天页，保持主界面
# 3) 记录存活日志，供后续 AI 对话服务复用

LOG=/data/local/tmp/voicebot/guard.log
MAIN="com.larus.nova/com.larus.home.impl.MainActivity"
mkdir -p /data/local/tmp/voicebot

echo "$(date '+%m-%d %H:%M:%S') guard started" >> $LOG

# 开机确保 adb 网络端口
RESETPROP=/sbin/resetprop
[ -x "$RESETPROP" ] && $RESETPROP service.adb.tcp.port 5555 >> $LOG 2>&1
setprop service.adb.tcp.port 5555

i=0
while true; do
  # 压制豆包聊天页
  cur=$(dumpsys window windows 2>/dev/null | grep -m1 'mCurrentFocus' | grep -oE 'com\.larus\.nova/[^ }]*' | head -1)
  case "$cur" in
    *ChatActivity*)
      echo "$(date '+%m-%d %H:%M:%S') suppress chat" >> $LOG
      am start -n "$MAIN" --activity-clear-top >/dev/null 2>&1
      ;;
  esac

  # 每 20 轮（约 60 秒）补一次 adb 端口
  i=$((i+1))
  if [ $((i % 20)) -eq 0 ]; then
    p=$(getprop service.adb.tcp.port 2>/dev/null)
    [ "$p" = "5555" ] || { setprop service.adb.tcp.port 5555; stop adbd; start adbd; echo "$(date '+%m-%d %H:%M:%S') adbd restart" >> $LOG; }
  fi

  sleep 3
done
