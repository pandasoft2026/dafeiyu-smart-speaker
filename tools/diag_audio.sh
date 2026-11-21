#!/system/bin/sh
echo "########## 1. 声卡列表 ##########"
cat /proc/asound/cards 2>/dev/null
echo ""
echo "########## 2. 所有 PCM 设备（c=录音 p=播放） ##########"
cat /proc/asound/pcm 2>/dev/null
echo ""
echo "########## 3. 各 capture 设备的硬件能力 ##########"
for d in /proc/asound/card0/pcm*c; do
  [ -d "$d" ] || continue
  name=$(basename $d)
  echo "--- $d ($name) ---"
  cat "$d/hw_params" 2>/dev/null | head -12
  echo "  [formats]"; cat "$d/formats" 2>/dev/null | head -4
done
echo ""
echo "########## 4. 音频配置文件 ##########"
ls -la /system/etc/ 2>/dev/null | grep -iE 'audio|mixer|asound'
find /system /vendor -iname '*audio_policy*' -o -iname 'mixer_paths*.xml' -o -iname '*audio*config*' 2>/dev/null | head -20
echo ""
echo "########## 5. TinyALSA 工具 ##########"
for t in tinycap tinymix tinyplay; do
  p=$(which $t 2>/dev/null)
  echo "  $t = ${p:-无}"
done
echo ""
echo "########## 6. 音频 HAL / DSP 库 ##########"
find /system/lib /vendor/lib -iname '*audio*hal*' -o -iname '*aec*' -o -iname '*ns*' -o -iname '*beamform*' -o -iname '*audiosphere*' 2>/dev/null | head -30
echo ""
echo "########## 7. AudioFlinger 状态 ##########"
dumpsys media.audio_flinger 2>/dev/null | grep -iE 'capture|input|sample rate|channel|device' | head -30
echo ""
echo "########## 8. 音频策略（输入设备） ##########"
dumpsys media.audio_policy 2>/dev/null | grep -iE 'BUILTIN_MIC|MIC|input source|channel' | head -30
echo ""
echo "########## 9. 内核音频驱动日志关键词 ##########"
dmesg 2>/dev/null | grep -iE 'mic|audio|snd|dai|codec|tpd' | tail -20
echo ""
echo "########## DONE ##########"
