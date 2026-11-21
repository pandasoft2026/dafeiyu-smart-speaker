# -*- coding: utf-8 -*-
"""定位 speech.platform.bing.com 在设备上建连慢的环节：DNS / IPv6 / 单个 IP。"""
import socket
import sys
import time

HOST = "speech.platform.bing.com"


def main():
    print("host = %s" % HOST)

    # 1) getaddrinfo 总耗时与结果
    t = time.time()
    try:
        infos = socket.getaddrinfo(HOST, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except Exception as e:
        print("1 getaddrinfo FAIL %s" % e)
        infos = []
    d1 = time.time() - t
    print("1 getaddrinfo     %.2fs  %d 条" % (d1, len(infos)))

    addrs = []
    for af, st, proto, cname, sa in infos:
        tag = "v6" if af == socket.AF_INET6 else "v4"
        print("    %s  %s" % (tag, sa[0]))
        addrs.append((af, sa[0]))

    seen = set()
    uniq = []
    for af, ip in addrs:
        if (af, ip) in seen:
            continue
        seen.add((af, ip))
        uniq.append((af, ip))

    # 2) 逐个 IP 直连（3 秒超时），跳过 DNS
    for af, ip in uniq:
        t = time.time()
        try:
            s = socket.socket(af, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((ip, 443))
            s.close()
            print("2 connect %-40s %.2fs OK" % (ip, time.time() - t))
        except Exception as e:
            print("2 connect %-40s %.2fs FAIL %s" % (ip, time.time() - t, e))

    # 3) 用域名连（会走 getaddrinfo + 逐个尝试）
    t = time.time()
    try:
        s = socket.create_connection((HOST, 443), 3)
        s.close()
        print("3 create_connection(HOST)  %.2fs OK" % (time.time() - t))
    except Exception as e:
        print("3 create_connection(HOST)  %.2fs FAIL %s" % (time.time() - t, e))

    # 4) 强制 IPv4 连
    t = time.time()
    try:
        s = socket.create_connection((HOST, 443), 3, source_address=None)
        s.close()
        print("4 二次 create_connection   %.2fs（看是否被缓存提速）" % (time.time() - t))
    except Exception as e:
        print("4 二次 create_connection   FAIL %s" % e)


if __name__ == "__main__":
    main()
