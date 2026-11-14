# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==11.3.0", "pillow-heif==1.1.0"]
# ///
"""Publish an event's gallery on the website (org ADR 0008).

    uv run scripts/event_photos.py <event> --list content/<date>/gallery.tsv
    uv run scripts/event_photos.py <event> --photo FILE "alt" [--plain FILE "alt"] …

Each FILE (an original in the media folder) goes through photos.web and
becomes ../website/content/<date>/photos/NN.jpg, in the order given, listed
with its alt text in photos.json, in the order the photos were taken (EXIF;
photos without a capture time go last, in the order given). --plain skips the
enhancement (slides, screens). Re-running replaces the gallery. A --list file has one photo per
line, `FILE<TAB>alt[<TAB>plain]`, FILE relative to the event's media folder;
lines starting with # are comments.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import photos
from common import WEBSITE_CONTENT, die, event_dir, media_dir


class Add(argparse.Action):
    """--photo and --plain append to one ordered list, so the order given is the gallery's."""

    def __call__(self, parser, ns, values, option_string=None):
        ns.photos = (ns.photos or []) + [(*values, option_string == "--photo")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event")
    for flag in ("--photo", "--plain"):
        ap.add_argument(flag, nargs=2, action=Add, dest="photos", metavar=("FILE", "ALT"))
    ap.add_argument("--list", type=Path, help="a gallery.tsv: FILE<TAB>alt[<TAB>plain] per line")
    args = ap.parse_args()
    event = event_dir(args.event)
    if args.list:
        media = media_dir(event)
        for line in args.list.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                file, alt, *flag = line.split("\t")
                args.photos = (args.photos or []) + [(str(media / file), alt, flag != ["plain"])]
    if not args.photos:
        die("give --list FILE or at least one --photo FILE ALT")
    args.photos.sort(key=lambda p: (photos.taken(Path(p[0])) or "9999",))
    for file, alt, _ in args.photos:
        if not Path(file).is_file():
            die(f"no such photo: {file}")
        if not alt.strip():
            die(f"{Path(file).name}: needs alt text")
    site = WEBSITE_CONTENT / event.name
    # Build the new gallery beside the old one, then swap, so a failure leaves the old intact.
    with tempfile.TemporaryDirectory(dir=site) as tmp:
        listing = []
        for n, (file, alt, enhance) in enumerate(args.photos, 1):
            dest = Path(tmp) / f"{n:02d}.jpg"
            photos.web(Path(file), dest, do_enhance=enhance)
            listing.append({"file": dest.name, "alt": alt.strip()})
            print(f"  photos/{dest.name}  {dest.stat().st_size // 1024} KB  ← {Path(file).name}")
        shutil.rmtree(site / "photos", ignore_errors=True)
        shutil.copytree(tmp, site / "photos")
    (site / "photos.json").write_text(json.dumps(listing, indent=2, ensure_ascii=False) + "\n")
    print(f"{event.name}: {len(listing)} photos")


if __name__ == "__main__":
    main()
