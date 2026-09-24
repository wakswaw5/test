# Toolkit Riset Meme

Kumpulan tool dan script untuk memantau tren meme (Reddit, YouTube, Instagram) dan
menyimpan **metadata**-nya untuk riset. Hasil unduhan hanya untuk analisis tren —
lihat [Catatan etika & legal](#catatan-etika--legal) di bawah.

## Isi repo

| Path | Fungsi |
|---|---|
| `scripts/reddit_top.py` | Ambil N post teratas subreddit lewat Reddit API (PRAW), simpan metadata ke `data/` |
| `scripts/gallery_dl_top.sh` | Contoh gallery-dl: unduh 3 gambar teratas harian r/memes (tanpa API key) |
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

## Menjalankan di Windows (PowerShell)

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

## Kredensial Reddit API

`reddit_top.py` dan `bdfr` memakai Reddit API resmi. Cara mendapatkan kredensial:

1. Buka https://www.reddit.com/prefs/apps (login dulu).
2. Klik **create another app...**, pilih tipe **script**.
3. Isi *name* bebas, *redirect uri*: `http://localhost:8080`.
4. Setelah dibuat: string pendek di bawah nama app = **client_id**, field *secret* = **client_secret**.

Simpan di environment variable — **jangan pernah** ditulis di dalam script atau di-commit:

```powershell
$env:REDDIT_CLIENT_ID = "..."
$env:REDDIT_CLIENT_SECRET = "..."
```

Atau taruh di file `.env` (sudah ada di `.gitignore`):

```
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

lalu load sebelum menjalankan, misalnya di PowerShell:

```powershell
Get-Content .env | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v }
```

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

Tanpa kredensial, script berhenti dan mencetak panduan membuatnya.

### `scripts/gallery_dl_top.sh` — 3 gambar teratas harian tanpa API key

```bash
scripts/gallery_dl_top.sh            # r/memes
scripts/gallery_dl_top.sh dankmemes  # subreddit lain
```

Perintah intinya (bisa dijalankan langsung di PowerShell):

```powershell
gallery-dl --range 1-3 --directory downloads/memes --write-metadata "https://www.reddit.com/r/memes/top/?t=day"
```

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
