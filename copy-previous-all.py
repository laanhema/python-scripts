#!/usr/bin/env python3

"""
Copies both the last executed terminal command and its output to the clipboard.
"""

import os
import subprocess
import sys


def copy_to_clipboard(text):
    """Copy text to clipboard using wl-copy, xclip, xsel, or termux-clipboard-set."""
    temp_path = "/tmp/cpa_clipboard.txt"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(text)

    commands = [
        (['wl-copy'], 'wl-copy'),
        (['xclip', '-selection', 'clipboard'], 'xclip'),
        (['xsel', '--clipboard', '--input'], 'xsel'),
        (['termux-clipboard-set'], 'termux-clipboard-set'),
    ]

    for cmd, name in commands:
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                process = subprocess.Popen(cmd, stdin=f, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                process.wait()
            if process.returncode == 0:
                print(f"Copied command and output to clipboard ({name})")
                return True
        except FileNotFoundError:
            continue
        except Exception:
            pass

    print("No clipboard tool found. Install wl-copy, xclip, xsel, or termux-clipboard-set.", file=sys.stderr)
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: copy-previous-all.py <command>", file=sys.stderr)
        sys.exit(1)

    command = " ".join(sys.argv[1:])

    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = result.stdout.decode('utf-8', errors='replace')

        prefix = os.environ.get("CPA_PREFIX", "$ ")

        if output:
            if not output.endswith("\n"):
                output += "\n"
            combined = f"{prefix}{command}\n{output}"
        else:
            combined = f"{prefix}{command}\n"

        if not copy_to_clipboard(combined):
            sys.exit(1)

    except Exception as e:
        print(f"Failed to execute command: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
