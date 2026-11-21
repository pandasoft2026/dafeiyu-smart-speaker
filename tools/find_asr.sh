#!/system/bin/sh
echo "########## 1. 所有语音/ASR相关的 so 库（全分区）##########"
find /system /vendor /oem /data/app -name '*.so' 2>/dev/null | grep -iE 'asr|speech|voice|recogn|wake|vosk|kaldi|whisper|snowboy|keyword|sound|audio|dsp|mtk.*vr|vr.*mtk|speech' | head -80
echo ""
echo "########## 2. 可能的模型/资源文件 ##########"
find /system /vendor /oem -type f \( -iname '*.bin' -o -iname '*.dat' -o -iname '*.model' -o -iname '*.tflite' -o -iname '*.nb' -o -iname '*.pcm' -o -iname '*.dic' -o -iname '*.gram' \) 2>/dev/null | grep -iE 'asr|speech|voice|wake|keyword|vr|audio|dsp|model|graph|token' | head -60
echo ""
echo "########## 3. vendor 下所有可能的语音目录 ##########"
find /vendor /system -type d 2>/dev/null | grep -iE 'asr|speech|voice|vr|wake|audio|dsp' | head -50
echo ""
echo "########## 4. 京东相关的一切 ##########"
find /system /vendor /oem -iname '*jd*' -o -iname '*jingdong*' -o -iname '*iot*' 2>/dev/null | head -60
echo ""
echo "########## 5. 全部 native 服务/进程名 ##########"
ls /vendor/bin/ /system/bin/ 2>/dev/null | grep -iE 'asr|speech|voice|vr|wake|audio|dsp|snd' | head -40
echo ""
echo "########## 6. 第三方语音SDK特征（讯飞/百度/思必驰/云知声）##########"
find /system /vendor -name '*.so' 2>/dev/null | grep -iE 'ifly|xf|baidu|aispeech|cloudminds|unistrong|turbo|dcl|nes|srec|ivw|wakeup' | head -40
echo ""
echo "########## 7. init.rc 里的语音相关服务 ##########"
grep -riE 'asr|speech|voice|wake|ivw|dsp|vr' /system/etc/init /vendor/etc/init 2>/dev/null | head -40
echo ""
echo "########## DONE ##########"
