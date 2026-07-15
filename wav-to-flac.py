#!/usr/bin/env python3

"""Convert all .wav files in the current directory to 24-bit FLAC using ffmpeg."""

import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

MAX_WORKERS = 4

print_lock = Lock()


def convert(wav_path):
    flac_path = wav_path.with_suffix(".flac")

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(wav_path),
            "-sample_fmt", "s32",
            "-bits_per_raw_sample", "24",
            str(flac_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 or not flac_path.exists() or flac_path.stat().st_size == 0:
        error = result.stderr.strip().splitlines()[-1] if result.stderr else "unknown error"
        flac_path.unlink(missing_ok=True)
        with print_lock:
            print(f"Failed: {wav_path.name} ({error})", file=sys.stderr)
        return False

    wav_path.unlink()
    with print_lock:
        print(f"Converted: {wav_path.name} -> {flac_path.name}")
    return True


def main():
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found on PATH.", file=sys.stderr)
        sys.exit(1)

    cwd = Path.cwd()
    wav_files = sorted(p for p in cwd.iterdir() if p.is_file() and p.suffix.lower() == ".wav")

    if not wav_files:
        print("No .wav files found in the current directory.")
        return

    succeeded = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(convert, wav_path) for wav_path in wav_files]
        for future in as_completed(futures):
            if future.result():
                succeeded += 1
            else:
                failed += 1

    print(f"\nDone: {succeeded} converted, {failed} failed, {len(wav_files)} total.")


if __name__ == "__main__":
    main()
