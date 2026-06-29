#!/usr/bin/env python3

"""Copy the last executed terminal command to clipboard for easy reuse.

Usage:
    Add to ~/.bashrc:
        lc() {
            local wrapper="/home/lauri/.local/bin/lc"
            local py_script="${SCRIPT_PATH:-/home/lauri/github/python-scripts/previous-command-clipboard.py}"
            
            if [ ! -f "$wrapper" ] || [ ! -f "$py_script" ]; then
                echo "Error: Required scripts for 'lc' are missing." >&2
                return 1
            fi

            local prev_cmd=$(fc -ln -2 -2 | sed 's/^[ \t]*//')
            "$wrapper" "$prev_cmd"
        }

    Then run any command, type lc, and it copies the previous command.
"""

import os
import subprocess
import sys


def copy_to_clipboard(text):
    """Copy text to clipboard using xclip, xsel, or termux-clipboard-set."""
    commands = [
        (['xclip', '-selection', 'clipboard'], 'xclip'),
        (['xsel', '--clipboard', '--input'], 'xsel'),
        (['termux-clipboard-set'], 'termux-clipboard-set'),
    ]

    for cmd, name in commands:
        try:
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            process.stdin.write(text.encode())
            process.stdin.close()
            process.wait()
            if process.returncode == 0:
                print(f"Copied to clipboard ({name}): {text}")
                return True
        except FileNotFoundError:
            continue
        except Exception:
            try:
                process.terminate()
                process.wait()
            except Exception:
                pass
            continue

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
