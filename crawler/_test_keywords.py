# -*- coding: utf-8 -*-
"""評估擴充關鍵字效果（修正版，測完可刪）"""
import csv, sys, copy
sys.stdout.reconfigure(encoding="utf-8")

rows = list(csv.DictReader(open("data/ptt_all.csv", encoding="utf-8-sig")))
recent = [r for r in rows if r["date"] >= "2026/11/11"]

current = {
    "租屋居住": ["租屋", "房租", "押金", "房東", "租約", "社會宅", "住宅"],
    "都更危老": ["都更", "危老", "重建", "容積", "建蔽"],
    "長照高齡": ["長照", "老人", "高齡", "照護", "失智", "安養"],
    "兒少家庭": ["兒少", "幼兒", "托育", "幼稚園", "學生", "營養午餐", "霸凌"],
    "交通安全": ["酒駕", "行人", "地雷", "交通事故", "肇逃", "捷運", "機車"],
    "電價能源": ["電價", "台電", "核電", "光電", "漲價", "能源"],
    "AI 科技": ["AI", "ai", "人工智慧", "ChatGPT", "機器人", "晶片", "輝達",
                "黃仁勳", "老黃", "NVIDIA", "nvidia", "顯示卡", "GPU", "5090", "RTX"],
    "房市政策": ["房價", "打房", "房貸", "房市", "炒房", "首購", "換屋"],
}

expanded = copy.deepcopy(current)
expanded["交通安全"] += ["車禍", "超速", "闖紅燈", "違規", "酒測", "救護", "公車",
                     "台鐵", "火車", "交通", "駕照", "追撞", "死傷"]
expanded["長照高齡"] += ["長者", "銀髮", "照服員", "養老", "獨居"]
expanded["兒少家庭"] += ["少子化", "生小孩", "育兒", "托嬰", "營養", "午餐",
                     "兒童", "青少年", "月子"]
expanded["電價能源"] += ["核能", "發電", "缺電", "電費", "綠電", "太陽能", "碳"]
expanded["租屋居住"] += ["租房", "租金", "套房", "分租"]
expanded["房市政策"] += ["買房", "預售", "成屋", "央行", "青安", "囤房"]
expanded["都更危老"] += ["老屋", "危樓", "改建", "容積率"]
expanded["AI 科技"] += ["nvda", "OpenAI", "LLM", "深度學習", "伺服器", "AMD",
                    "超微", "台積電", "自駕", "生成式"]


def count(kws_map):
    per = {g: 0 for g in kws_map}
    for r in recent:
        t = r["title"]
        for g, kws in kws_map.items():
            if any(k in t for k in kws):
                per[g] += 1
    return per


c = count(current)
e = count(expanded)
print("11/11-11/13 共", len(recent), "篇")
print("議題        現有   擴充後   增加")
for g in current:
    print(f"{g:<10} {c[g]:>5} {e[g]:>7} {e[g]-c[g]:>+6}")
print(f"{'合計':<10} {sum(c.values()):>5} {sum(e.values()):>7} "
      f"{sum(e.values())-sum(c.values()):>+6}")
