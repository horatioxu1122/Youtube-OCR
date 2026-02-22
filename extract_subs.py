"""
Extract hardcoded Chinese subtitles from YouTube videos.

Usage:
    uv run extract_subs.py <youtube_url> [--output output.txt] [--interval 0.5] [--crop-ratio 0.2]

Requirements:
    - ffmpeg must be installed and on PATH (https://ffmpeg.org/download.html)
"""

import argparse
import glob as glob_mod
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image


def find_ffmpeg() -> str:
    """Find ffmpeg executable, checking PATH and common Windows install locations."""
    # Check PATH first
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    # Check WinGet install location
    winget_pattern = str(
        Path.home()
        / "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/*/bin/ffmpeg.exe"
    )
    matches = glob_mod.glob(winget_pattern)
    if matches:
        return matches[0]
    print("ERROR: ffmpeg not found. Install it with: winget install Gyan.FFmpeg")
    sys.exit(1)


FFMPEG = find_ffmpeg()


def download_video(url: str, output_dir: Path, browser: str | None = None, cookies_file: str | None = None) -> Path:
    """Download a YouTube video using yt-dlp."""
    output_path = output_dir / "video.mp4"
    print(f"Downloading video from {url}...")
    # ios client doesn't support cookies; use tv_embedded (simpler n challenge) when cookies are needed
    using_cookies = bool(cookies_file or browser)
    player_client = "tv_embedded,web" if using_cookies else "ios,web"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--ffmpeg-location", str(Path(FFMPEG).parent),
        "--extractor-args", f"youtube:player_client={player_client}",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(output_path),
    ]
    if cookies_file:
        cmd += ["--cookies", cookies_file]
    elif browser:
        cmd += ["--cookies-from-browser", browser]
    cmd.append(url)
    subprocess.run(cmd, check=True)
    print(f"Downloaded to {output_path}")
    return output_path


def extract_frames(video_path: Path, output_dir: Path, interval: float = 0.5) -> list[Path]:
    """Extract frames from video at given interval (seconds)."""
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    print(f"Extracting frames every {interval}s...")
    subprocess.run(
        [
            FFMPEG, "-i", str(video_path),
            "-vf", f"fps=1/{interval}",
            "-q:v", "2",
            str(frames_dir / "frame_%06d.jpg"),
        ],
        check=True,
        capture_output=True,
    )
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    print(f"Extracted {len(frames)} frames")
    return frames


def crop_subtitle_region(image_path: Path, crop_ratio: float = 0.2) -> Image.Image:
    """Crop the bottom portion of an image where subtitles typically appear."""
    img = Image.open(image_path)
    w, h = img.size
    top = int(h * (1 - crop_ratio))
    return img.crop((0, top, w, h))


def ocr_frames(frames: list[Path], crop_ratio: float = 0.2) -> list[str]:
    """Run PaddleOCR on cropped subtitle regions and return text lines."""
    print("Initializing PaddleOCR (simplified Chinese)...")
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

    all_lines = []
    total = len(frames)
    for i, frame_path in enumerate(frames):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  OCR processing frame {i + 1}/{total}...")

        cropped = crop_subtitle_region(frame_path, crop_ratio)
        img_array = np.array(cropped)

        # 2.x API: returns [[[bbox, (text, confidence)], ...]] or [[None]]
        result = ocr.ocr(img_array, cls=True)
        if not result or not result[0]:
            continue

        frame_text = " ".join(line[1][0] for line in result[0])
        if frame_text.strip():
            all_lines.append(frame_text.strip())

    return all_lines


def _lcs_ratio(a: str, b: str) -> float:
    """Longest-common-subsequence similarity ratio between two strings."""
    m, n = len(a), len(b)
    if m == 0 and n == 0:
        return 1.0
    if m == 0 or n == 0:
        return 0.0
    # DP table (only two rows needed)
    prev_row = [0] * (n + 1)
    for i in range(1, m + 1):
        curr_row = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr_row[j] = prev_row[j - 1] + 1
            else:
                curr_row[j] = max(prev_row[j], curr_row[j - 1])
        prev_row = curr_row
    return (2 * prev_row[n]) / (m + n)


def deduplicate(lines: list[str], similarity_threshold: float = 0.8) -> list[str]:
    """Remove consecutive near-duplicate lines using LCS similarity."""
    if not lines:
        return []

    deduped = [lines[0]]
    for line in lines[1:]:
        if _lcs_ratio(line, deduped[-1]) < similarity_threshold:
            deduped.append(line)
    return deduped


def main():
    parser = argparse.ArgumentParser(description="Extract hardcoded Chinese subtitles from YouTube videos")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--output", "-o", default="subtitles.txt", help="Output text file (default: subtitles.txt)")
    parser.add_argument("--interval", "-i", type=float, default=0.5, help="Frame extraction interval in seconds (default: 0.5)")
    parser.add_argument("--crop-ratio", "-c", type=float, default=0.2, help="Bottom portion of frame to crop for subtitles (default: 0.2 = bottom 20%%)")
    parser.add_argument("--keep-frames", action="store_true", help="Keep extracted frames (default: clean up)")
    parser.add_argument("--browser", "-b", default=None, help="Browser to pull cookies from if YouTube blocks the download (e.g. chrome, firefox, edge)")
    parser.add_argument("--cookies-file", default=None, help="Path to a cookies.txt file for YouTube authentication (more reliable than --browser on Windows)")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(delete=not args.keep_frames) as tmp_dir:
        tmp_path = Path(tmp_dir)
        if args.keep_frames:
            print(f"Frames will be kept in: {tmp_path}")

        # Step 1: Download
        video_path = download_video(args.url, tmp_path, args.browser, args.cookies_file)

        # Step 2: Extract frames
        frames = extract_frames(video_path, tmp_path, args.interval)
        if not frames:
            print("No frames extracted. Check ffmpeg installation.")
            sys.exit(1)

        # Step 3: OCR
        lines = ocr_frames(frames, args.crop_ratio)
        print(f"OCR found {len(lines)} text lines")

        # Step 4: Deduplicate
        deduped = deduplicate(lines)
        print(f"After deduplication: {len(deduped)} unique lines")

    # Step 5: Write output
    output_path = Path(args.output)
    output_path.write_text("\n".join(deduped), encoding="utf-8")
    print(f"\nSubtitles saved to: {output_path}")
    print(f"Total lines: {len(deduped)}")


if __name__ == "__main__":
    main()
