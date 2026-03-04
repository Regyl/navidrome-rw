# Yandex Music to Navidrome migration

Utility to migrate your Yandex Music liked tracks into a Navidrome-compatible library using:

- Yandex Music API (`yandex-music`) for scraping liked tracks
- yt-dlp (YouTube and other sites) for downloading audio — tried first
- Soulseek (`aioslsk`) for downloading — fallback when yt-dlp finds nothing
- LRCLIB (same backend used by `lrcget`) for synced `.lrc` lyrics

Navidrome expects the library layout:

- `Artist Name/Album Name/song.mp3`
- `Artist Name/Album Name/song.lrc`
- `Artist Name/Album Name/album-cover.jpg`

### Requirements

- Python
- A valid Yandex Music access token
- FFmpeg (for yt-dlp audio conversion)
- A Soulseek account (username and password) — used as fallback when yt-dlp finds nothing

Install dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

You can configure the tool either via regular environment variables or a `.env` file in the project root.

#### Using a `.env` file

Create a file named `.env` next to `main.py` with contents like:

```bash
YANDEX_MUSIC_TOKEN=your_yandex_token_here
SLSK_USERNAME=your_soulseek_username
SLSK_PASSWORD=your_soulseek_password
SLSK_DOWNLOAD_DIR=D:\Temp\SoulseekDownloads
YTDLP_DOWNLOAD_DIR=D:\Temp\YtdlpDownloads
YM_NAVIDROME_DATA=D:\Temp\YmNavidromeCache
```

These values will be loaded automatically when you run the CLI.

#### Using regular environment variables

Set the following environment variables:

- `YANDEX_MUSIC_TOKEN` – Yandex Music API token.
- `SLSK_USERNAME` – Soulseek username.
- `SLSK_PASSWORD` – Soulseek password.
- `SLSK_DOWNLOAD_DIR` – directory where temporary Soulseek downloads are stored.
- `YTDLP_DOWNLOAD_DIR` – directory where temporary yt-dlp downloads are stored.
- `YM_NAVIDROME_DATA` – directory where `migration.db`, `migration.log`, and `migration_liked_tracks.json` are stored.
- `NAVIDROME_FOLDER` – Target folder which navidrome reads

### Usage

Run a full sync into an existing Navidrome music root:

```bash
python -m main sync
```

Retry previously failed tracks:

```bash
python -m main retry-failed
```

List previously failed tracks:

```bash
python -m main list-failed
```

Count successfully downloaded tracks:

```bash
python -m main count-successful
```