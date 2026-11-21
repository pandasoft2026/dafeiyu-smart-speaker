#!/data/data/com.termux/files/usr/bin/bash
PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH
cd /data/local/tmp/voicebot

echo "===== 1. 索引里找 cffi ====="
grep -A15 "^Package: cffi$" $PREFIX/var/lib/apt/lists/*Packages* 2>/dev/null | head -18
echo "--- python-cffi ---"
grep -A15 "^Package: python-cffi$" $PREFIX/var/lib/apt/lists/*Packages* 2>/dev/null | head -18

echo ""
echo "===== 2. 直接 apt-cache 查 ====="
apt-cache policy cffi python-cffi 2>&1 | head -20

echo ""
echo "===== 3. root 下 apt-get download cffi（DNS 正常）====="
su -c "cd /data/local/tmp/voicebot && $PREFIX/bin/apt-get download cffi 2>&1" | head -10
ls -la /data/local/tmp/voicebot/*ffi*.deb 2>/dev/null
