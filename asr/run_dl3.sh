#!/system/bin/sh
cd /data/local/tmp/voicebot
exec sh py.sh download_model.py > /data/local/tmp/dl3.log 2>&1
