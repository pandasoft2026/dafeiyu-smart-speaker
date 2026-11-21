#!/system/bin/sh
echo "########## 1. 语音识别服务 ##########"
dumpsys speech_recognition 2>/dev/null | head -40
echo ""
echo "########## 2. 系统语音包/识别引擎 ##########"
pm list packages 2>/dev/null | grep -iE 'speech|voice|recogn|asr|google|tts|srec|speechrecognition'
echo ""
echo "########## 3. SpeechRecognizer 实现 ##########"
cmd package query-intent-activities -a android.speech.RecognitionService 2>/dev/null | head -30
echo ""
echo "########## 4. 系统 TTS 引擎 ##########"
pm list packages 2>/dev/null | grep -iE 'tts|pico|speech|voice'
echo "--- TTS engines ---"
dumpsys text_services 2>/dev/null | grep -iE 'engine|tts|default' | head -20
echo ""
echo "########## 5. 离线语音资源 ##########"
find /system /vendor /data -iname '*.dic' -o -iname '*asr*' -o -iname '*speech*model*' 2>/dev/null | head -20
echo ""
echo "########## 6. 京东语音相关残留 ##########"
find /system/app /system/priv-app /vendor/app -maxdepth 1 -iname '*voice*' -o -iname '*speech*' -o -iname '*asr*' 2>/dev/null
echo ""
echo "########## DONE ##########"
