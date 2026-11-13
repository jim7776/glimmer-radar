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

# ---------- 注入 KNOWLEDGE（主題定義）從 keywords.json ----------
import json as _json
topics_path = os.path.abspath(os.path.join(HERE, "..", "keywords.json"))
with open(topics_path, encoding="utf-8") as f:
    topics_raw = _json.load(f)
knowledge = {}
for name, info in topics_raw.items():
    knowledge[name] = {
        "keywords": info.get("keywords", []),
        "angles": info.get("angles", []),
        "sources": info.get("sources", []),
    }
knowledge_str = "const KNOWLEDGE = " + _json.dumps(knowledge, ensure_ascii=False, separators=(",", ":")) + ";"
with open(HTML, encoding="utf-8", newline="") as f:
    html2 = f.read()
new_html2, n2 = re.subn(
    r"const KNOWLEDGE = \{[\s\S]*?\};",
    knowledge_str,
    html2,
    count=1,
)
if n2 != 1:
    raise SystemExit(f"找不到 KNOWLEDGE 區塊（替換 {n2} 次）")
with open(HTML, "w", encoding="utf-8", newline="") as f:
    f.write(new_html2)
print(f"已注入 KNOWLEDGE（{len(knowledge)} 個主題）")

print(f"已注入 index.html（{len(data)} 字元）")
