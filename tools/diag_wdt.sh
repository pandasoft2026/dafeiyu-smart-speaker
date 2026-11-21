#!/system/bin/sh
echo "===== 1. 进程中的 watchdog 相关 ====="
ps -A | grep -i wdt
ps -A | grep -i watch
echo "(以上为空表示没有 userspace 喂狗进程)"

echo ""
echo "===== 2. 启动相关属性 ====="
getprop | grep -iE 'boot|reboot|reset|wdt|watchdog'

echo ""
echo "===== 3. init.rc 中的 watchdog 服务定义 ====="
grep -riE 'watchdog|wdt' /system/etc/init /vendor/etc/init 2>/dev/null | head -20
grep -iE 'watchdog|wdt' /init.rc 2>/dev/null | head -10

echo ""
echo "===== 4. 内核 WDT 相关 sysfs ====="
find /sys -iname '*watchdog*' -o -iname '*wdt*' 2>/dev/null | head -30

echo ""
echo "===== 5. pstore / 崩溃日志 ====="
ls -la /sys/fs/pstore/ 2>/dev/null
cat /sys/fs/pstore/console-ramoops* 2>/dev/null | tail -30

echo ""
echo "===== 6. last_kmsg ====="
cat /proc/last_kmsg 2>/dev/null | grep -iE 'wdt|watchdog|reset|reboot' | tail -20

echo ""
echo "===== 7. 当前 uptime / 启动原因 ====="
cat /proc/uptime
getprop ro.boot.bootreason
getprop persist.sys.boot.reason
