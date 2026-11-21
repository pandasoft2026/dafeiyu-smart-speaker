#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "===== 1. apt 源 ====="
cat $PREFIX/etc/apt/sources.list 2>/dev/null
echo ""
echo "===== 2. apt update ====="
apt-get update -o Acquire::http::Timeout=20 2>&1 | tail -20
echo ""
echo "===== 3. 检查 python 包可用性 ====="
apt-cache policy python 2>&1 | head -10
