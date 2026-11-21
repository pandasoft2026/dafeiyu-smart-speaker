#!/system/bin/sh
# 测试：持续把当贝主界面顶到前台，压制豆包聊天页
MAIN="com.larus.nova/com.larus.home.impl.MainActivity"
CHAT="com.larus.bmhome.chat.ChatActivity"

echo "=== 启动守护测试（30秒，每2秒拉一次主界面）==="
i=0
while [ $i -lt 15 ]; do
  cur=$(dumpsys window windows 2>/dev/null | grep -m1 'mCurrentFocus' | grep -oE 'com\.larus\.nova/[^ }]*' | head -1)
  echo "[$i] focus=$cur"
  case "$cur" in
    *ChatActivity*)
      echo "    -> 发现豆包聊天页，拉回主界面"
      am start -n "$MAIN" --activity-clear-top >/dev/null 2>&1
      ;;
  esac
  sleep 2
  i=$((i+1))
done
echo "=== 最终状态 ==="
dumpsys window windows 2>/dev/null | grep -m1 'mCurrentFocus'
