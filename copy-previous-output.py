#!/usr/bin/env python3

"""
Executes the provided command, captures its output, and copies it to the clipboard.

Usage:
    Add to ~/.bashrc:
        cpo() {
            local wrapper="/home/lauri/.local/bin/cpo"
            local py_script="${SCRIPT_PATH:-/home/lauri/github/python-scripts/copy-previous-output.py}"
            
            if [ ! -f "$wrapper" ] || [ ! -f "$py_script" ]; then
                echo "Error: Required scripts for 'cpo' are missing." >&2
                return 1
            fi

            local prev_cmd=$(fc -ln -2 -2 | sed 's/^[ \t]*//')
            "$wrapper" "$prev_cmd"
        }

    Then run any command, type cpo, and it re-runs the previous command and copies its output.
"""

import os
import subprocess
import sys

def copy_to_clipboard(text):
    """Copy text to clipboard using wl-copy, xclip, xsel, or termux-clipboard-set."""
    commands = [
        (['wl-copy'], 'wl-copy'),
        (['xclip', '-selection', 'clipboard'], 'xclip'),
        (['xsel', '--clipboard', '--input'], 'xsel'),
        (['termux-clipboard-set'], 'termux-clipboard-set'),
    ]

    for cmd, name in commands:
        try:
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            process.stdin.write(text.encode('utf-8'))
            process.stdin.close()
            process.wait()
            if process.returncode == 0:
                print(f"Copied output to clipboard ({name})")
                return True
        except FileNotFoundError:
            continue
        except Exception:
            pass

    print("No clipboard tool found. Install wl-copy, xclip, xsel, or termux-clipboard-set.", file=sys.stderr)
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: copy-previous-output.py <command>", file=sys.stderr)
        sys.exit(1)

    command = " ".join(sys.argv[1:])
    
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = result.stdout.decode('utf-8')
        
        if not output:
            print("Command produced no output.")
            return
            
        if not copy_to_clipboard(output):
            sys.exit(1)
            
    except Exception as e:
        print(f"Failed to execute command: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
