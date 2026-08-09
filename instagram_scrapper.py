#!/usr/bin/env python3
"""
Bright Data snapshot photo bulk downloader
"""

import csv
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
CSV_FILE = "snapshot.csv"          # ← change to your downloaded CSV name
OUTPUT_DIR = "downloaded_photos"   # folder where photos will be saved
MAX_WORKERS = 12                   # parallel downloads (increase if you have good internet)
TIMEOUT = 30
# ====================================

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".avif"}
URL_REGEX = re.compile(
    r"https?://[^\s,\"'<>]+?\.(?:jpg|jpeg|png|webp|gif|bmp|tiff|avif)(?:\?[^\s,\"'<>]*)?",
    re.IGNORECASE,
)


def create_session():
    session = requests.Session()
    retries = Retry(total=4, backoff_factor=0.8, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
    )
    return session


def is_image_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in IMAGE_EXTENSIONS) or bool(URL_REGEX.search(url))


def extract_urls_from_csv(csv_path: str) -> list[str]:
    urls = set()
    with open(csv_path, "r", encoding="utf-8", errors="replace") as file:
        sample = file.read(4096)
        file.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel

        reader = csv.reader(file, dialect)
        for row in reader:
            for cell in row:
                if not cell:
                    continue
                found = URL_REGEX.findall(cell)
                for url in found:
                    urls.add(url.rstrip(".,;)\""))
                stripped_cell = cell.strip()
                if is_image_url(stripped_cell):
                    urls.add(stripped_cell)
    return sorted(urls)


def safe_filename(url: str, index: int) -> str:
    parsed = urlparse(url)
    name = os.path.basename(parsed.path)
    if not name or "." not in name:
        ext = ".jpg"
        for image_extension in IMAGE_EXTENSIONS:
            if image_extension in url.lower():
                ext = image_extension
                break
        name = f"photo_{index:05d}{ext}"
    return re.sub(r"[^\w\-_\.]", "_", name)


def download_one(session, url: str, filepath: Path) -> tuple[str, bool, str]:
    try:
        if filepath.exists() and filepath.stat().st_size > 1000:
            return url, True, "already exists"
        response = session.get(url, timeout=TIMEOUT, stream=True)
        response.raise_for_status()
        with open(filepath, "wb") as file:
            for chunk in response.iter_content(8192):
                file.write(chunk)
        return url, True, "ok"
    except Exception as error:
        return url, False, str(error)


def main():
    if not Path(CSV_FILE).exists():
        print(f"❌ CSV file not found: {CSV_FILE}")
        print("Download the snapshot CSV first and put it in the same folder as this script.")
        sys.exit(1)

    print(f"📂 Reading {CSV_FILE} ...")
    urls = extract_urls_from_csv(CSV_FILE)
    print(f"🔍 Found {len(urls)} unique image URLs")

    if not urls:
        print("No image URLs found. The CSV might use different column names or formats.")
        print("Open the CSV and tell me what the image columns look like — I can adjust the script.")
        sys.exit(0)

    output_directory = Path(OUTPUT_DIR)
    output_directory.mkdir(exist_ok=True)

    session = create_session()
    success = 0
    failed = 0

    print(f"⬇️  Downloading into '{OUTPUT_DIR}/' with {MAX_WORKERS} threads...\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for index, url in enumerate(urls, 1):
            filename = safe_filename(url, index)
            filepath = output_directory / filename
            counter = 1
            while filepath.exists():
                stem = Path(filename).stem
                suffix = Path(filename).suffix
                filepath = output_directory / f"{stem}_{counter}{suffix}"
                counter += 1
            futures[executor.submit(download_one, session, url, filepath)] = url

        for future in as_completed(futures):
            url, ok, message = future.result()
            if ok:
                success += 1
                print(f"✅ {success}/{len(urls)}  {url[:80]}...")
            else:
                failed += 1
                print(f"❌ {url[:80]}... → {message}")

    print("\n" + "=" * 50)
    print(f"Done!  {success} downloaded,  {failed} failed")
    print(f"Photos are in:  {output_directory.resolve()}")


if __name__ == "__main__":
    main()
