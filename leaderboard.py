import requests
import json
import os

# --- CONFIGURATION ---
# I have put the keys DIRECTLY here so it works on your computer instantly.
APIFY_TOKEN = "apify_api_tqeJhX9gybOZJbgP52aoXHbmIXXdgE0R6k18"
APIFY_ACTOR_ID = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"

JSONBIN_API_KEY = "$2a$10$9Kj3Z3DThKDQyjpuEnmVLeByQLw3nSaX7.VQI7jrOMabS/PDbPKPq"
JSONBIN_BIN_ID = "697ace2cd0ea881f408f200e"

# --- SCORING SYSTEM ---
POINTS_MAIN_TWEET = 10  
POINTS_REPLY = 1        

VAL_LIKE = 1
VAL_REPLY = 1
VAL_REPOST = 1

CAP_LIKES = 5
CAP_REPLIES = 5
CAP_REPOSTS = 5

RESET_LEADERBOARD = False 

def run_leaderboard_update():
    print("--- STARTING UPDATE (ACCUMULATION MODE) ---")
    
    # 1. LOAD EXISTING DATA
    print("1. Loading existing leaderboard...")
    headers = { 'X-Master-Key': JSONBIN_API_KEY }
    bin_url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    
    try:
        req = requests.get(bin_url, headers=headers)
        current_data = req.json().get('record', {})
    except Exception as e:
        print(f"   Warning: Could not load JSONBin ({e}). Starting fresh.")
        current_data = {}

    if RESET_LEADERBOARD or not current_data:
        print("   ⚠ STARTING FRESH (Reset or Empty)")
        user_database = {} 
        processed_ids = [] 
    else:
        if isinstance(current_data, list):
             user_database = {u['handle']: u for u in current_data}
             processed_ids = []
        else:
             user_database = {u['handle']: u for u in current_data.get('leaderboard', [])}
             processed_ids = current_data.get('processed_ids', [])
            
    print(f"   Loaded {len(user_database)} users and {len(processed_ids)} processed tweets.")

    # 2. GET NEW TWEETS
    print(f"2. Fetching NEW tweets from Apify (Actor: {APIFY_ACTOR_ID})...")
    
    # FIX: We use the manual token variable here
    run_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs/last?token={APIFY_TOKEN}&status=SUCCEEDED"
    run_req = requests.get(run_url)
    
    if run_req.status_code != 200:
        print(f"❌ Error finding actor run: {run_req.text}")
        return

    try:
        dataset_id = run_req.json()['data']['defaultDatasetId']
    except:
        print("❌ Error: No dataset found in last run.")
        return

    data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
    new_tweets = requests.get(data_url).json()

    if not isinstance(new_tweets, list):
        print("❌ Error: Apify returned invalid data.")
        return

    print(f"   Fetched {len(new_tweets)} tweets from latest run.")

    # 3. CALCULATE POINTS
    print("3. Merging points...")
    new_points_added = 0
    
    for tweet in new_tweets:
        t_id = tweet.get('id_str', tweet.get('id'))
        if not t_id: continue 
        
        if t_id in processed_ids:
            continue 

        user_info = tweet.get('author', tweet.get('user', {}))
        handle = user_info.get('userName', user_info.get('screen_name', 'unknown'))
        name = user_info.get('name', handle)
        avatar = user_info.get('profilePicture', user_info.get('profile_image_url_https', ''))

        if handle == 'unknown': continue
        if handle.lower() == 'gbackcoin': continue 

        if not handle.startswith('@'): handle = f"@{handle}"

        if handle not in user_database:
            user_database[handle] = { "name": name, "handle": handle, "avatar": avatar, "score": 0 }

        # Reply Logic
        is_reply = tweet.get('isReply', False) or tweet.get('in_reply_to_status_id') is not None
        base_points = POINTS_REPLY if is_reply else POINTS_MAIN_TWEET

        # Engagement Logic
        raw_likes = tweet.get('likeCount', tweet.get('favorite_count', 0))
        raw_retweets = tweet.get('retweetCount', tweet.get('retweet_count', 0))
        raw_replies = tweet.get('replyCount', tweet.get('reply_count', 0))

        engagement_points = (min(raw_likes, CAP_LIKES) * VAL_LIKE) + \
                            (min(raw_retweets, CAP_REPOSTS) * VAL_REPOST) + \
                            (min(raw_replies, CAP_REPLIES) * VAL_REPLY)

        total_tweet_points = base_points + engagement_points

        user_database[handle]['score'] += total_tweet_points
        processed_ids.append(t_id)
        new_points_added += total_tweet_points

    processed_ids = processed_ids[-5000:]

    print(f"   Processed complete. Added total of {new_points_added} points.")

    # 4. RANK & SAVE
    print("4. Saving updated leaderboard...")
    
    user_list = list(user_database.values())
    sorted_users = sorted(user_list, key=lambda x: x['score'], reverse=True)

    for i, user in enumerate(sorted_users):
        user['rank'] = i + 1

    users_to_save = sorted_users[:100] 

    final_payload = {
        "leaderboard": users_to_save,
        "processed_ids": processed_ids
    }

    req = requests.put(
        bin_url,
        json=final_payload,
        headers={'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}
    )

    if req.status_code == 200:
        print("✅ SUCCESS! Leaderboard updated.")
        print("   Top 5 Leaders:")
        for u in users_to_save[:5]:
            print(f"   #{u['rank']} {u['handle']} - {u['score']} pts")
    else:
        print(f"❌ Error uploading: {req.text}")

if __name__ == "__main__":
    run_leaderboard_update()
