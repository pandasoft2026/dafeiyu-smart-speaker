#!/bin/sh
# 统一 adb 入口：保证 daemon 在、保证已连接，再执行命令
# 用法: ./ah.sh <adb-args...>
ADB="/d/workbuddy/2026-11-19-10-59-25/tools/platform-tools/adb.exe"
DEV="${SPEAKER_IP:-192.168.1.50}:5555"
export MSYS_NO_PATHCONV=1

ensure() {
  # daemon 未起就先起
  if ! "$ADB" devices 2>/dev/null | grep -q "$DEV"; then
    "$ADB" connect "$DEV" >/dev/null 2>&1
  fi
  if ! "$ADB" devices 2>/dev/null | grep -q "$DEV"; then
    sleep 2
    "$ADB" kill-server >/dev/null 2>&1
    "$ADB" start-server >/dev/null 2>&1
    sleep 1
    "$ADB" connect "$DEV" >/dev/null 2>&1
  fi
}

ensure
# 真正执行，失败再确保一次
"$ADB" -s "$DEV" "$@" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  ensure
  "$ADB" -s "$DEV" "$@"
  rc=$?
fi
exit $rc
