"""Shared by the scripts: credentials, timecodes, the event folder.

Imported as a sibling (`import common`); every script here is run as
`python3 scripts/<name>.py`, which puts this directory on sys.path.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.parse
from typing import NoReturn

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Event identity lives in the website repository, checked out next to this one.
WEBSITE_CONTENT = ROOT.parent / "website" / "content"
# Luma slugs are ae-<city>-<n>: luma.com/ae-lisbon-6 is Lisbon meetup #6.
LUMA_SLUG = re.compile(r"ae-([a-z]+(?:-[a-z]+)*)-(\d+)")


def _media_root() -> pathlib.Path | None:
    """Camera files, audio, frames, chunk transcripts and clips live outside
    the repository; content/<date>/ holds only what gets published.

    AGNTENG_MEDIA, else the media/ of the workspace this checkout sits in,
    else None.
    """
    if os.environ.get("AGNTENG_MEDIA"):
        return pathlib.Path(os.environ["AGNTENG_MEDIA"]).expanduser()
    if ROOT.parent.name == "repos" and (ROOT.parent.parent / "media").is_dir():
        return ROOT.parent.parent / "media"
    return None


MEDIA_ROOT = _media_root()


def die(msg: str) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def secret(name: str, required: bool = True) -> str:
    """A credential from the environment, else from the repo-root .env.

    The environment comes first so a secrets runner wrapping `python3 …` works unchanged.
    Never printed and never taken on the command line: a key in argv ends up in
    shell history and in every process listing.
    """
    v = os.environ.get(name, "").strip()
    if v:
        return v
    for p in (pathlib.Path(".env"), ROOT / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line.startswith(f"{name}="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    if not required:
        return ""
    die(f"{name} is not set (environment or .env at the repo root)")


def openrouter_key() -> str:
    return secret("OPENROUTER_API_KEY")


def hm(seconds: float) -> str:
    """M:SS, or H:MM:SS past an hour: what a person reads off a transcript."""
    h, rem = divmod(max(0, int(seconds)), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def hms(seconds: float) -> str:
    """HH:MM:SS.mmm, for ffmpeg."""
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def parse_ts(value: str | float) -> float:
    """Seconds from 93, 1:33, 01:33.5 or 00:01:33.500."""
    value = str(value).strip()
    if not value:
        die("empty timecode")
    total = 0.0
    try:
        for part in value.split(":"):
            total = total * 60 + float(part)
    except ValueError:
        die(f"bad timecode: {value!r}")
    return total


def parse_span(spec: str) -> tuple[float, float]:
    """'8:36-21:28' → (516.0, 1288.0)."""
    a, sep, b = spec.partition("-")
    if not sep:
        die(f"span needs START-END, got {spec!r}")
    start, end = parse_ts(a), parse_ts(b)
    if end <= start:
        die(f"span {spec}: end must be after start")
    return start, end


def slug_of(url: str) -> str:
    """The Luma slug of `https://luma.com/<slug>?…`, `luma.com/<slug>` or `<slug>`."""
    return urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]


def date_for_slug(slug: str) -> str | None:
    """The date of the website event whose Luma URL has this slug."""
    for f in sorted(WEBSITE_CONTENT.glob("*/event.json")):
        try:
            luma = json.loads(f.read_text()).get("luma")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(luma, dict) and slug_of(str(luma.get("url", ""))) == slug:
            return f.parent.name
    return None


def event_dir(arg: str) -> pathlib.Path:
    """content/<date>/ from `content/<date>`, `<date>` or a Luma slug."""
    d = pathlib.Path(arg)
    if d.is_dir():
        return d
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", d.name):
        slug = slug_of(arg)
        date = date_for_slug(slug)
        if date is None:
            die(f"no website event.json has luma.com/{slug}: run scripts/luma_event.py {slug} --write")
        d = pathlib.Path(date)
    alt = ROOT / "content" / d.name
    if alt.is_dir():
        return alt
    # A new event: the website already has its event.json.
    if (WEBSITE_CONTENT / d.name / "event.json").is_file():
        alt.mkdir(parents=True)
        return alt
    die(f"not an event: {arg} (no content/{d.name}/ here or event.json in ../website/)")


def media_dir(event: pathlib.Path) -> pathlib.Path:
    """<media>/<date>/: raw/ (camera files), work/ (scratch) and the clips."""
    if MEDIA_ROOT is None:
        die("no media folder: set AGNTENG_MEDIA, or run `mise run bootstrap` in the workspace")
    d = MEDIA_ROOT / event.name
    d.mkdir(parents=True, exist_ok=True)
    return d


def work_dir(event: pathlib.Path) -> pathlib.Path:
    d = media_dir(event) / "work"
    d.mkdir(exist_ok=True)
    return d


def clip_path(event: pathlib.Path, name: str) -> pathlib.Path:
    """The clip for talk folder `name` (e.g. 02-david-mihal), kept beside the
    event's raw files rather than in the talk folder."""
    return media_dir(event) / f"{name}.mp4"
