#!/usr/bin/env python3

"""The script works by:
1. Converting non-markdown files to snake_case (lowercase with dashes)
2. Converting markdown files to SNAKE_CASE (uppercase with dashes)
3. Preserving file extensions
4. Skipping files that would not change (hidden files like .gitignore that don't match the word pattern)"""

import os
import re


def to_kebab_case(name):
    words = re.split(r'[^a-zA-Z0-9]+', name)
    words = [w.lower() for w in words if w]
    return '-'.join(words)


def to_upper_kebab_case(name):
    words = re.split(r'[^a-zA-Z0-9]+', name)
    words = [w.upper() for w in words if w]
    return '-'.join(words)


def main():
    current_dir = os.getcwd()

    for filename in os.listdir(current_dir):
        if os.path.isfile(filename):
            name, ext = os.path.splitext(filename)

            if ext.lower() == '.md':
                new_name = to_upper_kebab_case(name) + ext
            else:
                new_name = to_kebab_case(name) + ext

            if new_name != filename:
                os.rename(filename, new_name)
                print(f"Renamed: {filename} -> {new_name}")


if __name__ == "__main__":
    main()
