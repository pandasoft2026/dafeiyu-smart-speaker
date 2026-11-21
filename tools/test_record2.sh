#!/system/bin/sh
D=/data/local/tmp/audio_test
mkdir -p $D
rm -f $D/*.wav

echo "########## 测试1: pcm1c (MultiMedia1_Capture) 2ch 16k ##########"
/vendor/bin/tinycap $D/t1.pcm.wav -D 0 -d 1 -c 2 -r 16000 -b 16 -T 3 2>&1 | head -6
ls -l $D/t1.pcm.wav 2>/dev/null || echo "  无文件"
echo ""

echo "########## 测试2: pcm2c (TDM_Capture) 4ch 16k ##########"
/vendor/bin/tinycap $D/t2.tdm4.wav -D 0 -d 2 -c 4 -r 16000 -b 16 -T 3 2>&1 | head -6
ls -l $D/t2.tdm4.wav 2>/dev/null || echo "  无文件"
echo ""

echo "########## 测试3: pcm2c (TDM_Capture) 2ch 16k ##########"
/vendor/bin/tinycap $D/t3.tdm2.wav -D 0 -d 2 -c 2 -r 16000 -b 16 -T 3 2>&1 | head -6
ls -l $D/t3.tdm2.wav 2>/dev/null || echo "  无文件"
echo ""

echo "########## 测试4: pcm2c (TDM_Capture) 8ch 16k ##########"
/vendor/bin/tinycap $D/t4.tdm8.wav -D 0 -d 2 -c 8 -r 16000 -b 16 -T 3 2>&1 | head -6
ls -l $D/t4.tdm8.wav 2>/dev/null || echo "  无文件"
echo ""

echo "########## 结果：WAV 头解析 ##########"
for f in $D/*.wav; do
  [ -f "$f" ] || continue
  sz=$(stat -c%s "$f" 2>/dev/null)
  echo "--- $(basename $f) size=$sz ---"
  # channels at offset 22 (2 bytes), rate at 24 (4 bytes), bits at 34
  printf "  ch="; od -An -tu2 -j22 -N2 "$f" 2>/dev/null | tr -d ' \n'
  printf "  rate="; od -An -tu4 -j24 -N4 "$f" 2>/dev/null | tr -d ' \n'
  printf "  bits="; od -An -tu2 -j34 -N2 "$f" 2>/dev/null | tr -d ' \n'
  echo ""
done
echo "########## DONE ##########"
