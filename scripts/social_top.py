#!/usr/bin/env python3
"""Cari meme acak di Instagram, X, dan Facebook, simpan metadata seragam ke data/.

    python scripts/social_top.py                          # instagram + x, kata kunci acak, 10 post per platform
    python scripts/social_top.py -p x -q "meme kucing" -n 15
    python scripts/social_top.py --download --max-download 20   # + unduh file medianya
    python scripts/social_top.py -t latest --lang id -q memelucu # X terbaru berbahasa Indonesia
    python scripts/social_top.py -p facebook --fb-page <nama_page>

Login: pakai cookie browser yang dipilih di .env (COOKIE_BROWSER, isi lewat scripts/login.py).
Facebook tidak punya pencarian lewat tool ini — hanya foto/video dari satu page publik.
Watermark tidak bisa dideteksi otomatis; cek manual sebelum dipakai.
"""

import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

from _env import ROOT, load_env

DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = ROOT / "downloads"
MAX_DOWNLOAD = 5

# Kata kunci acak. Tambah/ubah sesuka hati.
QUERIES_X = ["meme", "memes", "meme indonesia", "meme lucu", "dank memes", "funny meme", "shitpost"]
TAGS_IG = ["meme", "memes", "memeindonesia", "memelucu", "dankmemes", "memeindo", "receh"]


def pick(seq, given):
    return given or random.choice(seq)


def build_url(platform, args):
    """Kembalikan (url, label_query). label_query disimpan di JSON supaya tahu asal datanya."""
    if platform == "instagram":
        tag = pick(TAGS_IG, args.query).lstrip("#").replace(" ", "")
        return f"https://www.instagram.com/explore/tags/{tag}/", f"#{tag}"
    if platform == "x":
        q = pick(QUERIES_X, args.query)
        # Catatan: X mengabaikan aksen, jadi "-même" akan meniadakan "meme" (ERROR_EMPTY_QUERY).
        # Tweet Prancis yang cocok karena "même" disaring belakangan di is_junk().
        parts = [q, "filter:media", "-filter:retweets"]
        if args.min_likes:
            parts.append(f"min_faves:{args.min_likes}")
        if args.lang:
            parts.append(f"lang:{args.lang}")
        return f"https://x.com/search?q={quote(' '.join(parts))}", q
    if platform == "facebook":
        if not args.fb_page:
            sys.exit("Facebook tidak punya pencarian; beri nama page: --fb-page <nama_page> "
                     "(contoh: --fb-page 9gag). Atau lewati facebook dengan -p instagram,x.")
        return f"https://www.facebook.com/{args.fb_page}/photos", f"page:{args.fb_page}"
    sys.exit(f"platform tidak dikenal: {platform}")


def is_junk(rec, query):
    """Saring hasil yang jelas bukan meme: tweet Prancis yang cocok gara-gara 'même'."""
    text_ = (rec.get("judul") or "").lower()
    if rec["platform"] == "x" and "meme" in query.lower() and "même" in text_ and "meme" not in text_:
        return True
    return False


def media_kind(url, file_kw):
    if file_kw.get("type") in ("video", "animated_gif") or file_kw.get("video_url"):
        return "video"
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in (".mp4", ".m3u8", ".webm", ".mov"):
        return "video"
    return "gambar"


def to_record(platform, post, files, label):
    """Petakan kwdict gallery-dl (beda per platform) ke format yang sama dengan reddit_top.py."""
    if platform == "instagram":
        rec = dict(
            id=str(post.get("post_id") or post.get("post_shortcode")),
            judul=(post.get("description") or "")[:500],
            skor=post.get("likes", 0), jumlah_komentar=post.get("comments", 0),
            url_post=post.get("post_url") or f"https://www.instagram.com/p/{post.get('post_shortcode')}/",
            author=post.get("username"),
        )
    elif platform == "x":
        a = post.get("author") or {}
        rec = dict(
            id=str(post.get("tweet_id")),
            judul=(post.get("content") or "")[:500],
            skor=post.get("favorite_count", 0), jumlah_komentar=post.get("reply_count", 0),
            url_post=f"https://x.com/{a.get('name', 'i')}/status/{post.get('tweet_id')}",
            author=a.get("name"), retweet=post.get("retweet_count", 0), views=post.get("view_count", 0),
        )
    else:  # facebook
        rec = dict(
            id=str(post.get("id") or post.get("photo_id") or post.get("set_id")),
            judul=(post.get("caption") or post.get("title") or "")[:500],
            skor=None, jumlah_komentar=None,
            url_post=post.get("url") or f"https://www.facebook.com/photo/?fbid={post.get('id')}",
            author=post.get("username") or post.get("user"),
        )
    date = post.get("date")
    kinds = [media_kind(u, kw) for u, kw in files]
    rec.update(
        platform=platform, query=label,
        url_media=[u for u, _ in files],
        _headers=[kw.get("_http_headers") or {} for _, kw in files],
        jenis_media=("galeri" if len(files) > 1 else kinds[0]) if files else "teks",
        tanggal=date.isoformat() if hasattr(date, "isoformat") else str(date or ""),
    )
    return rec


