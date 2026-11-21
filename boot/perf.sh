#!/system/bin/sh
# 性能模式：这台设备有外接电源、只跑语音助手，直接把 CPU 钉在最高频
# 1.5GHz 是 MT8167S 的最高 OPP（没有更高档位，真正的超频需要改内核），
# 所以这里做的是「不降频」：performance 调度 + min=max + 提高语音服务优先级。

for c in 0 1 2 3; do
  G=/sys/devices/system/cpu/cpu$c/cpufreq
  [ -d "$G" ] || continue
  MAX=$(cat $G/cpuinfo_max_freq 2>/dev/null)
  echo performance > $G/scaling_governor 2>/dev/null
  echo $MAX > $G/scaling_max_freq 2>/dev/null
  echo $MAX > $G/scaling_min_freq 2>/dev/null
done

# 语音服务：提高调度优先级 + 降低被低内存杀掉的概率
for p in $(ps -A -o PID,ARGS | grep 'service\.py' | grep -v grep | sed 's/^ *//' | cut -d' ' -f1); do
  renice -n -15 -p "$p" >/dev/null 2>&1
  echo -17 > /proc/$p/oom_score_adj 2>/dev/null
done

echo "governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null) cur=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null) max=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null)"
