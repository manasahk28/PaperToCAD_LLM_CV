#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to download and unpack model weights from Hugging Face:
https://huggingface.co/why0722/hcd-circuit-weights
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_DIR = REPO_ROOT / "weights"

BASE_URL = "https://huggingface.co/why0722/hcd-circuit-weights/resolve/main"

FILES = [
    ("weights_yolo_parseq.zip", 196),
    ("weights_hawp.zip", 343),
    ("weights_vitpose.zip", 2187),
    ("weights_dinov2.zip", 3232),
]


def download_file(url: str, dest_path: Path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    
    print(f"Downloading {dest_path.name} from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(temp_path, "wb") as f:
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB
        last_percent = -1
        
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = int(downloaded * 100 / total_size)
                if percent != last_percent and percent % 10 == 0:
                    print(f"  {percent}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
                    last_percent = percent
                    
    if temp_path.exists():
        if dest_path.exists():
            dest_path.unlink()
        temp_path.rename(dest_path)
    print(f"Downloaded {dest_path.name} successfully.")


def extract_zip(zip_path: Path, target_dir: Path):
    print(f"Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        # Check if zip contains top-level 'weights/' folder
        has_weights_root = any(name.startswith("weights/") for name in z.namelist())
        extract_to = REPO_ROOT if has_weights_root else WEIGHTS_DIR
        z.extractall(extract_to)
    print(f"Extraction complete for {zip_path.name}.")
    try:
        zip_path.unlink()
        print(f"Removed temporary archive: {zip_path.name}")
    except Exception as e:
        print(f"Note: could not delete {zip_path.name}: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download model weights for Hand-Drawn Circuit Recognition")
    parser.add_argument("--all", action="store_true", help="Download all weight archives")
    parser.add_argument("--subset", choices=["yolo_parseq", "hawp", "vitpose", "dinov2"], nargs="+",
                        help="Specific subsets to download")
    args = parser.parse_args()

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    
    selected = []
    if args.subset:
        subset_map = {
            "yolo_parseq": "weights_yolo_parseq.zip",
            "hawp": "weights_hawp.zip",
            "vitpose": "weights_vitpose.zip",
            "dinov2": "weights_dinov2.zip",
        }
        for s in args.subset:
            fname = subset_map[s]
            size = next(sz for (fn, sz) in FILES if fn == fname)
            selected.append((fname, size))
    else:
        selected = FILES

    print(f"Target directory: {WEIGHTS_DIR}")
    print(f"Selected archives to download ({len(selected)}):")
    for fname, size_mb in selected:
        print(f" - {fname} (~{size_mb} MB)")

    for fname, _ in selected:
        zip_path = WEIGHTS_DIR / fname
        url = f"{BASE_URL}/{fname}"
        download_file(url, zip_path)
        extract_zip(zip_path, WEIGHTS_DIR)

    print("\nAll selected weights are ready in:")
    print(f"  {WEIGHTS_DIR}")


if __name__ == "__main__":
    main()
