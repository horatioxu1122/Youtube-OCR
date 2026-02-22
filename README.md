# YouTube Hardcoded Subtitle Extractor

Extracts hardcoded (burned-in) Chinese subtitles from YouTube videos using OCR. Outputs plain text — no timecodes.

---

## Fresh Setup (Windows, nothing installed)

Follow these steps in order on a machine with no Python or uv installed.

### Step 1 — Install uv

Open **PowerShell** and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen PowerShell after this so the `uv` command is available.

### Step 2 — Install ffmpeg

In PowerShell:

```powershell
winget install Gyan.FFmpeg
```

Close and reopen PowerShell again after this.

### Step 3 — Verify both tools installed

```powershell
uv --version
ffmpeg -version
```

Both commands should print version info. If either fails, restart PowerShell and try again.

### Step 4 — Clone or copy the project

Place the project folder somewhere on your machine, e.g. `C:\Users\you\youtube-ocr`.

### Step 5 — Install Python and dependencies

Navigate to the project folder and run:

```powershell
cd "C:\Users\you\youtube-ocr"
uv sync
```

uv will automatically download Python 3.12 and all required packages. This only needs to be done once.

> **Note:** The first time you run the script, PaddleOCR will download its model weights (~200MB). This is automatic and only happens once.

---

## Usage

```bash
uv run extract_subs.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Output is saved to `subtitles.txt` in the current folder by default.

### Options

| Flag | Default | Description |
|---|---|---|
| `--output / -o` | `subtitles.txt` | Output file path |
| `--interval / -i` | `0.5` | Frame sampling interval in seconds (lower = more accurate, slower) |
| `--crop-ratio / -c` | `0.2` | Fraction of the frame bottom to scan for subtitles (0.2 = bottom 20%) |
| `--keep-frames` | off | Keep extracted frames instead of deleting them |
| `--browser / -b` | none | Browser to pull cookies from if YouTube blocks the download (`chrome`, `firefox`, `edge`) |
| `--cookies-file` | none | Path to a `cookies.txt` file — more reliable than `--browser` on Windows |

### Examples

```bash
# Save to a specific file
uv run extract_subs.py "https://youtube.com/watch?v=..." -o my_subs.txt

# Sample every second instead of every 0.5s (faster, may miss some lines)
uv run extract_subs.py "https://youtube.com/watch?v=..." -i 1.0

# Scan bottom 25% of frame (useful if subtitles are higher up)
uv run extract_subs.py "https://youtube.com/watch?v=..." -c 0.25
```

---

## How It Works

1. Downloads the video with `yt-dlp`
2. Extracts frames at the specified interval using `ffmpeg`
3. Crops the bottom portion of each frame where subtitles appear
4. Runs [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (simplified Chinese) on each crop
5. Deduplicates consecutive identical/similar lines
6. Writes unique subtitle lines to the output file

---

## Troubleshooting

**`uv` not found after install**
Close and reopen your terminal. If still missing, restart your computer.

**`ffmpeg` not found**
Close and reopen your terminal after `winget install Gyan.FFmpeg`. If still missing, restart your computer.

**YouTube says "Sign in to confirm you're not a bot" / DPAPI decryption error**

Modern Chrome and Edge on Windows encrypt cookies in a way that yt-dlp cannot read. The most reliable fix is to export a `cookies.txt` file manually:

1. Install the **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)** extension in Chrome or Edge
2. Go to [youtube.com](https://youtube.com) and make sure you are logged in
3. Click the extension icon → click **Export** → save the file as `cookies.txt` in the project folder
4. Run:

```bash
uv run extract_subs.py "https://youtube.com/watch?v=..." --cookies-file cookies.txt
```

> If you use Firefox, you can try `--browser firefox` directly (Firefox does not have the DPAPI encryption issue):
> ```bash
> uv run extract_subs.py "https://youtube.com/watch?v=..." --browser firefox
> ```

**Subtitles not being detected**
- Try `--crop-ratio 0.25` or higher if subtitles appear in the upper part of the bottom region
- Try `--interval 0.3` for denser sampling

**Processing is slow**
CPU-only inference is expected to be slow. A 20-minute video at 0.5s interval (~2400 frames) takes roughly 5-20 minutes depending on hardware.
