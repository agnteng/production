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
BLUE, VIOLET, MAGENTA, WHITE = "#1E2BE6", "#7C4DF5", "#ED4BA0", "#F4F5FF"
# The colour an event takes in the `colour` style, by its number.
COLOURS = [BLUE, VIOLET, MAGENTA]  # the ones white words read on


def photo_bg(src: str, seed: int, artifacts: list[dict], **more) -> dict:
    return {"kind": "photo", "src": src, "position": "center", "color": BLUE, "tint": True, "cell": 16,
            "rough": 0.3, "seed": seed, "animate": False, "artifacts": artifacts, **more}


def text(s: str, x: float, y: float, size: float, **more) -> dict:
    return {"type": "text", "text": s, "x": x, "y": y, "size": size, "align": "left", **more}


def edge(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The site's event header: the photo in blue, dissolving into a blue block that holds the words."""
    return {"frame": FRAME, "background": photo_bg(src, seed, [{"at": "left", "solid": 0.42, "reach": 0.7}]), "layers": [
        {"type": "logo", "form": "line", "anchor": "top-left", "scale": 0.3, "dx": 0.055, "dy": 0.2},
        text(name, 0.055, 0.5, 0.13),
        text(date, 0.057, 0.62, 0.04, weight=500),
    ]}


def corners(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The site's share image: two corners eaten away, the logo and the event in the middle."""
    return {"frame": FRAME, "background": photo_bg(src, seed, [{"at": "bottom-left", "solid": 0.3, "reach": 0.85}, {"at": "top-right", "solid": 0.3, "reach": 0.85}]), "layers": [
        {"type": "scrim", "shape": "vignette", "color": BLUE, "opacity": 0.6},
        {"type": "logo", "form": "lockup", "anchor": "center", "scale": 0.42, "dy": -0.07},
        text(f"{name} · {date}", 0.5, 0.63, 0.042, align="center", weight=600),
    ]}


def natural(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The photo nearly in its own colours, under a blue block that holds the words, with a few magenta cells."""
    return {"frame": FRAME, "background": photo_bg(src, seed, [{"at": "top", "solid": 0.3, "reach": 0.46}], tintOpacity=0.25, edge=MAGENTA), "layers": [
        {"type": "logo", "form": "mark", "anchor": "top-right", "scale": 0.075, "dx": -0.055, "dy": 0.19},
        text(name, 0.055, 0.215, 0.12),
        text(date, 0.057, 0.305, 0.038, weight=500),
    ]}


def colour(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """Each event in its own brand colour, with blue cells at the edge."""
    c = COLOURS[(n - 1) % len(COLOURS)]
    return {"frame": FRAME, "background": photo_bg(src, seed, [{"at": "left", "solid": 0.42, "reach": 0.7}], color=c, edge=BLUE if c != BLUE else MAGENTA), "layers": [
        {"type": "logo", "form": "line", "anchor": "top-left", "scale": 0.3, "dx": 0.055, "dy": 0.2},
        text(name, 0.055, 0.5, 0.13),
        text(date, 0.057, 0.62, 0.04, weight=500),
    ]}


def frame(src: str, seed: int, name: str, date: str, n: int) -> dict:
    """The photo almost untouched: light corners, the logo, and one label."""
    cs = [{"at": at, "solid": 0.1, "reach": 0.42} for at in ("top-left", "bottom-right")]
    return {"frame": FRAME, "background": photo_bg(src, seed, cs, tintOpacity=0.45, edge=MAGENTA), "layers": [
        {"type": "logo", "form": "line", "anchor": "top-left", "scale": 0.28, "dx": 0.05, "dy": 0.19},
        text(f"{name} · {date}", 0.065, 0.8, 0.036, weight=700, color=BLUE, pill=True, pillColor=WHITE),
    ]}


STYLES = {"edge": edge, "corners": corners, "natural": natural, "colour": colour, "frame": frame}
DEFAULT = "edge"


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
