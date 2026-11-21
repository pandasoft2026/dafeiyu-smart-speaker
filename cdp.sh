#!/bin/sh
# 一键在设备 WebView 里执行 JS（forward + 取值 + 执行必须在同一条命令内完成，
# 因为 adb forward 在命令结束/连接断开后会被回收）
# 用法: ./cdp.sh 'location.href'
#       ./cdp.sh 'document.elementsFromPoint(1120,501).map(e=>e.tagName+"."+e.className)'
set -e
ADB="/d/workbuddy/2026-11-19-10-59-25/tools/platform-tools/adb.exe"
DEV="${SPEAKER_IP:-192.168.1.50}:5555"
export MSYS_NO_PATHCONV=1

[ $# -ge 1 ] || { echo "usage: cdp.sh <js>"; exit 2; }
EXPR="$1"

ensure() {
  if ! "$ADB" devices 2>/dev/null | grep -q "$DEV"; then
    "$ADB" connect "$DEV" >/dev/null 2>&1
    sleep 1
  fi
}
ensure

PID=$("$ADB" -s "$DEV" shell "pidof com.dafeiyu.home" 2>/dev/null | tr -d '\r\n ')
[ -z "$PID" ] && PID=$("$ADB" -s "$DEV" shell "ps -A | grep dafeiyu" 2>/dev/null | tr -s ' ' | cut -d' ' -f2 | tr -d '\r\n ')
if [ -z "$PID" ]; then echo "NO_PID(应用没在跑)" >&2; exit 3; fi

SOCK="webview_devtools_remote_$PID"
# 老一点的 WebView 用的是 webview_devtools_remote_<pid>，也兼容默认名
"$ADB" -s "$DEV" forward tcp:9222 "localabstract:$SOCK" >/dev/null 2>&1 || \
  "$ADB" -s "$DEV" forward tcp:9222 localabstract:webview_devtools_remote >/dev/null 2>&1

JSON=$(curl -s --max-time 6 http://127.0.0.1:9222/json)
URL=$(printf '%s' "$JSON" | grep -o '"webSocketDebuggerUrl":"[^"]*"' | head -1 | sed 's/.*:"//; s/"$//')
if [ -z "$URL" ]; then
  # 这台设备的老 WebView 只给 devtoolsFrontendUrl，从里面的 ws= 抠地址
  PAGEID=$(printf '%s' "$JSON" | grep -o '"id":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"id":[[:space:]]*"//; s/"$//')
  [ -n "$PAGEID" ] && URL="ws://127.0.0.1:9222/devtools/page/$PAGEID"
fi
if [ -z "$URL" ]; then
  echo "NO_WS_URL" >&2
  printf '%s' "$JSON" | head -c 400 >&2
  exit 4
fi

node "D:/workbuddy/2026-11-19-10-59-25/cdp3.js" "$URL" "$EXPR"
