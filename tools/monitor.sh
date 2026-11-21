#!/system/bin/sh
# 长跑监控：每 60 秒记一次关键进程的 CPU/内存/线程/句柄，写 /data/local/tmp/voicebot/mon.log
# 用法：sh monitor.sh [分钟数]
cd /data/local/tmp/voicebot || exit 1
MIN=${1:-30}
rm -f mon.log
END=$(( $(date +%s) + MIN * 60 ))

cpu_of() {  # $1=pid -> 累计 tick（utime+stime，第 14/15 字段）
  [ -f "/proc/$1/stat" ] || { echo 0; return; }
  set -- $(cat "/proc/$1/stat")
  echo $(( ${14} + ${15} ))
}

prev_py=0; prev_app=0
while [ "$(date +%s)" -lt "$END" ]; do
  PY=$(ps -A -o PID,ARGS | grep '[s]ervice\.py' | sed 's/^ *//' | cut -d' ' -f1 | head -1)
  APP=$(pidof com.dafeiyu.home)
  LINE="$(date +%H:%M:%S)"
  if [ -n "$PY" ]; then
    C=$(cpu_of "$PY")
    RSS=$(ps -o RSS -p "$PY" 2>/dev/null | tail -1 | tr -d ' ')
    THR=$(ls /proc/$PY/task 2>/dev/null | wc -l)
    FD=$(ls /proc/$PY/fd 2>/dev/null | wc -l)
    if [ "$prev_py" -gt 0 ]; then
      LINE="$LINE py cpu=$(( (C - prev_py) * 10 / 600 ))% rss=${RSS}k thr=$THR fd=$FD"
    else
      LINE="$LINE py rss=${RSS}k thr=$THR fd=$FD"
    fi
    prev_py=$C
  else
    LINE="$LINE py=DEAD"
  fi
  if [ -n "$APP" ]; then
    C=$(cpu_of "$APP")
    RSS=$(ps -o RSS -p "$APP" 2>/dev/null | tail -1 | tr -d ' ')
    if [ "$prev_app" -gt 0 ]; then
      LINE="$LINE | app cpu=$(( (C - prev_app) * 10 / 600 ))% rss=${RSS}k"
    else
      LINE="$LINE | app rss=${RSS}k"
    fi
    prev_app=$C
  else
    LINE="$LINE | app=DEAD"
  fi
  TC=$(ps -A -o ARGS | grep -c '[t]inycap')
  LOAD=$(cut -d' ' -f1 /proc/loadavg)
  AVAIL=$(grep MemAvailable /proc/meminfo | tr -s ' ' | cut -d' ' -f2)
  LINE="$LINE | tinycap=$TC load=$LOAD avail=$(( AVAIL / 1024 ))M"
  echo "$LINE" >> mon.log
  sleep 60
done
echo "monitor done" >> mon.log
