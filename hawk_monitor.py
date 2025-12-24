import os
import time
import requests
from duckduckgo_search import DDGS
from github import Github # 引入 GitHub 工具
from datetime import datetime

# --- 1. 設定監控關鍵字 ---
LOCATIONS = ["中壢", "桃園", "平鎮", "八德"]
SERVICES = ["接睫毛", "做臉", "除毛", "清粉刺", "皮膚管理"]

KEYWORDS = []
for loc in LOCATIONS:
    for serv in SERVICES:
        KEYWORDS.append(f"{loc}{serv} site:threads.net")

KEYWORDS.extend([
    "中壢推薦做臉 site:threads.net",
    "桃園清粉刺推薦 site:threads.net",
    "想做皮膚管理 site:threads.net"
])

# --- 2. 設定排除關鍵字 ---
BLOCK_WORDS = [
    "推廣", "廣告", "教學", "課程", "徵才", "徵手模", 
    "工作室出租", "美睫教學", "紋繡教學"
]

# --- 3. 取得環境變數 ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME") # 例如: yourname/miniko-hawk

# --- 4. 功能函式 ---

def check_if_seen(repo, link_id):
    """檢查這個連結是否已經紀錄在 Issue 中"""
    if not repo:
        return False
    # 搜尋標題包含該連結的 Issue (state='all' 代表包含已關閉的)
    issues = repo.get_issues(state='all', labels=['lead'])
    for issue in issues:
        if link_id in issue.title:
            return True
    return False

def mark_as_seen(repo, link_id, content):
    """建立一個 Issue 來記錄這個潛在客戶"""
    if not repo:
        return
    try:
        # 建立一個標記為 'lead' 的 Issue
        issue = repo.create_issue(
            title=f"[已通知] {link_id}",
            body=f"內容摘要：\n{content}\n\n連結：{link_id}",
            labels=['lead']
        )
        # 建立後馬上關閉它，保持列表整潔
        issue.edit(state='closed')
        print(f"📝 已寫入紀錄: {link_id}")
    except Exception as e:
        print(f"寫入紀錄失敗: {e}")

def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
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

# --- 主程式 ---
def run_hawk_radar():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 霍克雷達 (智能去重版) 啟動...")
    
    # 初始化 GitHub 連線 (用於讀寫紀錄)
    repo = None
    if GITHUB_TOKEN and REPO_NAME:
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(REPO_NAME)
            print("✅ 成功連線到 GitHub 資料庫")
        except Exception as e:
            print(f"⚠️ 無法連線 GitHub: {e}")

    found_count = 0
    new_count = 0
    
    with DDGS() as ddgs:
        for query in KEYWORDS:
            print(f"🔍 正在掃描: {query} ...")
            try:
                # 為了避免遺漏，我們稍微抓多一點 (10筆)，然後靠程式過濾重複
                results = ddgs.text(query, region="tw-tzh", timelimit="d", max_results=10)
                
                if results:
                    for r in results:
                        link = r.get('href', '')
                        title = r.get('title', '')
                        body = r.get('body', '')
                        
                        # 1. 基本排除
                        full_text = f"{title} {body}"
                        if any(bad in full_text for bad in BLOCK_WORDS):
                            continue 

                        # 2. 智能去重檢查 (關鍵步驟!)
                        # 用連結當作唯一 ID
                        if repo and check_if_seen(repo, link):
                            print(f"⏭️ 跳過已通知過的: {link}")
                            continue

                        # --- 3. 發現新客戶 ---
                        found_count += 1
                        new_count += 1
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
                        
                        # 4. 寫入筆記本
                        mark_as_seen(repo, link, body)
                        
                        time.sleep(1)

                time.sleep(2)
                
            except Exception as e:
                print(f"搜尋錯誤 ({query}): {e}")
                time.sleep(5)

    print(f"✅ 掃描完成。掃描 {found_count} 筆，其中 {new_count} 筆是新的。")

if __name__ == "__main__":
    run_hawk_radar()
