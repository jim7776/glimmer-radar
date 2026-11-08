# -*- coding: utf-8 -*-
"""
微光雷達 - PTT 公開看板爬蟲
用途：抓取指定看板最近 N 頁的文章標題、日期、推噓數，輸出 CSV
資料來源：PTT 公開網頁（僅抓公開文章列表，請勿抓取需登入的個別推文內文）

連線策略（PTT 會封鎖雲端機房 IP，實測 GitHub Actions 回 403）：
  1. 直連 ptt.cc            ← 本機執行時走這條
  2. Google 翻譯轉傳 translate.goog（同語言轉傳，內容不變） ← 雲端執行時走這條
  3. allorigins 轉傳         ← 備援
"""
import csv
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

BASE = "https://www.ptt.cc"
# MVP 選擇的看板：綜合輿論 + 政治 + 房屋/租屋 + 兒少家庭 + 地方 + 公共行政
# （看板名以 https://www.ptt.cc/bbs/index.html 為準，已實測 200）
BOARDS = ["Gossiping", "HatePolitics", "home-sale", "WomenTalk",
          "BabyMother", "PublicServan", "Kaohsiung"]
MAX_PAGES_PER_BOARD = 60         # 上限保險絲（高流量看板如 Gossiping 一天可達千篇），正常用不到
SLEEP_BETWEEN = 1.5              # 請求間隔秒數，友善爬蟲（PTT 對高頻會回 429）
MAX_PAGE_RETRIES = 3             # 單頁失敗最多重試次數
RETRY_BACKOFF = 45               # 每次重試前的等待秒數（會遞增）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
COOKIES = {"over18": "1"}        # PTT 公開頁面年齡確認 cookie


# ---------- 轉傳管道（雲端 IP 被 PTT 封鎖時的替代路徑） ----------
def to_translate(url: str) -> str:
    """把 ptt.cc 網址轉成 Google 翻譯轉傳網址（sl=auto&tl=zh-TW：只轉傳、不翻譯）"""
    p = urllib.parse.urlsplit(url)
    host = p.netloc.replace(".", "-") + ".translate.goog"
    q = urllib.parse.urlencode({"_x_tr_sl": "auto", "_x_tr_tl": "zh-TW", "_x_tr_hl": "zh-TW"})
    return urllib.parse.urlunsplit(("https", host, p.path, q, ""))


def from_translate(href: str) -> str:
    """把轉傳網址還原回原始 ptt.cc 網址（含協定相對 // 開頭）"""
    if "translate.goog" not in href:
        return href
    if href.startswith("//"):
        href = "https:" + href
    p = urllib.parse.urlsplit(href)
    host = p.netloc.split(".")[0].replace("-", ".")      # www-ptt-cc -> www.ptt.cc
    query = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
             if not k.startswith("_x_tr_")]               # 去掉 _x_tr_* 參數
    return urllib.parse.urlunsplit(("https", host, p.path, urllib.parse.urlencode(query), p.fragment))


_direct_blocked = False        # 直連失敗一次後就不再浪費請求（雲端 IP 被封鎖時）


def fetch_html(url: str) -> str:
    """依序嘗試：直連 → Google 轉傳 → allorigins。回傳含 r-ent 文章列表的 HTML"""
    global _direct_blocked
    attempts = []
    if not _direct_blocked:
        attempts.append(("直連", url, True))
    attempts += [
        ("Google轉傳", to_translate(url), False),
        ("allorigins", "https://api.allorigins.win/raw?url=" + urllib.parse.quote(url, safe=""), False),
    ]
    errors = []
    for name, target, send_cookie in attempts:
        try:
            r = requests.get(target, headers=HEADERS,
                             cookies=COOKIES if send_cookie else None, timeout=30)
            if r.status_code == 200 and 'class="r-ent"' in r.text:
                print(f"    ✓ {name} 取得 {len(r.text)} 字元")
                return r.text
            errors.append(f"{name}=HTTP {r.status_code}")
            if name == "直連":
                _direct_blocked = True      # PTT 封鎖此 IP，後續直接走轉傳
        except Exception as e:
            errors.append(f"{name}={type(e).__name__}")
            if name == "直連":
                _direct_blocked = True
        time.sleep(1)
    raise RuntimeError("所有管道皆失敗：" + "、".join(errors))


def abs_url(href: str) -> str:
    """href 轉絕對網址（並把轉傳網址還原成 ptt.cc）"""
    href = from_translate(href or "")
    if href.startswith("http"):
        return href
    return BASE + href


