#!/usr/bin/env python3

"""Converts all .wav files inside current directory to .opus using ffmpeg."""

import argparse
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock


def default_worker_count():
    """One worker per two available CPUs, respecting cgroup/affinity limits."""
    try:
        available = len(os.sched_getaffinity(0))
    except AttributeError:  # Not available on every platform.
        available = os.cpu_count() or 4
    return max(1, available // 2)


MAX_WORKERS = default_worker_count()

print_lock = Lock()

BITRATE = "256k"


def convert(wav_path, opus_path, compression_level, delete_original):
    """Convert one file. Returns bytes saved on success, an error-message
    string on failure, None if skipped."""
    if opus_path.exists():
        with print_lock:
            print(f"Skipped: {wav_path.name} (output already exists: {opus_path.name})", file=sys.stderr)
        return None

    opus_path.parent.mkdir(parents=True, exist_ok=True)

    # Encode to a temp name and rename into place on success, so an
    # interrupted run never leaves a partial file at the final path (which a
    # rerun's exists() check would silently keep).
    part_path = opus_path.with_name(opus_path.name + ".part")

    try:
        wav_size = wav_path.stat().st_size
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",  # overwrite a stale .part left by an interrupted run
                "-i", str(wav_path),
                "-c:a", "libopus",
                "-b:a", BITRATE,
                "-vbr", "on",
                "-compression_level", str(compression_level),
                "-f", "opus",  # the .part suffix hides the format from ffmpeg
                str(part_path),
            ],
            capture_output=True,
            text=True,
            errors="replace",
        )
    except OSError as e:
        error = f"could not run ffmpeg: {e}"
        with print_lock:
            print(f"Failed: {wav_path.name} ({error})", file=sys.stderr)
        return error

    if result.returncode != 0 or not part_path.exists() or part_path.stat().st_size == 0:
        error = (result.stderr.strip() or "unknown error").splitlines()[-1]
        if result.returncode != 0:
            error = f"ffmpeg exited with code {result.returncode}: {error}"
        else:
            error = f"ffmpeg produced no output: {error}"
        part_path.unlink(missing_ok=True)
        with print_lock:
            print(f"Failed: {wav_path.name} ({error})", file=sys.stderr)
        return error

    # Mirror the source file's permission bits onto the converted file.
    try:
        shutil.copymode(wav_path, part_path)
    except OSError:
        pass

    try:
        os.replace(part_path, opus_path)
    except OSError as e:
        error = f"could not move finished file into place: {e}"
        part_path.unlink(missing_ok=True)
        with print_lock:
            print(f"Failed: {wav_path.name} ({error})", file=sys.stderr)
        return error

    opus_size = opus_path.stat().st_size

    deleted_note = ""
    if delete_original:
        try:
            wav_path.unlink()
            deleted_note = ", original deleted"
        except OSError as e:
            deleted_note = f", could not delete original ({e})"

    with print_lock:
        print(f"Converted: {wav_path.name} -> {opus_path.name}{deleted_note}")
    return wav_size - opus_size


def compression_level_arg(value):
    try:
        level = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid compression level: {value!r} (must be an integer 0-10)")
    if not 0 <= level <= 10:
        raise argparse.ArgumentTypeError(f"compression level must be between 0 and 10, got {level}")
    return level


def main():
    parser = argparse.ArgumentParser(
        description="Converts all .wav files inside current directory to .opus using ffmpeg.",
        usage="%(prog)s [keep_original_files] [compression_level]",
    )
    parser.add_argument(
        "keep_original_files",
        nargs="?",
        default="yes",
        choices=("yes", "no"),
        metavar="keep_original_files",
        help="Keep original .wav files after successful conversion (default: yes).",
    )
    parser.add_argument(
        "compression_level",
        nargs="?",
        default=10,
        type=compression_level_arg,
        help="Opus compression level 0-10 (default: 10). Higher levels cost more "
             "CPU time for slightly better quality at a given bitrate.",
    )
    args = parser.parse_args()
    delete_original = args.keep_original_files == "no"

    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found on PATH.", file=sys.stderr)
        sys.exit(1)

    cwd = Path.cwd()
    converted_root = cwd / "converted"
    wav_files = [
        p for p in cwd.rglob("*.wav", case_sensitive=False)  # needs Python 3.12+
        if p.is_file() and converted_root not in p.parents
    ]

    if not wav_files:
        print("No .wav files found in the current directory or its subdirectories.")
        return

    time1 = time.time()

    # Stat each file once, then dispatch biggest-first (longest-processing-time
    # scheduling) so workers stay saturated instead of stalling on one large
    # file at the tail. Path is a stable tiebreaker for equal-sized files.
    sizes = {p: p.stat().st_size for p in wav_files}
    wav_files.sort(key=lambda p: (-sizes[p], str(p)))

    succeeded = 0
    skipped = 0
    saved_bytes = 0
    failures = []  # (wav_path, error message) per failed file

    # When originals are kept, mirror the tree under "converted/"; otherwise
    # write each .opus in place next to its source so it replaces the original.
    if delete_original:
        opus_paths = [p.with_suffix(".opus") for p in wav_files]
    else:
        opus_paths = [converted_root / p.relative_to(cwd).with_suffix(".opus") for p in wav_files]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                convert,
                wav_path,
                opus_path,
                args.compression_level,
                delete_original,
            ): wav_path
            for wav_path, opus_path in zip(wav_files, opus_paths)
        }
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                skipped += 1
            elif isinstance(result, str):
                failures.append((futures[future], result))
            else:
                succeeded += 1
                saved_bytes += result

    print(f"\nDone: {succeeded} converted, {len(failures)} failed, {skipped} skipped, {len(wav_files)} total.")

    saved_gib = saved_bytes / 1024 ** 3
    print(f"Conversion completed. Managed to shave off {saved_gib:.2f} GiB.")
    print(f"Time elapsed: {time.time() - time1:.2f} seconds")

    if failures:
        sys.stdout.flush()  # keep the rundown after the stats when output is piped
        print(f"\n{len(failures)} file(s) failed to convert (originals left untouched):", file=sys.stderr)
        for wav_path, error in sorted(failures, key=lambda item: str(item[0])):
            print(f"  {wav_path.relative_to(cwd)}\n    {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
