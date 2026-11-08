# -*- coding: utf-8 -*-
"""
微光雷達 - YouTube 留言抓取（YouTube Data API v3）
用途：抓取指定影片的留言，輸出 CSV，作為跨社群討論資料源
先跑：python oauth_login.py  （取得 yt_token.json）
"""
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime

import requests

API = "https://www.googleapis.com/youtube/v3"


def get_token() -> str:
    """優先用 OAuth token（yt_token.json），其次環境變數 YT_API_KEY"""
    if os.path.exists("yt_token.json"):
        with open("yt_token.json", encoding="utf-8") as f:
            return json.load(f)["access_token"]
    key = os.environ.get("YT_API_KEY", "").strip()
    if key:
        return key
    print("找不到 yt_token.json，請先跑：python oauth_login.py")
    sys.exit(1)

# MVP 用途：抓「熱門新聞頻道」的影片留言。先用範例清單，之後換成你自己的來源
VIDEO_IDS = [
    "REPLACE_ME_1",   # <-- 換成你想追的影片 ID（網址 v= 後面那段）
]

MAX_PAGES_PER_VIDEO = 3        # 每支影片抓 3 頁留言（約 300 則）
SLEEP_BETWEEN = 0.5


def fetch_comments(token: str, video_id: str) -> list[dict]:
    rows = []
    page_token = ""
    for _ in range(MAX_PAGES_PER_VIDEO):
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "order": "time",
            "textFormat": "plainText",
            "key": token,          # YouTube API 接受 access_token 作為 key
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get(f"{API}/commentThreads", params=params, timeout=20)
        if r.status_code != 200:
            print(f"  ! API 錯誤 {video_id}: {r.status_code} {r.text[:200]}")
            break
        data = r.json()
        for item in data.get("items", []):
            sn = item["snippet"]["topLevelComment"]["snippet"]
            rows.append({
                "video_id": video_id,
                "comment_id": item["id"],
                "date": sn.get("publishedAt", "")[:10],
                "text": sn.get("textDisplay", "").replace("\n", " "),
                "like_count": sn.get("likeCount", 0),
            })
        page_token = data.get("nextPageToken", "")
        if not page_token:
            break
        time.sleep(SLEEP_BETWEEN)
    return rows


def main():
    token = get_token()

    # 沒有影片 ID 模式：改抓「搜尋熱門影片」→ 留言
    if VIDEO_IDS == ["REPLACE_ME_1"]:
        print("尚未設定影片 ID，改用搜尋模式抓取範例關鍵字的熱門影片...")
        query = sys.argv[1] if len(sys.argv) > 1 else "台灣 新聞"
        sr = requests.get(f"{API}/search", params={
            "part": "snippet", "q": query, "type": "video",
            "order": "viewCount", "maxResults": 5, "regionCode": "TW",
            "relevanceLanguage": "zh", "key": token,
        }, timeout=20)
        if sr.status_code != 200:
            print(f"搜尋失敗: {sr.status_code} {sr.text[:300]}")
            sys.exit(1)
        vids = [i["id"]["videoId"] for i in sr.json().get("items", []) if i["id"].get("videoId")]
        print(f"找到 {len(vids)} 支影片: {vids}")
    else:
        vids = VIDEO_IDS

    all_rows = []
    for vid in vids:
        print(f"[{vid}] 抓取留言...")
        rows = fetch_comments(token, vid)
        all_rows.extend(rows)
        print(f"  {len(rows)} 則留言")
        time.sleep(SLEEP_BETWEEN)

    if not all_rows:
        print("沒有抓到留言。")
        sys.exit(1)

    out = f"yt_data_{datetime.now():%Y%m%d}.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "comment_id", "date", "text", "like_count"])
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\n完成：共 {len(all_rows)} 則留言 -> {out}")


if __name__ == "__main__":
    main()
