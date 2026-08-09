# InstagramScrapper

Download image files from a Bright Data / Bright View Instagram CSV export.

## Requirements

- Python 3.10+

## Usage

From the repository directory:

```bash
python /home/runner/work/InstagramScrapper/InstagramScrapper/scraper.py /absolute/path/to/your.csv
```

This writes downloaded files into a `downloads/` folder by default.

### Choose an output directory

```bash
python /home/runner/work/InstagramScrapper/InstagramScrapper/scraper.py /absolute/path/to/your.csv --output /absolute/path/to/output
```

### Limit scanning to known URL columns

```bash
python /home/runner/work/InstagramScrapper/InstagramScrapper/scraper.py /absolute/path/to/your.csv --url-columns image_url display_url
```

## Notes

- The CSV must include a header row.
- The script scans every cell for `http` or `https` links unless `--url-columns` is provided.
- Only direct image URLs are downloaded. Non-image links are skipped.
