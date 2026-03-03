## Yandex Music → Navidrome migration

Utility to migrate your Yandex Music liked tracks into a Navidrome-compatible library using:

- Yandex Music API (`yandex-music`) for scraping liked tracks
- Soulseek (`aioslsk`) for downloading full audio files
- LRCLIB (same backend used by `lrcget`) for synced `.lrc` lyrics

Navidrome expects the library layout:

- `Artist Name/Album Name/song.ext`
- `Artist Name/Album Name/song.lrc`
- `Artist Name/Album Name/album-cover.jpg`

This tool creates that layout under a single root directory.

### Requirements

- Python 3.10+
- A valid Yandex Music access token
- A Soulseek account (username and password)

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
```

These values will be loaded automatically when you run the CLI.

#### Using regular environment variables

Set the following environment variables:

- `YANDEX_MUSIC_TOKEN` – Yandex Music API token.
- `SLSK_USERNAME` – Soulseek username.
- `SLSK_PASSWORD` – Soulseek password.
- `SLSK_DOWNLOAD_DIR` – optional, directory where temporary Soulseek downloads are stored (defaults to `./slsk_downloads`).

### Usage

Run a full sync into an existing Navidrome music root:

```bash
python -m main sync --music-root "D:\Music\Navidrome"
```

Dry-run (no downloads, just logging what would happen):

```bash
python -m main dry-run --music-root "D:\Music\Navidrome"
```

Retry previously failed tracks:

```bash
python -m main retry-failed --music-root "D:\Music\Navidrome"
```

`migration.db` and `migration.log` are stored in the music root for tracking and diagnostics.
