#!/usr/bin/env python3
"""Publish an event's gallery on the website (org ADR 0008).

    python3 scripts/event_photos.py <event> --photo FILE "alt text" [--photo FILE "alt" …]

Each FILE (an original in the media folder) becomes
../website/content/<date>/photos/NN.jpg, long edge at most 1600px, every
metadata field stripped (phone photos carry GPS), listed with its alt text in
photos.json. Re-running replaces the gallery. HEIC needs sips (macOS); ffmpeg
does the rest and turns photos upright from their EXIF orientation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import WEBSITE_CONTENT, die, event_dir

LONG_EDGE = 1600


def web_copy(src: Path, dest: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        if src.suffix.lower() in (".heic", ".heif"):
            if not shutil.which("sips"):
                die(f"{src.name}: HEIC needs sips (macOS); convert it to JPEG first")
            jpg = Path(tmp) / "in.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(jpg)],
                           check=True, capture_output=True)
            src, name = jpg, src.name
        else:
            name = src.name
        scale = f"scale='if(gt(iw,ih),min({LONG_EDGE},iw),-2)':'if(gt(iw,ih),-2,min({LONG_EDGE},ih))'"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", scale,
                            "-map_metadata", "-1", "-q:v", "4", str(dest)], capture_output=True, text=True)
        if r.returncode:
            die(f"{name}: {r.stderr.strip()[-300:]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event")
    ap.add_argument("--photo", nargs=2, action="append", metavar=("FILE", "ALT"), required=True)
    args = ap.parse_args()
    event = event_dir(args.event)
    for file, alt in args.photo:
        if not Path(file).is_file():
            die(f"no such photo: {file}")
        if not alt.strip():
            die(f"{Path(file).name}: needs alt text")
    site = WEBSITE_CONTENT / event.name
    # Build the new gallery beside the old one, then swap, so a failure leaves the old intact.
    with tempfile.TemporaryDirectory(dir=site) as tmp:
        listing = []
        for n, (file, alt) in enumerate(args.photo, 1):
            dest = Path(tmp) / f"{n:02d}.jpg"
            web_copy(Path(file), dest)
            listing.append({"file": dest.name, "alt": alt.strip()})
            print(f"  photos/{dest.name}  {dest.stat().st_size // 1024} KB  ← {Path(file).name}")
        shutil.rmtree(site / "photos", ignore_errors=True)
        shutil.copytree(tmp, site / "photos")
    (site / "photos.json").write_text(json.dumps(listing, indent=2, ensure_ascii=False) + "\n")
    print(f"{event.name}: {len(listing)} photos")


if __name__ == "__main__":
    main()
