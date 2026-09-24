#!/usr/bin/env python3
"""Wizard login sosial media untuk toolkit riset meme.

    python scripts/login.py                 # semua platform, satu per satu
    python scripts/login.py --only reddit,x # sebagian saja
    python scripts/login.py --check         # cek status login tanpa mengubah apa pun

Prinsip: password tidak pernah diminta oleh script ini. Kamu login sendiri di browser,
tool (yt-dlp / gallery-dl / instaloader) membaca cookie dari browser itu saat dipakai.
Yang disimpan ke .env hanya: client_id/secret Reddit, nama browser, username Instagram.
"""

import argparse
import os
import re
import subprocess
import sys
import webbrowser
from getpass import getpass

from _env import ENV_FILE, ROOT, load_env, set_env

PY = sys.executable
PLATFORMS = ["browser", "reddit", "instagram", "x", "facebook"]
BROWSERS = ["firefox", "chrome", "edge", "brave"]

# URL publik untuk tes cookie X. Kalau mati, wizard akan minta URL lain.
X_TEST_URL = "https://x.com/NASA/media"
# Facebook: URL halaman video tidak didukung yt-dlp, jadi wizard minta URL reel dari user
# dan menyimpannya di .env (FACEBOOK_TEST_URL) untuk --check berikutnya.


def hr(title):
    print(f"\n{'=' * 60}\n {title}\n{'=' * 60}")


def ok(msg):
    print(f"  [OK] {msg}")


def fail(msg):
    print(f"  [X]  {msg}")


def ask(prompt, default=""):
    s = input(f"  {prompt}{f' [{default}]' if default else ''}: ").strip()
    return s or default


