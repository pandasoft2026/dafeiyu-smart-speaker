#!/system/bin/sh
PREFIX=/data/data/com.termux/files/usr
echo "===== root 环境下测试域名解析 ====="
ping -c 1 -W 2 packages.termux.dev 2>&1 | tail -2
echo "---"
ping -c 1 -W 2 mirrors.tuna.tsinghua.edu.cn 2>&1 | tail -2

echo ""
echo "===== 用 root + Termux curl 下载 Packages 索引 ====="
$PREFIX/bin/curl -sL -m 30 -o /data/local/tmp/Packages.gz "https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main/dists/stable/main/binary-armhf/Packages.gz" 2>&1
ls -l /data/local/tmp/Packages.gz 2>/dev/null

echo ""
echo "===== 尝试官方源索引 ====="
$PREFIX/bin/curl -sL -m 30 -o /data/local/tmp/Packages2.gz "https://packages.termux.dev/apt/termux-main/dists/stable/main/binary/armhf/Packages.gz" 2>&1
ls -l /data/local/tmp/Packages2.gz 2>/dev/null
