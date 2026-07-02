#!/usr/bin/env python3

"""
Copies the last executed terminal command to clipboard for easy reuse.
"""

import os
import subprocess
import sys


def copy_to_clipboard(text):
    """Copy text to clipboard using xclip, xsel, or termux-clipboard-set."""
    temp_path = "/tmp/cpo_clipboard.txt"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(text)

    commands = [
        (['xclip', '-selection', 'clipboard'], 'xclip'),
        (['xsel', '--clipboard', '--input'], 'xsel'),
        (['termux-clipboard-set'], 'termux-clipboard-set'),
    ]

    for cmd, name in commands:
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                process = subprocess.Popen(cmd, stdin=f)
                process.wait()
            if process.returncode == 0:
                print(f"Copied to clipboard ({name}): {text}")
                return True
        except FileNotFoundError:
            continue
        except Exception:
            pass

    print("No clipboard tool found. Install xclip, xsel, or termux-clipboard-set.", file=sys.stderr)
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: previous-command-clipboard.py <command>", file=sys.stderr)
        sys.exit(1)

    command = " ".join(sys.argv[1:])

    if not copy_to_clipboard(command):
        sys.exit(1)


if __name__ == "__main__":
    main()
