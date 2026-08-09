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
CSV_FILE = "snapshot.csv"
OUTPUT_DIR = "downloaded_photos"
MAX_WORKERS = 8
TIMEOUT = 30
# ====================================

PHOTOS_COL = "photos"
URL_COL = "url"
USER_COL = "user_posted"


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def extract_urls(raw: str) -> list[str]:
    """Parse a pipe- or newline-separated list of photo URLs from a CSV cell."""
    if not raw:
        return []
    urls = [u.strip() for u in re.split(r"[\|\n]+", raw) if u.strip()]
    return [u for u in urls if u.startswith("http")]


def download_file(session: requests.Session, url: str, dest: Path) -> None:
    if dest.exists():
        return
    response = session.get(url, timeout=TIMEOUT, stream=True)
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    try:
        with open(tmp, "wb") as fh:
            for chunk in response.iter_content(chunk_size=65536):
                fh.write(chunk)
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def derive_extension(url: str, content_type: str = "") -> str:
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"}:
        return ext
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "png" in content_type:
        return ".png"
    if "gif" in content_type:
        return ".gif"
    if "webp" in content_type:
        return ".webp"
    return ".jpg"


def process_row(
    session: requests.Session,
    row: dict,
    output_dir: Path,
    row_index: int,
) -> tuple[int, int]:
    username = sanitize_filename(row.get(USER_COL, "") or f"row{row_index}")
    post_url = row.get(URL_COL, "")
    post_id = sanitize_filename(Path(urlparse(post_url).path).name) or str(row_index)

    photos_raw = row.get(PHOTOS_COL, "")
    photo_urls = extract_urls(photos_raw)

    if not photo_urls:
        return 0, 0

    success = 0
    fail = 0
    for idx, photo_url in enumerate(photo_urls, start=1):
        ext = derive_extension(photo_url)
        filename = f"{username}_{post_id}_{idx}{ext}"
        dest = output_dir / username / filename
        try:
            download_file(session, photo_url, dest)
            success += 1
        except Exception as exc:
            print(f"  [WARN] Failed {photo_url}: {exc}", file=sys.stderr)
            fail += 1

    return success, fail


def main() -> None:
    csv_path = Path(CSV_FILE)
    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if not rows:
        print("[INFO] No rows found in CSV.")
        return

    print(f"[INFO] Processing {len(rows)} rows from {csv_path} ...")

    session = build_session()
    total_ok = 0
    total_fail = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(process_row, session, row, output_dir, idx): idx
            for idx, row in enumerate(rows, start=1)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                ok, fail = future.result()
                total_ok += ok
                total_fail += fail
                if ok or fail:
                    print(f"  Row {idx}: {ok} downloaded, {fail} failed")
            except Exception as exc:
                print(f"  Row {idx}: unexpected error – {exc}", file=sys.stderr)
                total_fail += 1

    print(
        f"\n[DONE] {total_ok} photos downloaded, {total_fail} failures. "
        f"Output: {output_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
