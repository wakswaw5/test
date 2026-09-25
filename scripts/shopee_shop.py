#!/usr/bin/env python3
"""Ambil daftar produk sebuah toko Shopee: judul, varian, harga, foto, video.

    python scripts/shopee_shop.py https://shopee.co.id/addmaterial
    python scripts/shopee_shop.py addmaterial --max 30 --download
    python scripts/shopee_shop.py addmaterial --download --no-detail   # cepat: tanpa buka tiap produk

Cara kerja: membuka Shopee di Chromium sungguhan (Playwright, jendela terlihat) dan menyadap
respons JSON yang Shopee kirim ke halamannya sendiri (search_items untuk daftar, get_pc untuk
detail varian). Shopee memblokir request non-browser, jadi tidak ada cara lain yang andal.
Kalau Shopee minta login/captcha, selesaikan di jendela itu; profil browser disimpan di
.pw-profile/ (di luar git) supaya berikutnya tidak perlu lagi.

Hasil:
  data/shopee_<toko>.json dan .csv   — satu baris per varian: judul, varian, harga, stok, url
  downloads/shopee/<toko>/<judul>__<varian>_<n>.jpg  dan  <judul>.mp4  (dengan --download)

Setup sekali:  pip install playwright && python -m playwright install chromium
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from _env import ROOT

DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = ROOT / "downloads" / "shopee"
PROFILE_DIR = ROOT / ".pw-profile"
IMG_CDN = "https://down-id.img.susercontent.com/file/{}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def slug(text, maxlen=80):
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", str(text)).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:maxlen].rstrip(" .") or "tanpa-nama"


def shop_name(arg):
    if "shopee." in arg:
        return urlparse(arg).path.strip("/").split("/")[0]
    return arg.strip("/@ ")


def rupiah(v):
    return int(v) // 100000 if v else None   # Shopee menyimpan harga x100000


# ---------------------------------------------------------------- parsing respons Shopee
def parse_list_item(it):
    """Item dari /api/v4/shop/search_items (atau recommend). Kembalikan dict dasar."""
    it = it.get("item_basic", it)
    videos = []
    for v in it.get("video_info_list") or []:
        fmt = v.get("default_format") or (v.get("formats") or [{}])[0]
        if fmt.get("url"):
            videos.append(fmt["url"])
    return {
        "itemid": it.get("itemid"), "shopid": it.get("shopid"),
        "judul": it.get("name"),
        "harga": rupiah(it.get("price")), "harga_min": rupiah(it.get("price_min")),
        "harga_max": rupiah(it.get("price_max")),
        "stok": it.get("stock"), "terjual": it.get("historical_sold") or it.get("sold"),
        "foto": [IMG_CDN.format(h) for h in (it.get("images") or [it.get("image")]) if h],
        "video": videos,
        "url": f"https://shopee.co.id/product/{it.get('shopid')}/{it.get('itemid')}",
        "varian": [],
    }


def parse_detail(data, rec):
    """Data dari /api/v4/pdp/get_pc: isi varian (nama, harga, stok, foto varian)."""
    item = data.get("item") or data
    tiers = item.get("tier_variations") or []
    tier_imgs = {}
    if tiers:
        for opt, img in zip(tiers[0].get("options") or [], tiers[0].get("images") or []):
            if img:
                tier_imgs[opt] = IMG_CDN.format(img)
    for m in item.get("models") or []:
        name = m.get("name") or "default"
        first_opt = name.split(",")[0].strip()
        rec["varian"].append({
            "nama": name, "harga": rupiah(m.get("price")), "stok": m.get("stock"),
            "foto": tier_imgs.get(first_opt),
        })
    if item.get("images"):
        rec["foto"] = [IMG_CDN.format(h) for h in item["images"]]
    for v in item.get("video_info_list") or []:
        fmt = v.get("default_format") or (v.get("formats") or [{}])[0]
        if fmt.get("url") and fmt["url"] not in rec["video"]:
            rec["video"].append(fmt["url"])
    if item.get("name"):
        rec["judul"] = item["name"]
    return rec


# ---------------------------------------------------------------- browser
def scrape(shop, max_items, detail, headless=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright belum ada. Jalankan:  pip install playwright && python -m playwright install chromium")

    items, seen = {}, set()
    detail_box = {}

    def on_response(resp):
        url = resp.url
        try:
            if "/api/v4/shop/search_items" in url or "/api/v4/shop/rcmd_items" in url:
                data = resp.json()
                for it in (data.get("items") or data.get("data", {}).get("items") or []):
                    rec = parse_list_item(it)
                    if rec["itemid"] and rec["itemid"] not in seen:
                        seen.add(rec["itemid"])
                        items[rec["itemid"]] = rec
            elif "/api/v4/pdp/get_pc" in url:
                data = resp.json()
                d = data.get("data") or {}
                iid = (d.get("item") or {}).get("item_id") or (d.get("item") or {}).get("itemid")
                if iid:
                    detail_box[iid] = d
        except Exception:  # noqa: BLE001 — respons bukan JSON / bukan yang kita cari
            pass

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, user_agent=UA, locale="id-ID",
            viewport={"width": 1280, "height": 900}, args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.on("response", on_response)

        print(f"[shopee] membuka toko {shop} ...")
        page.goto(f"https://shopee.co.id/{shop}#product_list", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        if "login" in page.url or page.locator("text=Log in").count() and not items:
            print("  Shopee minta login/verifikasi. Selesaikan di jendela browser, lalu tekan Enter di sini.")
            input("  Enter kalau sudah... ")
            page.goto(f"https://shopee.co.id/{shop}#product_list", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

        # scroll + halaman berikutnya sampai cukup
        pages = 0
        while len(items) < max_items and pages < 50:
            for _ in range(6):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(600)
            before = len(items)
            nxt = page.locator("button.shopee-icon-button--right, button[aria-label='next page'], .shopee-button-next")
            if nxt.count() == 0 or nxt.first.is_disabled():
                break
            nxt.first.click()
            page.wait_for_timeout(3000)
            pages += 1
            if len(items) == before:
                break
        print(f"  {len(items)} produk ditemukan")

        recs = list(items.values())[:max_items]
        if detail:
            for i, rec in enumerate(recs, 1):
                print(f"  [{i}/{len(recs)}] detail: {rec['judul'][:60]}")
                try:
                    page.goto(rec["url"], wait_until="domcontentloaded")
                    for _ in range(20):                       # tunggu get_pc sampai 10 dtk
                        if rec["itemid"] in detail_box:
                            break
                        page.wait_for_timeout(500)
                    if rec["itemid"] in detail_box:
                        parse_detail(detail_box[rec["itemid"]], rec)
                    else:
                        print("    (detail tidak terbaca, pakai data daftar)")
                except Exception as e:  # noqa: BLE001
                    print(f"    gagal: {type(e).__name__}: {e}")
                time.sleep(1.5)                               # jangan terlalu cepat
        ctx.close()
    return recs


# ---------------------------------------------------------------- output
def write_outputs(shop, recs):
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / f"shopee_{shop}.json").write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for r in recs:
        if r["varian"]:
            for v in r["varian"]:
                rows.append([r["judul"], v["nama"], v["harga"], v["stok"], r["terjual"], r["url"]])
        else:
            rows.append([r["judul"], "", r["harga"] or r["harga_min"], r["stok"], r["terjual"], r["url"]])
    with open(DATA_DIR / f"shopee_{shop}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["judul", "varian", "harga_rp", "stok", "terjual", "url"])
        w.writerows(rows)
    print(f"{len(recs)} produk / {len(rows)} varian -> data/shopee_{shop}.json, .csv")


def download(shop, recs):
    dest = DOWNLOAD_DIR / shop
    dest.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Referer"] = "https://shopee.co.id/"
    n = 0

    def get(url, path):
        nonlocal n
        if path.exists():
            return
        try:
            r = s.get(url, timeout=60)
            r.raise_for_status()
            path.write_bytes(r.content)
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  gagal {url[:70]}: {e}", file=sys.stderr)

    for r in recs:
        title = slug(r["judul"])
        for i, u in enumerate(r["foto"], 1):
            get(u, dest / f"{title}_{i}.jpg")
        for v in r["varian"]:
            if v.get("foto"):
                get(v["foto"], dest / f"{title}__{slug(v['nama'], 40)}.jpg")
        for i, u in enumerate(r["video"], 1):
            get(u, dest / (f"{title}.mp4" if i == 1 else f"{title}_{i}.mp4"))
    print(f"{n} file diunduh ke downloads/shopee/{shop}/")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shop", help="URL toko atau nama toko, mis. https://shopee.co.id/addmaterial")
    ap.add_argument("--max", type=int, default=100, help="maksimal produk (default 100)")
    ap.add_argument("--no-detail", action="store_true", help="jangan buka tiap produk (tanpa varian & harga per varian)")
    ap.add_argument("--download", action="store_true", help="unduh foto + video")
    ap.add_argument("--headless", action="store_true", help="tanpa jendela (lebih sering diblokir Shopee)")
    args = ap.parse_args()

    shop = shop_name(args.shop)
    recs = scrape(shop, args.max, not args.no_detail, args.headless)
    if not recs:
        sys.exit("Tidak ada produk terbaca. Kalau jendela browser menampilkan captcha/login, "
                 "selesaikan dulu lalu ulangi; profil tersimpan di .pw-profile/.")
    write_outputs(shop, recs)
    if args.download:
        download(shop, recs)


if __name__ == "__main__":
    main()
