import requests
import pandas as pd
from tqdm import tqdm
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
API_KEY = "1436d2df92f1242d48e962b7406294b1"  # Replace with your key if needed
BASE_URL = "https://api.themoviedb.org/3"

MAX_PAGES = 500       # ~ 10,000 movies
SLEEP_TIME = 0.15      # Buffer to avoid rate limits

movies_data = []
credits_data = []

# --- SESSION SETUP ---
session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

print("⬇ Downloading RAW TMDB data...")

for page in tqdm(range(1, MAX_PAGES + 1), desc="Total Progress"):
    try:
        # 1. Get Popular List
        pop_response = session.get(
            f"{BASE_URL}/movie/popular",
            params={"api_key": API_KEY, "page": page},
            timeout=10
        )
        pop_response.raise_for_status()
        results = pop_response.json().get("results", [])

        for movie in results:
            movie_id = movie["id"]

            try:
                # 2. OPTIMIZATION: Get Details + Credits + Keywords in ONE call
                # This is 3x faster than your original approach
                details = session.get(
                    f"{BASE_URL}/movie/{movie_id}",
                    params={
                        "api_key": API_KEY,
                        "append_to_response": "credits,keywords" 
                    },
                    timeout=10
                ).json()

                # Extract Data
                movies_data.append({
                    "movie_id": movie_id,
                    "title": details.get("title"),
                    "release_date": details.get("release_date"),
                    "genres": [g['name'] for g in details.get("genres", [])],
                    "overview": details.get("overview"),
                    "popularity": details.get("popularity"),
                    "vote_average": details.get("vote_average"),
                    "vote_count": details.get("vote_count"),
                    "keywords": [k['name'] for k in details.get("keywords", {}).get("keywords", [])]
                })

                credits = details.get("credits", {})
                credits_data.append({
                    "movie_id": movie_id,
                    "cast": credits.get("cast", [])[:10], # Saving top 10 cast members
                    "crew": credits.get("crew", [])
                })

            except Exception as e:
                # If a specific movie fails, just print and move on
                # print(f"⚠ Skipped movie {movie_id}: {e}")
                pass
            
            # Sleep to respect rate limits
            time.sleep(SLEEP_TIME)

    except Exception as e:
        print(f"❌ Page {page} failed: {e}")

# --- SAVE DATA ONCE AT THE END ---
print("💾 Saving files...")
pd.DataFrame(movies_data).to_csv("tmdb_movies_raw.csv", index=False)
pd.DataFrame(credits_data).to_csv("tmdb_credits_raw.csv", index=False)

print("✅ Download complete")
print(f"Total Movies Collected: {len(movies_data)}")