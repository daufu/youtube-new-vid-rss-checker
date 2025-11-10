import feedparser
import json
import datetime # 1. 只引入整個 datetime 模組
import time # 2. 保持引入 time 模組
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

def get_today_start_time(tz_str):
    """以指定時區的中午12點為一天的開始"""
    target_tz = pytz.timezone(tz_str)
    now_tz = datetime.datetime.now(target_tz)
    # 3. 使用 datetime.time 來明確指定
    noon_time = datetime.time(12, 0)
    
    if now_tz.time() >= noon_time:
        start_of_day = now_tz.replace(hour=12, minute=0, second=0, microsecond=0)
    else:
        yesterday = now_tz - datetime.timedelta(days=1)
        start_of_day = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)
        
    return start_of_day

def load_json(file_path, default_data):
    """讀取 JSON 檔案，如果不存在或格式錯誤則返回預設值"""
    if not os.path.exists(file_path):
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_data

def check_channel(channel, today_start_time_utc, last_video_published_utc):
    """檢查單一頻道，返回新影片數量和最新的影片時間"""
    channel_id = channel['channel_id']
    channel_name = channel['name']
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    print(f"正在檢查頻道: {channel_name} (ID: {channel_id})")
    
    try:
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            raise feed.bozo_exception

        new_video_count = 0
        latest_entry_time_utc = None

        for entry in feed.entries:
            # 3. 使用 datetime.datetime 來明確指定
            published_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
            
            if latest_entry_time_utc is None or published_time > latest_entry_time_utc:
                latest_entry_time_utc = published_time

            if published_time > today_start_time_utc and published_time > last_video_published_utc:
                new_video_count += 1
        
        print(f"  -> 成功: 發現 {new_video_count} 個新影片。")
        return new_video_count, latest_entry_time_utc

    except URLError as e:
        print(f"  -> 錯誤: 網路連線問題或無效的 URL。 {e.reason}")
        return 0, None
    except Exception as e:
        print(f"  -> 錯誤: 無法解析 {channel_name} 的 RSS feed。可能是無效的 Channel ID 或 YouTube 暫時問題。詳細資訊: {e}")
        return 0, None

def main():
    """主執行函式"""
    channels = load_json(CONFIG["channels_file"], [])
    state = load_json(CONFIG["state_file"], {"videos": {}})
    
    today_start_time_hk = get_today_start_time(CONFIG["timezone"])
    today_start_time_utc = today_start_time_hk.astimezone(pytz.utc)

    output_status = []
    new_state_videos = state.get("videos", {})

    for i, channel in enumerate(channels):
        channel_id = channel['channel_id']
        
        last_video_published_str = state.get("videos", {}).get(channel_id)
        # 3. 使用 datetime.datetime 和 datetime.datetime.min
        last_video_published_utc = datetime.datetime.fromisoformat(last_video_published_str).replace(tzinfo=pytz.utc) if last_video_published_str else datetime.datetime.min.replace(tzinfo=pytz.utc)

        new_video_count, latest_entry_time_utc = check_channel(channel, today_start_time_utc, last_video_published_utc)

        output_status.append({
            "channel_name": channel['name'],
            # 3. 使用 datetime.datetime
            "retrieved_time": datetime.datetime.now(pytz.utc).isoformat(),
            "new_video_count": new_video_count
        })

        if latest_entry_time_utc:
            new_state_videos[channel_id] = latest_entry_time_utc.isoformat()
        
        if i < len(channels) - 1:
            delay = CONFIG["request_delay_seconds"]
            print(f"  ...延遲 {delay} 秒，避免請求過於頻繁...")
            # 這裡的 time.sleep() 現在可以正確工作了
            time.sleep(delay)

    with open(CONFIG["output_file"], 'w', encoding='utf-8') as f:
        json.dump(output_status, f, indent=2, ensure_ascii=False)

    with open(CONFIG["state_file"], 'w', encoding='utf-8') as f:
        json.dump({"videos": new_state_videos}, f, indent=2)

    print("所有頻道檢查完成。")

if __name__ == "__main__":
    main()
