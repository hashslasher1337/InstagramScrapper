#!/usr/bin/env python3

import argparse
import csv
import mimetypes
import re
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


URL_PATTERN = re.compile(r"https?://[^\s,;\"'<>]+")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; InstagramScrapper/1.0)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download image URLs from a CSV export into a local folder."
    )
    parser.add_argument("csv_file", help="Path to the CSV file to read")
    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="Directory to write downloaded files to (default: downloads)",
    )
    parser.add_argument(
        "--url-columns",
        nargs="+",
        help="Only scan these CSV column names for URLs",
    )
    parser.add_argument(
        "--delimiter",
        help="CSV delimiter override. By default the script attempts to detect it.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-request timeout in seconds (default: 30)",
    )
    return parser.parse_args()


def detect_delimiter(csv_path: Path) -> str:
    sample = csv_path.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
    try:
        return csv.Sniffer().sniff(sample).delimiter
    except csv.Error:
        return ","


def iter_urls(row: dict[str, str], url_columns: set[str] | None) -> Iterable[str]:
    items = row.items() if not url_columns else (
        (key, value) for key, value in row.items() if key in url_columns
    )

    for _, value in items:
        if not value:
            continue
        for match in URL_PATTERN.findall(value):
            yield match.rstrip(".,);]")


def extension_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    extension = mimetypes.guess_extension(content_type.split(";")[0].strip())
    return extension or ""


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or "download"


def build_filename(url: str, content_type: str | None, row_number: int, index: int) -> str:
    path_name = Path(urlparse(url).path).name
    if path_name:
        filename = sanitize_filename(path_name)
    else:
        filename = f"row_{row_number:05d}_{index:03d}"

    suffix = Path(filename).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        inferred = extension_from_content_type(content_type)
        if inferred in IMAGE_EXTENSIONS:
            filename = f"{Path(filename).stem or filename}{inferred}"

    return filename


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def download_file(url: str, destination: Path, timeout: int) -> bool:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return False

        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            handle.write(response.read())
    return True


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_file).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not csv_path.is_file():
        print(f"CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    delimiter = args.delimiter or detect_delimiter(csv_path)
    requested_columns = set(args.url_columns) if args.url_columns else None

    downloaded = 0
    skipped = 0
    errors = 0
    seen_urls: set[str] = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            print("The CSV file is missing a header row.", file=sys.stderr)
            return 1

        if requested_columns:
            missing = sorted(requested_columns.difference(reader.fieldnames))
            if missing:
                print(
                    f"Unknown column(s): {', '.join(missing)}. "
                    f"Available columns: {', '.join(reader.fieldnames)}",
                    file=sys.stderr,
                )
                return 1

        for row_number, row in enumerate(reader, start=2):
            for index, url in enumerate(iter_urls(row, requested_columns), start=1):
                if url in seen_urls:
                    skipped += 1
                    continue

                seen_urls.add(url)
                try:
                    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
                    with urlopen(request, timeout=args.timeout) as response:
                        content_type = response.headers.get("Content-Type", "")
                        if not content_type.startswith("image/"):
                            skipped += 1
                            continue

                        filename = build_filename(url, content_type, row_number, index)
                        destination = ensure_unique_path(output_dir / filename)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with destination.open("wb") as output_handle:
                            output_handle.write(response.read())
                        downloaded += 1
                        print(f"Downloaded {url} -> {destination}")
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    print(f"Failed to download {url}: {exc}", file=sys.stderr)

    print(
        f"Done. Downloaded: {downloaded}, skipped: {skipped}, errors: {errors}, "
        f"output: {output_dir}"
    )
    return 0 if downloaded or not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
