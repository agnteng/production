#!/usr/bin/env python3
"""Make an event's speaker announcement: a JPG, a GIF and an MP4.

    python3 scripts/speaker_cards.py <event>                 # every speaker, on one picture
    python3 scripts/speaker_cards.py <event> --each          # one portrait card per speaker
    python3 scripts/speaker_cards.py <event> --line "Lisbon · tonight"

Names, roles and photos come from the event's event.json in the website, so
they are the ones the site shows: fix a name or add a photo there (the
web-photos skill), then run this again. One speaker makes a portrait card
(1080x1350); two or three stand side by side (1920x1080).

The files go to <media>/<date>/speakers/: announcement.jpg, .gif and .mp4, or
<first>-<last>.* with --each. They are never written into a repository.

The picture is the brand's animation builder's: this fills one of its speaker
presets through the website's scripts/render_scene.py, which needs Chrome,
ffmpeg and the network.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys

import common
from common import die

WEBSITE = common.ROOT.parent / "website"
RENDER = WEBSITE / "scripts" / "render_scene.py"
PUBLIC = WEBSITE / "apps" / "branding" / "public"
# Where each preset keeps a speaker's photo, name and role, and its date line
# (`render_scene.py --presets` lists the layers).
CARD = {"preset": "Speaker card", "line": 2, "first": (0, 3, 4), "step": 0}
ROW = {"preset": {2: "Speaker pair", 3: "Speaker trio"}, "line": 2, "first": (3, 4, 5), "step": 3}


def render(layout: dict, line: str, speakers: list[dict], stem) -> None:
    preset = layout["preset"] if isinstance(layout["preset"], str) else layout["preset"][len(speakers)]
    sets = [f"layers.{layout['line']}.text={line}"]
    for i, s in enumerate(speakers):
        photo, name, role = (n + i * layout["step"] for n in layout["first"])
        # A photo already on the site is read from this checkout, so it need not be deployed yet.
        local = PUBLIC / s["photo"].lstrip("/")
        sets += [f"layers.{photo}.src={local if local.is_file() else s['photo']}",
                 f"layers.{name}.text={s['name']}", f"layers.{role}.text={s['title']}"]
    cmd = [sys.executable, str(RENDER), "--preset", preset]
    for s in sets:
        cmd += ["--set", s]
    done = subprocess.run([*cmd, *(f"{stem}.{ext}" for ext in ("jpg", "gif", "mp4"))])
    if done.returncode:
        sys.exit(done.returncode)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event", help="a date, a Luma slug or content/<date>")
    ap.add_argument("--each", action="store_true", help="one portrait card per speaker instead of one picture")
    ap.add_argument("--line", help="the line beside the logo (default: the city and the date)")
    args = ap.parse_args()

    event = common.event_dir(args.event)
    if not RENDER.is_file():
        die(f"no {RENDER}: update the website checkout")
    facts = json.loads((common.WEBSITE_CONTENT / event.name / "event.json").read_text())
    speakers = facts.get("speakers") or []
    if not speakers:
        die(f"{event.name}: event.json has no speakers yet; add them in the website")
    for s in speakers:
        if not all(s.get(k) for k in ("name", "title", "photo")):
            die(f"{s.get('name') or 'a speaker'} needs a name, a title and a photo in event.json (the web-photos skill adds a photo)")
    day = datetime.date.fromisoformat(facts["date"])
    line = args.line or f"{facts['city']} · {day.day} {day:%b}"
    out = common.media_dir(event) / "speakers"
    out.mkdir(exist_ok=True)

    if args.each or len(speakers) == 1:
        for s in speakers:
            render(CARD, line, [s], out / re.sub(r"[^a-z0-9]+", "-", s["name"].lower()).strip("-"))
    elif len(speakers) in ROW["preset"]:
        render(ROW, line, speakers, out / "announcement")
    else:
        die(f"{len(speakers)} speakers do not fit on one picture: use --each")


if __name__ == "__main__":
    main()
