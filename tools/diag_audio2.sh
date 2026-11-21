#!/system/bin/sh
echo "########## 1. mixer 中与麦克风/TDM/阵列相关的控件 ##########"
/vendor/bin/tinymix 2>/dev/null | grep -iE 'mic|tdm|dmic|adc|array|ecref|aec|capture|ul| uplink' | head -80
echo ""
echo "########## 2. TDM_Capture 设备节点能力 ##########"
for d in pcm2c pcm1c pcm4c; do
  echo "--- $d ---"
  echo "  info:"; cat /proc/asound/card0/$d/info 2>/dev/null | head -12
  echo "  hw_params:"; cat /proc/asound/card0/$d/hw_params 2>/dev/null | head -8
  echo "  formats:"; cat /proc/asound/card0/$d/formats 2>/dev/null | head -3
done
echo ""
echo "########## 3. audio_policy_configuration 输入部分 ##########"
grep -A6 -iE 'Built-In Mic|TDM|builtin_mic' /vendor/etc/audio_policy_configuration.xml 2>/dev/null | head -50
echo ""
echo "########## 4. audio_effects（AEC/降噪/波束成形） ##########"
cat /system/etc/audio_effects.conf 2>/dev/null | grep -iE 'aec|echo|noise|ns |beam|agc|flux|effect' | head -40
echo ""
echo "########## 5. mixer_paths 里的麦克风路径 ##########"
grep -iE 'MultiMedia1_Capture|TDM_Capture|BuiltinMic|MIC|ecref|DMIC' /vendor/etc/mixer_paths.xml 2>/dev/null | head -60
echo ""
echo "########## 6. 音频 HAL 库大小（判断有无 DSP 算法） ##########"
ls -lh /vendor/lib/hw/audio.primary.*.so /vendor/lib/libmtk*audio*.so 2>/dev/null | head -20
echo ""
echo "########## 7. 麦克风硬件在 DTS 中 ##########"
find /proc/device-tree -iname '*mic*' -o -iname '*tdm*' 2>/dev/null | head -20
echo ""
echo "########## DONE ##########"
