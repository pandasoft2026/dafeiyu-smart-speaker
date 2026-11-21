#!/system/bin/sh
echo "########## 1. 所有APK中找ASR引擎关键字（深度扫描）##########"
for f in $(find /system/app /system/priv-app /vendor/app /vendor/operator/app /data/app -name '*.apk' 2>/dev/null); do
  hit=$(strings "$f" 2>/dev/null | grep -iE 'SpeechRecognizer|RecognitionService|VoiceRecognition|kws|keyword.*spot|wakeup.*word|asr.*engine|speech.*engine' | head -1)
  [ -n "$hit" ] && echo "  $(basename $f): $hit"
done
echo ""
echo "########## 2. 京东桌面残留数据目录 ##########"
ls -la /data/data/ 2>/dev/null | grep -iE 'jdiot|jd|aslauncher|voice|speech|dangbei|nova'
echo "--- 找残留模型 ---"
find /data/data /data/media -type f 2>/dev/null | grep -iE 'asr|speech|voice|wake|model|\.bin$|grammar|vocab' | grep -vE 'sogou|cache' | head -40
echo ""
echo "########## 3. system/framework 里的语音类 ##########"
for jar in /system/framework/*.jar; do
  strings "$jar" 2>/dev/null | grep -qiE 'VoiceRecognition|voicecmd' && echo "HIT $jar"
done
echo ""
echo "########## 4. 所有可执行文件里找 ASR 引擎特征 ##########"
for f in /system/bin/* /vendor/bin/*; do
  [ -f "$f" ] || continue
  s=$(strings "$f" 2>/dev/null | grep -iE 'asr_engine|speech.*recogn|kws|wakeup|voice.*engine' | head -1)
  [ -n "$s" ] && echo "  $(basename $f): $s"
done
echo ""
echo "########## 5. ro 属性里的语音配置 ##########"
getprop | grep -iE 'voice|speech|asr|wake|kws|jd|recogn'
echo ""
echo "########## 6. DuraSpeed/系统优化里语音白名单 ##########"
getprop | grep -iE 'duraspeed|whitelist|background'
echo ""
echo "########## DONE ##########"