def fetch_page(board: str, page_url: str) -> tuple[list[dict], str | None]:
    """抓一頁文章列表，回傳 (文章列表, 上一頁網址)"""
    html = fetch_html(page_url)
    soup = BeautifulSoup(html, "lxml")

    posts = []
    for entry in soup.select("div.r-ent"):
        title_a = entry.select_one("div.title a")
        if title_a is None:
            continue  # 刪文
        title = title_a.get_text(strip=True)
        href = abs_url(title_a.get("href", ""))

        # 推噓數：div.nrec > span
        nrec = entry.select_one("div.nrec")
        push_text = nrec.get_text(strip=True) if nrec else ""
        push = parse_push(push_text)

        # 日期：div.date
        date_el = entry.select_one("div.date")
        date_str = date_el.get_text(strip=True) if date_el else ""

        posts.append({
            "board": board,
            "title": title,
            "date": normalize_date(date_str),
            "push": push,
            "url": href,
        })

    # 上一頁連結（PTT 按鈕文字為「‹ 上頁」，href 指向 indexN.html）
    prev_links = [a for a in soup.select("a.btn.wide")
                  if a.get("href") and "上頁" in a.get_text()]
    prev = prev_links[0] if prev_links else None
    prev_url = abs_url(prev["href"]) if prev and prev.get("href") else None
    return posts, prev_url


def parse_push(text: str) -> int:
    """把推/噓/箭頭符號轉成數值（推=+1, 噓=-1, 箭頭=0, 爆=+100）"""
    text = text.strip()
    if not text:
        return 0
    if text == "爆":
        return 100
    if text.startswith("X"):
        return -100
    m = re.match(r"^([+-]?)(\d+)$", text)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        return sign * int(m.group(2))
    return 0


def normalize_date(d: str) -> str:
    """ '11/06' -> '2026/11/06'（補年份，跨年時 12 月為前一年）"""
    m = re.match(r"^(\d{1,2})/(\d{1,2})$", d)
    if not m:
        return d
    month, day = int(m.group(1)), int(m.group(2))
    year = datetime.now().year
    # 若抓到的月份比目前月份大很多（例如現在 1 月卻抓到 12 月），代表是去年
    if month > datetime.now().month + 2:
        year -= 1
    return f"{year}/{month:02d}/{day:02d}"


def crawl(cutoff_override: str | None = None) -> list[dict]:
    # 累積式爬取：一路往回抓，直到「昨天以前」的文章出現為止，
    # 確保昨天與今天兩天資料完整（高流量看板如 Gossiping 需要抓較多頁）
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    cutoff = cutoff_override or (tw_now - timedelta(days=1)).strftime("%Y/%m/%d")
    print(f"回抓目標：抓到 {cutoff} 以前的文章就停（台北時間 {tw_now:%Y/%m/%d %H:%M}，每看板上限 {MAX_PAGES_PER_BOARD} 頁）")
    all_posts = []
    for board in BOARDS:
        url = f"{BASE}/bbs/{board}/index.html"
        print(f"[{board}] 開始抓取...")
        pages = 0
        attempts = 0
        while url and pages < MAX_PAGES_PER_BOARD:
            try:
                posts, prev_url = fetch_page(board, url)
            except Exception as e:
                # PTT 對高頻請求會回 429：等待後重試，而非直接放棄整個看板
                attempts += 1
                if attempts > MAX_PAGE_RETRIES:
                    print(f"  ! 頁面失敗（已重試 {MAX_PAGE_RETRIES} 次）{url}: {e}")
                    break
                wait = RETRY_BACKOFF * attempts
                print(f"  ⏳ {e} → 等 {wait} 秒後重試第 {attempts} 次...")
                time.sleep(wait)
                continue
            attempts = 0
            all_posts.extend(posts)
            print(f"  第 {pages + 1} 頁：{len(posts)} 篇")
            url = prev_url
            pages += 1
            # 該頁「多數文章」已早於 cutoff → 昨天以前都抓完了，停止此看板
            # 用中位數而非最小值：頁面混有置底舊文（日期很舊），最小值會誤判
            valid = sorted(p["date"] for p in posts if re.match(r"^\d{4}/\d{2}/\d{2}$", p["date"]))
            if valid and valid[len(valid) // 2] < cutoff:
                print(f"  已到 {cutoff} 以前（頁面中位日期 {valid[len(valid) // 2]}），停止抓取")
                break
            time.sleep(SLEEP_BETWEEN)
        time.sleep(SLEEP_BETWEEN)
    return all_posts


def main():
    # 可選參數：python ptt_crawler.py [回抓截止日 YYYY/MM/DD] [每看板最大頁數] [只抓哪個看板,逗號分隔]
    cutoff_override = sys.argv[1] if len(sys.argv) > 1 else None
    global MAX_PAGES_PER_BOARD, BOARDS
    if len(sys.argv) > 2:
        MAX_PAGES_PER_BOARD = int(sys.argv[2])
    if len(sys.argv) > 3:
        BOARDS = [b.strip() for b in sys.argv[3].split(",") if b.strip()]
        print(f"只抓這幾個看板：{BOARDS}")
    posts = crawl(cutoff_override)
    if not posts:
        print("沒有抓到任何資料，請檢查網路。")
        sys.exit(1)

    out = f"ptt_data_{datetime.now():%Y%m%d}.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["board", "title", "date", "push", "url"])
        writer.writeheader()
        writer.writerows(posts)

    print(f"\n完成：共 {len(posts)} 篇 -> {out}")
    print("欄位：board(看板) / title(標題) / date(日期) / push(推噓) / url(連結)")


if __name__ == "__main__":
    main()
