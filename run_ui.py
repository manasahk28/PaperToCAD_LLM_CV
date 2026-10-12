#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy launcher forwarder.
Directs execution to the unified single entry point: main.py
"""
import sys
from pathlib import Path

if __name__ == "__main__":
    import main
    main.main()
