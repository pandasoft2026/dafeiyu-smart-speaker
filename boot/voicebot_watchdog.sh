#!/system/bin/sh
# voicebot_watchdog - 语音服务的看门狗
#
# 之前没有任何东西盯着 service.py：它要是因为内存不足、模型异常、或者某个
# 没接住的崩溃死掉，就再也不会自己起来，用户看到的是「喊它不理、点麦克风也没
# 反应」，只能重启设备。这台设备是要在家常开的，必须能自愈。
#
# 判据两条，缺一不可：
#   1) 进程在（ps 能找到 service.py）
#   2) 端口在听（netstat 能看到 8899）—— 防「进程活着但卡死」这种假活
# 每 30 秒看一次，开销可以忽略。

BASE=/data/local/tmp/voicebot
LOG=$BASE/watchdog.log
mkdir -p "$BASE"

restart() {
  echo "$(date '+%m-%d %H:%M:%S') $1，重新拉起" >> "$LOG"
  cd "$BASE" || return
  # 先把可能有问题的残骸清干净，否则端口/麦克风会抢。
  # 匹配写成 python3 service\.py，别用宽松的 service\.py —— 后者会连
  # 正在执行这条命令的 shell 一起匹配上，把自己人杀掉。
  for p in $(ps -A -o PID,ARGS | grep -E '[p]ython3 service|[t]inycap' | sed 's/^ *//' | cut -d' ' -f1); do
    kill -9 "$p" 2>/dev/null
  done
  sleep 2

  # 起来之后必须确认端口真的在听。刚 kill 完端口可能还没释放，
  # 新进程 bind 失败会直接退出 —— 那就白等 30 秒才轮到下一轮。
  # 所以这里最多试 3 次，每次 4 秒，抢不到就不再硬抢（交给下一轮）。
  try=0
  while [ "$try" -lt 3 ]; do
    try=$((try + 1))
    setsid sh py.sh service.py >> svc.log 2>&1 &
    sleep 4
    if [ "$(netstat -tln 2>/dev/null | grep -c ':8899')" -gt 0 ]; then
      echo "$(date '+%m-%d %H:%M:%S') 第 $try 次拉起成功" >> "$LOG"
      break
    fi
    echo "$(date '+%m-%d %H:%M:%S') 第 $try 次拉起没抢到端口，重试" >> "$LOG"
    sleep 2
  done
  sh "$BASE/perf.sh" >/dev/null 2>&1
}

# 开机等一会儿，别和自启脚本抢
sleep 45

while true; do
  alive=$(ps -A -o ARGS | grep -c '[p]ython3 service')
  listen=$(netstat -tln 2>/dev/null | grep -c ':8899')
  if [ "$alive" -eq 0 ]; then
    restart "service.py 不在了"
  elif [ "$listen" -eq 0 ]; then
    restart "service.py 在但 8899 没在听（疑似卡死）"
  fi
  # 日志别无限长：超过 3MB 只留最后 300KB。这东西要常开几个月，
  # 不裁剪的话光日志就能把 /data 填满。
  # 注意用 cat > 原地覆盖，不能用 mv 换文件 —— 服务的 stdout 是重定向到
  # 这个 inode 的，换掉之后它会继续往已删除的旧 inode 写，日志就全丢了。
  sz=$(wc -c < "$BASE/svc.log" 2>/dev/null)
  if [ -n "$sz" ] && [ "$sz" -gt 3000000 ]; then
    tail -c 300000 "$BASE/svc.log" > "$BASE/svc.tail" 2>/dev/null && \
      cat "$BASE/svc.tail" > "$BASE/svc.log" && rm -f "$BASE/svc.tail"
  fi
  sleep 30
done
