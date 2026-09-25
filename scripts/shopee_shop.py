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


def find_item_lists(obj, depth=0):
    """Cari (rekursif) list of dict yang tampak seperti daftar produk Shopee."""
    if depth > 6:
        return
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj[:3]):
            probe = obj[0].get("item_basic", obj[0])
            if ("itemid" in probe or "item_id" in probe) and ("name" in probe or "title" in probe):
                yield obj
                return
        for x in obj:
            yield from find_item_lists(x, depth + 1)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from find_item_lists(v, depth + 1)


def find_detail(obj, depth=0):
    """Cari dict produk yang punya models/tier_variations (respons detail produk)."""
    if depth > 5 or not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, dict):
        if ("models" in obj or "tier_variations" in obj) and ("item_id" in obj or "itemid" in obj):
            return obj
        for v in obj.values():
            r = find_detail(v, depth + 1)
            if r:
                return r
    else:
        for v in obj:
            r = find_detail(v, depth + 1)
            if r:
                return r
    return None


def dom_items(page, shopid_hint=None):
    """Cadangan: baca kartu produk dari halaman (judul, harga, URL) kalau API tidak tertangkap."""
    out = []
    for a in page.locator("a[href*='-i.']").all():
        try:
            href = a.get_attribute("href") or ""
            m = re.search(r"-i\.(\d+)\.(\d+)", href)
            if not m:
                continue
            text = a.inner_text().strip().splitlines()
            text = [t.strip() for t in text if t.strip()]
            price = next((t for t in text if t.startswith("Rp")), "")
            title = next((t for t in text if not t.startswith("Rp") and len(t) > 8), "")
            out.append({
                "itemid": int(m.group(2)), "shopid": int(m.group(1)), "judul": title,
                "harga": int(re.sub(r"[^\d]", "", price)) if price else None,
                "harga_min": None, "harga_max": None, "stok": None, "terjual": None,
                "foto": [], "video": [], "varian": [],
                "url": "https://shopee.co.id" + href if href.startswith("/") else href,
            })
        except Exception:  # noqa: BLE001
            continue
    return out


# ---------------------------------------------------------------- browser
def scrape(shop, max_items, detail, headless=False, debug=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright belum ada. Jalankan:  pip install playwright && python -m playwright install chromium")

    items, seen = {}, set()
    detail_box = {}
    api_log = []
    phase = {"listing": True}

    def on_response(resp):
        url = resp.url
        if "/api/" not in url and "shopee" not in url:
            return
        try:
            if "json" not in (resp.headers.get("content-type") or ""):
                return
            data = resp.json()
        except Exception:  # noqa: BLE001 — bukan JSON
            return
        if debug:
            api_log.append(url)
        try:
            if phase["listing"]:
                for lst in find_item_lists(data):
                    for it in lst:
                        rec = parse_list_item(it)
                        if rec["itemid"] and rec["judul"] and rec["itemid"] not in seen:
                            seen.add(rec["itemid"])
                            items[rec["itemid"]] = rec
            d = find_detail(data)
            if d:
                iid = d.get("item_id") or d.get("itemid")
                detail_box[iid] = {"item": d}
        except Exception:  # noqa: BLE001
            pass

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, user_agent=UA, locale="id-ID",
            viewport={"width": 1280, "height": 900}, args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.on("response", on_response)

        shop_url = f"https://shopee.co.id/{shop}#product_list"

        def goto(url):
            """goto yang tahan terhadap redirect Shopee (ke login/verifikasi)."""
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception as e:  # noqa: BLE001 — "interrupted by another navigation" = redirect
                if "interrupted" not in str(e):
                    raise
            page.wait_for_timeout(4000)

        print(f"[shopee] membuka toko {shop} ...")
        goto(shop_url)
        if "/buyer/login" in page.url or "/verify" in page.url:
            print("  Shopee mewajibkan LOGIN untuk melihat toko.")
            print("  Login di JENDELA CHROMIUM yang terbuka (bukan Firefox — ini profil terpisah).")
            print("  Script menunggu sampai login selesai; tidak perlu tekan apa pun di sini.")
            for _ in range(600):                              # tunggu sampai 10 menit
                page.wait_for_timeout(1000)
                if "/buyer/login" not in page.url and "/verify" not in page.url:
                    break
            else:
                sys.exit("  Login tidak selesai dalam 10 menit. Ulangi perintahnya setelah login.")
            print("  Login terdeteksi, lanjut.")
            page.wait_for_timeout(2000)
            if shop not in page.url:
                goto(shop_url)
        if not items:                                         # belum ada respons daftar produk
            page.wait_for_timeout(4000)

        def merge_dom():
            for rec in dom_items(page):
                if rec["itemid"] not in seen:
                    seen.add(rec["itemid"])
                    items[rec["itemid"]] = rec

        # scroll + halaman berikutnya sampai cukup
        pages = 0
        while len(items) < max_items and pages < 50:
            for _ in range(6):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(600)
            merge_dom()
            before = len(items)
            nxt = page.locator("button.shopee-icon-button--right, button[aria-label='next page'], "
                               ".shopee-button-next, button.shopee-mini-page-controller__next-btn")
            if nxt.count() == 0 or nxt.first.is_disabled():
                break
            nxt.first.click()
            page.wait_for_timeout(3500)
            pages += 1
            merge_dom()
            if len(items) == before:
                break
        phase["listing"] = False

        # buang produk toko lain (rekomendasi Shopee ikut tertangkap): pakai shopid terbanyak
        shopids = [r["shopid"] for r in items.values() if r.get("shopid")]
        if shopids:
            shop_id = max(set(shopids), key=shopids.count)
            for k in [k for k, r in items.items() if r.get("shopid") not in (shop_id, None)]:
                del items[k]
        print(f"  {len(items)} produk ditemukan ({pages + 1} halaman)")
        if debug:
            DATA_DIR.mkdir(exist_ok=True)
            (DATA_DIR / "shopee_debug.txt").write_text("\n".join(api_log), encoding="utf-8")
            print(f"  debug: {len(api_log)} respons JSON dicatat di data/shopee_debug.txt")

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
        for attempt in range(3):
            try:
                with s.get(url, timeout=90, stream=True) as r:
                    r.raise_for_status()
                    tmp = path.with_suffix(path.suffix + ".part")
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                    tmp.replace(path)
                n += 1
                return
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"  gagal {url[:70]}: {e}", file=sys.stderr)
                time.sleep(2)

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
    ap.add_argument("--debug", action="store_true", help="catat semua endpoint JSON ke data/shopee_debug.txt")
    args = ap.parse_args()

    shop = shop_name(args.shop)
    recs = scrape(shop, args.max, not args.no_detail, args.headless, args.debug)
    if not recs:
        sys.exit("Tidak ada produk terbaca. Ulangi dengan --debug lalu kirim data/shopee_debug.txt "
                 "(daftar endpoint yang dipakai Shopee) supaya parser bisa disesuaikan.")
    write_outputs(shop, recs)
    if args.download:
        download(shop, recs)


if __name__ == "__main__":
    main()
