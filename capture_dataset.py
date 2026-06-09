#!/usr/bin/env python3
"""
Dartboard dataset capture tool.
Run on the Pi over SSH. Uses both cameras to capture labeled frames.

Usage:
    python3 capture_dataset.py

Output:
    captures/
        clean/
            cam0_001.jpg
            cam1_001.jpg
            ...
        darts/
            T20/
                cam0_001.jpg
                cam1_001.jpg
            D16/
                ...
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

try:
    from picamera2 import Picamera2
except ImportError:
    print("ERROR: picamera2 not available. Are you on the Pi?")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path("captures")
RESOLUTION = (1920, 1080)

# ── Camera setup ──────────────────────────────────────────────────────────────

def init_cameras():
    cams = []
    for i in range(2):
        try:
            cam = Picamera2(i)
            config = cam.create_still_configuration(
                main={"size": RESOLUTION, "format": "RGB888"}
            )
            cam.configure(config)
            cam.start()
            time.sleep(1)  # warm-up
            cams.append(cam)
            print(f"  Camera {i} ready")
        except Exception as e:
            print(f"  Camera {i} failed: {e}")
    return cams


def capture(cams, out_dir: Path, prefix: str):
    """Capture one frame from each camera into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Find next available index in this folder
    existing = list(out_dir.glob(f"cam0_*.jpg"))
    idx = len(existing) + 1
    for i, cam in enumerate(cams):
        path = out_dir / f"cam{i}_{idx:03d}.jpg"
        cam.capture_file(str(path))
        print(f"    Saved {path}")


def parse_label(raw: str) -> str | None:
    """
    Normalize label input. Accepts:
      T20, t20, triple20, triple 20
      D16, d16, double16
      S5, s5, single5
      bull, Bull, BULL
      bullseye, dbull
      miss
    Returns a canonical label like T20, D16, S5, BULL, BULLSEYE, MISS
    or None if unrecognized.
    """
    s = raw.strip().lower().replace(" ", "")
    if not s:
        return None

    # Bull / bullseye
    if s in ("bull", "outerball", "25"):
        return "BULL"
    if s in ("bullseye", "dbull", "doublebull", "50"):
        return "BULLSEYE"
    if s == "miss":
        return "MISS"

    # Ring prefix shorthands
    ring_map = {
        "t": "T", "triple": "T",
        "d": "D", "double": "D",
        "s": "S", "single": "S",
    }

    for prefix, ring in ring_map.items():
        if s.startswith(prefix):
            seg_str = s[len(prefix):]
            if seg_str.isdigit():
                seg = int(seg_str)
                if 1 <= seg <= 20:
                    return f"{ring}{seg}"

    # Bare number → single
    if s.isdigit():
        seg = int(s)
        if 1 <= seg <= 20:
            return f"S{seg}"

    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n🎯 Dartboard Dataset Capture")
    print("=" * 40)

    print("\nInitializing cameras...")
    cams = init_cameras()
    if not cams:
        print("No cameras found. Exiting.")
        sys.exit(1)
    print(f"{len(cams)} camera(s) ready.\n")

    clean_dir = OUTPUT_DIR / "clean"
    darts_dir = OUTPUT_DIR / "darts"

    try:
        while True:
            print("\nOptions:")
            print("  [c]  Capture clean frame (no darts)")
            print("  [d]  Capture dart frame (will prompt for label)")
            print("  [q]  Quit")
            choice = input("\n> ").strip().lower()

            if choice == "q":
                break

            elif choice == "c":
                print("Capturing clean frame...")
                capture(cams, clean_dir, "clean")

            elif choice == "d":
                raw = input("Label (e.g. T20, D16, S5, bull, bullseye, miss): ").strip()
                label = parse_label(raw)
                if label is None:
                    print(f"  ⚠️  Couldn't parse '{raw}'. Try again (e.g. T20, D16, bull).")
                    continue
                print(f"  Label: {label} — capturing...")
                capture(cams, darts_dir / label, label)

            else:
                print("  Unrecognized option.")

    except KeyboardInterrupt:
        print("\n\nInterrupted.")

    finally:
        print("\nStopping cameras...")
        for cam in cams:
            try:
                cam.stop()
            except Exception:
                pass

    # Summary
    print("\n── Dataset Summary ──────────────────")
    if clean_dir.exists():
        n = len(list(clean_dir.glob("cam0_*.jpg")))
        print(f"  Clean frames : {n}")
    if darts_dir.exists():
        labels = sorted(darts_dir.iterdir())
        total = 0
        for label_dir in labels:
            n = len(list(label_dir.glob("cam0_*.jpg")))
            total += n
            print(f"  {label_dir.name:<12}: {n} frame(s)")
        print(f"  Total dart   : {total}")
    print()


if __name__ == "__main__":
    main()
