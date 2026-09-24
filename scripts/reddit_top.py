#!/usr/bin/env python3
"""Ambil metadata post teratas dari sebuah subreddit lewat PRAW (Reddit API resmi).

Kredensial dibaca dari environment variable REDDIT_CLIENT_ID dan REDDIT_CLIENT_SECRET.
Hasil disimpan ke data/<subreddit>_<tanggal>.json. Media hanya diunduh dengan --download
(maksimal 5 file, untuk tes).
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import praw
import requests

from _env import load_env

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = ROOT / "downloads"
USER_AGENT = "meme-research-toolkit/0.1 (riset tren; script PRAW)"
MAX_DOWNLOAD = 5

CREDENTIAL_HELP = """\
Kredensial Reddit API belum diset.

1. Buka https://www.reddit.com/prefs/apps (login dulu).
2. Klik "create another app...", pilih tipe "script".
3. Isi name bebas, redirect uri: http://localhost:8080
4. Setelah dibuat: string pendek di bawah nama app = client_id,
   field "secret" = client_secret.
5. Set environment variable (jangan tulis ke script):
   PowerShell : $env:REDDIT_CLIENT_ID="..."; $env:REDDIT_CLIENT_SECRET="..."
   bash       : export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
   atau simpan di file .env (sudah ada di .gitignore) dan load sebelum menjalankan.
"""


def classify(post):
    """Kembalikan (jenis_media, url_media) untuk sebuah submission."""
    if getattr(post, "is_gallery", False):
        urls = []
        meta = getattr(post, "media_metadata", None) or {}
        for item in (post.gallery_data or {}).get("items", []):
            m = meta.get(item["media_id"], {})
            src = m.get("s", {})
            url = src.get("u") or src.get("gif") or src.get("mp4")
            if url:
                urls.append(url.replace("&amp;", "&"))
        return "galeri", urls
    if post.is_video and post.media and "reddit_video" in post.media:
        return "video", post.media["reddit_video"]["fallback_url"]
    path = urlparse(post.url).path.lower()
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "gambar", post.url
    if post.is_self:
        return "teks", None
    return "link", post.url


def to_record(post):
    kind, media = classify(post)
    return {
        "id": post.id,
        "judul": post.title,
        "skor": post.score,
        "jumlah_komentar": post.num_comments,
        "url_post": f"https://www.reddit.com{post.permalink}",
        "url_media": media,
        "jenis_media": kind,
        "tanggal": dt.datetime.fromtimestamp(post.created_utc, dt.timezone.utc).isoformat(),
        "nsfw": post.over_18,
        "author": str(post.author) if post.author else None,
    }


def download(records):
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    count = 0
    for rec in records:
        urls = rec["url_media"] if isinstance(rec["url_media"], list) else [rec["url_media"]]
        for url in urls:
            if count >= MAX_DOWNLOAD:
                return count
            if not url or rec["jenis_media"] not in ("gambar", "video", "galeri"):
                continue
            ext = Path(urlparse(url).path).suffix or ".bin"
            dest = DOWNLOAD_DIR / f"{rec['id']}_{count}{ext}"
            try:
                r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
                r.raise_for_status()
                dest.write_bytes(r.content)
                print(f"  unduh -> {dest.relative_to(ROOT)}")
                count += 1
            except requests.RequestException as e:
                print(f"  gagal {url}: {e}", file=sys.stderr)
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--subreddit", default="memes")
    ap.add_argument("-n", "--limit", type=int, default=10, help="jumlah post (default 10)")
    ap.add_argument("-t", "--time", default="day", choices=["day", "week"], help="periode top (default day)")
    ap.add_argument("--download", action="store_true", help=f"unduh maksimal {MAX_DOWNLOAD} file media ke downloads/")
    args = ap.parse_args()

    load_env()  # baca .env di root repo kalau ada
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(CREDENTIAL_HELP, file=sys.stderr)
        sys.exit(2)

    reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=USER_AGENT)
    reddit.read_only = True

    posts = reddit.subreddit(args.subreddit).top(time_filter=args.time, limit=args.limit)
    records = [to_record(p) for p in posts]

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"{args.subreddit}_{dt.date.today().isoformat()}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(records)} post r/{args.subreddit} (top {args.time}) -> {out.relative_to(ROOT)}")

    if args.download:
        n = download(records)
        print(f"{n} file media diunduh ke downloads/")


if __name__ == "__main__":
    main()
