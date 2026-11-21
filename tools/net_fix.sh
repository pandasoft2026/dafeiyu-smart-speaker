#!/system/bin/sh
echo "===== 修复前路由 ====="
ip route

echo ""
echo "===== 添加默认路由 ====="
ip route add default via ${PC_IP:-192.168.1.2} dev wlan0 2>&1
echo "result=$?"

echo ""
echo "===== 修复后路由 ====="
ip route

echo ""
echo "===== 测试域名解析 ====="
ping -c 2 -W 3 mirrors.tuna.tsinghua.edu.cn 2>&1 | tail -4

echo ""
echo "===== 测试外网 HTTP（用 toybox nc 或 curl）===="
/data/data/com.termux/files/usr/bin/curl -s -m 10 -o /dev/null -w "tuna:%{http_code}\n" https://mirrors.tuna.tsinghua.edu.cn/ 2>&1
