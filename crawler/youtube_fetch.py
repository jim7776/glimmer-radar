# -*- coding: utf-8 -*-
"""
微光雷達 - YouTube 留言抓取（YouTube Data API v3）
用途：抓取指定影片的留言，輸出 CSV，作為跨社群討論資料源
先跑：python oauth_login.py  （取得 yt_token.json）
"""
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

from build_rank import classify      # 共用同一套 8 大議題關鍵字（與榜單一致）

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

# 搜尋模式：依 8 大議題群組找相關熱門影片（讓 YouTube 留言能對上雷達議題）
# 每組 = (搜尋關鍵字, 對應的議題群組)。留言太口語、常不含關鍵字，
# 所以改用「這支影片是用哪個議題的關鍵字找到的」來歸類，比逐句比對準確。
SEARCH_QUERIES = [
    ("租屋 房東 房租", "租屋居住"),
    ("都更 危老 老屋", "都更危老"),
    ("長照 失智 照護", "長照高齡"),
    ("營養午餐 霸凌 學生", "兒少家庭"),
    ("行人 車禓 交通安全", "交通安全"),
    ("電價 台電 漲價", "電價能源"),
    ("房價 打房 房貸", "房市政策"),
    ("AI 人工智慧", "AI 科技"),
    ("輝達 黃仁勳 NVIDIA", "AI 科技"),   # NV 事件專用（近期話題，PTT/YouTube 都熱）
    ("台灣 新聞", ""),            # 泛用備援：無對應議題，改由文字比對
]
MAX_VIDEOS_PER_QUERY = 6      # 每個關鍵字最多嘗試幾支候選影片
TARGET_PER_QUERY = 1          # 每個議題至少要抓到幾支有留言的影片
MAX_TOTAL_VIDEOS = 10         # 整體最多抓幾支影片（留言量控制在每天 2,000 則內）

MAX_PAGES_PER_VIDEO = 2        # 每支影片抓 2 頁留言（約 200 則）
SLEEP_BETWEEN = 0.5


def fetch_comments(token: str, video_id: str, topic: str = "") -> list[dict]:
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
            if r.status_code == 403:
                print(f"  （{video_id} 關閉留言或不可取用，跳過）")
            else:
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
                "topic": topic,          # 這支影片是用哪個議題的關鍵字找到的
            })
        page_token = data.get("nextPageToken", "")
        if not page_token:
            break
        time.sleep(SLEEP_BETWEEN)
    return rows


def search_videos(token: str, query: str, days: int | None = None, order: str = "viewCount") -> list[str]:
    """用一個關鍵字搜尋影片，回傳影片 ID 列表
    days=7  → 只找最近 7 天發布的（留言日期才會落在近幾天）
    order=date → 依發布時間新到舊（能找到昨天/今天的新片，其留言就是最新留言）"""
    params = {
        "part": "snippet", "q": query, "type": "video",
        "order": order, "maxResults": MAX_VIDEOS_PER_QUERY, "regionCode": "TW",
        "relevanceLanguage": "zh", "key": token,
    }
    if days:
        params["publishedAfter"] = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    sr = requests.get(f"{API}/search", params=params, timeout=20)
    if sr.status_code != 200:
        print(f"  搜尋失敗（{query}）: {sr.status_code} {sr.text[:200]}")
        return []
    return [i["id"]["videoId"] for i in sr.json().get("items", []) if i["id"].get("videoId")]


def fetch_hot_videos(token: str) -> list[tuple[str, str]]:
    """抓台灣地區當日最熱門影片（比 search 便宜 100 倍配額，且是當紅影片 → 留言最新）"""
    r = requests.get(f"{API}/videos", params={
        "part": "snippet", "chart": "mostPopular", "regionCode": "TW",
        "maxResults": 50, "key": token,
    }, timeout=20)
    if r.status_code != 200:
        print(f"  熱門影片取得失敗: {r.status_code} {r.text[:200]}")
        return []
    out = []
    for item in r.json().get("items", []):
        title = item["snippet"].get("title", "")
        groups = classify(title)                 # 依影片標題分到議題（標題比留言口語好判斷）
        if groups:
            out.append((item["id"], groups[0]))
    return out


def main():
    token = get_token()

    tried, all_rows, ok_videos, ok_topics = set(), [], [], set()

    # ---- 第一優先：台灣當日熱門影片（留言都是最近的）----
    print("抓取台灣當日熱門影片...")
    hot = fetch_hot_videos(token)
    print(f"  熱門影片中與 8 大議題相關的：{len(hot)} 支")
    for vid, topic in hot:
        if len(ok_videos) >= MAX_TOTAL_VIDEOS:
            break
        tried.add(vid)
        print(f"  [{vid}]（{topic}）抓取留言...")
        rows = fetch_comments(token, vid, topic)
        time.sleep(SLEEP_BETWEEN)
        if rows:
            all_rows.extend(rows)
            ok_videos.append(vid)
            ok_topics.add(topic)
            print(f"    ✓ {len(rows)} 則留言（歸類：{topic}）")

    # ---- 第二優先：依議題關鍵字搜尋補足（熱門榜沒涵蓋到的議題）----
    print(f"\n搜尋補足，每個議題至少 {TARGET_PER_QUERY} 支有留言的影片...")
    for query, topic in SEARCH_QUERIES:
        if topic and topic in ok_topics:
            continue                      # 熱門榜已抓到這個議題，跳過
        if len(ok_videos) >= MAX_TOTAL_VIDEOS:
            break
        # 依序找候選：① 最近 2 天的新片（留言就是最新留言）
        #           ② 最近 7 天的熱門片  ③ 不限日期的熱門片
        vids: list[str] = []

        def add(cands):
            for v in cands:
                if v not in tried and v not in vids:
                    vids.append(v)

        add(search_videos(token, query, days=2, order="date"))
        if len(vids) < TARGET_PER_QUERY + 3:
            add(search_videos(token, query, days=7))
        if len(vids) < TARGET_PER_QUERY + 3:
            add(search_videos(token, query))
        vids = vids[:MAX_VIDEOS_PER_QUERY * 2]

        got = 0
        print(f"[{query}]{'（' + topic + '）' if topic else ''} 找到 {len(vids)} 支候選影片...")
        for vid in vids:
            if got >= TARGET_PER_QUERY or len(ok_videos) >= MAX_TOTAL_VIDEOS:
                break
            tried.add(vid)
            print(f"  [{vid}] 抓取留言...")
            rows = fetch_comments(token, vid, topic)
            time.sleep(SLEEP_BETWEEN)
            if rows:
                all_rows.extend(rows)
                ok_videos.append(vid)
                got += 1
                if topic:
                    ok_topics.add(topic)
                print(f"    ✓ {len(rows)} 則留言（歸類：{topic or '待文字比對'}）")
            else:
                print(f"    （無留言，換下一支）")

    if not ok_videos:
        print("沒有任何影片抓到留言。")
        sys.exit(1)

    print(f"\n成功抓到 {len(ok_videos)} 支影片的留言：{ok_videos}")
    out = f"yt_data_{datetime.now():%Y%m%d}.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "comment_id", "date", "text", "like_count", "topic"])
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"完成：共 {len(all_rows)} 則留言 -> {out}")


if __name__ == "__main__":
    main()
