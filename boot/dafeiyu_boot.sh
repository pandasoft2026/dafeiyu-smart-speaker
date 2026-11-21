#!/system/bin/sh
# 大肥鱼语音助手 · 开机自启
# 放在 /data/adb/service.d/ 下，Magisk 开机执行

(
  sleep 20

  # 0) 性能模式：这台设备有外接电源，CPU 直接钉最高频，不降频
  sh /data/local/tmp/voicebot/perf.sh >/dev/null 2>&1

  # 1) 音频：打开功放与主音量（Android 音频服务会重置，故尽早设置并复查）
  /vendor/bin/tinymix "Audio Amp Playback Volume" 7 7 2>/dev/null
  /vendor/bin/tinymix "Master Volume" 219 2>/dev/null

  # 2) 媒体音量调高
  for i in 1 2 3 4 5 6; do
    if media volume --stream 3 --set 3 >/dev/null 2>&1; then break; fi
    sleep 2
  done

  # 2.5) 息屏策略：10 分钟没人操作就熄屏；但语音服务必须照常工作。
  #  - stay_on_while_plugged_in 必须清零，否则插着电源会永远亮着
  #  - wake_lock 钉住内核唤醒锁：否则熄屏后 CPU 进休眠，tinycap 会断流漏唤醒
  settings put global stay_on_while_plugged_in 0
  settings put system screen_off_timeout 600000
  echo voicebot > /sys/power/wake_lock

  # 2.6) 干掉出厂自带的无障碍悬浮球（com.bs.smarttouchpro，屏幕上那个半透明
  # 白圈）。它会一直盖在所有应用最上层，既挡视线又白白多合成一层；实测在
  # 浅色界面像个"残影圆圈"，在深色界面特别明显。清空无障碍服务即可让圈消失，
  # 应用本身不卸载，用户想用随时能用设置里重新打开。
  settings put secure enabled_accessibility_services ''
  settings put secure accessibility_enabled 0

  # 3) 启动离线语音服务（先清掉残留实例）
  pkill -f "python3 service.py" 2>/dev/null
  sleep 1
  cd /data/local/tmp/voicebot || exit 0
  setsid sh py.sh service.py > svc.log 2>&1 &
  sleep 2
  # 语音服务提优先级，别被低内存杀手干掉
  sh /data/local/tmp/voicebot/perf.sh >/dev/null 2>&1

  # 4) 等模型就绪后把桌面拉到前台
  sleep 8
  am start -n com.dafeiyu.home/.MainActivity >/dev/null 2>&1

  # 5) 二次校正音频（此时 HAL 已完全就绪）
  sleep 6
  /vendor/bin/tinymix "Audio Amp Playback Volume" 7 7 2>/dev/null
  media volume --stream 3 --set 3 >/dev/null 2>&1
  sh /data/local/tmp/voicebot/perf.sh >/dev/null 2>&1

  # 6) 悬浮球会自己重新注册无障碍服务，开机后再压一次
  sleep 20
  settings put secure enabled_accessibility_services ''
  settings put secure accessibility_enabled 0
  settings put global stay_on_while_plugged_in 0
  settings put system screen_off_timeout 600000
) &
