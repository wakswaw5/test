#!/usr/bin/env bash
# Unduh 3 gambar teratas harian dari r/memes dengan gallery-dl (tanpa API key).
# Pakai: scripts/gallery_dl_top.sh [subreddit]   (default: memes)
set -euo pipefail

SUB="${1:-memes}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

gallery-dl \
  --range 1-3 \
  --directory "$ROOT/downloads/$SUB" \
  --write-metadata \
  "https://www.reddit.com/r/$SUB/top/?t=day"
