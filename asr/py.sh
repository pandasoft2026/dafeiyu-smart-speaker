#!/system/bin/sh
# Termux 环境启动器（从 root shell 调用）
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export TMPDIR=$PREFIX/tmp
export PATH=$PREFIX/bin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=$PREFIX/lib
export LANG=en_US.UTF-8
cd /data/local/tmp/voicebot || exit 1
exec $PREFIX/bin/python3 "$@"
