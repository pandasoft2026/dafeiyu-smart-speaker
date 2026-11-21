#!/system/bin/sh
echo "===== 1. DNS 属性 ====="
getprop | grep -i dns
echo ""
echo "===== 2. resolv.conf ====="
cat /system/etc/resolv.conf 2>/dev/null
echo "(appended by dhclient?)"
cat /data/misc/dhcp/dhcpcd.conf 2>/dev/null
echo ""
echo "===== 3. 网络接口 ====="
ip addr 2>/dev/null | grep -E 'inet |wlan|eth|^[0-9]'
echo ""
echo "===== 4. 路由 ====="
ip route 2>/dev/null
echo ""
echo "===== 5. 测试 DNS 服务器直连 (${PC_IP:-192.168.1.2}) ====="
ping -c 2 -W 2 ${PC_IP:-192.168.1.2} 2>&1 | tail -3
echo ""
echo "===== 6. 测试公共 DNS IP 是否可达 ====="
ping -c 1 -W 2 223.5.5.5 2>&1 | tail -2
ping -c 1 -W 2 119.29.29.29 2>&1 | tail -2
echo ""
echo "===== 7. WiFi DHCP 信息 ====="
dumpsys dhcp 2>/dev/null | grep -iE 'dns|gateway|ipaddr|server' | head -10
echo ""
echo "===== 8. HTTP IP 直连测试 ====="
/system/bin/toybox wget -q -O - --timeout=5 http://${PC_IP:-192.168.1.2}:8808/ 2>&1 | head -3
echo "(empty above = server down or wget issue)"
