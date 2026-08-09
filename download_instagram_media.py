#!/usr/bin/env python3
"""
Download videos + thumbnails from Bright Data Instagram reel snapshot
"""

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============== CONFIG ==============
JSON_FILE = "/home/workdir/attachments/sd_msm396bz1ii5y9atzx 2.json"
OUTPUT_DIR = "/home/workdir/artifacts/downloaded_media"
MAX_WORKERS = 8
TIMEOUT = 60
DOWNLOAD_VIDEOS = True
DOWNLOAD_THUMBNAILS = True
DOWNLOAD_AUDIO = False          # set True if you also want the separate audio tracks
DOWNLOAD_PROFILE_PICS = False   # set True if you want the account profile image
# ====================================

def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session

def clean_filename(text: str) -> str:
    return re.sub(r"[^\w\-_\.]", "_", text)[:120]

def download_one(session, url: str, filepath: Path) -> tuple[str, bool, str]:
    try:
        if filepath.exists() and filepath.stat().st_size > 8000:
            return str(filepath.name), True, "already exists"

        with session.get(url, timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
        return str(filepath.name), True, "ok"
    except Exception as e:
        return str(filepath.name), False, str(e)[:120]

def main():
    if not Path(JSON_FILE).exists():
        print(f"❌ JSON not found: {JSON_FILE}")
        sys.exit(1)

    print(f"📂 Loading {JSON_FILE} ...")
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📊 Found {len(data)} posts\n")

    out = Path(OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)

    tasks = []  # (url, filepath)

    for post in data:
        shortcode = post.get("shortcode") or post.get("post_id") or "unknown"
        user = post.get("user_posted") or "unknown"
        base = clean_filename(f"{user}_{shortcode}")

        if DOWNLOAD_VIDEOS and post.get("video_url"):
            tasks.append((post["video_url"], out / f"{base}.mp4"))

        if DOWNLOAD_THUMBNAILS and post.get("thumbnail"):
            tasks.append((post["thumbnail"], out / f"{base}_thumb.jpg"))

        if DOWNLOAD_AUDIO and post.get("audio_url"):
            tasks.append((post["audio_url"], out / f"{base}_audio.mp4"))

        if DOWNLOAD_PROFILE_PICS and post.get("profile_image_link"):
            # only once per unique profile
            tasks.append((post["profile_image_link"], out / f"{user}_profile.jpg"))

    # Deduplicate by filepath
    seen = set()
    unique_tasks = []
    for url, path in tasks:
        if path not in seen:
            seen.add(path)
            unique_tasks.append((url, path))

    print(f"⬇️  Will download {len(unique_tasks)} files with {MAX_WORKERS} threads\n")

    session = create_session()
    success = failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_one, session, url, path): (url, path)
            for url, path in unique_tasks
        }

        for i, future in enumerate(as_completed(futures), 1):
            name, ok, msg = future.result()
            if ok:
                success += 1
                status = "✅"
            else:
                failed += 1
                status = "❌"
            print(f"{status} [{i}/{len(unique_tasks)}] {name}  →  {msg}")

    print("\n" + "=" * 55)
    print(f"Finished: {success} downloaded, {failed} failed")
    print(f"Folder:   {out.resolve()}")
    print("=" * 55)

if __name__ == "__main__":
    main()
