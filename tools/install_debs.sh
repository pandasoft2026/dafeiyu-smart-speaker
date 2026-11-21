#!/data/data/com.termux/files/usr/bin/bash
PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH
cd /data/local/tmp/debs || exit 1

echo "===== deb 文件数 ====="
ls *.deb 2>/dev/null | wc -l

echo ""
echo "===== dpkg 批量安装 ====="
for deb in *.deb; do
  echo "--> $deb"
  dpkg -i "$deb" 2>&1 | tail -2
done

echo ""
echo "===== 强制修复依赖 ====="
dpkg --configure -a 2>&1 | tail -5

echo ""
echo "===== 验证 Python ====="
$PREFIX/bin/python --version 2>&1
$PREFIX/bin/python -c "print('HELLO from Termux Python')" 2>&1