def fetch(platform, url, label, limit, browser, mode="top"):
    """Jalankan extractor gallery-dl, kumpulkan post + URL media, tanpa mengunduh."""
    from gallery_dl.extractor.message import Message

    from _gdl import make_extractor

    posts, cur_post, cur_files = [], None, []

    def flush():
        if cur_post is not None:
            posts.append(to_record(platform, cur_post, cur_files, label))

    try:
        ex = make_extractor(url, browser, options=[
            (("extractor", "instagram"), "videos", True),
            (("extractor", "twitter"), "videos", True),
            (("extractor", "twitter"), "retweets", False),
            (("extractor", "twitter"), "search-results", "top" if mode == "top" else "live"),
        ])
        for msg in ex:
            if msg[0] == Message.Directory:
                flush()
                if len(posts) >= limit:
                    cur_post = None
                    break
                cur_post, cur_files = msg[-1], []
            elif msg[0] == Message.Url:
                url, kw = msg[1], msg[2]
                if url.startswith("ytdl:") and kw.get("_fallback"):
                    url = kw["_fallback"][0]   # URL mp4 langsung (gallery-dl pakai ytdl hanya untuk DASH)
                cur_files.append((url, kw))
        flush()
    except Exception as e:  # noqa: BLE001 — tampilkan apa adanya, jangan diakali
        sys.exit(f"{platform}: gagal ({type(e).__name__}: {e}). Kalau soal login/cookie, jalankan "
                 f"scripts/login.py --check --only {platform}")
    return posts[:limit], ex


def download(records, session, budget):
    """Unduh media dari records, maksimal `budget` file. Mengembalikan jumlah yang terunduh."""
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    count = 0
    for rec in records:
        for i, url in enumerate(rec["url_media"]):
            if count >= budget:
                return count
            ext = Path(urlparse(url).path).suffix or (".mp4" if rec["jenis_media"] == "video" else ".jpg")
            dest = DOWNLOAD_DIR / rec["platform"] / f"{rec['id']}_{i}{ext}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if url.startswith("ytdl:"):
                print(f"  lewati (butuh yt-dlp): {rec['url_post']}")
                continue
            headers = (rec.get("_headers") or [{}] * len(rec["url_media"]))[i]
            try:
                r = session.get(url, headers=headers, timeout=60)
                r.raise_for_status()
                dest.write_bytes(r.content)
                print(f"  unduh -> {dest.relative_to(ROOT)}")
                count += 1
            except Exception as e:  # noqa: BLE001
                print(f"  gagal {url[:80]}: {e}", file=sys.stderr)
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--platforms", default="instagram,x", help="dipisah koma: instagram,x,facebook")
    ap.add_argument("-q", "--query", help="kata kunci / hashtag; kosong = acak dari daftar di script")
    ap.add_argument("-n", "--limit", type=int, default=10, help="post per platform (default 10)")
    ap.add_argument("-t", "--time", default="top", choices=["top", "latest"], help="X: top atau latest")
    ap.add_argument("--fb-page", help="nama page Facebook (wajib untuk facebook)")
    ap.add_argument("--min-likes", type=int, default=None,
                    help="minimal like (default: 100 untuk top, 0 untuk latest)")
    ap.add_argument("--lang", help="X: batasi bahasa, mis. id atau en")
    ap.add_argument("--download", action="store_true", help="unduh file media ke downloads/<platform>/")
    ap.add_argument("--max-download", type=int, default=MAX_DOWNLOAD,
                    help=f"batas jumlah file yang diunduh (default {MAX_DOWNLOAD})")
    args = ap.parse_args()

    if args.min_likes is None:
        args.min_likes = 100 if args.time == "top" else 0

    load_env()
    import os
    browser = os.environ.get("COOKIE_BROWSER", "firefox")

    all_records, sessions = [], {}
    for platform in [p.strip().lower() for p in args.platforms.split(",") if p.strip()]:
        url, label = build_url(platform, args)
        print(f"[{platform}] {label}  ({url})")
        # IG hashtag hanya punya tab "recent": ambil lebih banyak lalu pilih yang paling banyak like
        pool = min(args.limit * 4, 100) if platform == "instagram" else args.limit
        records, ex = fetch(platform, url, label, pool, browser, args.time)
        sessions[platform] = ex.session
        records = [r for r in records if not is_junk(r, label)]
        records = [r for r in records if (r["skor"] or 0) >= args.min_likes or r["skor"] is None]
        records.sort(key=lambda r: r["skor"] or 0, reverse=True)
        records = records[:args.limit]
        print(f"  {len(records)} post (dari {pool} yang diperiksa, min {args.min_likes} like)")
        all_records.extend(records)

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"social_{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
    public = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_records]
    out.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(all_records)} post -> {out.relative_to(ROOT)}")

    if args.download and all_records:
        # pakai session extractor (sudah bawa cookie + header) supaya CDN tidak menolak
        n = 0
        for platform, sess in sessions.items():
            if n >= args.max_download:
                break
            n += download([r for r in all_records if r["platform"] == platform], sess, args.max_download - n)
        print(f"{n} file media diunduh ke downloads/")


if __name__ == "__main__":
    main()
