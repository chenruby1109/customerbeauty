import os
import time
import requests
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from github import Github
from datetime import datetime

# --- 1. 設定極速監控關鍵字 ---
# 為了避免被 Google 封鎖，我們精簡關鍵字，只查最核心的
# 格式：(關鍵字, 顯示名稱)
TARGETS = [
    ("中壢美甲 site:threads.net", "中壢美甲"),
    ("中壢接睫毛 site:threads.net", "中壢睫毛"),
    ("中壢做臉 site:threads.net", "中壢做臉"),
    ("中壢除毛 site:threads.net", "中壢除毛"),
    ("桃園皮膚管理 site:threads.net", "桃園皮膚")
]

# --- 2. 排除字眼 ---
BLOCK_WORDS = ["廣告", "推廣", "教學", "課程", "徵手模", "分享"]

# --- 3. 環境變數 ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME")

# --- 4. 初始化 Selenium (偽裝瀏覽器) ---
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 無頭模式 (不顯示視窗)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 使用一般使用者的 User-Agent，避免被認成機器人
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")
    chrome_options.add_argument("--lang=zh-TW") # 設定中文環境
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# --- 5. 功能函式 ---
def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True})

def check_if_seen(repo, link_id):
    if not repo: return False
    issues = repo.get_issues(state='all', labels=['lead'])
    for issue in issues:
        if link_id in issue.title: return True
    return False

def mark_as_seen(repo, link_id, content):
    if not repo: return
    try:
        issue = repo.create_issue(title=f"[已通知] {link_id}", body=f"{content}\n\n{link_id}", labels=['lead'])
        issue.edit(state='closed')
    except: pass

def google_search_past_hour(driver, query):
    # &tbs=qdr:h 代表 "Query Date Range: Hour" (過去一小時)
    # &hl=zh-TW 強制中文介面
    url = f"https://www.google.com/search?q={query}&tbs=qdr:h&hl=zh-TW"
    print(f"   >>> 前往 Google (過去1小時): {url}")
    
    driver.get(url)
    time.sleep(random.uniform(2, 5)) # 隨機等待，像真人一樣

    results = []
    # Google 的搜尋結果通常在 class="g" 的 div 裡
    elements = driver.find_elements(By.CSS_SELECTOR, 'div.g')
    
    if not elements:
        # 如果找不到 class="g"，可能是因為 Google 改版或出現驗證碼
        print("   ⚠️ 找不到結果或遇到驗證碼")
        # 截圖除錯 (可選)
        # driver.save_screenshot("debug.png")
        return []

    for el in elements:
        try:
            # 抓標題 (h3)
            title_el = el.find_element(By.TAG_NAME, 'h3')
            title = title_el.text
            
            # 抓連結 (a tag)
            link_el = el.find_element(By.TAG_NAME, 'a')
            link = link_el.get_attribute('href')
            
            # 抓摘要 (通常在 div 裡)
            content = el.text.replace(title, "")
            
            if "threads.net" in link:
                results.append({"title": title, "link": link, "content": content})
        except:
            continue
            
    return results

# --- 主程式 ---
def run_hawk_radar():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 霍克雷達 (Google 1小時極速版) 啟動...")
    
    # 準備 GitHub 資料庫
    repo = None
    if GITHUB_TOKEN and REPO_NAME:
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(REPO_NAME)
        except: pass

    driver = setup_driver()
    
    try:
        for query, label in TARGETS:
            print(f"🔍 正在搜尋: {label} ...")
            leads = google_search_past_hour(driver, query)
            
            print(f"   -> 找到 {len(leads)} 筆資料 (含重複)")
            
            for lead in leads:
                # 排除過濾
                if any(bad in lead['content'] for bad in BLOCK_WORDS): continue
                if repo and check_if_seen(repo, lead['link']): continue
                
                # 發送通知
                print(f"✅ 新發現: {lead['title']}")
                msg = (
                    f"🔥 <b>{label} 急客出現！</b> (1小時內)\n"
                    f"{lead['title']}\n"
                    f"------------------\n"
                    f"🔗 <a href='{lead['link']}'>點擊搶單</a>"
                )
                send_telegram(msg)
                mark_as_seen(repo, lead['link'], lead['content'])
            
            # 每次搜尋完休息久一點，避免 Google 生氣
            time.sleep(random.uniform(5, 10))
            
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
    finally:
        driver.quit()
        print("程式執行結束")

if __name__ == "__main__":
    run_hawk_radar()
