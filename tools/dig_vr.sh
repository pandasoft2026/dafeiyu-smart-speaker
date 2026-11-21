#!/system/bin/sh
echo "########## 1. /vendor/bin/vr 是什么 ##########"
ls -l /vendor/bin/vr
file /vendor/bin/vr 2>/dev/null
echo "--- strings 找线索 ---"
strings /vendor/bin/vr 2>/dev/null | grep -iE 'usage|speech|recogn|asr|model|wake|ivw|socket|service|jd|jingdong|parameter|help' | head -40
echo ""
echo "########## 2. vr 是否在运行 / 如何启动 ##########"
ps -A | grep -iE 'vr|voice'
getprop | grep -iE 'vr|voice|speech|asr'
echo ""
echo "########## 3. vr 相关的 rc 配置 ##########"
find /vendor/etc /system/etc -name '*.rc' 2>/dev/null | while read f; do grep -l 'vr\|voice' "$f" 2>/dev/null; done | head -20
grep -riE 'service.*vr|/vendor/bin/vr|voicerecognition' /vendor/etc /system/etc 2>/dev/null | head -30
echo ""
echo "########## 4. res.bin 模型文件 ##########"
ls -lh /vendor/models/res.bin
strings /vendor/models/res.bin 2>/dev/null | grep -iE 'asr|speech|model|wake|jd|version|grammar|cn|zh' | head -30
echo ""
echo "########## 5. libvoicerecognition 导出符号 ##########"
strings /system/lib/libvoicerecognition.so 2>/dev/null | grep -iE 'create|recogn|start|stop|asr|session|engine|jni' | head -40
echo ""
echo "########## 6. 从 system/framework 找 JNI 对应 Java 类 ##########"
find /system/framework /system/app /vendor/app -iname '*.jar' -o -iname '*.apk' 2>/dev/null | while read f; do
  strings "$f" 2>/dev/null | grep -qi 'VoiceRecognition' && echo "$f"
done | head -20
echo ""
echo "########## DONE ##########"
