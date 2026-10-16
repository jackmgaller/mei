#!/usr/bin/env python3
"""Draws the tank tops through Mei at the game's camera, with its costs: the great tank's
capture.py (../aq_great/capture.py, which says how) for this room.

    python3 carts/afterhours/rooms/aq_tops/capture.py [--build-dir build-ah-R2] [--verify]
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'aq_great'))
import capture  # noqa: E402

if __name__ == '__main__':
    capture.main('aq_tops')