def run(args, timeout=90):
    """Jalankan perintah, kembalikan (kode, stdout+stderr)."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except FileNotFoundError as e:
        return 127, str(e)


def last_line(text):
    lines = [l for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else "(tidak ada output)"


def browser():
    return os.environ.get("COOKIE_BROWSER", "firefox")


def open_url(url):
    """Buka URL di browser yang dipilih (COOKIE_BROWSER), bukan browser default Windows."""
    b = browser()
    exe = {"firefox": "firefox", "chrome": "chrome", "edge": "msedge", "brave": "brave"}.get(b, b)
    try:
        if sys.platform == "win32":
            # 'start <nama>' mencari program lewat registry App Paths, jadi tidak perlu ada di PATH
            subprocess.run(["cmd", "/c", "start", "", exe, url], check=True,
                           capture_output=True, timeout=15)
        else:
            subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    except Exception:  # noqa: BLE001 — jatuh ke browser default
        print(f"  (tidak bisa membuka {b}, memakai browser default — pastikan login di {b})")
        webbrowser.open(url)


# ---------------------------------------------------------------- browser
def setup_browser():
    hr("0. Browser untuk cookie")
    print("  Kamu akan login IG / X / FB di browser biasa. Tool membaca cookie dari situ.")
    print("  Firefox paling stabil. Chrome/Edge kadang gagal karena enkripsi cookie Windows.")
    b = ask(f"Browser ({'/'.join(BROWSERS)})", browser()).lower()
    if b not in BROWSERS:
        fail(f"'{b}' tidak dikenal, pakai firefox")
        b = "firefox"
    set_env("COOKIE_BROWSER", b)
    ok(f"COOKIE_BROWSER={b} disimpan ke .env")
    if b != "firefox":
        print(f"  !! Sejak 2024 {b.capitalize()} di Windows mengenkripsi cookie (app-bound encryption)")
        print("     dan yt-dlp/gallery-dl/instaloader TIDAK bisa membacanya. Kalau X/FB/IG gagal,")
        print("     pasang Firefox, login di sana, lalu ulangi wizard dan pilih firefox.")
    return True


def check_browser():
    b = browser()
    code, out = run([PY, "-m", "yt_dlp", "--cookies-from-browser", b, "--simulate", "--quiet",
                     "--no-warnings", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    if code == 0:
        ok(f"cookie dari {b} bisa dibaca")
        return True
    fail(f"cookie dari {b} tidak bisa dibaca: {last_line(out)}")
    if b != "firefox":
        print("  Saran: pasang Firefox, login di sana, lalu jalankan wizard lagi dan pilih firefox.")
    return False


# ---------------------------------------------------------------- reddit
def check_reddit(verbose=True):
    cid, sec = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not sec:
        # Tanpa API key, reddit_top.py memakai gallery-dl — uji jalur itu.
        try:
            from reddit_top import fetch_public
            post = fetch_public("memes", "day", 1)[0]
            ok(f"Reddit tanpa API key (via gallery-dl) jalan (contoh post: {post.title[:50]!r})")
            return True
        except SystemExit as e:
            fail(f"Reddit tanpa API key: {e}")
        except Exception as e:  # noqa: BLE001
            fail(f"Reddit tanpa API key gagal: {type(e).__name__}: {e}")
        return False
    try:
        import praw
        r = praw.Reddit(client_id=cid, client_secret=sec, user_agent="meme-research-toolkit login-check")
        r.read_only = True
        post = next(r.subreddit("memes").hot(limit=1))
        ok(f"Reddit API jalan (contoh post: {post.title[:50]!r})")
        return True
    except Exception as e:  # noqa: BLE001 — tampilkan apa pun errornya ke user
        fail(f"Reddit API gagal: {type(e).__name__}: {e}")
        return False


def setup_reddit():
    hr("1. Reddit API (OPSIONAL)")
    if os.environ.get("REDDIT_CLIENT_ID") and ask("Sudah ada kredensial di .env. Ganti? (y/N)", "n").lower() != "y":
        return check_reddit()
    print("  Tanpa API key, reddit_top.py tetap jalan lewat gallery-dl (tanpa login).")
    print("  CATATAN: sejak Nov 2025 (Responsible Builder Policy) tombol 'create app' di")
    print("  prefs/apps biasanya TIDAK berfungsi untuk akun baru; akses harus diminta lewat")
    print("  link 'register to use the API' dan sering ditolak. Kalau begitu, lewati saja.")
    if ask("Coba buat API key? (y/N)", "n").lower() != "y":
        return check_reddit()
    print("  Membuka https://www.reddit.com/prefs/apps ...")
    print("  1. Login Reddit, klik 'create another app...', pilih tipe: script")
    print("  2. name: bebas | redirect uri: http://localhost:8080 | klik create app")
    print("  3. client_id = string pendek di bawah nama app; secret = field 'secret'")
    webbrowser.open("https://www.reddit.com/prefs/apps")
    cid = ask("client_id (kosong = lewati)")
    sec = getpass("  client_secret (tidak ditampilkan): ").strip() if cid else ""
    if not cid or not sec:
        print("  dilewati, pakai mode tanpa API key")
        return check_reddit()
    set_env("REDDIT_CLIENT_ID", cid)
    set_env("REDDIT_CLIENT_SECRET", sec)
    ok("disimpan ke .env")
    return check_reddit()


# ---------------------------------------------------------------- instagram
def check_instagram():
    user = os.environ.get("INSTAGRAM_USERNAME")
    if not user:
        fail("INSTAGRAM_USERNAME belum ada di .env")
        return False
    try:
        import instaloader
        L = instaloader.Instaloader(quiet=True)
        L.load_session_from_file(user)
        if L.test_login() == user:
            ok(f"sesi Instagram @{user} valid")
            return True
        fail("sesi Instagram ada tapi sudah kadaluarsa")
    except FileNotFoundError:
        fail("sesi Instagram belum dibuat")
    except Exception as e:  # noqa: BLE001
        fail(f"Instagram: {type(e).__name__}: {e}")
    return False


def import_instagram_session():
    """Ambil cookie instagram.com dari browser lewat pembaca cookie yt-dlp (lebih andal
    daripada browser_cookie3 yang dipakai instaloader), lalu simpan sesi instaloader.
    Sesi disimpan di folder profil user (%LOCALAPPDATA%\\Instaloader), bukan di repo.
    Mengembalikan username, atau melempar exception dengan pesan yang jelas."""
    import instaloader
    from yt_dlp.cookies import extract_cookies_from_browser

    jar = extract_cookies_from_browser(browser())
    cookies = {c.name: c.value for c in jar if c.domain.endswith("instagram.com")}
    if "sessionid" not in cookies:
        raise RuntimeError(f"tidak ada cookie login instagram.com di {browser()} — sudah login di sana?")
    L = instaloader.Instaloader(quiet=True)
    L.context.update_cookies(cookies)
    user = L.test_login()
    if not user:
        raise RuntimeError("cookie ada tapi Instagram tidak mengenalinya sebagai sesi login")
    L.context.username = user
    L.save_session_to_file()
    return user


def setup_instagram():
    hr("2. Instagram")
    print("  Pakai AKUN SEKUNDER khusus riset — scraping bisa bikin akun dibatasi.")
    print(f"  Buka https://www.instagram.com di {browser()} dan login.")
    open_url("https://www.instagram.com/")
    input("  Tekan Enter setelah login di browser selesai... ")
    try:
        user = import_instagram_session()
    except Exception as e:  # noqa: BLE001
        fail(f"import sesi gagal: {type(e).__name__}: {e}")
        if browser() != "firefox":
            print("  Chrome/Edge: cookie terenkripsi, tidak bisa dibaca. Pakai Firefox.")
        return False
    set_env("INSTAGRAM_USERNAME", user)
    ok(f"login sebagai @{user}, sesi disimpan, username disimpan ke .env")
    return check_instagram()


# ---------------------------------------------------------------- x
def check_x(url=X_TEST_URL):
    code, out = run([PY, "-m", "gallery_dl", "--cookies-from-browser", browser(),
                     "--range", "1-1", "-g", url], timeout=120)
    if code == 0 and out.startswith("http"):
        ok("X: cookie valid, media bisa diambil")
        return True
    fail(f"X: {last_line(out)}")
    return False


def setup_x():
    hr("3. X / Twitter")
    print(f"  Buka https://x.com di {browser()} dan login (akun sekunder disarankan).")
    open_url("https://x.com/login")
    input("  Tekan Enter setelah login selesai... ")
    if check_x():
        return True
    url = ask("Tes dengan URL akun X lain (mis. https://x.com/<user>/media), kosong = lewati")
    return check_x(url) if url else False


# ---------------------------------------------------------------- facebook
def check_facebook(url=None):
    url = url or os.environ.get("FACEBOOK_TEST_URL")
    if not url:
        fail("Facebook: belum ada URL tes (jalankan wizard: python scripts/login.py --only facebook)")
        return False
    code, out = run([PY, "-m", "yt_dlp", "--cookies-from-browser", browser(), "--simulate",
                     "--no-warnings", "--print", "title", "--playlist-items", "1", url], timeout=120)
    if code == 0 and out:
        ok(f"Facebook: cookie valid (contoh: {last_line(out)[:50]!r})")
        return True
    fail(f"Facebook: {last_line(out)}")
    return False


def setup_facebook():
    hr("4. Facebook")
    print(f"  Buka https://www.facebook.com di {browser()} dan login.")
    open_url("https://www.facebook.com/")
    input("  Tekan Enter setelah login selesai... ")
    if os.environ.get("FACEBOOK_TEST_URL") and check_facebook():
        return True
    print("  Buka satu reel/video FB apa saja di browser, salin URL-nya (bentuk facebook.com/reel/...)")
    url = ask("URL reel/video FB untuk tes, kosong = lewati")
    if url:
        set_env("FACEBOOK_TEST_URL", url)
        return check_facebook(url)
    return False


# ---------------------------------------------------------------- main
SETUP = {"browser": setup_browser, "reddit": setup_reddit, "instagram": setup_instagram,
         "x": setup_x, "facebook": setup_facebook}
CHECK = {"browser": check_browser, "reddit": check_reddit, "instagram": check_instagram,
         "x": check_x, "facebook": check_facebook}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="daftar platform dipisah koma: " + ",".join(PLATFORMS))
    ap.add_argument("--check", action="store_true", help="hanya cek status, tidak login")
    args = ap.parse_args()

    if sys.prefix == sys.base_prefix and (ROOT / ".venv").exists():
        print("  !! Kamu menjalankan Python sistem, bukan .venv — paket toolkit tidak akan ketemu.")
        print("     Aktifkan dulu:  .\\.venv\\Scripts\\Activate.ps1")
        print("     atau jalankan:  .\\.venv\\Scripts\\python.exe scripts\\login.py ...\n")

    load_env()
    if not ENV_FILE.exists():
        ENV_FILE.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")

    wanted = [p.strip().lower() for p in args.only.split(",")] if args.only else PLATFORMS
    bad = [p for p in wanted if p not in PLATFORMS]
    if bad:
        sys.exit(f"platform tidak dikenal: {bad}. Pilihan: {PLATFORMS}")

    results = {}
    for p in wanted:
        if args.check:
            hr(f"cek {p}")
            results[p] = CHECK[p]()
        else:
            try:
                results[p] = SETUP[p]()
            except KeyboardInterrupt:
                print("\n  dilewati")
                results[p] = False

    hr("Ringkasan")
    for p, r in results.items():
        print(f"  {'OK ' if r else '-- '} {p}")
    print(f"\n  Konfigurasi: {ENV_FILE}  (jangan di-commit)")
    if not all(results.values()):
        print("  Ulangi yang gagal: python scripts/login.py --only <platform>")


if __name__ == "__main__":
    main()
