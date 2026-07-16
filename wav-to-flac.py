#!/usr/bin/env python3

"""Converts all .wav files in the current directory to .flac using ffmpeg.

By default original files are left untouched; converted files are written to a "converted" folder, mirroring the source directory structure. When originals are not kept ("no"), converted files are written in place alongside the sources and the originals are deleted, with no "converted" folder created.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
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


def convert(wav_path, flac_path, compression_level, delete_original):
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
                "-compression_level", str(compression_level),
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

    # Mirror the source file's permission bits onto the converted file.
    try:
        shutil.copymode(wav_path, flac_path)
    except OSError:
        pass

    deleted_note = ""
    if delete_original:
        try:
            wav_path.unlink()
            deleted_note = ", original deleted"
        except OSError as e:
            deleted_note = f", could not delete original ({e})"

    with print_lock:
        print(f"Converted: {wav_path.name} -> {flac_path.name} ({depth_label}{deleted_note})")
    return True


def compression_level_arg(value):
    try:
        level = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid compression level: {value!r} (must be an integer 1-12)")
    if not 1 <= level <= 12:
        raise argparse.ArgumentTypeError(f"compression level must be between 1 and 12, got {level}")
    return level


def main():
    parser = argparse.ArgumentParser(
        description="Converts all .wav files in the current directory to .flac using ffmpeg.",
        usage="%(prog)s [compression_level {1-12}] [keep_original_files {yes/no}]",
    )
    parser.add_argument(
        "compression_level",
        nargs="?",
        default=12,
        type=compression_level_arg,
        help="FLAC compression level 1-12 (default: 12).",
    )
    parser.add_argument(
        "keep_original_files",
        nargs="?",
        default="yes",
        choices=("no", "yes"),
        metavar="keep_original_files",
        help="Keep original .wav files after successful conversion (default: yes).",
    )
    args = parser.parse_args()
    delete_original = args.keep_original_files == "no"

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

    time1 = time.time()

    # Sum the original .wav sizes now, before any conversion (or deletion) happens.
    accum_size = sum(p.stat().st_size for p in wav_files)

    succeeded = 0
    failed = 0
    skipped = 0

    # When originals are kept, mirror the tree under "converted/"; otherwise
    # write each .flac in place next to its source so it replaces the original.
    if delete_original:
        flac_paths = [p.with_suffix(".flac") for p in wav_files]
    else:
        flac_paths = [converted_root / p.relative_to(cwd).with_suffix(".flac") for p in wav_files]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                convert,
                wav_path,
                flac_path,
                args.compression_level,
                delete_original,
            )
            for wav_path, flac_path in zip(wav_files, flac_paths)
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

    # Sum the resulting .flac sizes for the space-saving comparison.
    final_accum_size = sum(p.stat().st_size for p in flac_paths if p.is_file())

    saved_gib = (accum_size - final_accum_size) / 1024 ** 3
    print(f"Conversion completed. Managed to shave off {saved_gib:.2f} GiB.")
    print(f"Time Elapsed: {time.time() - time1:.2f} seconds")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
