#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to package the add-on into a valid Kodi installable ZIP file.
"""

import os
import zipfile

ADDON_ID = "plugin.video.filma24"
VERSION = "1.0.0"
OUTPUT_ZIP = f"{ADDON_ID}-{VERSION}.zip"

# Files and directories to include in package
INCLUDE_PATTERNS = [
    "addon.xml",
    "addon.py",
    "resources/settings.xml",
    "resources/icon.png",
    "resources/fanart.jpg",
    "resources/lib/__init__.py",
    "resources/lib/scraper.py",
]

EXCLUDE_EXTS = (".pyc", ".pyo", ".DS_Store", ".git")


def build_addon_zip():
    print(f"Packaging {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk("."):
            for file in files:
                filepath = os.path.relpath(os.path.join(root, file), ".")
                if filepath.startswith((".", "build", "__pycache__")) or filepath == OUTPUT_ZIP or filepath == "build_zip.py":
                    continue
                if any(filepath.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                if "__pycache__" in filepath:
                    continue

                archive_path = os.path.join(ADDON_ID, filepath)
                print(f"  Adding: {filepath} -> {archive_path}")
                zf.write(filepath, archive_path)

    print(f"\n[SUCCESS] Add-on package created: {OUTPUT_ZIP}")


if __name__ == "__main__":
    build_addon_zip()
