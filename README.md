# InstagramScrapper

Download photos from a Bright Data snapshot CSV in bulk.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

1. Put your exported Bright Data CSV next to `instagram_scrapper.py`.
2. Rename it to `snapshot.csv`, or update the `CSV_FILE` constant in the script.
3. Run:

```bash
python instagram_scrapper.py
```

Downloaded files are saved to `downloaded_photos/`.
