#!/system/bin/sh
# 部署脚本：持久化 ADB + 安装常驻守护到 Magisk service.d
PREFIX=/data/data/com.termux/files/usr
MAGISK_SD=/data/adb/service.d
LOG=/data/local/tmp/voicebot/deploy.log
mkdir -p /data/local/tmp/voicebot $MAGISK_SD

echo "=== $(date '+%m-%d %H:%M:%S') 部署开始 ===" > $LOG

# 1. 用 Magisk resetprop 持久化 adb tcp 端口（重启后自动监听）
echo "1. 持久化 ADB 端口" >> $LOG
$PREFIX/bin/resetprop persist.adb.tcp.port 5555 >> $LOG 2>&1
$PREFIX/bin/resetprop service.adb.tcp.port 5555 >> $LOG 2>&1
echo "   persist.adb.tcp.port=$(getprop persist.adb.tcp.port)" >> $LOG

# 2. 安装守护脚本到 Magisk service.d（开机 late_start 自动执行）
echo "2. 安装守护脚本" >> $LOG
cp /data/local/tmp/voicebot_guard.sh $MAGISK_SD/voicebot_guard.sh >> $LOG 2>&1
chmod 755 $MAGISK_SD/voicebot_guard.sh >> $LOG 2>&1
ls -l $MAGISK_SD/voicebot_guard.sh >> $LOG 2>&1

# 3. 立即启动一次守护（后台）
echo "3. 启动守护" >> $LOG
pkill -f voicebot_guard 2>/dev/null
nohup $MAGISK_SD/voicebot_guard.sh >/dev/null 2>&1 &
echo "   guard pid=$!" >> $LOG

echo "=== 部署完成 ===" >> $LOG
cat $LOG
