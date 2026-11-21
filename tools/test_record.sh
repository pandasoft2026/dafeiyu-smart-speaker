#!/system/bin/sh
D=/data/local/tmp/audio_test
mkdir -p $D
echo "########## 1. 查看当前 tinymix 关键控件值 ##########"
/vendor/bin/tinymix 2>/dev/null | grep -iE 'PGA Capture|AIN Mux|AIF TX Mux|ADC[1-8]_MUTE|Dmic Ch Phase|Audio Mic|Micbias'
echo ""
echo "########## 2. 测试1: 默认 Android capture (pcm1c, 2ch, 16k, 3秒) ##########"
timeout 6 /vendor/bin/tinycap -D 0 -d 1 -c 2 -r 16000 -b 16 $D/default_2ch.wav 2>&1 | head -5
ls -l $D/default_2ch.wav 2>/dev/null
echo ""
echo "########## 3. 测试2: TDM_Capture (pcm2c, 尝试4ch/8ch/16k) ##########"
timeout 6 /vendor/bin/tinycap -D 0 -d 2 -c 4 -r 16000 -b 16 $D/tdm_4ch.wav 2>&1 | head -5
ls -l $D/tdm_4ch.wav 2>/dev/null
echo ""
echo "########## 4. 测试3: TDM_Capture 8ch ##########"
timeout 6 /vendor/bin/tinycap -D 0 -d 2 -c 8 -r 16000 -b 16 $D/tdm_8ch.wav 2>&1 | head -5
ls -l $D/tdm_8ch.wav 2>/dev/null
echo ""
echo "########## 5. 录制文件头（判断实际声道数/采样率） ##########"
for f in $D/*.wav; do
  [ -f "$f" ] || continue
  echo "--- $f ---"
  # WAV header: bytes 22-23 = channels, 24-27 = sample rate
  od -An -tu2 -j22 -N2 "$f" 2>/dev/null | xargs echo "  channels:"
  od -An -tu4 -j24 -N4 "$f" 2>/dev/null | xargs echo "  samplerate:"
  od -An -tu4 -j40 -N4 "$f" 2>/dev/null | xargs echo "  data_size:"
done
echo ""
echo "########## DONE ##########"
