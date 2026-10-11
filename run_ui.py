#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convenience launcher for the PaperToCAD Studio Web UI.
Usage:
    python run_ui.py
"""

import sys
import webbrowser
from pathlib import Path

# Ensure UTF-8 stdout on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "ui"))

import uvicorn
from server import app

if __name__ == "__main__":
    port = 8000
    url = f"http://localhost:{port}"
    print(f"\n{'='*64}")
    print(f"[START] Launching PaperToCAD Studio Web Interface")
    print(f"[URL] Access the UI at: {url}")
    print(f"{'='*64}\n")

    # Open web browser automatically
    try:
        webbrowser.open(url)
    except Exception:
        pass

    uvicorn.run(app, host="127.0.0.1", port=port)

