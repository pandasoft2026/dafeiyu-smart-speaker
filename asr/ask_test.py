import json, urllib.request, time
t0 = time.time()
req = urllib.request.Request("http://127.0.0.1:8899/api/ask",
                            data=json.dumps({"text": "你好", "history": []}).encode(),
                            headers={"Content-Type": "application/json"})
try:
    r = urllib.request.urlopen(req, timeout=45)
    print("%.1fs" % (time.time() - t0), r.read().decode()[:200])
except Exception as e:
    print("%.1fs ERR" % (time.time() - t0), type(e).__name__, e)
