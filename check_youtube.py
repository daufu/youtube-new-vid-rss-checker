import feedparser
import json
from datetime import datetime, time, timedelta
import pytz
import os

# --- 設定 ---
CHANNELS_FILE = 'channels.json'
STATE_FILE = 'last_check.json'
OUTPUT_FILE = 'status.json'
HK_TZ = pytz.timezone('Asia/Hong_Kong')

def get_today_start_time():
    """以香港時間中午12點為一天的開始"""
    now_hk = datetime.now(HK_TZ)
    noon_time = time(12, 0)
    
    if now_hk.time() >= noon_time:
        start_of_day = now_hk.replace(hour=12, minute=0, second=0, microsecond=0)
    else:
        yesterday = now_hk - timedelta(days=1)
        start_of_day = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)
        
    return start_of_day

def load_json(file_path, default_data):
    """讀取 JSON 檔案，如果不存在則返回預設值"""
    if not os.path.exists(file_path):
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_data

def main():
    channels = load_json(CHANNELS_FILE, [])
    state = load_json(STATE_FILE, {"videos": {}})
    
    today_start_time_hk = get_today_start_time()
    today_start_time_utc = today_start_time_hk.astimezone(pytz.utc)

    output_status = []
    new_state_videos = state.get("videos", {})

    for channel in channels:
        channel_id = channel['channel_id']
        channel_name = channel['name']
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        
        print(f"正在檢查頻道: {channel_name}")
        
        feed = feedparser.parse(rss_url)
        if feed.bozo:
            print(f"  錯誤: 無法解析 {channel_name} 的 RSS feed。")
            continue

        new_video_count = 0
        
        last_video_published_str = state.get("videos", {}).get(channel_id)
        last_video_published_utc = datetime.fromisoformat(last_video_published_str).replace(tzinfo=pytz.utc) if last_video_published_str else datetime.min.replace(tzinfo=pytz.utc)

        latest_entry_time_utc = None

        for entry in feed.entries:
            published_time = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
            
            if latest_entry_time_utc is None or published_time > latest_entry_time_utc:
                latest_entry_time_utc = published_time

            if published_time > today_start_time_utc and published_time > last_video_published_utc:
                new_video_count += 1
        
        print(f"  發現 {new_video_count} 個新影片。")

        output_status.append({
            "channel_name": channel_name,
            "retrieved_time": datetime.now(pytz.utc).isoformat(),
            "new_video_count": new_video_count
        })

        if latest_entry_time_utc:
            new_state_videos[channel_id] = latest_entry_time_utc.isoformat()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_status, f, indent=2, ensure_ascii=False)

    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"videos": new_state_videos}, f, indent=2)

    print("檢查完成。")

if __name__ == "__main__":
    main()
