# -*- coding: utf-8 -*-
"""暫時性測試：抓 Stock 看板標題，評估漏抓量（測完可刪）"""
import urllib.request, re, time, html as h, sys
sys.stdout.reconfigure(encoding="utf-8")

opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "Mozilla/5.0")]

titles = []
url = "https://www.ptt.cc/bbs/Stock/index.html"
for _ in range(2):
    try:
        doc = opener.open(url, timeout=15).read().decode("utf-8", "ignore")
    except Exception as e:
        print("抓取失敗:", e)
        break
    titles += [h.unescape(re.sub("<[^>]+>", "", t))
               for t in re.findall(r'<div class="title">.*?<a href="[^"]+">(.*?)</a>', doc, re.S)]
    m = re.search(r'href="(/bbs/Stock/index\d+\.html)"', doc)
    if not m:
        break
    url = "https://www.ptt.cc" + m.group(1)
    time.sleep(1)

hits = {"NV/AI": 0, "電價能源": 0, "交通": 0, "其他": 0}
for t in titles:
    if re.search(r"Nvidia|NVDA|輝達|黃仁勳|AI|晶片|GPU", t, re.I):
        hits["NV/AI"] += 1
    elif re.search(r"電價|台電|核電|能源|漲價", t):
        hits["電價能源"] += 1
    elif re.search(r"車禍|交通|公車|捷運", t):
        hits["交通"] += 1
    else:
        hits["其他"] += 1

print(f"Stock 板 2 頁共 {len(titles)} 篇標題")
for k, v in hits.items():
    print(f"  {k}: {v}")
print()
print("=== NV/AI 相關標題範例 ===")
for t in titles:
    if re.search(r"Nvidia|NVDA|輝達|黃仁勳|晶片|GPU", t, re.I):
        print("  ", t[:55])
