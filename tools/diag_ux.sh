#!/system/bin/sh
echo "########## 1. 输入设备（实体按键来源） ##########"
cat /proc/bus/input/devices 2>/dev/null | grep -E 'Name:|Handlers:|EV:|KEY:'
echo ""
echo "########## 2. 按键布局文件 ##########"
ls -l /system/usr/keylayout/ 2>/dev/null
echo ""
echo "########## 3. 当前按键映射（找 power/home/back/volume） ##########"
for f in /system/usr/keylayout/*.kl /system/usr/keylayout/*.kcm; do
  [ -f "$f" ] || continue
  hits=$(grep -iE 'POWER|HOME|BACK|VOLUME|MENU|CALL|ENDCALL|SEARCH|WAKEUP' "$f" 2>/dev/null | head -12)
  if [ -n "$hits" ]; then echo "--- $f"; echo "$hits"; fi
done
echo ""
echo "########## 4. 京东相关包 ##########"
pm list packages 2>/dev/null | grep -iE 'jd|jingdong|jdiot|dangbei|jdcloud|jdiot'
echo ""
echo "########## 5. 所有第三方包（排除系统） ##########"
pm list packages -3 2>/dev/null
echo ""
echo "########## 6. 京东相关系统 App / 目录 ##########"
ls /system/app/ 2>/dev/null | grep -iE 'jd|jing|jdiot|dangbei'
ls /system/priv-app/ 2>/dev/null | grep -iE 'jd|jing|jdiot|dangbei'
echo ""
echo "########## 7. 运行中进程（找京东/当贝残留） ##########"
ps -A 2>/dev/null | grep -iE 'jd|jing|dangbei|nova|launcher|floating|float|assist'
echo ""
echo "########## 8. 悬浮球/辅助功能相关包 ##########"
pm list packages 2>/dev/null | grep -iE 'float|ball|assist|touch|overlay|swift'
echo ""
echo "########## 9. 开机自启（init.rc 中的自定义服务） ##########"
grep -iE '^service |class main' /system/etc/init/*.rc 2>/dev/null | head -30
echo ""
echo "########## 10. 后台服务数量与内存 ##########"
dumpsys activity services 2>/dev/null | grep -c 'ServiceRecord'
cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'
echo ""
echo "########## DONE ##########"
