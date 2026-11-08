# -*- coding: utf-8 -*-
"""
微光雷達 - 產生多日排名資料（給前端 index.html 的 RANK_DATA）
輸入：data/ptt_all.csv（累積 PTT 討論）、data/yt_all.csv（累積 YouTube 留言）
輸出：rank_data.json（近 14 天，每天 8 組議題）

欄位：
  score    升溫分 = z-score × 量級加權（單日 ≥3 篇才計分）
  lead     領先天數：連續達門檻（≥3 篇）的天數
  baseline 過去 7 天基期均值（基期 <1 時前端改顯示「基期過低」）
  sources  跨社群來源分佈 {ptt, yt}
  links    原始出處連結（最多 3 筆）
  trend    近 14 天討論量序列（時間軸用）
"""
import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
TW = timezone(timedelta(hours=8))          # 台北時區（Actions 伺服器是 UTC）

ISSUE_GROUPS = {
    "租屋居住": ["租屋", "房租", "押金", "房東", "租約", "社會宅", "住宅"],
    "都更危老": ["都更", "危老", "重建", "容積", "建蔽"],
    "長照高齡": ["長照", "老人", "高齡", "照護", "失智", "安養"],
    "兒少家庭": ["兒少", "幼兒", "托育", "幼稚園", "學生", "營養午餐", "霸凌"],
    "交通安全": ["酒駕", "行人", "地雷", "交通事故", "肇逃", "捷運", "機車"],
    "電價能源": ["電價", "台電", "核電", "光電", "漲價", "能源"],
    "AI 科技": ["AI", "ai", "人工智慧", "ChatGPT", "機器人", "晶片"],
    "房市政策": ["房價", "打炒房", "囤房", "房貸", "升息", "實價登錄"],
}
PUBLIC_VALUE_TAGS = {"租屋居住", "都更危老", "長照高齡", "兒少家庭", "交通安全"}


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def classify(text):
    if not text:
        return []
    return [g for g, kws in ISSUE_GROUPS.items() if any(k in text for k in kws)]


def main():
    ptt = load(os.path.join(DATA, "ptt_all.csv"))
    yt = load(os.path.join(DATA, "yt_all.csv"))
    if not ptt:
        raise SystemExit("data/ptt_all.csv 是空的，請先跑 merge_data.py")

    today = datetime.now(TW).date()
    dates = [(today - timedelta(days=i)).strftime("%Y/%m/%d") for i in range(13, -1, -1)]
    date_index = {d: i for i, d in enumerate(dates)}

    series = {g: [0] * 14 for g in ISSUE_GROUPS}
    yt_series = {g: [0] * 14 for g in ISSUE_GROUPS}
    samples = defaultdict(lambda: defaultdict(list))
    links = defaultdict(lambda: defaultdict(list))

    for r in ptt:
        d = r.get("date", "")
        if d not in date_index:
            continue
        i = date_index[d]
        for g in classify(r.get("title", "")):
            series[g][i] += 1
            title = r.get("title", "")
            if len(samples[g][d]) < 3 and title not in samples[g][d]:
                samples[g][d].append(title)
            url = (r.get("url") or "").strip()
            if url and len(links[g][d]) < 3 and all(l["url"] != url for l in links[g][d]):
                links[g][d].append({"title": title[:40], "url": url})

    for r in yt:
        d = (r.get("date") or "").replace("-", "/")
        if d not in date_index:
            continue
        i = date_index[d]
        for g in classify(r.get("text", "")):
            yt_series[g][i] += 1

    out = {}
    for i, d in enumerate(dates):
        if i < 7:
            continue                      # 前 7 天不足以算基期
        items = []
        for g in ISSUE_GROUPS:
            s = series[g]
            baseline = s[i - 7:i]
            today_v = s[i]
            if sum(baseline) == 0:
                z, growth, mean = 0.0, 0.0, 0.0
            else:
                mean = statistics.mean(baseline)
                sd = statistics.pstdev(baseline)
                z = (today_v - mean) / sd if sd > 0 else (0.0 if today_v <= mean else 3.0)
                z = min(z, 10)              # 標準分封頂，避免極端值讓分數失真
                growth = (today_v - mean) / mean if mean > 0 else 0.0
            score = max(z, 0) * (1 + min(today_v, 30) / 30) if today_v >= 3 else 0.0
            last3 = sum(s[max(0, i - 2):i + 1])
            lead = 0
            for j in range(i, -1, -1):     # 連續達門檻天數（領先天數）
                if s[j] >= 3:
                    lead += 1
                else:
                    break
            items.append({
                "group": g,
                "score": round(score, 2),
                "today": today_v,
                "last3": last3,
                "growth": round(growth * 100),
                "baseline": round(mean, 2),
                "lead": lead,
                "pv": g in PUBLIC_VALUE_TAGS,
                "sample": (samples[g].get(d) or [""])[0],
                "sources": {"ptt": today_v, "yt": yt_series[g][i]},
                "links": links[g].get(d, [])[:3],
                "trend": s[max(0, i - 13):i + 1],
            })
        items.sort(key=lambda x: (-x["score"], -x["today"]))
        out[d] = [it for it in items if it["score"] > 0] + [it for it in items if it["score"] <= 0]

    with open(os.path.join(HERE, "rank_data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"PTT 累積 {len(ptt)} 筆、YouTube 累積 {len(yt)} 筆")
    print(f"輸出 rank_data.json，共 {len(out)} 天（{dates[0]} ~ {dates[-1]}）")
    for d in list(out)[-3:]:
        ranked = [x for x in out[d] if x["score"] > 0]
        if not ranked:
            print(f"  {d}  （無達標議題）")
            continue
        top = ranked[0]
        print(f"  {d}  冠軍：{top['group']}（{top['score']} 分，領先 {top['lead']} 天，"
              f"PTT {top['sources']['ptt']} / YT {top['sources']['yt']}，連結 {len(top['links'])} 筆）")


if __name__ == "__main__":
    main()
