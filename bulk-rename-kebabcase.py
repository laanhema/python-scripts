#!/usr/bin/env python3

"""
This script renames all files in the current directory to kebab-case format.
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
        if filename.startswith('.'):
            continue
        if os.path.isfile(filename):
            name, ext = os.path.splitext(filename)

            new_name = to_kebab_case(name) + ext

            if new_name != filename:
                original_mode = os.stat(filename).st_mode
                os.rename(filename, new_name)
                os.chmod(new_name, original_mode)
                print(f"Renamed: {filename} -> {new_name}")


"""
when python runs a file directly, it sets "name" to "main"
in this script it means that the main function is invoked only if you launch this file directly,
not when you export its functions elsewhere:
"""
if __name__ == "__main__":
    main()
