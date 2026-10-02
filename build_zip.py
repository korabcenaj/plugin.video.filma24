#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to package the add-on into a valid Kodi installable ZIP file.
"""

import os
import zipfile

import re

ADDON_ID = "plugin.video.filma24"

def get_addon_version():
    with open("addon.xml", "r", encoding="utf-8") as f:
        m = re.search(r'id=["\']plugin\.video\.filma24["\'][^>]+version=["\']([^"\']+)["\']', f.read())
        return m.group(1) if m else "1.0.0"

VERSION = get_addon_version()
OUTPUT_ZIP = f"{ADDON_ID}-{VERSION}.zip"

EXCLUDE_EXTS = (".pyc", ".pyo", ".DS_Store", ".git", ".zip", ".html")


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
