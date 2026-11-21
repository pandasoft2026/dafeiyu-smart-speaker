#!/data/data/com.termux/files/usr/bin/bash
PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH
cd /data/data/com.termux/files/home || exit 1

echo "===== 1. 写入清华 TUNA 镜像源 ====="
cat > $PREFIX/etc/apt/sources.list <<'EOF'
deb https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main stable main
EOF
echo "sources:"; cat $PREFIX/etc/apt/sources.list

echo ""
echo "===== 2. apt update ====="
apt-get update -o Acquire::http::Timeout=25 2>&1 | tail -15

echo ""
echo "===== 3. 安装 python ====="
apt-get install -y python 2>&1 | tail -25

echo ""
echo "===== 4. 验证 ====="
$PREFIX/bin/python --version 2>&1
