#!/usr/bin/env python3
"""Make the cover image for an event's Substack recap, from a photo of the meetup.

    python3 scripts/recap_cover.py <event>                 # the event's cover photo
    python3 scripts/recap_cover.py <event> --photo 22      # another photo of its gallery
    python3 scripts/recap_cover.py <event> --style all     # every style, to compare

The photo is one the website already shows: the gallery's flagged cover (the
web-photos skill sets it), or --photo by its number there. The name and date
come from the event's event.json in the website.

The picture is 1456x1048, Substack's cover size. A shared link crops it to
about 1.9:1 from the middle, so every style keeps its words inside that band.

The file goes to <media>/<date>/cover/recap.jpg (recap-<style>.jpg with
--style all) and never into a repository.

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
FRAME = {"w": 1456, "h": 1048}
BLUE, MAGENTA, WHITE = "#1E2BE6", "#ED4BA0", "#F4F5FF"


def photo_bg(src: str, seed: int, artifacts: list[dict], **more) -> dict:
    return {"kind": "photo", "src": src, "position": "center", "color": BLUE, "tint": True, "cell": 16,
            "rough": 0.3, "seed": seed, "animate": False, "artifacts": artifacts, **more}


def text(s: str, x: float, y: float, size: float, **more) -> dict:
    return {"type": "text", "text": s, "x": x, "y": y, "size": size, "align": "left", **more}


def label(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The photo almost as taken, light corners, and one white label."""
    cs = [{"at": at, "solid": 0.08, "reach": 0.36} for at in ("top-left", "bottom-right")]
    return {"frame": FRAME, "background": photo_bg(src, seed, cs, tintOpacity=0.2, edge=MAGENTA), "layers": [
        text(f"{name} · {date}", 0.06, 0.8, 0.04, weight=700, color=BLUE, pill=True, pillColor=WHITE),
    ]}


def corner(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The photo as taken, with a blue corner of cells that holds the name and the date."""
    return {"frame": FRAME, "background": photo_bg(src, seed, [{"at": "bottom-left", "solid": 0.3, "reach": 0.52}], tintOpacity=0.15, edge=MAGENTA), "layers": [
        {"type": "rect", "x": 0, "y": 0.66, "w": 0.42, "h": 0.34, "color": BLUE, "opacity": 1, "radius": 0},  # the words always sit on solid blue
        text(name, 0.055, 0.765, 0.1),
        text(date, 0.057, 0.845, 0.036, weight=500),
    ]}


def strip(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The photo as taken, over a low blue band: the name on the left, the date on the right."""
    return {"frame": FRAME, "background": photo_bg(src, seed, [{"at": "bottom", "solid": 0.24, "reach": 0.36}], tintOpacity=0.15, edge=MAGENTA), "layers": [
        {"type": "rect", "x": 0, "y": 0.74, "w": 1, "h": 0.26, "color": BLUE, "opacity": 1, "radius": 0},
        text(name, 0.055, 0.815, 0.075),
        text(date, 0.945, 0.818, 0.036, align="right", weight=500),
    ]}


def blue(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The photo in the brand's blue, whole, with the name and the date low on a shadow."""
    cs = [{"at": at, "solid": 0.08, "reach": 0.36} for at in ("top-right", "bottom-left")]
    return {"frame": FRAME, "background": photo_bg(src, seed, cs, edge=MAGENTA), "layers": [
        {"type": "scrim", "shape": "bottom", "color": "#05071E", "opacity": 0.55},
        text(name, 0.055, 0.745, 0.1),
        text(date, 0.057, 0.825, 0.036, weight=500),
    ]}


def number(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The photo as taken, with the meetup's number large in a corner and the city and date beside it."""
    city = name.split(" #")[0]
    return {"frame": FRAME, "background": photo_bg(src, seed, [{"at": "bottom-right", "solid": 0.3, "reach": 0.5}], tintOpacity=0.15, edge=MAGENTA), "layers": [
        {"type": "rect", "x": 0.62, "y": 0.62, "w": 0.38, "h": 0.38, "color": BLUE, "opacity": 1, "radius": 0},
        text(f"#{n}", 0.945, 0.74, 0.19, align="right"),
        text(f"{city} · {date}", 0.945, 0.845, 0.034, align="right", weight=500),
    ]}


STYLES = {"label": label, "corner": corner, "strip": strip, "blue": blue, "number": number}
DEFAULT = "corner"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event", help="a date, a Luma slug or content/<date>")
    ap.add_argument("--photo", type=int, help="a photo of the event's gallery, by its number (default: the flagged cover)")
    ap.add_argument("--style", default=DEFAULT, choices=[*STYLES, "all"])
    args = ap.parse_args()

    event = common.event_dir(args.event)
    if not RENDER.is_file():
        die(f"no {RENDER}: update the website checkout")
    site = common.WEBSITE_CONTENT / event.name
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
    day = datetime.date.fromisoformat(event.name)
    n = int(facts.get("number") or 1)
    name, date = f"{facts.get('city', '')} #{n}".strip(), f"{day.day} {day:%B %Y}"

    out = common.media_dir(event) / "cover"
    out.mkdir(exist_ok=True)
    styles = list(STYLES) if args.style == "all" else [args.style]
    for style in styles:
        scene = STYLES[style](str(src), int(event.name.replace("-", "")), name, date, n)
        target = out / (f"recap-{style}.jpg" if args.style == "all" else "recap.jpg")
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(scene, f)
            f.flush()
            done = subprocess.run([sys.executable, str(RENDER), f.name, str(target)])
        if done.returncode:
            sys.exit(done.returncode)
        print(target)


if __name__ == "__main__":
    main()
