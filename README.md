# Toolkit Riset Meme

Kumpulan tool dan script untuk memantau tren meme (Reddit, YouTube, Instagram) dan
menyimpan **metadata**-nya untuk riset. Hasil unduhan hanya untuk analisis tren —
lihat [Catatan etika & legal](#catatan-etika--legal) di bawah.

## Isi repo

| Path | Fungsi |
|---|---|
| `scripts/reddit_top.py` | Ambil N post teratas subreddit lewat Reddit API (PRAW), simpan metadata ke `data/` |
| `scripts/gallery_dl_top.sh` | Contoh gallery-dl: unduh 3 gambar teratas harian r/memes (tanpa API key) |
| `scripts/social_top.py` | Cari meme acak di Instagram (hashtag) + X (pencarian) [+ Facebook per page], simpan metadata seragam ke `data/` |
| `scripts/login.py` | Wizard login: Reddit API, Instagram, X, Facebook — kamu login sendiri, script cuma memverifikasi |
| `setup.ps1` | Setup otomatis di Windows (venv, paket, Node, Chromium, `.env`, lalu wizard login) |
| `node/` | Project Node.js dengan crawlee + playwright untuk scraping halaman yang butuh JavaScript |
| `vendor/Meme_Api/` | Salinan sumber [D3vd/Meme_Api](https://github.com/D3vd/Meme_Api) sebagai referensi (Go, tidak dijalankan) |
| `data/` | Metadata JSON hasil `reddit_top.py` (boleh di-commit) |
| `downloads/` | File media hasil tes (di-ignore git) |
| `.claude/skills/` | Skill Claude Code untuk tool scraping (Firecrawl, Scrapling, Crawlee, dll.) |

## Tool yang dipakai

| Tool | Versi | Untuk apa |
|---|---|---|
| yt-dlp | 2026.08.19 | Unduh/inspeksi video dari YouTube, TikTok, Reddit, dll. |
| gallery-dl | 1.32.13 | Unduh gambar dari Reddit, Twitter/X, Imgur, dll. tanpa API key |
| instaloader | 4.15.3 | Unduh post dari akun Instagram publik |
| bdfr | 2.6.2 | Bulk download subreddit (butuh Reddit API) |
| praw | 7.7.1 | Reddit API resmi dari Python (dipakai `reddit_top.py`) |
| scrapy | 2.19.0 | Framework crawler untuk situs meme lain |
| crawlee + playwright | 3.18 / 1.63 | Crawler Node.js dengan browser sungguhan |
| ffmpeg | 6.1 | Dipakai yt-dlp untuk menggabung audio/video |

## Setup otomatis di Windows (cara cepat)

```powershell
git clone <url-repo-ini> meme-tools
cd meme-tools
.\setup.ps1
```

`setup.ps1` mencari Python 3.10+, membuat `.venv`, memasang semua paket, mengecek ffmpeg dan
Node.js (menawarkan pemasangan lewat `winget` kalau belum ada), memasang crawlee + playwright +
Chromium, membuat `.env` dari `.env.example`, lalu menjalankan **wizard login**.

Opsi: `-SkipLogin` (setup saja), `-SkipNode` (tanpa Node.js),
`-Python "C:\path\ke\python.exe"` (kalau Python tidak ada di PATH).
Kalau PowerShell menolak menjalankan script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Wizard login: `scripts/login.py`

Kamu tinggal login satu per satu; script tidak pernah meminta password.

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/login.py                   # semua: browser → Reddit → Instagram → X → Facebook
python scripts/login.py --only x,facebook # sebagian
python scripts/login.py --check           # cek mana yang masih valid
```

| Langkah | Yang kamu lakukan | Yang disimpan |
|---|---|---|
| Browser | Pilih browser tempat login (Firefox paling stabil) | `COOKIE_BROWSER` di `.env` |
| Reddit (opsional) | Jawab `n` untuk lewati — script jalan tanpa API key. Kalau punya key lama, tempel di sini | `REDDIT_CLIENT_ID/SECRET` di `.env` |
| Instagram | Login di browser, ketik username | sesi di `%LOCALAPPDATA%\Instaloader` (di luar repo) |
| X | Login di browser, tekan Enter | tidak ada — cookie dibaca dari browser saat dipakai |
| Facebook | Login di browser, tekan Enter | tidak ada — sama seperti X |

Setiap langkah langsung diverifikasi (ambil 1 post / 1 media). Pakai **akun sekunder** untuk
IG/X/FB; scraping bisa membuat akun dibatasi.

## Setup manual di Windows (kalau tidak mau pakai setup.ps1)

```powershell
git clone <url-repo-ini> meme-tools
cd meme-tools

# Virtual environment Python (Python 3.10+; path dengan spasi harus dikutip)
& "C:\Users\MASTER CORE\AppData\Local\Programs\Python\Python312\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# ffmpeg harus ada di PATH: cek dengan
ffmpeg -version

# Node.js (untuk crawlee/playwright)
cd node
npm install
npx playwright install chromium
cd ..
```

Setiap kali membuka terminal baru, aktifkan venv dulu: `.\.venv\Scripts\Activate.ps1`.

`scripts/gallery_dl_top.sh` adalah script bash; di Windows jalankan lewat **Git Bash**, atau
salin perintah gallery-dl di dalamnya ke PowerShell.

## Kredensial Reddit API (opsional)

> **Sejak November 2025 Reddit memberlakukan *Responsible Builder Policy*:** tombol
> *create app* di `prefs/apps` biasanya tidak berfungsi untuk akun baru (CAPTCHA lolos,
> diklik, tidak terjadi apa-apa, hanya muncul kalimat kebijakan). Akses API harus diminta
> lewat link *register to use the API* dan sering ditolak.
>
> Karena itu **`reddit_top.py` tidak butuh API key**: tanpa kredensial ia memakai extractor
> Reddit milik gallery-dl (endpoint JSON "polos" Reddit sekarang menjawab 403). Kredensial hanya perlu untuk `bdfr` dan
> untuk rate limit yang lebih longgar. Kalau kamu sudah punya API key lama, tetap bisa dipakai.

Kalau ingin mencoba membuat kredensial:

1. Buka https://www.reddit.com/prefs/apps (login dulu).
2. Klik **create another app...**, pilih tipe **script**.
3. Isi *name* bebas, *redirect uri*: `http://localhost:8080`.
4. Setelah dibuat: string pendek di bawah nama app = **client_id**, field *secret* = **client_secret**.

Cara termudah: `python scripts/login.py --only reddit` — wizard membuka halamannya, kamu tempel
nilainya, dan disimpan ke `.env` (sudah di `.gitignore`). Semua script otomatis membaca `.env`,
jadi tidak perlu set environment variable manual. Kalau mau manual, isi `.env` mengikuti
`.env.example`, **jangan pernah** tulis nilainya di dalam script atau di-commit.

### Cookie IG / X / FB

Tidak ada kredensial yang disimpan. Kamu login di browser (nama browser ada di `COOKIE_BROWSER`
di `.env`), lalu tool membaca cookie dari browser itu setiap kali dijalankan:

```powershell
yt-dlp     --cookies-from-browser firefox "<URL>"
gallery-dl --cookies-from-browser firefox "<URL>"
instaloader --load-cookies firefox --login <username>   # sekali, lalu sesi tersimpan di luar repo
```

Chrome/Edge di Windows kadang gagal dibaca (enkripsi cookie); kalau begitu pakai Firefox.

## Cara pakai tiap script

### `scripts/reddit_top.py` — metadata top post subreddit

```powershell
python scripts/reddit_top.py                                # 10 post teratas hari ini dari r/memes
python scripts/reddit_top.py -s dankmemes -n 25 -t week     # 25 post teratas minggu ini
python scripts/reddit_top.py --download                     # + unduh maks. 5 file media ke downloads/ (tes saja)
```

Hasil: `data/<subreddit>_<YYYY-MM-DD>.json`, satu objek per post:
`judul`, `skor`, `jumlah_komentar`, `url_post`, `url_media`, `jenis_media`
(`gambar` / `video` / `galeri` / `teks` / `link`), `tanggal`, `nsfw`, `author`.

Tanpa kredensial, script otomatis memakai extractor Reddit milik gallery-dl (tidak perlu API key). Baris pertama
output menunjukkan mode yang dipakai.

### `scripts/gallery_dl_top.sh` — 3 gambar teratas harian tanpa API key

```bash
scripts/gallery_dl_top.sh            # r/memes
scripts/gallery_dl_top.sh dankmemes  # subreddit lain
```

Perintah intinya (bisa dijalankan langsung di PowerShell):

```powershell
gallery-dl --range 1-3 --directory downloads/memes --write-metadata "https://www.reddit.com/r/memes/top/?t=day"
```

### `scripts/social_top.py` — meme acak dari Instagram + X (+ Facebook)

Butuh login lewat `scripts/login.py` dulu (cookie dibaca dari `COOKIE_BROWSER`).

```powershell
python scripts/social_top.py                              # instagram + x, kata kunci acak, 10 post per platform
python scripts/social_top.py -q "meme kucing" -n 15       # kata kunci sendiri
python scripts/social_top.py -p x -t latest --lang id     # X: terbaru, bahasa Indonesia
python scripts/social_top.py --min-likes 500              # hanya post dengan >= 500 like
python scripts/social_top.py -p facebook --fb-page 9gag   # FB tidak punya pencarian: harus per page
python scripts/social_top.py --download --max-download 20 # + unduh file medianya ke downloads/<platform>/
```

Default `-t top` menyaring `min_faves:100` di X dan hanya post bermedia (`filter:media`);
`-t latest` tanpa batas like. Instagram hashtag hanya punya tab *recent*, jadi script
mengambil 4× lebih banyak lalu memilih yang paling banyak like.

Hasil: `data/social_<tanggal>_<jam>.json`, format sama dengan `reddit_top.py` plus `platform`,
`query`, dan untuk X: `retweet`, `views`. Kata kunci acak diambil dari daftar `QUERIES_X` /
`TAGS_IG` di atas file — edit sesuka hati.

Catatan:
- **Watermark tidak bisa dideteksi otomatis.** Cek manual; metadata `author` membantu melacak sumber.
- Instagram hashtag dan pencarian X hanya jalan dengan akun login; pakai akun sekunder.
- Facebook: gallery-dl/yt-dlp tidak punya pencarian FB, hanya foto dari satu page publik.

### yt-dlp — video dari satu URL

```powershell
# hanya lihat info, tidak mengunduh
yt-dlp --simulate --print title --print duration_string "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# unduh satu video (mp4, kualitas terbaik) ke downloads/
yt-dlp -o "downloads/%(title)s.%(ext)s" -f "bv*+ba/b" --merge-output-format mp4 "<URL>"

# hanya metadata JSON, tanpa media
yt-dlp --skip-download --write-info-json -o "data/%(id)s" "<URL>"
```

### instaloader — post dari akun Instagram publik

```powershell
# 5 post terbaru, tanpa video, tanpa komentar
instaloader --count 5 --no-videos --no-comments --dirname-pattern downloads/ig_{profile} -- <username>

# hanya metadata (tanpa gambar/video)
instaloader --count 5 --no-pictures --no-videos --no-comments --dirname-pattern downloads/ig_{profile} -- <username>
```

Instagram sering meminta login setelah beberapa request. Jangan simpan sesi login di repo.

### bdfr — bulk download subreddit (butuh Reddit API)

```powershell
bdfr download downloads/bdfr --subreddit memes --sort top --time day --limit 10
```

Saat pertama kali dijalankan bdfr akan membuka browser untuk otorisasi dan menyimpan
konfigurasinya di folder profil pengguna, bukan di repo.

### crawlee + playwright — situs yang butuh JavaScript

```powershell
cd node
node -e "const {PlaywrightCrawler}=require('crawlee');new PlaywrightCrawler({maxRequestsPerCrawl:3,async requestHandler({page,request,log}){log.info(await page.title()+' '+request.url)}}).run(['https://example.com'])"
```

Contoh lengkapnya ada di skill `.claude/skills/web-scraping-toolkit/SKILL.md`.

## Cara kerja Meme_Api (`vendor/Meme_Api`)

[D3vd/Meme_Api](https://github.com/D3vd/Meme_Api) adalah layanan kecil berbahasa **Go**
yang memberi JSON meme acak dari Reddit — versi publiknya ada di `https://meme-api.com/gimme`.
Disimpan di sini sebagai referensi desain, bukan untuk dijalankan (butuh Go, Redis, dan
kredensial Reddit). Alurnya:

1. **Startup** (`main.go`): membaca `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`, menukarnya
   dengan access token di `https://www.reddit.com/api/v1/access_token`
   (`libraries/reddit/oAuth.go`), dan menyambung ke Redis (`REDISCLOUD_URL`). Jika salah satu
   tidak ada, proses langsung berhenti.
2. **Request** ke `/gimme`, `/gimme/{count}`, `/gimme/{subreddit}`, `/gimme/{subreddit}/{count}`
   (router Gin di `server/router.go`, handler di `api/gimme/`). Tanpa subreddit, dipilih acak
   dari `memes`, `me_irl`, `dankmemes` (`data/subreddits.go`). Count maksimal 50.
3. **Cache**: handler mengecek Redis dulu. Kalau kosong, mengambil 100 post `hot` dari
   `https://oauth.reddit.com/r/<sub>/hot?limit=100`, menyaring yang bukan gambar, menyimpan
   hasilnya ke Redis selama 2 jam (`data/constants.go`), lalu mengembalikan post acak.
4. **Respons**: `postLink`, `subreddit`, `title`, `url` (media), `nsfw`, `spoiler`, `author`,
   `ups`, dan `preview` (daftar URL thumbnail dari kecil ke besar).

Ide yang diambil untuk toolkit ini: pakai API resmi lewat OAuth, simpan hasil sementara
supaya tidak membebani Reddit, dan simpan hanya metadata + URL media.

## Catatan etika & legal

- Hasil unduhan dan metadata di repo ini **hanya untuk riset tren**: melihat format, topik,
  dan timing meme yang sedang naik.
- **Jangan upload ulang** konten orang lain ke channel/akun yang dimonetisasi tanpa izin
  pembuatnya atau tanpa transformasi yang berarti (komentar, analisis, parodi, dsb.).
- Patuhi ToS Reddit, YouTube, dan Instagram serta rate limit API. Script di sini sengaja
  membatasi jumlah unduhan.
- Jangan pernah commit kredensial, cookie, atau file media. `.gitignore` sudah mengaturnya,
  tapi cek lagi dengan `git status` sebelum commit.
