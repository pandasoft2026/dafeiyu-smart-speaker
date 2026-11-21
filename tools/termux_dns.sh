#!/data/data/com.termux/files/usr/bin/bash
PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH

echo "===== 写入 resolv.conf ====="
cat > $PREFIX/etc/resolv.conf <<'EOF'
nameserver 223.5.5.5
nameserver 119.29.29.29
nameserver ${PC_IP:-192.168.1.2}
EOF
chmod 644 $PREFIX/etc/resolv.conf
cat $PREFIX/etc/resolv.conf

echo ""
echo "===== 测试 Termux 用户域名解析 ====="
getent hosts mirrors.tuna.tsinghua.edu.cn 2>&1 | head -2
echo "---curl---"
curl -s -m 12 -o /dev/null -w "tuna:%{http_code}\n" https://mirrors.tuna.tsinghua.edu.cn/ 2>&1

echo ""
echo "===== apt update ====="
apt-get update -o Acquire::http::Timeout=25 2>&1 | tail -12

echo ""
echo "===== 安装 python ====="
apt-get install -y python 2>&1 | tail -20

echo ""
echo "===== 验证 ====="
python --version 2>&1
