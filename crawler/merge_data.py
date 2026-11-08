# -*- coding: utf-8 -*-
"""
微光雷達 - 累積式資料合併
把當日爬到的 ptt_data_*.csv / yt_data_*.csv 併入累積檔：
  data/ptt_all.csv  （依 url 去重，無 url 則看板+標題+日期）
  data/yt_all.csv   （依 comment_id 去重）
資料存在 GitHub 裡，每天只增量新增，不重爬歷史。
"""
import csv
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)


def load(path):
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def save(path, fields, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def row_key(row, primary, fallback_fields):
    v = (row.get(primary) or "").strip()
    if v:
        return (primary, v)
    return tuple(str(row.get(k, "")).strip() for k in fallback_fields)


def merge(acc_path, new_files, primary, fallback_fields):
    fields, acc = load(acc_path)
    seen = {row_key(r, primary, fallback_fields) for r in acc}
    added = 0
    for path in new_files:
        nf, rows = load(path)
        # 新檔可能有新欄位（例如 YouTube 加了 topic），欄位取聯集才不會丟資料
        for f in (nf or []):
            if f not in fields:
                fields.append(f)
        for row in rows:
            key = row_key(row, primary, fallback_fields)
            if key in seen:
                continue
            seen.add(key)
            acc.append(row)
            added += 1
    if not fields:
        print(f"  {os.path.basename(acc_path)}：尚無資料（本次也無新檔）")
        return
    save(acc_path, fields, acc)
    print(f"  {os.path.basename(acc_path)}：累積 {len(acc)} 筆（本次新增 {added}）")


def main():
    ptt_new = sorted(glob.glob(os.path.join(HERE, "ptt_data_*.csv")))
    yt_new = sorted(glob.glob(os.path.join(HERE, "yt_data_*.csv")))
    print("PTT 新檔：", [os.path.basename(p) for p in ptt_new] or "無")
    merge(os.path.join(DATA, "ptt_all.csv"), ptt_new, "url", ["board", "title", "date"])
    print("YouTube 新檔：", [os.path.basename(p) for p in yt_new] or "無")
    merge(os.path.join(DATA, "yt_all.csv"), yt_new, "comment_id", ["video_id", "date", "text"])


if __name__ == "__main__":
    main()
