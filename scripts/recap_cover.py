#!/usr/bin/env python3
"""Make the cover image for an event's Substack recap, from a photo of the meetup.

    python3 scripts/recap_cover.py <event>                 # the event's cover photo
    python3 scripts/recap_cover.py <event> --photo 22      # another photo of its gallery

The photo is one the website already shows: the gallery's flagged cover (the
web-photos skill sets it), or --photo by its number there. The name and date
come from the event's event.json in the website.

The picture is the whole photo in the brand's blue, with a few cells in two
corners and the event's name and date low on the left: no logo, and the people
stay in view. It is 1920x1080; a shared link crops a little off the top and
bottom, which the words stay clear of.

The file goes to <media>/<date>/cover/recap.jpg and never into a repository.

The picture is the brand's animation builder's: this writes a scene and hands
it to the website's scripts/render_scene.py, which needs Chrome and the network.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import tempfile

import common
from common import die

WEBSITE = common.ROOT.parent / "website"
RENDER = WEBSITE / "scripts" / "render_scene.py"
BLUE, MAGENTA, NAVY = "#1E2BE6", "#ED4BA0", "#05071E"


def scene(src: str, seed: int, name: str, date: str) -> dict:
    """The builder's scene for a cover (the website's scene.ts documents every field)."""
    corners = [{"at": at, "solid": 0.08, "reach": 0.36} for at in ("top-right", "bottom-left")]
    return {
        "frame": {"w": 1920, "h": 1080},
        # Each event's own pattern of cells, a few of them magenta.
        "background": {"kind": "photo", "src": src, "position": "center", "color": BLUE, "edge": MAGENTA, "tint": True,
                       "cell": 20, "rough": 0.3, "seed": seed, "animate": False, "artifacts": corners},
        "layers": [
            {"type": "scrim", "shape": "bottom", "color": NAVY, "opacity": 0.55},  # the words read on any photo
            {"type": "text", "text": name, "x": 0.05, "y": 0.755, "size": 0.125, "align": "left"},
            {"type": "text", "text": date, "x": 0.052, "y": 0.865, "size": 0.044, "align": "left", "weight": 500},
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event", help="a date, a Luma slug or content/<date>")
    ap.add_argument("--photo", type=int, help="a photo of the event's gallery, by its number (default: the flagged cover)")
    args = ap.parse_args()

    event = common.event_dir(args.event)
    if not RENDER.is_file():
        die(f"no {RENDER}: update the website checkout")
    site = common.WEBSITE_CONTENT / event.name
    if not (site / "event.json").is_file():
        die(f"no {site / 'event.json'}: the website has no such event")
    facts = json.loads((site / "event.json").read_text())
    gallery = json.loads((site / "photos.json").read_text()) if (site / "photos.json").is_file() else []
    if args.photo:
        file = f"{args.photo:02d}.jpg"
    else:
        file = next((p["file"] for p in gallery if p.get("cover")), None)
        if not file:
            die(f"{event.name}: no photo is flagged cover in the gallery; flag one (the web-photos skill) or pass --photo")
    src = site / "photos" / file
    if not src.is_file():
        die(f"no {src}: the gallery has {len(gallery)} photos")
    if not facts.get("city") or not facts.get("number"):
        die(f"{event.name}: event.json needs a city and a number")
    day = datetime.date.fromisoformat(event.name)
    name, date = f"{facts['city']} #{facts['number']}", f"{day.day} {day:%B %Y}"

    out = common.media_dir(event) / "cover"
    out.mkdir(exist_ok=True)
    target = out / "recap.jpg"
    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(scene(str(src), int(event.name.replace("-", "")), name, date), f)
        f.flush()
        done = subprocess.run([sys.executable, str(RENDER), f.name, str(target)])
    if done.returncode:
        sys.exit(done.returncode)
    print(target)


if __name__ == "__main__":
    main()
