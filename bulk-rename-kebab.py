#!/usr/bin/env python3

"""The script works by:
1. Converting files to kebab-case (lowercase with dashes)
2. Preserving file extensions
3. Skipping files that would not change (hidden files like .gitignore that don't match the word pattern)

The script path can be set via the SCRIPT_PATH environment variable, or will default to
/home/lauri/github/python-scripts/bulk-rename-kebab.py when running via wrapper script.
If run directly as python3 bulk-rename-kebab.py, it will use the local path.
"""

import os
import re


def to_kebab_case(name):
    words = re.split(r'[^a-zA-Z0-9]+', name)
    words = [w.lower() for w in words if w]
    return '-'.join(words)


def main():
    current_dir = os.getcwd()

    for filename in os.listdir(current_dir):
        if os.path.isfile(filename):
            name, ext = os.path.splitext(filename)

            new_name = to_kebab_case(name) + ext

            if new_name != filename:
                original_mode = os.stat(filename).st_mode
                os.rename(filename, new_name)
                os.chmod(new_name, original_mode)
                print(f"Renamed: {filename} -> {new_name}")


if __name__ == "__main__":
    main()
