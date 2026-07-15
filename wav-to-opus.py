#!/usr/bin/env python3

"""Convert all .wav files in the current directory (recursively) to Opus using ffmpeg.

Originals are left untouched; converted files are written to a "converted" folder,
mirroring the source directory structure.
"""

import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

MAX_WORKERS = max(1, (os.cpu_count() or 4) // 2)

print_lock = Lock()


def convert(wav_path, opus_path):
    if opus_path.exists():
        with print_lock:
            print(f"Skipped: {wav_path.name} (output already exists: {opus_path.name})", file=sys.stderr)
        return None

    opus_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-i", str(wav_path),
                "-c:a", "libopus",
                "-b:a", "192k",
                "-vbr", "on",
                "-compression_level", "10",
                str(opus_path),
            ],
            capture_output=True,
            text=True,
        )
    except OSError as e:
        with print_lock:
            print(f"Failed: {wav_path.name} ({e})", file=sys.stderr)
        return False

    if result.returncode != 0 or not opus_path.exists() or opus_path.stat().st_size == 0:
        error = result.stderr.strip().splitlines()[-1] if result.stderr else "unknown error"
        opus_path.unlink(missing_ok=True)
        with print_lock:
            print(f"Failed: {wav_path.name} ({error})", file=sys.stderr)
        return False

    with print_lock:
        print(f"Converted: {wav_path.name} -> {opus_path.name}")
    return True


def main():
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found on PATH.", file=sys.stderr)
        sys.exit(1)

    cwd = Path.cwd()
    converted_root = cwd / "converted"
    wav_files = sorted(
        p for p in cwd.rglob("*")
        if p.is_file() and p.suffix.lower() == ".wav" and converted_root not in p.parents
    )

    if not wav_files:
        print("No .wav files found in the current directory or its subdirectories.")
        return

    succeeded = 0
    failed = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(convert, wav_path, converted_root / wav_path.relative_to(cwd).with_suffix(".opus"))
            for wav_path in wav_files
        ]
        for future in as_completed(futures):
            result = future.result()
            if result is True:
                succeeded += 1
            elif result is False:
                failed += 1
            else:
                skipped += 1

    print(f"\nDone: {succeeded} converted, {failed} failed, {skipped} skipped, {len(wav_files)} total.")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
