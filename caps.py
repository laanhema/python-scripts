#!/usr/bin/env python3

"""Renames one or multiple files to CAPITAL-CASE"""


import os
import re
import sys


def to_capital_case(name):
    words = re.split(r'[^a-zA-Z0-9]+', name)
    words = [w.upper() for w in words if w]
    return '-'.join(words)


def main():
    amount_of_args = len(sys.argv) - 1
    if (amount_of_args >= 1):
        for i in range(1, len(sys.argv)):
            file_name = sys.argv[i]
            name, ext = os.path.splitext(file_name)

            new_name = f"{to_capital_case(name)}{ext}"

            if new_name != file_name:
                    original_mode = os.stat(file_name).st_mode
                    os.rename(file_name, new_name)
                    os.chmod(new_name, original_mode)
                    print(f"Renamed: {file_name} -> {new_name}")
    else:
        print("Error: Give the script at least 1 file as an argument!")


if __name__ == "__main__":
    main()