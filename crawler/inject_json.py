# -*- coding: utf-8 -*-
"""
微光雷達 - 把 rank_data.json 注入 index.html 的 const RANK_DATA 區塊
（GitHub Pages 是靜態頁，資料直接內嵌，無需後端）
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.abspath(os.path.join(HERE, "..", "index.html"))
JSON = os.path.join(HERE, "rank_data.json")

with open(JSON, encoding="utf-8") as f:
    data = f.read().strip()

with open(HTML, encoding="utf-8", newline="") as f:      # newline="" 保留原換行符
    html = f.read()

new_html, n = re.subn(
    r"const RANK_DATA = \{[\s\S]*?\n\};",
    "const RANK_DATA = " + data + ";",
    html,
    count=1,
)
if n != 1:
    raise SystemExit(f"找不到 RANK_DATA 區塊（替換 {n} 次）")

with open(HTML, "w", encoding="utf-8", newline="") as f:
    f.write(new_html)

print(f"已注入 index.html（{len(data)} 字元）")
