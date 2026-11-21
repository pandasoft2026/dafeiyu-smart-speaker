# -*- coding: utf-8 -*-
"""在设备上切换人设：python3 setmode.py sage|fish"""
import sys, json, urllib.request

mode = sys.argv[1] if len(sys.argv) > 1 else "fish"
req = urllib.request.Request("http://127.0.0.1:8899/api/mode",
                             data=json.dumps({"mode": mode}).encode(),
                             headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req, timeout=5).read().decode())
