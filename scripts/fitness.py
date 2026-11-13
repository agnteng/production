#!/usr/bin/env python3
"""Fitness checks: what a healthy repository looks like (docs/adr/0005).

    python3 scripts/fitness.py              repo checks (fast, no network)
    python3 scripts/fitness.py --render     built decks match tests/snapshots/
    python3 scripts/fitness.py --render --update   rewrite the snapshots on purpose
    python3 scripts/fitness.py --live       production answers as it should

Every check exists because its failure happened once. Exit 1 if any fails.

The internal-names check reads its denylist from PUBLIC_DENYLIST (the pattern
text itself, which CI supplies as a secret) or from the workspace this
checkout sits in. The patterns never live in this public repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FAILURES: list[str] = []


def fail(check: str, msg: str) -> None:
    FAILURES.append(f"{check}: {msg}")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, check=True).stdout


def tracked() -> list[str]:
    return [p for p in git("ls-files", "-z").split("\0") if p]


# ── internal names (org ADR: public repositories name no infrastructure) ──

GENERIC = [
    r"op://",                                        # secret-store references
    r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",            # private IPv4
    r"\b192\.168\.\d{1,3}\.\d{1,3}\b",
    r"\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
    r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b",  # CGNAT / tailnets
    r"/Users/[a-z0-9_-]+/",                          # local home paths
    r"/home/[a-z0-9_-]+/",
]
SKIP_FILES = {"scripts/fitness.py", "pnpm-lock.yaml"}


def denylist() -> list[str]:
    text = os.environ.get("PUBLIC_DENYLIST", "")
    if not text:
        f = ROOT.parent.parent / "private" / "denylist.txt"
        if ROOT.parent.name == "repos" and f.exists():
            text = f.read_text()
    pats = [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not pats:
        print("  note: no private denylist (PUBLIC_DENYLIST or the workspace); "
              "checking generic patterns only", file=sys.stderr)
    return pats


def check_internal_names() -> None:
    rx = re.compile("|".join(f"(?:{p})" for p in GENERIC + denylist()), re.I)

    def scan(where: str, text: str) -> None:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            # Report where, never the matched text: CI logs are public.
            fail("internal-names", f"{where}:{line} matches a denylisted pattern")
            return

    for path in tracked():
        if path in SKIP_FILES:
            continue
        p = ROOT / path
        try:
            scan(path, p.read_text())
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
    for sha in git("rev-list", "HEAD").split():
        scan(f"commit {sha[:7]} message", git("log", "-1", "--format=%B", sha))
    extra = os.environ.get("FITNESS_EXTRA_TEXT", "")
    if extra:
        scan("pull request title/body", extra)


# ── media and scratch stay out of git (org ADR: media never enters git) ──

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".wav", ".m4a", ".mp3", ".mxf"}
SCRATCH_DIRS = {"raw", "work", "upload", "clips"}
MAX_BYTES = 5_000_000


def check_media() -> None:
    for path in tracked():
        p = Path(path)
        if p.suffix.lower() in MEDIA_EXT:
            fail("media", f"{path} is a media file")
        elif path.startswith("content/") and SCRATCH_DIRS & set(p.parts):
            fail("media", f"{path} is inside a media/scratch folder")
        elif (ROOT / p).is_file() and (ROOT / p).stat().st_size > MAX_BYTES:
            fail("media", f"{path} is over {MAX_BYTES // 1_000_000} MB")


# ── event.json shape (docs/adr/0001) ──

def check_events() -> None:
    public = ROOT / "apps" / "branding" / "public"
    for f in sorted((ROOT / "content").glob("*/event.json")):
        where = f.relative_to(ROOT)
        try:
            e = json.loads(f.read_text())
        except json.JSONDecodeError as err:
            fail("events", f"{where}: not JSON ({err})")
            continue
        if e.get("date") != f.parent.name:
            fail("events", f"{where}: date {e.get('date')!r} is not the folder name")
        for k in ("city", "venue", "tonight"):
            if not isinstance(e.get(k), str) or not e[k]:
                fail("events", f"{where}: needs a non-empty {k!r}")
        if not isinstance(e.get("number"), int):
            fail("events", f"{where}: needs an integer 'number'")
        luma = e.get("luma")
        if luma is not None:
            if not str(luma.get("apiId", "")).startswith("evt-"):
                fail("events", f"{where}: luma.apiId should start with evt-")
            if not str(luma.get("url", "")).startswith("https://"):
                fail("events", f"{where}: luma.url should be an https URL")
            if not re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d", str(luma.get("startAt", ""))):
                fail("events", f"{where}: luma.startAt should be an ISO timestamp")
        for i, s in enumerate(e.get("speakers", [])):
            if not s.get("name") or not s.get("title"):
                fail("events", f"{where}: speaker {i} needs name and title")
            photo = s.get("photo")
            if photo and not (public / photo.lstrip("/")).is_file():
                fail("events", f"{where}: speaker {i} photo {photo} does not exist")


# ── generated text in sync (docs/adr/0003) ──

def check_youtube_md() -> None:
    import youtube_md
    for event in sorted(p for p in (ROOT / "content").iterdir() if p.is_dir()):
        for folder in sorted(p for p in event.iterdir() if p.is_dir() and p.name[:2].isdigit()):
            want = youtube_md.for_talk(folder)
            if want is None:
                continue
            md = folder / "youtube.md"
            if not md.exists() or md.read_text() != want:
                fail("youtube-md", f"{md.relative_to(ROOT)} is stale: run scripts/youtube_md.py")


# ── rendered decks unchanged (refactors must not alter what's on screen) ──

PAGES = ["", "brand-guidelines/", "sponsorship/", "slides/",
         "slides/lisbon-2026-07-29/", "slides/lisbon-2026-08-26/",
         "slides/lisbon-2026-09-23/", "slides/lisbon-2026-11-11/"]
SNAPSHOTS = ROOT / "tests" / "snapshots"
NORMALISE = [
    (re.compile(r"/_astro/[A-Za-z0-9_.-]+"), "/_astro/X"),
    (re.compile(r'astro-island uid="[^"]*"'), "astro-island"),
    (re.compile(r'(component-url|renderer-url|before-hydration-url)="[^"]*"'), r'\1="X"'),
]


def normalise(html: str) -> str:
    for rx, rep in NORMALISE:
        html = rx.sub(rep, html)
    return html


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_render(update: bool) -> None:
    entry = ROOT / "apps" / "branding" / "dist" / "server" / "entry.mjs"
    if not entry.exists():
        fail("render", "no build: run `LUMA_API_KEY= pnpm --filter branding build` first")
        return
    port = free_port()
    env = {**os.environ, "HOST": "127.0.0.1", "PORT": str(port), "LUMA_API_KEY": ""}
    srv = subprocess.Popen(["node", str(entry)], env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        for page in PAGES:
            name = (page.strip("/").replace("/", "_") or "index") + ".html"
            html = normalise(urllib.request.urlopen(
                f"http://127.0.0.1:{port}/{page}", timeout=10).read().decode())
            snap = SNAPSHOTS / name
            if update:
                snap.write_text(html)
            elif not snap.exists():
                fail("render", f"no snapshot for /{page}: run with --update")
            elif snap.read_text() != html:
                fail("render", f"/{page} renders differently from tests/snapshots/{name}")
    finally:
        srv.terminate()
        srv.wait()
    if update:
        print(f"  wrote {len(PAGES)} snapshots to {SNAPSHOTS.relative_to(ROOT)}")


# ── production (org ADR: deploys are verified live) ──

def get(url: str) -> tuple[int, bytes]:
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "agnteng-fitness"}), timeout=20)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def check_live() -> None:
    b, s = "https://branding.agnteng.com", "https://sponsors.agnteng.com"
    for page in PAGES:
        code, _ = get(f"{b}/{page}")
        if code != 200:
            fail("live", f"{b}/{page} answered {code}")
    code, body = get(f"{b}/api/audience.json")
    try:
        guests = json.loads(body).get("totalGuests", 0) if code == 200 else 0
    except json.JSONDecodeError:
        guests = 0
    if not guests:
        fail("live", "api/audience.json reports no guests: the build lost LUMA_API_KEY")
    if get(f"{s}/")[0] != 200:
        fail("live", f"{s}/ is not serving the sponsor deck")
    if get(f"{s}/brand-guidelines/")[0] != 404:
        fail("live", f"{s} serves more than the sponsor deck")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--update", action="store_true", help="with --render: rewrite snapshots")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    if args.live:
        checks = [("live", check_live)]
    elif args.render:
        checks = [("render", lambda: check_render(args.update))]
    else:
        checks = [("internal-names", check_internal_names), ("media", check_media),
                  ("events", check_events), ("youtube-md", check_youtube_md)]
    for name, fn in checks:
        before = len(FAILURES)
        fn()
        print(f"  {'ok  ' if len(FAILURES) == before else 'FAIL'} {name}")
    for f in FAILURES:
        print(f"  ✗ {f}", file=sys.stderr)
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
