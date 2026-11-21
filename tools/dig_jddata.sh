#!/system/bin/sh
echo "########## 1. 京东桌面数据目录结构 ##########"
find /data/data/com.oversea.aslauncher -maxdepth 3 -type d 2>/dev/null | head -50
echo ""
echo "########## 2. 语音/模型相关文件 ##########"
find /data/data/com.oversea.aslauncher -type f 2>/dev/null | grep -iE 'voice|wake|asr|speech|model|kws|pattern|feature|ubm|\.bin|\.dat|\.wav|grammar|word|词' | head -60
echo ""
echo "########## 3. 所有文件按大小（找模型大文件）##########"
find /data/data/com.oversea.aslauncher -type f -size +50k 2>/dev/null | head -40
echo ""
echo "########## 4. shared_prefs 里的语音配置 ##########"
ls /data/data/com.oversea.aslauncher/shared_prefs/ 2>/dev/null | grep -iE 'voice|wake|speech|asr|jd|setting'
for f in /data/data/com.oversea.aslauncher/shared_prefs/*voice* /data/data/com.oversea.aslauncher/shared_prefs/*wake* /data/data/com.oversea.aslauncher/shared_prefs/*speech*; do
  [ -f "$f" ] && { echo "--- $f"; cat "$f" 2>/dev/null | head -30; }
done
echo ""
echo "########## 5. jdiot.tailor 数据 ##########"
find /data/data/com.jdiot.tailor -type f 2>/dev/null | head -40
echo ""
echo "########## 6. files 目录 ##########"
find /data/data/com.oversea.aslauncher/files /data/data/com.oversea.aslauncher/databases -type f 2>/dev/null | head -40
echo ""
echo "########## DONE ##########"
