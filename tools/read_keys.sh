#!/system/bin/sh
# 读取 jd-kpd 的按键码定义（从 dmesg 和 keylayout 推断）
echo "===== jd-kpd sysfs ====="
find /sys/devices/platform/odm -name '*:kpd_jd*' -o -path '*kpd*' 2>/dev/null | head -10
echo ""
echo "===== 尝试读取按键码（getevent -il） ====="
getevent -il /dev/input/event0 2>/dev/null | head -30
echo ""
echo "===== DTS 中的按键定义 ====="
find /proc/device-tree -iname '*kpd*' 2>/dev/null | head -10
for f in $(find /proc/device-tree -path '*kpd_jd*' -type f 2>/dev/null | head -20); do
  echo -n "$f = "; cat "$f" 2>/dev/null | od -An -tu4 | head -1
done
