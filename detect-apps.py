#!/usr/bin/env python3

"""
List GUI applications from desktop files and identify GTK or Qt-based ones.
"""

import os
import re
import subprocess


DESKTOP_DIRECTORIES = [
    "/usr/share/applications",
    os.path.expanduser("~/.local/share/applications"),
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
]


def read_file_text(path):
    with open(path, "r", errors="ignore") as file_handle:
        return file_handle.read()


def iter_desktop_files():
    for directory in DESKTOP_DIRECTORIES:
        if os.path.exists(directory):
            for file_name in os.listdir(directory):
                if file_name.endswith(".desktop"):
                    yield os.path.join(directory, file_name)


def parse_desktop_entry(path):
    content = read_file_text(path)
    exec_match = re.search(r"^Exec=(.+)$", content, re.MULTILINE)
    if not exec_match:
        return None

    exec_line = exec_match.group(1).strip()
    tokens = exec_line.split()
    if tokens and tokens[0].endswith("flatpak") and len(tokens) > 1 and tokens[1] == "run":
        app_id = None
        for token in tokens[2:]:
            if token.startswith("--"):
                continue
            app_id = token
            break
        if not app_id:
            return None
        return {
            "display_name": app_id,
            "app_id": app_id,
            "is_flatpak": True,
        }

    exec_token = tokens[0]
    exec_name = os.path.basename(exec_token)
    return {
        "display_name": exec_name,
        "app_id": None,
        "is_flatpak": False,
    }


def get_gui_apps():
    """Finds GUI applications from desktop files, including Flatpak apps."""
    apps = []
    seen = set()

    for desktop_file in iter_desktop_files():
        entry = parse_desktop_entry(desktop_file)
        if not entry:
            continue

        key = (entry["display_name"], entry["app_id"], entry["is_flatpak"])
        if key not in seen:
            seen.add(key)
            apps.append(entry)

    return sorted(apps, key=lambda item: item["display_name"].lower())


def detect_flatpak_toolkit(app_id):
    """Uses flatpak metadata and the sandbox binary to check if an app is GTK or Qt."""
    try:
        metadata = subprocess.check_output(
            ["flatpak", "info", "-m", app_id],
            stderr=subprocess.DEVNULL,
        ).decode()

        runtime_match = re.search(r"^runtime=([^\n]+)", metadata, re.MULTILINE)
        if runtime_match:
            runtime = runtime_match.group(1)
            if runtime.startswith("org.kde.Platform"):
                return "Qt"

        command_match = re.search(r"^command=([^\n]+)", metadata, re.MULTILINE)
        if command_match:
            command = command_match.group(1).strip()
            if command:
                libs = subprocess.check_output(
                    [
                        "flatpak",
                        "run",
                        "--command=sh",
                        app_id,
                        "-c",
                        'binary=$(command -v "$1" 2>/dev/null); [ -n "$binary" ] && ldd "$binary" 2>/dev/null || true',
                        "sh",
                        command,
                    ],
                    stderr=subprocess.DEVNULL,
                ).decode()

                if "libQt" in libs or "Qt5" in libs or "Qt6" in libs:
                    return "Qt"
                if "libgtk" in libs or "libadwaita" in libs:
                    return "GTK"

        if runtime_match:
            runtime = runtime_match.group(1)
            if runtime.startswith("org.gnome.Platform"):
                return "GTK"

    except Exception:
        pass

    return "Other/Unknown"


def detect_toolkit(app_name, is_flatpak=False, app_id=None):
    """Uses ldd to check if a native app links to GTK or Qt libraries."""
    if is_flatpak and app_id:
        return detect_flatpak_toolkit(app_id)

    try:
        full_path = subprocess.check_output(
            ["which", app_name],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        libs = subprocess.check_output(["ldd", full_path], stderr=subprocess.DEVNULL).decode()

        if "libQt" in libs:
            return "Qt"
        if "libgtk" in libs:
            return "GTK"
        return "Other/Unknown"
    except Exception:
        return None


print(f"{'Application':<35} | {'Toolkit':<10}")
print("-" * 50)

for app in get_gui_apps():
    toolkit = detect_toolkit(app["display_name"], app["is_flatpak"], app["app_id"])
    if toolkit in ["GTK", "Qt"]:
        print(f"{app['display_name']:<35} | {toolkit:<10}")
