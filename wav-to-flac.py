#!/usr/bin/env python3

"""Converts all .wav files inside current directory to .flac using ffmpeg."""

import argparse
import os
import shutil
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock


def default_worker_count():
    """One worker per available CPU minus one, leaving a core for the OS and
    respecting cgroup/affinity limits."""
    try:
        available = len(os.sched_getaffinity(0))
    except AttributeError:  # Not available on every platform.
        available = os.cpu_count() or 4
    return max(1, available - 1)


MAX_WORKERS = default_worker_count()

print_lock = Lock()

# IEEE float sample format tags (in both the classic fmt tag and the
# WAVE_FORMAT_EXTENSIBLE SubFormat GUID prefix).
WAVE_FORMAT_IEEE_FLOAT = 3
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

MIN_PYTHON = (3, 12)  # rglob(case_sensitive=...) requires Python 3.12+.
REQUIRED_ENCODER = "flac"


def encoder_available(name):
    """True if the local ffmpeg build includes the named encoder.

    An unknown encoder still makes ffmpeg exit 0, so this matches on the
    "Encoder <name> ..." header ffmpeg prints to stdout for a real one.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-h", f"encoder={name}"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.stdout.startswith(f"Encoder {name} ")


def probe_format(wav_path):
    """Return (bit_depth, is_float) by parsing the WAV/RF64 header directly.

    Reads only the RIFF chunk table and the ``fmt `` chunk — no subprocess.
    Defaults to (24, False) if the file isn't a parseable WAV.
    """
    try:
        with open(wav_path, "rb") as f:
            riff = f.read(12)
            if len(riff) < 12 or riff[0:4] not in (b"RIFF", b"RF64") or riff[8:12] != b"WAVE":
                return 24, False

            # Walk the chunk table looking for "fmt " (it may be preceded by
            # JUNK, ds64, bext, etc.).
            while True:
                header = f.read(8)
                if len(header) < 8:
                    return 24, False
                chunk_id, chunk_size = struct.unpack("<4sI", header)

                if chunk_id == b"fmt ":
                    fmt = f.read(chunk_size)
                    if len(fmt) < 16:
                        return 24, False
                    audio_format, = struct.unpack_from("<H", fmt, 0)
                    bits_per_sample, = struct.unpack_from("<H", fmt, 14)
                    if audio_format == WAVE_FORMAT_EXTENSIBLE and len(fmt) >= 26:
                        # Extensible: the real format is the first 2 bytes of
                        # the SubFormat GUID (offset 24), and the true bit
                        # depth is wValidBitsPerSample (offset 18).
                        valid_bits, = struct.unpack_from("<H", fmt, 18)
                        sub_format, = struct.unpack_from("<H", fmt, 24)
                        is_float = sub_format == WAVE_FORMAT_IEEE_FLOAT
                        if valid_bits > 0:
                            bits_per_sample = valid_bits
                    else:
                        is_float = audio_format == WAVE_FORMAT_IEEE_FLOAT
                    if bits_per_sample > 0:
                        return bits_per_sample, is_float
                    return 24, is_float

                # Chunks are word-aligned: skip the data plus any pad byte.
                f.seek(chunk_size + (chunk_size & 1), os.SEEK_CUR)
    except OSError:
        return 24, False


def convert(wav_path, flac_path, compression_level, delete_original):
    """Convert one file. Returns bytes saved on success, an error-message
    string on failure, None if skipped."""
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

    # Encode to a temp name and rename into place on success, so an
    # interrupted run never leaves a partial file at the final path (which a
    # rerun's exists() check would silently keep).
    part_path = flac_path.with_name(flac_path.name + ".part")

    try:
        wav_size = wav_path.stat().st_size
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",  # overwrite a stale .part left by an interrupted run
                "-i", str(wav_path),
                *depth_args,
                "-compression_level", str(compression_level),
                "-f", "flac",  # the .part suffix hides the format from ffmpeg
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
        os.replace(part_path, flac_path)
    except OSError as e:
        error = f"could not move finished file into place: {e}"
        part_path.unlink(missing_ok=True)
        with print_lock:
            print(f"Failed: {wav_path.name} ({error})", file=sys.stderr)
        return error

    flac_size = flac_path.stat().st_size

    deleted_note = ""
    if delete_original:
        try:
            wav_path.unlink()
            deleted_note = ", original deleted"
        except OSError as e:
            deleted_note = f", could not delete original ({e})"

    with print_lock:
        print(f"Converted: {wav_path.name} -> {flac_path.name} ({depth_label}{deleted_note})")
    return wav_size - flac_size


def compression_level_arg(value):
    try:
        level = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid compression level: {value!r} (must be an integer 1-12)")
    if not 1 <= level <= 12:
        raise argparse.ArgumentTypeError(f"compression level must be between 1 and 12, got {level}")
    return level


def force_utf8_output():
    """Print to the console as UTF-8 regardless of the OS locale.

    On Windows stdout defaults to the legacy code page (e.g. cp1252), which
    can't encode filenames containing characters outside that page (Cyrillic,
    CJK, ...), so printing them raises UnicodeEncodeError. Reconfiguring to
    UTF-8 with errors="replace" makes such names printable everywhere.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main():
    force_utf8_output()

    parser = argparse.ArgumentParser(
        description="Converts all .wav files inside current directory to .flac using ffmpeg.",
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
        default=5,
        type=compression_level_arg,
        help="FLAC compression level 1-12 (default: 5). Levels 8-12 cost roughly "
             "2-5x the CPU time for typically ~1%% smaller files.",
    )
    args = parser.parse_args()
    delete_original = args.keep_original_files == "no"

    if sys.version_info < MIN_PYTHON:
        print(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.", file=sys.stderr)
        sys.exit(1)

    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found on PATH.", file=sys.stderr)
        sys.exit(1)

    if not encoder_available(REQUIRED_ENCODER):
        print(f"ffmpeg is installed but lacks the required '{REQUIRED_ENCODER}' encoder.", file=sys.stderr)
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
    # write each .flac in place next to its source so it replaces the original.
    if delete_original:
        flac_paths = [p.with_suffix(".flac") for p in wav_files]
    else:
        flac_paths = [converted_root / p.relative_to(cwd).with_suffix(".flac") for p in wav_files]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                convert,
                wav_path,
                flac_path,
                args.compression_level,
                delete_original,
            ): wav_path
            for wav_path, flac_path in zip(wav_files, flac_paths)
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
