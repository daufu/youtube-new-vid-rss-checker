import feedparser
import json
import datetime
import time
import pytz
import os
from urllib.error import URLError

# --- 專業的設定區 ---
CONFIG = {
    "channels_file": 'channels.json',
    "state_file": 'last_check.json',
    "output_file": 'status.json',
    "timezone": 'Asia/Hong_Kong',
    "request_delay_seconds": 2
}

def get_current_checking_window_utc(tz_str):
    """獲取香港時間當天午夜0點到午夜前的時間範圍，並轉換為UTC"""
    target_tz = pytz.timezone(tz_str)
    now_tz = datetime.datetime.now(target_tz)
    
    start_of_window = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_window = now_tz.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    start_utc = start_of_window.astimezone(pytz.utc)
    end_utc = end_of_window.astimezone(pytz.utc)
    
    return start_utc, end_utc

def load_json(file_path, default_data):
    if not os.path.exists(file_path):
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_data

# 1. 簡化函式，不再需要 last_seen_time_utc 參數
def check_channel(channel, start_time_utc, end_time_utc):
    """
    檢查單一頻道。
    返回: (在時間窗口內的新影片數, Feed中最新的影片時間)
    """
    channel_id = channel['channel_id']
    channel_name = channel['name']
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    print(f"正在檢查頻道: {channel_name}")
    
    try:
        feed = feedparser.parse(rss_url)
        if feed.bozo:
            raise feed.bozo_exception

        new_video_count = 0
        latest_entry_time_utc = None

        for entry in feed.entries:
            published_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
            
            # 記錄 Feed 中最新的影片時間，用於更新 last_check.json
            if latest_entry_time_utc is None or published_time > latest_entry_time_utc:
                latest_entry_time_utc = published_time

            # 2. 這是新的、簡化的核心判斷邏輯
            if start_time_utc <= published_time <= end_time_utc:
                new_video_count += 1
        
        print(f"  -> 成功: 在時間範圍內發現 {new_video_count} 個影片。")
        return new_video_count, latest_entry_time_utc

    except (URLError, Exception) as e:
        print(f"  -> 錯誤: 處理頻道 {channel_name} 時發生問題。詳細資訊: {e}")
        return 0, None

def main():
    """主執行函式"""
    channels = load_json(CONFIG["channels_file"], [])
    
    start_time_utc, end_time_utc = get_current_checking_window_utc(CONFIG["timezone"])
    
    print(f"檢查時間範圍 (UTC): {start_time_utc.strftime('%Y-%m-%d %H:%M:%S')} 至 {end_time_utc.strftime('%Y-%m-%d %H:%M:%S')}")

    output_status = []
    # 3. 準備一個字典來收集最新的影片時間，以便最後寫入 last_check.json
    new_state_videos = {}

    for i, channel in enumerate(channels):
        channel_id = channel['channel_id']
        
        # 1. 呼叫簡化後的函式
        new_video_count, latest_entry_time_utc = check_channel(channel, start_time_utc, end_time_utc)
        
        output_status.append({
            "channel_name": channel['name'],
            "retrieved_time": datetime.datetime.now(pytz.utc).isoformat(),
            "new_video_count": new_video_count
        })
        
        # 3. 收集每個頻道的最新影片時間
        if latest_entry_time_utc:
            new_state_videos[channel_id] = latest_entry_time_utc.isoformat()
        
        if i < len(channels) - 1:
            delay = CONFIG["request_delay_seconds"]
            print(f"  ...延遲 {delay} 秒...")
            time.sleep(delay)

    # 寫入 status.json (計數結果)
    with open(CONFIG["output_file"], 'w', encoding='utf-8') as f:
        json.dump(output_status, f, indent=2, ensure_ascii=False)

    # 寫入 last_check.json (純粹的記錄)
    final_state = {"videos": new_state_videos}
    with open(CONFIG["state_file"], 'w', encoding='utf-8') as f:
        json.dump(final_state, f, indent=2)

    print("所有頻道檢查完成。")

if __name__ == "__main__":
    main()
