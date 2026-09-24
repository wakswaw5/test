#!/usr/bin/env python3
"""Ambil post paling populer dari akun/page meme yang kamu daftarkan di sources.txt.

    python scripts/meme_accounts.py                       # semua akun di sources.txt, 10 post terpopuler per akun
    python scripts/meme_accounts.py -n 20 --download      # + unduh videonya/gambarnya
    python scripts/meme_accounts.py -s "tiktok @rankedmemes" -s "instagram rankedmemes"
    python scripts/meme_accounts.py --latest              # urut terbaru, bukan terpopuler

Platform: tiktok (tanpa login, video tanpa watermark via yt-dlp), instagram, x, facebook
(tiga terakhir pakai cookie browser dari scripts/login.py).
Metadata -> data/accounts_<tanggal>_<jam>.json, media -> downloads/<platform>/<akun>/.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from _env import ROOT, load_env

DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = ROOT / "downloads"
SOURCES_FILE = ROOT / "sources.txt"
PLATFORMS = ("tiktok", "instagram", "x", "facebook")


def read_sources(path, extra):
    """Baca 'platform akun' dari sources.txt dan opsi -s. Kembalikan [(platform, akun)]."""
    lines = []
    if path.exists():
        lines += path.read_text(encoding="utf-8").splitlines()
    lines += extra or []
    out = []
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0].lower() not in PLATFORMS:
            sys.exit(f"baris sources tidak dikenal: {line!r} (format: <platform> <akun>)")
        item = (parts[0].lower(), parts[1].lstrip("@"))
        if item not in out:
            out.append(item)
    if not out:
        sys.exit(f"Tidak ada sumber. Isi {SOURCES_FILE.name} atau pakai -s \"tiktok @akun\".")
    return out


def profile_url(platform, account):
    return {
        "tiktok": f"https://www.tiktok.com/@{account}/posts",
        "instagram": f"https://www.instagram.com/{account}/posts",
        "x": f"https://x.com/{account}/media",
        "facebook": f"https://www.facebook.com/{account}/photos",
    }[platform]


def to_record(platform, account, post, files):
    """Satu format untuk semua platform (sama dengan social_top.py / reddit_top.py)."""
    date = post.get("date")
    if platform == "tiktok":
        stats = post.get("stats") or {}
        rec = dict(
            id=str(post.get("id")), judul=(post.get("desc") or "")[:500],
            skor=int(stats.get("diggCount") or 0), jumlah_komentar=int(stats.get("commentCount") or 0),
            views=int(stats.get("playCount") or 0),
            url_post=f"https://www.tiktok.com/@{account}/video/{post.get('id')}",
            jenis_media="gambar" if post.get("post_type") == "image" else "video",
        )
    elif platform == "instagram":
        rec = dict(
            id=str(post.get("post_id") or post.get("post_shortcode")),
            judul=(post.get("description") or "")[:500],
            skor=post.get("likes", 0), jumlah_komentar=post.get("comments", 0),
            url_post=post.get("post_url") or f"https://www.instagram.com/p/{post.get('post_shortcode')}/",
        )
    elif platform == "x":
        rec = dict(
            id=str(post.get("tweet_id")), judul=(post.get("content") or "")[:500],
            skor=post.get("favorite_count", 0), jumlah_komentar=post.get("reply_count", 0),
            views=post.get("view_count", 0), retweet=post.get("retweet_count", 0),
            url_post=f"https://x.com/{account}/status/{post.get('tweet_id')}",
        )
    else:  # facebook
        rec = dict(
            id=str(post.get("id") or post.get("photo_id") or post.get("set_id")),
            judul=(post.get("caption") or post.get("title") or "")[:500],
            skor=None, jumlah_komentar=None,
            url_post=post.get("url") or f"https://www.facebook.com/photo/?fbid={post.get('id')}",
        )
    urls = []
    for u, kw in files:
        if u.startswith("ytdl:") and kw.get("_fallback"):
            u = kw["_fallback"][0]
        urls.append(u)
    if "jenis_media" not in rec:
        video = any(kw.get("type") in ("video", "animated_gif") or kw.get("video_url")
                    or Path(urlparse(u).path).suffix.lower() in (".mp4", ".webm", ".mov") for u, kw in files)
        rec["jenis_media"] = "galeri" if len(files) > 1 else ("video" if video else "gambar") if files else "teks"
    rec.update(platform=platform, akun=account, url_media=urls,
               _headers=[kw.get("_http_headers") or {} for _, kw in files],
               tanggal=date.isoformat() if hasattr(date, "isoformat") else str(date or ""))
    return rec


TIKTOK_IDS = DATA_DIR / "tiktok_ids.json"   # cache: nama akun -> secUid (ID internal TikTok)


def _ydl(browser, **extra):
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True, "cookiesfrombrowser": (browser,) if browser else None}
    opts.update(extra)
    return yt_dlp.YoutubeDL({k: v for k, v in opts.items() if v is not None})


def tiktok_target(account, browser):
    """Tentukan URL daftar video untuk yt-dlp.

    TikTok sering tidak memberi secUid lewat halaman profil ("Unable to extract secondary
    user ID"). Jalan keluar resmi yt-dlp: ambil channel_id (= secUid) dari SATU video akun
    itu, lalu pakai "tiktokuser:<secUid>". Karena itu sources.txt boleh berisi URL video:
        tiktok https://www.tiktok.com/@akun/video/123
    secUid yang ditemukan disimpan di data/tiktok_ids.json supaya berikutnya cukup nama akun.
    """
    ids = json.loads(TIKTOK_IDS.read_text(encoding="utf-8")) if TIKTOK_IDS.exists() else {}
    if "/video/" in account or "/photo/" in account:            # URL satu video
        url = account if account.startswith("http") else "https://" + account
        name = url.split("/@", 1)[1].split("/", 1)[0] if "/@" in url else url
        with _ydl(browser) as y:
            info = y.extract_info(url, download=False)
        sec = info.get("channel_id")
        name = info.get("uploader") or info.get("channel") or name
        if not sec:
            raise RuntimeError("video ditemukan tapi tidak ada channel_id di metadatanya")
        ids[name] = sec
        DATA_DIR.mkdir(exist_ok=True)
        TIKTOK_IDS.write_text(json.dumps(ids, indent=2), encoding="utf-8")
        print(f"  secUid @{name} disimpan ke {TIKTOK_IDS.relative_to(ROOT)}")
        return name, f"tiktokuser:{sec}"
    if account in ids:
        return account, f"tiktokuser:{ids[account]}"
    return account, f"https://www.tiktok.com/@{account}"


def fetch_tiktok(account, limit, browser):
    """Daftar video sebuah akun TikTok lewat yt-dlp (tanpa mengunduh)."""
    try:
        account, target = tiktok_target(account, browser)
        with _ydl(browser, extract_flat=True, playlist_items=f"1-{limit}") as y:
            info = y.extract_info(target, download=False)
    except Exception as e:  # noqa: BLE001
        msg = str(e).splitlines()[0]
        print(f"  gagal ({type(e).__name__}: {msg[:160]})", file=sys.stderr)
        if "secondary user ID" in msg:
            print("  -> Buka satu video akun ini di browser, salin URL-nya, dan tulis di sources.txt:\n"
                  f"     tiktok https://www.tiktok.com/@{account}/video/<id>\n"
                  "     Script akan mengambil ID akun dari video itu dan menyimpannya.", file=sys.stderr)
        return [], None
    recs = []
    for e in info.get("entries") or []:
        ts = e.get("timestamp")
        recs.append(dict(
            id=str(e.get("id")), judul=(e.get("title") or e.get("description") or "")[:500],
            skor=int(e.get("like_count") or 0), jumlah_komentar=int(e.get("comment_count") or 0),
            views=int(e.get("view_count") or 0),
            url_post=e.get("url") or e.get("webpage_url") or f"https://www.tiktok.com/@{account}/video/{e.get('id')}",
            jenis_media="video", platform="tiktok", akun=account, url_media=[], _headers=[],
            tanggal=dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat() if ts else "",
        ))
    return recs[:limit], None


def fetch(platform, account, limit, browser):
    if platform == "tiktok":
        return fetch_tiktok(account, limit, browser)

    from gallery_dl.extractor.message import Message

    from _gdl import make_extractor

    posts, cur, files = [], None, []

    def flush():
        if cur is not None:
            posts.append(to_record(platform, account, cur, files))

    try:
        ex = make_extractor(profile_url(platform, account), browser, options=[
            (("extractor", "instagram"), "videos", True),
            (("extractor", "twitter"), "videos", True),
            (("extractor", "twitter"), "retweets", False),
            (("extractor", "tiktok"), "videos", True),
        ])
        for msg in ex:
            if msg[0] == Message.Directory:
                flush()
                if len(posts) >= limit:
                    cur = None
                    break
                cur, files = msg[-1], []
            elif msg[0] == Message.Url:
                files.append((msg[1], msg[2]))
        flush()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"  gagal ({type(e).__name__}: {e})", file=sys.stderr)
        return [], None
    return posts[:limit], ex


def download_tiktok(rec, dest_dir, browser):
    """Video TikTok lewat yt-dlp: memilih versi tanpa watermark secara otomatis."""
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {"outtmpl": str(dest_dir / "%(id)s.%(ext)s"), "quiet": True, "no_warnings": True,
            "cookiesfrombrowser": (browser,) if browser else None}
    with yt_dlp.YoutubeDL({k: v for k, v in opts.items() if v is not None}) as y:
        y.download([rec["url_post"]])
    print(f"  unduh -> {dest_dir.relative_to(ROOT)}/{rec['id']}.mp4")
    return 1


def download_files(rec, dest_dir, session, budget):
    dest_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for i, url in enumerate(rec["url_media"]):
        if n >= budget:
            break
        if url.startswith("ytdl:"):
            continue
        ext = Path(urlparse(url).path).suffix or (".mp4" if rec["jenis_media"] == "video" else ".jpg")
        dest = dest_dir / f"{rec['id']}_{i}{ext}"
        try:
            r = session.get(url, headers=rec["_headers"][i], timeout=60)
            r.raise_for_status()
            dest.write_bytes(r.content)
            print(f"  unduh -> {dest.relative_to(ROOT)}")
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  gagal {url[:80]}: {e}", file=sys.stderr)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--source", action="append", help='tambah sumber, mis. -s "tiktok @rankedmemes"')
    ap.add_argument("-n", "--limit", type=int, default=10, help="post per akun yang disimpan (default 10)")
    ap.add_argument("--scan", type=int, default=None,
                    help="post terbaru yang diperiksa per akun sebelum diurutkan (default 3x limit, maks 60)")
    ap.add_argument("--latest", action="store_true", help="urut terbaru, bukan terpopuler")
    ap.add_argument("--min-likes", type=int, default=0)
    ap.add_argument("--download", action="store_true", help="unduh media ke downloads/<platform>/<akun>/")
    ap.add_argument("--max-download", type=int, default=10, help="batas file per akun (default 10)")
    args = ap.parse_args()

    load_env()
    browser = os.environ.get("COOKIE_BROWSER", "firefox")
    scan = args.scan or min(args.limit * 3, 60)

    all_records = []
    for platform, account in read_sources(SOURCES_FILE, args.source):
        print(f"[{platform}] @{account}")
        records, ex = fetch(platform, account, args.limit if args.latest else scan, browser)
        records = [r for r in records if (r["skor"] or 0) >= args.min_likes or r["skor"] is None]
        if not args.latest:
            records.sort(key=lambda r: r["skor"] or 0, reverse=True)
        records = records[:args.limit]
        print(f"  {len(records)} post" + ("" if args.latest else f" terpopuler dari {scan} terbaru"))
        all_records.extend(records)

        if args.download and records:
            n = 0
            dest_dir = DOWNLOAD_DIR / platform / account
            for rec in records:
                if n >= args.max_download:
                    break
                try:
                    if platform == "tiktok":
                        n += download_tiktok(rec, dest_dir, browser)
                    else:
                        n += download_files(rec, dest_dir, ex.session, args.max_download - n)
                except Exception as e:  # noqa: BLE001
                    print(f"  gagal {rec['url_post']}: {type(e).__name__}: {e}", file=sys.stderr)
            print(f"  {n} file diunduh")

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"accounts_{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
    public = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_records]
    out.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(all_records)} post -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
