import os
import time
import requests
from duckduckgo_search import DDGS
from datetime import datetime

# --- 1. 設定監控關鍵字 (自動組合地區+服務) ---
LOCATIONS = ["中壢", "桃園", "平鎮"]
SERVICES = ["接睫毛", "做臉", "除毛", "清粉刺", "皮膚管理"]

# 自動產生搜尋組合，例如 "中壢接睫毛 site:threads.net"
KEYWORDS = []
for loc in LOCATIONS:
    for serv in SERVICES:
        # site:threads.net 代表只搜尋 Threads 平台的內容
        # timelimit="d" 代表只找一天內的 (稍後程式參數設定)
        KEYWORDS.append(f"{loc}{serv} site:threads.net")

# 額外加上一些口語化的搜尋 (高意圖)
KEYWORDS.extend([
    "中壢推薦做臉 site:threads.net",
    "桃園清粉刺推薦 site:threads.net",
    "想做皮膚管理 site:threads.net"
])

# --- 2. 設定排除關鍵字 (過濾廣告/同行) ---
BLOCK_WORDS = [
    "推廣", "廣告", "教學", "課程", "徵才", "徵手模", 
    "工作室出租", "美睫教學", "紋繡教學"
]

# --- 3. Telegram 設定 (從 GitHub Secrets 讀取) ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("❌ 錯誤：找不到 TG 設定，請檢查 GitHub Secrets")
        return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"TG 發送失敗: {e}")

def run_hawk_radar():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 霍克雷達 (美業版) 啟動...")
    print(f"監控關鍵字數量: {len(KEYWORDS)} 組")
    
    found_count = 0
    # 這裡我們用一個簡單的集合來避免同一次執行抓到重複的連結
    seen_links = set()

    with DDGS() as ddgs:
        for query in KEYWORDS:
            print(f"🔍 正在掃描: {query} ...")
            try:
                # region="tw-tzh" (台灣), timelimit="d" (過去一天)
                results = ddgs.text(query, region="tw-tzh", timelimit="d", max_results=5)
                
                if results:
                    for r in results:
                        link = r.get('href', '')
                        title = r.get('title', '')
                        body = r.get('body', '')
                        
                        # 檢查是否重複
                        if link in seen_links:
                            continue
                        seen_links.add(link)

                        # 檢查排除字
                        full_text = f"{title} {body}"
                        if any(bad in full_text for bad in BLOCK_WORDS):
                            continue 

                        # --- 找到有效潛在客戶，發送通知 ---
                        found_count += 1
                        keyword_clean = query.replace(" site:threads.net", "")
                        
                        msg = (
                            f"🎯 <b>Miniko 雷達響了！</b>\n"
                            f"關鍵字：#{keyword_clean}\n"
                            f"------------------\n"
                            f"{body[:100]}...\n"
                            f"------------------\n"
                            f"🔗 <a href='{link}'>點擊去 Threads 留言</a>"
                        )
                        send_telegram(msg)
                        time.sleep(1) # 避免 TG 發太快

                time.sleep(2) # 搜尋引擎禮貌性延遲
                
            except Exception as e:
                print(f"搜尋錯誤 ({query}): {e}")
                time.sleep(5) # 發生錯誤多休息一下

    print(f"✅ 掃描完成，共發現 {found_count} 個潛在機會。")

if __name__ == "__main__":
    run_hawk_radar()
