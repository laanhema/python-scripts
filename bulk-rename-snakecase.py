#!/usr/bin/env python3

"""
This script renames all files in the current directory to snake_case format, ignoring itself.
"""

import os
import re

def to_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return re.sub(r'[\s\-]+', '_', s2)

def main():
    cwd = os.getcwd()
    for filename in os.listdir(cwd):
        if os.path.isfile(filename) and filename != os.path.basename(__file__):
            parts = filename.split('.')
            snake_parts = [to_snake_case(p) for p in parts]
            new_name = '.'.join(snake_parts)
            
            if new_name != filename:
                os.rename(filename, new_name)
                print(f"Renamed: {filename} -> {new_name}")

if __name__ == "__main__":
    main()
