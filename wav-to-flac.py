#!/usr/bin/env python3

"""Convert all .wav files in the current directory (recursively) to FLAC using ffmpeg.

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


def probe_format(wav_path):
    """Return (bit_depth, is_float) for the source, defaulting to (24, False) if it can't be determined."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=sample_fmt,bits_per_raw_sample,bits_per_sample",
                "-of", "default=noprint_wrappers=1",
                str(wav_path),
            ],
            capture_output=True,
            text=True,
        )
    except OSError:
        return 24, False

    fields = dict(line.partition("=")[::2] for line in result.stdout.split())
    is_float = fields.get("sample_fmt", "").startswith(("flt", "dbl"))

    for key in ("bits_per_raw_sample", "bits_per_sample"):
        value = fields.get(key, "")
        if value.isdigit() and int(value) > 0:
            return int(value), is_float
    return 24, is_float


def convert(wav_path, flac_path):
    if flac_path.exists():
        with print_lock:
            print(f"Skipped: {wav_path.name} (output already exists: {flac_path.name})", file=sys.stderr)
        return None

    depth, is_float = probe_format(wav_path)
    if is_float:
        # FLAC is integer-only; float32 has a 24-bit mantissa, so 24-bit integer
        # FLAC preserves its full precision for normalized audio.
        depth_args = ["-sample_fmt", "s32", "-bits_per_raw_sample", "24"]
        depth_label = f"{depth}-bit float -> 24-bit"
    elif depth <= 16:
        depth_args = ["-sample_fmt", "s16"]
        depth_label = f"{depth}-bit"
    elif depth <= 24:
        depth_args = ["-sample_fmt", "s32", "-bits_per_raw_sample", "24"]
        depth_label = f"{depth}-bit"
    else:
        # 32-bit FLAC encoding requires -strict experimental in ffmpeg.
        depth_args = ["-sample_fmt", "s32", "-bits_per_raw_sample", "32", "-strict", "experimental"]
        depth_label = f"{depth}-bit"

    flac_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-i", str(wav_path),
                *depth_args,
                str(flac_path),
            ],
            capture_output=True,
            text=True,
        )
    except OSError as e:
        with print_lock:
            print(f"Failed: {wav_path.name} ({e})", file=sys.stderr)
        return False

    if result.returncode != 0 or not flac_path.exists() or flac_path.stat().st_size == 0:
        error = result.stderr.strip().splitlines()[-1] if result.stderr else "unknown error"
        flac_path.unlink(missing_ok=True)
        with print_lock:
            print(f"Failed: {wav_path.name} ({error})", file=sys.stderr)
        return False

    with print_lock:
        print(f"Converted: {wav_path.name} -> {flac_path.name} ({depth_label})")
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
            executor.submit(convert, wav_path, converted_root / wav_path.relative_to(cwd).with_suffix(".flac"))
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
