#!/data/data/com.termux/files/usr/bin/bash
PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH

echo "===== 1. 写入正确的源（官方域名，root DNS 可达）===="
cat > $PREFIX/etc/apt/sources.list <<'EOF'
deb https://packages.termux.dev/apt/termux-main stable main
EOF
cat $PREFIX/etc/apt/sources.list

echo ""
echo "===== 2. 修权限（用 root 之外的方式）===="
chown -R u0_a12:u0_a12 $PREFIX/etc/apt 2>/dev/null || true
chown -R u0_a12:u0_a12 $PREFIX/cache/apt 2>/dev/null || true

echo ""
echo "===== 3. apt update ====="
apt-get update -o Acquire::http::Timeout=30 2>&1 | tail -15

echo ""
echo "===== 4. 安装 python ====="
apt-get install -y python 2>&1 | tail -30

echo ""
echo "===== 5. 验证 ====="
python --version 2>&1
python -c "print('python works')" 2>&1
