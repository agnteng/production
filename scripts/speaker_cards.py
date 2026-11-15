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
import pathlib
import subprocess
import sys

import common
from common import die

WEBSITE = common.ROOT.parent / "website"
RENDER = WEBSITE / "scripts" / "render_scene.py"
PUBLIC = WEBSITE / "apps" / "branding" / "public"
# Each preset by its number of speakers, with the layers of the first one's photo, name
# and role; a further speaker is three layers on, and the date line is layer 2
# (the website's `render_scene.py --presets` lists them).
PRESETS = {1: ("Speaker card", (0, 3, 4)), 2: ("Speaker pair", (3, 4, 5)), 3: ("Speaker trio", (3, 4, 5))}


def render(line: str, speakers: list[dict], stem) -> None:
    preset, first = PRESETS[len(speakers)]
    cmd = [sys.executable, str(RENDER), "--preset", preset, "--set", f"layers.2.text={line}"]
    for i, s in enumerate(speakers):
        photo, name, role = (n + 3 * i for n in first)
        # A photo already on the site is read from this checkout, so it need not be deployed yet.
        local = PUBLIC / s["photo"].lstrip("/")
        cmd += ["--set", f"layers.{photo}.src={local if local.is_file() else s['photo']}",
                "--set", f"layers.{name}.text={s['name']}", "--set", f"layers.{role}.text={s['title']}"]
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
    day = datetime.date.fromisoformat(event.name)
    line = args.line or f"{facts.get('city', '')} · {day.day} {day:%b}".removeprefix(" · ")
    out = common.media_dir(event) / "speakers"
    out.mkdir(exist_ok=True)

    if args.each or len(speakers) == 1:
        # A card is named after the speaker's photo, which the website already keeps
        # one per speaker as <first>-<last>.jpg.
        stems = [pathlib.PurePosixPath(s["photo"]).stem for s in speakers]
        if len(set(stems)) < len(stems):
            die("two speakers share a photo: give each their own in event.json")
        for s, stem in zip(speakers, stems):
            render(line, [s], out / stem)
    elif len(speakers) in PRESETS:
        render(line, speakers, out / "announcement")
    else:
        die(f"{len(speakers)} speakers do not fit on one picture: use --each")


if __name__ == "__main__":
    main()
