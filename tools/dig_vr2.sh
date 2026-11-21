#!/system/bin/sh
echo "########## 1. libvoicerecognition 完整依赖与符号 ##########"
ls -lh /system/lib/libvoicerecognition.so /system/lib/libvoicerecognition_jni.so
echo "--- NEEDED ---"
readelf -d /system/lib/libvoicerecognition.so 2>/dev/null | grep NEEDED | head -20
echo "--- 全部导出符号 ---"
strings /system/lib/libvoicerecognition.so 2>/dev/null | grep -E '^_ZN' | head -60
echo ""
echo "########## 2. 哪些APK引用了libvoicerecognition ##########"
for f in $(find /system/app /system/priv-app /vendor/app /vendor/operator/app -name '*.apk' 2>/dev/null); do
  if unzip -p "$f" classes.dex 2>/dev/null | strings 2>/dev/null | grep -qi 'VoiceCmdRecognition\|libvoicerecognition'; then
    echo "  HIT: $f"
  fi
done
echo ""
echo "########## 3. jni 库里的类名 ##########"
strings /system/lib/libvoicerecognition_jni.so 2>/dev/null | grep -iE 'com/|java/|Voice| Recognition|jd|jingdong' | head -40
echo ""
echo "########## 4. res.bin 详细 ##########"
ls -lh /vendor/models/
find /vendor/models /data -type f -size +10k -size -20M 2>/dev/null | grep -iE 'voice|wake|pattern|feature|ubm|password|model|\.bin' | head -30
echo ""
echo "########## 5. 声纹/唤醒相关的其它文件 ##########"
find /data /vendor /system -type f 2>/dev/null | grep -iE 'voice.*\.(dat|bin|cfg|ini|txt)|wake.*\.(dat|bin)|pattern|ubm|password.*dat' | head -30
echo ""
echo "########## 6. JDHealth APK 是否含语音 ##########"
strings /vendor/operator/app/JDHealth/JDHealth.apk 2>/dev/null | grep -iE 'voicerecognition|VoiceCmd|asr|speech' | head -10
echo ""
echo "########## DONE ##########"
